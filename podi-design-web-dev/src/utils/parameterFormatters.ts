// 本地辅助函数：用于从 params 中读取配置值，支持嵌套键
const getParamValue = (obj: any, key: string): any => {
  if (!obj) return undefined;
  if (obj[key] !== undefined) return obj[key];
  if (obj.params?.[key] !== undefined) return obj.params[key];
  if (obj.options?.[key] !== undefined) return obj.options[key];
  if (obj.config?.[key] !== undefined) return obj.config[key];
  return undefined;
};

/**
 * 格式化函数集合
 * 用于将参数原始值转换为用户友好的显示字符串
 * 键名需与参数元数据（metadata）中的 formatter 引用名一致
 */
export const formatters: Record<string, (value: any, params?: any) => string> = {
  /**
   * 格式化图像尺寸显示
   * 优先使用原始尺寸（当 resolution='original' 时），
   * 否则回退到 width/height 字段
   */
  formatImageSize: (v: any, params: any) => {
    const resolution = getParamValue(params, 'resolution');
    if (resolution === 'original') {
      const oSize = getParamValue(params, 'o_size');
      if (oSize?.width && oSize?.height) {
        return `${oSize.width}px × ${oSize.height}px`;
      }
    }
    const width = getParamValue(params, 'width');
    const height = getParamValue(params, 'height');
    if (width && height) {
      return `${width}px × ${height}px`;
    }
    return String(v); // 最终回退到原始值
  },

  /**
   * 格式化图像扩展（扩图）边缘值
   * 根据 extend_type 字段决定单位：
   * - 若存在 extend_type（比例模式）→ 显示为百分比（如 "20%"）
   * - 否则 → 显示为像素（如 "100px"）
   */
  formatExtendValue: (v: any, params?: any) => {
    if (getParamValue(params, 'extend_type')) {
      return `${v}%`;
    }
    return `${v}px`; // 注意：统一为 "100px"，避免 "100 px"（空格不一致）
  },
};

/**
 * 通用扩展方向标签生成器
 * 根据方向（left/top/right/bottom）和 extend_type 动态生成中文标签
 */
const generateExtendLabel = (direction: string, params: any): string => {
  // 方向映射表：将英文方向转为中文前缀
  const directionMap: Record<string, string> = {
    left: '左侧',
    top: '顶部',
    right: '右侧',
    bottom: '底部',
  };
  const prefix = directionMap[direction] || direction;
  // 若处于比例扩展模式，显示“比例”，否则显示普通“扩展”
  return params?.extend_type ? `${prefix}扩展比例` : `${prefix}扩展`;
};

/**
 * 动态标签生成函数集合
 * 用于在 UI 中根据参数上下文动态显示字段标签
 * 键名需与参数元数据（metadata）中的 labelGenerator 引用名一致
 */
export const labelGenerators: Record<string, (params: any) => string> = {
  extendLeft: (params) => generateExtendLabel('left', params),
  extendTop: (params) => generateExtendLabel('top', params),
  extendRight: (params) => generateExtendLabel('right', params),
  extendBottom: (params) => generateExtendLabel('bottom', params),
};

/** 默认导出，便于在其他模块统一引入 */
export default {
  formatters,
  labelGenerators,
};
