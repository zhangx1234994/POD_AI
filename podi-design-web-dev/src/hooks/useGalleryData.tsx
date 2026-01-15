import http from '@/utils/http';
import { mapToGalleryImage } from '@/utils/galleryUtils';

export interface FetchGalleryResult {
  images: any[];
  total: number | null;
  counts?: any;
}

export async function fetchGalleryImages(endpoint: string, query: string): Promise<FetchGalleryResult> {
  const resp = await http.get(`${endpoint}?${query}`);
  const payload: any = resp.data || {};
  const items = Array.isArray(payload) ? payload : payload.items || [];
  const totalCount = payload.total ?? items.length;
  const images = (await Promise.all(items.map(mapToGalleryImage))).filter(Boolean) as any[];
  return { images, total: typeof totalCount === 'number' ? totalCount : Number(totalCount) || 0, counts: payload.counts || {} };
}

export default fetchGalleryImages;
