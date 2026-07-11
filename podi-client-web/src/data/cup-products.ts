/**
 * 杯子品类产品数据 — 来源：杯子类-模板设计数据.xlsx
 * 按模板号分组，每个模板包含尺码 → 设计面 → 尺寸/DPI 信息
 */

export interface DesignSurface {
  name: string;        // 英文标识: "front" / "back" / "bottom" 等
  label: string;       // 中文标签: "正面" / "背面" / "杯身" 等
  dpi: number | null;
  width: number | null;  // px
  height: number | null; // px
}

export interface ProductSize {
  label: string;         // "OneSize" / "18OZ" / "32OZ" 等
  surfaces: DesignSurface[];
}

export interface CupProduct {
  id: string;             // 模板号，如 "10395"
  bodyCode: string;       // 主体编码，如 "2730"
  name: string;           // 模板名称
  category: string;       // 一级分类："杯子"
  tags: string[];         // 二级标签
  sizes: ProductSize[];
  modelFile: string;      // 3D 模型文件名（预留）
  materialSlots: string[]; // 材质槽（预留，与设计面对应）
  status: "ready" | "pending"; // 数据是否完整（有完整尺寸=ready）
}

// 表面名称标准化
function surfaceLabel(raw: string): { name: string; label: string } {
  const map: Record<string, { name: string; label: string }> = {
    "front": { name: "front", label: "正面" },
    "正面": { name: "front", label: "正面" },
    "前面": { name: "front", label: "正面" },
    "back": { name: "back", label: "背面" },
    "背面": { name: "back", label: "背面" },
    "后面": { name: "back", label: "背面" },
    "杯身": { name: "body", label: "杯身" },
    "底座": { name: "base", label: "底座" },
    "底": { name: "bottom", label: "底部" },
    "套身+袋": { name: "sleeve_bag", label: "套身+袋" },
    "袋围": { name: "bag_wrap", label: "袋围" },
    "手提": { name: "handle", label: "手提" },
    "肩带": { name: "strap", label: "肩带" },
    "口袋": { name: "pocket", label: "口袋" },
    "口袋包边": { name: "pocket_trim", label: "口袋包边" },
    "圆底": { name: "round_bottom", label: "圆底" },
    "饰带边条": { name: "trim_strip", label: "饰带边条" },
    "左边": { name: "left", label: "左边" },
    "右边": { name: "right", label: "右边" },
  };
  return map[raw] ?? { name: raw, label: raw };
}

// 根据产品名称推断标签
function inferTags(name: string): string[] {
  const tags: string[] = ["杯子"];
  if (name.includes("保温") || name.includes("太空壶")) tags.push("保温杯");
  if (name.includes("马克杯")) tags.push("马克杯");
  if (name.includes("运动水壶") || name.includes("水瓶")) tags.push("运动水壶");
  if (name.includes("汽车杯")) tags.push("汽车杯");
  if (name.includes("酒杯")) tags.push("酒杯");
  if (name.includes("冰霸杯")) tags.push("冰霸杯");
  if (name.includes("咖啡杯") || name.includes("咖啡保温")) tags.push("咖啡杯");
  if (name.includes("手柄杯") || name.includes("吸管杯")) tags.push("手柄杯");
  if (name.includes("子弹杯") || name.includes("子弹头")) tags.push("子弹杯");
  if (name.includes("啤酒")) tags.push("啤酒杯");
  if (name.includes("手提袋") || name.includes("水瓶罐")) tags.push("水壶配件");
  if (name.includes("杯套")) tags.push("杯套");
  if (name.includes("可乐瓶")) tags.push("可乐瓶");
  if (tags.length === 1) tags.push("其他杯型");
  return tags;
}

