"""
Reads the ocean-conservation-orgs Google Sheet and writes organisations.json
in the GeoJSON FeatureCollection format the map's index.html fetches at runtime.

Several tabs can feed the map (see WORKSHEET_NAMES). They must share the same
column headers. Every tab uses the same rule for the "added?" column.

Run by the GitHub Actions workflow in .github/workflows/update-map-data.yml
on a weekly schedule (and on-demand via "Run workflow").
"""

import json
import re
import sys

# --- Configuration: edit these lines for your sheet -----------------------
SHEET_ID = "PASTE_YOUR_GOOGLE_SHEET_ID_HERE"   # from the sheet's URL, the long
                                                 # id between /d/ and /edit

# Tab names, spelled exactly as they appear at the bottom of the spreadsheet
# (case-sensitive). If the same organisation appears in more than one tab, the
# tab listed first wins.
WORKSHEET_NAMES = ["Clean", "manual-additions"]
# ---------------------------------------------------------------------------

OUTPUT_PATH = "organisations.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
REQUIRED_HEADERS = ["Name", "Latitude", "Longitude"]


def clean_float(value):
    """Handle stray trailing commas in lat/lon cells (a known issue in this sheet)."""
    if value is None:
        return None
    s = str(value).strip().rstrip(",").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalise_name(name):
    """Key used to spot the same organisation in two tabs: case and spacing ignored."""
    return re.sub(r"\s+", " ", name).strip().lower()


def is_ready(row):
    """The "added?" gate: 'yes'/'y'/'true' publishes, 'no' (or anything else) does not.
    An empty cell publishes, as before."""
    flag = row.get("added?", "").strip().lower()
    return not flag or flag in ("yes", "y", "true")


def read_tab(spreadsheet, tab_name):
    """Return the tab's rows as dicts keyed by header. Everything stays a string,
    so phone numbers keep any leading zero."""
    values = spreadsheet.worksheet(tab_name).get_all_values()
    if not values:
        raise SystemExit(f"Tab '{tab_name}' is empty (no header row).")

    headers = [h.strip() for h in values[0]]
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise SystemExit(f"Tab '{tab_name}' is missing required column(s): {missing}. "
                         f"Headers found: {[h for h in headers if h]}")

    rows = []
    for raw in values[1:]:
        rows.append({h: (raw[i].strip() if i < len(raw) else "")
                     for i, h in enumerate(headers) if h})
    return rows


def build_features(tabs):
    """tabs: ordered list of (tab_name, rows). Returns (features, report)."""
    features = []
    seen = {}  # normalised name -> tab it first appeared in
    report = {}

    for tab_name, rows in tabs:
        stats = {"published": 0, "not_ready": 0, "no_coords": [], "duplicates": []}

        for row in rows:
            name = row.get("Name", "").strip()
            if not name:
                continue  # blank row

            if not is_ready(row):
                stats["not_ready"] += 1
                continue

            lat = clean_float(row.get("Latitude"))
            lon = clean_float(row.get("Longitude"))
            if lat is None or lon is None:
                stats["no_coords"].append(name)
                continue

            key = normalise_name(name)
            if key in seen:
                stats["duplicates"].append(f"{name} (already in '{seen[key]}')")
                continue
            seen[key] = tab_name

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "Name": name,
                    "Type": row.get("Type", ""),
                    "Description": row.get("Description", ""),
                    "Website": row.get("Website", ""),
                    "Email": row.get("Email", ""),
                    "Phone": row.get("Phone", ""),
                    "City": row.get("City", ""),
                    "Volunteering": row.get("Volunteering", ""),
                    "Volunteering_details": row.get("Volunteering_details", ""),
                }
            })
            stats["published"] += 1

        report[tab_name] = stats

    return features, report


def main():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    spreadsheet = gspread.authorize(creds).open_by_key(SHEET_ID)

    # A tab that can't be found raises an error and fails the run, so a typo in
    # a tab name is noticed rather than silently dropping its organisations.
    tabs = [(name, read_tab(spreadsheet, name)) for name in WORKSHEET_NAMES]
    features, report = build_features(tabs)

    if not features:
        raise SystemExit("No organisations to publish; leaving organisations.json unchanged.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(features)} organisations to {OUTPUT_PATH}")
    for tab_name, s in report.items():
        print(f"[{tab_name}] published {s['published']}, "
              f"not marked ready {s['not_ready']}, "
              f"missing coordinates {len(s['no_coords'])}, "
              f"duplicates skipped {len(s['duplicates'])}")
        if s["no_coords"]:
            print(f"  missing/invalid coordinates: {s['no_coords']}")
        if s["duplicates"]:
            print(f"  duplicates: {s['duplicates']}")


if __name__ == "__main__":
    sys.exit(main())
