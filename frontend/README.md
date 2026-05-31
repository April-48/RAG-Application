# Frontend

React + Vite + TypeScript + Tailwind. UI only — all data comes from the API.

## Main folders

```
src/
├── api/         HTTP client
├── hooks/       useDocuments, useChat (+ useAuth from context/AuthContext)
├── components/  Upload, Chat, Sources, ConfirmDialog, etc.
├── pages/       Login, Dashboard, Chat
└── App.tsx      routing
```

Chat supports SSE streaming, source panel, and **Clear history** (confirmation modal; clears server messages + Redis cache for that document).

Run (API should be on :8000):

```bash
npm install && npm run dev
```

Docs: [setup](../docs/setup.md) · [api_design](../docs/api_design.md)
