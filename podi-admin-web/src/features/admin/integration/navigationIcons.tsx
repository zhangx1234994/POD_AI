import type { ReactNode } from 'react';
import {
  ApiIcon,
  AppIcon,
  ChartBarIcon,
  DashboardIcon,
  FolderOpenIcon,
  SettingIcon,
  TaskIcon,
  ViewListIcon,
} from 'tdesign-icons-react';
import type { IntegrationNavId } from './navigation';

export const integrationNavIconMap: Record<IntegrationNavId, ReactNode> = {
  overview: <DashboardIcon size="18px" />,
  business: <AppIcon size="18px" />,
  auth: <SettingIcon size="18px" />,
  'vendor-models': <ApiIcon size="18px" />,
  abilities: <AppIcon size="18px" />,
  'ability-evals': <ChartBarIcon size="18px" />,
  executors: <ViewListIcon size="18px" />,
  'ability-logs': <TaskIcon size="18px" />,
  billing: <ChartBarIcon size="18px" />,
  'comfyui-management': <FolderOpenIcon size="18px" />,
  'workflow-builder': <TaskIcon size="18px" />,
  bindings: <ViewListIcon size="18px" />,
  apikeys: <ApiIcon size="18px" />,
  monitor: <ChartBarIcon size="18px" />,
  system: <SettingIcon size="18px" />,
  logs: <TaskIcon size="18px" />,
};
