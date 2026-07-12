/**
 * 商品目录渲染门禁。
 *
 * 目录主图必须是「对应 GLB + 对应设计面 + 已人工复核的贴图结果」。
 * 没有通过这道门禁的模型不能只因为文件存在就出现在可下单目录里。
 */
export type CatalogRenderReadiness = {
  status: "approved" | "blocked" | "pending";
  note: string;
};

export const catalogRenderReadiness: Record<string, CatalogRenderReadiness> = {
  "10165-onesize.glb": {
    status: "blocked",
    note: "手提袋含袋身、口袋、肩带等多个设计面，当前只校准了 front，不能用单张主图代表可生产效果。",
  },
  "10167-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10168-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10221-onesize.glb": {
    status: "blocked",
    note: "非全幅子弹头杯的透明 front 材质在目录静态图中没有正确承接贴图，需要单独修正渲染规则。",
  },
  "10223-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10224-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10226-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10228-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10230-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10231-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10232-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10234-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10235-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10236-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10241-18oz.glb": { status: "approved", note: "18oz 规格静态校样已复核。" },
  "10241-32oz.glb": { status: "approved", note: "32oz 规格静态校样已复核。" },
  "10241-40oz.glb": { status: "approved", note: "40oz 规格静态校样已复核。" },
  "10242-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10244-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10245-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10246-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10247-onesize.glb": {
    status: "approved",
    note: "杯身、底、边条、口袋和肩带已按独立材质槽与 UV 校准生成校样。",
  },
  "10248-onesize.glb": {
    status: "pending",
    note: "供应链尚未提供可生产的设计面尺寸，不能上架。",
  },
  "10249-onesize.glb": {
    status: "approved",
    note: "杯身与底座已按独立材质槽与 UV 校准生成校样。",
  },
  "10252-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10256-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10344-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10345-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10350-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10351-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10376-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10385-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
  "10395-onesize.glb": { status: "approved", note: "单主设计面静态校样已复核。" },
};

export function isCatalogRenderApproved(modelFile: string | null | undefined) {
  return Boolean(modelFile && catalogRenderReadiness[modelFile]?.status === "approved");
}
