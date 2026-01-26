# UI Standard (TDesign)

All admin/eval UIs follow Tencent **TDesign** strictly:

- Colors: https://tdesign.tencent.com/design/color
- Fonts: https://tdesign.tencent.com/design/fonts
- Motion: https://tdesign.tencent.com/design/motion
- Icons: https://tdesign.tencent.com/design/icon
- Layout: https://tdesign.tencent.com/design/layout
- Dark: https://tdesign.tencent.com/design/dark
- Office console: https://tdesign.tencent.com/design/offices

## Implementation (React)

- Component library: `tdesign-react` + `tdesign-icons-react`
- Global CSS: `podi-admin-web/src/main.tsx` imports `tdesign-react/es/style/index.css`
- Dark mode: toggle `t-theme-dark` on `<html>` (see `podi-admin-web/src/App.tsx`)
- Prefer TDesign components for everything user-facing: `Layout/Menu/Card/Table/Form/Input/Select/Button/Alert/Dialog/Message`

## Rules (must follow)

1) Do not hand-mix ad-hoc palettes (e.g. `bg-slate-900/40 text-slate-400`) for any visible UI.
2) Avoid building custom buttons/inputs/tables; use TDesign equivalents.
3) Spacing/layout should prefer TDesign Layout/Grid/Space. Tailwind can be used temporarily for migration, but new UI should not depend on custom color tokens.

