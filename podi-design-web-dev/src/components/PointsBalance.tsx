import React, { useEffect, useRef, useState } from 'react';
import { usePoints } from '@/contexts/PointsContext';

const PointsBalance: React.FC = () => {
  const { pointsStatistics, deductionAnimation } = usePoints();
  const [displayedPoints, setDisplayedPoints] = useState<number>(Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0));
  const animRef = useRef<{ raf?: number; start?: number } | null>(null);
  const [isFlashing, setIsFlashing] = useState(false);
  const [floatAmount, setFloatAmount] = useState<number | null>(null);
  const [floatKey, setFloatKey] = useState<number | null>(null);

  // keep displayedPoints in sync when pointsStatistics changes and no animation in progress
  useEffect(() => {
    const base = Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0);
    setDisplayedPoints(base);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pointsStatistics?.totalPoints, pointsStatistics?.total]);

  // Run deduction animation when deductionAnimation is set
  useEffect(() => {
    if (!deductionAnimation) return;
    const { from, to, amount, id } = deductionAnimation;
    if (animRef.current?.raf) cancelAnimationFrame(animRef.current.raf);
    const duration = 2000; // ms (2 seconds)
    const startTime = performance.now();
    animRef.current = { start: startTime };

    // start flash and floating indicator
    setIsFlashing(true);
    setFloatAmount(amount);
    setFloatKey(id);

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      // ease out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const current = Math.round(from + (to - from) * eased);
      setDisplayedPoints(current);
      if (t < 1) {
        animRef.current!.raf = requestAnimationFrame(tick);
      } else {
        // finish
        setTimeout(() => setIsFlashing(false), duration);
        // clear floating indicator after animation
        setTimeout(() => {
          setFloatKey(null);
          setFloatAmount(null);
        }, duration);
      }
    };

    animRef.current.raf = requestAnimationFrame(tick);

    return () => {
      if (animRef.current?.raf) cancelAnimationFrame(animRef.current.raf);
      animRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deductionAnimation]);

  return (
    <div className="w-full text-sm relative overflow-hidden">
      <span className={`inline-block ${isFlashing ? 'points-flash' : ''}`}>{displayedPoints}</span>
      {floatKey !== null && floatAmount !== null && (
        <span className="points-deduction-float">-{floatAmount}</span>
      )}
    </div>
  );
};

export default PointsBalance;
