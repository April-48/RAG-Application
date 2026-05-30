"""FastAPI entry point — wires routers, CORS, health check.

This layer is thin on purpose: routes validate HTTP stuff and call backend
services. Run from repo root:

    uvicorn middleware.app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth_routes, chat_routes, document_routes

app = FastAPI(title="RAG Document Q&A API")

# Vite dev server needs this or the browser blocks API calls (CORS).
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
def health() -> dict[str, str]:
    """Simple liveness probe for docker / manual checks."""
    return {"status": "ok"}


app.include_router(auth_routes.router)
app.include_router(document_routes.router)
app.include_router(chat_routes.router)
