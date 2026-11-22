# ADR-004: esbuild + Tailwind v4 compile API; minimal in-house router, query hook and charts

- Status: Accepted (2026-11-22). Revisit when packages can be installed.

## Context
The brief recommends Vite, React Router, TanStack Query, Recharts and Vitest. None could be installed. Available: React 19, TypeScript 6, esbuild 0.28, Tailwind CSS 4.3 (library, no CLI), tsx, Playwright.

## Decision
- `frontend/scripts/build.mjs` bundles with esbuild and compiles Tailwind through its `compile()` API, extracting class candidates from `src/` itself (over-collecting is safe: Tailwind ignores invalid candidates).
- `lib/router.ts`: hash router (no server rewrites needed).
- `lib/query.ts`: keyed cache with de-duplication and prefix invalidation, about 100 lines.
- `components/charts.tsx`: SVG column chart, heatmap and bar list following the dataviz rules (thin marks, recessive grid, tooltips, table view).
- Frontend unit tests use Node's built-in test runner via tsx; UI behaviour is covered by Playwright E2E instead of React Testing Library.
- `@types/react` could not be installed, so `tsconfig.offline.json` adds a minimal type shim. `tsconfig.json` is the normal configuration for machines with `npm install`.

## Consequences
- Fewer dependencies, fast builds (~0.2 s).
- Type checking of JSX DOM props is weaker under the offline shim. With network access, run `npm install && npm run typecheck` to check against real React types (not yet done; see Known Issues).
- Swapping in Vite/TanStack Query/Recharts later is localised to `scripts/`, `lib/query.ts` and `components/charts.tsx`.
