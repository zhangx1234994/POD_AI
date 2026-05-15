import { useMemo } from 'react';
import type { Ability, BusinessCapability, BusinessCapabilityFormState, JsonRecord } from '../../../types/admin';
import { businessKeyLabel, canonicalBusinessKey } from './businessLabels';

interface BusinessRunFilterState {
  businessKey: string;
}

interface BusinessDashboardDerivedStateParams {
  abilities: Ability[];
  businessCapabilities: BusinessCapability[];
  businessRunFilters: BusinessRunFilterState;
  businessCompareLeftId: string;
  businessCompareRightId: string;
}

export const readBusinessRollout = (metadata?: JsonRecord | null) => {
  const rollout = metadata && typeof metadata.rollout === 'object' && !Array.isArray(metadata.rollout)
    ? (metadata.rollout as JsonRecord)
    : {};
  const allowlist = Array.isArray(rollout.allowlist) ? rollout.allowlist : [];
  const percent = Number(rollout.percent || 0);
  return {
    enabled: Boolean(rollout.enabled),
    percent: Number.isFinite(percent) ? percent : 0,
    allowlistText: allowlist.map((item) => String(item)).join('\n'),
  };
};

export const readBusinessVlAssist = (recipe?: JsonRecord | null) => {
  const vlAssist = recipe && typeof recipe.vlAssist === 'object' && !Array.isArray(recipe.vlAssist)
    ? (recipe.vlAssist as JsonRecord)
    : {};
  return {
    enabled: Boolean(vlAssist.enabled),
    abilityId: typeof vlAssist.abilityId === 'string' && vlAssist.abilityId.trim()
      ? vlAssist.abilityId
      : 'vl_analyze_image',
  };
};

const formatBusinessJsonValue = (value?: JsonRecord | null) => (value ? JSON.stringify(value, null, 2) : '');

const parseBusinessJson = (value?: string | JsonRecord): { ok: boolean; value: JsonRecord } => {
  if (!value) return { ok: true, value: {} };
  if (typeof value === 'object') return { ok: true, value };
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false, value: {} };
  }
};

const splitLinesOrComma = (value?: string): string[] =>
  String(value || '')
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);

export const createBusinessCapabilityFormState = (item: BusinessCapability): BusinessCapabilityFormState => {
  const rollout = readBusinessRollout(item.metadata);
  const vlAssist = readBusinessVlAssist(item.recipe);
  return {
    id: item.id,
    businessKey: item.businessKey || 'fission',
    version: item.version || 'v1',
    displayName: item.displayName || '',
    description: item.description || '',
    status: item.status || 'inactive',
    isDefault: Boolean(item.isDefault),
    releaseTime: item.releaseTime || '',
    primaryAbilityId:
      item.primaryAbilityId ||
      (item.recipe && typeof item.recipe.primaryAbilityId === 'string' ? String(item.recipe.primaryAbilityId) : ''),
    vlAssistEnabled: vlAssist.enabled,
    vlAssistAbilityId: vlAssist.abilityId,
    rolloutEnabled: rollout.enabled,
    rolloutPercent: rollout.percent,
    rolloutAllowlistText: rollout.allowlistText,
    recipeText: formatBusinessJsonValue(item.recipe),
    inputSchemaText: formatBusinessJsonValue(item.inputSchema),
    outputSchemaText: formatBusinessJsonValue(item.outputSchema),
    metadataText: formatBusinessJsonValue(item.metadata),
  };
};

export const createBusinessCapabilityPayload = (
  form: BusinessCapabilityFormState,
): { ok: true; payload: Partial<BusinessCapability> } | { ok: false; error: string } => {
  if (!form.businessKey || !form.version || !form.displayName || !form.primaryAbilityId) {
    return { ok: false, error: '请填写业务标识、版本、名称，并选择主执行能力。' };
  }

  const recipe = parseBusinessJson(form.recipeText);
  const inputSchema = parseBusinessJson(form.inputSchemaText);
  const outputSchema = parseBusinessJson(form.outputSchemaText);
  const metadata = parseBusinessJson(form.metadataText);
  if (!recipe.ok || !inputSchema.ok || !outputSchema.ok || !metadata.ok) {
    return { ok: false, error: '配方、输入字段、输出字段、元信息格式不正确。' };
  }

  const nextRecipe: JsonRecord = { ...recipe.value };
  if (form.vlAssistEnabled) {
    nextRecipe.vlAssist = {
      enabled: true,
      abilityId: form.vlAssistAbilityId || 'vl_analyze_image',
    };
  } else {
    delete nextRecipe.vlAssist;
  }

  const nextMetadata: JsonRecord = { ...metadata.value };
  const rolloutAllowlist = splitLinesOrComma(form.rolloutAllowlistText);
  if (form.rolloutEnabled || Number(form.rolloutPercent || 0) > 0 || rolloutAllowlist.length > 0) {
    nextMetadata.rollout = {
      enabled: Boolean(form.rolloutEnabled),
      percent: Math.max(0, Math.min(100, Number(form.rolloutPercent || 0))),
      allowlist: rolloutAllowlist,
    };
  } else {
    delete nextMetadata.rollout;
  }

  return {
    ok: true,
    payload: {
      businessKey: form.businessKey.trim(),
      version: form.version.trim(),
      displayName: form.displayName.trim(),
      description: form.description?.trim() || null,
      status: form.status || 'inactive',
      isDefault: Boolean(form.isDefault),
      releaseTime: form.releaseTime || null,
      primaryAbilityId: form.primaryAbilityId,
      recipe: nextRecipe,
      inputSchema: inputSchema.value,
      outputSchema: outputSchema.value,
      metadata: nextMetadata,
    },
  };
};

