import { Link } from 'react-router-dom';

export default function ClientPromoStrip() {
  return (
    <div className="client-promo-strip">
      <div className="client-promo-strip__copy">
        <span>Phase 1</span>
        <strong>当前优先级：首任务成功、结果回看、资产沉淀、低余额转化</strong>
      </div>
      <Link to="/wallet">查看套餐与余额策略</Link>
    </div>
  );
}
