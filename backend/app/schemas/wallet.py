from pydantic import BaseModel, Field


class FreezeRequest(BaseModel):
    userId: str
    taskId: str
    action: str
    points: int = Field(..., gt=0)
    channel: str


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
    description: str | None = None


class TransactionsResponse(BaseModel):
    total: int
    items: list[TransactionItem]


class StatisticsResponse(BaseModel):
    totalPoints: int
    tempPoints: int
    frozenPoints: int
    grantedToday: int
