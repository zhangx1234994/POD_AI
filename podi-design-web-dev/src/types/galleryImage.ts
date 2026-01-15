export interface GalleryImage {
  id: string;
  imgId: string;
  name: string;
  url: string;
  type: 'uploaded' | 'generated' | 'sended';
  sourceType: 'UPLOAD' | 'GENERATE' | 'SEND';
  size: string;
  dimensions: string;
  uploadDate: string;
  tags: string[];
  aiTool?: string;
  originalType?: string;
  originalTags?: string;
}

export default GalleryImage;
