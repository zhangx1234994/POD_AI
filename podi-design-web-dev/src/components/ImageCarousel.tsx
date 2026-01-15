import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { ImageWithFallback } from '@/components/ImageWithFallback';

interface ImageCarouselProps {
  images: Array<{
    ossKey?: string;
    ossUrl?: string;
    filename?: string;
  }>;
  className?: string;
  imageClassName?: string;
  onImageClick?: (image: { ossUrl?: string; filename?: string }, index: number) => void;
}

export function ImageCarousel({
  images,
  className = '',
  imageClassName = '',
  onImageClick,
}: ImageCarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  // 如果没有图片，显示无图图标
  if (!images || images.length === 0) {
    return (
      <div
        className={`w-full h-full flex items-center justify-center bg-gray-50 border-2 border-dashed border-gray-200 rounded-lg ${className}`}
      >
        <div className="text-center">
          <svg
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M21 15V19C21 20.1046 20.1046 21 19 21H5C3.89543 21 3 20.1046 3 19V15"
              stroke="#9CA3AF"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M17 8L12 3L7 8"
              stroke="#9CA3AF"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M12 3V15"
              stroke="#9CA3AF"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className="text-sm text-gray-500 mt-2">无图片</p>
        </div>
      </div>
    );
  }

  // 如果只有一张图片，直接显示
  if (images.length === 1) {
    return (
      <div
        className={`w-full h-full ${className}`}
        onClick={() => onImageClick && onImageClick(images[0], 0)}
      >
        <ImageWithFallback
          src={images[0].ossUrl || ''}
          alt={images[0].filename || '图片'}
          className={`w-full h-full object-contain ${imageClassName}`}
        />
      </div>
    );
  }

  // 多张图片，显示轮播
  const goToPrevious = () => {
    setCurrentIndex((prevIndex: number) => (prevIndex - 1 + images.length) % images.length);
  };

  const goToNext = () => {
    setCurrentIndex((prevIndex: number) => (prevIndex + 1) % images.length);
  };

  const goToSlide = (index: number) => {
    setCurrentIndex(index);
  };

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* 当前图片 */}
      <div
        className="w-full h-full"
        onClick={() => onImageClick && onImageClick(images[currentIndex], currentIndex)}
      >
        <ImageWithFallback
          src={images[currentIndex].ossUrl || ''}
          alt={images[currentIndex].filename || `图片 ${currentIndex + 1}`}
          className={`w-full h-full object-contain ${imageClassName}`}
        />
      </div>

      {/* 左右切换按钮 */}
      <button
        onClick={goToPrevious}
        className="absolute left-2 top-1/2 transform -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 rounded-full p-1 shadow-md transition-all"
        aria-label="上一张"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>
      <button
        onClick={goToNext}
        className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 rounded-full p-1 shadow-md transition-all"
        aria-label="下一张"
      >
        <ChevronRight className="w-4 h-4" />
      </button>

      {/* 指示器 */}
      <div className="absolute bottom-2 left-0 right-0 flex justify-center gap-1">
        {images.map((image, index) => (
          <button
            key={`indicator-${index}-${image.ossUrl || image.filename || 'no-id'}`}
            onClick={() => goToSlide(index)}
            className={`w-2 h-2 rounded-full transition-all ${
              index === currentIndex ? 'bg-blue-500 w-6' : 'bg-white/60 hover:bg-white/80'
            }`}
            aria-label={`切换到图片 ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
}

export default ImageCarousel;
