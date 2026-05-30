# Frontend

React + Vite + TypeScript + Tailwind CSS. This layer contains **UI only** — no business
logic. It calls the middleware API and renders the results.

## Structure

```
src/
├── api/          # API client + per-domain call modules (auth, documents, chat)
├── types/        # Shared TypeScript types matching API contracts
├── hooks/        # React hooks (useAuth, useDocuments, ...)
├── components/   # Reusable presentational components
├── pages/        # Route-level pages (Login, Documents, Chat)
├── App.tsx       # Root component / routing
├── main.tsx      # Entry point
└── index.css     # Tailwind entry
```

## Conventions

- All network requests go through `src/api/client.ts`; never call `fetch` directly in components.
- Keep components presentational; data fetching belongs in hooks.
- Types mirror the middleware schemas so the contract stays explicit.

## Development

```bash
npm install
npm run dev
```

Requires the middleware API on port 8000 — see [`docs/setup.md`](../docs/setup.md).

## Related docs

- [`docs/setup.md`](../docs/setup.md) — full local setup (API + frontend)
- [`docs/api_design.md`](../docs/api_design.md) — HTTP API the frontend calls
