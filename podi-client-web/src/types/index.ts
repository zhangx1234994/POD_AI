export type NavItem = {
  key: string;
  label: string;
  path: string;
  badge?: string;
};

export type ShortcutItem = {
  key: string;
  title: string;
  subtitle: string;
  path: string;
  accent: string;
};

export type TaskItem = {
  id: string;
  title: string;
  status: 'idle' | 'queued' | 'running' | 'success' | 'failed';
  time: string;
  summary: string;
  image: string;
  resultUrl?: string;
};

export type AssetItem = {
  id: string;
  title: string;
  source: string;
  createdAt: string;
  image: string;
  type: 'image' | 'video';
  tags: string[];
  origin?: 'upload' | 'result';
  pathHint?: string;
  abilityKey?: string;
};

export type ToolItem = {
  key: string;
  title: string;
  subtitle: string;
  description: string;
  path: string;
  accent: string;
  group?: string;
};

export type WalletPack = {
  id: string;
  title: string;
  points: number;
  price: string;
  notes: string;
  featured?: boolean;
};

export type StudioAgent = {
  id: string;
  title: string;
  subtitle: string;
  accent: string;
  path?: string;
  image?: string;
};

export type WhiteboardProject = {
  id: string;
  title: string;
  summary: string;
  tag: string;
  image?: string;
};

export type RoleCase = {
  id: string;
  role: string;
  name: string;
  headline: string;
  uplift: string;
  savings: string;
  accent: string;
  image: string;
};

export type SupportLink = {
  id: string;
  title: string;
  subtitle: string;
  path: string;
  image: string;
};

export type BrandFooterLink = {
  id: string;
  label: string;
  value: string;
  path: string;
};

export type SocialLink = {
  id: string;
  label: string;
  path: string;
};

export type ShowcaseCard = {
  id: string;
  title: string;
  subtitle: string;
  image: string;
  path: string;
};
