"""
seed_places.py
==============
Seed the `places` table from Google Places API.
Covers bars, restaurants, nightclubs, breweries, etc. across Tulsa.

Usage:
    pip install requests python-dotenv
    python seed_places.py

Re-run quarterly to refresh ratings/hours.
Closed venues: set active=FALSE manually in Supabase.

Required in .env:
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_KEY=your-service-role-key
    GOOGLE_PLACES_API_KEY=your-api-key
"""

import os, sys, time, re, json, requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL   = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

NEARBY_URL  = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
DETAIL_FIELDS = (
    "name,place_id,formatted_address,vicinity,geometry,price_level,rating,"
    "user_ratings_total,formatted_phone_number,website,opening_hours,url,types"
)

# ── Tulsa metro search centers ────────────────────────────────────────────────
# Each entry: (lat, lng, neighborhood_label)
NEIGHBORHOODS = [
    # ── Tulsa proper ──────────────────────────────────────────────────────────
    (36.1563, -95.9929, "Downtown"),
    (36.1547, -95.9850, "Brady Arts"),
    (36.1600, -95.9750, "Pearl District"),
    (36.1530, -95.9700, "East Village"),
    (36.1450, -95.9950, "Blue Dome"),
    (36.1300, -95.9800, "Cherry Street"),
    (36.1220, -95.9780, "Brookside"),
    (36.1100, -95.9600, "Midtown"),
    (36.1050, -95.9300, "East Tulsa"),
    (36.0850, -95.9700, "South Tulsa"),
    (36.1400, -96.0300, "West Tulsa"),
    (36.0700, -96.0600, "Bixby"),
    (36.0380, -95.9670, "Jenks"),

    # ── Broken Arrow ──────────────────────────────────────────────────────────
    (36.0526, -95.7974, "Broken Arrow - Downtown / Rose District"),
    (36.0300, -95.8400, "Broken Arrow - Central"),
    (36.0100, -95.7700, "Broken Arrow - South"),

    # ── Owasso ────────────────────────────────────────────────────────────────
    (36.2695, -95.8547, "Owasso"),

    # ── Sand Springs ──────────────────────────────────────────────────────────
    (36.1395, -96.1092, "Sand Springs"),

    # ── Sapulpa ───────────────────────────────────────────────────────────────
    (35.9987, -96.1142, "Sapulpa"),

    # ── Claremore ─────────────────────────────────────────────────────────────
    (36.3126, -95.6158, "Claremore"),

    # ── Glenpool / Bixby South ────────────────────────────────────────────────
    (35.9548, -96.0076, "Glenpool"),

    # ── Catoosa (Hard Rock area) ──────────────────────────────────────────────
    (36.1887, -95.7449, "Catoosa"),
]

RADIUS = 1200  # meters (~0.75 miles)

# ── What to search: (google_type, our_place_type, optional_keyword) ───────────
SEARCHES = [
    ("bar",        "bar",          None),
    ("bar",        "tavern",       "tavern"),
    ("bar",        "tavern",       "dive bar"),
    ("night_club", "nightclub",    None),
    ("bar",        "cocktail_bar", "cocktail"),
    ("bar",        "brewery",      "brewery"),
    ("bar",        "brewery",      "taproom"),
    ("bar",        "wine_bar",     "wine bar"),
    ("bar",        "sports_bar",   "sports bar"),
    ("bar",        "karaoke_bar",  "karaoke"),
    ("restaurant", "restaurant",   None),
    ("cafe",       "cafe",         None),
]


# ── Supabase ───────────────────────────────────────────────────────────────────
def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def existing_place_ids() -> set:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/places?select=google_place_id",
        headers=sb_headers(), timeout=10
    )
    r.raise_for_status()
    return {x["google_place_id"] for x in r.json() if x.get("google_place_id")}

def upsert_place(row: dict) -> bool:
    headers = {**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/places?on_conflict=google_place_id",
        json=row, headers=headers, timeout=10
    )
    if r.status_code not in (200, 201):
        print(f"    ✗ Upsert failed ({r.status_code}): {r.text[:120]}")
        return False
    return True


# ── Google Places ──────────────────────────────────────────────────────────────
def nearby_search(lat, lng, gtype, keyword=None) -> list:
    """NearbySearch with auto-pagination (up to 60 results)."""
    params = {"location": f"{lat},{lng}", "radius": RADIUS, "type": gtype, "key": GOOGLE_API_KEY}
    if keyword:
        params["keyword"] = keyword
    results = []
    while True:
        data = requests.get(NEARBY_URL, params=params, timeout=10).json()
        results.extend(data.get("results", []))
        token = data.get("next_page_token")
        if not token or len(results) >= 60:
            break
        time.sleep(2)  # Google requires delay before next_page_token is valid
        params = {"pagetoken": token, "key": GOOGLE_API_KEY}
    return results

