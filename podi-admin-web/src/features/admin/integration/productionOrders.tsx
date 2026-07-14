import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Select, Space, Table, Tag, Typography } from 'tdesign-react';

import type { ProductionFulfillmentOrder } from '../../../types/admin';
import { adminApi } from '../../../services/adminApi';

const statusLabel: Record<string, string> = {
  awaiting_payment: '待支付',
  supplier_pending: '自动提交中',
  supplier_retry: '供应链待重试',
  ops_review: '供应链待重试',
  submitted_to_supplier: '已推送待核对',
  producing: '生产中',
  quality_check: '质检中',
  shipped: '已发货',
  delivered: '已签收',
  completed: '已完成',
};

const statusTheme = (status: string): 'success' | 'warning' | 'danger' | 'default' => {
  if (['submitted_to_supplier', 'producing', 'quality_check', 'shipped', 'delivered', 'completed'].includes(status)) return 'success';
  if (['awaiting_payment', 'supplier_pending', 'supplier_retry', 'ops_review'].includes(status)) return 'warning';
  return 'default';
};

const supplierStatusLabel = (value?: string | null) => value || '等待供应商回传';

export function ProductionOrdersPanel({ formatDateTime }: { formatDateTime: (value?: string | null) => string }) {
  const [orders, setOrders] = useState<ProductionFulfillmentOrder[]>([]);
  const [status, setStatus] = useState('all');
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      setOrders(await adminApi.listProductionFulfillmentOrders(status));
    } catch (err) {
      setError(err instanceof Error ? err.message : '生产订单读取失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [status]);

  const counts = useMemo(() => ({
    pendingPayment: orders.filter((order) => order.status === 'awaiting_payment').length,
    supplierRetry: orders.filter((order) => ['supplier_pending', 'supplier_retry', 'ops_review'].includes(order.status)).length,
    supplier: orders.filter((order) => ['submitted_to_supplier', 'producing', 'quality_check', 'shipped'].includes(order.status)).length,
  }), [orders]);

  const runAction = async (order: ProductionFulfillmentOrder, action: 'pay' | 'submit' | 'sync') => {
    const labels = {
      pay: '确认这是受控测试订单，并将其标记为已支付？正式支付接入后，此操作将由支付回调替代。',
      submit: '确认重试把这个已支付订单提交到蜂鸟？',
      sync: '从蜂鸟同步订单状态、效果图和物流信息？',
    };
    if (!window.confirm(labels[action])) return;
    setActionId(order.id);
    setError(null);
    try {
      if (action === 'pay') await adminApi.markProductionOrderPaidForTest(order.id, `controlled-test-${Date.now()}`);
      if (action === 'submit') await adminApi.submitProductionOrderToFengniao(order.id);
      if (action === 'sync') await adminApi.syncProductionOrderFromFengniao(order.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '订单操作失败');
    } finally {
      setActionId(null);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        theme="info"
        message="履约顺序：用户在 AI创品 完成支付 -> 平台自动推送蜂鸟创建待确认订单 -> 运营比对两边数据 -> 在蜂鸟后台确认生产、选择物流并支付供应链。本站后台用于对账、同步和异常重试；“测试代付”仅用于内测验收。"
      />
      {error ? <Alert theme="error" message={error} /> : null}
      <Space align="center" style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space>
          <Tag theme="warning" variant="light">待支付 {counts.pendingPayment}</Tag>
          <Tag theme="warning" variant="light">待供应链重试 {counts.supplierRetry}</Tag>
          <Tag theme="success" variant="light">蜂鸟已接收 {counts.supplier}</Tag>
        </Space>
        <Space>
          <Select
            value={status}
            style={{ width: 180 }}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '待支付', value: 'awaiting_payment' },
              { label: '自动提交中', value: 'supplier_pending' },
              { label: '供应链待重试', value: 'supplier_retry' },
              { label: '已推送待核对', value: 'submitted_to_supplier' },
              { label: '生产中', value: 'producing' },
              { label: '已发货', value: 'shipped' },
            ]}
            onChange={(value) => setStatus(String(value))}
          />
          <Button variant="outline" loading={loading} onClick={() => void refresh()}>刷新</Button>
        </Space>
      </Space>
      <Card bordered title="订单核对表">
        <Table
          rowKey="id"
          data={orders}
          loading={loading}
          columns={[
            {
              colKey: 'orderNo',
              title: '平台订单',
              minWidth: 190,
              cell: ({ row }: { row: ProductionFulfillmentOrder }) => (
                <Space direction="vertical" size={2}>
                  <Typography.Text strong>{row.orderNo}</Typography.Text>
                  <Typography.Text theme="secondary">{formatDateTime(row.createdAt)}</Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'items',
              title: '商品与生产文件',
              minWidth: 280,
              cell: ({ row }: { row: ProductionFulfillmentOrder }) => (
                <Space direction="vertical" size={4}>
                  {row.items.map((item) => (
                    <Space key={item.id} size={6} breakLine>
                      <Typography.Text>{item.productName} · {item.sizeCode} · {item.colorCode} · {item.quantity} 件</Typography.Text>
                      <Tag theme={item.preflight?.passed === true ? 'success' : 'danger'} variant="light">
                        {item.preflight?.passed === true ? '预检通过' : '预检未通过'}
                      </Tag>
                      <a href={item.productionAssetUrl} target="_blank" rel="noreferrer">生产图</a>
                    </Space>
                  ))}
                </Space>
              ),
            },
            {
              colKey: 'status',
              title: '平台状态',
              minWidth: 130,
              cell: ({ row }: { row: ProductionFulfillmentOrder }) => (
                <Space direction="vertical" size={4}>
                  <Tag theme={statusTheme(row.status)} variant="light">{statusLabel[row.status] || row.status}</Tag>
                  <Typography.Text theme="secondary">支付：{row.paymentStatus === 'paid' ? '已支付' : '待支付'}</Typography.Text>
                </Space>
              ),
            },
            {
              colKey: 'supplier',
              title: '蜂鸟回传',
              minWidth: 230,
              cell: ({ row }: { row: ProductionFulfillmentOrder }) => (
                <Space direction="vertical" size={3}>
                  <Typography.Text>{row.supplierOrderId || '未推送'}</Typography.Text>
                  <Typography.Text theme="secondary">{supplierStatusLabel(row.supplierStatus)}</Typography.Text>
                  {row.supplierEffectImageUrls.length ? (
                    <a href={row.supplierEffectImageUrls[0]} target="_blank" rel="noreferrer">查看供应商效果图</a>
                  ) : (
                    <Typography.Text theme="secondary">效果图待回传</Typography.Text>
                  )}
                </Space>
              ),
            },
            {
              colKey: 'actions',
              title: '操作',
              width: 300,
              fixed: 'right',
              cell: ({ row }: { row: ProductionFulfillmentOrder }) => (
                <Space breakLine>
                  {row.status === 'awaiting_payment' ? (
                    <Button size="small" theme="warning" loading={actionId === row.id} onClick={() => void runAction(row, 'pay')}>测试代付</Button>
                  ) : null}
                  {['supplier_pending', 'supplier_retry', 'ops_review'].includes(row.status) ? (
                    <Button size="small" theme="primary" loading={actionId === row.id} onClick={() => void runAction(row, 'submit')}>重试推送蜂鸟</Button>
                  ) : null}
                  {['submitted_to_supplier', 'producing', 'quality_check', 'shipped'].includes(row.status) ? (
                    <Button size="small" variant="outline" loading={actionId === row.id} onClick={() => void runAction(row, 'sync')}>同步蜂鸟回传</Button>
                  ) : null}
                </Space>
              ),
            },
          ]}
          empty={<Typography.Text theme="secondary">暂无真实生产订单。</Typography.Text>}
        />
      </Card>
    </Space>
  );
}
