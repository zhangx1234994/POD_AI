/**
 * AI action 单个参数的元数据配置
 */
export interface AiActionMetaParameter {
  label?: string | ((params: any) => string); // 显示名称（可动态）。当使用 `labelGenerator` 时可省略
  key: string;                               // 参数键
  type: 'string' | 'number' | 'array' | 'object' | 'boolean';
  valueMap?: Record<string, string>;         // 值映射（如 '2' → '2倍'）
  visible?: boolean | ((params: any) => boolean); // 是否在 UI 中显示（可为函数动态计算）
  formatter?: ((value: any, params?: any) => string) | string; // 格式化函数或格式化函数的 key（当为 string 时从 `parameterFormatters.formatters` 中查找）
  labelGenerator?: string;                    // 动态 label 的 key，可在 `parameterFormatters.labelGenerators` 中查找
  priority?: number;                         // 显示优先级
}

/**
 * AI action 的元数据（含名称和参数列表）
 */
export interface AiActionMetadata {
  name: string;                            // 中文动作名称
  parameters: AiActionMetaParameter[];     // 参数配置列表
}

export default {} as any;
