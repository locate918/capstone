from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env vars before importing services
load_dotenv()

from app.routes import search, chat, normalize

app = FastAPI(title="Locate918 LLM Service")

# Configure CORS (Allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routes
app.include_router(search.router, prefix="/api", tags=["Search"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(normalize.router, prefix="/api", tags=["Normalize"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "llm-service"}