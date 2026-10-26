import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import region

ROOT = Path(__file__).resolve().parent.parent


class RegionTest(unittest.TestCase):
    def test_parse_states(self):
        self.assertEqual(region.parse_states(" wa, or "), ["WA", "OR"])
        self.assertEqual(region.parse_states(["wa", "OR"]), ["WA", "OR"])
        for bad in ("", "Washington", "W1", "WA,XX", []):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                region.parse_states(bad)

    def test_states_read_from_config_file(self):
        cfg = Path(tempfile.mkdtemp()) / "sorter.toml"
        cfg.write_text('# states = ["XX"] in a comment\nprogram = "FLL"\nstates = ["WA", "ID"]\n')
        self.assertEqual(region.region_states(cfg), ["WA", "ID"])

    def test_config_without_states_stops(self):
        cfg = Path(tempfile.mkdtemp()) / "sorter.toml"
        cfg.write_text('program = "FLL"\n')
        with self.assertRaises(SystemExit):
            region.region_states(cfg)

    def test_tag_is_order_independent(self):
        self.assertEqual(region.tag(["WA", "OR"]), region.tag(["OR", "WA"]))
        self.assertEqual(region.tag(["WA", "OR"]), "or-wa")

    def test_extract_urls(self):
        self.assertEqual(region.extract_urls(["WA", "OR"]), [
            "https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf",
            "https://download.geofabrik.de/north-america/us/oregon-latest.osm.pbf"])

    def test_committed_region_is_wa_or(self):
        self.assertEqual(region.region_states(), ["WA", "OR"])

    def test_shell_interface(self):
        out = subprocess.run([sys.executable, "tools/region.py", "tag"], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "or-wa")


if __name__ == "__main__":
    unittest.main()
