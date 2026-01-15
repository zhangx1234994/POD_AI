import { useCallback, useState } from 'react';
import pointsAPI from '@/services/pointsAPI';
import { useAuth } from '@/contexts/AuthContext';
import { PointsPreviewDialog } from '@/pages/PointsHistory/PointsPreviewDialog';
import { PointsInsufficientDialog } from '@/pages/PointsHistory/PointsInsufficientDialog';
import { usePoints } from '@/contexts/PointsContext';

interface PrecheckOpts {
  action: string;
  imagesCount: number;
  taskId?: string;
  submitFn: () => Promise<any>;
}

export default function usePointsPrecheck() {
  // 中文说明：
  // 这个 hook 用来在提交任务之前进行“积分扣减能力校验”（points-cost）并展示相应的弹窗，
  // 将提交动作包装为两步：先调用 `precheckAndSubmit(opts)` 获取/展示预览或余额不足弹窗，
  // 将提交动作保存为待提交项（`pendingSubmit`），用户在预览弹窗确认后调用 `runPendingSubmit()` 执行实际提交。
  //
  // 核心职责：
  // - precheckAndSubmit(opts)：调用后端的 points-cost 接口，判断积分是否足够：
  //   - 不足时打开 `PointsInsufficientDialog`，不继续提交。
  //   - 足够时打开 `PointsPreviewDialog`，并把 `opts` 保存到 `pendingSubmit`，等待用户确认。
  // - runPendingSubmit()：当用户在预览弹窗确认后执行：
  //   1. 运行传入的 `submitFn()`（实际提交任务）。
  //   2. 提交成功或失败后刷新积分统计 `fetchPointsStatistics()`（尽量避免重复请求），
  //      并尝试检测是否发生退款（backend 返回显式退款信息，或通过对比提交前后积分统计推断）。
  //   3. 当检测到退款时：立即用 `toast.info(...)` 提示用户，并派发 DOM 事件 `points:refund`，
  //      以便页面中监听该事件的组件更新本地任务状态（例如标记已退款）。
  //
  // 设计要点/注意事项：
  // - refund 检测是保守的：优先读取 submitFn 返回或错误体中的退款字段；若没有则通过比较统计数据（提交前后 totalPoints）来推断。
  // - 当需要通过推断退款而触发一次统计刷新时，代码会复用该刷新结果来避免二次请求；
  //   如果已经有显式退款信息，则在提示用户后仍会主动刷新一次统计以保持 UI 与后端一致。
  // - hook 返回一个 `dialogs` JSX 片段，调用方只需把它渲染到组件中即可展示预览/不足弹窗。
  // - 该 hook 假设 `submitFn` 会抛出异常或返回包含后端信息的对象；错误分支中会尽量从错误体或刷新后的统计里提取退款信息。

  const { user } = useAuth();
  const { fetchPointsStatistics, startDeductionAnimation } = usePoints();

  const [previewOpen, setPreviewOpen] = useState(false);
  const [insufficientOpen, setInsufficientOpen] = useState(false);
  const [previewMeta, setPreviewMeta] = useState<{ imagesCount: number; perImageCost: number; currentPoints: number; totalCost?: number } | null>(null);
  const [insufficientMeta, setInsufficientMeta] = useState<{ required: number; current: number; imagesCount: number; perImageCost: number } | null>(null);
  const [pendingSubmit, setPendingSubmit] = useState<PrecheckOpts | null>(null);
  const [loading, setLoading] = useState(false);

  const fallbackSubmit = useCallback(async (opts: PrecheckOpts, reason?: string) => {
    if (!opts) return;
    try {
      await opts.submitFn();
    } catch (error) {
      throw error;
    } finally {
      if (reason) {
        console.warn(reason);
      }
    }
  }, []);

  const precheckAndSubmit = useCallback(async (opts: PrecheckOpts) => {
    if (!user?.id) {
      throw new Error('未登录');
    }
    setLoading(true);
    try {
      const res = await pointsAPI.queryPointsCost(user.id, opts.action, opts.imagesCount);
      const body = res?.data ?? res;
      const data = body?.data ?? body;

      const perImageCost = data?.pointsPerImage ?? 0;
      const totalPointsCost = data?.totalPointsCost ?? (perImageCost * opts.imagesCount);
      const currentTotalPoints = data?.currentTotalPoints ?? ((data?.currentTempPoints ?? 0) + (data?.currentRechargePoints ?? 0));
      const isSufficient = data?.isSufficient ?? false;

      if (!isSufficient) {
        setInsufficientMeta({ required: totalPointsCost, current: currentTotalPoints, imagesCount: opts.imagesCount, perImageCost });
        setInsufficientOpen(true);
        return;
      }

      setPreviewMeta({ imagesCount: opts.imagesCount, perImageCost, currentPoints: currentTotalPoints, totalCost: totalPointsCost });
      setPendingSubmit(opts);
      setPreviewOpen(true);
    } catch (error) {
      console.error('积分校验失败，直接提交任务:', error);
      setLoading(false);
      await fallbackSubmit(opts, 'points precheck failed, submitting directly');
      return;
    } finally {
      setLoading(false);
    }
  }, [user?.id, fallbackSubmit]);

  const runPendingSubmit = useCallback(async () => {
    if (!pendingSubmit) return;
    const { submitFn } = pendingSubmit;
    setPreviewOpen(false);
    setLoading(true);
    try {
      // Call the provided submit function and return its result.
      // This hook's responsibility is only to execute submission and
      // refresh points statistics; 
      const result = await submitFn();

      // Trigger deduction animation (use previewMeta.currentPoints as the amount
      // per product requirement: animate using the `currentTotalPoints` returned
      // by the points-cost query as the amount to deduct visually).
      try {
        const amountToDeduct = previewMeta?.totalCost ?? 0;
        if (amountToDeduct > 0) {
          startDeductionAnimation(amountToDeduct);
        }
      } catch (e) {
        // ignore animation errors
      }

      // Refresh points statistics once to reflect any balance changes.
      try {
        await fetchPointsStatistics();
      } catch (e) {
        // ignore failures to refresh here; polling will reconcile later
      }

      return result;
    } catch (err) {
      throw err;
    } finally {
      setLoading(false);
      setPendingSubmit(null);
    }
  }, [pendingSubmit, fetchPointsStatistics, previewMeta, startDeductionAnimation]);

  const dialogs = (
    <>
      <PointsPreviewDialog
        open={previewOpen}
        onOpenChange={(open: boolean) => setPreviewOpen(open)}
        imagesCount={previewMeta?.imagesCount ?? 0}
        perImageCost={previewMeta?.perImageCost ?? 0}
        currentPoints={previewMeta?.currentPoints ?? 0}
        totalPointsCost={previewMeta?.totalCost ?? 0}
        onConfirm={() => { void runPendingSubmit(); }}
      />

      <PointsInsufficientDialog
        open={insufficientOpen}
        onOpenChange={(open: boolean) => setInsufficientOpen(open)}
        required={insufficientMeta?.required ?? 0}
        current={insufficientMeta?.current ?? 0}
        imagesCount={insufficientMeta?.imagesCount ?? 0}
        perImageCost={insufficientMeta?.perImageCost ?? 0}
        onReduce={() => setInsufficientOpen(false)}
      />
    </>
  );

  return { precheckAndSubmit, dialogs, loading };
}
