export interface SourceOption {
  value: string;
  label: string;
}

/**
 * 构建来源选项列表。
 * 当 isEmbedded 为 true 时会包含第三方平台（SEND）选项。
 */
export function getSourceOptions(isEmbedded: boolean): SourceOption[] {
  const opts: SourceOption[] = [
    { value: 'all', label: '全部来源' },
    { value: 'UPLOAD', label: '本地上传' },
    { value: 'GENERATE', label: '工具生成' },
  ];
  if (isEmbedded) {
    opts.push({ value: 'SEND', label: '第三方平台' });
  }
  return opts;
}

export default getSourceOptions;
