import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { adminApi } from '../../../services/adminApi';
import type {
  BillingInvoiceRequestListResponse,
  BillingMonthlySettlementListResponse,
  BillingMonthlySettlementResponse,
  BillingNotificationConfigResponse,
  BillingOverviewResponse,
  BillingUserDetailResponse,
  MonthlySettlementCollectionNotificationListResponse,
  PackageAlertNotificationListResponse,
  PackageGrantPayload,
  PackagePurchaseOrderCreatePayload,
  PackagePurchaseOrderListResponse,
} from '../../../types/admin';

interface BillingActionsParams {
  billingBusinessKey: string;
  billingClientId: string;
  billingDetail: BillingUserDetailResponse | null;
  billingMonth: string;
  billingSelectedUserId: string;
  billingTenantId: string;
  billingWindowDays: number;
  downloadBlob: (blob: Blob, filename: string) => void;
  extractErrorMessage: (error: unknown) => string;
  setBillingDetail: Dispatch<SetStateAction<BillingUserDetailResponse | null>>;
  setBillingError: Dispatch<SetStateAction<string | null>>;
  setBillingExporting: Dispatch<SetStateAction<boolean>>;
  setBillingInvoiceRequests: Dispatch<SetStateAction<BillingInvoiceRequestListResponse | null>>;
  setBillingLoading: Dispatch<SetStateAction<boolean>>;
  setBillingMonthlyCollectionNotifications: Dispatch<
    SetStateAction<MonthlySettlementCollectionNotificationListResponse | null>
  >;
  setBillingMonthlySettlement: Dispatch<SetStateAction<BillingMonthlySettlementResponse | null>>;
  setBillingMonthlySettlementRecords: Dispatch<SetStateAction<BillingMonthlySettlementListResponse | null>>;
  setBillingNotificationConfig: Dispatch<SetStateAction<BillingNotificationConfigResponse | null>>;
  setBillingOverview: Dispatch<SetStateAction<BillingOverviewResponse | null>>;
  setBillingPackageAlertNotifications: Dispatch<SetStateAction<PackageAlertNotificationListResponse | null>>;
  setBillingPackagePurchaseOrders: Dispatch<SetStateAction<PackagePurchaseOrderListResponse | null>>;
  setBillingSelectedUserId: Dispatch<SetStateAction<string>>;
}

