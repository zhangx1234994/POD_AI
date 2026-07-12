/**
 * 杯子品类产品数据 — 来源：杯子品类数据(3).xlsx
 * 供应链字段以 Excel 为准；3D 模型来自 2026-07 蜂鸟模型包，按名称/容量保守匹配。
 */

export interface DesignSurface {
  name: string;
  label: string;
  sizeLabel: string;
  viewId: number | null;
  dpi: number | null;
  width: number | null;
  height: number | null;
}

export interface ProductColor {
  code: string;
  label: string;
  value: string;
  note?: string;
}

export interface ProductSize {
  label: string;
  colorCodes: string[];
  modelFile?: string;
  surfaces: DesignSurface[];
}

export interface ProductCraftOption {
  firstCraft: string;
  firstCraftName: string;
  secondCraft: string;
  secondCraftName: string;
  isDefault?: boolean;
}

export interface CupProduct {
  id: string;
  bodyCode: string;
  name: string;
  category: string;
  tags: string[];
  basePriceCents: number;
  colors: ProductColor[];
  firstCraft: string;
  secondCraft: string;
  craftOptions: ProductCraftOption[];
  sizes: ProductSize[];
  modelFile: string;
  materialSlots: string[];
  status: "ready" | "pending";
}

const colorMeta: Record<string, ProductColor> = {
  "beige1": { code: "beige1", label: "米色 1", value: "#f2eadb", note: "柔和浅底" },
  "beige2": { code: "beige2", label: "米色 2", value: "#eadfca", note: "柔和浅底" },
  "beige3": { code: "beige3", label: "米色 3", value: "#e2d5be", note: "柔和浅底" },
  "black": { code: "black", label: "黑色", value: "#111827", note: "深色杯身" },
  "blue": { code: "blue", label: "蓝色", value: "#2563eb", note: "蓝色杯身" },
  "blue-green": { code: "blue-green", label: "蓝绿", value: "#0891b2", note: "蓝绿杯身" },
  "burgundy": { code: "burgundy", label: "酒红", value: "#7f1d1d", note: "深红杯身" },
  "cameosa": { code: "cameosa", label: "藕粉", value: "#d9aaa3", note: "柔粉杯身" },
  "crimson": { code: "crimson", label: "绯红", value: "#b91c1c", note: "红色杯身" },
  "dark-orange": { code: "dark-orange", label: "深橙", value: "#c2410c", note: "深橙杯身" },
  "fruit-green": { code: "fruit-green", label: "果绿", value: "#8bc34a", note: "亮绿色" },
  "green": { code: "green", label: "绿色", value: "#16a34a", note: "绿色杯身" },
  "greenish-blue": { code: "greenish-blue", label: "蓝绿色", value: "#0f766e", note: "蓝绿杯身" },
  "grey": { code: "grey", label: "灰色", value: "#8b949e", note: "中性灰" },
  "light-blue": { code: "light-blue", label: "浅蓝", value: "#d9e6f3", note: "冷色浅底" },
  "light-green": { code: "light-green", label: "浅绿", value: "#dce8df", note: "清爽浅绿" },
  "light-pink": { code: "light-pink", label: "浅粉", value: "#f8c8d8", note: "浅粉底" },
  "light-purple": { code: "light-purple", label: "浅紫", value: "#e5d8f3", note: "柔和紫底" },
  "light-yellow": { code: "light-yellow", label: "浅黄", value: "#f7e58d", note: "浅暖底" },
  "matte-black": { code: "matte-black", label: "哑光黑", value: "#0b0f19", note: "哑光深色" },
  "navy-blue": { code: "navy-blue", label: "藏蓝", value: "#1e3a8a", note: "深蓝杯身" },
  "nude": { code: "nude", label: "裸色", value: "#d6b19a", note: "低饱和暖底" },
  "olive-green": { code: "olive-green", label: "橄榄绿", value: "#667a39", note: "复古绿" },
  "orange": { code: "orange", label: "橙色", value: "#f97316", note: "高饱和暖色" },
  "orangish": { code: "orangish", label: "橘色", value: "#fb923c", note: "橘色杯身" },
  "peach": { code: "peach", label: "蜜桃", value: "#f6d2c6", note: "暖色礼品" },
  "pink": { code: "pink", label: "粉色", value: "#f4a7b9", note: "礼品粉" },
  "purple": { code: "purple", label: "紫色", value: "#7e22ce", note: "紫色杯身" },
  "red": { code: "red", label: "红色", value: "#dc2626", note: "节日红" },
  "rose-gold": { code: "rose-gold", label: "玫瑰金", value: "#b76e79", note: "金属暖色" },
  "rose-red": { code: "rose-red", label: "玫红", value: "#e11d48", note: "玫红杯身" },
  "sky-blue": { code: "sky-blue", label: "天蓝", value: "#7dd3fc", note: "亮浅蓝" },
  "white": { code: "white", label: "白色", value: "#f8f7f2", note: "常用浅底" },
  "yellow": { code: "yellow", label: "黄色", value: "#facc15", note: "亮黄色" },
};

