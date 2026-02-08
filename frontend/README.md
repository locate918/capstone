# Locate918 Frontend

React-based event discovery app for Tulsa, featuring an AI assistant (Tully), interactive map, and curated event listings.

## Features

- **Hero Slideshow** — Auto-rotating images of Tulsa on the home page
- **Smart Search** — Natural language search powered by AI (e.g., "jazz concerts under $30")
- **Tully AI Chat** — Conversational event discovery assistant
- **Interactive Map** — Leaflet-based map with event markers and hover highlighting
- **Event Cards** — Rich event listings with vibe tags, pricing, and venue info
- **Event Modal** — Detailed overlay with AI-generated insights
- **Responsive Design** — Mobile list/map toggle, tablet and desktop layouts

## Quick Start

```bash
cd frontend
npm install
npm start
```

Opens at http://localhost:5173

## Environment Variables

Create `.env` in the `frontend/` folder:

```
PORT=5173
REACT_APP_BACKEND_URL=http://localhost:3000
REACT_APP_LLM_SERVICE_URL=http://localhost:8001
REACT_APP_USE_MOCKS=false
```

| Variable | Description |
|----------|-------------|
| `PORT` | Dev server port (default: 5173) |
| `REACT_APP_BACKEND_URL` | Rust backend API URL |
| `REACT_APP_LLM_SERVICE_URL` | Python LLM service URL |
| `REACT_APP_USE_MOCKS` | Set `true` to use mock data without backend |

### Mock Mode

Set `REACT_APP_USE_MOCKS=true` to develop without the backend. Mock data includes:

- 2 sample events (Founders Lounge, Jazz Night)
- Simulated chat responses from Tully
- Random Tulsa-area coordinates for map markers

To add more mock events, edit `getMockEvents()` in `src/services/api.js`.

## Project Structure

```
src/
??? components/
?   ??? AIChatWidget.js   # Tully chat interface
?   ??? EventCard.js      # Event listing card
?   ??? EventModal.js     # Event detail overlay
?   ??? Header.js         # Navigation & search
?   ??? TulsaMap.js       # Leaflet map
??? services/
?   ??? api.js            # API client
??? styles/
?   ??? theme.js          # Color palette
??? App.js                # Main component
??? index.css             # Global styles
```

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19 | UI framework |
| Tailwind CSS | 3.4 | Styling |
| Leaflet | 1.9 | Maps |
| react-leaflet | 5.0 | React bindings for Leaflet |
| Lucide React | 0.563 | Icons |

### Browser Requirements

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

React 19 and modern CSS features require recent browser versions.

## Scripts

| Command | Description |
|---------|-------------|
| `npm start` | Start dev server |
| `npm run build` | Production build (outputs to `build/`) |
| `npm test` | Run tests |
| `npm run eject` | Eject from Create React App (irreversible) |

## API Functions

All API functions are exported from `src/services/api.js`:

| Function | Endpoint | Service | Description |
|----------|----------|---------|-------------|
| `fetchEvents()` | `GET /api/events` | Backend :3000 | Get all upcoming events |
| `searchEvents(params)` | `GET /api/events/search` | Backend :3000 | Filter events with params |
| `smartSearch(query)` | `POST /api/search` | LLM :8001 | AI-powered natural language search |
| `chatWithTully(msg, userId, conversationId)` | `POST /api/chat` | LLM :8001 | Chat with Tully AI assistant |

### Search Parameters

`searchEvents()` accepts these filter parameters:

```js
searchEvents({
  q: "jazz",           // Text search
  category: "concerts", // Category filter
  price_max: 30,       // Maximum price
  outdoor: true,       // Outdoor events only
  family_friendly: true // Family-friendly only
});
```

## Theme Colors

| Color | Hex | Usage |
|-------|-----|-------|
| Gold | `#D4AF37` | Primary accent, highlights |
| Cream | `#f8f1e0` | Background |
| Navy | `#162b4a` | Cards, buttons |

Full theme available in `src/styles/theme.js`.

## Leaflet Setup

Leaflet CSS is required for maps to render correctly. It's imported in `TulsaMap.js`:

```js
import 'leaflet/dist/leaflet.css';
```

If map tiles or markers don't display, ensure Leaflet CSS is being bundled correctly.

## Deployment

### Build for Production

```bash
npm run build
```

Creates optimized bundle in `build/` folder.

### Deploy Options

| Platform | Command/Notes |
|----------|---------------|
| Vercel | `vercel --prod` (auto-detects React) |
| Netlify | Drag `build/` folder or connect repo |
| Static hosting | Upload `build/` contents |

### Environment Variables in Production

Set these in your hosting provider's dashboard:
- `REACT_APP_BACKEND_URL` — Your deployed backend URL
- `REACT_APP_LLM_SERVICE_URL` — Your deployed LLM service URL

## Troubleshooting

### Map not displaying

1. Check that `leaflet/dist/leaflet.css` is imported
2. Verify the map container has a defined height
3. Check browser console for tile loading errors

### CORS errors

Backend must allow requests from frontend origin. In development:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:3000`

### "Failed to fetch events" in console

1. Ensure backend is running (`cd backend && cargo run`)
2. Check `REACT_APP_BACKEND_URL` matches backend port
3. Try mock mode: set `REACT_APP_USE_MOCKS=true`

### Styles not applying

1. Run `npm install` to ensure Tailwind is installed
2. Check that `tailwind.config.js` exists in `frontend/`
3. Verify `index.css` imports Tailwind directives

### Port already in use

```bash
# Find process using port 5173
# Windows
netstat -ano | findstr :5173

# macOS/Linux
lsof -i :5173
```

## Related Documentation

- [Main Project README](../README.md) — Full stack setup
- [AI Service Overview](../docs/Design/AI_Service_Overview.md) — LLM integration details
