export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonRecord = Record<string, JsonValue>;

export interface Executor {
  id: string;
  name: string;
  type: string;
  base_url?: string;
  status: string;
  weight: number;
  max_concurrency: number;
  health_status?: string;
  last_heartbeat_at?: string;
  tags?: string[];
  config?: JsonRecord;
}

export interface Workflow {
  id: string;
  action: string;
  name: string;
  version?: string;
  type?: string;
  status?: string;
  definition?: JsonRecord;
  metadata?: JsonRecord;
  updated_at?: string;
}

export interface Binding {
  id: string;
  action: string;
  workflow_id: string;
  executor_id: string;
  priority: number;
  enabled: boolean;
}

export interface ApiKey {
  id: string;
  provider: string;
  name: string;
  status: string;
  daily_quota?: number;
  usage_count?: number;
  expire_at?: string;
  key_preview?: string;
  key?: string;
}

export interface BusinessApiKey {
  id: string;
  name: string;
  status: string;
  keyPreview: string;
  tenantId?: string | null;
  clientId?: string | null;
  allowedBusinessKeys: string[];
  usageCount: number;
  expireAt?: string | null;
  metadata?: JsonRecord | null;
  createdAt: string;
  updatedAt: string;
}

export interface BusinessApiKeyListResponse {
  items: BusinessApiKey[];
}

export interface BusinessApiKeyUsageLog {
  id: number;
  apiKeyId?: string | null;
  apiKeyName?: string | null;
  apiKeyPreview?: string | null;
  method: string;
  path: string;
  statusCode?: number | null;
  businessKey?: string | null;
  runId?: string | null;
  requestId?: string | null;
  traceId?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  errorCode?: string | null;
  durationMs?: number | null;
  ipAddress?: string | null;
  userAgent?: string | null;
  createdAt: string;
}

export interface BusinessApiKeyUsageLogListResponse {
  items: BusinessApiKeyUsageLog[];
  total: number;
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  displayName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  createdAt?: string | null;
  lastLoginAt?: string | null;
  adminAudit?: AuthUserAuditItem[];
}

export interface AuthUserAuditItem {
  action?: string | null;
  actorUserId?: string | null;
  actorUsername?: string | null;
  actorRole?: string | null;
  note?: string | null;
  changedFields?: string[];
  before?: JsonRecord | null;
  after?: JsonRecord | null;
  createdAt?: string | null;
}

export type AuthUserUpdatePayload = Partial<
  Pick<AuthUser, 'displayName' | 'role' | 'status' | 'tenantId' | 'clientId'>
> & {
  note?: string | null;
};

export type AuthUserFormState = AuthUserUpdatePayload & {
  userId?: string;
};

export interface AuthSession {
  id: string;
  userId?: string | null;
  username?: string | null;
  email?: string | null;
  displayName?: string | null;
  status: string;
  ipAddress?: string | null;
  userAgent?: string | null;
  expiresAt?: string | null;
  revokedAt?: string | null;
  lastSeenAt?: string | null;
  createdAt?: string | null;
}

