// Centralized UI class tokens (TDesign-inspired) for consistent contrast.
// Prefer these over ad-hoc `bg-slate-900/40 text-slate-400` mixes.

export const ui = {
  page: 'bg-ui-bg text-ui-text1',
  panel:
    'rounded-[var(--podi-radius)] border border-ui-border bg-ui-surface shadow-ui dark:shadow-black/40',
  panelMuted:
    'rounded-[var(--podi-radius)] border border-ui-border bg-ui-surface2 shadow-ui dark:shadow-black/30',
  title: 'text-ui-text1 font-semibold',
  desc: 'text-ui-text2',
  subtle: 'text-ui-text3',
  tableHead: 'text-ui-text2',
  input:
    'w-full rounded-xl border border-ui-border bg-ui-surface px-3 py-2 text-ui-text1 placeholder:text-ui-text3 focus:outline-none focus:ring-2 focus:ring-ui-primary/25',
  button:
    'rounded-xl bg-ui-primary px-4 py-2 text-sm font-semibold text-white hover:bg-ui-primaryHover disabled:cursor-not-allowed disabled:opacity-50',
  buttonGhost:
    'rounded-xl border border-ui-border bg-ui-surface px-3 py-2 text-sm text-ui-text2 hover:bg-ui-surface2',
} as const;