def get_details(place_id: str) -> dict:
    r = requests.get(
        DETAILS_URL,
        params={"place_id": place_id, "fields": DETAIL_FIELDS, "key": GOOGLE_API_KEY},
        timeout=10
    )
    return r.json().get("result", {})


# ── Row builder ────────────────────────────────────────────────────────────────
def nearest_hood(lat, lng) -> str:
    return min(NEIGHBORHOODS, key=lambda n: (n[0]-lat)**2 + (n[1]-lng)**2)[2]

def build_tags(details: dict, our_type: str) -> list:
    tags = set()
    gtypes = details.get("types", [])
    type_tag_map = {
        "bar": "bar", "tavern": "dive bar", "nightclub": "nightclub",
        "cocktail_bar": "cocktail bar", "brewery": "brewery",
        "wine_bar": "wine bar", "sports_bar": "sports bar",
        "karaoke_bar": "karaoke", "restaurant": "food", "cafe": "coffee",
    }
    if our_type in type_tag_map:
        tags.add(type_tag_map[our_type])
    if "restaurant" in gtypes:
        tags.add("food")
    price = details.get("price_level")
    if price:
        tags.add("$" * price)
    # Late night = closes after 1am
    for period in details.get("opening_hours", {}).get("periods", []):
        if period.get("close", {}).get("time", "0000") >= "0100":
            tags.add("late night")
            break
    return sorted(tags)

def build_row(details: dict, our_type: str) -> dict:
    geo  = details.get("geometry", {}).get("location", {})
    addr = details.get("formatted_address", "")
    lat  = geo.get("lat")
    lng  = geo.get("lng")
    zm   = re.search(r'\b(\d{5})\b', addr)
    hours = details.get("opening_hours")
    return {
        "name":            details.get("name", ""),
        "google_place_id": details.get("place_id"),
        "place_type":      our_type,
        "address":         details.get("vicinity") or addr,
        "neighborhood":    nearest_hood(lat, lng) if lat else None,
        "city":            "Tulsa",
        "state":           "OK",
        "zip":             zm.group(1) if zm else None,
        "latitude":        lat,
        "longitude":       lng,
        "price_level":     details.get("price_level"),
        "rating":          details.get("rating"),
        "review_count":    details.get("user_ratings_total"),
        "phone":           details.get("formatted_phone_number"),
        "website":         details.get("website"),
        "google_maps_url": details.get("url"),
        "hours":           {"periods": hours.get("periods",[]), "weekday_text": hours.get("weekday_text",[])} if hours else None,
        "tags":            build_tags(details, our_type),
        "description":     None,
        "active":          True,
        "manually_added":  False,
        "last_synced":     datetime.now(timezone.utc).isoformat(),
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    missing = [k for k,v in [("SUPABASE_URL",SUPABASE_URL),("SUPABASE_KEY",SUPABASE_KEY),("GOOGLE_PLACES_API_KEY",GOOGLE_API_KEY)] if not v]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    print("=" * 55)
    print("  Locate918 — Places Seeder")
    print("=" * 55)

    existing = existing_place_ids()
    print(f"Places already in DB: {len(existing)}\n")

    seen      = set()   # place_ids processed this run
    new_ct    = 0
    update_ct = 0
    fail_ct   = 0

    for hood_lat, hood_lng, hood_label in NEIGHBORHOODS:
        print(f"\n── {hood_label} ({hood_lat}, {hood_lng})")

        for gtype, our_type, keyword in SEARCHES:
            results = nearby_search(hood_lat, hood_lng, gtype, keyword)

            added = 0
            for r in results:
                pid = r.get("place_id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)

                is_update = pid in existing

                details = get_details(pid)
                time.sleep(0.05)

                if not details.get("name"):
                    continue

                row = build_row(details, our_type)
                if upsert_place(row):
                    added += 1
                    if is_update:
                        update_ct += 1
                    else:
                        new_ct += 1
                else:
                    fail_ct += 1
                time.sleep(0.1)

            if added:
                label = f"{our_type}" + (f" [{keyword}]" if keyword else "")
                print(f"  {label:25s} {added} places")

    print("\n" + "=" * 55)
    print("DONE")
    print(f"  New:     {new_ct}")
    print(f"  Updated: {update_ct}")
    print(f"  Failed:  {fail_ct}")
    print(f"  Total unique place_ids processed: {len(seen)}")

if __name__ == "__main__":
    main()