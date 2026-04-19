import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routes import chat, search, normalize, interactions

app = FastAPI()
SERVICE_VERSION = os.getenv("APP_VERSION", "0.1.0")
SERVICE_GIT_SHA = os.getenv("GITHUB_SHA", "dev")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3001",
        "https://admin.locate918.com",
        "https://locate918.com",
        "https://www.locate918.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add this to see exactly why 422 errors happen in your terminal
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# Register the routes
app.include_router(chat.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(normalize.router, prefix="/api")
app.include_router(interactions.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "llm-service",
        "version": SERVICE_VERSION,
        "git_sha": SERVICE_GIT_SHA,
    }


@app.get("/version")
async def version_check():
    return {
        "status": "ok",
        "service": "llm-service",
        "version": SERVICE_VERSION,
        "git_sha": SERVICE_GIT_SHA,
    }
