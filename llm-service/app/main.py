from fastapi import FastAPI
from dotenv import load_dotenv
from app.routes import search, chat, normalize

# Load environment variables
load_dotenv()

app = FastAPI(title="Locate918 LLM Service", version="1.0.0")

# Register Routers
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(normalize.router)

@app.get("/")
async def root():
    return {"status": "online", "service": "Locate918 LLM Service"}