import csv
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tools import make_map

ROOT = Path(__file__).resolve().parent.parent

ROW = {"team_id": "1", "team_name": "Near", "team_zipCode": "98101",
       "team_coordinates": "POINT (-122.33 47.61)", "event_id": "SEA", "event_zipCode": "98101",
       "event_coordinates": "POINT (-122.33 47.61)", "drive_minutes": "5.0", "drive_distance": "1.0",
       "from_manual_override": "false", "flagged_for_manual_review": "false", "flagged_reason": ""}


def row(**changes):
    return {**ROW, **changes}


class BuildTest(unittest.TestCase):
    def test_team_without_coordinates_is_listed_not_plotted(self):
        data = make_map.build([row(), row(team_id="2", team_zipCode="98999", team_coordinates="",
                                          event_id="", event_coordinates="",
                                          flagged_reason="unassigned: zip code not found")], {})
        self.assertEqual([t["id"] for t in data["teams"]], ["1"])
        self.assertEqual(data["unplotted"], [{"id": "2", "zip": "98999", "reason": "unassigned: zip code not found"}])
        self.assertEqual({r["key"]: r["count"] for r in data["rules"]}["unassigned"], 1)

    def test_reasons_map_to_rules(self):
        reasons = "3 or fewer teams in zip (1); looks closer on the map: TAC is 5.0 mi straight-line but 40.0 min farther by road"
        t = make_map.build([row(flagged_reason=reasons)], {})["teams"][0]
        self.assertEqual(t["rules"], ["looks_closer", "small_zip"])

    def test_empty_event_is_placed_at_a_venue_sharing_its_zip(self):
        events = [{"event_id": "SEA", "event_zipCode": "98101", "capacity": "2", "teams": "1", "fill_percent": "50",
                   "flagged_for_manual_review": "false", "flagged_reason": ""},
                  {"event_id": "SEA-SUN", "event_zipCode": "98101", "capacity": "2", "teams": "0", "fill_percent": "0",
                   "flagged_for_manual_review": "true", "flagged_reason": "empty: no teams placed"}]
        data = make_map.build([row()], {}, events)
        self.assertEqual(data["venues"][0]["codes"], ["SEA", "SEA-SUN"])
        self.assertEqual({e["code"]: e["at"] for e in data["events"]}["SEA-SUN"], (47.61, -122.33))

    def test_thresholds_from_config_appear_in_titles(self):
        titles = {r["key"]: r["title"] for r in make_map.build([row()], {"small_zip": 2})["rules"]}
        self.assertEqual(titles["small_zip"], "2 or fewer teams in zip")


class PageTest(unittest.TestCase):
    def run_map(self, rows, *extra):
        d = Path(tempfile.mkdtemp())
        with open(d / "in.csv", "w", newline="") as f:
            w = csv.DictWriter(f, list(ROW))
            w.writeheader()
            w.writerows(rows)
        out = subprocess.run([sys.executable, "tools/make_map.py", "--input", d / "in.csv", "--out", d / "map.html",
                              "--events", d / "none.csv", *extra], cwd=ROOT, capture_output=True, text=True)
        return out, d / "map.html"

    def test_page_has_collapsible_sections_and_ties_unassigned_to_the_card(self):
        _, page = self.run_map([row()])
        html = page.read_text()
        for title in ("Review flags", "Filters", "How to read the map"):
            self.assertIn(f">{title}</summary>", html)
        self.assertIn('on.has("unassigned")', html)  # the Unassigned box also shows or hides the not-located card

    def test_values_cannot_close_the_script_block(self):
        _, page = self.run_map([row(team_name="</script><img src=x onerror=alert(1)>")])
        html = page.read_text()
        self.assertEqual(html.count("</script>"), 2)  # Leaflet's tag and the page's own
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
        self.assertEqual(data["teams"][0]["name"], "</script><img src=x onerror=alert(1)>")

    def test_serve_binds_localhost_and_serves_the_page(self):
        d = Path(tempfile.mkdtemp())
        with open(d / "in.csv", "w", newline="") as f:
            w = csv.DictWriter(f, list(ROW)); w.writeheader(); w.writerow(row())
        proc = subprocess.Popen([sys.executable, "tools/make_map.py", "--input", d / "in.csv", "--out", d / "map.html",
                                 "--events", d / "none.csv", "--serve", "--port", "8799"],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for _ in range(50):
                try:
                    page = urllib.request.urlopen("http://127.0.0.1:8799/map.html", timeout=1).read().decode()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("server did not start")
            self.assertIn("Review flags", page)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

    def test_server_binds_loopback_only(self):
        page = Path(tempfile.mkdtemp()) / "map.html"
        page.write_text("x")
        httpd = make_map.make_server(page, 0)  # port 0: any free port
        try:
            self.assertEqual(httpd.server_address[0], "127.0.0.1")
        finally:
            httpd.server_close()

    def test_server_serves_only_the_map(self):
        import threading
        d = Path(tempfile.mkdtemp())
        (d / "map.html").write_text("<p>map</p>")
        (d / "teams.csv").write_text("1,Secret Team,98101\n")
        httpd = make_map.make_server(d / "map.html", 0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            page = urllib.request.urlopen(base + "/")  # redirected to the map
            self.assertEqual(page.read().decode(), "<p>map</p>")
            self.assertEqual(page.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
            for path in ("/teams.csv", "/../teams.csv", "/map.html/../teams.csv", "/.data/"):
                with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(base + path)
                self.assertEqual(e.exception.code, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
