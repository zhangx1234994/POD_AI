/**
 * 供应链生产面与 GLB 材质槽的显式映射。
 *
 * 供应链的“杯身 / 底部 / 口袋”等面不能再被当作一个 front 贴图处理。
 * 这里只描述模型槽位，图片像素尺寸仍以 cup-products.ts 的供应链数据为准。
 */
export const modelMaterialBindings: Record<string, Record<string, readonly string[]>> = {
  "10165-onesize.glb": {
    body: ["front"],
    strap: ["shoulderstrap"],
    pocket: ["pocket"],
    pocket_trim: ["pocket_edge"],
    round_bottom: ["buttom"],
  },
  "10247-onesize.glb": {
    body: ["front"],
    bottom: ["buttom"],
    trim_strip: ["pocket_edge"],
    pocket: ["pocket"],
    strap: ["shoulder_strap"],
  },
  "10249-onesize.glb": {
    body: ["front"],
    base: ["buttom"],
  },
};

function normalizeSlotName(value: string) {
  return value.trim().toLowerCase().replace(/[\s_-]+/g, "");
}

export function hasExplicitMaterialBindings(modelFile: string | null | undefined) {
  return Boolean(modelFile && modelMaterialBindings[modelFile]);
}

export function materialSlotsForSurface(modelFile: string | null | undefined, surfaceName: string) {
  if (!modelFile) return [];
  return modelMaterialBindings[modelFile]?.[surfaceName] ?? [];
}

export function doesMaterialMatchSurface(
  modelFile: string | null | undefined,
  materialName: string,
  meshName: string,
  surfaceName: string
) {
  const slots = materialSlotsForSurface(modelFile, surfaceName);
  if (!slots.length) return false;
  const materialKey = normalizeSlotName(`${materialName} ${meshName}`);
  return slots.some((slot) => materialKey.includes(normalizeSlotName(slot)));
}
