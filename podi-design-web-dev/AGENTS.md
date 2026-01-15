# Repository Guidelines

## Project Structure & Module Organization
- `src/` contains all React + TypeScript features split by domain (e.g., `src/components`, `src/pages`, `src/store`). Keep shared UI primitives in `src/components/ui` and colocate hooks or config files inside each feature folder.
- `public/` holds static assets (SVG, fonts) that Vite copies verbatim. Only place hashed bundles or CDN-ready media in `build/` after `npm run build`.
- Developer notes and UX specs live in `docs/` and top-level Markdown briefs (for example `菜单组件功能交互梳理.md`). Update these when flows change.

## Build, Test, and Development Commands
- `npm run dev` boots the Vite dev server with hot reload at http://localhost:5173.
- `npm run build` generates production assets under `build/` using the current `vite.config.ts`.
- `npm run type-check` runs `tsc --noEmit` to keep types in sync with API models.
- `npm run lint` executes ESLint with `@typescript-eslint` rules; warnings fail CI.
- `npm run ci-check` runs the type checker and linter exactly as GitHub Actions expect.

## Coding Style & Naming Conventions
- Use TypeScript, 2-space indentation, and prefer functional React components with hooks.
- Name components in `PascalCase`, hooks in `useCamelCase`, Zustand stores as `<domain>Store`.
- Run `npm run format` (Prettier) before committing; ESLint shares the same ignore/glob patterns.

## Testing Guidelines
- Vitest with Testing Library lives beside code: name files `*.test.tsx` near the component or utility.
- When covering UI logic, mock network calls via Axios interceptors or `fetch` stubs.
- Target smoke coverage for every route; include accessibility assertions (`toHaveAccessibleName`).
- Execute `npx vitest run` locally (or add a `test` script mirroring that command) before requesting reviews.

## Commit & Pull Request Guidelines
- Follow the repo’s conventional history: short imperative subject (`feat: add dashboard filters`) and optional body explaining rationale.
- Reference Jira ticket or GitHub issue IDs in the body and attach screenshots/GIFs for UI changes.
- Pull requests need: summary checklist, test evidence (command output), and notes on affected routes or configs.