const raw: Array<{
  bodyCode: string;
  templateId: string;
  name: string;
  size: string;
  surface: string;
  dpi: number | null;
  w: number | null;
  h: number | null;
}> = [
  { bodyCode: "2730", templateId: "10395", name: "20oz带手柄和吸管不锈钢杯", size: "OneSize", surface: "front", dpi: 150, w: 3378, h: 1949 },
  { bodyCode: "2642", templateId: "10385", name: "12oz水瓶罐", size: "OneSize", surface: "正面", dpi: 300, w: 2717, h: 1476 },
  { bodyCode: "1615", templateId: "10376", name: "30oz手提杯", size: "OneSize", surface: "front", dpi: 150, w: 3343, h: 2469 },
  { bodyCode: "1645", templateId: "10374", name: "40oz手柄杯喷塑", size: "OneSize", surface: "正面", dpi: null, w: null, h: null },
  { bodyCode: "2544", templateId: "10256", name: "双饮咖啡杯", size: "OneSize", surface: "正面", dpi: 150, w: 3142, h: 1848 },
  { bodyCode: "1683", templateId: "10252", name: "17oz子弹杯", size: "OneSize", surface: "正面", dpi: 150, w: 2486, h: 2486 },
  { bodyCode: "1660", templateId: "10351", name: "40oz手柄杯", size: "OneSize", surface: "正面", dpi: 300, w: 3715, h: 2811 },
  { bodyCode: "1663", templateId: "10350", name: "10oz汽车杯", size: "OneSize", surface: "正面", dpi: 150, w: 2748, h: 1488 },
  { bodyCode: "1576", templateId: "10249", name: "74oz/2.2L塑料运动水壶+套", size: "OneSize", surface: "杯身", dpi: 150, w: 2462, h: 1600 },
  { bodyCode: "1576", templateId: "10249", name: "74oz/2.2L塑料运动水壶+套", size: "OneSize", surface: "底座", dpi: 150, w: 800, h: 795 },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", surface: "套身+袋", dpi: null, w: null, h: null },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", surface: "袋围", dpi: null, w: null, h: null },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", surface: "底", dpi: null, w: null, h: null },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", surface: "手提", dpi: null, w: null, h: null },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", surface: "杯身", dpi: null, w: null, h: null },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", surface: "底", dpi: null, w: null, h: null },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", surface: "饰带边条", dpi: null, w: null, h: null },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", surface: "口袋", dpi: null, w: null, h: null },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", surface: "肩带", dpi: null, w: null, h: null },
  { bodyCode: "1662", templateId: "10246", name: "25oz热食保温瓶", size: "OneSize", surface: "正面", dpi: 150, w: 3529, h: 1665 },
  { bodyCode: "1661", templateId: "10245", name: "20oz咖啡保温瓶", size: "OneSize", surface: "正面", dpi: 150, w: 2852, h: 2173 },
  { bodyCode: "1667", templateId: "10244", name: "16oz二代可乐瓶", size: "OneSize", surface: "正面", dpi: 150, w: 2634, h: 2598 },
  { bodyCode: "1668", templateId: "10242", name: "29oz保温杯", size: "OneSize", surface: "正面", dpi: 150, w: 2811, h: 2835 },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "18OZ", surface: "正面", dpi: 150, w: 2699, h: 2126 },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "32OZ", surface: "正面", dpi: 150, w: 3331, h: 2422 },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "40OZ", surface: "正面", dpi: 150, w: 3372, h: 2894 },
  { bodyCode: "1412", templateId: "10238", name: "17oz吸管杯", size: "OneSize", surface: "前面", dpi: null, w: null, h: null },
  { bodyCode: "1416", templateId: "10236", name: "20OZ不锈钢瘦身杯", size: "OneSize", surface: "前面", dpi: 150, w: 2748, h: 2409 },
  { bodyCode: "1622", templateId: "10235", name: "30oz冰霸杯下不锈钢", size: "OneSize", surface: "front", dpi: 150, w: 3732, h: 2114 },
  { bodyCode: "1517", templateId: "10234", name: "12oz酒杯", size: "OneSize", surface: "前面", dpi: 150, w: 3285, h: 1205 },
  { bodyCode: "1561", templateId: "10233", name: "30oz喷塑冰霸杯汽车杯", size: "OneSize", surface: "前面", dpi: 150, w: 886, h: 886 },
  { bodyCode: "1561", templateId: "10233", name: "30oz喷塑冰霸杯汽车杯", size: "OneSize", surface: "后面", dpi: 150, w: 886, h: 886 },
  { bodyCode: "1610", templateId: "10232", name: "40oz活动手柄杯", size: "OneSize", surface: "front", dpi: 150, w: 3715, h: 2587 },
  { bodyCode: "1613", templateId: "10231", name: "12oz大口杯喷塑", size: "OneSize", surface: "front", dpi: 150, w: 3868, h: 1586 },
  { bodyCode: "1623", templateId: "10230", name: "30oz冰霸杯上下不锈钢", size: "OneSize", surface: "front", dpi: 150, w: 3732, h: 2043 },
  { bodyCode: "1625", templateId: "10228", name: "20oz汽车杯-上下不锈钢", size: "OneSize", surface: "front", dpi: 150, w: 3285, h: 1725 },
  { bodyCode: "1652", templateId: "10226", name: "16oz汽车杯", size: "OneSize", surface: "正面", dpi: 150, w: 3195, h: 1677 },
  { bodyCode: "1665", templateId: "10224", name: "20oz美式咖啡杯", size: "OneSize", surface: "正面", dpi: 150, w: 1643, h: 945 },
  { bodyCode: "1664", templateId: "10223", name: "12oz美式咖啡杯", size: "OneSize", surface: "正面", dpi: 150, w: 3285, h: 1276 },
  { bodyCode: "1684", templateId: "10221", name: "17oz子弹头不锈钢杯-非全幅", size: "OneSize", surface: "正面", dpi: 150, w: 2486, h: 2315 },
  { bodyCode: "1592", templateId: "10168", name: "12oz啤酒饮料保温杯", size: "OneSize", surface: "front", dpi: 150, w: 1468, h: 620 },
  { bodyCode: "1631", templateId: "10167", name: "12oz啤酒保温杯", size: "OneSize", surface: "front", dpi: 150, w: 2717, h: 1772 },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", surface: "杯身", dpi: 150, w: 1890, h: 1655 },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", surface: "肩带", dpi: 150, w: 1109, h: 366 },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", surface: "口袋", dpi: 150, w: 627, h: 1185 },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", surface: "口袋包边", dpi: 150, w: 2199, h: 272 },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", surface: "圆底", dpi: 150, w: 626, h: 623 },
  { bodyCode: "1408", templateId: "10347", name: "12oz酒杯（非全幅）", size: "OneSize", surface: "前面", dpi: null, w: null, h: null },
  { bodyCode: "1408", templateId: "10347", name: "12oz酒杯（非全幅）", size: "OneSize", surface: "后面", dpi: null, w: null, h: null },
  { bodyCode: "1309", templateId: "10346", name: "啤酒杯套（2件卖）", size: "12oz", surface: "正面", dpi: 150, w: 709, h: 1612 },
  { bodyCode: "1309", templateId: "10346", name: "啤酒杯套（2件卖）", size: "16oz", surface: "正面", dpi: 150, w: 591, h: 2008 },
  { bodyCode: "1621", templateId: "10345", name: "20oz汽车杯-下不锈钢", size: "OneSize", surface: "正面", dpi: 150, w: 3285, h: 1831 },
  { bodyCode: "1560", templateId: "10344", name: "20oz汽车杯", size: "OneSize", surface: "前面", dpi: 150, w: 3283, h: 2008 },
  { bodyCode: "1552", templateId: "10343", name: "20OZ喷塑汽车杯-上留不锈钢-非全幅", size: "OneSize", surface: "正面", dpi: null, w: null, h: null },
  { bodyCode: "1302", templateId: "10342", name: "11oz陶瓷马克杯", size: "OneSize", surface: "正面", dpi: 150, w: 2835, h: 1122 },
  { bodyCode: "1302", templateId: "10342", name: "11oz陶瓷马克杯", size: "OneSize", surface: "背面", dpi: 150, w: 2835, h: 1122 },
  { bodyCode: "1400", templateId: "10341", name: "15oz陶瓷马克杯", size: "OneSize", surface: "左边", dpi: null, w: null, h: null },
  { bodyCode: "1400", templateId: "10341", name: "15oz陶瓷马克杯", size: "OneSize", surface: "右边", dpi: null, w: null, h: null },
];