export const useBusinessDashboardDerivedState = ({
  abilities,
  businessCapabilities,
  businessRunFilters,
  businessCompareLeftId,
  businessCompareRightId,
}: BusinessDashboardDerivedStateParams) => {
  const businessAbilityOptions = useMemo(
    () =>
      abilities.map((item) => ({
        label: `${item.display_name} · ${item.provider}/${item.capability_key}`,
        value: item.id,
      })),
    [abilities],
  );

  const businessVlAbilityOptions = useMemo(
    () =>
      abilities
        .filter((item) => {
          const text = `${item.id} ${item.provider} ${item.category} ${item.capability_key}`.toLowerCase();
          return text.includes('vl') || text.includes('vision') || text.includes('analyze_image');
        })
        .map((item) => ({
          label: `${item.display_name} · ${item.provider}/${item.capability_key}`,
          value: item.id,
        })),
    [abilities],
  );

  const businessRunBusinessOptions = useMemo(() => {
    const seen = new Set<string>();
    const options = businessCapabilities
      .map((item) => canonicalBusinessKey(item.businessKey))
      .filter((key) => {
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .map((key) => ({ label: businessKeyLabel(key), value: key }));
    return [{ label: '全部业务', value: 'all' }, ...options];
  }, [businessCapabilities]);

  const businessRunVersionOptions = useMemo(() => {
    const businessKey = businessRunFilters.businessKey;
    const versions = businessCapabilities
      .filter((item) => businessKey === 'all' || canonicalBusinessKey(item.businessKey) === businessKey)
      .map((item) => item.version)
      .filter(Boolean);
    return [
      { label: '全部版本', value: 'all' },
      ...Array.from(new Set(versions)).map((version) => ({ label: version, value: version })),
    ];
  }, [businessCapabilities, businessRunFilters.businessKey]);

  const businessCapabilityVersionOptions = useMemo(
    () =>
      businessCapabilities.map((item) => ({
        label: `${businessKeyLabel(item.businessKey)} · ${item.version}${item.isDefault ? ' · 默认' : ''} · ${item.displayName}`,
        value: item.id,
      })),
    [businessCapabilities],
  );

  const effectiveBusinessCompareLeftId =
    businessCompareLeftId ||
    businessCapabilities.find((item) => item.isDefault)?.id ||
    businessCapabilities[0]?.id ||
    '';

  const selectedBusinessCompareLeft = useMemo(
    () => businessCapabilities.find((item) => item.id === effectiveBusinessCompareLeftId) || null,
    [businessCapabilities, effectiveBusinessCompareLeftId],
  );

  const businessCompareTargetOptions = useMemo(
    () =>
      businessCapabilities
        .filter((item) => {
          if (!selectedBusinessCompareLeft) return true;
          return canonicalBusinessKey(item.businessKey) === canonicalBusinessKey(selectedBusinessCompareLeft.businessKey) && item.id !== selectedBusinessCompareLeft.id;
        })
        .map((item) => ({
          label: `${item.version}${item.isDefault ? ' · 默认' : ''} · ${item.displayName}`,
          value: item.id,
        })),
    [businessCapabilities, selectedBusinessCompareLeft],
  );

  const effectiveBusinessCompareRightId =
    businessCompareRightId && businessCompareTargetOptions.some((item) => item.value === businessCompareRightId)
      ? businessCompareRightId
      : businessCompareTargetOptions[0]?.value || '';

  const selectedBusinessCompareRight = useMemo(
    () => businessCapabilities.find((item) => item.id === effectiveBusinessCompareRightId) || null,
    [businessCapabilities, effectiveBusinessCompareRightId],
  );

  return {
    businessAbilityOptions,
    businessVlAbilityOptions,
    businessRunBusinessOptions,
    businessRunVersionOptions,
    businessCapabilityVersionOptions,
    effectiveBusinessCompareLeftId,
    selectedBusinessCompareLeft,
    businessCompareTargetOptions,
    effectiveBusinessCompareRightId,
    selectedBusinessCompareRight,
  };
};
