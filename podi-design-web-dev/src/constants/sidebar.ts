// ========== 侧边栏与导航相关常量 ==========
// 此文件包含侧边栏用于展示的菜单项（主菜单配置、AI 工具侧边栏菜单配置），单独拆分便于侧边栏与工具页面解耦。
// 将这些静态配置放到 constants 目录，便于复用、统一维护，并与任务类型对齐。
import {
  Sparkles,
  Copy,
  Flower2,
  Grid3X3,
  Maximize2,
  WandSparkles,
  ImageIcon,
  Calculator,
  Database,
  Video,
  LayoutDashboard,
  Users,
  Settings,
  FlaskConical,
  Upload,
} from 'lucide-react';
import type { SidebarMenuItem } from '@/types/sidebar';

/* 主菜单配置（普通用户） */
export const MAIN_MENU: SidebarMenuItem[] = [
  {
    id: 'dashboard',
    label: '仪表板',
    icon: LayoutDashboard,
    path: '/dashboard',
    description: '查看系统概览与关键指标',
  },
  {
    id: 'personal-center',
    label: '个人中心',
    icon: Users,
    path: '/profile',
    description: '管理个人资料与账户设置',
  },
  {
    id: 'personal-gallery',
    label: '我的图库',
    icon: ImageIcon,
    path: '/personal-gallery',
    description: '管理您上传和生成的所有图片',
  },
];

/* AI 工具侧边栏菜单配置 */
export const AI_ACTIONS: SidebarMenuItem[] = [
  {
    id: 'hires',
    label: '无损放大',
    icon: Sparkles,
    path: '/aitl/hires',
    description: '提升图片分辨率，保持细节清晰',
    color: 'bg-blue-500',
  },
  {
    id: 'fission',
    label: '图片裂变',
    icon: Copy,
    path: '/aitl/fission',
    description: '基于原图生成多个创意变体',
    color: 'bg-blue-500',
  },
  {
    id: 'pattern-extract',
    label: '印花提取',
    icon: Flower2,
    path: '/aitl/pattern-extract',
    description: '从复杂图片中提取可用的印花图案',
    color: 'bg-indigo-500',
  },
  {
    id: 'seamless',
    label: '连续图案',
    icon: Grid3X3,
    path: '/aitl/seamless',
    description: '创建可无缝拼接的图案',
    color: 'bg-emerald-500',
  },
  {
    id: 'extend',
    label: '智能扩图',
    icon: Maximize2,
    path: '/aitl/extend',
    description: '智能扩展图片边缘内容',
    color: 'bg-blue-500',
  },
  {
    id: 'edit',
    label: 'AI图片编辑器',
    icon: WandSparkles,
    path: '/aitl/edit',
    description: '统一解决方案：生成/编辑/融合/风格/擦除',
    color: 'bg-blue-500',
    badge: '超级工具',
  },
  {
    id: 'ability-lab',
    label: '能力实验室',
    icon: FlaskConical,
    path: '/aitl/ability-lab',
    description: '直接调用统一能力接口，快速调试厂商能力',
    color: 'bg-purple-500',
    badge: 'NEW',
  },
];

/* 运营功能菜单配置 */
export const OPERATION_MENU: SidebarMenuItem[] = [
  {
    id: 'calculator',
    label: '毛利计算器',
    icon: Calculator,
    path: '/operation/calculator',
    description: '快速计算产品毛利与定价策略',
  },
  {
    id: 'collect',
    label: '数据采集',
    icon: Database,
    path: '/operation/collect',
    description: '抓取与整理市场及竞品数据',
  },
  {
    id: 'video',
    label: '视频生成',
    icon: Video,
    path: '/operation/video',
    description: 'AI 自动生成营销短视频',
  },
];

/* 管理员菜单配置 */
export const ADMIN_MENU: SidebarMenuItem[] = [
  {
    id: 'gallery',
    label: '图库管理',
    icon: Database,
    path: '/admin/gallery',
    description: '审核与管理全站用户图片资源',
  },
  {
    id: 'users',
    label: '用户管理',
    icon: Users,
    path: '/admin/users',
    description: '查看、编辑与封禁用户账户',
  },
  {
    id: 'settings',
    label: '系统设置',
    icon: Settings,
    path: '/admin/settings',
    description: '配置平台全局参数与权限',
  },
];

/* 演示菜单配置 */
export const DEMO_MENU: SidebarMenuItem[] = [
  {
    id: 'image-source-demo',
    label: '图片来源演示',
    icon: FlaskConical,
    path: '/demo/image-source',
    description: '展示不同图片来源的处理效果对比',
  },
  {
    id: 'enhanced-upload-demo',
    label: '增强上传演示',
    icon: Upload,
    path: '/demo/enhanced-upload',
    description: '演示智能上传与自动优化流程',
  },
];

export default {
  MAIN_MENU,
  AI_ACTIONS,
  OPERATION_MENU,
  ADMIN_MENU,
  DEMO_MENU,
};
