# Locate918 Deployment Guide

## Architecture

```
Users → Vercel (React frontend)
          ↓                ↓
     Railway (Rust :3000)  Railway (Python :8001)
          ↓                ↓
       Supabase (PostgreSQL + Auth)
```

## Prerequisites

- GitHub repo: https://github.com/locate918/capstone
- Supabase project: already running
- Railway account: https://railway.app (sign up with GitHub)
- Vercel account: https://vercel.com (sign up with GitHub)

---

## Step 1: Production Code Changes

### 1a. Rust Backend — `backend/src/main.rs`

Change the server address to read PORT from env and bind to 0.0.0.0:

```rust
// REPLACE THIS:
let addr = SocketAddr::from(([127, 0, 0, 1], 3000));

// WITH THIS:
let port: u16 = std::env::var("PORT")
    .unwrap_or_else(|_| "3000".to_string())
    .parse()
    .expect("PORT must be a number");
let addr = SocketAddr::from(([0, 0, 0, 0], port));
```

Also update CORS to allow your production frontend URL:

```rust
// REPLACE THIS:
let cors = CorsLayer::new()
    .allow_origin(Any)
    .allow_methods(Any)
    .allow_headers([
        header::CONTENT_TYPE,
        header::AUTHORIZATION,
    ]);

// WITH THIS:
use tower_http::cors::AllowOrigin;

let cors = CorsLayer::new()
    .allow_origin(AllowOrigin::list([
        "http://localhost:5173".parse().unwrap(),
        "https://locate918.vercel.app".parse().unwrap(),  // update with your actual Vercel URL
    ]))
    .allow_methods(Any)
    .allow_headers([
        header::CONTENT_TYPE,
        header::AUTHORIZATION,
    ]);
```

### 1b. Python LLM Service — `llm-service/main.py`

Add production origins to CORS and read PORT:

```python
import os

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://locate918.vercel.app",  # add your Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 1c. Frontend — `frontend/vercel.json`

Drop `vercel.json` into the `frontend/` directory. (Already created.)

### 1d. LLM Service — `llm-service/requirements.txt`

Drop `requirements.txt` into the `llm-service/` directory. (Already created.)

### 1e. Dockerfiles

- Copy `backend-Dockerfile` → `backend/Dockerfile`
- Copy `llm-Dockerfile` → `llm-service/Dockerfile`

### 1f. Commit and push

```powershell
git add -A
git commit -m "Add deployment configs: Dockerfiles, vercel.json, production CORS/PORT"
git push
```

---

## Step 2: Deploy Rust Backend on Railway

1. Go to https://railway.app → New Project → Deploy from GitHub Repo
2. Select `locate918/capstone`
3. Railway will ask which directory — select `backend`
4. It will auto-detect the Dockerfile
5. Go to the service **Settings** → set **Root Directory** to `backend`
6. Go to **Variables** and add:

```
DATABASE_URL=postgresql://postgres.kpihjwzqtwqlschmtekx:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://kpihjwzqtwqlschmtekx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Get DATABASE_URL from: Supabase Dashboard → Settings → Database → Connection String (URI)
Use the **pooler** connection string (port 6543), NOT the direct one.

7. Go to **Settings** → **Networking** → Generate Domain (gives you something like `locate918-backend-production.up.railway.app`)
8. Note this URL — you'll need it for the frontend.

### Verify:
```
curl https://YOUR-RAILWAY-URL.up.railway.app/api/events
```

---

## Step 3: Deploy Python LLM Service on Railway

1. Same Railway project → **+ New Service** → From GitHub Repo
2. Select same repo, set **Root Directory** to `llm-service`
3. It will auto-detect the Dockerfile
4. Go to **Variables** and add:

```
GEMINI_API_KEY=your-gemini-api-key
BACKEND_URL=https://YOUR-RUST-RAILWAY-URL.up.railway.app
```

5. Generate Domain under **Settings** → **Networking**
6. Note this URL too.

### Verify:
```
curl https://YOUR-LLM-RAILWAY-URL.up.railway.app/health
```

---

## Step 4: Deploy Frontend on Vercel

1. Go to https://vercel.com → Add New Project → Import from GitHub
2. Select `locate918/capstone`
3. Set **Root Directory** to `frontend`
4. Framework Preset: **Create React App**
5. Add **Environment Variables**:

```
REACT_APP_BACKEND_URL=https://YOUR-RUST-RAILWAY-URL.up.railway.app
REACT_APP_LLM_SERVICE_URL=https://YOUR-LLM-RAILWAY-URL.up.railway.app
REACT_APP_SUPABASE_URL=https://kpihjwzqtwqlschmtekx.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

6. Click **Deploy**
7. Note your Vercel URL (e.g., `locate918.vercel.app`)

### Post-deploy:
- Go back to Railway and update the CORS origins in your Rust backend and Python service to include the actual Vercel URL
- Redeploy both Railway services

---

## Step 5: Supabase Config for Production

1. **Supabase Dashboard → Authentication → URL Configuration**
    - Add your Vercel URL to **Redirect URLs**: `https://locate918.vercel.app/**`
    - This is required for email verification links and OAuth redirects

2. **Supabase Dashboard → Settings → API**
    - Confirm your anon key matches what you set in Vercel env vars

---

## Step 6: Verify Everything

```bash
# 1. Events load (public, no auth)
curl https://YOUR-BACKEND.up.railway.app/api/events

# 2. LLM health check
curl https://YOUR-LLM.up.railway.app/health

# 3. Auth wall works
curl -i https://YOUR-BACKEND.up.railway.app/api/users/me
# Should return 401

# 4. Frontend loads
# Visit https://locate918.vercel.app
# Sign up, sign in, verify events load, verify chat works
```

---

## Cost Estimate

| Service | Plan | Cost |
|---------|------|------|
| Vercel | Hobby (free) | $0/mo |
| Railway (Rust) | Hobby | ~$5/mo |
| Railway (Python) | Hobby | ~$5/mo |
| Supabase | Free tier | $0/mo |
| **Total** | | **~$10/mo** |

---

## Troubleshooting

**Build fails on Railway:**
- Check that Root Directory is set correctly
- Check build logs for missing env vars
- Ensure Cargo.lock is committed (remove it from .gitignore)

**CORS errors in browser:**
- Update CORS origins in both backend services to match your exact Vercel URL
- Redeploy after changing

**Auth not working:**
- Add Vercel URL to Supabase redirect URLs
- Check that SUPABASE_URL and SUPABASE_ANON_KEY are set in Railway

**Database connection fails:**
- Use the pooler connection string (port 6543) not direct (port 5432)
- Railway needs the full connection string with password

**502 errors:**
- Check Railway logs for panics
- Make sure PORT is being read from env, not hardcoded
- Make sure binding to 0.0.0.0 not 127.0.0.1