/**
 * Mock 数据 — 素材、订单、灵感广场等
 * 后续接入真实 API 时替换
 */
import type {
  AssetItem,
  InspirationWork,
  ProductionOrderSnapshot,
  PublishApplicationSnapshot,
} from "../types";

type DemoImageName = "floral-pattern" | "geometric-pattern" | "stripe-pattern";
type ProductDemoName =
  | "product-mug"
  | "product-mug-coral"
  | "product-tumbler-blue"
  | "product-can-cooler"
  | "product-tee"
  | "product-tote"
  | "product-pillow";

const market = (name: string) => `/demo/market/${name}.webp`;
const marketPng = (name: string) => `/demo/market/${name}.png`;
const demoMap: Record<DemoImageName, string> = {
  "floral-pattern": market("pattern-vintage-floral"),
  "geometric-pattern": market("pattern-garden"),
  "stripe-pattern": market("pattern-dark-botanical"),
};
const productDemoMap: Record<ProductDemoName, string> = {
  "product-mug": market("image2-tumbler-product"),
  "product-mug-coral": marketPng("product-mug-coral-navy"),
  "product-tumbler-blue": marketPng("product-tumbler-blue-botanical"),
  "product-can-cooler": marketPng("product-can-cooler-dark-botanical"),
  "product-tee": market("product-tee-botanical"),
  "product-tote": market("product-tote-floral"),
  "product-pillow": market("podi-cup-catalog"),
};

const demo = (name: DemoImageName) => demoMap[name];
const productDemo = (name: ProductDemoName) => productDemoMap[name];

/* ── 素材 ── */

export const initialAssets: AssetItem[] = [
  {
    id: "asset-1",
    type: "pattern",
    title: "复古花卉连续图案",
    url: demo("floral-pattern"),
    thumbnailUrl: demo("floral-pattern"),
    source: "花纹提取结果",
    createdAt: "2026-06-20 10:00",
    selected: false,
    favorite: false,
    visibility: "public",
  },
  {
    id: "asset-2",
    type: "variation",
    title: "蓝绿花园裂变图",
    url: demo("geometric-pattern"),
    thumbnailUrl: demo("geometric-pattern"),
    source: "图案裂变结果",
    createdAt: "2026-06-20 10:05",
    selected: false,
    favorite: false,
    visibility: "private",
  },
  {
    id: "asset-3",
    type: "processed",
    title: "粉橙花束处理图",
    url: market("pattern-bloom"),
    thumbnailUrl: market("pattern-bloom"),
    source: "批量去背景",
    createdAt: "2026-06-19 16:30",
    selected: false,
    favorite: false,
    visibility: "reviewing",
  },
  {
    id: "asset-4",
    type: "pattern",
    title: "深色植物夜花纹",
    url: demo("stripe-pattern"),
    thumbnailUrl: demo("stripe-pattern"),
    source: "上传图片提取",
    createdAt: "2026-06-19 14:20",
    selected: false,
    favorite: true,
    visibility: "private",
  },
  {
    id: "asset-5",
    type: "original",
    title: "上传图 — 复古恐龙图案",
    url: market("pattern-dino"),
    thumbnailUrl: market("pattern-dino"),
    source: "本地上传",
    createdAt: "2026-06-18 09:00",
    selected: false,
    favorite: false,
    visibility: "private",
  },
  {
    id: "asset-6",
    type: "ai_generated",
    title: "AI 生成 — 夜色花卉",
    url: market("pattern-night-flower"),
    thumbnailUrl: market("pattern-night-flower"),
    source: "文字描述生成",
    createdAt: "2026-06-18 11:30",
    selected: false,
    favorite: true,
    visibility: "private",
  },
];

/* ── 灵感广场 ── */

export const inspirationWorks: InspirationWork[] = [
  {
    id: "work-1",
    title: "复古花卉杯身",
    kind: "产品作品",
    image: productDemo("product-mug-coral"),
    author: "designer_liu",
    tags: ["杯子", "花卉", "已生成产品"],
    tries: 128,
    favorites: 342,
    earnings: "抵扣 ¥186.40",
    trend: "本周 38 人试做",
  },
  {
    id: "work-2",
    title: "蓝绿抽象花纹",
    kind: "图片作品",
    image: demo("geometric-pattern"),
    author: "pattern_lab",
    tags: ["花纹", "可裂变", "图片灵感"],
    tries: 67,
    favorites: 204,
    earnings: "抵扣 ¥72.30",
    trend: "适合二次裂变",
  },
  {
    id: "work-3",
    title: "深色植物杯套",
    kind: "产品作品",
    image: productDemo("product-can-cooler"),
    author: "outdoor_studio",
    tags: ["杯套", "礼品", "产品灵感"],
    tries: 92,
    favorites: 188,
    earnings: "抵扣 ¥94.10",
    trend: "节日礼品方向",
  },
  {
    id: "work-4",
    title: "水彩花束透明底",
    kind: "图片作品",
    image: demo("floral-pattern"),
    author: "flower_maker",
    tags: ["透明底", "花卉", "可做产品"],
    tries: 43,
    favorites: 151,
    earnings: "抵扣 ¥38.60",
    trend: "新图上升中",
  },
];

/* ── 订单 ── */

export const baseOrderItems: ProductionOrderSnapshot[] = [
  {
    id: "order-1",
    product: "环绕马克杯",
    asset: "复古花卉图案 01",
    quantity: "1 件试做",
    status: "制作中",
    eta: "预计 5-7 天发出",
    image: productDemo("product-mug-coral"),
    createdAt: "06/18 14:20",
    shippingSummary: "西安市雁塔区测试地址",
    discount: "已用 1 张产品券",
    usedProductCoupon: true,
  },
  {
    id: "order-2",
    product: "基础短袖 T 恤",
    asset: "几何条纹裂变 A",
    quantity: "50 件批量制作",
    status: "待确认",
    eta: "确认后排产",
    image: productDemo("product-tee"),
    createdAt: "06/17 11:08",
    shippingSummary: "待补充收货信息",
    discount: "可用站内抵扣权益",
    usedProductCoupon: false,
  },
];

/* ── 公开申请 ── */

export const initialPublishApplications: PublishApplicationSnapshot[] = [];

/* ── demo 资源路径辅助 ── */

export { demo, productDemo };
