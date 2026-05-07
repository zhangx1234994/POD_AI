import { lazy } from 'react';

export const AbilityEvaluationPage = lazy(() =>
  import('../../../pages/AbilityEvaluation/AbilityEvaluationPage').then((mod) => ({
    default: mod.AbilityEvaluationPage,
  })),
);

export const BusinessCapabilityGrid = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessCapabilityGrid })),
);
export const BusinessCoreEntryPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessCoreEntryPanel })),
);
export const BusinessCoreClosurePanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessCoreClosurePanel })),
);
export const BusinessOrchestrationMapPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessOrchestrationMapPanel })),
);
export const BusinessCapabilityEditorDialog = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessCapabilityEditorDialog })),
);
export const BusinessActionPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessActionPanel })),
);
export const BusinessReleaseGuardPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessReleaseGuardPanel })),
);
export const BusinessGovernancePanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessGovernancePanel })),
);
export const BusinessOperationLogPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessOperationLogPanel })),
);
export const BusinessRunHistoryPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessRunHistoryPanel })),
);
export const BusinessUsageSummaryPanel = lazy(() =>
  import('./business').then((mod) => ({ default: mod.BusinessUsageSummaryPanel })),
);

export const ApiExposurePanel = lazy(() =>
  import('./apiExposure').then((mod) => ({ default: mod.ApiExposurePanel })),
);

export const VendorModelsPanel = lazy(() =>
  import('./vendorModels').then((mod) => ({ default: mod.VendorModelsPanel })),
);
export const AuthPanel = lazy(() => import('./auth').then((mod) => ({ default: mod.AuthPanel })));
export const BillingPanel = lazy(() => import('./billing').then((mod) => ({ default: mod.BillingPanel })));
export const BindingRoutesPanel = lazy(() =>
  import('./bindings').then((mod) => ({ default: mod.BindingRoutesPanel })),
);
export const DispatchLogsPanel = lazy(() =>
  import('./dispatchLogs').then((mod) => ({ default: mod.DispatchLogsPanel })),
);
export const ExecutorsPanel = lazy(() => import('./executors').then((mod) => ({ default: mod.ExecutorsPanel })));
export const LegacyApiKeysPanel = lazy(() =>
  import('./legacyApiKeys').then((mod) => ({ default: mod.LegacyApiKeysPanel })),
);
export const MonitorPanel = lazy(() => import('./monitor').then((mod) => ({ default: mod.MonitorPanel })));
export const SystemConfigPanel = lazy(() =>
  import('./systemConfig').then((mod) => ({ default: mod.SystemConfigPanel })),
);
export const WorkflowBuilderPanel = lazy(() =>
  import('./workflowBuilder').then((mod) => ({ default: mod.WorkflowBuilderPanel })),
);

export const ComfyuiAgentsPanel = lazy(() =>
  import('./comfyuiAgents').then((mod) => ({ default: mod.ComfyuiAgentsPanel })),
);
export const ComfyuiAlertsPanel = lazy(() =>
  import('./comfyuiAlerts').then((mod) => ({ default: mod.ComfyuiAlertsPanel })),
);
export const ComfyuiAssetsPanel = lazy(() =>
  import('./comfyuiAssets').then((mod) => ({ default: mod.ComfyuiAssetsPanel })),
);
export const ComfyuiDesktopPanel = lazy(() =>
  import('./comfyuiDesktop').then((mod) => ({ default: mod.ComfyuiDesktopPanel })),
);
export const ComfyuiLorasPanel = lazy(() =>
  import('./comfyuiLoras').then((mod) => ({ default: mod.ComfyuiLorasPanel })),
);
export const ComfyuiManifestsPanel = lazy(() =>
  import('./comfyuiManifests').then((mod) => ({ default: mod.ComfyuiManifestsPanel })),
);
export const ComfyuiServersPanel = lazy(() =>
  import('./comfyuiServers').then((mod) => ({ default: mod.ComfyuiServersPanel })),
);
export const ComfyuiTasksPanel = lazy(() =>
  import('./comfyuiTasks').then((mod) => ({ default: mod.ComfyuiTasksPanel })),
);
export const ComfyuiTemplatesPanel = lazy(() =>
  import('./comfyuiTemplates').then((mod) => ({ default: mod.ComfyuiTemplatesPanel })),
);

export const panelFallback = (label: string) => (
  <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600 shadow-sm">
    {label}加载中，请稍候...
  </div>
);
