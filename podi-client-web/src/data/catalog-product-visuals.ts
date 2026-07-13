import { cupProducts } from "./cup-products";
import { isCatalogRenderApproved } from "./catalog-render-readiness";
import type { CupProduct, DesignSurface, ProductSize } from "./cup-products";

export type ApprovedCatalogItem = {
  product: CupProduct;
  size: ProductSize;
  surface: DesignSurface;
  modelFile: string;
  renderUrl: string;
};

export function firstReadySurface(size: ProductSize) {
  return size.surfaces.find((surface) => surface.width && surface.height) ?? null;
}

export function catalogModelFile(product: CupProduct, size: ProductSize) {
  return size.modelFile || product.modelFile || null;
}

export function catalogRenderUrl(product: CupProduct, size: ProductSize) {
  const modelFile = catalogModelFile(product, size);
  if (!modelFile || !isCatalogRenderApproved(modelFile)) return null;
  return `/models/catalog-renders/${modelFile.replace(/\.glb$/i, ".png")}`;
}

export function approvedCatalogItem(product: CupProduct, size: ProductSize): ApprovedCatalogItem | null {
  const surface = firstReadySurface(size);
  const modelFile = catalogModelFile(product, size);
  const renderUrl = catalogRenderUrl(product, size);
  if (!surface || !modelFile || !renderUrl) return null;
  return { product, size, surface, modelFile, renderUrl };
}

export function listApprovedCatalogItems(products: CupProduct[] = cupProducts) {
  return products.flatMap((product) =>
    product.sizes.flatMap((size) => {
      const item = approvedCatalogItem(product, size);
      return item ? [item] : [];
    })
  );
}

export function resolveApprovedCatalogItem(templateId: string, sizeLabel: string) {
  const product = cupProducts.find((candidate) => candidate.id === templateId);
  const size = product?.sizes.find((candidate) => candidate.label === sizeLabel);
  return product && size ? approvedCatalogItem(product, size) : null;
}
