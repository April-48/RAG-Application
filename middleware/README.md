# Middleware (FastAPI API layer)

Thin HTTP layer: routes, JWT, Pydantic validation, HTTP status codes. Business logic lives in the `backend` package.

## Main folders

```
app/
├── main.py              app + /health
├── dependencies/        auth, rate limit
├── schemas/             request/response models
└── routes/              auth, documents, chat
```

Install backend first:

```bash
cd middleware && pip install -r requirements.txt
```

Run from repo root:

```bash
uvicorn middleware.app.main:app --reload --port 8000
```

Docs: [setup](../docs/setup.md) · [api_design](../docs/api_design.md) · [RAG pipeline](../docs/rag_pipeline.md)
