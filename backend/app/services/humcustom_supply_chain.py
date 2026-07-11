"""Controlled Humcustom/Fengniao API client used only by operations workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.core.config import Settings, get_settings


@dataclass(slots=True)
class HumcustomPlaceOrderResult:
    plat_order_id: str
    order_id: str | None
    platform_order_id: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class HumcustomOrderSnapshot:
    plat_order_id: str
    order_status_name: str | None
    waybill_no: str | None
    raw: dict[str, Any]


class HumcustomSupplyChainError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class HumcustomSupplyChainClient:
    def __init__(self) -> None:
        self._cached_access_token: str | None = None
        self._cached_expires_time_ms: int | None = None

    def place_order(self, payload: dict[str, Any]) -> HumcustomPlaceOrderResult:
        plat_order_id = _text(payload.get("platOrderId"))
        if not plat_order_id:
            raise HumcustomSupplyChainError(400, "FENGNIAO_ORDER_ID_REQUIRED", "缺少平台订单号。")
        settings = get_settings()
        response = self._request_json(
            settings=settings,
            method="POST",
            path="/open/api/v1/order/placeOrder",
            headers={"accessToken": self._get_access_token(settings)},
            json=payload,
            failure_code="FENGNIAO_PLACE_ORDER_FAILED",
            failure_message="蜂鸟下单失败。",
        )
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        express = data.get("expressResult") if isinstance(data.get("expressResult"), dict) else {}
        return HumcustomPlaceOrderResult(
            plat_order_id=plat_order_id,
            order_id=_text(express.get("orderId") or data.get("orderId")),
            platform_order_id=_text(express.get("platformOrderId") or data.get("platformOrderId")),
            raw=response,
        )

    def query_order(self, plat_order_id: str) -> HumcustomOrderSnapshot:
        query_id = _text(plat_order_id)
        if not query_id:
            raise HumcustomSupplyChainError(400, "FENGNIAO_ORDER_ID_REQUIRED", "缺少平台订单号。")
        settings = get_settings()
        response = self._request_json(
            settings=settings,
            method="GET",
            path="/open/api/v1/order/queryOrder",
            headers={"accessToken": self._get_access_token(settings)},
            params={"platOrderId": query_id},
            failure_code="FENGNIAO_QUERY_FAILED",
            failure_message="蜂鸟订单查询失败。",
        )
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        records = data.get("orderDetailList") if isinstance(data.get("orderDetailList"), list) else []
        selected = next(
            (row for row in records if isinstance(row, dict) and _text(row.get("platOrderId")) == query_id),
            next((row for row in records if isinstance(row, dict)), None),
        )
        if not isinstance(selected, dict):
            raise HumcustomSupplyChainError(404, "FENGNIAO_ORDER_NOT_FOUND", "蜂鸟未返回该订单记录。")
        return HumcustomOrderSnapshot(
            plat_order_id=_text(selected.get("platOrderId")) or query_id,
            # Humcustom places current order-level status and waybill fields in
            # ``data`` for this endpoint, while the list contains item details.
            order_status_name=_text(data.get("orderStatusName")) or _text(selected.get("orderStatusName")),
            waybill_no=_text(data.get("waybillNo")) or _text(selected.get("waybillNo")),
            raw=response,
        )

    def _get_access_token(self, settings: Settings) -> str:
        configured = (settings.humcustom_access_token or "").strip()
        if configured:
            return configured
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        if self._cached_access_token and self._cached_expires_time_ms and self._cached_expires_time_ms - now_ms > 60_000:
            return self._cached_access_token
        if not (settings.humcustom_app_key or "").strip() or not (settings.humcustom_app_secret or "").strip():
            raise HumcustomSupplyChainError(503, "FENGNIAO_NOT_CONFIGURED", "蜂鸟供应链密钥未配置。")
        payload = self._request_json(
            settings=settings,
            method="GET",
            path="/open/api/v1/oauth/token",
            params={"appKey": settings.humcustom_app_key, "appSecret": settings.humcustom_app_secret},
            failure_code="FENGNIAO_TOKEN_FAILED",
            failure_message="蜂鸟授权失败。",
        )
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        token = _text(data.get("accessToken"))
        expires = _int(data.get("expiresTime"))
        if not token:
            raise HumcustomSupplyChainError(502, "FENGNIAO_TOKEN_FAILED", "蜂鸟授权未返回 accessToken。")
        self._cached_access_token = token
        self._cached_expires_time_ms = expires
        return token

    def _request_json(
        self, *, settings: Settings, method: str, path: str, failure_code: str, failure_message: str,
        headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method, f"{settings.humcustom_api_base_url.rstrip('/')}{path}", headers=headers, params=params, json=json,
                timeout=max(3, int(settings.humcustom_timeout_seconds or 20)),
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise HumcustomSupplyChainError(504, "FENGNIAO_TIMEOUT", f"{failure_message}请求超时。") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HumcustomSupplyChainError(502, failure_code, failure_message) from exc
        if not isinstance(payload, dict):
            raise HumcustomSupplyChainError(502, failure_code, f"{failure_message}响应格式异常。")
        if payload.get("success") is False or payload.get("code") not in (None, 0, "0"):
            message = _text(payload.get("message")) or failure_message
            code = payload.get("code")
            if str(code) == "401":
                raise HumcustomSupplyChainError(502, "FENGNIAO_AUTH_INVALID", f"蜂鸟授权失效：{message}")
            raise HumcustomSupplyChainError(502, failure_code, message)
        return payload


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


humcustom_supply_chain_client = HumcustomSupplyChainClient()
