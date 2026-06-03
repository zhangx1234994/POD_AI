import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Card, Input, Tag, Textarea, MessagePlugin } from 'tdesign-react';
import { ChartBubbleIcon } from 'tdesign-icons-react';
import { evalApi } from '../../api';
import type { BusinessAgentMessage, BusinessAgentPlan, BusinessAgentSession, BusinessRunPollResult } from '../../api';
import { toDisplayErrorMessage } from '../../utils/errorMessageMap';
import { IMAGE_EDIT_SKILL_OPTIONS } from './model';

type AgentStatus = 'idle' | 'planning' | 'confirming' | 'polling' | 'restoring';

type AgentThreadSnapshot = {
  sessionId: string;
  title: string;
  imageUrl?: string;
  latestPlanId?: string | null;
  latestRunId?: string | null;
  latestRunStatus?: string | null;
  outputUrls?: string[];
  updatedAt: number;
  lastMessage?: string;
};

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

const DEFAULT_AGENT_PLACEHOLDER = '直接说你想怎么改，例如：把这张花纹改得更高级，适合服装面料，保留主体花型。';
const AGENT_CHAT_EXAMPLES = [
  '把这张图改得更高级一些，适合服装面料，保留主体花型和构图。',
  '整体更干净，颜色偏蓝绿色，背景不要变。',
  '去掉明显瑕疵和杂点，纹理要自然连续。',
];

const EMPTY_CHAT_MESSAGE: BusinessAgentMessage = {
  id: 'empty-chatbot-message',
  sessionId: 'local',
  role: 'assistant',
  content: '上传或粘贴一张主图，然后像聊天一样告诉我想怎么改。我会先整理执行建议，确认后开始出图。',
};

const THREAD_STORAGE_KEY = 'podi:image-edit-agent:threads:v1';
const MAX_THREAD_SNAPSHOTS = 12;

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

const normalizeRunResultId = (result: BusinessRunPollResult | Record<string, unknown> | null): string =>
  String(result?.runId || result?.id || '').trim();

