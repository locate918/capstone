"""
Locate918 Test Scraper - Cain's Ballroom
Run with: python scraper.py
"""

import httpx
import asyncio
from bs4 import BeautifulSoup

LLM_SERVICE_URL = "http://localhost:8001"
BACKEND_URL = "http://localhost:3000"

async def scrape_cains_ballroom():
    """Scrape events from Cain's Ballroom website"""
    print("🎸 Scraping Cain's Ballroom...")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            # Fetch the events page
            response = await client.get(
                "https://www.cainsballroom.com/events/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find event containers (adjust selector based on actual site structure)
            events = soup.select(".event-info, .eventlist-event, article.event, .eventWrapper")

            if not events:
                # Try getting any content for testing
                print("⚠️  No events found with specific selectors, sending full page to LLM")
                content = soup.get_text()[:5000]
                events = [content]

            print(f"📋 Found {len(events)} potential events")

            for i, event in enumerate(events[:5]):  # Limit to 5 for testing
                if isinstance(event, str):
                    html_content = event
                else:
                    html_content = str(event)

                print(f"\n🎵 Processing event {i+1}...")
                print(f"   Content preview: {html_content[:200]}...")

                # Send to normalize endpoint
                try:
                    normalize_response = await client.post(
                        f"{LLM_SERVICE_URL}/api/normalize",
                        json={
                            "raw_content": html_content,
                            "source_url": f"https://www.cainsballroom.com/events#{i}",
                            "source_name": "Cain's Ballroom"
                        },
                        timeout=30.0
                    )

                    if normalize_response.status_code == 200:
                        result = normalize_response.json()
                        print(f"   ✅ Normalized {result['count']} event(s)")
                        for e in result.get("events", []):
                            print(f"      - {e.get('title', 'Unknown')}")
                    else:
                        print(f"   ❌ Normalize failed: {normalize_response.status_code}")
                        print(f"      {normalize_response.text[:200]}")

                except httpx.ConnectError:
                    print(f"   ❌ Could not connect to LLM service at {LLM_SERVICE_URL}")
                    print("      Make sure the LLM service is running!")
                    return

        except httpx.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")


async def scrape_visit_tulsa():
    """Scrape events from Visit Tulsa"""
    print("\n🌷 Scraping Visit Tulsa...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://www.visittulsa.com/events/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0,
                follow_redirects=True
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Get event content
            events = soup.select(".event-card, .event-item, .card, article")[:5]

            if not events:
                print("⚠️  No events found, trying page text")
                # Just grab some text content for testing
                main_content = soup.select_one("main, .content, body")
                if main_content:
                    events = [str(main_content)[:3000]]

            print(f"📋 Found {len(events)} items to process")

            for i, event in enumerate(events[:3]):
                html_content = str(event) if not isinstance(event, str) else event

                print(f"\n🎪 Processing item {i+1}...")

                try:
                    normalize_response = await client.post(
                        f"{LLM_SERVICE_URL}/api/normalize",
                        json={
                            "raw_content": html_content[:4000],
                            "source_url": f"https://www.visittulsa.com/events/#{i}",
                            "source_name": "Visit Tulsa"
                        },
                        timeout=30.0
                    )

                    if normalize_response.status_code == 200:
                        result = normalize_response.json()
                        print(f"   ✅ Normalized {result['count']} event(s)")
                    else:
                        print(f"   ❌ Failed: {normalize_response.status_code}")

                except httpx.ConnectError:
                    print(f"   ❌ LLM service not running!")
                    return

        except Exception as e:
            print(f"❌ Error: {e}")


async def test_with_fake_data():
    """Test the pipeline with fake event data"""
    print("\n🧪 Testing with fake data...")

    fake_events = [
        {
            "raw_content": """
                <div class="event">
                    <h2>Jazz Night at The Colony</h2>
                    <p>Join us for an evening of smooth jazz!</p>
                    <p>Date: February 15, 2026 at 8:00 PM</p>
                    <p>Venue: The Colony, 2809 S Harvard Ave, Tulsa</p>
                    <p>Tickets: $15-25</p>
                    <p>21+ event</p>
                </div>
            """,
            "source_url": "https://example.com/jazz-night",
            "source_name": "Test Source"
        },
        {
            "raw_content": """
                <div class="event">
                    <h2>Tulsa Food Truck Festival</h2>
                    <p>Over 30 food trucks! Live music, family fun!</p>
                    <p>Saturday, February 22, 2026 - 11am to 8pm</p>
                    <p>Gathering Place, Tulsa OK</p>
                    <p>FREE admission</p>
                    <p>Family friendly, outdoor event</p>
                </div>
            """,
            "source_url": "https://example.com/food-truck-fest",
            "source_name": "Test Source"
        },
        {
            "raw_content": """
                Rock Concert - SOLD OUT!
                Band: The Oklahoma Kid
                When: March 1st 2026, doors at 7pm
                Where: Cain's Ballroom, 423 N Main St
                Price: $35
                All ages welcome
            """,
            "source_url": "https://example.com/rock-concert",
            "source_name": "Test Source"
        }
    ]

    async with httpx.AsyncClient() as client:
        for i, event_data in enumerate(fake_events):
            print(f"\n📝 Sending fake event {i+1}...")

            try:
                response = await client.post(
                    f"{LLM_SERVICE_URL}/api/normalize",
                    json=event_data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Normalized {result['count']} event(s)")
                    for e in result.get("events", []):
                        print(f"      Title: {e.get('title')}")
                        print(f"      Venue: {e.get('venue')}")
                        print(f"      Time: {e.get('start_time')}")
                        print(f"      Price: ${e.get('price_min')} - ${e.get('price_max')}")
                else:
                    print(f"   ❌ Failed: {response.status_code}")
                    print(f"      {response.text[:300]}")

            except httpx.ConnectError:
                print(f"   ❌ Could not connect to {LLM_SERVICE_URL}")
                print("      Start the LLM service first!")
                return


async def test_search():
    """Test the search endpoint"""
    print("\n🔍 Testing search...")

    queries = [
        "jazz concerts this weekend",
        "family events",
        "free outdoor events",
        "rock music under $30"
    ]

    async with httpx.AsyncClient() as client:
        for query in queries:
            print(f"\n   Query: '{query}'")
            try:
                response = await client.post(
                    f"{LLM_SERVICE_URL}/api/search",
                    json={"query": query},
                    timeout=15.0
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"   Parsed: {result.get('parsed')}")
                    print(f"   Found: {len(result.get('events', []))} events")
                else:
                    print(f"   ❌ Failed: {response.status_code}")

            except httpx.ConnectError:
                print(f"   ❌ LLM service not running")
                return


async def test_chat():
    """Test the chat endpoint"""
    print("\n💬 Testing chat with Tully...")

    messages = [
        "Hey Tully! What's happening this weekend?",
        "Any good jazz music coming up?",
        "I'm looking for family-friendly outdoor events"
    ]

    async with httpx.AsyncClient() as client:
        for msg in messages:
            print(f"\n   You: {msg}")
            try:
                response = await client.post(
                    f"{LLM_SERVICE_URL}/api/chat",
                    json={"message": msg},
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"   Tully: {result.get('message', '')[:300]}...")
                else:
                    print(f"   ❌ Failed: {response.status_code}")

            except httpx.ConnectError:
                print(f"   ❌ LLM service not running")
                return


async def check_backend():
    """Check if Rust backend is running"""
    print("🔌 Checking backend connection...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/events", timeout=5.0)
            print(f"   ✅ Backend is running! Found {len(response.json())} events")
            return True
        except:
            print(f"   ❌ Backend not running at {BACKEND_URL}")
            print("   Start it with: cd backend && cargo run")
            return False


async def main():
    print("=" * 60)
    print("🚀 LOCATE918 TEST SUITE")
    print("=" * 60)

    # Check services
    backend_ok = await check_backend()

    print("\n" + "-" * 60)
    print("Choose test mode:")
    print("  1. Test with fake data (recommended first)")
    print("  2. Scrape Cain's Ballroom")
    print("  3. Scrape Visit Tulsa")
    print("  4. Test search endpoint")
    print("  5. Test chat endpoint")
    print("  6. Run all tests")
    print("-" * 60)

    choice = input("Enter choice (1-6): ").strip()

    if choice == "1":
        await test_with_fake_data()
    elif choice == "2":
        await scrape_cains_ballroom()
    elif choice == "3":
        await scrape_visit_tulsa()
    elif choice == "4":
        await test_search()
    elif choice == "5":
        await test_chat()
    elif choice == "6":
        await test_with_fake_data()
        await test_search()
        await test_chat()
    else:
        print("Invalid choice, running fake data test...")
        await test_with_fake_data()

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())