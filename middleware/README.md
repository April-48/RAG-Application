# Middleware (FastAPI API layer)

A thin HTTP transport layer. It handles routing, JWT authentication, request
validation, and permission checks, then delegates all real work to the `backend`
services. **No heavy business logic lives in route files.**

## Structure

```
app/
├── main.py                    # FastAPI app, router wiring
├── dependencies/              # FastAPI route dependencies
│   ├── get_current_user.py    # resolves bearer token -> User via backend
│   └── permissions.py         # ownership / access-control checks
├── schemas/                   # Pydantic request/response models (validation)
│   ├── auth_schema.py
│   ├── documents.py
│   └── chat.py
└── routes/                    # Thin endpoints that call backend services
    ├── auth_routes.py         # POST /auth/signup, /auth/login; GET /auth/me
    ├── documents.py
    └── chat.py
```

## Importing the backend

The middleware calls the backend's business logic. The backend is its own
top-level package named `app` (under `<repo>/backend`), packaged via
`backend/pyproject.toml` and **installed as an editable package** — this
`requirements.txt` includes `-e ../backend`. This middleware package is imported
as `middleware.app`. Because the backend is a real installed package, **no
`sys.path` manipulation is needed**:

- backend modules are imported absolutely: `from app.services.auth_service import AuthService`
- middleware-internal modules use relative imports: `from ..schemas.auth_schema import ...`

## Responsibilities

- **Routing** — declare endpoints, group with `APIRouter`.
- **Auth** — issue/verify JWTs; resolve the current user.
- **Validation** — enforce request/response contracts with Pydantic schemas.
- **Permissions** — ensure users only access their own documents (`owner_id` checks).
- **Delegation** — call into `backend` services; do not embed business logic.

## Development

Install dependencies from **this directory** so the `-e ../backend` line in
`requirements.txt` resolves correctly (this installs the backend editable
package plus its dependencies and the middleware's own deps):

```bash
cd middleware && pip install -r requirements.txt && cd ..
```

Then run from the **repository root** (so `middleware.app` is importable; the
backend `app` is importable because it's installed):

```bash
uvicorn middleware.app.main:app --reload --port 8000
```

Interactive API docs are then at `http://localhost:8000/docs`.

For Postgres, Redis, migrations, and env vars, start with [`docs/setup.md`](../docs/setup.md).

## Related docs

- [`docs/setup.md`](../docs/setup.md) — full local setup
- [`docs/api_design.md`](../docs/api_design.md) — routes this layer exposes
- [`docs/system_design.md`](../docs/system_design.md) — how middleware fits in the stack
