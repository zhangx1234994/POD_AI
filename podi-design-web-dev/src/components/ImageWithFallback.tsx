import React, { useState, useEffect } from 'react';
import { IMAGE_ERROR_PLACEHOLDER, IMAGE_LOADING_PLACEHOLDER } from '@/constants/image';

export interface ImageWithFallbackProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  overlay?: React.ReactNode;
}

export function ImageWithFallback(props: ImageWithFallbackProps) {
  const [didError, setDidError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  const { src, alt, style, className, overlay, ...rest } = props as any;

  useEffect(() => {
    if (!src || typeof src !== 'string') {
      setDidError(true);
      setIsLoading(false);
      return;
    }

    // 如果是base64或blob URL，直接使用
    if (src.startsWith('data:') || src.startsWith('blob:')) {
      setBlobUrl(src);
      setIsLoading(false);
      return;
    }

    // 直接使用外链地址，避免跨域预检
    setDidError(false);
    setIsLoading(true);
    setBlobUrl(src);
    return () => {};
  }, [src]);

  const handleError = () => {
    setDidError(true);
    setIsLoading(false);
  };

  const handleLoad = () => {
    setIsLoading(false);
  };

  if (didError || !blobUrl) {
    return (
      <div
        className={`relative ${className ?? ''}`}
        style={style}
      >
        <div className="flex items-center justify-center w-full h-full">
          <img src={IMAGE_ERROR_PLACEHOLDER} alt="Error loading image" {...rest} data-original-url={src} />
        </div>
        {overlay ? <div className="absolute inset-0 flex items-center justify-center">{overlay}</div> : null}
      </div>
    );
  }

  return (
    <div className={`relative ${className ?? ''}`} style={style}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <img src={IMAGE_LOADING_PLACEHOLDER} alt="Loading..." className="w-8 h-8" />
        </div>
      )}
      <img
        src={blobUrl}
        alt={alt}
        className={`${className ?? ''} ${isLoading ? 'opacity-0' : 'opacity-100'}`}
        loading="lazy"
        decoding="async"
        style={style}
        {...rest}
        onError={handleError}
        onLoad={handleLoad}
      />
      {overlay ? <div className="absolute inset-0 flex items-center justify-center">{overlay}</div> : null}
    </div>
  );
};

export default ImageWithFallback;
