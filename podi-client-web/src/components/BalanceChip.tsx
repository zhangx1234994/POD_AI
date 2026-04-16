import { WalletIcon, AddCircleIcon } from 'tdesign-icons-react';
import { Link } from 'react-router-dom';

export default function BalanceChip({ balance }: { balance?: number | null }) {
  return (
    <div className="client-balance-chip">
      <div className="client-balance-chip__value">
        <WalletIcon size="16" />
        <span>{typeof balance === 'number' ? balance.toLocaleString() : '--'}</span>
      </div>
      <Link className="client-balance-chip__action" to="/wallet">
        <AddCircleIcon size="14" />
        充值
      </Link>
    </div>
  );
}
