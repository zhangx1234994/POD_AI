import type { LucideIcon } from 'lucide-react';

/**
 * 侧边栏功能菜单项的配置接口
 */
export interface SidebarMenuItem {
  id: string;
  label: string;
  icon: LucideIcon | any;
  path: string;
  description?: string;
  color?: string;
  badge?: string;
  disabled?: boolean;
  isNew?: boolean;
}