const createAgentRequestId = () => `eval-image-edit-chat-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const shortAgentId = (value?: string | null) => {
  const text = String(value || '').trim();
  return text ? text.slice(0, 8) : '未创建';
};

const formatAgentError = (err: unknown, fallback: string): string => {
  const raw = String((err as any)?.message || err || '').trim();
  return toDisplayErrorMessage(raw) || raw || fallback;
};

const truncateText = (value: string, max = 24) => {
  const text = value.trim().replace(/\s+/g, ' ');
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const getLatestUserMessage = (session?: BusinessAgentSession | null) => {
  const messages = session?.messages || [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === 'user' && messages[index]?.content) return String(messages[index].content);
  }
  return '';
};

const buildThreadTitle = (session: BusinessAgentSession, fallback = '') => {
  const title = String(session.title || '').trim();
  if (title && title !== '对话改图') return truncateText(title, 24);
  const latestMessage = getLatestUserMessage(session) || fallback;
  return truncateText(latestMessage || '未命名改图任务', 24);
};

const loadThreadSnapshots = (): AgentThreadSnapshot[] => {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(THREAD_STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.sessionId === 'string' && item.sessionId)
      .slice(0, MAX_THREAD_SNAPSHOTS)
      .map((item) => ({
        sessionId: item.sessionId,
        title: String(item.title || '未命名改图任务'),
        imageUrl: item.imageUrl ? String(item.imageUrl) : undefined,
        latestPlanId: item.latestPlanId ? String(item.latestPlanId) : null,
        latestRunId: item.latestRunId ? String(item.latestRunId) : null,
        latestRunStatus: item.latestRunStatus ? String(item.latestRunStatus) : null,
        outputUrls: Array.isArray(item.outputUrls) ? item.outputUrls.map((url: unknown) => String(url || '')).filter(Boolean) : [],
        updatedAt: Number(item.updatedAt || Date.now()),
        lastMessage: item.lastMessage ? String(item.lastMessage) : '',
      }))
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
};

const saveThreadSnapshots = (items: AgentThreadSnapshot[]) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(items.slice(0, MAX_THREAD_SNAPSHOTS)));
  } catch {
    // Ignore storage quota and private browsing failures; the active session still works.
  }
};

const formatThreadTime = (time: number) => {
  const date = new Date(time);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const timeText = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
  if (sameDay) return timeText;
  return `${date.getMonth() + 1}/${date.getDate()} ${timeText}`;
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

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
  const [runResultsById, setRunResultsById] = useState<Record<string, BusinessRunPollResult>>({});
  const [uploading, setUploading] = useState(false);
  const [threads, setThreads] = useState<AgentThreadSnapshot[]>(() => loadThreadSnapshots());
  const [sourceOpen, setSourceOpen] = useState(false);
  const [pollStartedAt, setPollStartedAt] = useState<number | null>(null);
  const [pollElapsedSeconds, setPollElapsedSeconds] = useState(0);
  const [agentError, setAgentError] = useState('');
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const sessionRequestIdRef = useRef(createAgentRequestId());
  const fetchedRunIdsRef = useRef<Set<string>>(new Set());
  const previousMainImageRef = useRef(String(imageUrl || '').trim());

  const busy = status !== 'idle';
  const runId = normalizeRunId(run);
  const currentRunResult = runId ? runResultsById[runId] || runResult : null;
  const planPayload = (plan?.toolPayload || {}) as Record<string, unknown>;
  const sourceImageUrl = String(imageUrl || '').trim();
  const currentImageUrl = String(session?.imageUrl || sourceImageUrl || '').trim();
  const runStatus = String(currentRunResult?.status || run?.status || '').toLowerCase();
  const chatMessages = useMemo(() => {
    const items = (session?.messages || []).filter((item) => item.role === 'user' || item.role === 'assistant' || item.role === 'tool');
    return items.length > 0 ? items : [EMPTY_CHAT_MESSAGE];
  }, [session?.messages]);
  const toolRunIds = useMemo(() => {
    const ids: string[] = [];
    for (const item of session?.messages || []) {
      const id = String(item.runId || '').trim();
      if (id && !ids.includes(id)) ids.push(id);
    }
    if (runId && !ids.includes(runId)) ids.push(runId);
    return ids;
  }, [runId, session?.messages]);
  const latestSuccessfulRun = useMemo(() => {
    for (let index = toolRunIds.length - 1; index >= 0; index -= 1) {
      const id = toolRunIds[index];
      const result = runResultsById[id] || (id === runId ? currentRunResult : null);
      const urls = normalizeOutputUrls(result || null);
      if (String(result?.status || '').toLowerCase() === 'succeeded' && urls.length > 0) return { id, urls };
    }
    return null;
  }, [currentRunResult, runId, runResultsById, toolRunIds]);
  const latestOutputUrls = latestSuccessfulRun?.urls || [];
  const latestOutputRunId = latestSuccessfulRun?.id || '';
  const latestOutputUrl = latestOutputUrls[0] || '';
  const activeImageUrl = latestOutputUrl || currentImageUrl;
  const activeImageIsGenerated = Boolean(latestOutputUrl);
  const currentPlanRunId = useMemo(() => {
    if (!plan?.id) return '';
    const toolCall = (session?.toolCalls || []).find((item) => item.planId === plan.id && item.runId);
    if (toolCall?.runId) return String(toolCall.runId);
    const toolMessage = (session?.messages || []).find((item) => item.planId === plan.id && item.runId);
    return String(toolMessage?.runId || '').trim();
  }, [plan?.id, session?.messages, session?.toolCalls]);
  const currentPlanRunResult = currentPlanRunId ? runResultsById[currentPlanRunId] || (currentPlanRunId === runId ? currentRunResult : null) : null;
  const currentPlanRunStatus = String(currentPlanRunResult?.status || '').toLowerCase();
  const currentPlanNeedsConfirmation = Boolean(plan && !currentPlanRunId && plan.status !== 'executed');
  const statusLabel =
    status === 'planning'
      ? '正在理解图片'
      : status === 'confirming'
        ? '正在提交任务'
        : status === 'polling'
          ? '正在出图'
          : status === 'restoring'
            ? '正在恢复任务'
            : runStatus
              ? statusText[runStatus] || runStatus
              : currentPlanNeedsConfirmation
                ? '等待确认'
                : '待沟通';

  const rememberRunResult = (id: string, result: BusinessRunPollResult | Record<string, unknown> | null, opts?: { asCurrent?: boolean }) => {
    const normalizedId = String(id || normalizeRunResultId(result)).trim();
    if (!normalizedId || !result) return;
    const normalized = result as BusinessRunPollResult;
    setRunResultsById((prev) => ({ ...prev, [normalizedId]: normalized }));
    if (opts?.asCurrent) setRunResult(normalized);
  };

  const rememberThread = (snapshot: AgentThreadSnapshot) => {
    setThreads((prev) => {
      const merged = [snapshot, ...prev.filter((item) => item.sessionId !== snapshot.sessionId)]
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, MAX_THREAD_SNAPSHOTS);
      saveThreadSnapshots(merged);
      return merged;
    });
  };

  const resetAgentSession = (opts?: { keepMessage?: boolean; notify?: boolean }) => {
    setSession(null);
    setPlan(null);
    setRun(null);
    setRunResult(null);
    setRunResultsById({});
    fetchedRunIdsRef.current = new Set();
    setPollStartedAt(null);
    setPollElapsedSeconds(0);
    setAgentError('');
    sessionRequestIdRef.current = createAgentRequestId();
    if (!opts?.keepMessage) setMessage('');
    if (opts?.notify) void MessagePlugin.info('已开启新的改图任务，历史任务保留在左侧。');
  };

  useEffect(() => {
    const next = sourceImageUrl;
    const prev = previousMainImageRef.current;
    if (session?.id && next && prev && next !== prev) {
      resetAgentSession({ keepMessage: true });
      void MessagePlugin.info('主图已变化，已为这张图开启新的改图任务。');
    }
    previousMainImageRef.current = next;
  }, [sourceImageUrl, session?.id]);

  useEffect(() => {
    if (!session?.id) return;
    rememberThread({
      sessionId: session.id,
      title: buildThreadTitle(session, message),
      imageUrl: activeImageUrl || undefined,
      latestPlanId: plan?.id || session.latestPlanId || null,
      latestRunId: runId || session.latestRunId || session.latestToolCall?.runId || null,
      latestRunStatus: runStatus || null,
      outputUrls: latestOutputUrls,
      updatedAt: Date.now(),
      lastMessage: getLatestUserMessage(session) || message,
    });
  }, [activeImageUrl, latestOutputUrls.join('|'), plan?.id, runId, runStatus, session?.id, session?.latestPlanId, session?.latestRunId, session?.latestToolCall?.runId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [agentError, chatMessages.length, latestOutputUrls.length, runStatus, status, plan?.id]);

  useEffect(() => {
    const ids = Array.from(
      new Set(
        (session?.messages || [])
          .map((item) => String(item.runId || '').trim())
          .filter(Boolean),
      ),
    ).slice(-8);
    for (const id of ids) {
      if (runResultsById[id] || fetchedRunIdsRef.current.has(id)) continue;
      fetchedRunIdsRef.current.add(id);
      void evalApi
        .getBusinessRun(id)
        .then((result) => rememberRunResult(id, result))
        .catch(() => {
          fetchedRunIdsRef.current.delete(id);
        });
    }
  }, [runResultsById, session?.messages]);

  useEffect(() => {
    if (status !== 'polling' || !pollStartedAt) return undefined;
    setPollElapsedSeconds(Math.max(0, Math.floor((Date.now() - pollStartedAt) / 1000)));
    const timer = window.setInterval(() => {
      setPollElapsedSeconds(Math.max(0, Math.floor((Date.now() - pollStartedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [pollStartedAt, status]);

  const refreshRun = async (id: string, opts?: { asCurrent?: boolean }): Promise<BusinessRunPollResult | null> => {
    const result = await evalApi.getBusinessRun(id);
    rememberRunResult(id, result, { asCurrent: opts?.asCurrent ?? true });
    return result;
  };

  const pollRun = async (id: string) => {
    setStatus('polling');
    setPollStartedAt(Date.now());
    let finalResult: BusinessRunPollResult | null = null;
    try {
      for (let index = 0; index < 120; index += 1) {
        const result = await refreshRun(id);
        finalResult = result;
        const state = String(result?.status || '').toLowerCase();
        if (state === 'succeeded' || state === 'failed') break;
        await sleep(5000);
      }
    } finally {
      const urls = normalizeOutputUrls(finalResult);
      if (String(finalResult?.status || '').toLowerCase() === 'succeeded' && urls[0]) {
        setSession((prev) => (prev ? { ...prev, imageUrl: urls[0] } : prev));
      }
      setStatus('idle');
    }
  };

  const generatePlan = async () => {
    const text = message.trim();
    if (!text) {
      await MessagePlugin.error('请先输入你想怎么改。');
      return;
    }
    setAgentError('');
    setStatus('planning');
    setPlan(null);
    setRun(null);
    setRunResult(null);
    try {
      const baseImageUrl = activeImageUrl || undefined;
      const payload = {
        message: text,
        imageUrl: baseImageUrl,
        quality,
        size,
        outputFormat,
        maskUrl: maskUrl || undefined,
        referenceImages: referenceImages.map((url, index) => ({ url, index })),
        selectionHints,
        context: {
          entry: 'podi-eval-web',
          surface: 'image-edit-chatbot',
          baseImageRole: activeImageIsGenerated ? 'previous_result' : 'source_image',
          previousRunId: activeImageIsGenerated ? latestOutputRunId || undefined : undefined,
        },
      };
      if (!session?.id) {
        const created = await evalApi.createImageEditAgentSession({
          imageUrl: baseImageUrl,
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
          metadata: {
            referenceCount: referenceImages.length,
            selectionHintCount: selectionHints.length,
            baseImageRole: activeImageIsGenerated ? 'previous_result' : 'source_image',
          },
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
      setMessage('');
    } catch (err) {
      const errorText = formatAgentError(err, '对话改图回复失败');
      setAgentError(errorText);
      await MessagePlugin.error(errorText);
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
      await MessagePlugin.error('请先生成建议。');
      return;
    }
    if (!activeImageUrl) {
      await MessagePlugin.error('请先上传或粘贴主图。');
      return;
    }
    setAgentError('');
    setStatus('confirming');
    try {
      const result = await evalApi.confirmImageEditAgentPlan(session.id, plan.id, {
        requestId: `iec:${shortAgentId(session.id)}:${shortAgentId(plan.id)}:${Date.now().toString(36)}`,
        overrides: { imageUrl: activeImageUrl },
      });
      setSession(result.session);
      setPlan(result.plan);
      setRun(result.run);
      const id = normalizeRunId(result.run);
      if (id) rememberRunResult(id, result.run, { asCurrent: true });
      if (id) void pollRun(id);
    } catch (err) {
      const errorText = formatAgentError(err, '确认执行失败');
      setAgentError(errorText);
      await MessagePlugin.error(errorText);
      setStatus('idle');
    }
  };

  const restoreThread = async (item: AgentThreadSnapshot) => {
    if (busy) return;
    setAgentError('');
    setStatus('restoring');
    try {
      const result = await evalApi.getImageEditAgentSession(item.sessionId);
      const nextSession = result.session;
      const plans = nextSession.plans || [];
      const nextPlan = nextSession.latestPlan || plans[plans.length - 1] || null;
      const restoredRunId = nextSession.latestRunId || nextSession.latestToolCall?.runId || item.latestRunId || '';
      setSession(nextSession);
      setPlan(nextPlan);
      setRun(restoredRunId ? { runId: restoredRunId, id: restoredRunId, status: item.latestRunStatus || 'submitted' } : null);
      setRunResult(null);
      setMessage('');
      if (restoredRunId && item.outputUrls?.length) {
        rememberRunResult(restoredRunId, {
          runId: restoredRunId,
          id: restoredRunId,
          status: item.latestRunStatus || 'succeeded',
          imageUrls: item.outputUrls,
        });
      }
      const restoredImageUrl = String(nextSession.imageUrl || item.imageUrl || '').trim();
      if (restoredImageUrl) onImageUrlChange?.(restoredImageUrl);
      if (restoredRunId) {
        const latest = await refreshRun(restoredRunId);
        const state = String(latest?.status || '').toLowerCase();
        const urls = normalizeOutputUrls(latest);
        if (state === 'succeeded' && urls[0]) {
          setSession((prev) => (prev?.id === nextSession.id ? { ...prev, imageUrl: urls[0] } : prev));
        }
        if (state && state !== 'succeeded' && state !== 'failed') void pollRun(restoredRunId);
      }
    } catch (err) {
      const errorText = formatAgentError(err, '恢复任务失败');
      setAgentError(errorText);
      await MessagePlugin.error(errorText);
    } finally {
      setStatus((current) => (current === 'polling' ? current : 'idle'));
    }
  };

  const uploadSourceImage = async (file: File) => {
    setUploading(true);
    try {
      const url = await onUploadImage(file);
      onImageUrlChange?.(url);
      const nextSession = session ? { ...session, imageUrl: url } : null;
      setSession(nextSession);
      setSourceOpen(false);
      await MessagePlugin.success('主图已上传，可继续对话改图。');
    } catch (err) {
      const errorText = formatAgentError(err, '上传失败');
      setAgentError(errorText);
      await MessagePlugin.error(errorText);
    } finally {
      setUploading(false);
    }
  };

  const getRunResultForMessage = (id: string) => runResultsById[id] || (id === runId ? currentRunResult : null);

  const renderImageStrip = (urls: string[], titlePrefix: string) => {
    if (urls.length === 0) return null;
    return (
      <div className="podi-image-edit-agent__message-images">
        {urls.map((url, index) => (
          <button key={`${url}-${index}`} type="button" onClick={() => onPreviewImage?.(url, `${titlePrefix} ${index + 1}`)}>
            <img src={url} alt={`${titlePrefix} ${index + 1}`} />
          </button>
        ))}
      </div>
    );
  };

  const renderMessageAttachments = (item: BusinessAgentMessage) => {
    const urls = (item.attachments || [])
      .map((attachment) => String(attachment?.url || '').trim())
      .filter(Boolean);
    if (urls.length === 0) return null;
    return renderImageStrip(urls.slice(0, 3), item.role === 'user' ? '本轮基准图' : '消息图片');
  };

  const renderToolMessageContent = (item: BusinessAgentMessage) => {
    const id = String(item.runId || '').trim();
    const result = id ? getRunResultForMessage(id) : null;
    const state = String(result?.status || (id === runId ? runStatus : '') || '').toLowerCase();
    const urls = normalizeOutputUrls(result || null);
    const errorText = String(result?.error || result?.errorMessage || result?.error_message || '').trim();
    const runningText =
      id && id === runId && status === 'polling'
        ? `正在出图，完成后结果会直接出现在这里。已等待 ${pollElapsedSeconds}s`
        : '任务已提交，完成后结果会直接出现在这里。';
    const content =
      state === 'succeeded'
        ? '已完成，结果如下。继续输入时会默认基于这张结果图修改。'
        : state === 'failed'
          ? `执行失败，请查看错误后重试。${errorText ? `\n${errorText}` : ''}`
          : runningText;
    return (
      <>
        <p>
          {state !== 'succeeded' && state !== 'failed' ? <i aria-hidden="true" /> : null}
          {content}
        </p>
        {renderImageStrip(urls, '对话改图输出')}
      </>
    );
  };

  const renderChatMessage = (item: BusinessAgentMessage) => {
    const isTool = item.role === 'tool';
    const roleClass = item.role === 'user' ? 'user' : isTool ? 'tool' : 'assistant';
    return (
      <div key={item.id} className={`podi-image-edit-agent__message is-${roleClass}`}>
        <span>{item.role === 'user' ? '你' : isTool ? '执行结果' : '图片 Codex'}</span>
        {isTool ? (
          renderToolMessageContent(item)
        ) : (
          <>
            <p>{item.content || (item.planId ? '我整理了一条可执行建议，你可以继续沟通或直接确认执行。' : '已收到。')}</p>
            {renderMessageAttachments(item)}
          </>
        )}
      </div>
    );
  };

  const renderWorkingMessage = () => {
    if (status === 'idle' || status === 'restoring' || status === 'polling') return null;
    const text =
      status === 'planning'
        ? '正在理解图片和你的目标，整理可执行建议...'
        : status === 'confirming'
          ? '正在提交图编辑任务...'
          : `正在出图，完成后结果会直接出现在这里。已等待 ${pollElapsedSeconds}s`;
    return (
      <div className="podi-image-edit-agent__message is-working">
        <span>图片 Codex</span>
        <p>
          <i aria-hidden="true" />
          {text}
        </p>
      </div>
    );
  };

  const renderErrorMessage = () => {
    if (!agentError) return null;
    return (
      <div className="podi-image-edit-agent__message is-error">
        <span>图片 Codex</span>
        <p>{agentError}</p>
      </div>
    );
  };

  const renderPlanMessage = () => {
    if (!plan) return null;
    if ((currentPlanRunId || plan.status === 'executed') && currentPlanRunStatus !== 'failed') return null;
    return (
      <div className="podi-image-edit-agent__message is-plan">
        <span>图片 Codex 建议</span>
        <div className="podi-image-edit-agent__plan-head">
          <div>
            <strong>{plan.title || '可执行改图建议'}</strong>
            <p>{plan.summary || '已生成一版可执行方案。你可以继续补充要求，也可以直接执行。'}</p>
          </div>
          <div className="podi-image-edit-agent__plan-tags">
            <Tag theme="primary" variant="light">
              {skillLabel(planPayload.editSkill)}
            </Tag>
            <Tag theme="warning" variant="light">
              {costLabel[String(plan.estimatedCostLevel || '')] || '成本待估'}
            </Tag>
            <Tag theme="default" variant="light">
              {riskLabel[String(plan.riskLevel || '')] || '风险待估'}
            </Tag>
          </div>
        </div>
        {(plan.editPlan || []).length > 0 ? (
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
        ) : null}
        {plan.warnings && plan.warnings.length > 0 ? <Alert theme="info" message={plan.warnings.join('；')} /> : null}
        <div className="podi-image-edit-agent__instruction">
          <span>将执行</span>
          <p>{String(planPayload.instruction || plan.summary || '')}</p>
        </div>
        <div className="podi-image-edit-agent__inline-actions">
          <Button theme="primary" loading={status === 'confirming'} disabled={busy || !activeImageUrl} onClick={() => void confirmPlan()}>
            执行这版
          </Button>
          {showApplyToEditor && onApplyPlan ? (
            <Button disabled={busy} onClick={() => onApplyPlanFrom(plan)}>
              同步到工作台
            </Button>
          ) : null}
        </div>
      </div>
    );
  };

  return (
    <Card
      bordered
      className="podi-image-edit-agent"
      title={
        <div className="podi-image-edit-agent__title">
          <ChartBubbleIcon />
          <div>
            <strong>图片 Codex</strong>
            <span>一个改图任务一条线程：对话、执行、结果都在同一处。</span>
          </div>
        </div>
      }
    >
      <div className="podi-image-edit-agent__workspace">
        <aside className="podi-image-edit-agent__threads" aria-label="最近改图任务">
          <div className="podi-image-edit-agent__threads-head">
            <span>最近任务</span>
            <button type="button" disabled={busy} onClick={() => resetAgentSession({ keepMessage: false, notify: true })}>
              新建
            </button>
          </div>
          <div className="podi-image-edit-agent__thread-list">
            {threads.length > 0 ? (
              threads.map((item) => (
                <button
                  key={item.sessionId}
                  type="button"
                  className={session?.id === item.sessionId ? 'is-active' : ''}
                  disabled={busy}
                  onClick={() => void restoreThread(item)}
                >
                  <strong>{item.title}</strong>
                  <span>
                    {statusText[String(item.latestRunStatus || '').toLowerCase()] || (item.latestPlanId ? '有建议' : '会话')}
                    {' · '}
                    {formatThreadTime(item.updatedAt)}
                  </span>
                </button>
              ))
            ) : (
              <p>暂无历史任务</p>
            )}
          </div>
        </aside>

        <section className="podi-image-edit-agent__chat" aria-label="图片改图对话">
          <div className="podi-image-edit-agent__chat-head">
            <div>
              <strong>{session ? buildThreadTitle(session, message) : '新改图任务'}</strong>
              <span>{activeImageUrl ? (activeImageIsGenerated ? '当前基准图：上一轮结果' : '当前基准图：主图') : '先上传或粘贴主图'}</span>
            </div>
            <Tag theme={status === 'idle' ? 'default' : 'primary'} variant="light">
              {statusLabel}
            </Tag>
          </div>
          <div className="podi-image-edit-agent__messages">
            {chatMessages.map((item) => renderChatMessage(item))}
            {renderWorkingMessage()}
            {renderErrorMessage()}
            {renderPlanMessage()}
            <div ref={messagesEndRef} />
          </div>
          <div className="podi-image-edit-agent__composer">
            <Textarea
              value={message}
              autosize={{ minRows: 3, maxRows: 5 }}
              placeholder={DEFAULT_AGENT_PLACEHOLDER}
              disabled={status === 'planning' || status === 'confirming' || status === 'restoring'}
              onChange={(value) => setMessage(String(value))}
            />
            <div className="podi-image-edit-agent__suggestions" aria-label="对话示例">
              {AGENT_CHAT_EXAMPLES.map((example) => (
                <button key={example} type="button" disabled={busy} onClick={() => setMessage(example)}>
                  {example}
                </button>
              ))}
            </div>
            <div className="podi-image-edit-agent__actions">
              <Button theme="primary" loading={status === 'planning'} disabled={busy || !message.trim()} onClick={() => void generatePlan()}>
                <ChartBubbleIcon />
                发送
              </Button>
              <Button variant="outline" loading={uploading} disabled={busy} onClick={() => imageInputRef.current?.click()}>
                {currentImageUrl ? '更换主图' : '上传主图'}
              </Button>
              <Button variant="text" disabled={busy} onClick={() => resetAgentSession({ keepMessage: false, notify: true })}>
                新建改图
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
          </div>
          {!currentImageUrl ? <Alert theme="warning" message="执行前需要一张主图；新建改图只会开启新线程，不会删除左侧历史。" /> : null}
        </section>

        <aside className="podi-image-edit-agent__context" aria-label="当前图片和任务状态">
          <div className={`podi-image-edit-agent__image${activeImageUrl ? '' : ' is-empty'}`}>
            {activeImageUrl ? (
              <button type="button" onClick={() => onPreviewImage?.(activeImageUrl, activeImageIsGenerated ? '当前基准图：上一轮结果' : '当前基准图：主图')}>
                <img src={activeImageUrl} alt={activeImageIsGenerated ? '当前基准图：上一轮结果' : '当前基准图：主图'} />
              </button>
            ) : (
              <button type="button" onClick={() => imageInputRef.current?.click()}>
                <strong>上传主图</strong>
                <span>让图片 Codex 先看到图片</span>
              </button>
            )}
          </div>
          {activeImageIsGenerated && sourceImageUrl && sourceImageUrl !== activeImageUrl ? (
            <div className="podi-image-edit-agent__context-result">
              <span>原始主图</span>
              <button type="button" onClick={() => onPreviewImage?.(sourceImageUrl, '对话改图原始主图')}>
                <img src={sourceImageUrl} alt="对话改图原始主图" />
              </button>
            </div>
          ) : null}
          <div className="podi-image-edit-agent__state">
            <span>当前状态</span>
            <strong>{statusLabel}</strong>
            {status === 'polling' ? <small>已等待 {pollElapsedSeconds}s，页面会自动刷新结果。</small> : null}
            {status !== 'polling' && activeImageIsGenerated ? <small>继续输入会基于上一轮成功结果图修改；新任务请点左侧“新建”。</small> : null}
          </div>
          <details className="podi-image-edit-agent__source" open={sourceOpen} onToggle={(event) => setSourceOpen(event.currentTarget.open)}>
            <summary>当前基准图 URL</summary>
            <Input
              value={activeImageUrl}
              placeholder="粘贴主图 URL"
              clearable
              onChange={(value) => {
                const url = String(value || '').trim();
                onImageUrlChange?.(url);
                setSession((prev) => (prev ? { ...prev, imageUrl: url } : prev));
                setPlan(null);
                setRun(null);
                setRunResult(null);
                setRunResultsById({});
              }}
            />
          </details>
          <details className="podi-image-edit-agent__debug">
            <summary>调试信息</summary>
            <p>会话：{session ? shortAgentId(session.id) : '未创建'}</p>
            <p>建议：{plan ? shortAgentId(plan.id) : '无'}</p>
            <p>任务：{runId ? shortAgentId(runId) : '无'}</p>
          </details>
        </aside>
      </div>
    </Card>
  );
}