export const useBillingActions = ({
  billingBusinessKey,
  billingClientId,
  billingDetail,
  billingMonth,
  billingSelectedUserId,
  billingTenantId,
  billingWindowDays,
  downloadBlob,
  extractErrorMessage,
  setBillingDetail,
  setBillingError,
  setBillingExporting,
  setBillingInvoiceRequests,
  setBillingLoading,
  setBillingMonthlyCollectionNotifications,
  setBillingMonthlySettlement,
  setBillingMonthlySettlementRecords,
  setBillingNotificationConfig,
  setBillingOverview,
  setBillingPackageAlertNotifications,
  setBillingPackagePurchaseOrders,
  setBillingSelectedUserId,
}: BillingActionsParams) => {
  const refreshBillingUserDetail = useCallback(
    async (userId = billingSelectedUserId) => {
      const normalizedUserId = String(userId || '').trim();
      if (!normalizedUserId) {
        setBillingDetail(null);
        return;
      }
      setBillingLoading(true);
      setBillingError(null);
      try {
        const detail = await adminApi.getBillingUserDetail(normalizedUserId, {
          month: billingMonth,
          windowDays: billingWindowDays,
          businessKey: billingBusinessKey,
          pageSize: 20,
        });
        setBillingSelectedUserId(normalizedUserId);
        setBillingDetail(detail);
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '用户账单明细加载失败');
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingBusinessKey,
      billingMonth,
      billingSelectedUserId,
      billingWindowDays,
      extractErrorMessage,
      setBillingDetail,
      setBillingError,
      setBillingLoading,
      setBillingSelectedUserId,
    ],
  );

  const refreshBillingOverview = useCallback(async () => {
    setBillingLoading(true);
    setBillingError(null);
    try {
      const billingQuery = {
        month: billingMonth,
        windowDays: billingWindowDays,
        tenantId: billingTenantId,
        clientId: billingClientId,
        businessKey: billingBusinessKey,
        limit: 100,
      };
      const [
        overview,
        monthlySettlement,
        monthlySettlementRecords,
        packageAlertNotifications,
        monthlyCollectionNotifications,
        notificationConfig,
        packagePurchaseOrders,
        invoiceRequests,
      ] = await Promise.all([
        adminApi.getBillingOverview({
          ...billingQuery,
          issueLimit: 20,
          packageAlertLimit: 20,
        }),
        adminApi.getBillingMonthlySettlement({ ...billingQuery, limit: 200 }),
        adminApi.listBillingMonthlySettlements({ ...billingQuery, limit: 100 }),
        adminApi.listBillingPackageAlertNotifications(20),
        adminApi.listBillingMonthlyCollectionNotifications(20),
        adminApi.getBillingNotificationConfig(),
        adminApi.listPackagePurchaseOrders({ businessKey: billingBusinessKey, limit: 50 }),
        adminApi.listBillingInvoiceRequests({ businessKey: billingBusinessKey, limit: 50 }),
      ]);
      setBillingOverview(overview);
      setBillingMonthlySettlement(monthlySettlement);
      setBillingMonthlySettlementRecords(monthlySettlementRecords);
      setBillingPackageAlertNotifications(packageAlertNotifications);
      setBillingMonthlyCollectionNotifications(monthlyCollectionNotifications);
      setBillingNotificationConfig(notificationConfig);
      setBillingPackagePurchaseOrders(packagePurchaseOrders);
      setBillingInvoiceRequests(invoiceRequests);
      const nextUserId =
        (billingSelectedUserId && overview.items.some((item) => item.user.id === billingSelectedUserId)
          ? billingSelectedUserId
          : overview.items[0]?.user.id) || '';
      setBillingSelectedUserId(nextUserId);
      if (nextUserId) {
        const detail = await adminApi.getBillingUserDetail(nextUserId, {
          month: billingMonth,
          windowDays: billingWindowDays,
          businessKey: billingBusinessKey,
          pageSize: 20,
        });
        setBillingDetail(detail);
      } else {
        setBillingDetail(null);
      }
    } catch (error) {
      setBillingError(extractErrorMessage(error) || '账单费用数据加载失败');
    } finally {
      setBillingLoading(false);
    }
  }, [
    billingBusinessKey,
    billingClientId,
    billingMonth,
    billingSelectedUserId,
    billingTenantId,
    billingWindowDays,
    extractErrorMessage,
    setBillingDetail,
    setBillingError,
    setBillingInvoiceRequests,
    setBillingLoading,
    setBillingMonthlyCollectionNotifications,
    setBillingMonthlySettlement,
    setBillingMonthlySettlementRecords,
    setBillingNotificationConfig,
    setBillingOverview,
    setBillingPackageAlertNotifications,
    setBillingPackagePurchaseOrders,
    setBillingSelectedUserId,
  ]);

  const exportBillingUserLedger = useCallback(async () => {
    const userId = billingSelectedUserId || billingDetail?.user.id;
    if (!userId) {
      setBillingError('请先选择一个用户，再导出流水。');
      return;
    }
    setBillingExporting(true);
    setBillingError(null);
    try {
      const blob = await adminApi.exportBillingUserLedger(userId, billingMonth, { businessKey: billingBusinessKey });
      const user = billingDetail?.user.username || userId;
      downloadBlob(blob, `billing-ledger-${user}-${billingMonth}.csv`);
    } catch (error) {
      setBillingError(extractErrorMessage(error) || '账单流水导出失败');
    } finally {
      setBillingExporting(false);
    }
  }, [
    billingBusinessKey,
    billingDetail,
    billingMonth,
    billingSelectedUserId,
    downloadBlob,
    extractErrorMessage,
    setBillingError,
    setBillingExporting,
  ]);

  const grantBillingPackage = useCallback(
    async (payload: PackageGrantPayload) => {
      const userId = billingSelectedUserId || billingDetail?.user.id;
      if (!userId) {
        setBillingError('请先选择一个用户，再发放套餐。');
        return;
      }
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.grantBillingPackage(userId, payload);
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '套餐发放失败，请检查套餐标识、额度和到期时间。');
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingDetail,
      billingSelectedUserId,
      extractErrorMessage,
      refreshBillingOverview,
      setBillingError,
      setBillingLoading,
    ],
  );

  const createPackagePurchaseOrder = useCallback(
    async (payload: PackagePurchaseOrderCreatePayload) => {
      const userId = billingSelectedUserId || billingDetail?.user.id;
      if (!userId) {
        setBillingError('请先选择一个用户，再创建购买订单。');
        return;
      }
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.createPackagePurchaseOrder({ ...payload, userId });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '套餐购买订单创建失败，请检查用户、套餐、额度和金额。');
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingDetail,
      billingSelectedUserId,
      extractErrorMessage,
      refreshBillingOverview,
      setBillingError,
      setBillingLoading,
    ],
  );

  const markPackagePurchaseOrderPaid = useCallback(
    async (orderId: string) => {
      const normalizedId = String(orderId || '').trim();
      if (!normalizedId) return;
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.updatePackagePurchaseOrder(normalizedId, {
          status: 'paid',
          paymentReference: `manual-paid-${billingMonth}`,
          note: '管理端手动确认付款并入账套餐',
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '套餐购买订单付款确认失败。');
      } finally {
        setBillingLoading(false);
      }
    },
    [billingMonth, extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  const createBillingInvoiceRequest = useCallback(
    async (orderId: string, title: string, taxNo?: string | null, email?: string | null) => {
      const normalizedOrderId = String(orderId || '').trim();
      const normalizedTitle = String(title || '').trim();
      if (!normalizedOrderId) return;
      if (!normalizedTitle) {
        setBillingError('请先填写发票抬头。');
        return;
      }
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.createBillingInvoiceRequest({
          relatedOrderType: 'package_purchase_order',
          relatedOrderId: normalizedOrderId,
          invoiceTitle: normalizedTitle,
          taxNo: String(taxNo || '').trim() || null,
          deliveryEmail: String(email || '').trim() || null,
          invoiceType: 'ordinary',
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '发票申请创建失败，请确认订单已付款并填写发票抬头。');
      } finally {
        setBillingLoading(false);
      }
    },
    [extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  const markBillingInvoiceRequestIssued = useCallback(
    async (invoiceRequestId: string) => {
      const normalizedId = String(invoiceRequestId || '').trim();
      if (!normalizedId) return;
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.updateBillingInvoiceRequest(normalizedId, {
          status: 'issued',
          invoiceNo: `manual-invoice-${billingMonth}-${normalizedId.slice(-8)}`,
          note: '管理端手动标记已开票',
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '标记开票失败，请检查发票状态。');
      } finally {
        setBillingLoading(false);
      }
    },
    [billingMonth, extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  const issueBillingMonthlySettlement = useCallback(
    async (tenantId?: string | null, clientId?: string | null) => {
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.issueBillingMonthlySettlement({
          month: billingMonth,
          windowDays: billingWindowDays,
          tenantId: tenantId || null,
          clientId: clientId || null,
          businessKey: billingBusinessKey === 'all' ? null : billingBusinessKey,
          note: '管理端手动生成月结单',
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '月结单生成失败，请先处理异常扣费后再试。');
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingBusinessKey,
      billingMonth,
      billingWindowDays,
      extractErrorMessage,
      refreshBillingOverview,
      setBillingError,
      setBillingLoading,
    ],
  );

  const markBillingMonthlySettlementPaid = useCallback(
    async (settlementId: string) => {
      const normalizedId = String(settlementId || '').trim();
      if (!normalizedId) return;
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.updateBillingMonthlySettlement(normalizedId, {
          status: 'paid',
          paymentReference: `manual-paid-${billingMonth}`,
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '月结单标记付款失败。');
      } finally {
        setBillingLoading(false);
      }
    },
    [billingMonth, extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  const runBillingPackageAlertNotification = useCallback(
    async (send: boolean, notificationTemplate?: string) => {
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.runBillingPackageAlertNotification({
          tenantId: billingTenantId || null,
          clientId: billingClientId || null,
          businessKey: billingBusinessKey === 'all' ? null : billingBusinessKey,
          expiringDays: 14,
          includeLowBalance: true,
          send,
          webhookFormat: 'generic',
          notificationTemplate: notificationTemplate || (send ? 'client_followup' : 'ops_digest'),
          note: send ? '管理端手动发送套餐预警' : '管理端手动生成套餐预警记录',
          limit: 500,
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || (send ? '套餐预警通知发送失败。' : '套餐预警记录生成失败。'));
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingBusinessKey,
      billingClientId,
      billingTenantId,
      extractErrorMessage,
      refreshBillingOverview,
      setBillingError,
      setBillingLoading,
    ],
  );

  const runBillingMonthlyCollectionNotification = useCallback(
    async (send: boolean, notificationTemplate?: string) => {
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.runBillingMonthlyCollectionNotification({
          month: billingMonth,
          tenantId: billingTenantId || null,
          clientId: billingClientId || null,
          businessKey: billingBusinessKey === 'all' ? null : billingBusinessKey,
          minCollectionLevel: 'remind',
          send,
          webhookFormat: 'generic',
          notificationTemplate: notificationTemplate || (send ? 'finance_collection' : 'ops_digest'),
          note: send ? '管理端手动发送月结催收通知' : '管理端手动生成月结催收记录',
          limit: 200,
        });
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || (send ? '月结催收通知发送失败。' : '月结催收记录生成失败。'));
      } finally {
        setBillingLoading(false);
      }
    },
    [
      billingBusinessKey,
      billingClientId,
      billingMonth,
      billingTenantId,
      extractErrorMessage,
      refreshBillingOverview,
      setBillingError,
      setBillingLoading,
    ],
  );

  const saveBillingNotificationConfig = useCallback(
    async (
      channels: Array<{
        key: string;
        enabled: boolean;
        webhookUrl?: string | null;
        webhookFormat?: string | null;
      }>,
    ) => {
      setBillingLoading(true);
      setBillingError(null);
      try {
        const response = await adminApi.updateBillingNotificationConfig({ channels });
        setBillingNotificationConfig(response);
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '通知渠道配置保存失败。');
      } finally {
        setBillingLoading(false);
      }
    },
    [extractErrorMessage, setBillingError, setBillingLoading, setBillingNotificationConfig],
  );

  const retryBillingIssue = useCallback(
    async (runId: string) => {
      const normalizedRunId = String(runId || '').trim();
      if (!normalizedRunId) return;
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.retryBusinessRunBilling(normalizedRunId);
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '扣费重试失败，请先确认余额、定价和任务状态。');
      } finally {
        setBillingLoading(false);
      }
    },
    [extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  const refundBillingIssue = useCallback(
    async (runId: string) => {
      const normalizedRunId = String(runId || '').trim();
      if (!normalizedRunId) return;
      setBillingLoading(true);
      setBillingError(null);
      try {
        await adminApi.refundBusinessRunBilling(normalizedRunId);
        await refreshBillingOverview();
      } catch (error) {
        setBillingError(extractErrorMessage(error) || '退回扣费失败，请先确认任务状态和历史扣费记录。');
      } finally {
        setBillingLoading(false);
      }
    },
    [extractErrorMessage, refreshBillingOverview, setBillingError, setBillingLoading],
  );

  return {
    createBillingInvoiceRequest,
    createPackagePurchaseOrder,
    exportBillingUserLedger,
    grantBillingPackage,
    issueBillingMonthlySettlement,
    markBillingInvoiceRequestIssued,
    markBillingMonthlySettlementPaid,
    markPackagePurchaseOrderPaid,
    refreshBillingOverview,
    refreshBillingUserDetail,
    refundBillingIssue,
    retryBillingIssue,
    runBillingMonthlyCollectionNotification,
    runBillingPackageAlertNotification,
    saveBillingNotificationConfig,
  };
};
