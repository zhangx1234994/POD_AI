import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import pointsAPI from '@/services/pointsAPI';
import { POINTS_MIDNIGHT_GRANT_ANIMATION_MS, POINTS_DEDUCTION_ANIMATION_MS, POINTS_ADDITION_ANIMATION_MS, DEFAULT_POINTS_PAGE_SIZE } from '@/constants/points';
import { useAuth } from '@/contexts/AuthContext';
import { WALLET_POINTS_EVENT } from '@/constants/events';

interface PointsContextValue {
  // 扣减积分的动画信息（空表示未激活）
  deductionAnimation: { active: boolean; from: number; to: number; amount: number; id: number } | null;
  // 触发扣减动画（amount 为正数）
  startDeductionAnimation: (amount: number) => void;
  // 增加积分的动画信息（空表示未激活）
  additionAnimation: { active: boolean; from: number; to: number; amount: number; id: number } | null;
  // 触发增加动画（amount 为正数）
  startAdditionAnimation: (amount: number) => void;
  // 临时积分（午夜发放）的特效信息（不同于普通加分动画）
  midnightGrantAnimation: { active: boolean; amount: number; id: number; grantAt?: string } | null;
  // 触发临时积分特效（会进行排队，实际播放由可见性与首次交互决定）
  startMidnightGrantAnimation: (amount: number, grantAt?: string) => void;
  // 提交后短时横幅提示（顶部居中显示）
  submissionToast: { active: boolean; amount: number; remaining: number; id: number } | null;
  pointsStatistics: any | null;
  transactionsList: any[];
  total: number;
  page: number;
  totalPages: number;
  pageSize: number;
  changeType: string;
  pointsType: string;
  taskId: string;
  loadingStatistics: boolean;
  loadingTransactions: boolean;
  setChangeType: (v: string) => void;
  setPointsType: (v: string) => void;
  setTaskId: (v: string) => void;
  setTransactionsList: (l: any[]) => void;
  setPage: (p: number) => void;
  fetchPointsStatistics: (override?: any) => Promise<void>;
  fetchTransactions: (opts?: any) => Promise<void>;
  refresh: () => Promise<void>;
}

const PointsContext = createContext<PointsContextValue | undefined>(undefined);

