#!/usr/bin/env python3
"""Write a one-file HTML map of the sorter's output, for reviewing flagged teams.

Each team is a dot colored by its assigned event; flagged teams have a red outline and
a thin line to their event. Click a dot for the team's event, travel and flag reasons.
A card explains each review rule with its threshold from sorter.toml and how many teams
it caught; checkboxes filter the map by rule.

The page embeds the team data, so it is written to .data/ (git-ignored) by default.
Do not commit or publish it. It loads Leaflet from unpkg.com (pinned by hash) and map
tiles from OpenStreetMap; those servers see which area is viewed, not team data.

OpenStreetMap's tile policy requires an HTTP Referer, which a page opened straight from
disk (file://) does not send, so the tiles come back "Access blocked". Serve it instead:

    python3 tools/make_map.py --serve      (writes the map, then serves it on 127.0.0.1:8765)
    then open http://127.0.0.1:8765/map.html, or the "Review map" port in a Codespace

Usage: python3 tools/make_map.py [--input .data/team_assignments.csv] [--out .data/map.html]
                                 [--events .data/event_summary.csv] [--serve] [--port 8765]
"""
import argparse
import csv
import http.server
import json
import math
import re
import sys
import tomllib
from pathlib import Path

POINT = re.compile(r"POINT \(([-\d.]+) ([-\d.]+)\)")
REVIEW_DEFAULTS = {"small_zip": 3, "large_zip": 30, "assigned_miles": 40, "nearest_miles": 75,
                   "travel_minutes": 90, "looks_closer_minutes": 30}


def rule_of(reason):
    """Which review rule produced one entry of flagged_reason."""
    for key, test in (
        ("unassigned", lambda r: r.startswith("unassigned")),
        ("small_zip", lambda r: "or fewer teams in zip" in r),
        ("large_zip", lambda r: "or more teams in zip" in r),
        ("assigned_miles", lambda r: r.startswith("assigned event over")),
        ("nearest_miles", lambda r: r.startswith("nearest event over")),
        ("looks_closer", lambda r: r.startswith("looks closer on the map")),
        ("travel", lambda r: r.startswith("travel over")),
    ):
        if test(reason):
            return key
    return "other"


def rule_text(review):
    g = lambda k: f"{review.get(k, REVIEW_DEFAULTS[k]):g}"
    return {
        "unassigned": ("Unassigned", "Not placed. The text after the colon says why and what to fix."),
        "small_zip": (f"{g('small_zip')} or fewer teams in zip",
                      "A small group, often placed wherever seats are left. Check it went somewhere sensible."),
        "large_zip": (f"{g('large_zip')} or more teams in zip",
                      "A large group placed as one block. It may fill an event by itself or need splitting."),
        "assigned_miles": (f"Assigned event over {g('assigned_miles')} miles",
                           "A long drive to the event the team was given."),
        "nearest_miles": (f"Nearest event over {g('nearest_miles')} miles",
                          "No event is close. A candidate for a new event location in future seasons."),
        "looks_closer": (f"Looks closer on the map ({g('looks_closer_minutes')}+ min)",
                         "An event that looks nearer is much longer by road: water or mountains in the way. "
                         "Usually correct; it explains a placement that looks wrong on the map."),
        "travel": (f"Travel over {g('travel_minutes')} minutes", "A long drive in time."),
        "other": ("Other", "A reason this map does not recognize."),
    }


def point(wkt):
    m = POINT.match(wkt or "")
    return (float(m.group(2)), float(m.group(1))) if m else None  # (lat, lon)


