import type { UploadResult } from '../types/media';

const DRAFT_PREFIX = 'podi-client-draft:';

export type WorkspaceDraft = {
  formValues: Record<string, string>;
  uploads: UploadResult[];
};

export function readWorkspaceDraft(path: string): WorkspaceDraft | null {
  try {
    const raw = sessionStorage.getItem(`${DRAFT_PREFIX}${path}`);
    if (!raw) return null;
    return JSON.parse(raw) as WorkspaceDraft;
  } catch {
    return null;
  }
}

export function writeWorkspaceDraft(path: string, draft: WorkspaceDraft) {
  sessionStorage.setItem(`${DRAFT_PREFIX}${path}`, JSON.stringify(draft));
}

