interface DesignPreviewThumbProps {
  productImage: string;
  sourceImage?: string | null;
  alt: string;
  className?: string;
}

export default function DesignPreviewThumb({ productImage, sourceImage, alt, className = "" }: DesignPreviewThumbProps) {
  return (
    <div className={`design-preview-thumb ${className}`.trim()}>
      <img className="design-preview-thumb__product" src={productImage} alt={alt} />
      {sourceImage && (
        <span className="design-preview-thumb__asset">
          <img src={sourceImage} alt={`${alt} 使用的设计素材`} />
          <em>设计素材</em>
        </span>
      )}
    </div>
  );
}
