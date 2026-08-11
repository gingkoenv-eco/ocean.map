"""
Reads the ocean-conservation-orgs Google Sheet and writes organisations.json
in the GeoJSON FeatureCollection format the map's index.html fetches at runtime.

Run by the GitHub Actions workflow in .github/workflows/update-map-data.yml
on a weekly schedule (and on-demand via "Run workflow").
"""

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

# --- Configuration: edit these two lines for your sheet -------------------
SHEET_ID = "1rHbdODAygn0zJfDwMvmePOyxQKcBUuqIz75B5JjsLd4"   # from the sheet's URL, the long
                                                 # id between /d/ and /edit
WORKSHEET_NAME = "Clean"                        # the tab name holding the
                                                 # cleaned data (rename to match yours)
# ---------------------------------------------------------------------------

OUTPUT_PATH = "organisations.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


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


def main():
    creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    rows = worksheet.get_all_records()  # list of dicts, keyed by header row

    features = []
    skipped_no_coords = []
    skipped_not_marked_ready = 0

    for row in rows:
        name = str(row.get("Name", "")).strip()
        if not name:
            continue  # blank row

        # Only publish rows explicitly marked ready in the "added?" column.
        # Remove this block entirely if you don't use that column as a gate.
        added_flag = str(row.get("added?", "")).strip().lower()
        if added_flag and added_flag not in ("yes", "y", "true"):
            skipped_not_marked_ready += 1
            continue

        lat = clean_float(row.get("Latitude"))
        lon = clean_float(row.get("Longitude"))
        if lat is None or lon is None:
            skipped_no_coords.append(name)
            continue

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "Name": name,
                "Type": str(row.get("Type", "")).strip(),
                "Description": str(row.get("Description", "")).strip(),
                "Website": str(row.get("Website", "")).strip(),
                "Email": str(row.get("Email", "")).strip(),
                "Phone": str(row.get("Phone", "")).strip(),
                "City": str(row.get("City", "")).strip(),
                "Volunteering": str(row.get("Volunteering", "")).strip(),
                "Volunteering_details": str(row.get("Volunteering_details", "")).strip(),
            }
        })

    geojson = {"type": "FeatureCollection", "features": features}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(features)} organisations to {OUTPUT_PATH}")
    if skipped_not_marked_ready:
        print(f"Skipped {skipped_not_marked_ready} rows not marked ready ('added?' column)")
    if skipped_no_coords:
        print(f"Skipped {len(skipped_no_coords)} rows with missing/invalid coordinates: {skipped_no_coords}")


if __name__ == "__main__":
    main()