function productColors(codes: string[]): ProductColor[] {
  const unique = Array.from(new Set(codes.map((code) => code.trim()).filter(Boolean)));
  const colors = unique.map((code) => colorMeta[code] ?? { code, label: code, value: "#f8f7f2", note: "供应链颜色" });
  return colors.length ? colors : [colorMeta.white];
}

const uvPrintCraftTemplateIds = new Set([
  "10167", "10168", "10221", "10223", "10224", "10226", "10228", "10230",
  "10231", "10232", "10233", "10234", "10235", "10236", "10238", "10241",
  "10242", "10343", "10344", "10345", "10347",
]);

const heatTransferCraftTemplateIds = new Set(["10165", "10341", "10342"]);

// 陶瓷马克杯不是当前 AI 创品的在售品类。保留原始供应链行用于
// 历史订单追溯，但绝不把它们组装进面向用户的产品目录。
const discontinuedTemplateIds = new Set(["10341", "10342"]);

function craftOptionsForTemplate(templateId: string): ProductCraftOption[] {
  if (uvPrintCraftTemplateIds.has(templateId)) {
    return [
      { firstCraft: "17", firstCraftName: "360度UV打印", secondCraft: "2", secondCraftName: "光油", isDefault: true },
      { firstCraft: "17", firstCraftName: "360度UV打印", secondCraft: "1", secondCraftName: "哑光" },
    ];
  }
  if (heatTransferCraftTemplateIds.has(templateId)) {
    return [
      { firstCraft: "21", firstCraftName: "热转印", secondCraft: "1", secondCraftName: "热转印", isDefault: true },
    ];
  }
  return [];
}

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

const knownBasePriceCents: Record<string, number> = {
  "10395": 3980,
  "10385": 3280,
  "10376": 4280,
  "10256": 4580,
  "10238": 2280,
  "10236": 2360,
};

function inferBasePriceCents(templateId: string, name: string): number {
  if (knownBasePriceCents[templateId]) return knownBasePriceCents[templateId];
  if (name.includes("太空壶") || name.includes("手提杯") || name.includes("手柄杯")) return 5580;
  if (name.includes("保温") || name.includes("汽车杯") || name.includes("运动水壶")) return 4280;
  if (name.includes("马克杯") || name.includes("咖啡杯")) return 2580;
  if (name.includes("酒杯") || name.includes("啤酒")) return 2280;
  if (name.includes("杯套") || name.includes("配件") || name.includes("手提袋")) return 1980;
  return 2980;
}

