import { useMemo } from 'react';
import type {
  ComfyuiAgent,
  ComfyuiAgentAlert,
  ComfyuiAgentManifest,
  ComfyuiAgentTask,
  ComfyuiRepairJob,
  Executor,
} from '../../../types/admin';
import {
  buildComfySyncGuide,
  buildComfySyncSteps,
  type ComfyuiManageTab,
} from './comfyuiDashboardConfig';

const isMockLikeRecord = (value?: string | null): boolean => {
  const text = String(value || '').trim().toLowerCase();
  if (!text) return false;
  return /(^|[-_])mock([-_]|$)/.test(text) || text.includes('history_success_no_images');
};

const finalTaskStatusSet = new Set(['success', 'succeeded', 'completed', 'failed', 'error', 'cancelled', 'canceled', 'stopped']);

interface ComfyuiDashboardDerivedStateParams {
  activeTab: ComfyuiManageTab;
  agentAlerts: ComfyuiAgentAlert[];
  agentList: ComfyuiAgent[];
  agentTasks: ComfyuiAgentTask[];
  baselineExecutorId: string;
  diffLogCount: number;
  executors: Executor[];
  manifestList: ComfyuiAgentManifest[];
  repairJobs: ComfyuiRepairJob[];
  showTestNodes: boolean;
}

export const useComfyuiDashboardDerivedState = ({
  activeTab,
  agentAlerts,
  agentList,
  agentTasks,
  baselineExecutorId,
  diffLogCount,
  executors,
  manifestList,
  repairJobs,
  showTestNodes,
}: ComfyuiDashboardDerivedStateParams) => {
  const allComfyExecutors = useMemo(
    () => executors.filter((executor) => (executor.type || '').toLowerCase().includes('comfyui')),
    [executors],
  );

  const comfyExecutors = useMemo(() => {
    if (showTestNodes) return allComfyExecutors;
    return allComfyExecutors.filter((executor) => !isMockLikeRecord(executor.id) && !isMockLikeRecord(executor.name));
  }, [allComfyExecutors, showTestNodes]);

  const comfyHiddenExecutorCount = useMemo(
    () => Math.max(0, allComfyExecutors.length - comfyExecutors.length),
    [allComfyExecutors.length, comfyExecutors.length],
  );

  const visibleComfyAgentList = useMemo(() => {
    if (showTestNodes) return agentList;
    return agentList.filter((agent) => !isMockLikeRecord(agent.id) && !isMockLikeRecord(agent.name));
  }, [agentList, showTestNodes]);

  const comfyHiddenAgentCount = useMemo(
    () => Math.max(0, agentList.length - visibleComfyAgentList.length),
    [agentList.length, visibleComfyAgentList.length],
  );

  const comfyAgentMap = useMemo(() => {
    const map = new Map<string, ComfyuiAgent>();
    visibleComfyAgentList.forEach((agent) => map.set(agent.id, agent));
    return map;
  }, [visibleComfyAgentList]);

  const comfyAgentOptions = useMemo(
    () =>
      visibleComfyAgentList.map((agent) => ({
        label: agent.name ? `${agent.name} · ${agent.id}` : agent.id,
        value: agent.id,
      })),
    [visibleComfyAgentList],
  );

  const comfyManifestOptions = useMemo(
    () =>
      manifestList.map((manifest) => ({
        label: `${manifest.role} · ${manifest.version}`,
        value: String(manifest.id),
      })),
    [manifestList],
  );

  const visibleComfyAgentTasks = useMemo(() => {
    if (showTestNodes) return agentTasks;
    return agentTasks.filter((task) => !isMockLikeRecord(task.agentId));
  }, [agentTasks, showTestNodes]);

  const comfyPublishedManifestCount = useMemo(
    () => manifestList.filter((item) => String(item.status || '').toLowerCase() === 'published').length,
    [manifestList],
  );

  const comfyRunningTaskCount = useMemo(
    () =>
      visibleComfyAgentTasks.filter((task) => {
        const status = String(task.finalStatus || task.status || '').toLowerCase();
        return status ? !finalTaskStatusSet.has(status) : true;
      }).length,
    [visibleComfyAgentTasks],
  );

  const comfyRepairRunningCount = useMemo(
    () =>
      repairJobs.filter((job) => {
        const status = String(job.status || '').toLowerCase();
        return status ? !finalTaskStatusSet.has(status) : true;
      }).length,
    [repairJobs],
  );

  const comfyRepairFailedCount = useMemo(
    () =>
      repairJobs.filter((job) => {
        const status = String(job.status || '').toLowerCase();
        return status === 'failed' || status === 'error';
      }).length,
    [repairJobs],
  );

  const comfySyncSteps = useMemo(
    () =>
      buildComfySyncSteps({
        activeTab,
        baselineExecutorId,
        diffLogCount,
        executorCount: comfyExecutors.length,
        manifestCount: manifestList.length,
        publishedManifestCount: comfyPublishedManifestCount,
        runningTaskCount: comfyRunningTaskCount,
        visibleTaskCount: visibleComfyAgentTasks.length,
      }),
    [
      activeTab,
      baselineExecutorId,
      comfyExecutors.length,
      comfyPublishedManifestCount,
      comfyRunningTaskCount,
      diffLogCount,
      manifestList.length,
      visibleComfyAgentTasks.length,
    ],
  );

  const comfySyncCurrentStep = useMemo(
    () => comfySyncSteps.find((item) => item.tab === activeTab) || null,
    [activeTab, comfySyncSteps],
  );

  const comfySyncCurrentGuide = useMemo(
    () =>
      buildComfySyncGuide({
        activeTab,
        baselineExecutorId,
        manifestCount: manifestList.length,
        publishedManifestCount: comfyPublishedManifestCount,
        runningTaskCount: comfyRunningTaskCount,
        visibleTaskCount: visibleComfyAgentTasks.length,
      }),
    [
      activeTab,
      baselineExecutorId,
      comfyPublishedManifestCount,
      comfyRunningTaskCount,
      manifestList.length,
      visibleComfyAgentTasks.length,
    ],
  );

  const visibleComfyAgentAlerts = useMemo(() => {
    if (showTestNodes) return agentAlerts;
    return agentAlerts.filter((item) => !isMockLikeRecord(item.agentId));
  }, [agentAlerts, showTestNodes]);

  return {
    comfyAgentMap,
    comfyAgentOptions,
    comfyExecutors,
    comfyHiddenAgentCount,
    comfyHiddenExecutorCount,
    comfyManifestOptions,
    comfyPublishedManifestCount,
    comfyRepairFailedCount,
    comfyRepairRunningCount,
    comfyRunningTaskCount,
    comfySyncCurrentGuide,
    comfySyncCurrentStep,
    comfySyncSteps,
    visibleComfyAgentAlerts,
    visibleComfyAgentList,
    visibleComfyAgentTasks,
  };
};
