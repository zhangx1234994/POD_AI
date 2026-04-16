import { useEffect, useMemo, useState } from 'react';
import { clientApi } from '../services/clientApi';
import { getAbilityPresentationName } from '../utils/abilityPresentation';
import type { AbilityInfo } from '../types/api';

export function useAbilityPresentationMap() {
  const [abilities, setAbilities] = useState<AbilityInfo[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await clientApi.listAbilities();
        if (!cancelled) setAbilities(data.items || []);
      } catch {
        if (!cancelled) setAbilities([]);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return useMemo(() => {
    const map = new Map<string, string>();
    abilities.forEach((ability) => {
      const name = getAbilityPresentationName(ability);
      if (name && ability.capabilityKey) {
        map.set(ability.capabilityKey, name);
      }
    });
    return map;
  }, [abilities]);
}