def build(rows, review, event_rows=()):
    events, teams, per_zip = {}, [], {}
    for r in rows:
        ev = point(r.get("event_coordinates"))
        if r.get("event_id") and ev:
            events.setdefault(ev, set()).add(r["event_id"])
    order = sorted({e for codes in events.values() for e in codes})
    # Empty events have no team rows, so place them from the summary's zip when another event shares it.
    by_zip = {}
    for r in rows:
        ev = point(r.get("event_coordinates"))
        if r.get("event_zipCode") and ev:
            by_zip[r["event_zipCode"]] = ev
    where = {code: p for p, codes in events.items() for code in codes}
    event_list = []
    for e in event_rows:
        p = where.get(e["event_id"]) or by_zip.get(e.get("event_zipCode", ""))
        if p:
            events.setdefault(p, set()).add(e["event_id"])
        event_list.append({"code": e["event_id"], "zip": e.get("event_zipCode", ""),
                           "teams": int(e.get("teams") or 0), "capacity": int(e.get("capacity") or 0),
                           "percent": int(e.get("fill_percent") or 0),
                           "flagged": e.get("flagged_for_manual_review") == "true",
                           "reason": e.get("flagged_reason", ""), "at": p})
    for r in rows:
        tp = point(r.get("team_coordinates"))
        if not tp:
            continue
        # Teams in one zip share a point; spread them in a small spiral so each is clickable.
        i = per_zip.setdefault(r["team_zipCode"], 0)
        per_zip[r["team_zipCode"]] = i + 1
        a, d = i * 2.39996, 0.0025 * math.sqrt(i)
        reasons = [x for x in (r.get("flagged_reason") or "").split("; ") if x]
        teams.append({
            "lat": tp[0] + d * math.sin(a), "lon": tp[1] + d * math.cos(a),
            "id": r["team_id"], "name": r.get("team_name", ""), "zip": r["team_zipCode"],
            "event": r.get("event_id", ""), "ev": point(r.get("event_coordinates")),
            "minutes": r.get("drive_minutes", ""), "miles": r.get("drive_distance", ""),
            "override": r.get("from_manual_override") == "true",
            "reasons": reasons, "rules": sorted({rule_of(x) for x in reasons}),
        })
    counts = {}  # from every row, so the card matches the sorter's summary even for unplotted teams
    for r in rows:
        for k in {rule_of(x) for x in (r.get("flagged_reason") or "").split("; ") if x}:
            counts[k] = counts.get(k, 0) + 1
    unplotted = [{"id": r.get("team_id", ""), "zip": r.get("team_zipCode", ""),
                  "reason": next((x for x in (r.get("flagged_reason") or "").split("; ")
                                  if x.startswith("unassigned")), "")}
                 for r in rows if not point(r.get("team_coordinates"))]
    return {
        "teams": teams, "eventOrder": order,
        "venues": [{"lat": p[0], "lon": p[1], "codes": sorted(c)} for p, c in events.items()],
        "rules": [{"key": k, "title": t, "text": d, "count": counts.get(k, 0)}
                  for k, (t, d) in rule_text(review).items() if counts.get(k) or k != "other"],
        "unplotted": unplotted,
        "events": event_list,
    }


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>Team assignments review map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
 integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
 integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<style>
 html, body, #map { height: 100%; margin: 0; font: 14px/1.4 system-ui, sans-serif; }
 #card { position: absolute; top: 10px; right: 10px; z-index: 1000; width: 330px; max-height: 90vh;
   overflow: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,.25); padding: 12px 14px; }
 #card h2 { font-size: 16px; margin: 0 0 4px; }
 #card .sub { color: #555; margin-bottom: 8px; }
 #card label { display: block; margin: 8px 0 0; font-weight: 600; cursor: pointer; }
 #card .why { color: #444; font-weight: normal; margin: 2px 0 0 22px; }
 #card .n { color: #b00; font-weight: 600; }
 #card summary { cursor: pointer; font-weight: 700; }
 #card summary.top { font-size: 16px; margin-bottom: 4px; }
 #card details.section { border-top: 1px solid #ddd; margin-top: 10px; padding-top: 8px; }
 #card details.section > summary { font-size: 14px; }
 #events ul { list-style: none; margin: 0; padding: 0; }
 #events li { margin: 4px 0; }
 #events a { font-weight: 600; color: #0645ad; }
 .popup b { display: inline-block; min-width: 70px; }
 .popup ul { margin: 4px 0 0; padding-left: 18px; }
 #unplotted { display: none; position: absolute; bottom: 24px; left: 10px; z-index: 1000; max-width: 360px;
   max-height: 40vh; overflow: auto; background: #fff8e1; border: 1px solid #e0a800; border-radius: 8px;
   box-shadow: 0 2px 10px rgba(0,0,0,.25); padding: 10px 14px; }
 #unplotted summary { font-size: 15px; font-weight: 700; cursor: pointer; }
 #unplotted ul { margin: 4px 0 6px; padding-left: 18px; }
 #unplotted li div { color: #555; }
