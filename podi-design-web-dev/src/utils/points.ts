// Helpers for formatting point-related numeric values
export function formatSigned(val?: any, missing?: string | undefined): string | undefined {
  if (val === undefined || val === null || val === '') return missing === undefined ? undefined : missing;
  const n = Number(val);
  if (Number.isNaN(n)) return String(val);
  return n > 0 ? `+${n}` : `${n}`;
};

export default {
  formatSigned,
};
