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
import { businessKeyLabel, canonicalBusinessKey } from './businessLabels';
import {
  createBusinessCapabilityFormState,
  createBusinessCapabilityPayload,
} from './businessDashboardState';

export interface BusinessRunFilters {
  businessKey: string;
  status: string;
  billingStatus: string;
  callbackStatus: string;
  issueCategory: string;
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
  businessRuns: BusinessRun[];
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

export interface BusinessDraftRunBatchItem {
  capability: BusinessCapability;
  payload: Record<string, unknown>;
}

export interface BusinessDraftRunBatchResult {
  submitted: number;
  total: number;
  runIds: string[];
  errors: string[];
}

export const useBusinessDashboardActions = ({
  businessForm,
  businessRuns,
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

  const handleBusinessCreateDraft = useCallback(
    async (item: BusinessCapability) => {
      setBusinessActionError(null);
      setBusinessActionLoadingId(`create-draft:${item.id}`);
      try {
        const draft = await adminApi.createBusinessCapabilityDraft(item.id, {
          note: `从 ${businessKeyLabel(item.businessKey)} ${item.version} 复制草稿，用于业务链路图调整。`,
        });
        await load();
        return draft;
      } catch (error: any) {
        console.error('create business draft failed', error);
        setBusinessActionError(error?.message || '复制草稿失败，请检查服务日志。');
        return null;
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [load, setBusinessActionError, setBusinessActionLoadingId],
  );

  const handleBusinessDraftRecipeUpdate = useCallback(
    async (
      item: BusinessCapability,
      payload: { recipe: Record<string, unknown>; primaryAbilityId?: string | null; note?: string | null },
    ) => {
      setBusinessActionError(null);
      setBusinessActionLoadingId(`save-draft-recipe:${item.id}`);
      try {
        const draft = await adminApi.updateBusinessCapabilityDraftRecipe(item.id, payload);
        await load();
        return draft;
      } catch (error: any) {
        console.error('save business draft recipe failed', error);
        setBusinessActionError(error?.message || '保存草稿配方失败，请检查服务日志。');
        return null;
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [load, setBusinessActionError, setBusinessActionLoadingId],
  );

  const handleBusinessSetDefault = useCallback(
    async (item: BusinessCapability) => {
      setBusinessActionError(null);
      if (item.releaseGate?.canRequestDefault === false) {
        const suggestion = item.releaseGate.suggestions?.[0] || '先完成业务真实链路验收，并记录“验收通过”。';
        setBusinessActionError(`暂不能申请默认版本切换：${suggestion}`);
        return;
      }
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

  const handleBusinessRecordAcceptance = useCallback(
    async (item: BusinessCapability) => {
      setBusinessActionError(null);
      const note = window.prompt(
        `记录 ${businessKeyLabel(item.businessKey)} ${item.version} 的人工验收结论。请填写验收说明：`,
        '测评端真实链路通过，回调和结果回填正常。',
      );
      if (note === null) return;
      setBusinessActionLoadingId(`acceptance:${item.id}`);
      try {
        await adminApi.recordBusinessCapabilityAcceptance(item.id, {
          status: 'passed',
          note,
          checklist: {
            businessFlow: true,
            callback: true,
            resultAssets: true,
          },
          metadata: {
            source: 'admin-web',
          },
        });
        await load();
      } catch (error: any) {
        console.error('record business acceptance failed', error);
        setBusinessActionError(error?.message || '记录业务版本验收失败，请检查服务日志。');
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
    const res = await adminApi.listBusinessRuns(businessRunFilters);
    setBusinessRuns(res.items || []);
    setBusinessRunTotal(Number(res.total || 0));
    const [summary, operationLogs, approvals] = await Promise.allSettled([
      adminApi.getBusinessUsageSummary(businessRunFilters),
      isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi.listBusinessOperationLogs({ businessKey: businessRunFilters.businessKey, limit: 20 }),
      isBusinessReadOnly
        ? Promise.resolve({ items: [] })
        : adminApi.listBusinessDefaultApprovals({ businessKey: businessRunFilters.businessKey, status: 'pending', limit: 20 }),
    ]);
    if (summary.status === 'fulfilled') {
      setBusinessUsageSummary(summary.value);
    }
    if (operationLogs.status === 'fulfilled') {
      setBusinessOperationLogs(operationLogs.value.items || []);
    }
    if (approvals.status === 'fulfilled') {
      setBusinessDefaultApprovals(approvals.value.items || []);
    }
  }, [
    businessRunFilters,
    isBusinessReadOnly,
    setBusinessDefaultApprovals,
    setBusinessOperationLogs,
    setBusinessRuns,
    setBusinessRunTotal,
    setBusinessUsageSummary,
  ]);

  const handleBusinessDraftRun = useCallback(
    async (item: BusinessCapability, draftPayload?: Record<string, unknown>) => {
      setBusinessActionError(null);
      const businessKey = canonicalBusinessKey(item.businessKey);
      let payload: Record<string, unknown> = draftPayload ? { ...draftPayload } : {};
      if (!draftPayload) {
        const label = businessKeyLabel(item.businessKey);
        const imageUrl = window.prompt(`试运行 ${label} ${item.version}。请输入一张可公网访问的样图 URL：`, '');
        if (!imageUrl) return;
        payload.imageUrl = imageUrl.trim();
        if (businessKey === 'fission_evaluate') {
          const generatedImageUrl = window.prompt('这个业务需要同时提供生成图 URL。请输入生成图 URL：', '');
          if (!generatedImageUrl) return;
          payload.generatedImageUrl = generatedImageUrl.trim();
        }
      }
      const imageUrl = String(payload.imageUrl || payload.originalImageUrl || '').trim();
      const generatedImageUrl = String(payload.generatedImageUrl || '').trim();
      if (!imageUrl) {
        setBusinessActionError('请先填写样图 URL。');
        return;
      }
      if (businessKey === 'fission_evaluate' && !generatedImageUrl) {
        setBusinessActionError('裂变评分试运行需要同时填写生成图 URL。');
        return;
      }
      payload = {
        ...payload,
        imageUrl,
        source: 'admin-draft-run',
        channel: 'admin-web',
        requestId: `admin-draft-${Date.now()}`,
        metadata: {
          ...((payload.metadata && typeof payload.metadata === 'object' && !Array.isArray(payload.metadata)
            ? payload.metadata
            : {}) as Record<string, unknown>),
          adminDraftRun: true,
          capabilityId: item.id,
        },
      };
      if (businessKey === 'fission_evaluate') {
        payload.originalImageUrl = imageUrl;
        payload.generatedImageUrl = generatedImageUrl;
      }
      setBusinessActionLoadingId(`draft-run:${item.id}`);
      try {
        const run = await adminApi.runBusinessCapabilityDraft(item.id, payload);
        setBusinessRunDetail(run);
        setBusinessActionError(`试运行已提交：${run.runId || run.id}。可在下方业务任务清单继续跟踪。`);
        await refreshBusinessRuns();
      } catch (error: any) {
        console.error('run business draft capability failed', error);
        setBusinessActionError(error?.message || '业务版本试运行失败，请检查样图 URL、底层能力和服务日志。');
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [
      refreshBusinessRuns,
      setBusinessActionError,
      setBusinessActionLoadingId,
      setBusinessRunDetail,
    ],
  );

  const handleBusinessDraftRunBatch = useCallback(
    async (items: BusinessDraftRunBatchItem[]): Promise<BusinessDraftRunBatchResult> => {
      setBusinessActionError(null);
      const total = items.length;
      const runIds: string[] = [];
      const errors: string[] = [];
      if (total <= 0) {
        setBusinessActionError('没有可提交的固定样例。');
        return { submitted: 0, total: 0, runIds, errors: ['没有可提交的固定样例。'] };
      }
      setBusinessActionLoadingId('draft-run-batch');
      try {
        let latestRun: BusinessRun | null = null;
        for (const entry of items) {
          const item = entry.capability;
          const businessKey = canonicalBusinessKey(item.businessKey);
          const imageUrl = String(entry.payload.imageUrl || entry.payload.originalImageUrl || '').trim();
          const generatedImageUrl = String(entry.payload.generatedImageUrl || '').trim();
          if (!imageUrl) {
            errors.push(`${businessKeyLabel(item.businessKey)} ${item.version}：缺少样例图片 URL`);
            continue;
          }
          if (businessKey === 'fission_evaluate' && !generatedImageUrl) {
            errors.push(`${businessKeyLabel(item.businessKey)} ${item.version}：缺少生成图 URL`);
            continue;
          }
          const metadata =
            entry.payload.metadata && typeof entry.payload.metadata === 'object' && !Array.isArray(entry.payload.metadata)
              ? (entry.payload.metadata as Record<string, unknown>)
              : {};
          const payload: Record<string, unknown> = {
            ...entry.payload,
            imageUrl,
            source: 'admin-fixed-sample-batch',
            channel: 'admin-web',
            requestId: `admin-qsample-${Date.now()}-${runIds.length + errors.length}`,
            metadata: {
              ...metadata,
              adminDraftRun: true,
              fixedSampleBatch: true,
              capabilityId: item.id,
            },
          };
          if (businessKey === 'fission_evaluate') {
            payload.originalImageUrl = imageUrl;
            payload.generatedImageUrl = generatedImageUrl;
          }
          try {
            const run = await adminApi.runBusinessCapabilityDraft(item.id, payload);
            latestRun = run;
            runIds.push(run.runId || run.id);
          } catch (error: any) {
            console.error('run business fixed sample batch item failed', error);
            errors.push(`${businessKeyLabel(item.businessKey)} ${item.version}：${error?.message || '提交失败'}`);
          }
        }
        if (latestRun) {
          setBusinessRunDetail(latestRun);
        }
        await refreshBusinessRuns();
        const message =
          errors.length > 0
            ? `固定样例批量提交 ${runIds.length}/${total}，失败 ${errors.length} 条：${errors.slice(0, 2).join('；')}`
            : `固定样例批量提交完成：${runIds.length}/${total}。等待结果完成后到 runId 详情标注质量。`;
        setBusinessActionError(message);
        return { submitted: runIds.length, total, runIds, errors };
      } finally {
        setBusinessActionLoadingId(null);
      }
    },
    [
      refreshBusinessRuns,
      setBusinessActionError,
      setBusinessActionLoadingId,
      setBusinessRunDetail,
    ],
  );

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

  const handleBusinessBulkCallbackRetry = useCallback(async () => {
    const runIds = businessRuns
      .filter((row) => row.callbackStatus === 'failed' || Boolean(row.callbackError))
      .map((row) => row.runId || row.id);
    if (runIds.length === 0) {
      setBusinessActionError('当前已加载记录里没有回调失败任务。先筛选“业务回调问题”或刷新列表。');
      return;
    }
    if (!window.confirm(`确认重试当前已加载的 ${runIds.length} 条回调失败任务？`)) return;
    setBusinessActionError(null);
    setBusinessActionLoadingId('bulk:callback');
    try {
      const res = await adminApi.bulkRetryBusinessRunCallbacks({ runIds, onlyFailed: true });
      if (res.failed > 0) {
        setBusinessActionError(`批量回调重试完成：成功 ${res.succeeded} 条，失败或跳过 ${res.failed} 条。`);
      }
      await refreshBusinessRuns();
    } catch (error: any) {
      console.error('bulk retry business callbacks failed', error);
      setBusinessActionError(error?.message || '批量回调重试失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [businessRuns, refreshBusinessRuns, setBusinessActionError, setBusinessActionLoadingId]);

  const handleBusinessBulkRetest = useCallback(async () => {
    const runIds = businessRuns
      .filter((row) => {
        const status = String(row.status || '').toLowerCase();
        const hasIssue = Boolean(row.issueCategory && row.issueCategory !== 'none');
        return hasIssue || status === 'failed' || status === 'cancelled';
      })
      .map((row) => row.runId || row.id);
    if (runIds.length === 0) {
      setBusinessActionError('当前已加载记录里没有需要复测的问题任务。先按问题类型筛选或刷新列表。');
      return;
    }
    if (
      !window.confirm(
        `确认按原始入参复测当前已加载的 ${runIds.length} 条问题任务？复测会创建新任务，但不会沿用旧任务的业务回调地址。`,
      )
    ) {
      return;
    }
    setBusinessActionError(null);
    setBusinessActionLoadingId('bulk:retest');
    try {
      const res = await adminApi.bulkRetestBusinessRuns({ runIds, onlyFailed: true });
      const summary = `批量复测已提交：新建 ${res.succeeded} 条，失败或跳过 ${res.failed} 条。`;
      setBusinessActionError(summary);
      await refreshBusinessRuns();
    } catch (error: any) {
      console.error('bulk retest business runs failed', error);
      setBusinessActionError(error?.message || '批量复测失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [businessRuns, refreshBusinessRuns, setBusinessActionError, setBusinessActionLoadingId]);

  const handleBusinessBulkIgnoreIssues = useCallback(async () => {
    const runIds = businessRuns
      .filter((row) => row.issueCategory && row.issueCategory !== 'none')
      .map((row) => row.runId || row.id);
    if (runIds.length === 0) {
      setBusinessActionError('当前已加载记录里没有待处理链路问题。先按问题类型筛选或刷新列表。');
      return;
    }
    const note = window.prompt(
      `确认把当前已加载的 ${runIds.length} 条问题记录标记为“无需处理”？请填写原因，方便后续复盘。`,
      '已人工确认，本轮暂不继续处理。',
    );
    if (note === null) return;
    setBusinessActionError(null);
    setBusinessActionLoadingId('bulk:ignore');
    try {
      const res = await adminApi.bulkMarkBusinessRunsIgnored({ runIds, note });
      if (res.failed > 0) {
        setBusinessActionError(`批量标记完成：成功 ${res.succeeded} 条，失败 ${res.failed} 条。`);
      }
      await refreshBusinessRuns();
    } catch (error: any) {
      console.error('bulk ignore business issues failed', error);
      setBusinessActionError(error?.message || '批量标记无需处理失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [businessRuns, refreshBusinessRuns, setBusinessActionError, setBusinessActionLoadingId]);

  const handleBusinessGenerateIssueChecklist = useCallback(async () => {
    const runIds = businessRuns
      .filter((row) => row.issueCategory && row.issueCategory !== 'none')
      .map((row) => row.runId || row.id);
    if (runIds.length === 0) {
      setBusinessActionError('当前已加载记录里没有待处理链路问题。先按问题类型筛选或刷新列表。');
      return;
    }
    setBusinessActionError(null);
    setBusinessActionLoadingId('bulk:checklist');
    try {
      const res = await adminApi.generateBusinessRunIssueChecklist({ runIds, onlyFailed: true });
      const markdown = String(res.markdown || '').trim();
      if (markdown && navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(markdown);
        setBusinessActionError(`已生成 ${res.issueCount} 条排障清单，并复制到剪贴板；跳过 ${res.skippedCount} 条。`);
      } else {
        const blob = new Blob([markdown || '当前没有需要处理的问题记录。'], { type: 'text/markdown;charset=utf-8' });
        downloadBlob(blob, `business-issue-checklist-${Date.now()}.md`);
        setBusinessActionError(`已生成 ${res.issueCount} 条排障清单并下载；跳过 ${res.skippedCount} 条。`);
      }
    } catch (error: any) {
      console.error('generate business issue checklist failed', error);
      setBusinessActionError(error?.message || '生成排障清单失败，请检查服务日志。');
    } finally {
      setBusinessActionLoadingId(null);
    }
  }, [businessRuns, downloadBlob, setBusinessActionError, setBusinessActionLoadingId]);

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
    handleBusinessCreateDraft,
    handleBusinessDraftRecipeUpdate,
    handleBusinessSetDefault,
    handleBusinessDefaultApprovalDecision,
    handleBusinessToggleActive,
    handleBusinessRecordAcceptance,
    handleBusinessDraftRun,
    handleBusinessDraftRunBatch,
    handleBusinessCompare,
    handleBusinessRollback,
    refreshBusinessRuns,
    exportBusinessRuns,
    handleBusinessCallbackRetry,
    handleBusinessBulkCallbackRetry,
    handleBusinessBulkRetest,
    handleBusinessBulkIgnoreIssues,
    handleBusinessGenerateIssueChecklist,
    handleBusinessSubmit,
  };
};