</style></head><body>
<div id="map"></div>
<div id="unplotted"><details open><summary id="unplotted-title"></summary><div id="unplotted-body"></div></details></div>
<div id="card">
 <details open>
  <summary class="top">Review flags</summary>
  <div class="sub" id="summary"></div>
  <details open class="section">
   <summary>Filters</summary>
   <label><input type="checkbox" id="show-unflagged" checked> Teams with no flags</label>
   <div id="rules"></div>
  </details>
  <details open class="section" id="events-box" hidden>
   <summary id="events-title">Events</summary>
   <div id="events"></div>
  </details>
  <details class="section">
   <summary>How to read the map</summary>
   <p class="sub">Dot color = assigned event. Red outline = flagged; the dashed line runs to the team's
    event. Squares are venues; a red square has an empty or under-filled event. Teams in one zip are
    spread slightly so each can be clicked; positions are zip centres, not addresses.</p>
  </details>
 </details>
</div>
<script>
const DATA = __DATA__;
const map = L.map("map");
if (location.protocol === "file:") {
  const warn = el("div", "Map tiles are blocked when this page is opened as a file. Serve it locally: " +
    "python3 tools/make_map.py --serve, then open http://127.0.0.1:8765/map.html");
  warn.style.cssText = "position:absolute;top:10px;left:60px;z-index:1001;max-width:420px;background:#fdecea;" +
    "border:1px solid #d00;border-radius:8px;padding:8px 12px;box-shadow:0 2px 10px rgba(0,0,0,.25)";
  document.body.append(warn);
}
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18, attribution: "&copy; OpenStreetMap contributors",
  // OpenStreetMap requires a Referer on tile requests; set it per tile so a stricter page
  // policy (some proxies add one) cannot strip it.
  referrerPolicy: "strict-origin-when-cross-origin"}).addTo(map);
const hue = code => Math.round(360 * DATA.eventOrder.indexOf(code) / Math.max(1, DATA.eventOrder.length));
const color = code => code ? `hsl(${hue(code)}, 70%, 45%)` : "#999";

function el(tag, text) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; }
function row(box, label, value) {
  const d = el("div"); d.append(el("b", label), document.createTextNode(" " + value)); box.append(d);
}
function eventLink(code) {
  if (!code || !venueMarkers[code]) return document.createTextNode(code || "unassigned");
  const a = el("a", code); a.href = "#";
  a.addEventListener("click", ev => { ev.preventDefault(); focusEvent(code); });
  return a;
}
function popup(t) {
  const box = el("div"); box.className = "popup";
  box.append(el("strong", `${t.id} ${t.name}`));
  row(box, "Zip", t.zip);
  const ev = el("div"); ev.append(el("b", "Event"), document.createTextNode(" "), eventLink(t.event)); box.append(ev);
  if (t.minutes) row(box, "Drive", `${t.minutes} min, ${t.miles} mi`);
  if (t.override) row(box, "Placed", "by manual override");
  if (t.reasons.length) {
    const ul = el("ul");
    t.reasons.forEach(r => {
      const li = el("li");
      const m = r.match(/^(looks closer on the map: )([^ ]+)( is .*)$/);
      if (m && venueMarkers[m[2]]) li.append(document.createTextNode(m[1]), eventLink(m[2]), document.createTextNode(m[3]));
      else li.textContent = r;
      ul.append(li);
    });
    box.append(ul);
  }
  return box;
}

