from pydantic import BaseModel, Field


class FreezeRequest(BaseModel):
    userId: str
    taskId: str
    action: str | None = None
    points: int = Field(..., gt=0)
    channel: str | None = None


class FreezeResponse(BaseModel):
    holdId: str
    balance: int


class HoldActionRequest(BaseModel):
    holdId: str


class TransactionsQuery(BaseModel):
    userId: str
    page: int = 1
    pageSize: int = 20


class TransactionItem(BaseModel):
    id: str
    changeType: str
    points: int
    beforeBalance: int
    afterBalance: int
    taskId: str | None = None
    traceId: str | None = None
    description: str | None = None
    provider: str | None = None
    modelKey: str | None = None
    createdAt: str | None = None


class TransactionsResponse(BaseModel):
    total: int
    items: list[TransactionItem]


class LedgerResponse(TransactionsResponse):
    userId: str
    page: int
    pageSize: int


class StatisticsResponse(BaseModel):
    totalPoints: int
    tempPoints: int
    frozenPoints: int
    grantedToday: int


class BalanceResponse(BaseModel):
    userId: str
    balance: int
    frozenBalance: int
    currency: str


class RechargeOrderCreateRequest(BaseModel):
    userId: str
    amount: int
    channel: str = "manual"


class RechargeOrderResponse(BaseModel):
    orderNo: str
    userId: str
    amount: int
    channel: str
    status: str
    createdAt: str
    paidAt: str | None = None
    failReason: str | None = None
    transactionId: str | None = None
    updatedAt: str | None = None


class RechargeOrderStatusUpdateRequest(BaseModel):
    status: str
    failReason: str | None = None
    transactionId: str | None = None
    taskId: str | None = None
    traceId: str | None = None
    provider: str | None = None
    modelKey: str | None = None


class BillResponse(BaseModel):
    userId: str
    month: str
    income: int
    expense: int
    net: int
    count: int


class CostSnapshotItem(BaseModel):
    date: str
    provider: str
    modelKey: str
    points: int
    taskId: str | None = None


class CostSnapshotResponse(BaseModel):
    userId: str
    provider: str | None = None
    modelKey: str | None = None
    count: int
    totalPoints: int
    items: list[CostSnapshotItem]
