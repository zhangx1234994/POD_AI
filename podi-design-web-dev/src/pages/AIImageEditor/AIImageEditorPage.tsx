import React, { useState } from 'react';
import { EditorToolbar } from './components/EditorToolbar';
import { EditorCanvas } from './components/EditorCanvas';
import { EditorSidebar } from './components/EditorSidebar';
import { EditorFooter } from './components/EditorFooter';
import { EnhancedImageUpload } from '@/components/EnhancedImageUpload';
import type { ImageItem } from '@/types/upload';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface AIImageEditorPageProps {
  action?: string;
}

type ShapeType = 'point' | 'rect' | 'circle';

interface Shape {
  id: string;
  type: ShapeType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  radius?: number;
  color: string;
  size: number;
  label?: string;
  description?: string;
}

export const AIImageEditorPage: React.FC<AIImageEditorPageProps> = () => {
  const allowMultiple = false;
  const maxImages = 1;
  const [zoom, setZoom] = useState(100);
  const [activeTool, setActiveTool] = useState<'select' | 'click' | 'rect' | 'circle'>('select');
  const [brushSize, setBrushSize] = useState(30);
  const [selectedColor, setSelectedColor] = useState('#F87171');
  const [description, setDescription] = useState('');
  const [outputSize, setOutputSize] = useState<'original' | 'custom'>('original');
  const [shapes, setShapes] = useState<Shape[]>([]);
  const [selectedShapeId, setSelectedShapeId] = useState<string | null>(null);
  const [highlightedShapeId, setHighlightedShapeId] = useState<string | null>(null);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [mainImageSrc, setMainImageSrc] = useState<string | undefined>(undefined);
  const [uploadedImages, setUploadedImages] = useState<ImageItem[]>([]);
  const [mainImageSource, setMainImageSource] = useState<'upload' | 'personal'>('upload');

  const handleUpload = () => {
    setShowUploadDialog(true);
  };

  const handleImagesChange = (images: ImageItem[]) => {
    setUploadedImages(images);
    if (images.length > 0) {
      setMainImageSrc(images[0].preview);
      setMainImageSource(images[0].source as 'upload' | 'personal' || 'upload');
    } else {
      setMainImageSrc(undefined);
      setMainImageSource('upload');
      setShapes([]);
      setSelectedShapeId(null);
    }
    if (images.length > 0) {
      setShowUploadDialog(false);
    }
  };

  const handleShapeAdd = (shape: Shape) => {
    setShapes(prev => [...prev, shape]);
    setSelectedShapeId(shape.id);
  };

  const handleShapeUpdate = (updatedShape: Shape) => {
    setShapes(prev => prev.map(shape => 
      shape.id === updatedShape.id ? updatedShape : shape
    ));
  };

  const handleShapeDelete = (shapeId: string) => {
    setShapes(prev => prev.filter(shape => shape.id !== shapeId));
    if (selectedShapeId === shapeId) {
      setSelectedShapeId(null);
    }
  };

  const handleShapeSelect = (shapeId: string | null) => {
    setSelectedShapeId(shapeId);
  };

  const handleClearAll = () => {
    setMainImageSrc(undefined);
    setUploadedImages([]);
    setShapes([]);
    setSelectedShapeId(null);
    setHighlightedShapeId(null);
    setOutputSize('original');
  };

  return (
    <div className="flex flex-col h-full relative overflow-hidden">
      <div className="flex-1 flex flex-col relative overflow-hidden">
        <div className="z-10" style={{ marginTop: '0px' }}>
          <EditorToolbar 
            activeTool={activeTool}
            onToolChange={setActiveTool}
            brushSize={brushSize}
            onBrushSizeChange={setBrushSize}
            selectedColor={selectedColor}
            onColorChange={setSelectedColor}
            zoomLevel={zoom}
            onZoomChange={setZoom}
            onUpload={handleUpload}
            hasBaseImage={Boolean(mainImageSrc)}
          />
        </div>

        <div className="flex-1 flex gap-4 overflow-hidden">
          <div className="flex-1 flex flex-col overflow-hidden">
            <EditorCanvas 
              imageSrc={mainImageSrc}
              onUpload={handleUpload}
              activeTool={activeTool}
              brushSize={brushSize}
              selectedColor={selectedColor}
              shapes={shapes}
              onShapeAdd={handleShapeAdd}
              onShapeUpdate={handleShapeUpdate}
              onShapeDelete={handleShapeDelete}
              onShapeSelect={handleShapeSelect}
              selectedShapeId={selectedShapeId}
              highlightedShapeId={highlightedShapeId}
              zoomLevel={zoom}
              onZoomChange={setZoom}
            />
            <EditorFooter annotationCount={shapes.length} shapes={shapes} onHighlightShape={setHighlightedShapeId} onShapeDelete={handleShapeDelete} />
          </div>

          <div className="flex-none w-[312px] overflow-hidden flex flex-col">
            <EditorSidebar 
              description={description}
              onDescriptionChange={setDescription}
              outputSize={outputSize}
              onOutputSizeChange={setOutputSize}
              shapes={shapes}
              selectedShapeId={selectedShapeId}
              onShapeSelect={setSelectedShapeId}
              onShapeUpdate={handleShapeUpdate}
              onShapeDelete={handleShapeDelete}
              mainImageSrc={mainImageSrc}
              uploadedImages={uploadedImages}
              mainImageSource={mainImageSource}
              onHighlightShape={setHighlightedShapeId}
              onClearAll={handleClearAll}
            />
          </div>
        </div>
      </div>
      <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col pt-10">
          <DialogHeader>
            <DialogTitle>上传图片</DialogTitle>
            <DialogDescription className="text-xs">
              点击上传或从图库选择图片作为底图
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex-1 py-4">
            <EnhancedImageUpload
              title="选择底图"
              description="点击上传或从图库选择"
              supportText={`支持 PNG, JPG, JPEG, BMP格式，单张最大5M，最多${maxImages}张`}
              maxImages={maxImages}
              allowMultiple={allowMultiple}
              onImagesChange={handleImagesChange}
              zebraConnected={true}
              hummingbirdConnected={true}
              images={uploadedImages}
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AIImageEditorPage;
