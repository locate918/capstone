"""
geocode_venues.py
Backfill latitude/longitude for all venues in Supabase using Google Maps Geocoding API.

Usage:
  1. Set environment variables (or edit the values below):
       SUPABASE_URL=https://your-project.supabase.co
       SUPABASE_KEY=your-service-role-key
       GOOGLE_MAPS_API_KEY=your-google-api-key

  2. pip install requests (should already be in your venv)

  3. python geocode_venues.py

What it does:
  - Fetches all venues that have an address but no lat/lng
  - Geocodes each address via Google Maps Geocoding API
  - Updates the venue row in Supabase with the coordinates
  - Prints a summary of what was updated vs. what failed
"""

import os
import sys
import time
import requests

# ── Configuration ─────────────────────────────────────────────────────────────
# Set these as environment variables or hardcode for quick testing

from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Default city/state to append if not in the address already
DEFAULT_SUFFIX = "Tulsa, OK"

# Google Geocoding endpoint
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def check_config():
    """Validate that all required config is set."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not GOOGLE_MAPS_API_KEY:
        missing.append("GOOGLE_MAPS_API_KEY")

    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("\nSet them before running:")
        print("  export SUPABASE_URL=https://your-project.supabase.co")
        print("  export SUPABASE_KEY=your-service-role-key")
        print("  export GOOGLE_MAPS_API_KEY=your-google-api-key")
        sys.exit(1)


def fetch_venues_missing_coords():
    """Fetch all venues that have an address but no coordinates."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # PostgREST query: address is not null AND (latitude is null OR longitude is null)
    url = (
        f"{SUPABASE_URL}/rest/v1/venues"
        f"?address=not.is.null"
        f"&or=(latitude.is.null,longitude.is.null)"
        f"&select=id,name,address,city"
        f"&order=name"
    )

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def geocode_address(address, city="Tulsa", state="OK"):
    """
    Geocode a single address using Google Maps Geocoding API.
    Returns (latitude, longitude) or None on failure.
    """
    # Build a full address string for better accuracy
    full_address = address.strip()

    # Append city/state if not already included
    lower = full_address.lower()
    if "tulsa" not in lower and "ok" not in lower:
        full_address = f"{full_address}, {city or 'Tulsa'}, OK"
    elif "ok" not in lower:
        full_address = f"{full_address}, OK"

    params = {
        "address": full_address,
        "key": GOOGLE_MAPS_API_KEY,
        # Bias results toward Tulsa metro area
        "bounds": "35.9|-96.2|36.3|-95.7",
    }

    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] == "OK" and data["results"]:
            loc = data["results"][0]["geometry"]["location"]
            return (loc["lat"], loc["lng"])
        else:
            print(f"  Geocoding returned status: {data['status']}")
            return None

    except Exception as e:
        print(f"  Geocoding error: {e}")
        return None


def update_venue_coords(venue_id, lat, lng):
    """Update a venue's coordinates in Supabase."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    url = f"{SUPABASE_URL}/rest/v1/venues?id=eq.{venue_id}"
    payload = {"latitude": lat, "longitude": lng}

    resp = requests.patch(url, json=payload, headers=headers)
    resp.raise_for_status()
    return True


def main():
    check_config()

    print("=" * 60)
    print("Locate918 Venue Geocoder")
    print("=" * 60)

    # Step 1: Fetch venues needing coordinates
    print("\nFetching venues missing coordinates...")
    venues = fetch_venues_missing_coords()

    if not venues:
        print("All venues already have coordinates! Nothing to do.")
        return

    print(f"Found {len(venues)} venues to geocode.\n")

    # Step 2: Geocode each venue
    success = 0
    failed = []

    for i, venue in enumerate(venues, 1):
        name = venue["name"]
        address = venue["address"]
        city = venue.get("city", "Tulsa")

        print(f"[{i}/{len(venues)}] {name}")
        print(f"  Address: {address}")

        coords = geocode_address(address, city)

        if coords:
            lat, lng = coords
            print(f"  Coords:  ({lat}, {lng})")

            try:
                update_venue_coords(venue["id"], lat, lng)
                print(f"  ✓ Updated!")
                success += 1
            except Exception as e:
                print(f"  ✗ Failed to save: {e}")
                failed.append((name, "save error"))
        else:
            print(f"  ✗ Could not geocode")
            failed.append((name, "geocoding failed"))

        # Small delay to respect API rate limits
        if i < len(venues):
            time.sleep(0.2)

    # Step 3: Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total venues processed: {len(venues)}")
    print(f"  Successfully geocoded:  {success}")
    print(f"  Failed:                 {len(failed)}")

    if failed:
        print("\n  Failed venues:")
        for name, reason in failed:
            print(f"    - {name} ({reason})")
        print("\n  For failed venues, you can manually look up coordinates")
        print("  on Google Maps and run:")
        print("    UPDATE venues SET latitude = ?, longitude = ? WHERE name = '?';")

    print("\nDone! Your Leaflet map should now show accurate pins.")


if __name__ == "__main__":
    main()