import { Button, Space } from 'tdesign-react';
import type { Ability, AbilityInvocationLog, StoredAsset } from '../../../types/admin';
import { toDisplayErrorMessage } from '../../../utils/errorMessageMap';
import { StatusBadge } from '../shared/ui';
import { formatDateTime } from './formatters';

function StatusPill({ status }: { status: string }) {
  return <StatusBadge status={status} />;
}

type CozeAbilityMapping = {
  ability: Ability;
  workflowId?: string | null;
  latestLog?: AbilityInvocationLog | null;
};

type WorkflowBuilderPanelProps = {
  loading: boolean;
  cozeBaseUrl: string;
  cozeLoopUrl: string;
  cozeTokenHint: string;
  defaultTimeout?: number | null;
  cozeAbilityStats: {
    total: number;
    mapped: number;
  };
  cozeAbilityMappings: CozeAbilityMapping[];
  cozeRecentLogs: AbilityInvocationLog[];
  onOpenCozeStudio: () => void;
  onOpenCozeLoop: () => void;
  resolveAssetUrl: (asset: StoredAsset) => string;
};

export function WorkflowBuilderPanel({
  loading,
  cozeBaseUrl,
  cozeLoopUrl,
  cozeTokenHint,
  defaultTimeout,
  cozeAbilityStats,
  cozeAbilityMappings,
  cozeRecentLogs,
  onOpenCozeStudio,
  onOpenCozeLoop,
  resolveAssetUrl,
}: WorkflowBuilderPanelProps) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-400">
        正在加载系统配置…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="text-lg font-semibold text-white">Coze 编排入口</div>
            <p className="mt-2 text-sm text-slate-400">
              Coze 主要用于快速拼流程和临时实验。正式业务优先沉淀到“业务能力”，这里负责记录 Coze 流程 ID、打开编排画布，并查看最近运行情况。
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-2xl border border-slate-800/70 bg-slate-900/60 px-4 py-3">
                <div className="text-xs text-slate-500">编排画布</div>
                <div className="mt-1 text-sm font-semibold text-white">{cozeBaseUrl ? '已配置' : '未配置'}</div>
              </div>
              <div className="rounded-2xl border border-slate-800/70 bg-slate-900/60 px-4 py-3">
                <div className="text-xs text-slate-500">流程绑定</div>
                <div className="mt-1 text-sm font-semibold text-white">
                  {cozeAbilityStats.mapped}/{cozeAbilityStats.total}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-800/70 bg-slate-900/60 px-4 py-3">
                <div className="text-xs text-slate-500">运行观察</div>
                <div className="mt-1 text-sm font-semibold text-white">{cozeLoopUrl ? '已配置' : '未配置'}</div>
              </div>
              <div className="rounded-2xl border border-slate-800/70 bg-slate-900/60 px-4 py-3">
                <div className="text-xs text-slate-500">调用凭证</div>
                <div className="mt-1 text-sm font-semibold text-white">{cozeTokenHint}</div>
              </div>
            </div>
            <div className="mt-3 grid gap-3 text-xs text-slate-400 md:grid-cols-3">
              <div>
                <div className="text-slate-500">画布地址</div>
                <div className="font-mono text-sm text-white">{cozeBaseUrl || '未配置'}</div>
              </div>
              <div>
                <div className="text-slate-500">运行观察地址（可选）</div>
                <div className="font-mono text-sm text-white">{cozeLoopUrl || '未配置'}</div>
              </div>
              <div>
                <div className="text-slate-500">调用凭证</div>
                <div className="text-white">{cozeTokenHint}</div>
              </div>
              <div>
                <div className="text-slate-500">默认超时</div>
                <div className="text-white">{defaultTimeout ?? 0}s</div>
              </div>
              <div>
                <div className="text-slate-500">流程绑定</div>
                <div className="text-white">
                  {cozeAbilityStats.mapped}/{cozeAbilityStats.total} 已填写流程 ID
                </div>
              </div>
            </div>
          </div>
          <Space breakLine>
            <Button variant="outline" disabled={!cozeBaseUrl} onClick={onOpenCozeStudio}>
              打开编排画布
            </Button>
            <Button variant="outline" disabled={!cozeLoopUrl} onClick={onOpenCozeLoop}>
              打开运行观察
            </Button>
          </Space>
        </div>
        <div className="mt-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 text-xs text-slate-300">
          <div className="font-semibold text-white">接入步骤提醒</div>
          <ol className="mt-2 list-decimal space-y-1 pl-4">
            <li>在 Coze 内创建流程，复制流程 ID。</li>
            <li>在“能力目录”中选择厂商=Coze 的能力，填写对应的流程 ID 字段。</li>
            <li>保存后即可在本平台触发能力；最近运行会进入调用记录，接入运行观察后可进一步回放排查。</li>
          </ol>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-white text-lg font-semibold">Coze 流程绑定</h3>
              <p className="text-xs text-slate-400">列出厂商=Coze 的能力与流程 ID 绑定情况。</p>
            </div>
          </div>
          {cozeAbilityMappings.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 text-sm text-slate-400">
              还没有注册 Coze 能力，请在“能力目录”中新建厂商=Coze 的能力，并填写流程 ID。
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table>
                <thead>
                  <tr className="text-left text-xs uppercase tracking-widest text-slate-500">
                    <th>能力</th>
                    <th>流程 ID</th>
                    <th>最近运行</th>
                  </tr>
                </thead>
                <tbody>
                  {cozeAbilityMappings.map(({ ability, workflowId, latestLog }) => (
                    <tr key={ability.id}>
                      <td className="text-sm text-white">
                        <div className="font-semibold">{ability.display_name}</div>
                        <div className="text-xs text-slate-500">{ability.capability_key}</div>
                        <div className="mt-1 text-xs text-slate-400">
                          状态：<StatusPill status={ability.status} />
                        </div>
                      </td>
                      <td className="text-sm text-slate-300">
                        {workflowId ? (
                          <span className="font-mono text-xs">{workflowId}</span>
                        ) : (
                          <span className="text-amber-300">未填写</span>
                        )}
                      </td>
                      <td className="text-xs text-slate-400">
                        {latestLog ? (
                          <>
                            <StatusPill status={latestLog.status} />
                            <div className="mt-1">{formatDateTime(latestLog.created_at)}</div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-white text-lg font-semibold">最近运行记录</h3>
            <span className="text-xs text-slate-500">来自能力调用记录</span>
          </div>
          {cozeRecentLogs.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 text-sm text-slate-400">
              暂无运行记录，可在上方能力详情中执行一次测试。
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {cozeRecentLogs.map((log) => (
                <div key={log.id} className="rounded-2xl border border-slate-800/60 bg-slate-950/40 p-4 text-xs text-slate-300">
                  <div className="flex items-center justify-between text-white">
                    <span>
                      #{log.id} · {log.capability_key}
                    </span>
                    <StatusPill status={log.status} />
                  </div>
                  <div className="mt-1 text-slate-400">{formatDateTime(log.created_at)}</div>
                  {log.result_assets && log.result_assets.length > 0 && (
                    <div className="mt-2">
                      <div className="text-slate-500">输出资源</div>
                      {log.result_assets.map((asset, index) => {
                        const url = resolveAssetUrl(asset);
                        if (!url) return null;
                        return (
                          <div key={`${log.id}-asset-${index}`} className="truncate text-sky-300">
                            <a href={url} target="_blank" rel="noreferrer" className="underline">
                              {url}
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {log.error_message && <div className="mt-2 text-rose-300">错误：{toDisplayErrorMessage(log.error_message)}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
