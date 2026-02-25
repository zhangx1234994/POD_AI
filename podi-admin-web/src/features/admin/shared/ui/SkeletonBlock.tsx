export function SkeletonBlock({ height = 96 }: { height?: number }) {
  return (
    <div
      className="podi-skeleton-block"
      style={{ height }}
      aria-hidden="true"
    />
  );
}