export interface InviteCode {
  id: string;
  code: string;
  role: string;
  tenantId?: string | null;
  clientId?: string | null;
  maxUses: number;
  usedCount: number;
  status: string;
  expiresAt?: string | null;
  createdBy?: string | null;
  note?: string | null;
  metadata?: JsonRecord | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface AuthUserListResponse {
  items: AuthUser[];
}

export interface AuthScopeTotals {
  users: number;
  activeUsers: number;
  adminUsers: number;
  clientUsers: number;
  unscopedClientUsers: number;
  activeSessions: number;
  activeInvites: number;
  unscopedActiveInvites: number;
  expiredActiveInvites: number;
}

export interface AuthScopeRoleItem {
  role: string;
  count: number;
  activeCount: number;
}

export interface AuthScopeTenantItem {
  tenantId?: string | null;
  clientId?: string | null;
  userCount: number;
  activeUserCount: number;
  clientUserCount: number;
  activeSessionCount: number;
}

export interface AuthScopeRiskItem {
  key: string;
  title: string;
  severity: string;
  count: number;
  detail: string;
}

export interface AuthScopeChecklistItem {
  key: string;
  title: string;
  passed: boolean;
  detail: string;
  action: string;
}

export interface AuthScopeBusinessApiPolicyItem {
  key: string;
  title: string;
  detail: string;
  enforced: boolean;
}

export interface AuthScopeRoleBoundaryItem {
  key: string;
  title: string;
  principal: string;
  allowed: string;
  blocked: string;
  enforced: boolean;
}

export interface AuthScopeSummaryResponse {
  generatedAt: string;
  releaseReady?: boolean;
  blockingRiskCount?: number;
  warningRiskCount?: number;
  totals: AuthScopeTotals;
  roles: AuthScopeRoleItem[];
  tenants: AuthScopeTenantItem[];
  risks: AuthScopeRiskItem[];
  checklist?: AuthScopeChecklistItem[];
  businessApiPolicy?: AuthScopeBusinessApiPolicyItem[];
  roleBoundary?: AuthScopeRoleBoundaryItem[];
}

export interface BillingUserRead {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  displayName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
}

export interface WalletBalance {
  userId: string;
  balance: number;
  frozenBalance: number;
  currency: string;
}

export interface WalletBill {
  userId: string;
  month: string;
  income: number;
  expense: number;
  net: number;
  count: number;
}

export interface WalletLedgerItem {
  id: string;
  changeType: string;
  points: number;
  beforeBalance: number;
  afterBalance: number;
  taskId?: string | null;
  traceId?: string | null;
  description?: string | null;
  provider?: string | null;
  modelKey?: string | null;
  createdAt?: string | null;
}

export interface WalletLedger {
  userId: string;
  total: number;
  page: number;
  pageSize: number;
  items: WalletLedgerItem[];
}

export interface WalletUsageDailyItem {
  date: string;
  expensePoints: number;
  incomePoints: number;
  count: number;
}

export interface WalletUsageDimensionItem {
  key: string;
  count: number;
  points: number;
}

export interface WalletUsageSummary {
  userId: string;
  windowDays: number;
  totalExpensePoints: number;
  totalIncomePoints: number;
  expenseCount: number;
  incomeCount: number;
  daily: WalletUsageDailyItem[];
  providers: WalletUsageDimensionItem[];
  models: WalletUsageDimensionItem[];
}

export interface WalletCostSnapshotItem {
  date: string;
  provider: string;
  modelKey: string;
  points: number;
  taskId?: string | null;
}

export interface WalletCostSnapshot {
  userId: string;
  provider?: string | null;
  modelKey?: string | null;
  count: number;
  totalPoints: number;
  items: WalletCostSnapshotItem[];
}

export interface PackageBalanceItem {
  id: string;
  userId: string;
  packageKey: string;
  packageName?: string | null;
  businessKey?: string | null;
  totalUnits: number;
  usedUnits: number;
  frozenUnits: number;
  remainingUnits: number;
  unitName: string;
  status: string;
  source?: string | null;
  expiresAt?: string | null;
  createdAt?: string | null;
}

export interface PackageBalanceList {
  userId: string;
  businessKey?: string | null;
  packageKey?: string | null;
  totalRemainingUnits: number;
  items: PackageBalanceItem[];
}

export interface PackageLedgerItem {
  id: string;
  packageBalanceId: string;
  userId: string;
  packageKey: string;
  businessKey?: string | null;
  changeType: string;
  units: number;
  balanceAfter: number;
  taskId?: string | null;
  traceId?: string | null;
  source?: string | null;
  description?: string | null;
  createdAt?: string | null;
}

export interface PackageLedger {
  userId: string;
  businessKey?: string | null;
  packageKey?: string | null;
  total: number;
  page: number;
  pageSize: number;
  items: PackageLedgerItem[];
}

export interface PackageGrantPayload {
  packageKey: string;
  units: number;
  businessKey?: string | null;
  packageName?: string | null;
  unitName?: string | null;
  expiresAt?: string | null;
  traceId?: string | null;
  description?: string | null;
}

export interface PackageGrantResponse {
  transactionId: string;
  ledgerIds: string[];
  packageBalanceId: string;
  userId: string;
  packageKey: string;
  businessKey?: string | null;
  granted: number;
  remainingUnits: number;
  idempotent: boolean;
  traceId?: string | null;
  packageBalances: PackageBalanceList;
  packageLedger: PackageLedger;
}

export interface BillingUserOverview {
  user: BillingUserRead;
  balance: number;
  frozenBalance: number;
  currency: string;
  month: string;
  income: number;
  expense: number;
  net: number;
  billCount: number;
  windowDays: number;
  totalExpensePoints: number;
  totalIncomePoints: number;
  expenseCount: number;
  incomeCount: number;
  packageRemainingUnits: number;
}

export interface BillingIssue {
  id: string;
  runId: string;
  businessKey: string;
  version?: string | null;
  status: string;
  issueType: string;
  issueLabel: string;
  userId?: string | null;
  userName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  billingStatus: string;
  walletStatus?: string | null;
  currency?: string | null;
  costAmount?: number | null;
  quotaUnits?: number | null;
  error?: string | null;
  createdAt?: string | null;
}

export interface BillingPackageAlert {
  id: string;
  alertType: string;
  alertLabel: string;
  userId: string;
  userName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  packageKey: string;
  packageName?: string | null;
  businessKey?: string | null;
  totalUnits: number;
  remainingUnits: number;
  unitName: string;
  expiresAt?: string | null;
  daysUntilExpiry?: number | null;
}

export interface BillingOverviewResponse {
  month: string;
  windowDays: number;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  totalUsers: number;
  totalBalance: number;
  totalFrozenBalance: number;
  totalIncome: number;
  totalExpense: number;
  totalNet: number;
  totalExpensePoints: number;
  totalIncomePoints: number;
  expenseCount: number;
  incomeCount: number;
  totalPackageRemainingUnits: number;
  issueCount: number;
  issues: BillingIssue[];
  packageAlertCount: number;
  packageExpiringSoonCount: number;
  packageLowBalanceCount: number;
  packageAlerts: BillingPackageAlert[];
  items: BillingUserOverview[];
}

export interface BillingCurrencyAmount {
  currency: string;
  amount?: number;
  amountCents?: number;
}

export interface BillingCommercialReportBusinessRow {
  businessKey: string;
  runCount: number;
  succeededRunCount: number;
  billableRunCount: number;
  chargedRunCount: number;
  noChargeRunCount?: number;
  unpricedRunCount: number;
  billingIssueCount: number;
  quotaUnits: number;
  costByCurrency: BillingCurrencyAmount[];
}

export interface BillingCommercialReportResponse {
  month: string;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  generatedAt: string;
  status: string;
  statusLabel: string;
  nextAction: string;
  runCount: number;
  succeededRunCount: number;
  failedRunCount: number;
  billableRunCount: number;
  chargedRunCount: number;
  packageChargedRunCount: number;
  walletChargedRunCount: number;
  noChargeRunCount?: number;
  unpricedRunCount: number;
  billingIssueCount: number;
  quotaUnits: number;
  costByCurrency: BillingCurrencyAmount[];
  paidPackageOrderCount: number;
  pendingPackageOrderCount: number;
  packageSoldUnits: number;
  packageOrderRevenueByCurrency: BillingCurrencyAmount[];
  pendingPackageRevenueByCurrency: BillingCurrencyAmount[];
  activePackageCatalogCount: number;
  businessRows: BillingCommercialReportBusinessRow[];
  riskItems: BillingIssue[];
}

export interface BillingMonthlySettlementItem {
  id: string;
  tenantId?: string | null;
  clientId?: string | null;
  userCount: number;
  totalBalance: number;
  totalFrozenBalance: number;
  totalIncome: number;
  totalExpense: number;
  totalNet: number;
  totalPackageRemainingUnits: number;
  issueCount: number;
  packageAlertCount: number;
  settlementStatus: string;
  settlementLabel: string;
}

export interface BillingMonthlySettlementResponse {
  month: string;
  windowDays: number;
  businessKey?: string | null;
  totalGroups: number;
  issueGroupCount: number;
  packageAlertGroupCount: number;
  items: BillingMonthlySettlementItem[];
}

export interface BillingMonthlySettlementRecord {
  id: string;
  month: string;
  scopeKey: string;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  userCount: number;
  totalBalance: number;
  totalFrozenBalance: number;
  totalIncome: number;
  totalExpense: number;
  totalNet: number;
  totalPackageRemainingUnits: number;
  issueCount: number;
  packageAlertCount: number;
  status: string;
  statusLabel: string;
  daysSinceIssued?: number | null;
  collectionLevel: string;
  collectionAction: string;
  paymentReference?: string | null;
  note?: string | null;
  issuedByUserId?: string | null;
  issuedByUsername?: string | null;
  issuedAt?: string | null;
  paidAt?: string | null;
  cancelledAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface BillingMonthlySettlementListResponse {
  month: string;
  status?: string | null;
  total: number;
  items: BillingMonthlySettlementRecord[];
}

export interface BillingMonthlySettlementIssuePayload {
  month?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  windowDays?: number | null;
  note?: string | null;
}

export interface BillingMonthlySettlementIssueResponse {
  settlement: BillingMonthlySettlementRecord;
  idempotent: boolean;
}

export interface BillingMonthlySettlementUpdatePayload {
  status?: string | null;
  paymentReference?: string | null;
  note?: string | null;
}

export interface PackageAlertNotificationPayload {
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  expiringDays?: number | null;
  includeLowBalance?: boolean;
  send?: boolean;
  webhookFormat?: string | null;
  notificationTemplate?: string | null;
  note?: string | null;
  limit?: number | null;
}

export interface PackageAlertNotificationResponse {
  id: string;
  generatedAt: string;
  sendStatus: string;
  sendDetail?: string | null;
  webhookFormat: string;
  webhookConfigured: boolean;
  notificationTemplate: string;
  nextAction: string;
  alertCount: number;
  expiringSoonCount: number;
  lowBalanceCount: number;
  alerts: BillingPackageAlert[];
}

export interface PackageAlertNotificationRecord {
  id: string;
  notificationType: string;
  sendStatus: string;
  sendDetail?: string | null;
  webhookFormat: string;
  webhookConfigured: boolean;
  notificationTemplate: string;
  nextAction: string;
  alertCount: number;
  expiringSoonCount: number;
  lowBalanceCount: number;
  createdByUserId?: string | null;
  createdByUsername?: string | null;
  sentAt?: string | null;
  createdAt?: string | null;
}

export interface PackageAlertNotificationListResponse {
  total: number;
  items: PackageAlertNotificationRecord[];
}

export interface MonthlySettlementCollectionNotificationPayload {
  month?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  minCollectionLevel?: string | null;
  send?: boolean;
  webhookFormat?: string | null;
  notificationTemplate?: string | null;
  note?: string | null;
  limit?: number | null;
}

export interface MonthlySettlementCollectionNotificationResponse {
  id: string;
  generatedAt: string;
  sendStatus: string;
  sendDetail?: string | null;
  webhookFormat: string;
  webhookConfigured: boolean;
  notificationTemplate: string;
  nextAction: string;
  settlementCount: number;
  remindCount: number;
  followUpCount: number;
  escalateCount: number;
  settlements: BillingMonthlySettlementRecord[];
}

export interface MonthlySettlementCollectionNotificationRecord {
  id: string;
  notificationType: string;
  sendStatus: string;
  sendDetail?: string | null;
  webhookFormat: string;
  webhookConfigured: boolean;
  notificationTemplate: string;
  nextAction: string;
  settlementCount: number;
  remindCount: number;
  followUpCount: number;
  escalateCount: number;
  createdByUserId?: string | null;
  createdByUsername?: string | null;
  sentAt?: string | null;
  createdAt?: string | null;
}

export interface MonthlySettlementCollectionNotificationListResponse {
  total: number;
  items: MonthlySettlementCollectionNotificationRecord[];
}

export interface BillingNotificationChannel {
  key: string;
  displayName: string;
  description?: string | null;
  enabled: boolean;
  configured: boolean;
  webhookUrl?: string | null;
  webhookFormat: string;
  source: string;
}

export interface BillingNotificationConfigResponse {
  channels: BillingNotificationChannel[];
}

export interface BillingNotificationConfigPayload {
  channels: Array<{
    key: string;
    enabled: boolean;
    webhookUrl?: string | null;
    webhookFormat?: string | null;
  }>;
}

export interface PackagePurchaseOrder {
  id: string;
  orderNo: string;
  userId: string;
  userName?: string | null;
  packageKey: string;
  packageName?: string | null;
  businessKey?: string | null;
  units: number;
  unitName: string;
  amountCents: number;
  currency: string;
  channel: string;
  status: string;
  statusLabel: string;
  paymentReference?: string | null;
  transactionId?: string | null;
  failReason?: string | null;
  note?: string | null;
  createdByUserId?: string | null;
  createdByUsername?: string | null;
  paidAt?: string | null;
  cancelledAt?: string | null;
  failedAt?: string | null;
  expiresAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PackageCatalogItem {
  packageKey: string;
  packageName: string;
  businessKey?: string | null;
  description?: string | null;
  units: number;
  unitName: string;
  amountCents: number;
  currency: string;
  validityDays?: number | null;
  status: string;
  sortOrder: number;
  metadata?: JsonRecord | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PackageCatalogListResponse {
  total: number;
  items: PackageCatalogItem[];
}

export interface PackageCatalogPayload {
  packageKey: string;
  packageName: string;
  businessKey?: string | null;
  description?: string | null;
  units: number;
  unitName?: string | null;
  amountCents?: number | null;
  currency?: string | null;
  validityDays?: number | null;
  status?: string | null;
  sortOrder?: number | null;
  metadata?: JsonRecord | null;
}

export interface PackagePurchaseOrderListResponse {
  total: number;
  items: PackagePurchaseOrder[];
}

export interface PackagePurchaseOrderCreatePayload {
  userId: string;
  packageKey: string;
  units: number;
  businessKey?: string | null;
  packageName?: string | null;
  unitName?: string | null;
  amountCents?: number | null;
  currency?: string | null;
  channel?: string | null;
  expiresAt?: string | null;
  note?: string | null;
}

export interface PackagePurchaseOrderUpdatePayload {
  status: string;
  paymentReference?: string | null;
  transactionId?: string | null;
  failReason?: string | null;
  note?: string | null;
}

export interface PackagePurchaseOrderUpdateResponse {
  order: PackagePurchaseOrder;
  packageBalances?: PackageBalanceList | null;
  packageLedger?: PackageLedger | null;
  idempotent: boolean;
}

export interface BillingInvoiceRequest {
  id: string;
  invoiceNo?: string | null;
  relatedOrderType: string;
  relatedOrderId?: string | null;
  userId?: string | null;
  userName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  businessKey?: string | null;
  invoiceTitle: string;
  taxNo?: string | null;
  invoiceType: string;
  amountCents: number;
  currency: string;
  deliveryEmail?: string | null;
  status: string;
  statusLabel: string;
  note?: string | null;
  createdByUserId?: string | null;
  createdByUsername?: string | null;
  issuedByUserId?: string | null;
  issuedByUsername?: string | null;
  issuedAt?: string | null;
  cancelledAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface BillingInvoiceRequestListResponse {
  total: number;
  items: BillingInvoiceRequest[];
}

export interface BillingInvoiceRequestCreatePayload {
  relatedOrderType?: string | null;
  relatedOrderId?: string | null;
  userId?: string | null;
  invoiceTitle: string;
  taxNo?: string | null;
  invoiceType?: string | null;
  amountCents?: number | null;
  currency?: string | null;
  deliveryEmail?: string | null;
  note?: string | null;
}

export interface BillingInvoiceRequestUpdatePayload {
  status: string;
  invoiceNo?: string | null;
  note?: string | null;
}

export interface BillingUserDetailResponse {
  user: BillingUserRead;
  balance: WalletBalance;
  bill: WalletBill;
  usage: WalletUsageSummary;
  ledger: WalletLedger;
  costSnapshots: WalletCostSnapshot;
  packageBalances: PackageBalanceList;
  packageLedger: PackageLedger;
}

export interface AuthSessionListResponse {
  items: AuthSession[];
}

export interface InviteCodeListResponse {
  items: InviteCode[];
}

export type InviteCodeCreatePayload = Partial<Pick<InviteCode, 'role' | 'tenantId' | 'clientId' | 'maxUses' | 'expiresAt' | 'note' | 'metadata'>>;

export type ExecutorFormState = Partial<Omit<Executor, 'config'>> & {
  config?: string;
};

export type WorkflowFormState = Partial<Omit<Workflow, 'definition' | 'metadata'>> & {
  definition?: string;
  metadata?: string;
};

export type BindingFormState = Partial<Binding>;

export type ApiKeyFormState = Partial<ApiKey>;

export type VendorKeyFormState = Partial<VendorKey> & {
  key?: string;
  secret?: string | null;
};

export interface VendorProvider {
  provider: string;
  displayName: string;
  status: string;
  envKeyConfigured?: boolean;
  requiresGlobalEgress: boolean;
  supportedChecks: string[];
  supportedApiTypes: string[];
  executionModes: string[];
}

export interface VendorProviderListResponse {
  service: string;
  baseUrl: string;
  providers: VendorProvider[];
}

export interface VendorEgressCheckResponse {
  success: boolean;
  provider: string;
  check: string;
  url: string;
  httpStatus?: number | null;
  latencyMs?: number | null;
  errorCode?: string | null;
  message?: string | null;
  suggestion?: string | null;
}

export interface VendorKey {
  id: string;
  provider: string;
  alias: string;
  model?: string | null;
  status: string;
  keyPreview: string;
  dailyQuota?: number | null;
  monthlyQuota?: number | null;
  usageCount: number;
  maxConcurrency: number;
  cooldownUntil?: string | null;
  lastError?: string | null;
  lastUsedAt?: string | null;
  metadata?: JsonRecord;
}

export interface VendorKeyListResponse {
  baseUrl: string;
  items: VendorKey[];
}

export interface VendorUsageSummaryItem {
  provider: string;
  model?: string | null;
  status: string;
  count: number;
  errorCode?: string | null;
  avgLatencyMs?: number | null;
  lastSeenAt?: string | null;
}

export interface VendorUsageSummaryResponse {
  baseUrl: string;
  windowHours: number;
  items: VendorUsageSummaryItem[];
}

export interface VendorGovernanceTotals {
  providerCount: number;
  modelCount: number;
  activeModelCount: number;
  abilityCount: number;
  activeAbilityCount: number;
  keyCount: number;
  activeStoredKeyCount: number;
  envKeyProviderCount: number;
  issueCount: number;
}

export interface VendorGovernanceProviderItem {
  provider: string;
  displayName: string;
  providerStatus: string;
  envKeyConfigured: boolean;
  runtimeKeyConfigured: boolean;
  keyCount: number;
  activeStoredKeyCount: number;
  disabledKeyCount: number;
  cooldownKeyCount: number;
  exhaustedKeyCount: number;
  errorKeyCount: number;
  uncheckedKeyCount: number;
  staleKeyCheckCount: number;
  failedKeyCheckCount: number;
  modelCount: number;
  activeModelCount: number;
  abilityCount: number;
  activeAbilityCount: number;
  succeededCalls: number;
  failedCalls: number;
  queuedCalls: number;
  runningCalls: number;
  avgLatencyMs?: number | null;
  lastSeenAt?: string | null;
  requiresGlobalEgress: boolean;
  supportedApiTypes: string[];
  executionModes: string[];
  issues: string[];
  suggestions: string[];
}

export interface VendorGovernanceSummaryResponse {
  baseUrl: string;
  windowHours: number;
  generatedAt: string;
  totals: VendorGovernanceTotals;
  providers: VendorGovernanceProviderItem[];
  issues: string[];
}

export interface VendorModel {
  id?: number | null;
  provider: string;
  model: string;
  displayName: string;
  status: string;
  apiTypes: string[];
  executionModes: string[];
  supportsMask: boolean;
  supportsMultipleImages: boolean;
  supportsVideo: boolean;
  supportsText: boolean;
  requiresGlobalEgress: boolean;
  source: string;
  routePolicy?: JsonRecord | null;
  defaultTaskPolicy?: JsonRecord | null;
  inputSchema?: JsonRecord | null;
  costPolicy?: JsonRecord | null;
  metadata?: JsonRecord;
  latestAcceptance?: JsonRecord | null;
  acceptanceRecords?: JsonRecord[];
  auditRecords?: JsonRecord[];
  releaseGate?: {
    status?: string;
    label?: string;
    canRelease?: boolean;
    acceptancePassed?: boolean;
    runtimeKeyConfigured?: boolean;
    egressVerified?: boolean;
    blockers?: string[];
    warnings?: string[];
    suggestions?: string[];
    primaryIssue?: string | null;
    primaryActionLabel?: string | null;
    primaryAction?: string | null;
    primarySeverity?: string | null;
  } | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface VendorModelListResponse {
  baseUrl: string;
  items: VendorModel[];
}

export interface VendorModelSyncResponse {
  provider: string;
  sourceUrl: string;
  total: number;
  created: number;
  updated: number;
  skipped: number;
}

export type VendorModelBulkActionType = 'enable' | 'disable' | 'record_acceptance' | 'apply_cost_policy';

export interface VendorModelBulkActionRequest {
  modelIds: number[];
  action: VendorModelBulkActionType;
  note?: string | null;
  acceptance?: {
    status?: string;
    note?: string | null;
    evidenceRunId?: string | null;
    evidenceUrl?: string | null;
    checklist?: JsonRecord | null;
    metadata?: JsonRecord;
  };
  costPolicy?: JsonRecord | null;
  status?: string | null;
}

export interface VendorModelBulkActionItem {
  modelId: number;
  success: boolean;
  error?: string | null;
  model?: VendorModel | null;
}

export interface VendorModelBulkActionResponse {
  action: VendorModelBulkActionType;
  total: number;
  updated: number;
  failed: number;
  items: VendorModelBulkActionItem[];
}

export type VendorModelFormState = Partial<VendorModel> & {
  apiTypesText?: string;
  executionModesText?: string;
  metadataText?: string;
  routePolicyText?: string;
  defaultTaskPolicyText?: string;
  inputSchemaText?: string;
  costPolicyText?: string;
};

export interface Ability {
  id: string;
  provider: string;
  category: string;
  capability_key: string;
  version?: string | null;
  display_name: string;
  description?: string | null;
  status: string;
  ability_type: string;
  executor_id?: string | null;
  workflow_id?: string | null;
  vendor_model_id?: number | null;
  coze_workflow_id?: string | null;
  default_params?: JsonRecord | null;
  input_schema?: JsonRecord | null;
  metadata?: JsonRecord | null;
  last_health_check_at?: string | null;
  last_health_status?: string | null;
  success_rate?: number | null;
  created_at: string;
  updated_at: string;
}

export type AbilityFormState = Partial<Omit<Ability, 'default_params' | 'input_schema' | 'metadata'>> & {
  default_params?: string;
  input_schema?: string;
  metadata?: string;
};

export interface PublicAbility {
  id: string;
  provider: string;
  category: string;
  capabilityKey: string;
  version?: string | null;
  displayName: string;
  description?: string | null;
  status: string;
  abilityType: string;
  workflowId?: string | null;
  executorId?: string | null;
  vendorModelId?: number | null;
  cozeWorkflowId?: string | null;
  defaultParams?: JsonRecord | null;
  inputSchema?: JsonRecord | null;
  metadata?: JsonRecord | null;
  requiresImage?: boolean;
  supportsMultipleImages?: boolean;
  maxOutputImages?: number | null;
  lastHealthCheckAt?: string | null;
  lastHealthStatus?: string | null;
  successRate?: number | null;
}

export interface AbilityListResponse {
  items: PublicAbility[];
}

export interface AbilityHealthSummaryItem {
  abilityId: string;
  displayName: string;
  provider: string;
  capabilityKey: string;
  status: string;
  healthStatus: string;
  lastHealthCheckAt?: string | null;
  successRate?: number | null;
  finishedLogCount: number;
  latestLogStatus?: string | null;
  latestLogAt?: string | null;
  stale: boolean;
  needsTest: boolean;
}

export interface AbilityHealthSummaryResponse {
  generatedAt: string;
  staleHours: number;
  total: number;
  healthy: number;
  degraded: number;
  failed: number;
  unknown: number;
  staleCount: number;
  needsTestCount: number;
  items: AbilityHealthSummaryItem[];
}

export interface BusinessCapability {
  id: string;
  businessKey: string;
  version: string;
  displayName: string;
  description?: string | null;
  status: string;
  isDefault: boolean;
  releaseTime?: string | null;
  recipe?: JsonRecord | null;
  inputSchema?: JsonRecord | null;
  outputSchema?: JsonRecord | null;
  metadata?: JsonRecord | null;
  primaryAbilityId?: string | null;
  primaryAbilityName?: string | null;
  primaryAbilityProvider?: string | null;
  vendorModelId?: number | null;
  vendorModelName?: string | null;
  vendorModelProvider?: string | null;
  governanceStatus?: string | null;
  governanceIssues?: string[];
  governanceSuggestions?: string[];
  runtimeKeyConfigured?: boolean | null;
  modelCostConfigured?: boolean | null;
  egressVerified?: boolean | null;
  recipeSteps?: BusinessRecipeStep[];
  latestAcceptance?: BusinessAcceptanceRecord | null;
  acceptanceRecords?: BusinessAcceptanceRecord[];
  releaseGate?: BusinessReleaseGate | null;
  latestRun?: BusinessCapabilityLatestRun | null;
  runMetrics?: BusinessCapabilityRunMetrics | null;
  createdAt: string;
  updatedAt: string;
}

export interface BusinessReleaseGate {
  status?: string | null;
  label?: string | null;
  canRelease?: boolean | null;
  canRequestDefault?: boolean | null;
  acceptancePassed?: boolean | null;
  blockers?: string[];
  warnings?: string[];
  suggestions?: string[];
}

export interface BusinessAcceptanceRecord {
  id?: string | null;
  status?: string | null;
  note?: string | null;
  evidenceRunId?: string | null;
  evidenceUrl?: string | null;
  checklist?: JsonRecord | null;
  metadata?: JsonRecord | null;
  actorUserId?: string | null;
  actorUsername?: string | null;
  actorRole?: string | null;
  createdAt?: string | null;
}

export interface BusinessCapabilityLatestRun {
  id: string;
  status: string;
  createdAt?: string | null;
  created_at?: string | null;
  finishedAt?: string | null;
  finished_at?: string | null;
  imageCount?: number | null;
  image_count?: number | null;
  videoCount?: number | null;
  video_count?: number | null;
  error?: string | null;
}

export interface BusinessCapabilityRunMetrics {
  windowHours?: number | null;
  window_hours?: number | null;
  total?: number | null;
  succeeded?: number | null;
  failed?: number | null;
  running?: number | null;
  queued?: number | null;
  cancelled?: number | null;
  successRate?: number | null;
  success_rate?: number | null;
}

export interface BusinessRecipeStep {
  order: number;
  id?: string | null;
  type?: string | null;
  role?: string | null;
  displayName?: string | null;
  enabled: boolean;
  componentLabel?: string | null;
  componentKind?: string | null;
  componentDescription?: string | null;
  dependsOn?: string[] | null;
  inputs?: string[] | null;
  outputs?: string[] | null;
  params?: JsonValue | null;
  onError?: string | null;
  timeout?: number | null;
  retry?: JsonValue | null;
  visibility?: string | null;
  abilityId?: string | null;
  abilityName?: string | null;
  abilityProvider?: string | null;
}

export interface BusinessCapabilityFormState {
  id?: string;
  businessKey: string;
  version: string;
  displayName: string;
  description?: string;
  status: string;
  isDefault: boolean;
  releaseTime?: string;
  primaryAbilityId: string;
  vlAssistEnabled: boolean;
  vlAssistAbilityId: string;
  rolloutEnabled: boolean;
  rolloutPercent: number;
  rolloutAllowlistText: string;
  recipeText: string;
  inputSchemaText: string;
  outputSchemaText: string;
  metadataText: string;
}

export interface BusinessCapabilityListResponse {
  items: BusinessCapability[];
}

export interface BusinessCapabilityCompareField {
  section: string;
  field: string;
  left?: unknown;
  right?: unknown;
}

export interface BusinessCapabilityCompareResponse {
  left: BusinessCapability;
  right: BusinessCapability;
  sameBusinessKey: boolean;
  changedFields: BusinessCapabilityCompareField[];
  summary: {
    changedCount: number;
    leftVersion?: string | null;
    rightVersion?: string | null;
    leftIsDefault?: boolean | null;
    rightIsDefault?: boolean | null;
    rightStatus?: string | null;
    [key: string]: unknown;
  };
}

export interface BusinessDefaultApproval {
  id: string;
  businessKey: string;
  sourceCapabilityId?: string | null;
  targetCapabilityId: string;
  status: string;
  requesterUserId?: string | null;
  requesterUsername?: string | null;
  approverUserId?: string | null;
  approverUsername?: string | null;
  requestNote?: string | null;
  decisionNote?: string | null;
  beforePayload?: JsonRecord | null;
  afterPayload?: JsonRecord | null;
  sourceCapability?: BusinessCapability | null;
  targetCapability?: BusinessCapability | null;
  createdAt: string;
  updatedAt: string;
  decidedAt?: string | null;
  appliedAt?: string | null;
}

export interface BusinessDefaultApprovalListResponse {
  items: BusinessDefaultApproval[];
}

export interface BusinessRun {
  id: string;
  runId: string;
  businessKey: string;
  businessVersionId?: string | null;
  version?: string | null;
  status: string;
  source: string;
  channel?: string | null;
  traceId?: string | null;
  requestId?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  userId?: string | null;
  userName?: string | null;
  abilityId?: string | null;
  abilityName?: string | null;
  abilityProvider?: string | null;
  vendorModelId?: number | null;
  vendorModelName?: string | null;
  vendorModelProvider?: string | null;
  taskId?: string | null;
  abilityTaskId?: string | null;
  abilityLogId?: number | null;
  requestPayload?: JsonRecord | null;
  resultPayload?: JsonRecord | null;
  imageUrls?: string[] | null;
  videoUrls?: string[] | null;
  texts?: string[] | null;
  error?: string | null;
  errorMessage?: string | null;
  durationMs?: number | null;
  billingUnit?: string | null;
  unitPrice?: number | null;
  costAmount?: number | null;
  currency?: string | null;
  quotaUnits?: number | null;
  costBreakdown?: JsonRecord | null;
  billingStatus?: string | null;
  chargeable?: boolean | null;
  noChargeReason?: string | null;
  callbackStatus?: string | null;
  callbackHttpStatus?: number | null;
  callbackError?: string | null;
  debugUrl?: string | null;
  routeInfo?: JsonRecord | null;
  issueCategory?: string | null;
  issueLabel?: string | null;
  issueSeverity?: string | null;
  issueAction?: string | null;
  issueEvidence?: string | null;
  retestSourceRunId?: string | null;
  retestLatestRunId?: string | null;
  retestLatestStatus?: string | null;
  retestAttempts?: number | null;
  retestRecovered?: boolean | null;
  retestSummary?: JsonRecord | null;
  flowSummary?: BusinessRunFlowSummary | null;
  steps?: BusinessRunStep[];
  createdAt: string;
  updatedAt: string;
  finishedAt?: string | null;
}

export interface BusinessRunFlowSummary {
  total?: number | null;
  succeeded?: number | null;
  failed?: number | null;
  running?: number | null;
  queued?: number | null;
  planned?: number | null;
  skipped?: number | null;
  cancelled?: number | null;
  progressPercent?: number | null;
  currentStepOrder?: number | null;
  currentStepLabel?: string | null;
  currentStepStatus?: string | null;
  currentStepError?: string | null;
  issueCategory?: string | null;
  issueLabel?: string | null;
  issueSeverity?: string | null;
  issueAction?: string | null;
  issueEvidence?: string | null;
  message?: string | null;
  nextAction?: string | null;
  route?: JsonRecord | null;
  ability?: JsonRecord | null;
  executor?: JsonRecord | null;
  output?: JsonRecord | null;
  callback?: JsonRecord | null;
}

export interface BusinessRunStep {
  id: string;
  runId: string;
  order: number;
  stepId?: string | null;
  stepType: string;
  role?: string | null;
  displayName?: string | null;
  enabled: boolean;
  status: string;
  componentLabel?: string | null;
  componentKind?: string | null;
  componentDescription?: string | null;
  abilityId?: string | null;
  abilityName?: string | null;
  abilityProvider?: string | null;
  abilityTaskId?: string | null;
  abilityLogId?: number | null;
  executorId?: string | null;
  executorName?: string | null;
  executorType?: string | null;
  executionEvidence?: JsonRecord | null;
  resultSummary?: JsonRecord | null;
  error?: string | null;
  durationMs?: number | null;
  billingUnit?: string | null;
  unitPrice?: number | null;
  costAmount?: number | null;
  currency?: string | null;
  quotaUnits?: number | null;
  costBreakdown?: JsonRecord | null;
  billingStatus?: string | null;
  chargeable?: boolean | null;
  noChargeReason?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface BusinessRunListResponse {
  total: number;
  items: BusinessRun[];
}

export interface BusinessRunBulkActionItem {
  runId: string;
  newRunId?: string | null;
  ok: boolean;
  status: string;
  message?: string | null;
}

export interface BusinessRunBulkActionResponse {
  action: string;
  total: number;
  succeeded: number;
  failed: number;
  items: BusinessRunBulkActionItem[];
}

export interface BusinessRunIssueChecklistItem {
  runId: string;
  businessKey?: string | null;
  version?: string | null;
  status: string;
  issueCategory: string;
  issueLabel: string;
  issueSeverity: string;
  issueAction?: string | null;
  issueEvidence?: string | null;
  recommendedActions: string[];
  diagnostics: string[];
  abilityId?: string | null;
  abilityName?: string | null;
  executorId?: string | null;
  executorName?: string | null;
  callbackStatus?: string | null;
  retestLatestRunId?: string | null;
  retestLatestStatus?: string | null;
  createdAt?: string | null;
}

export interface BusinessRunIssueChecklistResponse {
  generatedAt: string;
  total: number;
  issueCount: number;
  skippedCount: number;
  byCategory: Record<string, number>;
  bySeverity: Record<string, number>;
  markdown: string;
  items: BusinessRunIssueChecklistItem[];
}

export interface BusinessOperationLog {
  id: string;
  action: string;
  targetType: string;
  targetId?: string | null;
  businessKey?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  actorUserId?: string | null;
  actorUsername?: string | null;
  actorRole?: string | null;
  note?: string | null;
  beforePayload?: JsonRecord | null;
  afterPayload?: JsonRecord | null;
  createdAt: string;
}

export interface BusinessOperationLogListResponse {
  items: BusinessOperationLog[];
}

export interface BusinessUsageBucket {
  key: string;
  label: string;
  total: number;
  succeeded: number;
  failed: number;
  running: number;
  queued: number;
  cancelled: number;
  billable?: number;
  unpriced?: number;
  noCharge?: number;
  billingPending?: number;
  callbackSuccess?: number;
  callbackFailed?: number;
  callbackRunning?: number;
  callbackMissing?: number;
  successRate?: number | null;
  avgDurationMs?: number | null;
  costByCurrency?: Record<string, number>;
  actualCostByCurrency?: Record<string, number>;
  quotaUnits: number;
  actualQuotaUnits?: number;
  latestAt?: string | null;
}

export interface BusinessIssueBucket extends BusinessUsageBucket {
  severity?: string | null;
  action?: string | null;
}

export interface BusinessUnresolvedIssueBucket extends BusinessIssueBucket {
  retested?: number;
  retestAttempts?: number;
}

export interface BusinessUnresolvedIssue {
  id: string;
  runId: string;
  businessKey: string;
  version?: string | null;
  status: string;
  source: string;
  tenantId?: string | null;
  clientId?: string | null;
  traceId?: string | null;
  issueCategory: string;
  issueLabel: string;
  issueAction?: string | null;
  retestAttempts?: number;
  retestLatestRunId?: string | null;
  retestLatestStatus?: string | null;
  createdAt: string;
}

export interface BusinessUsageFailure {
  id: string;
  runId: string;
  businessKey: string;
  version?: string | null;
  status: string;
  source: string;
  channel?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  traceId?: string | null;
  error?: string | null;
  createdAt: string;
}

export interface BusinessUsageSummaryResponse {
  windowHours: number;
  filters: JsonRecord;
  total: number;
  succeeded: number;
  failed: number;
  running: number;
  queued: number;
  cancelled: number;
  billable?: number;
  unpriced?: number;
  noCharge?: number;
  billingPending?: number;
  callbackSuccess?: number;
  callbackFailed?: number;
  callbackRunning?: number;
  callbackMissing?: number;
  successRate?: number | null;
  avgDurationMs?: number | null;
  costByCurrency: Record<string, number>;
  actualCostByCurrency?: Record<string, number>;
  quotaUnits: number;
  actualQuotaUnits?: number;
  byBusiness: BusinessUsageBucket[];
  bySource: BusinessUsageBucket[];
  byTenant: BusinessUsageBucket[];
  byClient: BusinessUsageBucket[];
  byVersion: BusinessUsageBucket[];
  byIssue: BusinessIssueBucket[];
  unresolvedIssues?: BusinessUnresolvedIssueBucket[];
  recentUnresolvedIssues?: BusinessUnresolvedIssue[];
  recentFailures: BusinessUsageFailure[];
}

export interface StoredAsset {
  ossUrl?: string | null;
  ossKey?: string | null;
  sourceUrl?: string | null;
  contentType?: string | null;
  mimeType?: string | null;
  size?: number | null;
  tag?: string | null;
  url?: string | null;
  type?: string | null;
  kind?: string | null;
  role?: string | null;
  outputType?: string | null;
}

export interface AbilityInvocationLog {
  id: number;
  ability_id?: string | null;
  ability_provider: string;
  capability_key: string;
  ability_name?: string | null;
  ability_current_template_id?: string | null;
  ability_template_history_count?: number | null;
  ability_template_published?: boolean | null;
  executor_id?: string | null;
  executor_name?: string | null;
  executor_type?: string | null;
  source: string;
  task_id?: string | null;
  callback_id?: string | null;
  trace_id?: string | null;
  workflow_run_id?: string | null;
  status: string;
  submit_status?: string | null;
  final_status?: string | null;
  error_code?: string | null;
  duration_ms?: number | null;
  stored_url?: string | null;
  request_payload?: JsonRecord | null;
  response_payload?: JsonRecord | null;
  result_assets?: StoredAsset[] | null;
  output_summary?: AbilityInvocationOutputSummary | null;
  error_message?: string | null;
  callback_status?: string | null;
  callback_http_status?: number | null;
  callback_payload?: JsonRecord | null;
  callback_response?: JsonRecord | null;
  callback_error?: string | null;
  callback_started_at?: string | null;
  callback_finished_at?: string | null;
  billing_unit?: string | null;
  unit_price?: number | null;
  currency?: string | null;
  cost_amount?: number | null;
  created_at: string;
}

export interface AbilityInvocationOutputSummary {
  image_count: number;
  video_count: number;
  text_count: number;
  structured_count?: number;
  asset_count: number;
  primary_kind?: 'image' | 'video' | 'text' | 'structured' | 'asset' | string | null;
  primary_url?: string | null;
  text_preview?: string | null;
  has_output: boolean;
}

export interface ComfyuiQueueStatus {
  executorId: string;
  baseUrl: string;
  executorName?: string | null;
  executorStatus?: string | null;
  maxConcurrency?: number | null;
  tags?: string[] | null;
  runningCount: number;
  pendingCount: number;
  totalCount?: number | null;
  queueMaxSize?: number | null;
  capacityTarget?: number | null;
  idleSlots?: number | null;
  utilization?: number | null;
  saturation?: string | null;
  diagnosisLevel?: string | null;
  diagnosis?: string | null;
  backendQueued?: number | null;
  backendRunning?: number | null;
  backendActive?: number | null;
  backendOldestQueuedAt?: string | null;
  backendOldestRunningAt?: string | null;
  feedCode?: string | null;
  feedDiagnosisLevel?: string | null;
  feedDiagnosis?: string | null;
  routeEvidence?: {
    recentTotal?: number | null;
    recentQueued?: number | null;
    recentRunning?: number | null;
    recentSucceeded?: number | null;
    recentFailed?: number | null;
    recentCancelled?: number | null;
    recentOther?: number | null;
    latestTaskId?: string | null;
    latestStatus?: string | null;
    latestTaskAt?: string | null;
  } | null;
  routeDiagnosisLevel?: string | null;
  routeDiagnosis?: string | null;
  supported?: boolean;
  message?: string | null;
  raw?: JsonRecord | null;
}

export interface ComfyuiModelCatalogResponse {
  executorId: string;
  baseUrl: string;
  models: Record<string, string[]>;
  nodeKeys?: string[] | null;
  nodeCount?: number | null;
}

export interface ComfyuiQueueSummary {
  totalRunning: number;
  totalPending: number;
  totalCount: number;
  totalCapacity?: number | null;
  totalIdleSlots?: number | null;
  utilization?: number | null;
  backendQueuedTotal?: number | null;
  backendRunningTotal?: number | null;
  backendActiveTotal?: number | null;
  supportedServers?: number | null;
  unsupportedServers?: number | null;
  saturatedServers?: number | null;
  idleServers?: number | null;
  stalledServers?: number | null;
  underUsedServers?: number | null;
  feedGapServers?: number | null;
  backendBlockedServers?: number | null;
  routeEvidenceWindowHours?: number | null;
  routeEvidenceTotal?: number | null;
  routeEvidenceCoveredServers?: number | null;
  recentRouteMissingServers?: number | null;
  diagnostics?: Array<{ level: string; code: string; message: string }>;
  timestamp?: string | null;
  servers: ComfyuiQueueStatus[];
}

export interface ComfyuiWorkflowCompatibilityDiagnostic {
  level: string;
  code: string;
  message: string;
}

export interface ComfyuiWorkflowMissingNode {
  nodeId: string;
  classType: string;
}

export interface ComfyuiWorkflowMissingModel {
  nodeId: string;
  classType: string;
  inputName: string;
  value: string;
}

export interface ComfyuiWorkflowCompatibilityServer {
  executorId: string;
  compatible: boolean;
  reachable: boolean;
  missingNodes: ComfyuiWorkflowMissingNode[];
  missingModels: ComfyuiWorkflowMissingModel[];
  message?: string | null;
}

export interface ComfyuiWorkflowCompatibilityItem {
  abilityId: string;
  displayName: string;
  capabilityKey: string;
  workflowKey: string;
  workflowId?: string | null;
  action?: string | null;
  allowedExecutorIds: string[];
  bindingExecutorIds: string[];
  expectedExecutorIds: string[];
  compatibleExecutorIds: string[];
  incompatibleExecutorIds: string[];
  requiredNodeKeys: string[];
  requiredNodeCount: number;
  status: 'ok' | 'warning' | 'failed' | string;
  diagnostics: ComfyuiWorkflowCompatibilityDiagnostic[];
  servers: ComfyuiWorkflowCompatibilityServer[];
}

export interface ComfyuiWorkflowCompatibilityExecutor {
  executorId: string;
  executorName?: string | null;
  baseUrl?: string | null;
  status?: string | null;
  reachable: boolean;
  nodeCount?: number | null;
  message?: string | null;
}

export interface ComfyuiWorkflowCompatibility {
  checkedAt: string;
  totalWorkflows: number;
  okCount: number;
  warningCount: number;
  failedCount: number;
  servers: ComfyuiWorkflowCompatibilityExecutor[];
  workflows: ComfyuiWorkflowCompatibilityItem[];
}

export interface ComfyuiLora {
  id: number;
  file_name: string;
  display_name: string;
  description?: string | null;
  base_model?: string | null;
  base_models?: string[] | null;
  tags?: string[] | null;
  trigger_words?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
  installed?: boolean | null;
}

export interface ComfyuiLoraCatalogResponse {
  executorId?: string | null;
  baseUrl?: string | null;
  installedFiles?: string[] | null;
  untrackedFiles?: string[] | null;
  items: ComfyuiLora[];
}

export interface ComfyuiModelCatalogItem {
  id: number;
  file_name: string;
  display_name: string;
  model_type: string;
  description?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  tags?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiModelCatalogResponse {
  items: ComfyuiModelCatalogItem[];
}

export interface ComfyuiPluginCatalogItem {
  id: number;
  node_key: string;
  display_name: string;
  package_name?: string | null;
  version?: string | null;
  description?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  tags?: string[] | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiPluginCatalogResponse {
  items: ComfyuiPluginCatalogItem[];
}

export interface ComfyuiVersionCatalogItem {
  id: number;
  version: string;
  commit_sha?: string | null;
  repo_url?: string | null;
  source_url?: string | null;
  download_url?: string | null;
  released_at?: string | null;
  notes?: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiVersionCatalogResponse {
  items: ComfyuiVersionCatalogItem[];
}

export interface ComfyuiVersionCatalogSyncResponse {
  repo_url: string;
  fetched_at: string;
  total: number;
  created: number;
  updated: number;
}

export interface ComfyuiServerDiffLog {
  id: number;
  baseline_executor_id: string;
  payload?: JsonRecord | null;
  created_at: string;
}

export interface ComfyuiAgent {
  id: string;
  name?: string | null;
  role?: string | null;
  host?: string | null;
  baseUrl?: string | null;
  base_url?: string | null;
  status?: string | null;
  allowed?: boolean | null;
  last_seen_at?: string | null;
  last_heartbeat_at?: string | null;
  last_manifest_version?: string | null;
  metrics?: JsonRecord | null;
  config?: JsonRecord | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiAgentManifest {
  id: number;
  role: string;
  version: string;
  status?: string | null;
  downloadUrl?: string | null;
  download_url?: string | null;
  content?: JsonRecord | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiManifestDriftCollection {
  expected: string[];
  reported: string[];
  missing: string[];
  extra: string[];
}

export interface ComfyuiManifestDriftResponse {
  manifestId: number;
  manifestVersion: string;
  agentId: string;
  agentLastManifestVersion?: string | null;
  sameVersion: boolean;
  hasSnapshot: boolean;
  comfyui: JsonRecord;
  models: ComfyuiManifestDriftCollection;
  plugins: ComfyuiManifestDriftCollection;
  workflows: ComfyuiManifestDriftCollection;
}

export interface ComfyuiRepairPlanItem {
  agentId: string;
  role?: string | null;
  actions: string[];
  missingItems: Record<string, string[]>;
  reason?: string | null;
}

export interface ComfyuiRepairPlan {
  manifestId: number;
  manifestVersion: string;
  mode: string;
  generatedAt: string;
  items: ComfyuiRepairPlanItem[];
  summary: {
    totalAgents: number;
    executableAgents: number;
    skippedAgents: number;
    totalActions: number;
  };
}

export interface ComfyuiRepairJobItem {
  id: number;
  agentId?: string | null;
  taskId?: string | null;
  status: string;
  submitStatus?: string | null;
  callbackStatus?: string | null;
  finalStatus?: string | null;
  actions: string[];
  missingItems: Record<string, string[]>;
  failedItems?: JsonRecord | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  updatedAt: string;
}

export interface ComfyuiRepairJob {
  id: string;
  manifestId: number;
  mode: string;
  status: string;
  requestedAgentCount: number;
  submittedTaskCount: number;
  succeededTaskCount: number;
  failedTaskCount: number;
  skippedTaskCount: number;
  createdBy?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
  resultPayload?: JsonRecord | null;
  items: ComfyuiRepairJobItem[];
}

export interface ComfyuiRolePrimary {
  role: string;
  agentId?: string | null;
  baseUrl?: string | null;
  updatedAt?: string | null;
}

export interface ComfyuiMonitoringLane {
  lane: string;
  total: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  avgWaitSeconds: number;
  failureRate: number;
  retryCount: number;
}

export interface ComfyuiMonitoringSummary {
  generatedAt: string;
  windowHours: number;
  lanes: ComfyuiMonitoringLane[];
}

export interface ComfyuiMonitoringQueueItem {
  lane: string;
  provider: string;
  queued: number;
  running: number;
  total: number;
  avgWaitSeconds: number;
}

export interface ComfyuiMonitoringQueuesResponse {
  generatedAt: string;
  windowHours: number;
  items: ComfyuiMonitoringQueueItem[];
}

export interface ComfyuiMonitoringErrorItem {
  provider: string;
  stage: string;
  errorCode: string;
  count: number;
  lastOccurredAt?: string | null;
  sampleMessage?: string | null;
}

export interface ComfyuiMonitoringErrorsResponse {
  generatedAt: string;
  windowHours: number;
  items: ComfyuiMonitoringErrorItem[];
}

export interface ComfyuiRuntimePolicy {
  policyType: string;
  defaultPolicy: JsonRecord;
  laneOverrides: JsonRecord;
  nodeOverrides: JsonRecord;
  notes?: string | null;
  updatedAt: string;
}

export interface ComfyuiResourceOption {
  id: string;
  key: string;
  label: string;
  resourceType: string;
  status: string;
  description?: string | null;
  downloadUrl?: string | null;
  metadata?: JsonRecord | null;
}

export interface ComfyuiResourceOptionsResponse {
  resourceType: string;
  status?: string | null;
  total: number;
  items: ComfyuiResourceOption[];
}

export interface ComfyuiAgentTask {
  id: string;
  agentId: string;
  manifestId?: number | null;
  manifestUrl?: string | null;
  actions?: string[] | null;
  status: string;
  submitStatus?: string | null;
  callbackStatus?: string | null;
  finalStatus?: string | null;
  errorCode?: string | null;
  tokenNonce?: string | null;
  pushedAt?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  requestPayload?: JsonRecord | null;
  resultPayload?: JsonRecord | null;
  errorMessage?: string | null;
  expiresAt?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ComfyuiAgentTaskEvent {
  id: number;
  taskId: string;
  level: string;
  message: string;
  payload?: JsonRecord | null;
  eventTime?: string | null;
  created_at?: string;
}

export interface ComfyuiAgentAlert {
  id: number;
  agentId: string;
  alertType: string;
  message: string;
  payload?: JsonRecord | null;
  created_at?: string;
}

export interface ComfyuiAgentTokenResponse {
  token: string;
  expiresAt: string;
  scope: string;
  agentId: string;
}

export interface ComfyuiEnrollCode {
  id: number;
  code: string;
  role: string;
  status: string;
  note?: string | null;
  maxUses: number;
  usedCount: number;
  expiresAt: string;
  usedAt?: string | null;
  usedByAgentId?: string | null;
  createdBy?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ComfyuiDesktopRelease {
  id: number;
  channel: string;
  version: string;
  osType: string;
  arch: string;
  status: string;
  downloadUrl: string;
  sha256: string;
  minAgentVersion?: string | null;
  notes?: string | null;
  payload?: JsonRecord | null;
  publishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DashboardTotals {
  total_tasks: number;
  queue_depth: number;
  pending_batches: number;
  failed_tasks: number;
}

export interface QueueOverview {
  total_pending: number;
  total_running: number;
  task_pending: number;
  task_running: number;
  ability_pending: number;
  ability_running: number;
  eval_pending: number;
  eval_running: number;
  pending_batches: number;
  pending_batch_tasks: number;
}

export interface TaskStatusBucket {
  status: string;
  count: number;
}

export interface TodaySummary {
  created: number;
  completed: number;
  failed: number;
}

export interface RecentTask {
  id: string;
  user_id: string;
  tool_action: string;
  channel: string;
  status: string;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
}

export interface ExecutorHealth {
  id: string;
  name: string;
  status: string;
  health_status?: string | null;
  max_concurrency: number;
  weight: number;
  last_heartbeat_at?: string | null;
}

export interface DashboardStrategySummary {
  window_hours: number;
  north_star: DashboardStrategyIndicator;
  indicators: DashboardStrategyIndicator[];
  business_total: number;
  business_succeeded: number;
  business_failed: number;
  success_rate?: number | null;
  billable: number;
  unpriced: number;
  no_charge: number;
  billing_pending: number;
  callback_failed: number;
  callback_missing: number;
  wallet_settled: number;
  wallet_failed: number;
  cost_by_currency: Record<string, number>;
  quota_units: number;
  risk_count: number;
}

export interface DashboardStrategyIndicator {
  key: string;
  title: string;
  value: string;
  target: string;
  status: 'healthy' | 'warning' | 'critical' | string;
  detail: string;
  action: string;
}

export interface StrategySnapshotResponse {
  id: string;
  generatedAt: string;
  windowHours: number;
  note?: string | null;
  summary: DashboardStrategySummary;
}

export interface StrategySnapshotListResponse {
  items: StrategySnapshotResponse[];
}

export interface ReleasePreflightCheck {
  name: string;
  title: string;
  status: 'pass' | 'warn' | 'fail' | string;
  blocking: boolean;
  detail: string;
  durationMs?: number | null;
  suggestion?: string | null;
}

export interface ReleasePreflightResponse {
  id: string;
  mode: string;
  status: 'passed' | 'warning' | 'blocked' | string;
  canRelease: boolean;
  generatedAt: string;
  baseUrl: string;
  blockingCount: number;
  warningCount: number;
  checks: ReleasePreflightCheck[];
}

export interface ReleasePreflightSnapshotListResponse {
  items: ReleasePreflightResponse[];
}

export interface ReleasePatrolRecordResponse {
  id: string;
  status: 'passed' | 'failed' | 'cancelled' | 'manual' | string;
  generatedAt: string;
  command?: string | null;
  reportPath?: string | null;
  note?: string | null;
  summary: JsonRecord;
}

export interface ReleasePatrolRecordListResponse {
  items: ReleasePatrolRecordResponse[];
}

export interface HealthWatchUnitStatus {
  unit: string;
  title: string;
  kind: 'timer' | 'service' | string;
  status: 'healthy' | 'running' | 'failed' | 'disabled' | 'unavailable' | 'unknown' | string;
  summary: string;
  loadState?: string | null;
  activeState?: string | null;
  subState?: string | null;
  unitFileState?: string | null;
  result?: string | null;
  execMainStatus?: number | null;
  lastTrigger?: string | null;
  nextElapse?: string | null;
  recentLogs: string[];
}

export interface HealthWatchStatusResponse {
  generatedAt: string;
  supported: boolean;
  items: HealthWatchUnitStatus[];
  issues: string[];
}

export interface ReleaseDecisionRecordResponse {
  id: string;
  status: 'approved' | 'deferred' | 'blocked' | string;
  title: string;
  generatedAt: string;
  preflightId?: string | null;
  patrolId?: string | null;
  note?: string | null;
  summary: JsonRecord;
}

export interface ReleaseDecisionRecordListResponse {
  items: ReleaseDecisionRecordResponse[];
}

export interface WeeklyReportResponse {
  id: string;
  generatedAt: string;
  windowHours: number;
  reportPath: string;
  snapshotId: string;
  sendStatus: 'not_sent' | 'sent' | 'failed' | string;
  sendDetail?: string | null;
  webhookFormat: 'generic' | 'feishu' | 'dingtalk' | string;
  webhookConfigured: boolean;
  summary: DashboardStrategySummary;
}

export interface WeeklyReportListResponse {
  items: WeeklyReportResponse[];
}

export interface DashboardMetrics {
  totals: DashboardTotals;
  queue_overview: QueueOverview;
  status_buckets: TaskStatusBucket[];
  today: TodaySummary;
  recent_tasks: RecentTask[];
  executor_health: ExecutorHealth[];
  strategy_summary: DashboardStrategySummary;
}

export interface DispatchLogEntry {
  id: number;
  task_id: string;
  tool_action: string;
  task_status: string;
  event_type: string;
  payload?: JsonRecord | null;
  created_at: string;
}

export interface DispatchLogResponse {
  entries: DispatchLogEntry[];
}

export interface DatabaseConfig {
  backend: string;
  driver?: string | null;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  dsn: string;
}

export interface OssConfig {
  bucket: string;
  endpoint: string;
  public_domain?: string | null;
  root_prefix: string;
  sts_duration: number;
  role_arn?: string | null;
}

export interface SecurityConfig {
  jwt_access_ttl: number;
  jwt_refresh_ttl: number;
  upload_token_ttl: number;
}

export interface CozeConfig {
  base_url?: string | null;
  loop_base_url?: string | null;
  default_timeout: number;
  token_present: boolean;
  token_hint?: string | null;
}

export interface TodoItem {
  title: string;
  description: string;
  severity: string;
  status: string;
}

export interface SystemConfig {
  app_name: string;
  database: DatabaseConfig;
  oss: OssConfig;
  security: SecurityConfig;
  coze?: CozeConfig | null;
  feature_flags: Record<string, boolean>;
  todo_items: TodoItem[];
}

export interface AbilityLogListResponse {
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
  items: AbilityInvocationLog[];
}

export interface AbilityLogMetricBucket {
  ability_provider: string;
  capability_key: string;
  executor_id?: string | null;
  count: number;
  success_count: number;
  failed_count: number;
  success_rate?: number | null;
  avg_duration_ms?: number | null;
  p50_duration_ms?: number | null;
  p95_duration_ms?: number | null;
  total_cost?: number | null;
  avg_cost?: number | null;
  last_success_at?: string | null;
  last_failed_at?: string | null;
}

export interface AbilityLogCostSummary {
  key: string;
  count: number;
  total_cost?: number | null;
  avg_cost?: number | null;
}

export interface AbilityLogMetricsResponse {
  window_hours: number;
  total_count?: number | null;
  total_success_count?: number | null;
  total_failed_count?: number | null;
  uncosted_count?: number | null;
  total_cost?: number | null;
  avg_cost_per_call?: number | null;
  provider_totals?: AbilityLogCostSummary[];
  currency_totals?: AbilityLogCostSummary[];
  buckets: AbilityLogMetricBucket[];
}

export interface AbilityTemplateSnapshot {
  id: string;
  version_label?: string | null;
  action: string;
  created_at: string;
  notes?: string | null;
  default_params?: JsonRecord | null;
  input_schema?: JsonRecord | null;
  metadata?: JsonRecord | null;
}

export interface AbilityTemplateStateResponse {
  ability_id: string;
  current_template_id?: string | null;
  history: AbilityTemplateSnapshot[];
}

export interface AbilityTemplateValidateResponse {
  ok: boolean;
  errors: string[];
  warnings: string[];
}
