import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  JsonRecord,
  VendorEgressCheckResponse,
  VendorGovernanceSummaryResponse,
  VendorKey,
  VendorKeyFormState,
  VendorModel,
  VendorModelFormState,
  VendorProvider,
  VendorUsageSummaryItem,
} from '../../../types/admin';
import {
  defaultVendorKeyForm,
  defaultVendorModelForm,
} from './integrationDashboardConfig';

const normalizeTagList = (value: unknown): string[] => {
  const out: string[] = [];
  if (!value) return out;
  if (Array.isArray(value)) {
    value.forEach((item) => {
      if (typeof item === 'string') {
        const trimmed = item.trim();
        if (trimmed) out.push(trimmed);
      } else if (item !== null && item !== undefined) {
        const trimmed = String(item).trim();
        if (trimmed) out.push(trimmed);
      }
    });
    return out;
  }
  if (typeof value === 'string') {
    value
      .replace(/;/g, ',')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((item) => out.push(item));
    return out;
  }
  const trimmed = String(value).trim();
  if (trimmed) out.push(trimmed);
  return out;
};

const normalizeTextList = (value: unknown): string[] => {
  if (typeof value === 'string') {
    return normalizeTagList(value.replace(/[\n，]/g, ','));
  }
  return normalizeTagList(value);
};

const formatTextList = (value?: string[] | null) => {
  if (!value || value.length === 0) return '';
  return value.join(', ');
};

const safeParseJSON = (value?: string | JsonRecord): { ok: boolean; value: JsonRecord } => {
  if (!value) return { ok: true, value: {} };
  if (typeof value === 'object') return { ok: true, value };
  try {
    return { ok: true, value: JSON.parse(value) };
  } catch {
    return { ok: false, value: {} };
  }
};

const stringifyJSON = (value?: string | JsonRecord) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

interface VendorModelActionsParams {
  extractErrorMessage: (error: unknown) => string;
  setVendorBaseUrl: Dispatch<SetStateAction<string>>;
  setVendorEgressChecks: Dispatch<SetStateAction<Record<string, VendorEgressCheckResponse>>>;
  setVendorError: Dispatch<SetStateAction<string>>;
  setVendorGovernanceSummary: Dispatch<SetStateAction<VendorGovernanceSummaryResponse | null>>;
  setVendorKeyForm: Dispatch<SetStateAction<VendorKeyFormState>>;
  setVendorKeys: Dispatch<SetStateAction<VendorKey[]>>;
  setVendorLoading: Dispatch<SetStateAction<boolean>>;
  setVendorModelForm: Dispatch<SetStateAction<VendorModelFormState>>;
  setVendorModelFormError: Dispatch<SetStateAction<string | null>>;
  setVendorModels: Dispatch<SetStateAction<VendorModel[]>>;
  setVendorNotice: Dispatch<SetStateAction<string>>;
  setVendorProviders: Dispatch<SetStateAction<VendorProvider[]>>;
  setVendorUsageItems: Dispatch<SetStateAction<VendorUsageSummaryItem[]>>;
  setVendorUsageWindowHours: Dispatch<SetStateAction<number>>;
  vendorKeyForm: VendorKeyFormState;
  vendorModelForm: VendorModelFormState;
}

