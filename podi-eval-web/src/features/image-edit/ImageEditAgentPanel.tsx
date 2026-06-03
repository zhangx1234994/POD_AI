import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Card, Input, Space, Tag, Textarea, Typography, MessagePlugin } from 'tdesign-react';
import { ChartBubbleIcon } from 'tdesign-icons-react';
import { evalApi } from '../../api';
import type { BusinessAgentMessage, BusinessAgentPlan, BusinessAgentSession, BusinessRunPollResult } from '../../api';
import { toDisplayErrorMessage } from '../../utils/errorMessageMap';
import { IMAGE_EDIT_SKILL_OPTIONS } from './model';

type AgentStatus = 'idle' | 'planning' | 'confirming' | 'polling';

export type ImageEditAgentPanelProps = {
  imageUrl: string;
  instruction: string;
  editSkill: string;
  quality: string;
  size: string;
  outputFormat: string;
  maskUrl?: string;
  referenceImages?: string[];
  selectionHints?: Array<Record<string, unknown>>;
  onUploadImage: (file: File) => Promise<string>;
  onImageUrlChange?: (url: string) => void;
  onPreviewImage?: (url: string, title?: string) => void;
  onApplyPlan?: (payload: {
    instruction?: string;
    editSkill?: string;
    quality?: string;
    size?: string;
    outputFormat?: string;
    maskUrl?: string;
  }) => void;
  showApplyToEditor?: boolean;
};

const DEFAULT_AGENT_PLACEHOLDER = '描述你想怎么改，例如：把这张花纹改得更轻奢，适合连衣裙，不要改变主花型。';
const AGENT_CHAT_EXAMPLES = [
  '把这张图改得更高级一些，适合服装面料，保留主体花型和构图。',
  '整体更干净，颜色偏蓝绿色，背景不要变。',
  '去掉明显瑕疵和杂点，纹理要自然连续。',
];

const EMPTY_CHAT_MESSAGE: BusinessAgentMessage = {
  id: 'empty-chatbot-message',
  sessionId: 'local',
  role: 'assistant',
  content: '你好，我是对话改图助手。上传或粘贴主图后，直接告诉我想怎么改；我会先整理建议，确认后再执行。',
};

const costLabel: Record<string, string> = {
  low: '低成本',
  medium: '中等成本',
  high: '高成本',
};

const riskLabel: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
};

const statusText: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
};

const skillLabel = (value: unknown): string => {
  const raw = String(value || '');
  return IMAGE_EDIT_SKILL_OPTIONS.find((item) => item.value === raw)?.label || raw || '图编辑';
};

const normalizeOutputUrls = (result: BusinessRunPollResult | null): string[] => {
  if (!result) return [];
  const values = result.imageUrls || result.image_urls || [];
  return Array.isArray(values) ? values.map((item) => String(item || '').trim()).filter(Boolean) : [];
};

const normalizeRunId = (run: Record<string, unknown> | null): string => String(run?.runId || run?.id || '').trim();