// 将原始数据分组为 CupProduct[]
function buildProducts(): CupProduct[] {
  const templateMap = new Map<string, CupProduct>();

  for (const row of raw) {
    let product = templateMap.get(row.templateId);
    if (!product) {
      const s = surfaceLabel(row.surface);
      product = {
        id: row.templateId,
        bodyCode: row.bodyCode,
        name: row.name,
        category: "杯子",
        tags: inferTags(row.name),
        sizes: [],
        modelFile: `${row.bodyCode}.glb`,
        materialSlots: [],
        status: "pending",
      };
      templateMap.set(row.templateId, product);
    }

    // 查找或创建尺码
    let sizeEntry = product.sizes.find((s) => s.label === row.size);
    if (!sizeEntry) {
      sizeEntry = { label: row.size, surfaces: [] };
      product.sizes.push(sizeEntry);
    }

    // 添加设计面（避免重复）
    const sLabel = surfaceLabel(row.surface);
    if (!sizeEntry.surfaces.find((s) => s.name === sLabel.name)) {
      sizeEntry.surfaces.push({
        name: sLabel.name,
        label: sLabel.label,
        dpi: row.dpi,
        width: row.w,
        height: row.h,
      });
    }
  }

  // 计算 status 和 materialSlots
  for (const product of templateMap.values()) {
    const allSurfaces = product.sizes.flatMap((s) => s.surfaces);
    const hasDimensions = allSurfaces.some((s) => s.width !== null && s.height !== null);
    product.status = hasDimensions ? "ready" : "pending";
    product.materialSlots = allSurfaces.map((s) => s.name);
  }

  return Array.from(templateMap.values());
}

export const cupProducts: CupProduct[] = buildProducts();

// 按标签获取所有可用标签
export const cupTags: string[] = Array.from(
  new Set(cupProducts.flatMap((p) => p.tags))
).sort();

// 按分类和标签筛选
export function filterCupProducts(
  tag: string | null,
  search: string | null
): CupProduct[] {
  let result = cupProducts;
  if (tag && tag !== "全部") {
    result = result.filter((p) => p.tags.includes(tag));
  }
  if (search?.trim()) {
    const q = search.toLowerCase();
    result = result.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.id.includes(q) ||
        p.tags.some((t) => t.includes(q))
    );
  }
  return result;
}
