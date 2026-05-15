export const providerOptions = [
  { value: 'baidu', label: '百度智能云' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'aliyun', label: '阿里云' },
  { value: 'volcengine', label: '火山引擎' },
  { value: 'kie', label: 'KIE 中转' },
  { value: 'comfyui', label: 'ComfyUI 流程' },
  { value: 'coze', label: 'Coze Studio' },
];

export const abilityTypeOptions = [
  { value: 'api', label: '第三方模型/API' },
  { value: 'comfyui', label: '生图工作流' },
  { value: 'workflow', label: '中台编排' },
  { value: 'tool', label: '平台工具' },
];

export const categoryOptions = [
  { value: 'pattern_extract', label: '花纹提取' },
  { value: 'fission', label: '图裂变' },
  { value: 'image_fission', label: '图裂变（旧分类）' },
  { value: 'outpaint', label: '扩图' },
  { value: 'seamless_pattern', label: '连续图' },
  { value: 'cutout', label: '抠图' },
  { value: 'image_composition', label: '图像融合' },
  { value: 'image_enhancement', label: '图像增强' },
  { value: 'vision_analysis', label: '图像理解' },
  { value: 'text_prompt', label: '文本与提示词' },
  { value: 'video_generation', label: '生视频' },
  { value: 'platform_tools', label: '平台工具' },
  { value: 'image_generation', label: '图片生成（旧分类）' },
  { value: 'image_process', label: '图像处理（旧分类）' },
  { value: 'vision_language', label: '图像理解（旧分类）' },
  { value: 'text_generation', label: '文字生成（旧分类）' },
  { value: 'video', label: '视频处理（旧分类）' },
  { value: 'speech', label: '语音/音频（旧分类）' },
  { value: 'utilities', label: '平台工具（旧分类）' },
  { value: 'other', label: '其他（待归类）' },
];

export const statusOptions = [
  { value: 'inactive', label: '未启用' },
  { value: 'active', label: '启用' },
  { value: 'deprecated', label: '下线' },
];

export const businessRunStatusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'succeeded', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
];

export const businessRunBillingStatusOptions = [
  { value: 'all', label: '全部计费' },
  { value: 'billable', label: '可计费' },
  { value: 'unpriced', label: '待定价' },
  { value: 'no_charge', label: '不计费' },
  { value: 'billing_pending', label: '未完成' },
];

export const businessRunCallbackStatusOptions = [
  { value: 'all', label: '全部回调' },
  { value: 'success', label: '回调成功' },
  { value: 'failed', label: '回调失败' },
  { value: 'running', label: '回调中' },
  { value: 'none', label: '未配置回调' },
];

export const businessRunIssueCategoryOptions = [
  { value: 'all', label: '全部问题' },
  { value: 'executor', label: '执行节点问题' },
  { value: 'output', label: '结果回填问题' },
  { value: 'callback', label: '业务回调问题' },
  { value: 'billing', label: '计费扣减问题' },
  { value: 'parameter', label: '参数问题' },
  { value: 'version', label: '版本/路由问题' },
  { value: 'none', label: '暂无明显问题' },
];

export const businessUsageWindowOptions = [
  { value: 1, label: '近 1 小时' },
  { value: 24, label: '近 24 小时' },
  { value: 168, label: '近 7 天' },
  { value: 720, label: '近 30 天' },
];

export const comfyModelTypeOptions = [
  { value: 'unet', label: 'UNET' },
  { value: 'clip', label: 'CLIP' },
  { value: 'vae', label: 'VAE' },
  { value: 'controlnet', label: 'ControlNet' },
  { value: 'other', label: '其他' },
];

export const apiKeyStatusOptions = [
  { value: 'active', label: '启用 (active)' },
  { value: 'inactive', label: '停用 (inactive)' },
  { value: 'deprecated', label: '下线 (deprecated)' },
] as const;

export const comfyDesktopReleaseStatusOptions = [
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' },
  { value: 'deprecated', label: '废弃' },
] as const;

export const comfyDesktopUpdateStatusMeta: Record<
  string,
  { theme: 'success' | 'warning' | 'danger' | 'default'; text: string }
> = {
  up_to_date: { theme: 'success', text: '已是最新' },
  update_available: { theme: 'warning', text: '可升级' },
  apply_started: { theme: 'warning', text: '升级已触发' },
  applying: { theme: 'warning', text: '升级中' },
  applied: { theme: 'success', text: '升级完成' },
  apply_failed: { theme: 'danger', text: '升级失败' },
  apply_blocked_running_task: { theme: 'warning', text: '执行中暂缓升级' },
  apply_not_supported: { theme: 'default', text: '当前系统不支持' },
  check_failed: { theme: 'danger', text: '检查失败' },
  no_release: { theme: 'default', text: '暂无可用版本' },
  not_ready: { theme: 'default', text: '尚未接入' },
  disabled: { theme: 'default', text: '自动更新关闭' },
};
