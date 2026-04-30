import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  BusinessCapability,
  BusinessCapabilityCompareResponse,
  BusinessCapabilityFormState,
  BusinessDefaultApproval,
  BusinessOperationLog,
  BusinessRun,
  BusinessUsageSummaryResponse,
} from '../../../types/admin';
import { businessKeyLabel } from './businessLabels';
import {
  createBusinessCapabilityFormState,
  createBusinessCapabilityPayload,
} from './businessDashboardState';

export interface BusinessRunFilters {
  businessKey: string;
  status: string;
  billingStatus: string;
  callbackStatus: string;
  version: string;
  source: string;
  tenantId: string;
  clientId: string;
  traceId: string;
  windowHours: number;
  limit: number;
}

interface BusinessDashboardActionsParams {
  businessForm: BusinessCapabilityFormState;
  businessRunFilters: BusinessRunFilters;
  defaultBusinessCapabilityForm: BusinessCapabilityFormState;
  effectiveBusinessCompareLeftId: string;
  effectiveBusinessCompareRightId: string;
  isBusinessReadOnly: boolean;
  selectedBusinessCompareLeft: BusinessCapability | null;
  selectedBusinessCompareRight: BusinessCapability | null;
  downloadBlob: (blob: Blob, filename: string) => void;
  load: () => Promise<void>;
  setBusinessActionError: Dispatch<SetStateAction<string | null>>;
  setBusinessActionLoadingId: Dispatch<SetStateAction<string | null>>;
  setBusinessCompareResult: Dispatch<SetStateAction<BusinessCapabilityCompareResponse | null>>;
  setBusinessDefaultApprovals: Dispatch<SetStateAction<BusinessDefaultApproval[]>>;
  setBusinessDialogOpen: Dispatch<SetStateAction<boolean>>;
  setBusinessForm: Dispatch<SetStateAction<BusinessCapabilityFormState>>;
  setBusinessFormError: Dispatch<SetStateAction<string | null>>;
  setBusinessOperationLogs: Dispatch<SetStateAction<BusinessOperationLog[]>>;
  setBusinessRunDetail: Dispatch<SetStateAction<BusinessRun | null>>;
  setBusinessRuns: Dispatch<SetStateAction<BusinessRun[]>>;
  setBusinessRunTotal: Dispatch<SetStateAction<number>>;
  setBusinessUsageSummary: Dispatch<SetStateAction<BusinessUsageSummaryResponse | null>>;
}