const layers = DATA.teams.map(t => {
  const flagged = t.reasons.length > 0;
  const dot = L.circleMarker([t.lat, t.lon], { radius: 6, weight: flagged ? 3 : 1,
    color: flagged ? "#d00" : "#333", fillColor: color(t.event), fillOpacity: 0.9 }).bindPopup(() => popup(t));
  const line = flagged && t.ev ? L.polyline([[t.lat, t.lon], t.ev], { color: "#d00", weight: 1, dashArray: "4 4" }) : null;
  return { t, dot, line };
});
const eventsByCode = Object.fromEntries(DATA.events.map(e => [e.code, e]));
function venuePopup(v) {
  const box = el("div"); box.className = "popup";
  v.codes.forEach(code => {
    const e = eventsByCode[code];
    const line = el("div"); line.append(el("b", code));
    line.append(document.createTextNode(e ? ` ${e.teams} of ${e.capacity} seats (${e.percent}%)` : ""));
    box.append(line);
    if (e && e.reason) { const why = el("div", e.reason); why.style.cssText = "color:#b00;margin:0 0 4px 12px"; box.append(why); }
  });
  return box;
}
const venueMarkers = {};
DATA.venues.forEach(v => {
  const flagged = v.codes.some(c => eventsByCode[c] && eventsByCode[c].flagged);
  const icon = L.divIcon({ className: "", iconSize: [14, 14],
    html: `<div style="width:12px;height:12px;border:2px solid ${flagged ? "#d00" : "#000"};` +
          `background:${color(v.codes[0])};${flagged ? "outline:2px solid #d00;" : ""}"></div>` });
  const m = L.marker([v.lat, v.lon], { icon, zIndexOffset: 1000 })
    .bindTooltip(v.codes.join(", ")).bindPopup(() => venuePopup(v)).addTo(map);
  v.codes.forEach(c => venueMarkers[c] = m);
});

function focusEvent(code) {
  const m = venueMarkers[code];
  if (!m) return;
  map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 11), { duration: 0.8 });
  map.once("moveend", () => m.openPopup());
}
if (DATA.events.length) {
  const box = document.getElementById("events");
  const flagged = DATA.events.filter(e => e.flagged);
  document.getElementById("events-title").textContent = `Events (${flagged.length} of ${DATA.events.length} flagged)`;
  document.getElementById("events-box").hidden = false;
  const list = el("ul");
  [...flagged, ...DATA.events.filter(e => !e.flagged)].forEach(e => {
    const li = el("li");
    const name = el(venueMarkers[e.code] ? "a" : "span", e.code);
    if (venueMarkers[e.code]) { name.href = "#"; name.addEventListener("click", ev => { ev.preventDefault(); focusEvent(e.code); }); }
    li.append(name, document.createTextNode(` ${e.teams}/${e.capacity}`));
    if (e.reason) { const why = el("div", e.reason); why.className = "why"; li.append(why); }
    if (!venueMarkers[e.code]) li.append(el("div", "No location to show on the map."));
    list.append(li);
  });
  box.append(list);
}

const rulesBox = document.getElementById("rules");
DATA.rules.forEach(r => {
  const label = el("label"); const cb = el("input"); cb.type = "checkbox"; cb.checked = true; cb.dataset.rule = r.key;
  const onMap = DATA.teams.filter(t => t.rules.includes(r.key)).length;
  const off = r.count - onMap;
  const n = el("span", off ? ` (${r.count}, ${off} not on map)` : ` (${r.count})`); n.className = "n";
  label.append(cb, document.createTextNode(" " + r.title), n);
  const why = el("div", r.text + (r.key === "unassigned" && DATA.unplotted.length
    ? " Teams with no location are listed in the card at bottom left; this box shows or hides it." : ""));
  why.className = "why";
  rulesBox.append(label, why);
});
const flaggedCount = DATA.teams.filter(t => t.reasons.length).length;
document.getElementById("summary").textContent =
  `${DATA.teams.length} teams on the map, ${flaggedCount} flagged` +
  (DATA.unplotted.length ? `, ${DATA.unplotted.length} not shown (see the card at bottom left)` : "") + ".";

if (DATA.unplotted.length) {
  const card = document.getElementById("unplotted");
  document.getElementById("unplotted-title").textContent = DATA.unplotted.length === 1
    ? "1 team is not on the map" : `${DATA.unplotted.length} teams are not on the map`;
  const ul = el("ul");
  DATA.unplotted.forEach(u => {
    const li = el("li");
    li.append(el("b", `Team ${u.id}`),
              document.createTextNode(` has a zip code we could not locate (${u.zip || "blank"}).`));
    if (u.reason) li.append(el("div", u.reason));
    ul.append(li);
  });
  document.getElementById("unplotted-body").append(ul,
    el("div", "Check the zip in the teams file, or place the team with a pre-assignment."));
  card.style.display = "block";
}

