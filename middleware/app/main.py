"""FastAPI entry point. I keep this layer thin — routes validate HTTP and call backend services.

Run from repo root:
    uvicorn middleware.app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth_routes, chat_routes, document_routes

app = FastAPI(title="RAG Document Q&A API")

# I allow the Vite dev origin or the browser blocks API calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
# GET /health — liveness probe for Docker Compose and manual curl checks.
# Return {"status": "ok"} when the uvicorn process is running.
# I do not check Postgres or Redis here; this only proves the API layer is up.
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_routes.router)
app.include_router(document_routes.router)
app.include_router(chat_routes.router)
