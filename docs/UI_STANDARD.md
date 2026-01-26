# UI Standard (TDesign Inspired)

This repo uses Tailwind, but we **do not** mix random `bg-slate-* + text-slate-*` pairs per page anymore.
To keep contrast readable and the admin console consistent, we adopt a small set of **semantic tokens**
inspired by Tencent TDesign (colors / fonts / motion / layout).

References (design language):
- Colors: https://tdesign.tencent.com/design/color
- Fonts: https://tdesign.tencent.com/design/fonts
- Motion: https://tdesign.tencent.com/design/motion
- Icons: https://tdesign.tencent.com/design/icon
- Layout: https://tdesign.tencent.com/design/layout
- Dark: https://tdesign.tencent.com/design/dark
- Office console: https://tdesign.tencent.com/design/offices

## Where Tokens Live

- CSS variables: `podi-admin-web/src/styles/tokens.css`
- Tailwind semantic colors: `podi-admin-web/tailwind.config.js` (`ui.*`)
- Shared class helpers: `podi-admin-web/src/utils/ui.ts`

## Rules (must follow)

1) Use semantic colors:
   - Background: `bg-ui-bg`
   - Panels/cards: `bg-ui-surface` + `border-ui-border`
   - Text: `text-ui-text1` (primary), `text-ui-text2` (secondary), `text-ui-text3` (disabled/hint)
   - Brand: `ui.primary`, status: `ui.success/ui.warning/ui.error`

2) Avoid:
   - `bg-slate-900/40` + `text-slate-400` (low contrast in light mode)
   - hard-coded `text-white` for headings (breaks in light mode)

3) Components should prefer shared classes:
   - `ui.panel`, `ui.panelMuted`, `ui.input`, `ui.button`, `ui.buttonGhost`

4) Dark mode:
   - Only toggle `html.dark`; tokens handle the rest.
   - Do not maintain separate "dark-only" layouts.

## Motion (recommended)

- Fast: 150ms (hover/focus)
- Normal: 200ms (panel open/close)
- Slow: 300ms (page transitions)

Use Tailwind `transition` with `duration-150/200/300` and `ease-out`.

## Typography (recommended)

- Title: `text-lg font-semibold`
- Section title: `text-xl font-semibold`
- Body: `text-sm`
- Hint/Meta: `text-xs text-ui-text2/text-ui-text3`

