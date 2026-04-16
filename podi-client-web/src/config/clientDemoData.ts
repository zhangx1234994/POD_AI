import type { AssetItem, TaskItem, WalletPack, WhiteboardProject } from '../types';
import { buildEditorialVisual } from './clientVisuals';

const img = (seed: string) => buildEditorialVisual(seed, 900);

export const demoRecentTasks: TaskItem[] = [
  { id: 'T-3012', title: '图案提取 · 春夏印花', status: 'success', time: '2 分钟前', summary: '1800x1800 设计稿已生成并入库', image: img('photo-1521572267360-ee0c2909d518') },
  { id: 'T-3011', title: '四方连续 · 花卉底纹', status: 'running', time: '6 分钟前', summary: '正在做连续化与边缘校验', image: img('photo-1512436991641-6745cdb1723f') },
  { id: 'T-3010', title: 'AI扩图 · 电商主图', status: 'queued', time: '11 分钟前', summary: '前方任务较多，系统正在排队', image: img('photo-1503342217505-b0a15ec3261c') },
  { id: 'T-3008', title: '图生视频 · 服装走秀', status: 'failed', time: '28 分钟前', summary: '本次生成失败，可保持参数重新发起', image: img('photo-1483985988355-763728e1935b') },
];

export const demoRecentAssets: AssetItem[] = [
  { id: 'A-101', title: '春夏花卉提取稿', source: '图案提取', createdAt: '今天 10:22', image: img('photo-1496747611176-843222e1e57c'), type: 'image', tags: ['印花', '已收藏'] },
  { id: 'A-102', title: '格纹连续纹理', source: '四方连续', createdAt: '今天 09:48', image: img('photo-1529139574466-a303027c1d8b'), type: 'image', tags: ['连续纹理'] },
  { id: 'A-103', title: '商拍细节视频', source: '图生视频', createdAt: '昨天 18:30', image: img('photo-1524504388940-b1c1722653e1'), type: 'video', tags: ['视频', '电商'] },
  { id: 'A-104', title: '主图扩边版本', source: 'AI扩图', createdAt: '昨天 15:10', image: img('photo-1521572163474-6864f9cf17ab'), type: 'image', tags: ['主图', '扩图'] },
];

export const demoWalletPacks: WalletPack[] = [
  { id: 'pack-s', title: '入门包', points: 500, price: '49', notes: '适合体验常用图像能力' },
  { id: 'pack-m', title: '高频包', points: 1500, price: '129', notes: '适合设计团队日常出图', featured: true },
  { id: 'pack-l', title: '商拍包', points: 4000, price: '299', notes: '适合营销图、视频与批量任务' },
];

export const demoWalletLedger = [
  { id: 'L-01', type: '消费', title: '图案提取 · 春夏印花', points: -18, time: '今天 10:22' },
  { id: 'L-02', type: '充值', title: '高频包到账', points: 1500, time: '今天 09:12' },
  { id: 'L-03', type: '消费', title: 'AI扩图 · 电商主图', points: -12, time: '昨天 16:48' },
  { id: 'L-04', type: '释放', title: '失败任务返还', points: 8, time: '昨天 15:02' },
];

export const demoWhiteboardProjects: WhiteboardProject[] = [
  {
    id: 'board-01',
    title: '春夏印花方向白板',
    summary: '从参考图、提取稿到四方连续的完整链路都能继续编辑。',
    tag: '研发设计',
    image: img('photo-1521572267360-ee0c2909d518'),
  },
  {
    id: 'board-02',
    title: '电商主图裂变板',
    summary: '围绕一张主图同时推进扩图、精修、视频和套图输出。',
    tag: '视觉商拍',
    image: img('photo-1483985988355-763728e1935b'),
  },
];