export const PointsProvider: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [pointsStatistics, setPointsStatistics] = useState<any | null>(null);
  const [transactionsList, setTransactionsList] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(DEFAULT_POINTS_PAGE_SIZE);
  const [changeType, setChangeType] = useState<string>('all');
  const [pointsType, setPointsType] = useState<string>('all');
  const [taskId, setTaskId] = useState<string>('');
  const [loadingStatistics, setLoadingStatistics] = useState(false);
  const [loadingTransactions, setLoadingTransactions] = useState(false);
  const [deductionAnimation, setDeductionAnimation] = useState<{ active: boolean; from: number; to: number; amount: number; id: number } | null>(null);
  const [additionAnimation, setAdditionAnimation] = useState<{ active: boolean; from: number; to: number; amount: number; id: number } | null>(null);
  const [midnightGrantAnimation, setMidnightGrantAnimation] = useState<{ active: boolean; amount: number; id: number; grantAt?: string } | null>(null);
  const [submissionToast, setSubmissionToast] = useState<{ active: boolean; amount: number; remaining: number; id: number } | null>(null);
  const [pendingMidnightGrant, setPendingMidnightGrant] = useState<{ amount: number; grantAt?: string } | null>(null);
  const [hasUserInteracted, setHasUserInteracted] = useState(false);

  const fetchPointsStatistics = useCallback(async () => {
    if (!user?.id) return;
    setLoadingStatistics(true);
    try {
      const response = await pointsAPI.getPointsStatistics({ userId: user.id });
      const res = response?.data ?? response;
      const data = res?.data ?? res;
      setPointsStatistics(data ?? null);
      return data ?? null;
    } catch (err) {
      console.error('fetchPointsStatistics error', err);
    } finally {
      setLoadingStatistics(false);
    }
  }, [user?.id]);

  
  const fetchTransactions = useCallback(async (opts: any = {}) => {
    if (!user?.id) return;
    setLoadingTransactions(true);
    try {
      // 优先使用传入的 opts 覆盖本地状态，否则使用 context 中保存的 filter 状态
      // 这允许调用方临时覆盖分页或过滤条件而不改变全局状态
      const pageToFetch = opts.current ?? page;
      const sizeToFetch = opts.size ?? pageSize;
      const changeTypeToUse = opts.changeType ?? changeType;
      const pointsTypeToUse = opts.pointsType ?? pointsType;
      const taskIdToUse = opts.taskId ?? taskId;

      // 构造查询字符串：始终包含用户 ID、页码和页大小
      // 仅在对应过滤条件存在且不是 'all' 或空字符串时才追加到查询中
      // 注意对参数值进行 encodeURIComponent 以保证 URL 安全
      // include multiple common page param names to maximize backend compatibility
      let queryParams = `userId=${encodeURIComponent(String(user.id))}`;
      queryParams += `&current=${encodeURIComponent(String(pageToFetch))}`;
      queryParams += `&page=${encodeURIComponent(String(pageToFetch))}`;
      queryParams += `&size=${encodeURIComponent(String(sizeToFetch))}`;
      if (changeTypeToUse && changeTypeToUse !== 'all') {
        // changeType 表示积分变动类型（如增加/减少）
        queryParams += `&changeType=${encodeURIComponent(String(changeTypeToUse))}`;
      }
      if (pointsTypeToUse && pointsTypeToUse !== 'all') {
        // pointsType 表示积分来源/类型
        queryParams += `&pointsType=${encodeURIComponent(String(pointsTypeToUse))}`;
      }
      if (taskIdToUse && String(taskIdToUse).trim() !== '') {
        // taskId 用于按任务 ID 搜索相关的积分记录
        queryParams += `&taskId=${encodeURIComponent(String(taskIdToUse).trim())}`;
      }

      // 调用 pointsAPI：传入的为 query 字符串（或完整 path 取决于 pointsAPI 实现）
      // 保持与后端兼容：如果没有任何过滤条件，则只会按 userId 查询该用户的所有积分记录
      const res = await pointsAPI.getPointsTransactions(queryParams);
      const data = res?.data ?? res;
      // backend returns { data: { records: [], total, current, size, pages } } or direct
      const records = data.data?.records ?? data.records ?? data.items ?? [];
      const totalCount = data.data?.total ?? data.total ?? 0;
      // backend may return current page and total pages
      const serverCurrent = data.data?.current ?? data.current ?? data.page ?? data.data?.page ?? data.pageNo ?? data.data?.pageNo ?? pageToFetch;
      const serverPages = data.data?.pages ?? data.pages ?? data.data?.totalPages ?? data.totalPages ?? data.data?.pagesTotal ?? Math.max(1, Math.ceil(totalCount / sizeToFetch));

      setTransactionsList(records);
      setTotal(totalCount);
      setPage(Number(serverCurrent));
      setTotalPages(Number(serverPages));
    } catch (err) {
      console.error('fetchTransactions error', err);
    } finally {
      setLoadingTransactions(false);
    }
  }, [user?.id, page, pageSize, changeType, pointsType, taskId]);

  useEffect(() => {
    if (user?.id) {
      fetchPointsStatistics();
      fetchTransactions({ current: 1 });
    } else {
      setPointsStatistics(null);
    }
  }, [user?.id, fetchPointsStatistics, fetchTransactions]);

  // 在统计数据更新后，检测是否存在今日临时积分发放（由后端返回字段指示），并触发一次性特效
  useEffect(() => {
    const stats = pointsStatistics?.data ?? pointsStatistics ?? null;
    if (!stats) return;
    const temp = stats?.tempPoints ?? stats?.temp ?? stats?.currentTempPoints ?? stats?.current_temp_points ?? 0;
    const grantAt = stats?.lastTemporaryGrantAt ?? stats?.last_temporary_grant_at ?? stats?.lastTemporaryGrantAtDate ?? null;
    if (!grantAt) return;
    if (!temp || Number(temp) <= 0) return;

    try {
      const key = `podi-midnight-grant-shown:${String(grantAt)}`;
      if (!localStorage.getItem(key)) {
        startMidnightGrantAnimation(Number(temp), String(grantAt));
        try { localStorage.setItem(key, String(Date.now())); } catch (e) { }
      }
    } catch (e) {
      // ignore localStorage errors
    }
  }, [pointsStatistics]);

  useEffect(() => {
    if (!user?.id) {
      setTransactionsList([]);
    }
  }, [user?.id]);

  useEffect(() => {
    const handler = () => {
      fetchPointsStatistics();
    };
    window.addEventListener(WALLET_POINTS_EVENT, handler);
    return () => {
      window.removeEventListener(WALLET_POINTS_EVENT, handler);
    };
  }, [fetchPointsStatistics]);

  const refresh = async () => {
    await fetchPointsStatistics();
    await fetchTransactions({ current: page });
  };

  // 触发扣减动画：记录起始值与目标值，动画会在前端展示数值滚动与下沉提示
  const startDeductionAnimation = (amount: number) => {
    if (!amount || amount <= 0) return;
    const from = Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0);
    const to = Math.max(0, from - Number(amount));
    const id = Date.now();
    setDeductionAnimation({ active: true, from, to, amount: Number(amount), id });
    // 同时在 Header 顶部显示一次性提交横幅：消耗与剩余
    try {
      setSubmissionToast({ active: true, amount: Number(amount), remaining: to, id });
      setTimeout(() => setSubmissionToast(null), POINTS_DEDUCTION_ANIMATION_MS);
    } catch (e) {
      // ignore
    }
    // 动画持续时间与横幅保持一致，超时后清理状态
    setTimeout(() => setDeductionAnimation(null), POINTS_DEDUCTION_ANIMATION_MS);
  };

  // 触发增加动画：记录起始值与目标值，前端会展示绿色上浮提示与数值滚动
  const startAdditionAnimation = (amount: number) => {
    if (!amount || amount <= 0) return;
    const from = Number(pointsStatistics?.totalPoints ?? pointsStatistics?.total ?? 0);
    const to = from + Number(amount);
    const id = Date.now();
    setAdditionAnimation({ active: true, from, to, amount: Number(amount), id });
    // 与横幅时长保持一致
    setTimeout(() => setAdditionAnimation(null), POINTS_ADDITION_ANIMATION_MS);
  };

  // 触发临时积分（午夜发放）特效：此调用会将发放排入队列，实际播放由页面可见性与用户首次交互共同决定
  const startMidnightGrantAnimation = (amount: number, grantAt?: string) => {
    if (!amount || amount <= 0) return;
    setPendingMidnightGrant({ amount: Number(amount), grantAt });
  };

  // 当页面可见且用户已进行首次交互时，播放排队中的临时积分特效
  useEffect(() => {
    if (!pendingMidnightGrant) return;
    if (document.visibilityState === 'visible' && hasUserInteracted) {
      const { amount, grantAt } = pendingMidnightGrant;
      const id = Date.now();
      setMidnightGrantAnimation({ active: true, amount: Number(amount), id, grantAt });
      setPendingMidnightGrant(null);
      setTimeout(() => setMidnightGrantAnimation(null), POINTS_MIDNIGHT_GRANT_ANIMATION_MS);
    }
  }, [pendingMidnightGrant, hasUserInteracted]);

  useEffect(() => {
    if (hasUserInteracted) {
      // still attach visibilitychange to possibly play pending grant when tab becomes visible
    }
    const onFirstInteraction = () => setHasUserInteracted(true);
    const onVisibilityChange = () => {
      // 当标签页从不可见变为可见时，如果已经有过首次交互且存在排队的临时积分，则立即播放
      if (document.visibilityState === 'visible' && pendingMidnightGrant && hasUserInteracted) {
        const { amount, grantAt } = pendingMidnightGrant;
        const id = Date.now();
        setMidnightGrantAnimation({ active: true, amount: Number(amount), id, grantAt });
        setPendingMidnightGrant(null);
        setTimeout(() => setMidnightGrantAnimation(null), POINTS_MIDNIGHT_GRANT_ANIMATION_MS);
      }
    };
    window.addEventListener('click', onFirstInteraction, { once: true });
    window.addEventListener('keydown', onFirstInteraction, { once: true });
    window.addEventListener('mousemove', onFirstInteraction, { once: true });
    window.addEventListener('touchstart', onFirstInteraction, { once: true });
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.removeEventListener('click', onFirstInteraction as any);
      window.removeEventListener('keydown', onFirstInteraction as any);
      window.removeEventListener('mousemove', onFirstInteraction as any);
      window.removeEventListener('touchstart', onFirstInteraction as any);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [hasUserInteracted, pendingMidnightGrant]);

  const value: PointsContextValue = {
    deductionAnimation,
    additionAnimation,
    midnightGrantAnimation,
    submissionToast,
    transactionsList,
    pointsStatistics,
    total,
    page,
    totalPages,
    pageSize,
    changeType,
    pointsType,
    taskId,
    loadingStatistics,
    loadingTransactions,
    setChangeType: (v: string) => setChangeType(v),
    setPointsType: (v: string) => setPointsType(v),
    setTaskId: (v: string) => setTaskId(v),
    setTransactionsList: (l: any[]) => setTransactionsList(l),
    setPage: (p: number) => setPage(p),
    fetchPointsStatistics,
    fetchTransactions,
    refresh,
    startDeductionAnimation,
    startAdditionAnimation,
    startMidnightGrantAnimation,
  };

  return <PointsContext.Provider value={value}>{children}</PointsContext.Provider>;
};

export const usePoints = () => {
  const ctx = useContext(PointsContext);
  if (!ctx) throw new Error('usePoints must be used within PointsProvider');
  return ctx;
};

export default PointsContext;
