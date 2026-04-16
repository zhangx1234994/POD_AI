import { useEffect, useMemo, useState } from 'react';
import { Button } from 'tdesign-react';
import { ImageIcon, RefreshIcon } from 'tdesign-icons-react';
import type { AbilityInfo } from '../../types/api';
import type { UploadResult } from '../../types/media';
import type { ShellMode } from '../../types/workspace';
import type { RuntimeToolConfig } from '../../config/toolConfigs';
import { getToolPresentation } from '../../config/toolPresentation';
import type { ToolItem } from '../../types';
import type { ToolField } from '../../config/toolConfigs';
import {
  getAbilityExpectedOutput,
  getAbilityFormIntro,
  getAbilityPresentationName,
  getAbilityPresentationSummary,
} from '../../utils/abilityPresentation';

type RecentCandidate = {
  image: string;
  title: string;
};

export default function WorkspaceFormPanel({
  tool,
  mode,
  runtime,
  ability,
  abilitiesLoading,
  abilitiesError,
  isAuthenticated,
  uploads,
  uploading,
  formValues,
  submitting,
  inputRef,
  estimatedPoints,
  balance,
  recentCandidates,
  canSubmit,
  onSelectFiles,
  onUseRecentAsset,
  onChangeField,
  onReset,
  onSubmit,
}: {
  tool: ToolItem;
  mode: ShellMode;
  runtime?: RuntimeToolConfig;
  ability: AbilityInfo | null;
  abilitiesLoading: boolean;
  abilitiesError: string | null;
  isAuthenticated: boolean;
  uploads: UploadResult[];
  uploading: boolean;
  formValues: Record<string, string>;
  submitting: boolean;
  inputRef: React.RefObject<HTMLInputElement>;
  estimatedPoints: number | null;
  balance: number | null;
  recentCandidates: RecentCandidate[];
  canSubmit: boolean;
  onSelectFiles: (files: FileList | null) => void | Promise<void>;
  onUseRecentAsset: (asset: RecentCandidate) => void;
  onChangeField: (key: string, value: string) => void;
  onReset: () => void;
  onSubmit: () => void | Promise<void>;
}) {
  const [showAdvancedFields, setShowAdvancedFields] = useState(false);
  const modeLabel = mode === 'design' ? '设计创作' : mode === 'shoot' ? '商拍出图' : '交付处理';
  const promptField = runtime?.fields.find((field) => field.key === 'prompt');
  const presentation = getToolPresentation(tool.key, mode);
  const displayTitle = getAbilityPresentationName(ability) || tool.title;
  const displaySummary = getAbilityPresentationSummary(ability) || tool.description;
  const abilityFields = useMemo(() => {
    const fields = ability?.inputSchema?.fields;
    if (!Array.isArray(fields)) return new Map<string, NonNullable<AbilityInfo['inputSchema']>['fields'][number]>();
    return new Map(fields.filter((field) => field?.name).map((field) => [String(field.name), field]));
  }, [ability?.inputSchema?.fields]);
  const resolvedFields = useMemo(() => {
    const fields = runtime?.fields || [];
    return fields.map((field) => {
      const abilityField = abilityFields.get(field.key);
      return {
        ...field,
        label: abilityField?.label || field.label,
        placeholder: abilityField?.placeholder || field.placeholder,
        description: abilityField?.description || field.description,
        advanced: typeof abilityField?.advanced === 'boolean' ? abilityField.advanced : field.advanced,
      } as ToolField;
    });
  }, [abilityFields, runtime?.fields]);
  const promptFieldResolved = resolvedFields.find((field) => field.key === 'prompt');
  const modeTags = presentation.workflowTags || [];
  const quickRecipes = presentation.quickRecipes || [];
  const signalCards = [
    {
      label: '工作类型',
      value: modeLabel,
    },
    {
      label: '输入方式',
      value: runtime?.requiresImage ? `${runtime.imageSlots || 1} 张参考图` : '文字描述',
    },
    {
      label: '结果节奏',
      value: runtime?.invokeMode === 'task' ? '稍后回看结果' : '提交后直接返回',
    },
  ];
  const previewMosaic = (uploads.length ? uploads.map((item) => ({ image: item.url, title: item.name })) : recentCandidates).slice(0, 3);
  const outputExpectation =
    mode === 'design'
      ? '更适合先出方向，再继续改款、提取图案或做连续纹理。'
      : mode === 'shoot'
        ? '更适合先完成主图或营销图，再继续补细节图和视频素材。'
        : '更适合放在最终交付前，统一做清晰度、尺寸和参数处理。';
  const emptyMosaicCopy = runtime?.requiresImage
    ? {
        title: '先上传一张图，再开始这一步。',
        note: '这里只保留和当前动作相关的输入，不再预塞演示图。',
      }
    : {
        title: '直接填写本次目标，就可以开始。',
        note: '这个动作不依赖参考图，先把意图写清楚，结果会回到右侧。',
      };
  const publicFormIntro = getAbilityFormIntro(ability);
  const publicExpectedOutput = getAbilityExpectedOutput(ability);
  const fieldGroups = useMemo(() => {
    const fields = resolvedFields;
    const textareaFields = fields.filter((field) => field.type === 'textarea');
    const primaryMarked = fields.filter((field) => !field.advanced);
    const compactFields = primaryMarked.filter((field) => field.type !== 'textarea');
    const primaryCompactCount = textareaFields.length ? 2 : Math.min(3, compactFields.length);
    const advancedFields = fields.filter((field) => field.advanced);
    const primaryFields = advancedFields.length
      ? primaryMarked
      : ([...textareaFields, ...compactFields.slice(0, primaryCompactCount)] as ToolField[]);

    return {
      primary: primaryFields,
      advanced: advancedFields.length ? advancedFields : compactFields.slice(primaryCompactCount),
    };
  }, [resolvedFields]);

  useEffect(() => {
    setShowAdvancedFields(false);
  }, [tool.key]);

  const renderField = (field: ToolField) => (
    <label key={field.key} className={`client-field${field.type === 'textarea' ? ' client-field--wide' : ''}`}>
      <span>{field.label}</span>
      {field.description ? <small className="client-field__hint">{field.description}</small> : null}
      {field.type === 'textarea' ? (
        <textarea
          rows={5}
          placeholder={field.placeholder}
          value={formValues[field.key] || ''}
          onChange={(event) => onChangeField(field.key, event.target.value)}
        />
      ) : field.type === 'select' ? (
        <select value={formValues[field.key] || field.options[0]?.value || ''} onChange={(event) => onChangeField(field.key, event.target.value)}>
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={field.type === 'number' ? 'number' : 'text'}
          placeholder={field.placeholder}
          value={formValues[field.key] || ''}
          onChange={(event) => onChangeField(field.key, event.target.value)}
        />
      )}
    </label>
  );

  return (
    <section className="client-panel client-panel--form">
      <div className="client-panel__header">
        <div>
          <p className="client-eyebrow">{tool.subtitle}</p>
          <h3>填写本次输入</h3>
          <p className="client-panel__header-note">{displaySummary}</p>
        </div>
        <div className="client-estimate-card">
          <span>本次创作</span>
          <strong>{displayTitle}</strong>
          <small>{runtime?.invokeMode === 'task' ? '任务会先进入队列，结果稍后回到当前页和任务中心。' : '提交后会直接返回结果，可继续沉淀到资产中心。'}</small>
          <em>{typeof estimatedPoints === 'number' ? `预计消耗 ${estimatedPoints} 点` : '提交前会自动估算积分'}</em>
        </div>
      </div>

      <p className="client-panel__lede">
        {publicFormIntro ||
          (isAuthenticated ? '直接填写本次目标并提交，结果会优先回到当前工作区。' : '现在先看前台流程，登录后就能直接提交真实任务。')}
      </p>

      <div className="client-workspace-brief">
        <div className="client-workspace-brief__signals">
          {signalCards.map((item) => (
            <div key={item.label} className="client-workspace-brief__signal">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
        <div className="client-workspace-brief__story">
          <div className="client-workspace-brief__story-copy">
            <span>怎么开始</span>
            <strong>{presentation.heroTitle || (runtime?.requiresImage ? '先放参考图，再把目标写清楚。' : '先把风格、品类和重点写清楚。')}</strong>
            <p>{presentation.heroNote || publicExpectedOutput || outputExpectation}</p>
            <div className="client-workspace-brief__tag-row">
              {modeTags.map((tag) => (
                <em key={tag}>{tag}</em>
              ))}
            </div>
            {promptFieldResolved && quickRecipes.length ? (
              <div className="client-workspace-brief__recipe-block">
                <div className="client-workspace-brief__recipe-heading">
                  <span>快速带入</span>
                  <strong>先用一条成熟表达把输入写满</strong>
                </div>
                <div className="client-workspace-brief__recipe-row">
                {quickRecipes.map((recipe, index) => (
                  <button key={recipe} type="button" className="client-workspace-brief__recipe" onClick={() => onChangeField(promptFieldResolved.key, recipe)}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>带入这条</strong>
                    <small>{recipe.slice(0, 24)}...</small>
                  </button>
                ))}
                </div>
              </div>
            ) : null}
          </div>
          {previewMosaic.length ? (
            <div className="client-workspace-brief__mosaic">
              {previewMosaic.map((item, index) => (
                <div
                  key={`${item.title}-${index}`}
                  className={`client-workspace-brief__mosaic-card${index === 0 ? ' is-main' : ''}`}
                  style={{ backgroundImage: `url(${item.image})` }}
                />
              ))}
            </div>
          ) : (
            <div className="client-workspace-brief__mosaic-empty">
              <span>当前没有最近素材</span>
              <strong>{emptyMosaicCopy.title}</strong>
              <p>{emptyMosaicCopy.note}</p>
            </div>
          )}
        </div>
      </div>

      {runtime?.note ? <div className="client-callout client-callout--warm">{runtime.note}</div> : null}

      {!runtime ? (
        <div className="client-callout client-callout--warm">
          这个功能页已经先做了正式前台壳层，当前真实创作链路还没补到这里，后续会继续接通。
        </div>
      ) : null}

      {isAuthenticated && abilitiesLoading ? <div className="client-callout">正在同步能力配置，请稍候再提交。</div> : null}
      {isAuthenticated && abilitiesError ? <div className="client-callout client-callout--warm">{abilitiesError}</div> : null}

      {runtime?.requiresImage ? (
        <div className="client-upload-box">
          <div className="client-upload-box__icon">
            <ImageIcon size="22" />
          </div>
          <div>
            <div className="client-upload-box__title">先放入这次创作要用的图片</div>
            <div className="client-upload-box__text">
              {runtime.imageSlots && runtime.imageSlots > 1
                ? `最多支持 ${runtime.imageSlots} 张图，当前已放入 ${uploads.length} 张。`
                : '支持 JPG / PNG / WebP。'}
            </div>
            {uploads.length ? (
              <div className="client-uploaded-list">
                {uploads.map((upload) => (
                  <span key={upload.objectKey}>{upload.name}</span>
                ))}
              </div>
            ) : null}
          </div>
          <div className="client-upload-box__actions">
            <input
              ref={inputRef}
              hidden
              multiple={(runtime.imageSlots || 1) > 1}
              accept="image/png,image/jpeg,image/webp"
              type="file"
              onChange={(event) => void onSelectFiles(event.target.files)}
            />
            <button className="client-soft-button" type="button" onClick={() => inputRef.current?.click()} disabled={uploading}>
              {uploading ? '上传中...' : '添加图片'}
            </button>
            {recentCandidates.length ? (
              <button className="client-soft-button" type="button" onClick={() => onUseRecentAsset(recentCandidates[0])}>
                使用最近素材
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="client-callout">这个功能不需要先放参考图，直接写清楚你的创作目标即可。</div>
      )}

      <div className="client-form-grid">
        {fieldGroups.primary.map((field) => renderField(field))}
      </div>
      {fieldGroups.advanced.length ? (
        <div className="client-advanced-fields">
          <button className="client-soft-button" type="button" onClick={() => setShowAdvancedFields((prev) => !prev)}>
            {showAdvancedFields ? '收起更多参数' : `更多参数 (${fieldGroups.advanced.length})`}
          </button>
          {showAdvancedFields ? <div className="client-form-grid">{fieldGroups.advanced.map((field) => renderField(field))}</div> : null}
        </div>
      ) : null}

      <div className="client-submit-row">
        <div>
          <div className="client-submit-row__hint">提交后结果会回到当前页面，也能在任务中心继续查看。</div>
          <div className="client-submit-row__balance">
            {isAuthenticated ? `当前可用积分 ${typeof balance === 'number' ? balance.toLocaleString() : '--'} 点` : '当前为预览模式，请先登录。'}
          </div>
          {runtime?.requiresImage && !uploads.length ? <div className="client-submit-row__hint">当前还缺少参考图，补一张后再提交。</div> : null}
        </div>
        <div className="client-submit-row__actions">
          <button className="client-soft-button" type="button" onClick={onReset}>
            <RefreshIcon size="16" /> 重置
          </button>
          <Button theme="primary" size="large" loading={submitting} disabled={!canSubmit} onClick={() => void onSubmit()}>
            {mode === 'toolbox' ? '开始处理' : mode === 'shoot' ? '开始生成' : '开始创作'}
          </Button>
        </div>
      </div>
    </section>
  );
}
