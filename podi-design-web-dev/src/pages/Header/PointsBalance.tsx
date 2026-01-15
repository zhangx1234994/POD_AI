import React, { useEffect, useRef, useState } from 'react';
import { usePoints } from '@/contexts/PointsContext';
import { POINTS_ADDITION_ANIMATION_MS, POINTS_DEDUCTION_ANIMATION_MS, POINTS_MIDNIGHT_GRANT_ANIMATION_MS } from '@/constants/points';

export const PointsBalance: React.FC = () => {
  const { pointsStatistics, deductionAnimation, additionAnimation, midnightGrantAnimation } = usePoints();
  const [displayedPoints, setDisplayedPoints] = useState<number>(Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0));
  const animRef = useRef<{ raf?: number; start?: number } | null>(null);
  // flashColor: 'red' | 'green' | null
  const [flashColor, setFlashColor] = useState<string | null>(null);
  const [floatAmount, setFloatAmount] = useState<number | null>(null);
  const [floatKey, setFloatKey] = useState<number | null>(null);
  const [floatSign, setFloatSign] = useState<'+' | '-' | null>(null);
  // 临时积分闪光触发键，用于重新触发 CSS 动画
  const [tempFlashKey, setTempFlashKey] = useState<number | null>(null);

  // 当 pointsStatistics 变化时（且没有动画进行），同步显示的积分值
  useEffect(() => {
    const base = Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0);
    setDisplayedPoints(base);
  }, [pointsStatistics?.totalPoints, pointsStatistics?.total]);

  // 当 deductionAnimation / additionAnimation 被设置时，运行对应动画
  useEffect(() => {
    const anim = deductionAnimation ?? additionAnimation;
    if (!anim) return;
    const isAddition = !!additionAnimation;
    const { from, to, amount, id } = anim;
    if (animRef.current?.raf) cancelAnimationFrame(animRef.current.raf);
    const duration = isAddition ? POINTS_ADDITION_ANIMATION_MS : POINTS_DEDUCTION_ANIMATION_MS;
    const startTime = performance.now();
    animRef.current = { start: startTime };

    // 设置闪烁颜色与浮动提示符号
    setFlashColor(isAddition ? 'green' : 'red');
    setFloatAmount(amount);
    setFloatKey(id);
    setFloatSign(isAddition ? '+' : '-');

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      // 使用 cubic ease-out 缓动
      const eased = 1 - Math.pow(1 - t, 3);
      const current = Math.round(from + (to - from) * eased);
      setDisplayedPoints(current);
      if (t < 1) {
        animRef.current!.raf = requestAnimationFrame(tick);
      } else {
        // 动画结束：停止闪烁并在动画结束后清除浮动提示
        setTimeout(() => setFlashColor(null), duration);
        setTimeout(() => {
          setFloatKey(null);
          setFloatAmount(null);
          setFloatSign(null);
        }, duration);
      }
    };

    animRef.current.raf = requestAnimationFrame(tick);

    return () => {
      if (animRef.current?.raf) cancelAnimationFrame(animRef.current.raf);
      animRef.current = null;
    };
  }, [deductionAnimation, additionAnimation]);

  // 当午夜临时积分特效激活时，触发更平滑的临时积分闪光动效（用于 CSS 动画重置）
  useEffect(() => {
    if (midnightGrantAnimation?.active) {
      setTempFlashKey(midnightGrantAnimation.id ?? Date.now());
      // 保持动画状态，与横幅显示时长一致后清理
      const timer = setTimeout(() => setTempFlashKey(null), POINTS_MIDNIGHT_GRANT_ANIMATION_MS);
      return () => clearTimeout(timer);
    }
    // 若 midGrant 不存在，则清理
    setTempFlashKey(null);
  }, [midnightGrantAnimation?.id, midnightGrantAnimation?.active]);

  return (
    <div className="w-full text-sm relative overflow-hidden">
      {!midnightGrantAnimation && (
        <span className={`inline-block ${flashColor === 'red' ? 'points-flash' : ''} ${flashColor === 'green' ? 'points-flash-green' : ''}`}>{displayedPoints}</span>
      )}
      {midnightGrantAnimation && (
        <span className={`points-temp-flash ${tempFlashKey ? 'animate' : ''}`}>{pointsStatistics?.tempPoints ?? pointsStatistics?.temp ?? 0}</span>
      )}
      {floatKey !== null && floatAmount !== null && floatSign === '-' && (
        <span className="points-deduction-float">-{floatAmount}</span>
      )}
      {floatKey !== null && floatAmount !== null && floatSign === '+' && (
        <span className="points-addition-float">+{floatAmount}</span>
      )}
    </div>
  );
};

export default PointsBalance;
