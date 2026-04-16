import { useEffect, useState } from 'react';
import { clientApi } from '../services/clientApi';

export function useWalletSnapshot(userId?: string | null) {
  const [balance, setBalance] = useState<number | null>(null);
  const [frozenBalance, setFrozenBalance] = useState<number | null>(null);
  const [grantedToday, setGrantedToday] = useState<number | null>(null);
  const [expense30Days, setExpense30Days] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadWallet() {
      if (!userId) {
        setBalance(null);
        setFrozenBalance(null);
        setGrantedToday(null);
        setExpense30Days(null);
        return;
      }
      try {
        const [wallet, stats, usage] = await Promise.all([
          clientApi.getWalletBalance(userId),
          clientApi.getWalletStatistics(userId),
          clientApi.getWalletUsageSummary(userId),
        ]);
        if (!cancelled) {
          setBalance(wallet.balance);
          setFrozenBalance(wallet.frozenBalance);
          setGrantedToday(stats.grantedToday);
          setExpense30Days(usage.totalExpensePoints);
        }
      } catch {
        if (!cancelled) {
          setBalance(null);
          setFrozenBalance(null);
          setGrantedToday(null);
          setExpense30Days(null);
        }
      }
    }
    void loadWallet();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  return {
    balance,
    frozenBalance,
    grantedToday,
    expense30Days,
    setBalance,
  };
}

