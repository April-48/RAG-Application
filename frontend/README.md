# Frontend

React + Vite + TypeScript + Tailwind. UI only — all data comes from the API.

## Main folders

```
src/
├── api/         HTTP client
├── hooks/       useAuth, useDocuments, useChat
├── components/  Upload, Chat, Sources, etc.
├── pages/       Login, Dashboard, Chat
└── App.tsx      routing
```

Run (API should be on :8000):

```bash
npm install && npm run dev
```

Docs: [setup](../docs/setup.md) · [api_design](../docs/api_design.md)
