import type { ToolItem } from '../types';
import type { UploadResult } from './media';

export type ShellMode = 'design' | 'shoot' | 'toolbox';

export interface WorkspaceProps {
  tool: ToolItem;
  mode: ShellMode;
}

export interface ResultState {
  status: 'idle' | 'queued' | 'running' | 'success' | 'failed' | 'submitting';
  taskId?: string;
  startedAtMs?: number;
  elapsedSeconds?: number;
  mediaUrl?: string;
  text?: string;
  message?: string;
  error?: string;
}

export interface WorkspaceSeedTask {
  id: string;
  title: string;
  tool: string;
  status: 'idle' | 'queued' | 'running' | 'success' | 'failed';
  createdAt: number;
  updatedAt: number;
  resultUrl?: string;
  error?: string;
  uploads?: UploadResult[];
  formValues?: Record<string, string>;
  result?: ResultState;
}

export interface WorkspaceSeedDraft {
  uploads?: UploadResult[];
  formValues?: Record<string, string>;
  result?: ResultState;
  source?: string;
  templateId?: string;
  templateTitle?: string;
  focusField?: string;
}

export interface WorkspaceLocationState {
  seedAsset?: {
    image: string;
    title: string;
  };
  seedTask?: WorkspaceSeedTask;
  seedDraft?: WorkspaceSeedDraft;
}

export interface WorkspaceDraft {
  formValues: Record<string, string>;
  uploads: UploadResult[];
}

export interface TaskDisplayStatus {
  status: 'idle' | 'queued' | 'running' | 'success' | 'failed';
  taskId?: string;
  startedAtMs?: number;
  elapsedSeconds?: number;
  mediaUrl?: string;
  text?: string;
  message?: string;
  error?: string;
}