const raw: Array<{
  bodyCode: string; templateId: string; name: string; size: string; colorCodes: string[]; surface: string; viewId: number | null; firstCraft: string; secondCraft: string; dpi: number | null; w: number | null; h: number | null; modelFile: string;
}> = [
  { bodyCode: "2730", templateId: "10395", name: "20oz带手柄和吸管不锈钢杯", size: "OneSize", colorCodes: ["black", "white", "beige1", "light-green", "light-blue", "peach", "light-purple"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3378, h: 1949, modelFile: "10395-onesize.glb" },
  { bodyCode: "2642", templateId: "10385", name: "12oz水瓶罐", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 300, w: 2717, h: 1476, modelFile: "10385-onesize.glb" },
  { bodyCode: "1615", templateId: "10376", name: "30oz手提杯", size: "OneSize", colorCodes: ["black", "blue", "cameosa", "crimson", "greenish-blue", "grey", "light-blue", "light-green", "light-purple", "light-yellow", "navy-blue", "olive-green", "orange", "pink", "white", "red", "sky-blue"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3343, h: 2469, modelFile: "10376-onesize.glb" },
  { bodyCode: "1645", templateId: "10374", name: "40oz手柄杯喷塑", size: "OneSize", colorCodes: ["black", "white", "pink", "fruit-green", "light-purple", "navy-blue", "nude"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "2544", templateId: "10256", name: "双饮咖啡杯", size: "OneSize", colorCodes: ["black", "pink", "red", "white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3142, h: 1848, modelFile: "10256-onesize.glb" },
  { bodyCode: "1683", templateId: "10252", name: "17oz子弹杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2486, h: 2486, modelFile: "10252-onesize.glb" },
  { bodyCode: "1660", templateId: "10351", name: "40oz手柄杯", size: "OneSize", colorCodes: ["black", "blue", "burgundy", "cameosa", "yellow", "greenish-blue", "grey", "light-blue", "light-green", "navy-blue", "olive-green", "orangish", "pink", "purple", "red", "sky-blue", "white", "dark-orange"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 300, w: 3715, h: 2811, modelFile: "10351-onesize.glb" },
  { bodyCode: "1663", templateId: "10350", name: "10oz汽车杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2748, h: 1488, modelFile: "10350-onesize.glb" },
  { bodyCode: "1576", templateId: "10249", name: "74oz/2.2L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "yellow", "pink"], surface: "杯身", viewId: 1, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 2462, h: 1600, modelFile: "10249-onesize.glb" },
  { bodyCode: "1576", templateId: "10249", name: "74oz/2.2L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "yellow", "pink"], surface: "底座", viewId: 2, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 800, h: 795, modelFile: "" },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "light-pink", "pink"], surface: "套身+袋", viewId: 1, firstCraft: "包帽厂", secondCraft: "其他", dpi: null, w: null, h: null, modelFile: "10248-onesize.glb" },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "light-pink", "pink"], surface: "袋围", viewId: 2, firstCraft: "包帽厂", secondCraft: "其他", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "light-pink", "pink"], surface: "底", viewId: 3, firstCraft: "包帽厂", secondCraft: "其他", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1608", templateId: "10248", name: "32oz/1L塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "light-pink", "pink"], surface: "手提", viewId: 4, firstCraft: "包帽厂", secondCraft: "其他", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], surface: "杯身", viewId: 1, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 2185, h: 1538, modelFile: "10247-onesize.glb" },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], surface: "底", viewId: 2, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 727, h: 727, modelFile: "" },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], surface: "饰带边条", viewId: 3, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 1777, h: 263, modelFile: "" },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], surface: "口袋", viewId: 4, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 590, h: 1055, modelFile: "" },
  { bodyCode: "1609", templateId: "10247", name: "64oz塑料运动水壶+套", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], surface: "肩带", viewId: 5, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 1160, h: 412, modelFile: "" },
  { bodyCode: "1662", templateId: "10246", name: "25oz热食保温瓶", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3529, h: 1665, modelFile: "10246-onesize.glb" },
  { bodyCode: "1661", templateId: "10245", name: "20oz咖啡保温瓶", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2852, h: 2173, modelFile: "10245-onesize.glb" },
  { bodyCode: "1667", templateId: "10244", name: "16oz二代可乐瓶", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2634, h: 2598, modelFile: "10244-onesize.glb" },
  { bodyCode: "1668", templateId: "10242", name: "29oz保温杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2811, h: 2835, modelFile: "10242-onesize.glb" },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "18OZ", colorCodes: ["black", "beige1", "pink"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2699, h: 2126, modelFile: "10241-18oz.glb" },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "32OZ", colorCodes: ["black", "beige2", "pink"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3331, h: 2422, modelFile: "10241-32oz.glb" },
  { bodyCode: "1692", templateId: "10241", name: "不锈钢太空壶-多容量", size: "40OZ", colorCodes: ["black", "beige3", "pink"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3372, h: 2894, modelFile: "10241-40oz.glb" },
  { bodyCode: "1412", templateId: "10238", name: "17oz吸管杯", size: "OneSize", colorCodes: ["black", "blue"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1416", templateId: "10236", name: "20OZ不锈钢瘦身杯", size: "OneSize", colorCodes: ["white"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2748, h: 2409, modelFile: "10236-onesize.glb" },
  { bodyCode: "1622", templateId: "10235", name: "30oz冰霸杯下不锈钢", size: "OneSize", colorCodes: ["white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3732, h: 2114, modelFile: "10235-onesize.glb" },
  { bodyCode: "1517", templateId: "10234", name: "12oz酒杯", size: "OneSize", colorCodes: ["white"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3285, h: 1205, modelFile: "10234-onesize.glb" },
  { bodyCode: "1561", templateId: "10233", name: "30oz喷塑冰霸杯汽车杯", size: "OneSize", colorCodes: ["pink", "sky-blue"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 886, h: 886, modelFile: "" },
  { bodyCode: "1561", templateId: "10233", name: "30oz喷塑冰霸杯汽车杯", size: "OneSize", colorCodes: ["pink", "sky-blue"], surface: "后面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 886, h: 886, modelFile: "" },
  { bodyCode: "1610", templateId: "10232", name: "40oz活动手柄杯", size: "OneSize", colorCodes: ["black", "pink", "purple", "red", "sky-blue", "white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3715, h: 2587, modelFile: "10232-onesize.glb" },
  { bodyCode: "1613", templateId: "10231", name: "12oz大口杯喷塑", size: "OneSize", colorCodes: ["white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3868, h: 1586, modelFile: "10231-onesize.glb" },
  { bodyCode: "1623", templateId: "10230", name: "30oz冰霸杯上下不锈钢", size: "OneSize", colorCodes: ["white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3732, h: 2043, modelFile: "10230-onesize.glb" },
  { bodyCode: "1625", templateId: "10228", name: "20oz汽车杯-上下不锈钢", size: "OneSize", colorCodes: ["white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3285, h: 1725, modelFile: "10228-onesize.glb" },
  { bodyCode: "1652", templateId: "10226", name: "16oz汽车杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3195, h: 1677, modelFile: "10226-onesize.glb" },
  { bodyCode: "1665", templateId: "10224", name: "20oz美式咖啡杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 1643, h: 945, modelFile: "10224-onesize.glb" },
  { bodyCode: "1664", templateId: "10223", name: "12oz美式咖啡杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3285, h: 1276, modelFile: "10223-onesize.glb" },
  { bodyCode: "1684", templateId: "10221", name: "17oz子弹头不锈钢杯-非全幅", size: "OneSize", colorCodes: ["black", "white", "yellow"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2486, h: 2315, modelFile: "10221-onesize.glb" },
  { bodyCode: "1592", templateId: "10168", name: "12oz啤酒饮料保温杯", size: "OneSize", colorCodes: ["white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2717, h: 1181, modelFile: "10168-onesize.glb" },
  { bodyCode: "1631", templateId: "10167", name: "12oz啤酒保温杯", size: "OneSize", colorCodes: ["black", "blue-green", "greenish-blue", "pink", "purple", "rose-red", "sky-blue", "white"], surface: "front", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 2717, h: 1772, modelFile: "10167-onesize.glb" },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], surface: "杯身", viewId: 1, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 1890, h: 1655, modelFile: "10165-onesize.glb" },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], surface: "肩带", viewId: 2, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 1109, h: 366, modelFile: "" },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], surface: "口袋", viewId: 3, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 627, h: 1185, modelFile: "" },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], surface: "口袋包边", viewId: 4, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 2199, h: 272, modelFile: "" },
  { bodyCode: "1682", templateId: "10165", name: "水瓶手提袋", size: "OneSize", colorCodes: ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], surface: "圆底", viewId: 5, firstCraft: "包帽厂", secondCraft: "其他", dpi: 150, w: 626, h: 623, modelFile: "" },
  { bodyCode: "1408", templateId: "10347", name: "12oz酒杯（非全副）", size: "OneSize", colorCodes: ["green", "black", "white", "pink", "matte-black", "purple"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1408", templateId: "10347", name: "12oz酒杯（非全副）", size: "OneSize", colorCodes: ["green", "black", "white", "pink", "matte-black", "purple"], surface: "后面", viewId: 2, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1621", templateId: "10345", name: "20oz汽车杯-下不锈钢", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3285, h: 1831, modelFile: "10345-onesize.glb" },
  { bodyCode: "1560", templateId: "10344", name: "20oz汽车杯", size: "OneSize", colorCodes: ["white"], surface: "前面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: 150, w: 3283, h: 2008, modelFile: "10344-onesize.glb" },
  { bodyCode: "1552", templateId: "10343", name: "20OZ喷塑汽车杯-上留不锈钢-非全幅", size: "OneSize", colorCodes: ["green", "black", "white", "rose-gold"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "不锈钢杯", dpi: null, w: null, h: null, modelFile: "" },
  { bodyCode: "1302", templateId: "10342", name: "11oz陶瓷马克杯", size: "OneSize", colorCodes: ["white"], surface: "正面", viewId: 1, firstCraft: "杯子厂", secondCraft: "非不锈钢杯", dpi: 150, w: 2835, h: 1122, modelFile: "" },
  { bodyCode: "1302", templateId: "10342", name: "11oz陶瓷马克杯", size: "OneSize", colorCodes: ["white"], surface: "背面", viewId: 2, firstCraft: "杯子厂", secondCraft: "非不锈钢杯", dpi: 150, w: 2835, h: 1122, modelFile: "" },
  { bodyCode: "1400", templateId: "10341", name: "15oz陶瓷马克杯", size: "OneSize", colorCodes: ["white"], surface: "左边", viewId: 1, firstCraft: "杯子厂", secondCraft: "非不锈钢杯", dpi: 150, w: 708, h: 886, modelFile: "" },
  { bodyCode: "1400", templateId: "10341", name: "15oz陶瓷马克杯", size: "OneSize", colorCodes: ["white"], surface: "右边", viewId: 2, firstCraft: "杯子厂", secondCraft: "非不锈钢杯", dpi: 150, w: 708, h: 886, modelFile: "" },
];

function buildProducts(): CupProduct[] {
  const templateMap = new Map<string, CupProduct>();

  for (const row of raw) {
    let product = templateMap.get(row.templateId);
    if (!product) {
      product = {
        id: row.templateId,
        bodyCode: row.bodyCode,
        name: row.name,
        category: "杯子",
        tags: inferTags(row.name),
        basePriceCents: inferBasePriceCents(row.templateId, row.name),
        colors: productColors(row.colorCodes),
        firstCraft: row.firstCraft,
        secondCraft: row.secondCraft,
        craftOptions: craftOptionsForTemplate(row.templateId),
        sizes: [],
        modelFile: row.modelFile,
        materialSlots: [],
        status: "pending",
      };
      templateMap.set(row.templateId, product);
    }

    let sizeEntry = product.sizes.find((size) => size.label === row.size);
    if (!sizeEntry) {
      sizeEntry = { label: row.size, colorCodes: row.colorCodes, modelFile: row.modelFile, surfaces: [] };
      product.sizes.push(sizeEntry);
    }

    const sLabel = surfaceLabel(row.surface);
    const surfaceKey = `${sLabel.name}:${row.viewId ?? ""}:${row.w ?? ""}:${row.h ?? ""}`;
    if (!sizeEntry.surfaces.find((surface) => `${surface.name}:${surface.viewId ?? ""}:${surface.width ?? ""}:${surface.height ?? ""}` === surfaceKey)) {
      sizeEntry.surfaces.push({
        name: sLabel.name,
        label: sLabel.label,
        sizeLabel: row.size,
        viewId: row.viewId,
        dpi: row.dpi,
        width: row.w,
        height: row.h,
      });
    }
    if (!product.modelFile && row.modelFile) product.modelFile = row.modelFile;
  }

  for (const product of templateMap.values()) {
    const allSurfaces = product.sizes.flatMap((size) => size.surfaces);
    product.status = allSurfaces.some((surface) => surface.width !== null && surface.height !== null) ? "ready" : "pending";
    product.materialSlots = Array.from(new Set(allSurfaces.map((surface) => surface.name)));
  }

  return Array.from(templateMap.values()).filter((product) => !discontinuedTemplateIds.has(product.id));
}

export const cupProducts: CupProduct[] = buildProducts();

export const cupTags: string[] = Array.from(
  new Set(cupProducts.flatMap((product) => product.tags))
).sort();

export function filterCupProducts(tag: string | null, search: string | null): CupProduct[] {
  let result = cupProducts;
  if (tag && tag !== "全部") {
    result = result.filter((product) => product.tags.includes(tag));
  }
  if (search?.trim()) {
    const q = search.toLowerCase();
    result = result.filter(
      (product) =>
        product.name.toLowerCase().includes(q) ||
        product.id.includes(q) ||
        product.bodyCode.includes(q) ||
        product.colors.some((color) => color.code.toLowerCase().includes(q) || color.label.includes(q)) ||
        product.tags.some((tagName) => tagName.includes(q))
    );
  }
  return result;
}
