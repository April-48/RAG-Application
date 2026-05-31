# Middleware (FastAPI API layer)

This folder is a thin HTTP layer. It defines routes, checks JWT auth, validates requests, and maps errors to HTTP status codes. The real logic lives in the `backend` package.

Route files should stay small — they call backend services and return JSON or files.

## Structure

```
app/
├── main.py                    # FastAPI app, routers, GET /health
├── dependencies/
│   ├── get_current_user.py    # Bearer token → User
│   ├── chat_rate_limit.py     # Optional Redis rate limit on ask routes
│   └── permissions.py         # Access-control helpers
├── schemas/                   # Pydantic request/response models
│   ├── auth_schema.py
│   ├── document_schema.py
│   └── chat_schema.py
└── routes/
    ├── auth_routes.py         # signup, login, me
    ├── document_routes.py     # upload, list, rename, download, delete
    └── chat_routes.py         # ask, ask/stream (SSE), history
```

## How the backend is imported

The backend is a separate Python package named `app` under `backend/`. Install it with:

```bash
cd middleware && pip install -r requirements.txt
```

That file includes `-e ../backend`. After install:

- Backend code: `from app.services.auth_service import AuthService`
- Middleware code: `from ..schemas.auth_schema import ...`

No manual `sys.path` edits are needed.

## What this layer does

- **Routing** — define endpoints with `APIRouter`
- **Auth** — issue and verify JWTs
- **Validation** — Pydantic schemas for request/response shapes
- **Permissions** — make sure users only touch their own documents
- **Delegation** — call backend services; do not put RAG logic in route files

## Run locally

From the repo root:

```bash
uvicorn middleware.app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

For Postgres, Redis, migrations, and env vars, see [setup guide](../docs/setup.md).

## Related docs

- [Setup guide](../docs/setup.md)
- [API design](../docs/api_design.md) — matches OpenAPI at `/docs`
- [System design](../docs/system_design.md)
