# Frontend

React + Vite + TypeScript + Tailwind CSS. This folder is **UI only** — no business logic. It calls the middleware API and shows the results.

## Structure

```
src/
├── api/          # API client (auth, documents, chat)
├── types/        # TypeScript types matching API shapes
├── hooks/        # useAuth, useDocuments, useChat, ...
├── components/   # Reusable UI pieces
├── pages/        # Login, Dashboard, Chat, ...
├── App.tsx       # Routing
├── main.tsx      # Entry point
└── index.css     # Tailwind entry
```

## Conventions

- All HTTP calls go through `src/api/client.ts` — do not call `fetch` directly in components.
- Keep components focused on UI; put data fetching in hooks.
- Types should match the middleware schemas so the contract stays clear.

## Run locally

```bash
npm install
npm run dev
```

The API should be running on port 8000. See [setup guide](../docs/setup.md).

## Related docs

- [Setup guide](../docs/setup.md)
- [API design](../docs/api_design.md)