export const useBusinessDashboardActions = ({
  businessForm,
  businessRunFilters,
  defaultBusinessCapabilityForm,
  effectiveBusinessCompareLeftId,
  effectiveBusinessCompareRightId,
  isBusinessReadOnly,
  selectedBusinessCompareLeft,
  selectedBusinessCompareRight,
  downloadBlob,
  load,
  setBusinessActionError,
  setBusinessActionLoadingId,
  setBusinessCompareResult,
  setBusinessDefaultApprovals,
  setBusinessDialogOpen,
  setBusinessForm,
  setBusinessFormError,
  setBusinessOperationLogs,
  setBusinessRunDetail,
  setBusinessRuns,
  setBusinessRunTotal,
  setBusinessUsageSummary,
}: BusinessDashboardActionsParams) => {
  const resetBusinessForm = useCallback(() => {
    setBusinessForm(defaultBusinessCapabilityForm);
    setBusinessFormError(null);
    setBusinessActionError(null);
  }, [defaultBusinessCapabilityForm, setBusinessActionError, setBusinessForm, setBusinessFormError]);

  const handleBusinessEdit = useCallback(
    (item: BusinessCapability) => {
      setBusinessForm(createBusinessCapabilityFormState(item));
      setBusinessFormError(null);
      setBusinessActionError(null);
      setBusinessDialogOpen(true);
    },
    [setBusinessActionError, setBusinessDialogOpen, setBusinessForm, setBusinessFormError],
  );

  const handleBusinessSetDefault = useCallback(
    async (item: BusinessCapability) => {
      setBusinessActionError(null);
      if (
        !window.confirm(
          `确认申请把 ${businessKeyLabel(item.businessKey)} 的默认版本切到 ${item.version}？审批通过后，业务入口会优先使用这个版本。请确认已完成测评端真实链路测试。`,
        )
      ) {
        return;
      }
      setBusinessActionLoadingId(`default:${item.id}`);
      try {
        await adminApi.createBusinessDefaultApproval(item.id, {
          note: `申请切换 ${businessKeyLabel(item.businessKey)} 默认版本到 ${item.version}`,
        });
        await load();
      } catch (error: any) {
        console.error('create default approval failed', error);
        setBusinessActionError(error?.message || '默认版本切换申请失败，请检查服务日志。');
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [load, setBusinessActionError, setBusinessActionLoadingId],
  );

  const handleBusinessDefaultApprovalDecision = useCallback(
    async (item: BusinessDefaultApproval, decision: 'approve' | 'reject') => {
      setBusinessActionError(null);
      const actionId = `${decision}:approval:${item.id}`;
      setBusinessActionLoadingId(actionId);
      try {
        if (decision === 'approve') {
          await adminApi.approveBusinessDefaultApproval(item.id, { note: '管理端审批通过' });
        } else {
          await adminApi.rejectBusinessDefaultApproval(item.id, { note: '管理端驳回' });
        }
        await load();
      } catch (error: any) {
        console.error('default approval decision failed', error);
        setBusinessActionError(error?.message || '默认版本审批处理失败，请检查服务日志。');
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [load, setBusinessActionError, setBusinessActionLoadingId],
  );

  const handleBusinessToggleActive = useCallback(
    async (item: BusinessCapability) => {
      setBusinessActionError(null);
      const isActive = item.status === 'active';
      if (isActive && item.isDefault) {
        setBusinessActionError('默认版本不能直接停用，请先把同业务的其他版本设为默认。');
        return;
      }
      if (
        isActive &&
        !window.confirm(
          `确认停用 ${businessKeyLabel(item.businessKey)} ${item.version}？停用后它不能再作为灰度、对照或回滚目标使用。`,
        )
      ) {
        return;
      }
      setBusinessActionLoadingId(`status:${item.id}`);
      try {
        await adminApi.updateBusinessCapability(item.id, {
          status: isActive ? 'inactive' : 'active',
          isDefault: isActive ? false : item.isDefault,
        });
        await load();
      } catch (error: any) {
        console.error('toggle business capability status failed', error);
        setBusinessActionError(error?.message || '更新业务版本状态失败，请检查服务日志。');
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [load, setBusinessActionError, setBusinessActionLoadingId],
  );

  const handleBusinessCompare = useCallback(async () => {
    const leftId = effectiveBusinessCompareLeftId;
    const rightId = effectiveBusinessCompareRightId;
    setBusinessActionError(null);
    setBusinessCompareResult(null);
    if (!leftId || !rightId) {
      setBusinessActionError('请选择要对比的两个业务版本。');
      return;
    }
    setBusinessActionLoadingId('compare:business');
    try {
      const result = await adminApi.compareBusinessCapabilities(leftId, rightId);
      setBusinessCompareResult(result);
    } catch (error: any) {
      console.error('compare business capability failed', error);
      setBusinessActionError(error?.message || '版本对比失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [
    effectiveBusinessCompareLeftId,
    effectiveBusinessCompareRightId,
    setBusinessActionError,
    setBusinessActionLoadingId,
    setBusinessCompareResult,
  ]);

  const handleBusinessRollback = useCallback(async () => {
    const source = selectedBusinessCompareLeft;
    const target = selectedBusinessCompareRight;
    setBusinessActionError(null);
    if (!source || !target) {
      setBusinessActionError('请选择当前版本和要回到的目标版本。');
      return;
    }
    if (source.businessKey !== target.businessKey) {
      setBusinessActionError('只能在同一个业务下回滚版本。');
      return;
    }
    if (target.status !== 'active') {
      setBusinessActionError('目标版本不是启用状态，不能设为默认。');
      return;
    }
    if (
      !window.confirm(
        `确认把 ${businessKeyLabel(target.businessKey)} 默认版本回到 ${target.version}？当前版本不会自动停用，但新的业务入口会切到目标版本。请确认目标版本最近测试通过。`,
      )
    ) {
      return;
    }
    setBusinessActionLoadingId('rollback:business');
    try {
      await adminApi.rollbackBusinessCapability(source.id, {
        targetCapabilityId: target.id,
        note: `管理端回滚：${source.version} -> ${target.version}`,
      });
      setBusinessCompareResult(null);
      await load();
    } catch (error: any) {
      console.error('rollback business capability failed', error);
      setBusinessActionError(error?.message || '业务版本回滚失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [
    load,
    selectedBusinessCompareLeft,
    selectedBusinessCompareRight,
    setBusinessActionError,
    setBusinessActionLoadingId,
    setBusinessCompareResult,
  ]);

  const refreshBusinessRuns = useCallback(async () => {
    const [res, summary, operationLogs, approvals] = await Promise.all([
      adminApi.listBusinessRuns(businessRunFilters),
      adminApi.getBusinessUsageSummary(businessRunFilters),
      isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi.listBusinessOperationLogs({ businessKey: businessRunFilters.businessKey, limit: 20 }),
      isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi.listBusinessDefaultApprovals({ businessKey: businessRunFilters.businessKey, status: 'pending', limit: 20 }),
    ]);
    setBusinessRuns(res.items || []);
    setBusinessRunTotal(Number(res.total || 0));
    setBusinessUsageSummary(summary);
    setBusinessOperationLogs(operationLogs.items || []);
    setBusinessDefaultApprovals(approvals.items || []);
  }, [
    businessRunFilters,
    isBusinessReadOnly,
    setBusinessDefaultApprovals,
    setBusinessOperationLogs,
    setBusinessRuns,
    setBusinessRunTotal,
    setBusinessUsageSummary,
  ]);

  const exportBusinessRuns = useCallback(async () => {
    setBusinessActionError(null);
    setBusinessActionLoadingId('export:runs');
    try {
      const blob = await adminApi.exportBusinessRuns({ ...businessRunFilters, limit: 1000 });
      downloadBlob(blob, `business-runs-${Date.now()}.csv`);
    } catch (error: any) {
      console.error('export business runs failed', error);
      setBusinessActionError(error?.message || '导出业务调用记录失败，请检查筛选条件或服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [businessRunFilters, downloadBlob, setBusinessActionError, setBusinessActionLoadingId]);

  const handleBusinessCallbackRetry = useCallback(
    async (row: BusinessRun) => {
      setBusinessActionError(null);
      setBusinessActionLoadingId(`callback:${row.id}`);
      try {
        const next = await adminApi.retryBusinessRunCallback(row.runId || row.id);
        setBusinessRuns((prev) => prev.map((item) => (item.id === row.id ? next : item)));
        setBusinessRunDetail((prev) => (prev && prev.id === row.id ? next : prev));
        await refreshBusinessRuns();
      } catch (error: any) {
        console.error('retry business callback failed', error);
        setBusinessActionError(error?.message || '回调重试失败，请检查回调地址或服务日志。');
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [
      refreshBusinessRuns,
      setBusinessActionError,
      setBusinessActionLoadingId,
      setBusinessRunDetail,
      setBusinessRuns,
    ],
  );

  const handleBusinessSubmit = useCallback(async () => {
    const nextPayload = createBusinessCapabilityPayload(businessForm);
    if (!nextPayload.ok) {
      setBusinessFormError(nextPayload.error);
      return;
    }
    const { payload } = nextPayload;
    try {
      if (businessForm.id) {
        await adminApi.updateBusinessCapability(businessForm.id, payload);
      } else {
        await adminApi.createBusinessCapability({ ...payload, id: businessForm.id });
      }
      resetBusinessForm();
      setBusinessDialogOpen(false);
      void load();
    } catch (error: any) {
      console.error('save business capability failed', error);
      setBusinessFormError(error?.message || '保存业务版本失败，请检查服务日志。');
    }
  }, [businessForm, load, resetBusinessForm, setBusinessDialogOpen, setBusinessFormError]);

  return {
    resetBusinessForm,
    handleBusinessEdit,
    handleBusinessSetDefault,
    handleBusinessDefaultApprovalDecision,
    handleBusinessToggleActive,
    handleBusinessCompare,
    handleBusinessRollback,
    refreshBusinessRuns,
    exportBusinessRuns,
    handleBusinessCallbackRetry,
    handleBusinessSubmit,
  };
};
