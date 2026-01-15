import { AI_ACTION_METADATA, DEFAULT_AI_ACTION_PARAMETERS } from '@/constants/metadata';
import type { AiActionMetaParameter } from '@/types/metadata';
import { formatters, labelGenerators } from '@/utils/parameterFormatters';

interface ParsedParam {
  label: string;
  value: string;
  key: string;
}

/**
 * 在对象及其常见配置子对象（params / options / config）中查找指定 key 的值
 */
export const findConfigValue = (obj: any, key: string): any => {
  if (!obj) return undefined;
  if (obj[key] !== undefined) return obj[key];
  if (obj.params?.[key] !== undefined) return obj.params[key];
  if (obj.options?.[key] !== undefined) return obj.options[key];
  if (obj.config?.[key] !== undefined) return obj.config[key];
  return undefined;
};

/**
 * 格式化参数值
 */
export const formatParameterValue = (value: any, config: AiActionMetaParameter, params?: any): string => {
  if (value === undefined || value === null) return '无';
  
  // 转换为字符串处理
  let stringValue = String(value);
  
  // 特殊处理scale参数，提取数字部分（如"2x" -> "2"）
  if (config.key === 'scale' && typeof value === 'string') {
    const numericMatch = stringValue.match(/^\d+/);
    if (numericMatch) {
      stringValue = numericMatch[0];
    }
  }
  
  // 特殊处理aux_imageList参数，显示参考图数量
  if (config.key === 'aux_imageList') {
    if (Array.isArray(value)) {
      if (value.length === 0) return '无';
      // 显示参考图数量和文件名
      const filenames = value.map((item: any) => item.filename || '参考图').join('、');
      return `${value.length}张: ${filenames}`;
    }
    return '无';
  }
  
  // 使用配置的格式化函数或从 formatters 表中查找（字段名：formatter）
  if (config.formatter) {
    if (typeof config.formatter === 'function') return config.formatter(value, params);
    if (typeof config.formatter === 'string') {
      const fn = formatters[config.formatter];
      if (fn) return fn(value, params);
    }
  }
  
  // 使用值映射
  if (config.valueMap) {
    // 先尝试精确匹配
    if (config.valueMap[stringValue]) {
      return config.valueMap[stringValue];
    }
    // 尝试匹配数字部分
    const numericMatch = stringValue.match(/^\d+/);
    if (numericMatch && config.valueMap[numericMatch[0]]) {
      return config.valueMap[numericMatch[0]];
    }
  }
  
  // 数组格式化
  if (Array.isArray(value)) {
    if (value.length === 0) return '无';
    return value.join(', ');
  }
  
  // 对象格式化
  if (typeof value === 'object') {
    try {
      // 尝试将对象转换为可读字符串
      const str = JSON.stringify(value);
      if (str.length > 50) {
        return `${str.substring(0, 50)}...`;
      }
      return str;
    } catch {
      return '对象';
    }
  }
  
  // 基本类型直接转换
  return String(value);
};

/**
 * 解析参数配置
 */
export const getParameterConfig = (action: string): AiActionMetaParameter[] => {
  const mapping = AI_ACTION_METADATA[action];
  if (mapping) {
    return mapping.parameters;
  }
  return [];
};

/**
 * 解析并格式化参数
 */
export const parseParameters = (params: any): ParsedParam[] => {
  if (!params) return [];
  
  const parsed: ParsedParam[] = [];
  
  // 获取action类型
  const action = findConfigValue(params, 'action');
  
  // 获取该action的参数配置
  let parameterConfigs = getParameterConfig(action);
  
  // 合并默认参数配置
  parameterConfigs = [...parameterConfigs, ...DEFAULT_AI_ACTION_PARAMETERS];
  
  // 预处理：提取width和height值，用于生成size参数
  const width = findConfigValue(params, 'width');
  const height = findConfigValue(params, 'height');
  
  // 处理参数
  for (const config of parameterConfigs) {
    // 跳过不可见参数
    let isVisible = true;
    if (typeof config.visible === 'function') {
      isVisible = config.visible(params);
    } else if (config.visible === false) {
      isVisible = false;
    }

    if (!isVisible) continue;
    
    let value = findConfigValue(params, config.key);
    
    // 特殊处理size参数：使用width和height组合生成
    if (config.key === 'size' && width && height) {
      value = `${width}x${height}`;
    }
    
    if (value === undefined && config.key !== 'action') continue;
    
    // 格式化参数值
    const displayValue = formatParameterValue(value, config, params);
    
    // 解析动态label：优先使用 label 函数，其次使用 labelGenerator 在 labelGenerators 中查找
    let label: string;
    if (typeof config.label === 'function') {
      label = config.label(params);
    } else if (config.labelGenerator && labelGenerators[config.labelGenerator]) {
      label = labelGenerators[config.labelGenerator](params);
    } else {
      label = String(config.label);
    }
    
    parsed.push({
      label: label,
      value: displayValue,
      key: config.key
    });
  }
  
  // 按优先级排序
  parsed.sort((a, b) => {
    const configA = parameterConfigs.find(c => c.key === a.key);
    const configB = parameterConfigs.find(c => c.key === b.key);
    
    const priorityA = configA?.priority || 999;
    const priorityB = configB?.priority || 999;
    
    return priorityA - priorityB;
  });
  
  return parsed;
};

/**
 * 获取action的中文名称
 */
export const getActionDisplayName = (action: string): string => {
  const mapping = AI_ACTION_METADATA[action];
  return mapping?.name || action;
};

export default {
  findConfigValue,
  formatParameterValue,
  getParameterConfig,
  parseParameters,
  getActionDisplayName,
};