import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { AI_ACTIONS } from '@/constants/sidebar';

type Pattern = string | RegExp;

/**
 * Hook to determine whether current route matches allowed patterns.
 * By default it uses `aiTools` paths as allow-list.
 */
export default function useRouteVisibility(allowed?: Pattern[]) {
  const location = useLocation();

  const patterns: Pattern[] = useMemo(() => {
    if (allowed && allowed.length > 0) return allowed;
    return (AI_ACTIONS || []).map((s) => s.path).filter(Boolean) as string[];
  }, [allowed]);

  const pathname = location?.pathname || '';

  return useMemo(() => {
    return patterns.some((p) => {
      if (typeof p === 'string') return pathname.startsWith(p);
      try {
        return p.test(pathname);
      } catch (e) {
        return false;
      }
    });
  }, [patterns, pathname]);
}