function refresh() {
  const on = new Set([...document.querySelectorAll("#rules input:checked")].map(c => c.dataset.rule));
  const unflagged = document.getElementById("show-unflagged").checked;
  layers.forEach(({ t, dot, line }) => {
    const show = t.rules.length ? t.rules.some(k => on.has(k)) : unflagged;
    [dot, line].forEach(l => l && (show ? l.addTo(map) : l.remove()));
  });
  if (DATA.unplotted.length) {
    document.getElementById("unplotted").style.display = on.has("unassigned") ? "block" : "none";
  }
}
document.getElementById("card").addEventListener("change", refresh);
refresh();
const pts = DATA.teams.map(t => [t.lat, t.lon]).concat(DATA.venues.map(v => [v.lat, v.lon]));
if (pts.length) map.fitBounds(pts, { padding: [20, 20] }); else map.setView([47.4, -120.7], 7);
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Write an HTML review map of the sorter's output")
    ap.add_argument("--input", default=".data/team_assignments.csv", help="Sorter output CSV")
    ap.add_argument("--out", default=".data/map.html", help="HTML file to write (keep it out of git)")
    ap.add_argument("--config", default="sorter.toml", help="Settings file, for the review thresholds")
    ap.add_argument("--events", default=".data/event_summary.csv", help="Event summary CSV from the sorter")
    ap.add_argument("--serve", action="store_true",
                    help="After writing the map, serve it on 127.0.0.1 until Ctrl+C")
    ap.add_argument("--port", type=int, default=8765, help="Port for --serve (default: 8765)")
    a = ap.parse_args()
    try:
        with open(a.input, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        sys.exit(f"{a.input} not found. Run the sorter first: python3 -m sorter.cli")
    event_rows = []
    if Path(a.events).exists():
        with open(a.events, newline="", encoding="utf-8-sig") as f:
            event_rows = list(csv.DictReader(f))
    else:
        print(f"Note: {a.events} not found; the map will not list events. Rerun the sorter to create it.")
    review = {}
    if Path(a.config).exists():
        with open(a.config, "rb") as f:
            review = tomllib.load(f).get("review", {})
    data = build(rows, review, event_rows)
    # Escape "<" so no value from the CSV can close the <script> block.
    blob = json.dumps(data).replace("<", "\\u003c")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(PAGE.replace("__DATA__", blob), encoding="utf-8")
    flagged = sum(1 for t in data["teams"] if t["reasons"])
    print(f"Wrote {a.out}: {len(data['teams'])} teams, {len(data['venues'])} venues, {flagged} flagged.")
    print("It contains team data: do not commit it or share it publicly.")
    if a.serve:
        serve(Path(a.out), a.port)
    else:
        print("To view it (map tiles need a web server, not a file:// URL), rerun with --serve.")


class MapHandler(http.server.BaseHTTPRequestHandler):
    """Serves the one map page and nothing else, so other files in .data/ (the team and
    event CSVs) cannot be listed or downloaded through the server. "/" redirects to the map."""
    page = None  # set by make_server

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/" + self.page.name)
            self.end_headers()
            return
        if path != "/" + self.page.name:
            self.send_error(404, "Only the map is served here")
            return
        body = self.page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def make_server(page, port):
    """An HTTP server for the map page only, bound to 127.0.0.1 so other machines cannot connect."""
    handler = type("BoundMapHandler", (MapHandler,), {"page": page})
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(page, port):
    """Serve the map's folder on this machine only, until Ctrl+C.

    In a Codespace the port is still forwarded to your browser; keep its visibility
    Private, since the page lists team names.
    """
    try:
        httpd = make_server(page, port)
    except OSError as e:
        sys.exit(f"Could not listen on 127.0.0.1:{port} ({e}). Pick another port with --port.")
    print(f"Serving http://127.0.0.1:{port}/{page.name}  (Ctrl+C to stop)")
    print("In a Codespace: open it from the Ports tab ('Review map'); keep the port Private.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
