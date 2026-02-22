"""
Locate918 Universal Scraper Tool
================================
Smart extraction that handles ANY site format. No LLM required.
Respects robots.txt - will not scrape sites that disallow it.

Usage:
    pip install flask playwright httpx beautifulsoup4 python-dotenv python-dateutil
    playwright install chromium
    python scraperTool.py

Open http://localhost:5000

Module structure:
    scraperTool.py            - This entry point
    scraperUtils.py           - Config, robots.txt, URL management, date patterns
    scraperExtractors/        - Extraction strategies package
        __init__.py           - Re-exports (routes imports unchanged)
        fetchers.py           - HTTP/Playwright fetch with API interception
        apiExtractors.py      - EventCalendarApp, Timely, BOK Center APIs
        cmsExtractors.py      - Expo, Eventbrite, Simpleview, SiteWrench, RecDesk, TicketLeap
        platformExtractors.py - Tribe, Stubwire, Etix, TNEW, GCal, Squarespace, etc.
        genericExtractors.py  - Repeating structures, date proximity fallbacks
        universal.py          - Orchestrator + garbage filter
    scraperRoutes.py          - Flask routes, data transform, LLM normalization, GUI
"""

from flask import Flask
from scraperUtils import OUTPUT_DIR, BACKEND_URL, LLM_SERVICE_URL
from scraperRoutes import register_routes

app = Flask(__name__)
register_routes(app)

if __name__ == '__main__':
    print("=" * 50)
    print("  Locate918 Universal Scraper")
    print("  Smart extraction — LLM Normalized")
    print("  ✓ Respects robots.txt")
    print("  ✓ Gemini normalization via :8001")
    print("=" * 50)
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  LLM Service: {LLM_SERVICE_URL}")
    print("=" * 50)
    print("  http://localhost:5000")
    print("=" * 50)

    app.run(debug=True, port=5000)