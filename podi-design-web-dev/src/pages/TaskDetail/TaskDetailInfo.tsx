import { Card, CardContent } from '@/components/ui/card';
import { Calendar, Clock } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { parseParameters, getParameterConfig } from '@/utils/parameterUtils';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { ImageWithFallback } from '@/components/ImageWithFallback';

export function TaskDetailInfo({ task }: { task?: any }) {
  const success = task?.successCount ?? (task as any)?.successCount ?? 0;
  const total = task?.totalCount ?? (task as any)?.subTaskCount ?? 0;

  const statusCfg = task.statusCfg ?? null;
  const StatusIcon = statusCfg?.icon ?? Clock;

  const createdAt = task?.createTime ? new Date(task.createTime) : null;
  const createdStr = createdAt ? createdAt.toLocaleString() : '—';
  const params = task?.workflowParams ?? task?.workflow_params ?? {};

  const parsedParams = parseParameters(params);

  const rawParams = params?.params || params?.options || params || {};

  const rawAction = params?.action ?? task?.action ?? '';
  const actionKey = String(rawAction).replace(/-\d+$/, '');

  const mapping = getParameterConfig(actionKey) ?? null;
  const promptParamCfg = mapping?.find((p: any) => p.key === 'prompt');
  const promptVisible = promptParamCfg ? (promptParamCfg.visible !== false) : false;

  const promptParsed = parsedParams.find((p) => p.key === 'prompt');
  const promptValue = (promptParsed && promptParsed.value) ? promptParsed.value : '-';

  const displayParams = parsedParams.filter((p) => !(p.key === 'prompt' && promptVisible));

  return (
    <Card className="bg-card border border-border rounded-lg text-foreground">
      <CardContent className="px-6 py-6 [&:last-child]:pb-0">
        <div className="flex flex-row justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-14 h-14 flex items-center justify-center">
              <StatusIcon className={`h-12 w-12 ${statusCfg?.color || 'text-muted-foreground'}`} />
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-4">
                <div className="w-28 text-sm text-muted-foreground">成功/总数</div>

                <div className="flex items-baseline text-md font-medium text-foreground">
                  <span className="text-green-600">{success}</span>
                  <span className="text-foreground"> / </span>
                  <span className="text-foreground">{total}</span>
                </div>
              </div>

              <div className="flex items-center text-muted-foreground gap-4">
                <span className="text-sm">耗时</span>
                <span className="text-md text-foreground">{task?.duration ?? '—'}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-sm text-muted-foreground ml-auto">
            <div className="inline-flex items-center text-muted-foreground">
              <Calendar className="h-5 w-5 opacity-90 text-muted-foreground" />
            </div>
            <div>
              <div className="text-sm text-muted-foreground">创建时间</div>
              <div className="text-md mt-1 text-foreground">
                {createdStr}
              </div>
            </div>
          </div>
        </div>

        {promptVisible ? (
          <>
            <Separator className="my-4" />
            <div className="grid grid-cols-1">
              <p className="text-xs text-muted-foreground mb-2">任务描述</p>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words bg-muted/5">
                {promptValue}
              </p>
            </div>
          </>
        ) : null}

        <Separator className="my-4" />
        <div className="grid grid-cols-1">
          <p className="text-xs text-muted-foreground mb-2">处理参数</p>
          {parsedParams.length === 0 ? (
            <div className="text-center text-sm text-muted-foreground">暂无参数信息</div>
          ) : (
            <div className="space-y-2">
              {(() => {
                const auxParam = displayParams.find((p) => p.key === 'aux_imageList');
                const otherParams = displayParams.filter((p) => p.key !== 'aux_imageList');
                return (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                      {otherParams.map((p) => (
                          <div key={p.key} className="text-sm">
                            <span className="text-muted-foreground">{p.label}:</span>
                            <span className="ml-2 text-muted-foreground font-medium">{p.value}</span>
                          </div>
                      ))}
                    </div>

                    {auxParam ? (
                      <div key={auxParam.key} className="col-span-1">
                        <div className="flex">
                          <div className="text-sm text-muted-foreground">{auxParam.label}:</div>
                          <div className="flex-1 ml-2">
                            {Array.isArray(rawParams.aux_imageList) && rawParams.aux_imageList.length > 0 ? (
                              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                                {(rawParams.aux_imageList || []).map((img: any, idx: number) => (
                                  <div key={idx} className="flex flex-col items-start gap-1">
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <div className="cursor-pointer group">
                                          <ImageWithFallback
                                            src={img.ossUrl}
                                            alt={img.filename}
                                            className="w-16 h-16 object-cover rounded border transition-all group-hover:scale-105 flex-shrink-0"
                                          />
                                        </div>
                                      </TooltipTrigger>
                                      <TooltipContent
                                        className="bg-white border p-2 pb-3 shadow-lg w-64 h-64 overflow-hidden"
                                        showArrow={false}
                                        sideOffset={6}
                                      >
                                        <div className="w-full h-full flex flex-col">
                                          <div className="w-full flex items-center justify-center" style={{ height: 'calc(100% - 40px)' }}>
                                            <ImageWithFallback src={img.ossUrl} alt={img.filename} className="max-w-full h-full border object-contain rounded" />
                                          </div>
                                          <div className="mt-2 flex h-10 flex-col items-center">
                                            <div className="w-full text-sm text-muted-foreground text-center truncate">{img.filename}</div>
                                            {img.source && <div className="w-full text-xs text-muted-foreground text-center truncate">{img.source}</div>}
                                          </div>
                                        </div>
                                      </TooltipContent>
                                    </Tooltip>

                                    <div className="text-sm font-medium text-muted-foreground truncate w-full text-left">{img.filename}</div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-sm text-gray-500">无</div>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </>
                );
              })()}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default TaskDetailInfo;
