import type { Ability, JsonRecord } from '../../../types/admin';

type TagTheme = 'success' | 'warning' | 'danger' | 'primary' | 'default';

export type AbilityOutputKind = 'image' | 'video' | 'text' | 'structured' | 'asset';

export type AbilityOutputProfile = {
  kind: AbilityOutputKind;
  label: string;
  detail: string;
  theme: TagTheme;
  inputTags: string[];
  outputTags: string[];
};

const normalize = (value?: unknown) => String(value || '').trim().toLowerCase();

const getMetadata = (ability?: Ability | null): JsonRecord => {
  const metadata = ability?.metadata;
  return metadata && typeof metadata === 'object' && !Array.isArray(metadata) ? metadata : {};
};

const getSchemaFields = (ability?: Ability | null): JsonRecord[] => {
  const schema = ability?.input_schema;
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return [];
  const fields = (schema as JsonRecord).fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter((item): item is JsonRecord => Boolean(item) && typeof item === 'object' && !Array.isArray(item));
};

const schemaHasField = (ability: Ability, keywords: string[]) => {
  const lowered = keywords.map((item) => item.toLowerCase());
  return getSchemaFields(ability).some((field) => {
    const key = normalize(field.key);
    const label = normalize(field.label);
    const description = normalize(field.description);
    return lowered.some((keyword) => key.includes(keyword) || label.includes(keyword) || description.includes(keyword));
  });
};

const metadataValue = (metadata: JsonRecord, keys: string[]) => {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
};

const inferOutputKind = (ability: Ability): AbilityOutputKind => {
  const metadata = getMetadata(ability);
  const explicit = normalize(
    metadataValue(metadata, ['outputType', 'output_type', 'outputKind', 'output_kind', 'resultType', 'result_type']),
  );
  const apiType = normalize(metadata.api_type);
  const category = normalize(ability.category);

  if (explicit.includes('video')) return 'video';
  if (explicit.includes('image')) return 'image';
  if (explicit.includes('text')) return 'text';
  if (explicit.includes('json') || explicit.includes('structured') || explicit.includes('vl')) return 'structured';

  if (apiType.includes('video') || category.includes('video')) return 'video';
  if (apiType.includes('vision') || apiType === 'vl' || category.includes('vision')) return 'structured';
  if (apiType.includes('chat') || apiType.includes('text') || category.includes('text')) return 'text';
  if (apiType.includes('image') || category.includes('image')) return 'image';
  return 'asset';
};

export const resolveAbilityOutputProfile = (ability: Ability): AbilityOutputProfile => {
  const metadata = getMetadata(ability);
  const apiType = normalize(metadata.api_type);
  const kind = inferOutputKind(ability);
  const requiresImage =
    Boolean(metadata.requires_image_input) ||
    Boolean(metadata.requiresImageInput) ||
    schemaHasField(ability, ['image_url', 'image_urls', 'input_url', 'input_urls', 'mask_url']);
  const supportsMultipleImages =
    Boolean(metadata.supports_multiple_images) ||
    Boolean(metadata.supportsMultipleImages) ||
    schemaHasField(ability, ['image_urls', 'input_urls']);
  const supportsMask = Boolean(metadata.supports_mask) || Boolean(metadata.supportsMask) || schemaHasField(ability, ['mask_url', 'mask']);
  const supportsPrompt = schemaHasField(ability, ['prompt', '提示词']);

  const inputTags = [
    requiresImage ? '需图片' : '',
    supportsMultipleImages ? '支持多图' : '',
    supportsMask ? '支持蒙版' : '',
    supportsPrompt ? '有提示词' : '',
  ].filter(Boolean);

  const outputTags = [
    kind === 'image' ? '输出图片' : '',
    kind === 'video' ? '输出视频' : '',
    kind === 'text' ? '输出文字' : '',
    kind === 'structured' ? '输出结构化结果' : '',
    kind === 'asset' ? '输出资源' : '',
  ].filter(Boolean);

  if (kind === 'video') {
    return {
      kind,
      label: '视频能力',
      detail: apiType ? `接口类型：${apiType}` : '生成或处理视频结果',
      theme: 'warning',
      inputTags,
      outputTags,
    };
  }
  if (kind === 'text') {
    return {
      kind,
      label: '文字能力',
      detail: apiType ? `接口类型：${apiType}` : '生成或增强文字内容',
      theme: 'primary',
      inputTags,
      outputTags,
    };
  }
  if (kind === 'structured') {
    return {
      kind,
      label: '图像理解',
      detail: apiType ? `接口类型：${apiType}` : '返回图片描述、标签或结构化判断',
      theme: 'success',
      inputTags,
      outputTags,
    };
  }
  if (kind === 'image') {
    return {
      kind,
      label: '图片能力',
      detail: apiType ? `接口类型：${apiType}` : '生成、编辑或处理图片结果',
      theme: 'success',
      inputTags,
      outputTags,
    };
  }
  return {
    kind,
    label: '资源能力',
    detail: apiType ? `接口类型：${apiType}` : '返回文件、链接或其他资源',
    theme: 'default',
    inputTags,
    outputTags,
  };
};
