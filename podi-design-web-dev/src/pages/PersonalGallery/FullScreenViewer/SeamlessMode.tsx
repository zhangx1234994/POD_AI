import { UnifiedViewerContainer } from './UnifiedViewerContainer';

interface SeamlessModeProps {
  generatedUrl: string;
  generatedUrls?: string[];
  patternType?: string | undefined;
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  handlers: any;
}

export function SeamlessMode({
  generatedUrl,
  generatedUrls,
  patternType,
  scale,
  position,
  isDragging,
  handlers,
}: SeamlessModeProps) {

  // Determine source images
  const sources = (generatedUrls && generatedUrls.length > 0) ? generatedUrls : [generatedUrl];

  // Prepare 9-slot grid. For `seamless` fill all 9 with the primary image.
  // For `twoway` place up to 3 images into middle row (indexes 3,4,5).
  const gridSrcs: (string | null)[] = Array.from({ length: 9 }, () => null);
  if (patternType === 'twoway') {
    // choose first three sources (or repeat the primary if fewer)
    const three = [sources[0] || generatedUrl, sources[1] || sources[0] || generatedUrl, sources[2] || sources[0] || generatedUrl];
    gridSrcs[3] = three[0];
    gridSrcs[4] = three[1];
    gridSrcs[5] = three[2];
  } else {
    // default: seamless or unknown -> tile the first source across 3x3
    gridSrcs.fill(sources[0] || generatedUrl);
  }

  return (
    <UnifiedViewerContainer
      referenceUrl={generatedUrl}
      scale={scale}
      position={position}
      isDragging={isDragging}
      handlers={handlers}
      disableTransform={true}
    >
      <div className="w-full h-full flex items-center justify-center overflow-hidden">
        <div 
          className="grid grid-cols-3 gap-0 flex-none shadow-2xl origin-center will-change-transform"
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          }}
        >
          {gridSrcs.map((src, i) => (
            src ? (
              <img
                key={i}
                src={src}
                className="block select-none"
                style={{
                  maxWidth: '33vw',
                  maxHeight: '33vh',
                  width: 'auto',
                  height: 'auto',
                  objectFit: 'contain'
                }}
                draggable={false}
                alt=""
              />
            ) : (
              <div key={i} className="w-full h-full bg-transparent" />
            )
          ))}
        </div>
      </div>
    </UnifiedViewerContainer>
  );
}

export default SeamlessMode;
