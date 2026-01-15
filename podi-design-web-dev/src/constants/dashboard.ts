import { Image, Sparkles, Palette, Layers } from 'lucide-react';

export const QUICK_ACTIONS = [
  {
    title: 'AI生成',
    description: '使用AI智能生成设计',
    icon: Sparkles,
    color: 'bg-gradient-to-r from-purple-500 to-pink-500',
    action: 'ai-generate',
  },
  {
    title: '图片处理',
    description: '编辑和优化图片',
    icon: Image,
    color: 'bg-gradient-to-r from-blue-500 to-cyan-500',
    action: 'image-process',
  },
  {
    title: '图案设计',
    description: '创建专业图案',
    icon: Palette,
    color: 'bg-gradient-to-r from-green-500 to-teal-500',
    action: 'pattern-design',
  },
  {
    title: '批量操作',
    description: '批量处理任务',
    icon: Layers,
    color: 'bg-gradient-to-r from-orange-500 to-red-500',
    action: 'batch-process',
  },
];

export default {
    QUICK_ACTIONS,
};
