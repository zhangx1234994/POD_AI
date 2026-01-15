import { useEffect, useState } from 'react';

/**
 * 读取 localStorage 中的 platform 值，并提供是否为嵌入第三方平台的布尔标记。
 * 注意：在 SSR 环境下要防守 window 未定义的情况。
 */
export function usePlatform() {
  const [platform, setPlatform] = useState<string | null>(null);
  const [isEmbedded, setIsEmbedded] = useState<boolean>(false);

  useEffect(() => {
    try {
      const raw = typeof window !== 'undefined' ? window.localStorage.getItem('platform') : null;
      // 将获取到的值转换为字符串（若为 null 则转为空字符串），然后判断
      const p = raw != null ? String(raw) : '';
      setPlatform(p || null);
      // isEmbedded 定义为：有值且不等于 '1'
      setIsEmbedded(p !== '' && p !== '1');
    } catch (e) {
      setPlatform(null);
      setIsEmbedded(false);
    }
  }, []);

  return { platform, isEmbedded };
}

export default usePlatform;
