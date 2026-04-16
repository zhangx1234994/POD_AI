export type ClientVisualAsset = {
  id: string;
  title: string;
  url: string;
  purpose: string;
  help: string;
  sourceLabel: string;
  sourceType: 'editorial-placeholder';
  controlledBy: string;
  controlPoint: string;
};

const editorialVisual = (seed: string, width = 1200) =>
  `https://images.unsplash.com/${seed}?auto=format&fit=crop&w=${width}&q=80`;

const buildAsset = (
  id: string,
  seed: string,
  title: string,
  purpose: string,
  help: string,
  width = 1200,
): ClientVisualAsset => ({
  id,
  title,
  url: editorialVisual(seed, width),
  purpose,
  help,
  sourceLabel: 'Unsplash editorial placeholder',
  sourceType: 'editorial-placeholder',
  controlledBy: '客户端产品前台',
  controlPoint: 'src/config/clientVisuals.ts',
});

export const buildEditorialVisual = editorialVisual;

export const clientVisualPolicy = {
  principle: '视觉在客户端里不是装饰，而是承担解释业务阶段、强化场景代入和降低理解成本的内容资产。',
  currentMode:
    'Phase 1 先统一使用可替换的 editorial placeholder，所有入口页、案例位、钱包位、登录位都从单一 registry 输出，避免页面各自 hardcode。',
  nextMode: '后续接入品牌自有案例图或运营素材库时，只替换 registry，不再散改页面组件。',
};

export const clientVisualRegistry = {
  homeHero: buildAsset(
    'home-hero',
    'photo-1515886657613-9f3515b0c78f',
    '首页主视觉',
    '承接首页对服装设计场景的第一印象，先让用户感知这不是通用 AI 工具。',
    '帮助用户在进入工作台前形成行业感和产品气质预期。',
    1400,
  ),
  landingDesign: buildAsset(
    'landing-design',
    'photo-1515886657613-9f3515b0c78f',
    '设计场景案例图',
    '解释设计方向生成与成衣感表达。',
    '帮助设计师理解平台解决的是方向收敛，而不是单次出图。',
  ),
  landingCommerce: buildAsset(
    'landing-commerce',
    'photo-1483985988355-763728e1935b',
    '商拍场景案例图',
    '解释营销套图、商拍和电商物料裂变。',
    '帮助运营理解首个结果可以继续走向下一步营销素材。',
  ),
  landingAssets: buildAsset(
    'landing-assets',
    'photo-1521572163474-6864f9cf17ab',
    '资产沉淀场景图',
    '解释结果为什么必须进入资产层。',
    '帮助用户理解平台强调复用与留存，不鼓励一次性下载后散失。',
  ),
  studioAgentFashion: buildAsset(
    'studio-agent-fashion',
    'photo-1515886657613-9f3515b0c78f',
    '工作室时尚设计智能体',
    '作为工作室默认主打智能体卡片的视觉承接。',
    '帮助用户在进入工作室时先理解设计方向入口。',
  ),
  studioBoardDesign: buildAsset(
    'studio-board-design',
    'photo-1521572267360-ee0c2909d518',
    '工作室研发设计白板',
    '承接图案提取、连续纹理和放大收口的设计白板场景。',
    '帮助用户理解白板不是装饰，而是可回来的项目面板。',
  ),
  studioBoardCommerce: buildAsset(
    'studio-board-commerce',
    'photo-1483985988355-763728e1935b',
    '工作室商拍白板',
    '承接主图、套图和视频持续扩展的商拍白板场景。',
    '帮助用户理解工作室首页承接的是连续营销生产。',
  ),
  studioBoardCreate: buildAsset(
    'studio-board-create',
    'photo-1515886657613-9f3515b0c78f',
    '工作室新建白板',
    '作为新建设计项目入口的默认视觉占位。',
    '帮助用户理解新白板入口对应新的创作起点。',
  ),
  loginHero: buildAsset(
    'login-hero',
    'photo-1521572267360-ee0c2909d518',
    '登录页主视觉',
    '说明登录并不是形式动作，而是切换到真实任务、真实钱包、真实资产数据的边界。',
    '帮助用户理解登录后看到的是业务现实，而不是演示层。',
    1200,
  ),
  walletHero: buildAsset(
    'wallet-hero',
    'photo-1521572267360-ee0c2909d518',
    '钱包页主视觉',
    '说明余额、充值与回流路径本身就是生产前台的一部分。',
    '帮助用户理解充值不是离开工作，而是为了继续完成工作。',
    1400,
  ),
  walletBalance: buildAsset(
    'wallet-balance',
    'photo-1521572267360-ee0c2909d518',
    '余额提醒图',
    '强调提交前先看余额和预计消耗。',
    '帮助用户减少因余额不足带来的中断感。',
  ),
  walletReturn: buildAsset(
    'wallet-return',
    'photo-1503342217505-b0a15ec3261c',
    '充值回流图',
    '强调下单后要返回原页面继续提交。',
    '帮助用户理解钱包页不是终点，而是回流跳板。',
  ),
  walletLedger: buildAsset(
    'wallet-ledger',
    'photo-1496747611176-843222e1e57c',
    '账单理解图',
    '强调积分账单要解释得清楚。',
    '帮助非技术用户看懂点数消耗、返还和充值关系。',
  ),
  walletPackStarter: buildAsset(
    'wallet-pack-starter',
    'photo-1529139574466-a303027c1d8b',
    '入门包图',
    '配合轻量套餐展示，服务首次付费判断。',
    '帮助用户建立低门槛购买理解。',
  ),
  walletPackGrowth: buildAsset(
    'wallet-pack-growth',
    'photo-1496747611176-843222e1e57c',
    '高频包图',
    '配合主推荐套餐展示，服务设计与运营日常使用。',
    '帮助高频用户快速判断最适合自己的购买档位。',
  ),
  walletPackScale: buildAsset(
    'wallet-pack-scale',
    'photo-1521572163474-6864f9cf17ab',
    '商拍包图',
    '配合重度消耗场景展示，服务批量营销素材生产。',
    '帮助团队用户理解扩容成本与能力边界。',
  ),
  workspacePreviewDesign: buildAsset(
    'workspace-preview-design',
    'photo-1558618666-fcd25c85cd64',
    '工作区预览设计示例',
    '作为空结果状态下的设计类示例图占位。',
    '帮助用户理解当前工作区最终会产出什么类型的结果。',
    400,
  ),
  workspacePreviewCommerce: buildAsset(
    'workspace-preview-commerce',
    'photo-1441986300917-64674bd600d8',
    '工作区预览商拍示例',
    '作为空结果状态下的商拍类示例图占位。',
    '帮助用户理解当前工作区支持的结果表达方式。',
    400,
  ),
} as const;
