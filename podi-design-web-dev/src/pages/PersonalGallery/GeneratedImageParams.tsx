import { parseParameters } from '@/utils/parameterUtils';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { ImageWithFallback } from '@/components/ImageWithFallback';

interface GeneratedImageParamsProps {
  params: any;
}

interface ReferenceImage {
  ossUrl: string;
  source: string;
  filename: string;
}

export function GeneratedImageParams({ params }: GeneratedImageParamsProps) {
  const parsedParams = parseParameters(params);
  
  // 获取原始参数数据，用于获取aux_imageList的完整信息
  const rawParams = params?.params || params?.options || params || {};
  
  if (parsedParams.length === 0) {
    return <div className="text-center text-sm text-muted-foreground">暂无参数信息</div>;
  }

  // 检查内容是否过长，需要显示tooltip
  const isContentLong = (content: string): boolean => {
    // 简单判断：超过50个字符或包含换行符
    return content.length > 50 || content.includes('\n');
  };

  // 截断文本，不包含省略号（由CSS处理）
  const truncateText = (content: string): string => {
    return content;
  };

  return (
    <div className="space-y-3">
      {parsedParams.map((param) => {
        const content = String(param.value);
        const showTooltip = isContentLong(content);
        
        // 处理参考图参数，显示缩略图
        if (param.key === 'aux_imageList') {
          const referenceImages = (rawParams.aux_imageList || []) as ReferenceImage[];
          
          return (
            <div key={param.key} className="grid grid-cols-3 gap-2 items-start">
              <span className="text-sm text-muted-foreground font-medium pt-1 text-left">{param.label}:</span>
              <div className="col-span-2 mt-1">
                {referenceImages.length > 0 ? (
                  <ul className="space-y-2">
                    {referenceImages.map((img, index) => (
                      <li key={index} className="flex items-center gap-2">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-2 cursor-pointer group">
                              <ImageWithFallback
                                src={img.ossUrl}
                                alt={img.filename}
                                className="w-10 h-10 object-cover rounded border border-gray-200 transition-all group-hover:scale-105 flex-shrink-0"
                              />
                              <span className="text-sm text-gray-600 truncate max-w-[150px]">{img.filename}</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent
                            className="bg-white border-gray-200 p-2 shadow-lg max-w-[300px] max-h-[300px] overflow-auto"
                            showArrow={false}
                            sideOffset={8}
                          >
                            <div className="flex flex-col items-center gap-2">
                              <ImageWithFallback
                                src={img.ossUrl}
                                alt={img.filename}
                                className="w-50 h-32 object-contain rounded"
                              />
                              <div className="text-sm text-gray-700 whitespace-pre-wrap break-words text-center">{img.filename}</div>
                              {img.source && <div className="text-sm text-gray-500 break-words text-center">{img.source}</div>}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-sm text-gray-500">无</span>
                )}
              </div>
            </div>
          );
        }
        
        return (
          <div key={param.key} className="grid grid-cols-3 gap-2 items-start">
            <span className="text-sm text-muted-foreground font-medium pt-1 text-left">{param.label}:</span>

            {/* Right column: value (left-aligned, spans 2 cols) */}
            <div className="col-span-2 text-left">
              {showTooltip ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-sm cursor-help hover:text-primary block truncate max-w-full">
                      {truncateText(content)}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent
                    className="bg-white text-gray-800 border-gray-200 p-2 shadow-lg w-50 h-auto overflow-auto dark:bg-gray-800 dark:text-white dark:border-gray-700"
                    showArrow={false}
                    sideOffset={4}
                  >
                    <div className="whitespace-pre-wrap text-sm break-words text-gray-800 dark:text-white">{content}</div>
                  </TooltipContent>
                </Tooltip>
              ) : (
                <span className="text-sm block break-words">{content}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default GeneratedImageParams;
