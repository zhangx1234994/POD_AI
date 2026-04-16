import { trackClientEvent } from './clientAnalytics';

export type ClientAssetRecord = {
  id: string;
  title: string;
  source: string;
  createdAt: string;
  image: string;
  type: 'image' | 'video';
  tags: string[];
  origin: 'upload' | 'result';
  pathHint?: string;
  taskId?: string;
  abilityKey?: string;
  provider?: string;
};

const STORAGE_KEY = 'podi-client-asset-library';
const EVENT_NAME = 'podi-client-assets-updated';

function readStore(): ClientAssetRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ClientAssetRecord[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStore(items: ClientAssetRecord[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 100)));
  window.dispatchEvent(new CustomEvent(EVENT_NAME));
}

export function listClientAssets(): ClientAssetRecord[] {
  return readStore();
}

export function saveClientAsset(asset: ClientAssetRecord) {
  const current = readStore();
  const deduped = current.filter((item) => item.id !== asset.id && !(asset.taskId && item.taskId === asset.taskId && item.image === asset.image));
  writeStore([asset, ...deduped]);
  trackClientEvent('client_asset_saved', {
    id: asset.id,
    title: asset.title,
    origin: asset.origin,
    type: asset.type,
    pathHint: asset.pathHint || null,
    taskId: asset.taskId || null,
    abilityKey: asset.abilityKey || null,
    provider: asset.provider || null,
  });
}

export function subscribeClientAssets(listener: () => void) {
  window.addEventListener(EVENT_NAME, listener);
  return () => window.removeEventListener(EVENT_NAME, listener);
}

export function removeClientAsset(assetId: string) {
  const current = readStore();
  writeStore(current.filter((item) => item.id !== assetId));
}
