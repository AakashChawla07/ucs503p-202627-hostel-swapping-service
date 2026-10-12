# Web UI

React + TypeScript, built by Vite straight into `code/hostelswap/webui/`.
That build output is committed, so `uvicorn hostelswap.api:app` serves the
UI on a machine with no Node installed. Rebuild after any change here:

    npm install            # once
    npm run build          # type-checks, then writes code/hostelswap/webui/

For day-to-day work, run the API and the dev server side by side — Vite
proxies `/api` and `/assets` to port 8000, so cookies and asset paths
match production:

    uvicorn hostelswap.api:app --reload     # terminal 1, from the repo root
    npm --prefix frontend run dev           # terminal 2

## Layout

    src/api.ts          every call to the backend, typed
    src/types.ts        the shapes those endpoints return
    src/styles.css      design tokens and components
    src/App.tsx         routing and the session mirror
    src/components/     shell, cards, chain cards, modal
    src/modals/         every form in the app
    src/pages/          Login, Student, Admin

Forms live in `src/modals/` by design: the pages stay readable as
dashboards, and a form that commits something irreversible (offering a
swap, locking a round) gets a confirmation step for free.