const createAgentRequestId = () => `eval-image-edit-chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const shortAgentId = (value?: string | null) => {
  const text = String(value || '').trim();
  return text ? text.slice(0, 8) : '未创建';
};

const formatAgentError = (err: unknown, fallback: string): string => {
  const raw = String((err as any)?.message || err || '').trim();
  return toDisplayErrorMessage(raw) || raw || fallback;
};

export function ImageEditAgentPanel(props: ImageEditAgentPanelProps) {
  const {
    imageUrl,
    quality,
    size,
    outputFormat,
    maskUrl = '',
    referenceImages = [],
    selectionHints = [],
    onUploadImage,
    onImageUrlChange,
    onPreviewImage,
    onApplyPlan,
    showApplyToEditor = false,
  } = props;
  const [session, setSession] = useState<BusinessAgentSession | null>(null);
  const [plan, setPlan] = useState<BusinessAgentPlan | null>(null);
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [run, setRun] = useState<Record<string, unknown> | null>(null);
  const [runResult, setRunResult] = useState<BusinessRunPollResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const sessionRequestIdRef = useRef(createAgentRequestId());
  const previousMainImageRef = useRef(String(imageUrl || '').trim());

  const busy = status !== 'idle';
  const runId = normalizeRunId(run);
  const outputUrls = useMemo(() => normalizeOutputUrls(runResult), [runResult]);
  const planPayload = (plan?.toolPayload || {}) as Record<string, unknown>;
  const currentImageUrl = String(imageUrl || session?.imageUrl || '').trim();
  const runStatus = String(runResult?.status || run?.status || '').toLowerCase();
  const chatMessages = useMemo(() => {
    const items = (session?.messages || []).filter((item) => item.role === 'user' || item.role === 'assistant' || item.role === 'tool');
    return items.length > 0 ? items : [EMPTY_CHAT_MESSAGE];
  }, [session?.messages]);

  const resetAgentSession = (opts?: { keepMessage?: boolean; notify?: boolean }) => {
    setSession(null);
    setPlan(null);
    setRun(null);
    setRunResult(null);
    sessionRequestIdRef.current = createAgentRequestId();
    if (!opts?.keepMessage) setMessage('');
    if (opts?.notify) void MessagePlugin.info('已开启新的对话改图会话。');
  };

  useEffect(() => {
    const next = String(imageUrl || '').trim();
    const prev = previousMainImageRef.current;
    if (session?.id && next && prev && next !== prev) {
      resetAgentSession({ keepMessage: true });
      void MessagePlugin.info('主图已变化，下一次生成方案会开启新会话。');
    }
    previousMainImageRef.current = next;
  }, [imageUrl, session?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [chatMessages.length, outputUrls.length, runStatus]);

  const refreshRun = async (id: string): Promise<BusinessRunPollResult | null> => {
    const result = await evalApi.getBusinessRun(id);
    setRunResult(result);
    return result;
  };

  const pollRun = async (id: string) => {
    setStatus('polling');
    try {
      for (let index = 0; index < 45; index += 1) {
        const result = await refreshRun(id);
        const state = String(result?.status || '').toLowerCase();
        if (state === 'succeeded' || state === 'failed') break;
        await new Promise((resolve) => window.setTimeout(resolve, 4000));
      }
    } finally {
      setStatus('idle');
    }
  };

  const generatePlan = async () => {
    const text = message.trim();
    if (!text) {
      await MessagePlugin.error('请先输入你想怎么改。');
      return;
    }
    setStatus('planning');
    try {
      const payload = {
        message: text,
        imageUrl: currentImageUrl || undefined,
        quality,
        size,
        outputFormat,
        maskUrl: maskUrl || undefined,
        referenceImages: referenceImages.map((url, index) => ({ url, index })),
        selectionHints,
        context: {
          entry: 'podi-eval-web',
          surface: 'image-edit-chatbot',
        },
      };
      if (!session?.id) {
        const created = await evalApi.createImageEditAgentSession({
          imageUrl: currentImageUrl || undefined,
          message: text,
          source: 'eval',
          channel: 'image-edit-chat',
          requestId: sessionRequestIdRef.current,
          quality,
          size,
          outputFormat,
          maskUrl: maskUrl || undefined,
          referenceImages: payload.referenceImages,
          selectionHints,
          context: payload.context,
          metadata: { referenceCount: referenceImages.length, selectionHintCount: selectionHints.length },
        });
        setSession(created.session);
        const nextPlan = created.plan || created.session.latestPlan || null;
        setPlan(nextPlan);
        if (nextPlan && showApplyToEditor) onApplyPlanFrom(nextPlan);
      } else {
        const result = await evalApi.sendImageEditAgentMessage(session.id, payload);
        setSession(result.session);
        setPlan(result.plan);
        if (showApplyToEditor) onApplyPlanFrom(result.plan);
      }
      await MessagePlugin.success('ChatBot 已回复，可继续沟通或确认执行。');
    } catch (err) {
      await MessagePlugin.error(formatAgentError(err, '对话改图回复失败'));
    } finally {
      setStatus('idle');
    }
  };

  const onApplyPlanFrom = (nextPlan: BusinessAgentPlan) => {
    const payload = nextPlan.toolPayload || {};
    onApplyPlan?.({
      instruction: String(payload.instruction || ''),
      editSkill: String(payload.editSkill || ''),
      quality: String(payload.quality || ''),
      size: String(payload.size || ''),
      outputFormat: String(payload.output_format || payload.outputFormat || ''),
      maskUrl: String(payload.maskUrl || ''),
    });
  };

  const confirmPlan = async () => {
    if (!session?.id || !plan?.id) {
      await MessagePlugin.error('请先生成方案。');
      return;
    }
    if (!currentImageUrl) {
      await MessagePlugin.error('请先上传或粘贴主图 URL。');
      return;
    }
    setStatus('confirming');
    try {
      const result = await evalApi.confirmImageEditAgentPlan(session.id, plan.id, {
        requestId: `iec:${shortAgentId(session.id)}:${shortAgentId(plan.id)}:${Date.now().toString(36)}`,
        overrides: { imageUrl: currentImageUrl },
      });
      setSession(result.session);
      setPlan(result.plan);
      setRun(result.run);
      await MessagePlugin.success(`已提交业务任务：${normalizeRunId(result.run)}`);
      const id = normalizeRunId(result.run);
      if (id) void pollRun(id);
    } catch (err) {
      await MessagePlugin.error(formatAgentError(err, '确认执行失败'));
      setStatus('idle');
    }
  };

  const uploadSourceImage = async (file: File) => {
    setUploading(true);
    try {
      const url = await onUploadImage(file);
      onImageUrlChange?.(url);
      const nextSession = session ? { ...session, imageUrl: url } : null;
      setSession(nextSession);
      await MessagePlugin.success('主图已上传，可继续对话改图。');
    } catch (err) {
      await MessagePlugin.error(formatAgentError(err, '上传失败'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card
      bordered
      className="podi-image-edit-agent"
      title={
        <div className="podi-image-edit-agent__title">
          <ChartBubbleIcon />
          <div>
            <strong>对话改图 ChatBot</strong>
            <span>看着主图聊天，确认后生成结果，新任务单独开会话。</span>
          </div>
        </div>
      }
    >
      <div className={`podi-image-edit-agent__grid${plan ? ' has-plan' : ' is-chat-only'}`}>
        <div className="podi-image-edit-agent__chat">
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <div className={`podi-image-edit-agent__image${currentImageUrl ? '' : ' is-empty'}`}>
              {currentImageUrl ? (
                <button type="button" onClick={() => onPreviewImage?.(currentImageUrl, '对话改图主图')}>
                  <img src={currentImageUrl} alt="对话改图主图" />
                </button>
              ) : (
                <button type="button" onClick={() => imageInputRef.current?.click()}>
                  <strong>上传主图</strong>
                  <span>改图前先让 ChatBot 看到图片</span>
                </button>
              )}
            </div>
            <div className="podi-image-edit-agent__session">
              <span>{session ? '继续当前会话' : '新会话草稿'}</span>
              <strong>{session ? shortAgentId(session.id) : '未创建'}</strong>
              {plan ? <em>最新建议 {shortAgentId(plan.id)}</em> : null}
              <Button size="small" variant="text" disabled={busy} onClick={() => resetAgentSession({ keepMessage: false, notify: true })}>
                新任务
              </Button>
            </div>
            <div className="podi-image-edit-agent__messages">
              {chatMessages.map((item) => (
                <div key={item.id} className={`podi-image-edit-agent__message is-${item.role === 'user' ? 'user' : item.role === 'tool' ? 'tool' : 'assistant'}`}>
                  <span>{item.role === 'user' ? '你' : item.role === 'tool' ? '执行结果' : 'ChatBot'}</span>
                  <p>{item.content || (item.planId ? '我整理了一条可执行建议，你可以继续沟通或直接确认执行。' : '已收到。')}</p>
                </div>
              ))}
              {runId ? (
                <div className="podi-image-edit-agent__message is-tool">
                  <span>执行结果</span>
                  <p>
                    {statusText[String(runResult?.status || run?.status || '')] || '已提交'} · {runId}
                    {runResult?.error || runResult?.errorMessage || runResult?.error_message ? `\n${runResult.error || runResult.errorMessage || runResult.error_message}` : ''}
                  </p>
                  {outputUrls.length > 0 ? (
                    <div className="podi-image-edit-agent__message-images">
                      {outputUrls.map((url, index) => (
                        <button key={`${url}-${index}`} type="button" onClick={() => onPreviewImage?.(url, `对话改图输出 ${index + 1}`)}>
                          <img src={url} alt={`对话改图输出 ${index + 1}`} />
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>
            <Input
              value={currentImageUrl}
              placeholder="主图 URL"
              clearable
              onChange={(value) => onImageUrlChange?.(String(value || ''))}
            />
            <Textarea
              value={message}
              autosize={{ minRows: 3, maxRows: 5 }}
              placeholder={DEFAULT_AGENT_PLACEHOLDER}
              onChange={(value) => setMessage(String(value))}
            />
            <div className="podi-image-edit-agent__suggestions" aria-label="对话示例">
              {AGENT_CHAT_EXAMPLES.map((example) => (
                <button key={example} type="button" onClick={() => setMessage(example)}>
                  {example}
                </button>
              ))}
            </div>
            <div className="podi-image-edit-agent__actions">
              <Button theme="primary" loading={status === 'planning'} disabled={busy} onClick={() => void generatePlan()}>
                <ChartBubbleIcon />
                发送
              </Button>
              {showApplyToEditor && onApplyPlan ? (
                <Button disabled={!plan || busy} onClick={() => plan && onApplyPlanFrom(plan)}>
                  应用到编辑器
                </Button>
              ) : null}
              <Button theme="success" loading={status === 'confirming'} disabled={!plan || busy} onClick={() => void confirmPlan()}>
                执行最新建议
              </Button>
              <Button variant="outline" loading={uploading} disabled={busy} onClick={() => imageInputRef.current?.click()}>
                上传主图
              </Button>
              <input
                ref={imageInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void uploadSourceImage(file);
                  event.currentTarget.value = '';
                }}
              />
            </div>
            {!currentImageUrl ? <Alert theme="warning" message="执行前必须上传或粘贴主图；新任务请点“新任务”，避免上下文串到上一轮。" /> : null}
          </Space>
        </div>

        {plan ? (
          <div className="podi-image-edit-agent__plan">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div className="podi-image-edit-agent__plan-head">
                <div>
                  <Typography.Text strong>{plan.title || '对话改图建议'}</Typography.Text>
                  <Typography.Paragraph>{plan.summary || '已生成可执行方案。'}</Typography.Paragraph>
                </div>
                <Space size="small">
                  <Tag theme="primary" variant="light">
                    {skillLabel(planPayload.editSkill)}
                  </Tag>
                  <Tag theme="warning" variant="light">
                    {costLabel[String(plan.estimatedCostLevel || '')] || '成本待估'}
                  </Tag>
                  <Tag theme="default" variant="light">
                    {riskLabel[String(plan.riskLevel || '')] || '风险待估'}
                  </Tag>
                </Space>
              </div>
              <div className="podi-image-edit-agent__steps">
                {(plan.editPlan || []).map((item, index) => (
                  <div key={`${item.step || index}-${index}`} className="podi-image-edit-agent__step">
                    <span>{index + 1}</span>
                    <div>
                      <strong>{item.step || '处理步骤'}</strong>
                      <small>{item.reason || '按方案执行。'}</small>
                    </div>
                  </div>
                ))}
              </div>
              {plan.warnings && plan.warnings.length > 0 ? (
                <Alert theme="info" message={plan.warnings.join('；')} />
              ) : null}
              <div className="podi-image-edit-agent__instruction">
                <span>执行指令</span>
                <p>{String(planPayload.instruction || '')}</p>
              </div>
            </Space>
          </div>
        ) : null}
      </div>

      {runId ? (
        <div className="podi-image-edit-agent__run">
          <div>
            <span>图编辑任务</span>
            <strong>{runId}</strong>
          </div>
          <div>
            <span>状态</span>
            <strong>{statusText[String(runResult?.status || run?.status || '')] || String(runResult?.status || run?.status || '已提交')}</strong>
          </div>
          <Button size="small" variant="outline" disabled={status === 'polling'} onClick={() => void refreshRun(runId)}>
            刷新结果
          </Button>
        </div>
      ) : null}

    </Card>
  );
}