export const useVendorModelActions = ({
  extractErrorMessage,
  setVendorBaseUrl,
  setVendorEgressChecks,
  setVendorError,
  setVendorGovernanceSummary,
  setVendorKeyForm,
  setVendorKeys,
  setVendorLoading,
  setVendorModelForm,
  setVendorModelFormError,
  setVendorModels,
  setVendorNotice,
  setVendorProviders,
  setVendorUsageItems,
  setVendorUsageWindowHours,
  vendorKeyForm,
  vendorModelForm,
}: VendorModelActionsParams) => {
  const loadVendorCatalog = useCallback(async () => {
    setVendorLoading(true);
    setVendorError('');
    setVendorNotice('');
    try {
      const [providers, keys, models, usage, governance] = await Promise.all([
        adminApi.listVendorProviders(),
        adminApi.listVendorKeys(),
        adminApi.listVendorModels(),
        adminApi.getVendorUsageSummary(24),
        adminApi.getVendorGovernanceSummary(24).catch(() => null),
      ]);
      setVendorProviders(providers.providers || []);
      setVendorKeys(keys.items || []);
      setVendorModels(models.items || []);
      setVendorUsageItems(usage.items || []);
      setVendorUsageWindowHours(Number(usage.windowHours || 24));
      if (governance) setVendorGovernanceSummary(governance);
      setVendorBaseUrl(providers.baseUrl || keys.baseUrl || models.baseUrl || usage.baseUrl || governance?.baseUrl || '');
    } catch (error) {
      setVendorError(extractErrorMessage(error) || '模型弹药库加载失败');
    } finally {
      setVendorLoading(false);
    }
  }, [
    extractErrorMessage,
    setVendorBaseUrl,
    setVendorError,
    setVendorGovernanceSummary,
    setVendorKeys,
    setVendorLoading,
    setVendorModels,
    setVendorNotice,
    setVendorProviders,
    setVendorUsageItems,
    setVendorUsageWindowHours,
  ]);

  const handleSyncVolcengineModels = useCallback(async () => {
    setVendorLoading(true);
    setVendorError('');
    setVendorNotice('');
    try {
      const result = await adminApi.syncVolcengineModels();
      await loadVendorCatalog();
      setVendorNotice(
        `火山模型已同步：新增 ${result.created} 个，更新 ${result.updated} 个，跳过 ${result.skipped} 个。`,
      );
    } catch (error) {
      setVendorError(extractErrorMessage(error) || '火山模型同步失败，请检查 VOLCENGINE_API_KEY 和服务出网。');
    } finally {
      setVendorLoading(false);
    }
  }, [extractErrorMessage, loadVendorCatalog, setVendorError, setVendorLoading, setVendorNotice]);

  const handleVendorEgressCheck = useCallback(
    async (provider: string, includeAuth = false) => {
      setVendorError('');
      try {
        const result = await adminApi.checkVendorProviderEgress(provider, { check: 'models', includeAuth });
        setVendorEgressChecks((prev) => ({ ...prev, [provider]: result }));
      } catch (error) {
        setVendorError(extractErrorMessage(error) || '出网检查失败');
      }
    },
    [extractErrorMessage, setVendorEgressChecks, setVendorError],
  );

  const resetVendorModelForm = useCallback(
    (seed?: VendorModel) => {
      if (!seed) {
        setVendorModelForm(defaultVendorModelForm);
        setVendorModelFormError(null);
        return;
      }
      setVendorModelForm({
        ...seed,
        apiTypesText: formatTextList(seed.apiTypes),
        executionModesText: formatTextList(seed.executionModes),
        metadataText: stringifyJSON(seed.metadata as JsonRecord),
        routePolicyText: stringifyJSON(seed.routePolicy as JsonRecord),
        defaultTaskPolicyText: stringifyJSON(seed.defaultTaskPolicy as JsonRecord),
        inputSchemaText: stringifyJSON(seed.inputSchema as JsonRecord),
        costPolicyText: stringifyJSON(seed.costPolicy as JsonRecord),
      });
      setVendorModelFormError(null);
    },
    [setVendorModelForm, setVendorModelFormError],
  );

  const handleVendorModelSubmit = useCallback(async () => {
    if (!vendorModelForm.provider || !vendorModelForm.model || !vendorModelForm.displayName) {
      setVendorModelFormError('请填写厂商标识、模型编号和显示名称');
      return;
    }
    const jsonFields = [
      ['metadata', vendorModelForm.metadataText],
      ['routePolicy', vendorModelForm.routePolicyText],
      ['defaultTaskPolicy', vendorModelForm.defaultTaskPolicyText],
      ['inputSchema', vendorModelForm.inputSchemaText],
      ['costPolicy', vendorModelForm.costPolicyText],
    ] as const;
    const jsonFieldLabels: Record<(typeof jsonFields)[number][0], string> = {
      metadata: '元信息',
      routePolicy: '路由策略',
      defaultTaskPolicy: '默认任务策略',
      inputSchema: '入参结构',
      costPolicy: '计价策略',
    };
    const parsedJson: Record<string, JsonRecord> = {};
    for (const [key, raw] of jsonFields) {
      const parsed = safeParseJSON(raw);
      if (!parsed.ok) {
        setVendorModelFormError(`${jsonFieldLabels[key]}格式不正确`);
        return;
      }
      parsedJson[key] = parsed.value;
    }
    setVendorModelFormError(null);
    setVendorError('');
    const payload: Partial<VendorModel> = {
      provider: String(vendorModelForm.provider),
      model: String(vendorModelForm.model),
      displayName: String(vendorModelForm.displayName),
      status: String(vendorModelForm.status || 'active'),
      apiTypes: normalizeTextList(vendorModelForm.apiTypesText || vendorModelForm.apiTypes),
      executionModes: normalizeTextList(vendorModelForm.executionModesText || vendorModelForm.executionModes),
      supportsMask: Boolean(vendorModelForm.supportsMask),
      supportsMultipleImages: Boolean(vendorModelForm.supportsMultipleImages),
      supportsVideo: Boolean(vendorModelForm.supportsVideo),
      supportsText: Boolean(vendorModelForm.supportsText),
      requiresGlobalEgress: Boolean(vendorModelForm.requiresGlobalEgress),
      source: String(vendorModelForm.source || 'backend-admin'),
      metadata: parsedJson.metadata,
      routePolicy: parsedJson.routePolicy,
      defaultTaskPolicy: parsedJson.defaultTaskPolicy,
      inputSchema: parsedJson.inputSchema,
      costPolicy: parsedJson.costPolicy,
    };
    try {
      if (vendorModelForm.id) {
        await adminApi.updateVendorModel(Number(vendorModelForm.id), payload);
      } else {
        await adminApi.createVendorModel(payload);
      }
      resetVendorModelForm();
      await loadVendorCatalog();
    } catch (error) {
      setVendorModelFormError(extractErrorMessage(error) || '保存模型失败');
    }
  }, [
    extractErrorMessage,
    loadVendorCatalog,
    resetVendorModelForm,
    setVendorError,
    setVendorModelFormError,
    vendorModelForm,
  ]);

  const handleVendorKeySubmit = useCallback(async () => {
    if (!vendorKeyForm.provider || !vendorKeyForm.alias || !vendorKeyForm.status) return;
    setVendorError('');
    try {
      if (vendorKeyForm.id) {
        await adminApi.updateVendorKey(vendorKeyForm.id, {
          alias: vendorKeyForm.alias,
          key: vendorKeyForm.key,
          secret: vendorKeyForm.secret,
          model: vendorKeyForm.model,
          status: vendorKeyForm.status,
          dailyQuota: vendorKeyForm.dailyQuota,
          monthlyQuota: vendorKeyForm.monthlyQuota,
          maxConcurrency: vendorKeyForm.maxConcurrency,
          metadata: vendorKeyForm.metadata,
        });
      } else if (vendorKeyForm.key) {
        const provider = String(vendorKeyForm.provider);
        const alias = String(vendorKeyForm.alias);
        await adminApi.createVendorKey({
          provider,
          alias,
          key: vendorKeyForm.key,
          secret: vendorKeyForm.secret,
          model: vendorKeyForm.model,
          status: vendorKeyForm.status,
          dailyQuota: vendorKeyForm.dailyQuota,
          monthlyQuota: vendorKeyForm.monthlyQuota,
          maxConcurrency: vendorKeyForm.maxConcurrency,
          metadata: vendorKeyForm.metadata,
        });
      } else {
        return;
      }
      setVendorKeyForm(defaultVendorKeyForm);
      await loadVendorCatalog();
    } catch (error) {
      setVendorError(extractErrorMessage(error) || '保存 vendor key 失败');
    }
  }, [
    extractErrorMessage,
    loadVendorCatalog,
    setVendorError,
    setVendorKeyForm,
    vendorKeyForm,
  ]);

  return {
    handleSyncVolcengineModels,
    handleVendorEgressCheck,
    handleVendorKeySubmit,
    handleVendorModelSubmit,
    loadVendorCatalog,
    resetVendorModelForm,
  };
};
