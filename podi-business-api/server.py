#!/usr/bin/env python3
"""Local PODI business API.

This service is intentionally separate from the 8099 mid-platform. It owns
client-facing account, asset, task, wallet and order state for local main-site
closure. Capability execution can later be proxied to the mid-platform from
this layer, instead of letting the browser call the mid-platform directly.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.request
from io import BytesIO
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import oss2


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / ".data"
UPLOAD_DIR = DATA_DIR / "uploads"
STATE_PATH = DATA_DIR / "state.json"
CLIENT_CATALOG_RENDER_DIR = ROOT.parent / "podi-client-web" / "public" / "models" / "catalog-renders"

DEFAULT_SHIPPING_OPTIONS = (
  {"id": "zto", "label": "中通快递", "feeCents": 1000},
  {"id": "sf", "label": "顺丰速运", "feeCents": 2000},
)


def load_local_env(path: Path) -> None:
  if not path.exists():
    return
  for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key and key not in os.environ:
      os.environ[key] = value


load_local_env(ROOT / ".env")
load_local_env(ROOT.parent / "backend" / ".env")

CLIENT_ORIGIN = os.getenv("PODI_CLIENT_ORIGIN", "http://127.0.0.1:5180").rstrip("/")
MIDPLATFORM_BASE = os.getenv("PODI_MIDPLATFORM_BASE_URL", "http://127.0.0.1:8099").rstrip("/")
MIDPLATFORM_API_KEY = os.getenv("PODI_MIDPLATFORM_API_KEY", "")
# Business API is a trusted consumer of the middle platform. Prefer a dedicated
# token when configured, otherwise use the service token already loaded from
# backend/.env. The browser never receives either value.
MIDPLATFORM_SERVICE_TOKEN = (MIDPLATFORM_API_KEY or os.getenv("SERVICE_API_TOKEN", "")).strip()
TEST_SMS_CODE = os.getenv("PODI_TEST_SMS_CODE", "123456")
PODI_OPS_ADMIN_USERNAME = os.getenv("PODI_OPS_ADMIN_USERNAME", "").strip()
PODI_OPS_ADMIN_PASSWORD = os.getenv("PODI_OPS_ADMIN_PASSWORD", "")
ALIYUN_SMS_ACCESS_KEY_ID = os.getenv("ALIYUN_SMS_ACCESS_KEY_ID", "").strip()
ALIYUN_SMS_ACCESS_KEY_SECRET = os.getenv("ALIYUN_SMS_ACCESS_KEY_SECRET", "").strip()
ALIYUN_SMS_SIGN_NAME = os.getenv("ALIYUN_SMS_SIGN_NAME", "西安郁郁芊芊科技").strip()
ALIYUN_SMS_LOGIN_TEMPLATE_CODE = os.getenv("ALIYUN_SMS_LOGIN_TEMPLATE_CODE", "SMS_500500023").strip()
ALIYUN_SMS_IMAGE_LOGIN_TEMPLATE_CODE = os.getenv("ALIYUN_SMS_IMAGE_LOGIN_TEMPLATE_CODE", "SMS_500595029").strip()
ALIYUN_SMS_TEMPLATE_PARAM_NAME = os.getenv("ALIYUN_SMS_TEMPLATE_PARAM_NAME", "code").strip() or "code"
ALIYUN_SMS_ENDPOINT = os.getenv("ALIYUN_SMS_ENDPOINT", "https://dysmsapi.aliyuncs.com/").strip()
SMS_CODE_EXPIRES_SECONDS = int(os.getenv("PODI_SMS_CODE_EXPIRES_SECONDS", "300"))
SMS_RESEND_INTERVAL_SECONDS = int(os.getenv("PODI_SMS_RESEND_INTERVAL_SECONDS", "60"))
SMS_DAILY_LIMIT_PER_PHONE = int(os.getenv("PODI_SMS_DAILY_LIMIT_PER_PHONE", "10"))
SMS_MAX_VERIFY_ATTEMPTS = int(os.getenv("PODI_SMS_MAX_VERIFY_ATTEMPTS", "5"))
ALLOW_TEST_SMS_CODE = os.getenv("PODI_ALLOW_TEST_SMS_CODE", "").strip().lower() in {"1", "true", "yes", "on"}
CLIENT_QUEUE_MAX_TASKS = int(os.getenv("PODI_CLIENT_QUEUE_MAX_TASKS", "10"))
CLIENT_QUEUE_MAX_IN_FLIGHT = int(os.getenv("PODI_CLIENT_QUEUE_MAX_IN_FLIGHT", "3"))
CLIENT_QUEUE_DISPATCH_PER_TICK = int(os.getenv("PODI_CLIENT_QUEUE_DISPATCH_PER_TICK", "1"))
CLIENT_QUEUE_MAX_ATTEMPTS = int(os.getenv("PODI_CLIENT_QUEUE_MAX_ATTEMPTS", "6"))
PROCESS_TASK_STALE_SECONDS = int(os.getenv("PODI_PROCESS_TASK_STALE_SECONDS", str(60 * 60)))
PROCESS_ITEM_DISPATCH_STALE_SECONDS = int(os.getenv("PODI_PROCESS_ITEM_DISPATCH_STALE_SECONDS", "120"))
PROCESS_TASK_ADVANCE_LOCK_SECONDS = int(os.getenv("PODI_PROCESS_TASK_ADVANCE_LOCK_SECONDS", "45"))
ACTIVE_PROCESS_ITEM_STATUSES = {"queued", "dispatching", "running", "submitted", "pending", "processing"}
PROCESS_TASK_CREDITS_BY_TYPE = {
  "clean": 1,
  "extend": 2,
  "extract": 3,
  "variation": 3,
  "seamless2": 2,
  "seamless4": 3,
  "image_edit": 6,
}
ASSET_DIMENSION_PROBE_MAX_BYTES = int(os.getenv("PODI_ASSET_DIMENSION_PROBE_MAX_BYTES", str(8 * 1024 * 1024)))
ASSET_DIMENSION_BOOTSTRAP_LIMIT = int(os.getenv("PODI_ASSET_DIMENSION_BOOTSTRAP_LIMIT", "8"))
MODEL_INPUT_UPLOAD_MAX_BYTES = int(os.getenv("PODI_MODEL_INPUT_UPLOAD_MAX_BYTES", str(12 * 1024 * 1024)))
CLIENT_ASSET_PREVIEW_MAX_BYTES = int(os.getenv("PODI_CLIENT_ASSET_PREVIEW_MAX_BYTES", str(12 * 1024 * 1024)))
OSS_ACCESS_KEY = os.getenv("OSS_ACCESS_KEY") or os.getenv("ALIYUN_OSS_KEY_ID") or os.getenv("ALIYUN_ACCESS_KEY_ID") or ""
OSS_SECRET_KEY = os.getenv("OSS_SECRET_KEY") or os.getenv("ALIYUN_OSS_KEY_SECRET") or os.getenv("ALIYUN_ACCESS_KEY_SECRET") or ""
OSS_BUCKET = os.getenv("OSS_BUCKET") or os.getenv("ALIYUN_OSS_BUCKET") or "podi"
OSS_REGION = os.getenv("OSS_REGION") or os.getenv("ALIYUN_OSS_REGION") or "oss-cn-hangzhou"
OSS_ENDPOINT = os.getenv("OSS_INTERNAL_ENDPOINT") or os.getenv("OSS_ENDPOINT") or os.getenv("ALIYUN_OSS_ENDPOINT") or "oss-cn-hangzhou.aliyuncs.com"
OSS_PUBLIC_DOMAIN = (os.getenv("OSS_PUBLIC_DOMAIN") or os.getenv("ALIYUN_OSS_PUBLIC_DOMAIN") or f"https://{OSS_BUCKET}.{OSS_REGION}.aliyuncs.com").rstrip("/")
OSS_ROOT_PREFIX = (os.getenv("OSS_ROOT_PREFIX") or os.getenv("ALIYUN_OSS_ROOT_PREFIX") or "test").strip("/")
HUMCUSTOM_BASE = os.getenv("HUMCUSTOM_API_BASE_URL", "https://openapi.humcustom.com").rstrip("/")
HUMCUSTOM_APP_KEY = os.getenv("HUMCUSTOM_APP_KEY", "").strip()
HUMCUSTOM_APP_SECRET = os.getenv("HUMCUSTOM_APP_SECRET", "").strip()
HUMCUSTOM_ACCESS_TOKEN = os.getenv("HUMCUSTOM_ACCESS_TOKEN", "").strip()
HUMCUSTOM_TIMEOUT_SECONDS = max(3, int(os.getenv("HUMCUSTOM_TIMEOUT_SECONDS", "20")))
HUMCUSTOM_TOKEN_CACHE: dict[str, Any] = {"accessToken": None, "expiresTime": None}
VOLCENGINE_ARK_BASE = os.getenv("VOLCENGINE_ARK_BASE_URL", "https://ark.cn-beijing.volces.com").rstrip("/")
VOLCENGINE_ARK_API_KEY = (os.getenv("VOLCENGINE_ARK_API_KEY") or os.getenv("VOLCENGINE_API_KEY") or "").strip()
AGENT_VL_PROVIDER = os.getenv("PODI_AGENT_VL_PROVIDER", "volcengine-doubao-lite").strip().lower()
AGENT_VL_MODEL = os.getenv("PODI_AGENT_VL_MODEL", "doubao-seed-2-0-lite-260428").strip()
AGENT_PLANNER_MODEL = os.getenv("PODI_AGENT_PLANNER_MODEL", "doubao-seed-2-1-turbo-260628").strip()
AGENT_VL_TIMEOUT_SECONDS = max(3, int(os.getenv("PODI_AGENT_VL_TIMEOUT_SECONDS", "90")))
AGENT_EXECUTION_MODE = os.getenv("PODI_AGENT_EXECUTION_MODE", "real").strip().lower()
# The business client never selects an image vendor directly. It asks the
# middle platform for these governed abilities, whose credentials and fallbacks
# stay outside the user-facing service.
AGENT_IMAGE2_GENERATE_ABILITY_ID = os.getenv("PODI_AGENT_IMAGE2_GENERATE_ABILITY_ID", "packy_gpt_image_2_generate").strip()
AGENT_IMAGE2_EDIT_ABILITY_ID = os.getenv("PODI_AGENT_IMAGE2_EDIT_ABILITY_ID", "packy_gpt_image_2_edit").strip()
AGENT_IMAGE2_QUALITY = os.getenv("PODI_AGENT_IMAGE2_QUALITY", "auto").strip() or "auto"
AGENT_IMAGE2_BUSINESS_VERSION = os.getenv("PODI_AGENT_IMAGE2_BUSINESS_VERSION", "gpt-image2-vl-v2").strip() or "gpt-image2-vl-v2"
AGENT_SEAMLESS_BUSINESS_ENDPOINT = os.getenv("PODI_AGENT_SEAMLESS_BUSINESS_ENDPOINT", "/api/business/seamless/runs").strip()
AGENT_TEXT2IMAGE_BUSINESS_ENDPOINT = os.getenv("PODI_AGENT_TEXT2IMAGE_BUSINESS_ENDPOINT", "").strip()
AGENT_TEXT2IMAGE_ABILITY_ID = os.getenv("PODI_AGENT_TEXT2IMAGE_ABILITY_ID", AGENT_IMAGE2_GENERATE_ABILITY_ID).strip()
# A default ability id alone is not evidence that the service can invoke it.
# Prompt-only generation needs both a governed middle-platform ability and
# service-to-service authentication for its asynchronous task API.
AGENT_TEXT2IMAGE_AVAILABLE = bool(AGENT_TEXT2IMAGE_ABILITY_ID and MIDPLATFORM_SERVICE_TOKEN)
try:
  import certifi  # type: ignore

  HUMCUSTOM_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
  HUMCUSTOM_SSL_CONTEXT = ssl.create_default_context()

BUSINESS_ENDPOINT_BY_KEY = {
  "outpaint": "/api/business/outpaint/runs",
  "pattern_extract": "/api/business/pattern-extract/runs",
  "fission": "/api/business/fission/runs",
  "seamless": "/api/business/seamless/runs",
  "image_edit": "/api/business/image-edit/runs",
}

AGENT_BUSINESS_ENDPOINT_BY_ABILITY = {
  "pattern_extract": "/api/business/pattern-extract/runs",
  "variation": "/api/business/fission/runs",
  "two_way_seamless": AGENT_SEAMLESS_BUSINESS_ENDPOINT,
  "four_way_seamless": AGENT_SEAMLESS_BUSINESS_ENDPOINT,
  "postprocess_to_surface": "/api/business/product-design/runs",
  "render_product_preview": "/api/business/product-design/runs",
}

AGENT_ALLOWED_STEP_ABILITIES = {
  "vl_analyze",
  "pattern_extract",
  "variation",
  "two_way_seamless",
  "four_way_seamless",
  "image2_recreate",
  "postprocess_to_surface",
  "render_product_preview",
  "ask_user",
}

AGENT_ABILITY_USER_LABELS = {
  "vl_analyze": "理解图片和商品",
  "pattern_extract": "提取花纹",
  "variation": "生成候选图",
  "two_way_seamless": "生成杯身连续图",
  "four_way_seamless": "生成无缝连续图",
  "image2_recreate": "AI 精修重绘",
  "postprocess_to_surface": "适配设计面",
  "render_product_preview": "生成产品预览",
  "ask_user": "等待你确认",
}

STATE_LOCK = threading.RLock()
PROCESS_TASK_ADVANCE_LOCKS: dict[str, float] = {}

SUPPLY_CHAIN_PRODUCT_OVERRIDES = {
  "10395": {"templateNo": "10395", "platformSku": "2730", "name": "20oz带手柄和吸管不锈钢杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "white", "beige1", "light-green", "light-blue", "peach", "light-purple"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "white", "beige1", "light-green", "light-blue", "peach", "light-purple"] }}},
  "10385": {"templateNo": "10385", "platformSku": "2642", "name": "12oz水瓶罐", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10376": {"templateNo": "10376", "platformSku": "1615", "name": "30oz手提杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue", "cameosa", "crimson", "greenish-blue", "grey", "light-blue", "light-green", "light-purple", "light-yellow", "navy-blue", "olive-green", "orange", "pink", "white", "red", "sky-blue"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue", "cameosa", "crimson", "greenish-blue", "grey", "light-blue", "light-green", "light-purple", "light-yellow", "navy-blue", "olive-green", "orange", "pink", "white", "red", "sky-blue"] }}},
  "10374": {"templateNo": "10374", "platformSku": "1645", "name": "40oz手柄杯喷塑", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "white", "pink", "fruit-green", "light-purple", "navy-blue", "nude"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "white", "pink", "fruit-green", "light-purple", "navy-blue", "nude"] }}},
  "10351": {"templateNo": "10351", "platformSku": "1660", "name": "40oz手柄杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue", "burgundy", "cameosa", "yellow", "greenish-blue", "grey", "light-blue", "light-green", "navy-blue", "olive-green", "orangish", "pink", "purple", "red", "sky-blue", "white", "dark-orange"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue", "burgundy", "cameosa", "yellow", "greenish-blue", "grey", "light-blue", "light-green", "navy-blue", "olive-green", "orangish", "pink", "purple", "red", "sky-blue", "white", "dark-orange"] }}},
  "10350": {"templateNo": "10350", "platformSku": "1663", "name": "10oz汽车杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10347": {"templateNo": "10347", "platformSku": "1408", "name": "12oz酒杯（非全副）", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "green", "colorCodes": ["green", "black", "white", "pink", "matte-black", "purple"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["green", "black", "white", "pink", "matte-black", "purple"] }}},
  "10345": {"templateNo": "10345", "platformSku": "1621", "name": "20oz汽车杯-下不锈钢", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10344": {"templateNo": "10344", "platformSku": "1560", "name": "20oz汽车杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10343": {"templateNo": "10343", "platformSku": "1552", "name": "20OZ喷塑汽车杯-上留不锈钢-非全幅", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "green", "colorCodes": ["green", "black", "white", "rose-gold"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["green", "black", "white", "rose-gold"] }}},
  "10342": {"templateNo": "10342", "platformSku": "1302", "name": "11oz陶瓷马克杯", "firstCraft": "杯子厂", "secondCraft": "非不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10341": {"templateNo": "10341", "platformSku": "1400", "name": "15oz陶瓷马克杯", "firstCraft": "杯子厂", "secondCraft": "非不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10256": {"templateNo": "10256", "platformSku": "2544", "name": "双饮咖啡杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "pink", "red", "white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "pink", "red", "white"] }}},
  "10252": {"templateNo": "10252", "platformSku": "1683", "name": "17oz子弹杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10249": {"templateNo": "10249", "platformSku": "1576", "name": "74oz/2.2L塑料运动水壶+套", "firstCraft": "包帽厂", "secondCraft": "其他", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "yellow", "pink"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "yellow", "pink"] }}},
  "10248": {"templateNo": "10248", "platformSku": "1608", "name": "32oz/1L塑料运动水壶+套", "firstCraft": "包帽厂", "secondCraft": "其他", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue", "light-pink", "pink"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue", "light-pink", "pink"] }}},
  "10247": {"templateNo": "10247", "platformSku": "1609", "name": "64oz塑料运动水壶+套", "firstCraft": "包帽厂", "secondCraft": "其他", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue", "blue-green", "pink", "greenish-blue", "purple", "sky-blue"] }}},
  "10246": {"templateNo": "10246", "platformSku": "1662", "name": "25oz热食保温瓶", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10245": {"templateNo": "10245", "platformSku": "1661", "name": "20oz咖啡保温瓶", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10244": {"templateNo": "10244", "platformSku": "1667", "name": "16oz二代可乐瓶", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10242": {"templateNo": "10242", "platformSku": "1668", "name": "29oz保温杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10241": {"templateNo": "10241", "platformSku": "1692", "name": "不锈钢太空壶-多容量", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "18OZ", "colorCode": "black", "colorCodes": ["black", "beige1", "pink"], "sizes": {"18OZ": {"sizeCode": "18OZ", "colorCodes": ["black", "beige1", "pink"] }, "32OZ": {"sizeCode": "32OZ", "colorCodes": ["black", "beige2", "pink"] }, "40OZ": {"sizeCode": "40OZ", "colorCodes": ["black", "beige3", "pink"] }}},
  "10238": {"templateNo": "10238", "platformSku": "1412", "name": "17oz吸管杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue"] }}},
  "10236": {"templateNo": "10236", "platformSku": "1416", "name": "20OZ不锈钢瘦身杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10235": {"templateNo": "10235", "platformSku": "1622", "name": "30oz冰霸杯下不锈钢", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10234": {"templateNo": "10234", "platformSku": "1517", "name": "12oz酒杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10233": {"templateNo": "10233", "platformSku": "1561", "name": "30oz喷塑冰霸杯汽车杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "pink", "colorCodes": ["pink", "sky-blue"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["pink", "sky-blue"] }}},
  "10232": {"templateNo": "10232", "platformSku": "1610", "name": "40oz活动手柄杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "pink", "purple", "red", "sky-blue", "white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "pink", "purple", "red", "sky-blue", "white"] }}},
  "10231": {"templateNo": "10231", "platformSku": "1613", "name": "12oz大口杯喷塑", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10230": {"templateNo": "10230", "platformSku": "1623", "name": "30oz冰霸杯上下不锈钢", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10228": {"templateNo": "10228", "platformSku": "1625", "name": "20oz汽车杯-上下不锈钢", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10226": {"templateNo": "10226", "platformSku": "1652", "name": "16oz汽车杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10224": {"templateNo": "10224", "platformSku": "1665", "name": "20oz美式咖啡杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10223": {"templateNo": "10223", "platformSku": "1664", "name": "12oz美式咖啡杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10221": {"templateNo": "10221", "platformSku": "1684", "name": "17oz子弹头不锈钢杯-非全幅", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "white", "yellow"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "white", "yellow"] }}},
  "10168": {"templateNo": "10168", "platformSku": "1592", "name": "12oz啤酒饮料保温杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "white", "colorCodes": ["white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["white"] }}},
  "10167": {"templateNo": "10167", "platformSku": "1631", "name": "12oz啤酒保温杯", "firstCraft": "杯子厂", "secondCraft": "不锈钢杯", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue-green", "greenish-blue", "pink", "purple", "rose-red", "sky-blue", "white"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue-green", "greenish-blue", "pink", "purple", "rose-red", "sky-blue", "white"] }}},
  "10165": {"templateNo": "10165", "platformSku": "1682", "name": "水瓶手提袋", "firstCraft": "包帽厂", "secondCraft": "其他", "sizeCode": "OneSize", "colorCode": "black", "colorCodes": ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"], "sizes": {"OneSize": {"sizeCode": "OneSize", "colorCodes": ["black", "blue", "blue-green", "greenish-blue", "pink", "purple", "sky-blue"] }}},
}

SUPPLY_CHAIN_UV_PRINT_CRAFT_TEMPLATE_IDS = {
  "10167", "10168", "10221", "10223", "10224", "10226", "10228", "10230",
  "10231", "10232", "10233", "10234", "10235", "10236", "10238", "10241",
  "10242", "10343", "10344", "10345", "10347",
}

SUPPLY_CHAIN_HEAT_TRANSFER_CRAFT_TEMPLATE_IDS = {"10165", "10341", "10342"}

# 陶瓷马克杯已从用户侧产品目录下架。保留供应链映射仅用于历史订单
# 查询和对账，新的试做、下单与运营售价均不可再使用这些模板。
DISCONTINUED_PRODUCT_TEMPLATE_IDS = {"10341", "10342"}

SUPPLY_CHAIN_DISABLED_CRAFT_OPTIONS = {
  "5d": {"firstCraft": "17", "firstCraftName": "360度UV打印", "secondCraft": "3", "secondCraftName": "5D打印"},
}


def now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def now_label() -> str:
  return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_local_datetime(value: Any) -> datetime | None:
  if not value:
    return None
  text = str(value).strip()
  for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
    try:
      return datetime.strptime(text, fmt)
    except ValueError:
      pass
  try:
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
  except ValueError:
    return None


def optional_text(value: Any) -> str | None:
  if value is None:
    return None
  text = str(value).strip()
  return text or None


def optional_int(value: Any) -> int | None:
  if value in (None, ""):
    return None
  try:
    return int(value)
  except (TypeError, ValueError):
    return None


def optional_float(value: Any, default: float = 0.0) -> float:
  if value in (None, ""):
    return default
  try:
    return float(value)
  except (TypeError, ValueError):
    return default


def clean_dict(value: dict[str, Any]) -> dict[str, Any]:
  return {key: item for key, item in value.items() if item not in (None, "", [], {})}


def shipping_summary(value: dict[str, Any] | None, fallback: str | None = None) -> str:
  if not value:
    return fallback or "待补充收货信息"
  recipient = str(value.get("recipientName") or "").strip()
  city = str(value.get("city") or "").strip()
  country = str(value.get("country") or "").strip()
  if recipient or city or country:
    return " / ".join(item for item in (recipient, city, country) if item)
  return fallback or "待补充收货信息"


def supply_chain_shipping_fields(value: dict[str, Any]) -> dict[str, Any]:
  return {
    "shipCountry": value.get("country"),
    "shipState": value.get("state"),
    "shipCity": value.get("city"),
    "shipDistrict": value.get("district"),
    "shipPostaCode": value.get("postalCode"),
    "shipEmail": value.get("email"),
    "shipAddress": value.get("address"),
    "shipPhoneNumber": value.get("phoneNumber"),
    "recipientName": value.get("recipientName"),
  }


def redact_shipping(value: dict[str, Any]) -> dict[str, Any]:
  redacted = dict(value)
  if redacted.get("shipPhoneNumber"):
    phone = str(redacted["shipPhoneNumber"])
    redacted["shipPhoneNumber"] = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else "***"
  if redacted.get("shipEmail"):
    redacted["shipEmail"] = "***"
  return redacted


def is_public_http_url(value: Any) -> bool:
  text = str(value or "").strip()
  return text.startswith("https://") or text.startswith("http://")


def public_demo(path: str) -> str:
  return f"{CLIENT_ORIGIN}{path}"


def catalog_product_render_url(product_id: str, size_label: str | None = None) -> str | None:
  """Return the actual catalogue render for a production template, never a generic demo cup."""
  template_id = product_template_id(product_id)
  normalized_size = re.sub(r"[^a-z0-9]+", "", str(size_label or "").lower())
  candidates = []
  if normalized_size:
    candidates.append(f"{template_id}-{normalized_size}.png")
  candidates.append(f"{template_id}-onesize.png")
  for file_name in candidates:
    if (CLIENT_CATALOG_RENDER_DIR / file_name).is_file():
      return public_demo(f"/models/catalog-renders/{file_name}")
  return None


def is_localhost_image_url(value: Any) -> bool:
  text = str(value or "").strip()
  if not text:
    return False
  parsed = urlparse(text)
  if parsed.scheme in {"http", "https"}:
    return (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
  return text.startswith("/demo/") or text.startswith("/media/uploads/")


def local_fetchable_url(value: Any) -> str | None:
  text = str(value or "").strip()
  if not text:
    return None
  parsed = urlparse(text)
  if parsed.scheme in {"http", "https"}:
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
      return None
    return text
  if text.startswith("/demo/") or text.startswith("/media/uploads/"):
    return f"{CLIENT_ORIGIN}{text}" if text.startswith("/demo/") else f"http://127.0.0.1:8240{text}"
  return None


def _oss_endpoint() -> str:
  endpoint = OSS_ENDPOINT
  return endpoint if endpoint.startswith("http") else f"https://{endpoint}"


def upload_model_input_bytes_to_oss(
  *,
  user_id: str,
  source_url: str,
  data: bytes,
  content_type: str | None,
) -> str:
  return upload_image_bytes_to_oss(
    user_id=user_id,
    source_url=source_url,
    data=data,
    content_type=content_type,
    namespace="model-inputs",
  )


def upload_image_bytes_to_oss(
  *,
  user_id: str,
  source_url: str,
  data: bytes,
  content_type: str | None,
  namespace: str,
) -> str:
  if not (OSS_ACCESS_KEY and OSS_SECRET_KEY and OSS_BUCKET):
    raise RuntimeError("OSS credentials missing for asset upload")
  suffix = mimetypes.guess_extension(content_type or "") or Path(urlparse(source_url).path).suffix or ".png"
  safe_suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]+", suffix) else ".png"
  date_str = datetime.utcnow().strftime("%Y%m%d")
  user_part = re.sub(r"[^A-Za-z0-9._-]+", "-", user_id or "system").strip("-") or "system"
  namespace_part = re.sub(r"[^A-Za-z0-9._/-]+", "-", namespace or "assets").strip("/") or "assets"
  prefix = "/".join(segment for segment in [OSS_ROOT_PREFIX, namespace_part, user_part, date_str] if segment)
  object_key = f"{prefix}/{secrets.token_hex(4)}-{int(time.time())}{safe_suffix}"
  auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
  bucket = oss2.Bucket(auth, _oss_endpoint(), OSS_BUCKET, connect_timeout=30)
  headers = {"Content-Type": content_type} if content_type else None
  bucket.put_object(object_key, data, headers=headers)
  return f"{OSS_PUBLIC_DOMAIN}/{quote(object_key, safe='/')}"


def oss_object_key_from_url(value: Any) -> str | None:
  text = str(value or "").strip()
  if not text:
    return None
  parsed = urlparse(text)
  public_domain = urlparse(OSS_PUBLIC_DOMAIN)
  if parsed.scheme not in {"http", "https"} or not parsed.netloc:
    return None
  if parsed.netloc != public_domain.netloc:
    return None
  key = unquote(parsed.path or "").lstrip("/")
  return key or None


def is_oss_asset_url(value: Any) -> bool:
  return bool(oss_object_key_from_url(value))


def fetch_image_bytes_for_asset(value: Any) -> tuple[bytes, str | None, str]:
  text = str(value or "").strip()
  if not text:
    raise ValueError("ASSET_IMAGE_URL_REQUIRED")
  if is_model_data_url(text):
    match = re.match(r"^data:(image/[^;,]+);base64,(.+)$", text, re.I | re.S)
    if not match:
      raise ValueError("ASSET_DATA_URL_INVALID")
    return base64.b64decode(match.group(2)), match.group(1), "data-url"

  candidates = []
  local_url = local_fetchable_url(text)
  if local_url:
    candidates.append(local_url)
    parsed = urlparse(local_url)
    if parsed.path.startswith("/demo/"):
      for origin in (CLIENT_ORIGIN, "http://127.0.0.1:5180", "http://127.0.0.1:8230"):
        candidate = f"{origin.rstrip('/')}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
        if candidate not in candidates:
          candidates.append(candidate)
  elif is_public_http_url(text):
    candidates.append(text)
  else:
    raise ValueError("ASSET_IMAGE_URL_UNSUPPORTED")

  last_error: Exception | None = None
  for candidate in candidates:
    try:
      request = urllib.request.Request(candidate, headers={"User-Agent": "PODI-BusinessAPI/asset-oss-ingest"})
      parsed = urlparse(candidate)
      context = HUMCUSTOM_SSL_CONTEXT if parsed.scheme == "https" else None
      open_kwargs = {"timeout": 20}
      if context is not None:
        open_kwargs["context"] = context
      with urllib.request.urlopen(request, **open_kwargs) as response:  # type: ignore[arg-type]
        content_type = response.headers.get("content-type") or mimetypes.guess_type(urlparse(candidate).path)[0] or "image/png"
        data = response.read(MODEL_INPUT_UPLOAD_MAX_BYTES + 1)
      if len(data) > MODEL_INPUT_UPLOAD_MAX_BYTES:
        raise ValueError("ASSET_IMAGE_TOO_LARGE_FOR_UPLOAD")
      return data, content_type, candidate
    except Exception as exc:  # noqa: BLE001 - try alternate local dev origins
      last_error = exc
  raise RuntimeError(f"asset image fetch failed: {last_error}")


def mark_asset_oss_metadata(asset: dict[str, Any], url: str, *, original_url: str | None = None, reason: str = "auto") -> bool:
  metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
  changed = False
  object_key = oss_object_key_from_url(url)
  if object_key and metadata.get("ossKey") != object_key:
    metadata["ossKey"] = object_key
    changed = True
  if url and metadata.get("ossUrl") != url:
    metadata["ossUrl"] = url
    changed = True
  if metadata.get("storageProvider") != "aliyun-oss":
    metadata["storageProvider"] = "aliyun-oss"
    changed = True
  if metadata.get("ossStatus") != "stored":
    metadata["ossStatus"] = "stored"
    changed = True
  if original_url and original_url != url and not metadata.get("originalUrl"):
    metadata["originalUrl"] = original_url
    changed = True
  if reason and metadata.get("ossLastReason") != reason:
    metadata["ossLastReason"] = reason
    changed = True
  if changed:
    metadata["ossStoredAt"] = metadata.get("ossStoredAt") or now_label()
    asset["metadata"] = metadata
  return changed


def ensure_asset_oss(user_id: str, asset: dict[str, Any], *, reason: str = "asset-management") -> bool:
  if asset.get("removedAt") or asset.get("visibility") == "deleted":
    return False
  url = str(asset.get("url") or asset.get("thumbnailUrl") or "").strip()
  if not url:
    return False
  if is_oss_asset_url(url):
    return mark_asset_oss_metadata(asset, url, reason=reason)

  data, content_type, source_url = fetch_image_bytes_for_asset(url)
  oss_url = upload_image_bytes_to_oss(
    user_id=user_id,
    source_url=source_url,
    data=data,
    content_type=content_type,
    namespace="assets",
  )
  previous_url = str(asset.get("url") or "")
  previous_thumb = str(asset.get("thumbnailUrl") or "")
  asset["url"] = oss_url
  if not previous_thumb or previous_thumb == previous_url or is_localhost_image_url(previous_thumb):
    asset["thumbnailUrl"] = oss_url
  mark_asset_oss_metadata(asset, oss_url, original_url=previous_url, reason=reason)
  enrich_asset_dimensions(asset)
  return True


def prepare_asset_for_storage(user_id: str, asset: dict[str, Any], *, reason: str) -> bool:
  try:
    return ensure_asset_oss(user_id, asset, reason=reason)
  except Exception as exc:  # noqa: BLE001 - asset remains usable, status is visible in ops
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    metadata["ossStatus"] = "failed"
    metadata["ossLastError"] = str(exc)
    metadata["ossLastErrorAt"] = now_label()
    metadata["ossLastReason"] = reason
    asset["metadata"] = metadata
    return False


def create_verified_seamless_artwork(
  *,
  user_id: str,
  source_url: str,
  title: str,
  width: int,
  height: int,
  dpi: int,
  source_asset_id: str | None = None,
  business_run_id: str | None = None,
) -> dict[str, Any]:
  if width < 64 or height < 64 or width > 10000 or height > 10000:
    raise ValueError("CLIENT_PRODUCTION_ARTWORK_SIZE_INVALID")
  try:
    from PIL import Image  # type: ignore
  except Exception as exc:  # noqa: BLE001 - this is a deploy dependency failure
    raise RuntimeError("CLIENT_PRODUCTION_ARTWORK_PROCESS_UNAVAILABLE") from exc

  data, _content_type, fetched_url = fetch_image_bytes_for_asset(source_url)
  try:
    with Image.open(BytesIO(data)) as source_image:
      artwork = source_image.convert("RGBA")
      if artwork.size != (width, height):
        artwork = artwork.resize((width, height), Image.Resampling.LANCZOS)
      pixels = artwork.load()
      for y in range(height):
        pixels[width - 1, y] = pixels[0, y]
      for x in range(width):
        pixels[x, height - 1] = pixels[x, 0]
      output = BytesIO()
      artwork.save(output, format="PNG", optimize=True)
  except Exception as exc:  # noqa: BLE001 - keep image internals out of client errors
    raise RuntimeError("CLIENT_PRODUCTION_ARTWORK_PROCESS_FAILED") from exc

  oss_url = upload_image_bytes_to_oss(
    user_id=user_id,
    source_url=fetched_url,
    data=output.getvalue(),
    content_type="image/png",
    namespace="production-artwork",
  )
  asset = {
    "id": "asset-" + secrets.token_hex(6),
    "type": "pattern",
    "title": title,
    "url": oss_url,
    "thumbnailUrl": oss_url,
    "source": "产品设计 · AI 四方连续",
    "createdAt": now_label(),
    "selected": False,
    "favorite": False,
    "visibility": "private",
    "licenseMode": "private",
    "licenseSource": "created",
    "usedInProducts": 0,
    "width": width,
    "height": height,
    "dpi": dpi,
    "metadata": {
      "seamless": True,
      "tileable": True,
      "isSeamless": True,
      "seamlessVerified": True,
      "productionValidation": "verified",
      "productionValidationMethod": "target-size-export-edge-pixel-lock",
      "seamlessEdgeCheck": {
        "leftRight": "exact",
        "topBottom": "exact",
        "width": width,
        "height": height,
      },
      "sourceAssetId": source_asset_id or None,
      "sourceUrl": source_url,
      "businessRunId": business_run_id or None,
      "outputWidth": width,
      "outputHeight": height,
      "dpi": dpi,
    },
  }
  mark_asset_oss_metadata(asset, oss_url, original_url=source_url, reason="production-seamless-export")
  ensure_bucket("assets", user_id).insert(0, asset)
  save_state(STATE)
  return asset


def asset_storage_status(asset: dict[str, Any]) -> str:
  metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
  if asset.get("removedAt") or asset.get("visibility") == "deleted":
    return "deleted"
  if metadata.get("ossDeletedAt"):
    return "oss_deleted"
  if is_oss_asset_url(asset.get("url")) or metadata.get("ossStatus") == "stored":
    return "oss"
  if is_localhost_image_url(asset.get("url")) or is_localhost_image_url(asset.get("thumbnailUrl")):
    return "local"
  if is_public_http_url(asset.get("url")):
    return "external"
  return "unknown"


def delete_oss_objects_for_asset(asset: dict[str, Any]) -> dict[str, Any]:
  if not (OSS_ACCESS_KEY and OSS_SECRET_KEY and OSS_BUCKET):
    raise RuntimeError("OSS credentials missing for asset deletion")
  metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
  keys = []
  for candidate in (metadata.get("ossKey"), asset.get("url"), asset.get("thumbnailUrl")):
    key = str(candidate or "").strip()
    if not key:
      continue
    if key.startswith("http://") or key.startswith("https://"):
      key = oss_object_key_from_url(key) or ""
    if key and key not in keys:
      keys.append(key)
  if not keys:
    return {"deletedKeys": [], "message": "没有可删除的 OSS 对象。"}
  auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
  bucket = oss2.Bucket(auth, _oss_endpoint(), OSS_BUCKET, connect_timeout=30)
  deleted = []
  for key in keys:
    bucket.delete_object(key)
    deleted.append(key)
  return {"deletedKeys": deleted}


def ensure_model_readable_image_url(value: Any, *, user_id: str) -> tuple[str, str | None]:
  text = str(value or "").strip()
  if not text or is_remote_model_image_url(text):
    return text, None
  first_fetch_url = local_fetchable_url(text)
  if not first_fetch_url:
    return text, None
  parsed = urlparse(first_fetch_url)
  candidates = [first_fetch_url]
  if parsed.path.startswith("/demo/"):
    for origin in (CLIENT_ORIGIN, "http://127.0.0.1:5180", "http://127.0.0.1:8230"):
      candidate = f"{origin.rstrip('/')}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
      if candidate not in candidates:
        candidates.append(candidate)
  last_error: Exception | None = None
  content_type = None
  data = b""
  fetch_url = first_fetch_url
  for candidate in candidates:
    try:
      with urllib.request.urlopen(candidate, timeout=15) as response:
        content_type = response.headers.get("content-type") or mimetypes.guess_type(urlparse(candidate).path)[0] or "image/png"
        data = response.read(MODEL_INPUT_UPLOAD_MAX_BYTES + 1)
        fetch_url = candidate
        break
    except Exception as exc:  # noqa: BLE001 - try next local dev origin
      last_error = exc
  else:
    raise RuntimeError(f"local image fetch failed: {last_error}")
  if len(data) > MODEL_INPUT_UPLOAD_MAX_BYTES:
    raise ValueError("MODEL_INPUT_TOO_LARGE_FOR_UPLOAD")
  oss_url = upload_model_input_bytes_to_oss(user_id=user_id, source_url=fetch_url, data=data, content_type=content_type)
  return oss_url, text


def normalize_model_input_urls(value: Any, *, user_id: str, rewrites: list[dict[str, str]]) -> Any:
  if isinstance(value, str):
    if not is_localhost_image_url(value):
      return value
    next_url, previous_url = ensure_model_readable_image_url(value, user_id=user_id)
    if previous_url and next_url != previous_url:
      rewrites.append({"from": previous_url, "to": next_url})
    return next_url
  if isinstance(value, list):
    return [normalize_model_input_urls(item, user_id=user_id, rewrites=rewrites) for item in value]
  if isinstance(value, dict):
    normalized: dict[str, Any] = {}
    for key, item in value.items():
      lowered = str(key).lower()
      if lowered in {"imageurl", "image_url", "url", "thumbnailurl", "thumbnail_url"}:
        normalized[key] = normalize_model_input_urls(item, user_id=user_id, rewrites=rewrites)
      elif lowered in {"referenceimages", "reference_images", "imageurls", "image_urls", "input_urls", "inputurls", "images"}:
        normalized[key] = normalize_model_input_urls(item, user_id=user_id, rewrites=rewrites)
      elif lowered == "metadata" and isinstance(item, dict):
        metadata = dict(item)
        for meta_key in ("referenceImageUrls", "reference_image_urls", "sourceImageUrl", "source_image_url"):
          if meta_key in metadata:
            metadata[meta_key] = normalize_model_input_urls(metadata[meta_key], user_id=user_id, rewrites=rewrites)
        normalized[key] = metadata
      else:
        normalized[key] = item
    return normalized
  return value


def normalize_local_demo_urls(value: Any) -> bool:
  """Rewrite stale localhost demo asset origins to the current client origin."""
  changed = False
  if isinstance(value, dict):
    for key, item in list(value.items()):
      if isinstance(item, str):
        next_value = re.sub(
          r"^https?://(?:127\.0\.0\.1|localhost):\d+(/demo/)",
          f"{CLIENT_ORIGIN}\\1",
          item,
        )
        if next_value != item:
          value[key] = next_value
          changed = True
      elif isinstance(item, (dict, list)):
        changed = normalize_local_demo_urls(item) or changed
  elif isinstance(value, list):
    for index, item in enumerate(list(value)):
      if isinstance(item, str):
        next_value = re.sub(
          r"^https?://(?:127\.0\.0\.1|localhost):\d+(/demo/)",
          f"{CLIENT_ORIGIN}\\1",
          item,
        )
        if next_value != item:
          value[index] = next_value
          changed = True
      elif isinstance(item, (dict, list)):
        changed = normalize_local_demo_urls(item) or changed
  return changed


def is_remote_model_image_url(value: Any) -> bool:
  text = str(value or "").strip()
  if not (text.startswith("https://") or text.startswith("http://")):
    return False
  parsed = urlparse(text)
  host = (parsed.hostname or "").lower()
  return host not in {"127.0.0.1", "localhost", "::1"}


def is_model_data_url(value: Any) -> bool:
  return bool(re.match(r"^data:image/[^;,]+;base64,", str(value or "").strip(), re.I))


def local_upload_path_from_url(value: Any) -> Path | None:
  text = str(value or "").strip()
  if not text:
    return None
  parsed = urlparse(text)
  if parsed.scheme in {"http", "https"}:
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
      return None
    path = parsed.path
  else:
    path = text
  if not path.startswith("/media/uploads/"):
    return None
  relative = unquote(path.removeprefix("/media/uploads/"))
  target = (UPLOAD_DIR / relative).resolve()
  try:
    if not str(target).startswith(str(UPLOAD_DIR.resolve())) or not target.exists() or not target.is_file():
      return None
  except OSError:
    return None
  return target


def local_upload_data_url(value: Any) -> str | None:
  target = local_upload_path_from_url(value)
  if not target:
    return None
  mime = mimetypes.guess_type(str(target))[0] or "image/png"
  try:
    encoded = base64.b64encode(target.read_bytes()).decode("ascii")
  except OSError:
    return None
  return f"data:{mime};base64,{encoded}"


def model_image_input_for_asset(asset: dict[str, Any] | None) -> tuple[str | None, str]:
  if not asset:
    return None, "none"
  image_url = str(asset.get("url") or asset.get("thumbnailUrl") or "").strip()
  if is_model_data_url(image_url):
    return image_url, "data_url"
  if is_remote_model_image_url(image_url):
    return image_url, "remote_url"
  local_data_url = local_upload_data_url(image_url)
  if local_data_url:
    return local_data_url, "local_upload_data_url"
  return image_url or None, "unsupported_url" if image_url else "none"


def extract_json_object(text: str) -> dict[str, Any] | None:
  raw = (text or "").strip()
  if not raw:
    return None
  if raw.startswith("```"):
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
  try:
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else None
  except json.JSONDecodeError:
    pass
  start = raw.find("{")
  end = raw.rfind("}")
  if start >= 0 and end > start:
    try:
      parsed = json.loads(raw[start : end + 1])
      return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
      return None
  return None


def text_list(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item or "").strip()]
  text = str(value).strip()
  return [text] if text else []


def volcengine_response_text(payload: dict[str, Any]) -> str:
  if not isinstance(payload, dict):
    return ""
  output_text = payload.get("output_text")
  if isinstance(output_text, str):
    return output_text
  choices = payload.get("choices")
  if isinstance(choices, list) and choices:
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
      return content
    if isinstance(content, list):
      texts = []
      for item in content:
        if isinstance(item, dict):
          value = item.get("text") or item.get("content")
          if isinstance(value, str):
            texts.append(value)
      return "\n".join(texts)
  output = payload.get("output")
  if isinstance(output, list):
    texts = []
    for block in output:
      if not isinstance(block, dict):
        continue
      content = block.get("content")
      if isinstance(content, list):
        for item in content:
          if isinstance(item, dict):
            value = item.get("text") or item.get("content")
            if isinstance(value, str):
              texts.append(value)
      elif isinstance(content, str):
        texts.append(content)
    return "\n".join(texts)
  return ""


def volcengine_ark_request(path: str, payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
  if not VOLCENGINE_ARK_API_KEY:
    raise RuntimeError("VOLCENGINE_ARK_API_KEY is not configured")
  data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
  request = urllib.request.Request(
    f"{VOLCENGINE_ARK_BASE}{path}",
    data=data,
    headers={
      "Authorization": f"Bearer {VOLCENGINE_ARK_API_KEY}",
      "Content-Type": "application/json",
    },
    method="POST",
  )
  with urllib.request.urlopen(request, timeout=timeout or AGENT_VL_TIMEOUT_SECONDS, context=HUMCUSTOM_SSL_CONTEXT) as response:
    return json.loads(response.read().decode("utf-8"))


def agent_vl_prompt(
  product_context: dict[str, Any] | None,
  user_message: str,
  asset: dict[str, Any] | None = None,
  assets: list[dict[str, Any]] | None = None,
  intent_hint: str | None = None,
  reference_instruction: str | None = None,
) -> str:
  surfaces = product_surface_defaults(product_context)
  surface_text = [
    {
      "surfaceId": item.get("name"),
      "label": item.get("label"),
      "width": item.get("width"),
      "height": item.get("height"),
      "role": item.get("role"),
      "supportsWrap": item.get("supportsWrap"),
      "supportsHandleTexture": item.get("supportsHandleTexture"),
    }
    for item in surfaces
  ]
  product_name = (product_context or {}).get("productName") or "当前商品"
  asset_list = assets if isinstance(assets, list) and assets else ([asset] if asset else [])
  asset_context = [
    {
      "index": index + 1,
      "title": item.get("title"),
      "type": item.get("type"),
      "source": item.get("source"),
    }
    for index, item in enumerate(asset_list)
    if isinstance(item, dict)
  ]
  return (
    "你是 POD 定制商品的视觉设计路由分析员。你的任务不是生成图片，而是根据图片、"
    "用户需求和商品贴图面约束，判断下一步应该走哪条可生产的设计路线。"
    "只输出 JSON，不要输出 Markdown，不要解释 JSON 以外的内容。\n"
    f"商品: {product_name}\n"
    f"贴图面: {json.dumps(surface_text, ensure_ascii=False)}\n"
    f"素材上下文: {json.dumps([clean_dict(item) for item in asset_context], ensure_ascii=False)}\n"
    f"多图参考关系: {reference_instruction or '未指定；如有多张图，请判断它们分别承担色调、元素、构图或主体参考。'}\n"
    f"业务端初判: {intent_hint or 'unknown'}\n"
    f"用户需求: {user_message or '用户希望获得适合生产的设计方案'}\n"
    "可选 recommendedIntent 只能是: print_as_is, clean_and_print, extract_pattern, "
    "make_seamless_wrap, generate_variations, ai_recreate, compose_product_design, clarify。\n"
    "imageType 尽量使用: logo, text_screenshot, child_drawing, personal_photo, product_photo, "
    "fabric_or_wallpaper, pattern_asset, low_quality_image, prompt_only, unknown。\n"
    "layoutMode 只能是: decal, wrap, fit, manual。\n"
    "qualityRisk 尽量使用 low/medium/high，并在 risks 中写清原因。\n"
    "判断优先级:\n"
    "1. 只有用户明确说原样、直接印、不要改、Logo/头像/名字/文字标志时，才推荐 print_as_is，layoutMode=decal。\n"
    "2. 如果用户说帮我设计、参考这张图、做同风格、做一款产品、生成一套方案，即使上传了图片，也应优先推荐 ai_recreate 或 extract_pattern，不要把原图直接贴到商品上。\n"
    "3. 孩子绘画、纪念照片、手拍照片不要擅自花纹化；先 clarify，询问保留原画感、清理增强还是重绘。\n"
    "4. 花布、壁纸、图案、装饰纹理优先 extract_pattern；如果用户明确要杯身环绕/无缝/接缝，则推荐 make_seamless_wrap。\n"
    "5. 低清、噪点、截图压缩、文字密集图片应优先 clarify；可建议 clean_and_print 或 ai_recreate，但不要直接进入生产。\n"
    "6. 截图、表格、网页 UI、参数页、聊天记录不是正常装饰素材，默认 clarify，询问是否误传或是否要重新排版。\n"
    "7. 只文字需求或需要原创视觉时推荐 ai_recreate，但必须提示后续要裁切/扩图/缩放到贴图面尺寸。\n"
    "8. Image2 只能负责生成/重绘/风格化，不能保证目标比例、DPI、连续图；需要后处理或连续图能力时必须在 risks/observations 标明。\n"
    "9. 杯身满版环绕不能简单把主体图强行平铺；如果图里有明确主体，应优先建议生成可连续背景，再把主体作为局部/中心元素组合。\n"
    "10. 所有进入生产的结果都必须适配到商品贴图面的精确像素尺寸；差几个像素可以拉伸/补边，比例差异大时必须裁切、扩图或重绘。\n"
    "11. 如果不能确认无缝连续，必须把接缝风险写进 risks，并建议用户先做连续图或改为局部印刷。\n"
    "12. 如果图片可用但设计方向不唯一，needsUserConfirmation=true，并提出 1-3 个用户能理解的问题。\n"
    "JSON 字段必须包含: imageType, printable, qualityRisk, recommendedIntent, "
    "recommendedSurfaceId, layoutMode, needsSeamless, needsImage2, needsUserConfirmation, "
    "confidence, observations, risks, questions。confidence 用 0-1 数字。"
  )


def call_volcengine_vision_analysis(
  image_url: str | None,
  user_message: str,
  product_context: dict[str, Any] | None,
  provider: str,
  asset: dict[str, Any] | None = None,
  image_urls: list[str] | None = None,
  assets: list[dict[str, Any]] | None = None,
  intent_hint: str | None = None,
  reference_instruction: str | None = None,
) -> dict[str, Any]:
  model = AGENT_PLANNER_MODEL if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
  prompt = agent_vl_prompt(
    product_context,
    user_message,
    asset=asset,
    assets=assets,
    intent_hint=intent_hint,
    reference_instruction=reference_instruction,
  )
  usable_image_urls = list(dict.fromkeys([str(item) for item in (image_urls or ([image_url] if image_url else [])) if str(item or "").strip()]))
  if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} or "2-1" in model:
    content: list[dict[str, Any]] = []
    for current_url in usable_image_urls:
      content.append({"type": "image_url", "image_url": {"url": current_url}})
    content.append({"type": "text", "text": prompt})
    payload = {"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0.1}
    response = volcengine_ark_request("/api/v3/chat/completions", payload)
  else:
    content = []
    for current_url in usable_image_urls:
      content.append({"type": "input_image", "image_url": current_url})
    content.append({"type": "input_text", "text": prompt})
    payload = {"model": model, "input": [{"role": "user", "content": content}], "temperature": 0.1}
    response = volcengine_ark_request("/api/v3/responses", payload)
  parsed = extract_json_object(volcengine_response_text(response))
  if not parsed:
    raise RuntimeError("Volcengine VL did not return valid JSON")
  return parsed


def heuristic_vision_analysis(
  asset: dict[str, Any] | None,
  message: str,
  product_context: dict[str, Any] | None,
  intent_hint: str,
) -> dict[str, Any]:
  text = " ".join([
    str(message or ""),
    str((asset or {}).get("title") or ""),
    str((asset or {}).get("source") or ""),
  ]).lower()
  image_type = "unknown"
  if any(word in text for word in ("logo", "标志", "商标")):
    image_type = "logo"
  elif any(word in text for word in ("孩子", "手绘", "绘画", "原画")):
    image_type = "child_drawing"
  elif any(word in text for word in ("花布", "壁纸", "花纹", "图案")):
    image_type = "pattern"
  elif any(word in text for word in ("低清", "模糊", "像素低", "不清晰")):
    image_type = "low_quality_photo"
  elif asset:
    image_type = str(asset.get("type") or "image")
  surfaces = product_surface_defaults(product_context)
  surface_id = str((surfaces[0] if surfaces else {}).get("name") or "front")
  return {
    "provider": "heuristic",
    "model": "local-rules",
    "imageType": image_type,
    "printable": image_type != "unknown",
    "qualityRisk": "high" if image_type == "low_quality_photo" else "medium" if image_type == "unknown" else "low",
    "recommendedIntent": intent_hint,
    "recommendedSurfaceId": surface_id,
    "layoutMode": "wrap" if intent_hint == "make_seamless_wrap" else "decal" if intent_hint == "print_as_is" else "fit",
    "needsSeamless": intent_hint == "make_seamless_wrap",
    "needsImage2": intent_hint == "ai_recreate",
    "needsUserConfirmation": intent_hint == "clarify",
    "confidence": 0.62 if image_type == "unknown" else 0.78,
    "observations": ["本地规则分析，未调用外部 VL。"],
    "risks": ["需要真实 VL 复核。"] if image_type == "unknown" else [],
    "questions": [],
  }


def analyze_agent_visual_context(
  user_id: str,
  asset_ids: list[str] | None,
  message: str,
  product_context: dict[str, Any] | None,
  intent_hint: str,
) -> dict[str, Any]:
  assets = user_assets_by_ids(user_id, asset_ids)
  asset = assets[0] if assets else None
  image_inputs: list[str] = []
  image_transports: list[str] = []
  unsupported_count = 0
  for current_asset in assets:
    image_input, image_transport = model_image_input_for_asset(current_asset)
    if image_input and image_transport != "unsupported_url":
      image_inputs.append(image_input)
    elif image_input and image_transport == "unsupported_url":
      unsupported_count += 1
    if image_transport:
      image_transports.append(image_transport)
  image_transport = ",".join(list(dict.fromkeys(image_transports))) if image_transports else "none"
  reference_instruction = reference_role_instruction_from_text(message, assets)
  provider = AGENT_VL_PROVIDER or "heuristic"
  if provider in {"", "heuristic", "local"}:
    return heuristic_vision_analysis(asset, message, product_context, intent_hint)
  if not VOLCENGINE_ARK_API_KEY:
    result = heuristic_vision_analysis(asset, message, product_context, intent_hint)
    attempted_model = AGENT_PLANNER_MODEL if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
    result.update({
      "provider": provider,
      "model": attempted_model,
      "skippedReason": "VOLCENGINE_ARK_API_KEY 未配置",
      "fallback": "heuristic",
      "sourceAssetIds": [item.get("id") for item in assets if item.get("id")],
      "imageCount": len(assets),
      "referenceInstruction": reference_instruction,
    })
    return result

  if assets and not image_inputs and unsupported_count:
    result = heuristic_vision_analysis(asset, message, product_context, intent_hint)
    attempted_model = AGENT_PLANNER_MODEL if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
    result.update({
      "provider": provider,
      "model": attempted_model,
      "skippedReason": "图片不是公网 URL，且本地文件不可读取，VL 服务无法读取",
      "imageTransport": image_transport,
      "fallback": "heuristic",
      "sourceAssetIds": [item.get("id") for item in assets if item.get("id")],
      "imageCount": len(assets),
      "referenceInstruction": reference_instruction,
    })
    return result
  try:
    analysis = call_volcengine_vision_analysis(
      image_inputs[0] if image_inputs else None,
      message,
      product_context,
      provider,
      asset=asset,
      assets=assets,
      image_urls=image_inputs,
      intent_hint=intent_hint,
      reference_instruction=reference_instruction,
    )
    analysis["provider"] = provider
    analysis["model"] = AGENT_PLANNER_MODEL if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
    analysis["sourceAssetId"] = (asset or {}).get("id")
    analysis["sourceAssetIds"] = [item.get("id") for item in assets if item.get("id")]
    analysis["imageCount"] = len(assets)
    analysis["imageTransport"] = image_transport
    analysis["referenceInstruction"] = reference_instruction
    return analysis
  except Exception as exc:
    if provider not in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"}:
      try:
        analysis = call_volcengine_vision_analysis(
          image_inputs[0] if image_inputs else None,
          message,
          product_context,
          "volcengine-doubao-turbo",
          asset=asset,
          assets=assets,
          image_urls=image_inputs,
          intent_hint=intent_hint,
          reference_instruction=reference_instruction,
        )
        analysis["provider"] = "volcengine-doubao-turbo"
        analysis["model"] = AGENT_PLANNER_MODEL
        analysis["sourceAssetId"] = (asset or {}).get("id")
        analysis["sourceAssetIds"] = [item.get("id") for item in assets if item.get("id")]
        analysis["imageCount"] = len(assets)
        analysis["imageTransport"] = image_transport
        analysis["referenceInstruction"] = reference_instruction
        analysis["fallbackFrom"] = provider
        return analysis
      except Exception as fallback_exc:
        exc = fallback_exc
    result = heuristic_vision_analysis(asset, message, product_context, intent_hint)
    attempted_model = AGENT_PLANNER_MODEL if provider in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
    result.update({
      "provider": provider,
      "model": attempted_model,
      "modelError": str(exc)[:240],
      "fallback": "heuristic",
      "imageTransport": image_transport,
      "recommendedIntent": "clarify" if asset else result.get("recommendedIntent"),
      "needsUserConfirmation": True if asset else result.get("needsUserConfirmation"),
      "confidence": 0.42 if asset else result.get("confidence"),
      "sourceAssetIds": [item.get("id") for item in assets if item.get("id")],
      "imageCount": len(assets),
      "referenceInstruction": reference_instruction,
    })
    return result


def prompt_only_agent_analysis(
  message: str,
  product_context: dict[str, Any] | None,
  intent_hint: str,
) -> dict[str, Any]:
  surfaces = product_surface_defaults(product_context)
  surface_id = str((surfaces[0] if surfaces else {}).get("name") or "front")
  intended = intent_hint if intent_hint in ALLOWED_AGENT_INTENTS else "compose_product_design"
  if intended == "clarify" and (message or "").strip():
    intended = "ai_recreate"
  return {
    "provider": "business-rules",
    "model": "prompt-only-product-design",
    "source": "prompt_only",
    "imageType": "prompt_only",
    "printable": True,
    "qualityRisk": "unknown",
    "recommendedIntent": intended,
    "recommendedSurfaceId": surface_id,
    "layoutMode": "wrap" if intended in {"make_seamless_wrap", "compose_product_design"} else "fit",
    "needsSeamless": intended == "make_seamless_wrap",
    "needsImage2": intended in {"ai_recreate", "compose_product_design"},
    "needsUserConfirmation": False,
    "confidence": 0.72,
    "observations": ["用户没有提供参考图，本次按纯文字产品设计需求进入方案规划。"],
    "risks": ["AI 生成图仍需后处理到商品贴图面的精确尺寸和 DPI。"],
    "questions": [],
  }


def default_state() -> dict[str, Any]:
  assets = [
    {
      "id": "asset-1",
      "type": "pattern",
      "title": "复古花卉连续图案",
      "url": public_demo("/demo/market/pattern-vintage-floral.webp"),
      "thumbnailUrl": public_demo("/demo/market/pattern-vintage-floral.webp"),
      "source": "花纹提取结果",
      "createdAt": "2026-06-20 10:00",
      "selected": False,
      "favorite": False,
      "visibility": "public",
      "licenseMode": "free_reuse",
      "licenseSource": "created",
      "author": "designer_liu",
      "usedInProducts": 3,
    },
    {
      "id": "asset-2",
      "type": "variation",
      "title": "蓝绿花园裂变图",
      "url": public_demo("/demo/market/pattern-garden.webp"),
      "thumbnailUrl": public_demo("/demo/market/pattern-garden.webp"),
      "source": "图案裂变结果",
      "createdAt": "2026-06-20 10:05",
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "created",
      "usedInProducts": 1,
    },
    {
      "id": "asset-3",
      "type": "processed",
      "title": "粉橙花束处理图",
      "url": public_demo("/demo/market/pattern-bloom.webp"),
      "thumbnailUrl": public_demo("/demo/market/pattern-bloom.webp"),
      "source": "图片标准化",
      "createdAt": "2026-06-19 16:30",
      "selected": False,
      "favorite": False,
      "visibility": "reviewing",
      "licenseMode": "paid_points",
      "licenseSource": "created",
      "licensePoints": 32,
      "usedInProducts": 0,
    },
    {
      "id": "asset-4",
      "type": "pattern",
      "title": "深色植物夜花纹",
      "url": public_demo("/demo/market/pattern-dark-botanical.webp"),
      "thumbnailUrl": public_demo("/demo/market/pattern-dark-botanical.webp"),
      "source": "上传图片提取",
      "createdAt": "2026-06-19 14:20",
      "selected": False,
      "favorite": True,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "created",
      "usedInProducts": 2,
    },
    {
      "id": "asset-7",
      "type": "pattern",
      "title": "已授权 · 蓝绿抽象花纹",
      "url": public_demo("/demo/market/pattern-garden.webp"),
      "thumbnailUrl": public_demo("/demo/market/pattern-garden.webp"),
      "source": "灵感广场授权",
      "createdAt": "2026-06-21 15:12",
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "paid_points",
      "licenseSource": "purchased",
      "licensePoints": 24,
      "author": "pattern_lab",
      "acquiredAt": "2026-06-21 15:12",
      "usedInProducts": 0,
    },
    {
      "id": "asset-8",
      "type": "product_preview",
      "title": "产品预览 · 复古花卉杯",
      "url": public_demo("/demo/market/product-mug-coral-navy.png"),
      "thumbnailUrl": public_demo("/demo/market/product-mug-coral-navy.png"),
      "source": "产品试做生成",
      "createdAt": "2026-06-21 18:40",
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "product_snapshot",
      "usedInProducts": 1,
    },
  ]
  return {
    "users": {},
    "sessions": {},
    "designAgentSessions": {},
    "assets": {"demo-user": assets},
    "tasks": {"demo-user": []},
    "orders": {"demo-user": []},
    "commerce": {
      "shippingFeeCents": 1000,
      "shippingConfigured": True,
      "shippingOptions": [dict(item) for item in DEFAULT_SHIPPING_OPTIONS],
      "currency": "CNY",
      "productPrices": {},
    },
    "wallets": {},
    "couponCampaigns": [],
    "redemptionCodes": [],
    "publishApplications": {"demo-user": []},
    "complaints": {"demo-user": []},
    "smsCodes": {},
  }


def load_state() -> dict[str, Any]:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
  if not STATE_PATH.exists():
    state = default_state()
    save_state(state)
    return state
  try:
    with STATE_PATH.open("r", encoding="utf-8") as handle:
      state = json.load(handle)
  except Exception:
    state = default_state()
  for key, fallback in default_state().items():
    state.setdefault(key, fallback)
  return state


def save_state(state: dict[str, Any]) -> None:
  DATA_DIR.mkdir(parents=True, exist_ok=True)
  tmp = STATE_PATH.with_suffix(".tmp")
  with tmp.open("w", encoding="utf-8") as handle:
    json.dump(state, handle, ensure_ascii=False, indent=2)
  tmp.replace(STATE_PATH)


def commerce_config() -> dict[str, Any]:
  config = STATE.setdefault("commerce", {})
  raw_options = config.get("shippingOptions")
  normalized_options: list[dict[str, Any]] = []
  if isinstance(raw_options, list):
    seen: set[str] = set()
    labels = {item["id"]: item["label"] for item in DEFAULT_SHIPPING_OPTIONS}
    for raw in raw_options:
      if not isinstance(raw, dict):
        continue
      option_id = str(raw.get("id") or "").strip().lower()
      fee_cents = optional_int(raw.get("feeCents"))
      if option_id not in labels or option_id in seen or fee_cents is None or fee_cents < 0 or fee_cents > 200000:
        continue
      normalized_options.append({"id": option_id, "label": labels[option_id], "feeCents": fee_cents})
      seen.add(option_id)
  if len(normalized_options) != len(DEFAULT_SHIPPING_OPTIONS):
    legacy_fee = optional_int(config.get("shippingFeeCents"))
    normalized_options = [dict(item) for item in DEFAULT_SHIPPING_OPTIONS]
    if legacy_fee is not None and legacy_fee > 0:
      normalized_options[0]["feeCents"] = legacy_fee
  config["shippingOptions"] = normalized_options
  config["shippingFeeCents"] = next(item["feeCents"] for item in normalized_options if item["id"] == "zto")
  # The two delivery methods are an explicit business decision, not a client-side default.
  config["shippingConfigured"] = True
  config.setdefault("currency", "POINT")
  config.setdefault("productPrices", {})
  config.setdefault("productCosts", {})
  return config


def commerce_config_snapshot() -> dict[str, Any]:
  config = commerce_config()
  return {
    "shippingFeeCents": max(0, optional_int(config.get("shippingFeeCents")) or 0),
    "shippingConfigured": bool(config.get("shippingConfigured")),
    "shippingOptions": [dict(item) for item in config["shippingOptions"]],
    "currency": "POINT",
  }


def product_pricing_snapshot() -> list[dict[str, Any]]:
  config = commerce_config()
  prices = config.get("productPrices") if isinstance(config.get("productPrices"), dict) else {}
  rows: list[dict[str, Any]] = []
  for product_id, product in SUPPLY_CHAIN_PRODUCT_OVERRIDES.items():
    if product_id in DISCONTINUED_PRODUCT_TEMPLATE_IDS:
      continue
    configured_price = optional_int(prices.get(product_id))
    cost_price_cents, cost_source = product_cost_quote(product_id, str(product.get("name") or ""))
    rows.append({
      "productId": product_id,
      "productName": product.get("name") or product_id,
      "costPriceCents": cost_price_cents,
      "costSource": cost_source,
      "recommendedSalePriceCents": recommended_sale_price_cents(cost_price_cents),
      "salePriceCents": configured_price if configured_price and configured_price > 0 else None,
      "costPricePoints": max(1, int(round(cost_price_cents / 100))),
      "recommendedSalePricePoints": max(1, int(round(recommended_sale_price_cents(cost_price_cents) / 100))),
      "salePricePoints": max(1, int(round(configured_price / 100))) if configured_price and configured_price > 0 else None,
    })
  return sorted(rows, key=lambda item: str(item["productId"]), reverse=True)


def public_product_pricing_snapshot() -> list[dict[str, Any]]:
  return [
    {
      "productId": item["productId"],
      "productName": item["productName"],
      "salePriceCents": item["salePriceCents"],
      "salePricePoints": item["salePricePoints"],
    }
    for item in product_pricing_snapshot()
  ]


def product_cost_price_cents(product_id: str, name: str) -> int:
  known = {
    "10395": 3980,
    "10385": 3280,
    "10376": 4280,
    "10256": 4580,
    "10238": 2280,
    "10236": 2360,
  }
  if product_id in known:
    return known[product_id]
  if any(token in name for token in ("太空壶", "手提杯", "手柄杯")):
    return 5580
  if any(token in name for token in ("保温", "汽车杯", "运动水壶")):
    return 4280
  if any(token in name for token in ("马克杯", "咖啡杯")):
    return 2580
  if any(token in name for token in ("酒杯", "啤酒")):
    return 2280
  if any(token in name for token in ("杯套", "配件", "手提袋")):
    return 1980
  return 2980


def product_cost_quote(product_id: str, name: str) -> tuple[int, str]:
  configured = commerce_config().get("productCosts")
  if isinstance(configured, dict):
    value = optional_int(configured.get(product_id))
    if value is not None and value > 0:
      return value, "运营录入的蜂鸟成本"
  # The order was submitted to Honeybird successfully on 2026-07-10. Keep this
  # separately traceable instead of treating the remaining category estimates as quotes.
  if product_id == "10167":
    return 2696, "蜂鸟测试订单"
  return product_cost_price_cents(product_id, name), "待蜂鸟报价校准"


def recommended_sale_price_cents(cost_price_cents: int) -> int:
  # 约 32% 毛利缓冲 AI、售后和支付成本；物流在结算时单独收取。
  target_cents = cost_price_cents / 0.68
  return max(990, int(((target_cents + 10 + 99) // 100) * 100 - 10))


def recommended_sale_price_points(cost_price_cents: int) -> int:
  return max(1, int(round(recommended_sale_price_cents(cost_price_cents) / 100)))


STATE = load_state()


def json_error(code: str, message: str, status: int = 400) -> tuple[int, dict[str, Any]]:
  return status, {"errorCode": code, "message": message}


class SmsError(Exception):
  def __init__(self, status: int, code: str, message: str) -> None:
    super().__init__(message)
    self.status = status
    self.code = code
    self.message = message


def aliyun_sms_enabled() -> bool:
  return bool(ALIYUN_SMS_ACCESS_KEY_ID and ALIYUN_SMS_ACCESS_KEY_SECRET and ALIYUN_SMS_SIGN_NAME and ALIYUN_SMS_LOGIN_TEMPLATE_CODE)


def sms_template_code_for_scene(scene: str | None) -> str:
  normalized = (scene or "login").strip().lower()
  if normalized in {"image_login", "image-processing-login", "image"} and ALIYUN_SMS_IMAGE_LOGIN_TEMPLATE_CODE:
    return ALIYUN_SMS_IMAGE_LOGIN_TEMPLATE_CODE
  return ALIYUN_SMS_LOGIN_TEMPLATE_CODE


def aliyun_percent_encode(value: Any) -> str:
  return quote(str(value), safe="~-_.")


def send_aliyun_sms_code(phone: str, code: str, scene: str | None = None) -> dict[str, Any]:
  template_code = sms_template_code_for_scene(scene)
  template_param = json.dumps({ALIYUN_SMS_TEMPLATE_PARAM_NAME: code}, ensure_ascii=False, separators=(",", ":"))
  params = {
    "AccessKeyId": ALIYUN_SMS_ACCESS_KEY_ID,
    "Action": "SendSms",
    "Format": "JSON",
    "PhoneNumbers": phone,
    "RegionId": "cn-hangzhou",
    "SignName": ALIYUN_SMS_SIGN_NAME,
    "SignatureMethod": "HMAC-SHA1",
    "SignatureNonce": secrets.token_urlsafe(18),
    "SignatureVersion": "1.0",
    "TemplateCode": template_code,
    "TemplateParam": template_param,
    "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "Version": "2017-05-25",
  }
  canonical_query = "&".join(
    f"{aliyun_percent_encode(key)}={aliyun_percent_encode(params[key])}"
    for key in sorted(params)
  )
  string_to_sign = f"GET&%2F&{aliyun_percent_encode(canonical_query)}"
  digest = hmac.new(
    f"{ALIYUN_SMS_ACCESS_KEY_SECRET}&".encode("utf-8"),
    string_to_sign.encode("utf-8"),
    hashlib.sha1,
  ).digest()
  signature = base64.b64encode(digest).decode("utf-8")
  query = canonical_query + "&Signature=" + aliyun_percent_encode(signature)
  url = ALIYUN_SMS_ENDPOINT.rstrip("/") + "/?" + query
  request = urllib.request.Request(url, method="GET")
  try:
    with urllib.request.urlopen(request, timeout=8, context=HUMCUSTOM_SSL_CONTEXT) as response:
      data = json.loads(response.read().decode("utf-8") or "{}")
  except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    raise SmsError(502, "SMS_PROVIDER_HTTP_ERROR", f"短信服务请求失败：HTTP {exc.code}。{body[:120]}") from exc
  except (urllib.error.URLError, TimeoutError) as exc:
    raise SmsError(502, "SMS_PROVIDER_UNAVAILABLE", "短信服务暂时不可用，请稍后再试。") from exc
  except json.JSONDecodeError as exc:
    raise SmsError(502, "SMS_PROVIDER_RESPONSE_INVALID", "短信服务响应无法解析。") from exc
  if str(data.get("Code") or "").upper() != "OK":
    provider_code = str(data.get("Code") or "UNKNOWN")
    provider_message = str(data.get("Message") or "短信发送失败")
    raise SmsError(502, "SMS_PROVIDER_SEND_FAILED", f"短信发送失败：{provider_code} {provider_message}")
  return data


def request_sms_code(phone: str, scene: str | None = None) -> dict[str, Any]:
  now = int(time.time())
  today = datetime.now().strftime("%Y-%m-%d")
  sms_bucket = STATE.setdefault("smsCodes", {})
  current = sms_bucket.get(phone) if isinstance(sms_bucket.get(phone), dict) else {}
  sent_at = int(current.get("sentAt") or 0)
  if sent_at and now - sent_at < SMS_RESEND_INTERVAL_SECONDS:
    raise SmsError(
      429,
      "SMS_CODE_TOO_FREQUENT",
      f"验证码已发送，请 {SMS_RESEND_INTERVAL_SECONDS - (now - sent_at)} 秒后再试。",
    )
  daily_date = str(current.get("dailyDate") or today)
  daily_count = int(current.get("dailyCount") or 0) if daily_date == today else 0
  if daily_count >= SMS_DAILY_LIMIT_PER_PHONE:
    raise SmsError(429, "SMS_DAILY_LIMIT_EXCEEDED", "今天验证码发送次数已达上限，请明天再试。")

  real_sms = aliyun_sms_enabled()
  code = f"{secrets.randbelow(1_000_000):06d}" if real_sms else TEST_SMS_CODE
  provider_payload: dict[str, Any] = {}
  if real_sms:
    provider_payload = send_aliyun_sms_code(phone, code, scene)
  sms_bucket[phone] = {
    "code": code,
    "scene": scene or "login",
    "sentAt": now,
    "expiresAt": now + SMS_CODE_EXPIRES_SECONDS,
    "attempts": 0,
    "dailyDate": today,
    "dailyCount": daily_count + 1,
    "provider": "aliyun" if real_sms else "local-test",
    "bizId": provider_payload.get("BizId"),
    "requestId": provider_payload.get("RequestId"),
  }
  save_state(STATE)
  response = {"ok": True, "expiresIn": SMS_CODE_EXPIRES_SECONDS, "resendAfter": SMS_RESEND_INTERVAL_SECONDS}
  if not real_sms:
    response["testCode"] = code
  return response


def verify_sms_code(phone: str, code: str) -> None:
  now = int(time.time())
  sms_bucket = STATE.setdefault("smsCodes", {})
  current = sms_bucket.get(phone) if isinstance(sms_bucket.get(phone), dict) else None
  if not current:
    if not aliyun_sms_enabled() and (ALLOW_TEST_SMS_CODE or code == TEST_SMS_CODE):
      return
    raise SmsError(422, "SMS_CODE_REQUIRED", "请先获取短信验证码。")
  if int(current.get("expiresAt") or 0) < now:
    sms_bucket.pop(phone, None)
    save_state(STATE)
    raise SmsError(422, "SMS_CODE_EXPIRED", "验证码已过期，请重新获取。")
  attempts = int(current.get("attempts") or 0)
  if attempts >= SMS_MAX_VERIFY_ATTEMPTS:
    sms_bucket.pop(phone, None)
    save_state(STATE)
    raise SmsError(429, "SMS_CODE_TOO_MANY_ATTEMPTS", "验证码尝试次数过多，请重新获取。")
  if str(current.get("code") or "") != code:
    current["attempts"] = attempts + 1
    save_state(STATE)
    raise SmsError(422, "SMS_CODE_INVALID", "验证码不正确。")
  sms_bucket.pop(phone, None)
  save_state(STATE)


def ensure_bucket(name: str, user_id: str) -> list[dict[str, Any]]:
  bucket = STATE.setdefault(name, {})
  return bucket.setdefault(user_id, [])


def ensure_wallet(user_id: str) -> dict[str, Any]:
  wallet = STATE.setdefault("wallets", {}).setdefault(
    user_id,
    {
      "userId": user_id,
      "aiCredits": 286,
      "productCouponCount": 1,
      "shareBalance": 42.8,
      "latestWalletEvent": "新账号体验额度已入账。",
      "coupons": [],
      "ledger": [],
      "redeemedCodes": [],
    },
  )
  wallet.setdefault("coupons", [])
  wallet.setdefault("ledger", [])
  wallet.setdefault("redeemedCodes", [])
  return wallet


def wallet_ledger_entry(wallet: dict[str, Any], action: str, amount: int, note: str) -> None:
  wallet.setdefault("ledger", []).insert(0, {
    "id": "ledger-" + secrets.token_hex(6),
    "time": now_label(),
    "action": action,
    "amount": amount,
    "note": note,
  })
  wallet["ledger"] = wallet["ledger"][:100]


def coupon_is_available(coupon: dict[str, Any], product_id: str | None = None) -> bool:
  if coupon.get("status") != "available":
    return False
  expires_at = optional_text(coupon.get("expiresAt"))
  if expires_at:
    try:
      if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        coupon["status"] = "expired"
        return False
    except ValueError:
      pass
  scope_product_id = optional_text(coupon.get("productId"))
  return not scope_product_id or not product_id or product_template_id(product_id) == product_template_id(scope_product_id)


def available_wallet_coupons(wallet: dict[str, Any], product_id: str | None = None) -> list[dict[str, Any]]:
  return [
    coupon
    for coupon in wallet.setdefault("coupons", [])
    if isinstance(coupon, dict) and coupon_is_available(coupon, product_id)
  ]


def refresh_wallet_coupon_count(wallet: dict[str, Any]) -> int:
  detailed_available = len(available_wallet_coupons(wallet))
  legacy_count = max(0, optional_int(wallet.get("legacyProductCouponCount")) or 0)
  if "legacyProductCouponCount" not in wallet:
    existing_count = max(0, optional_int(wallet.get("productCouponCount")) or 0)
    legacy_count = max(0, existing_count - detailed_available)
    wallet["legacyProductCouponCount"] = legacy_count
  wallet["productCouponCount"] = detailed_available + legacy_count
  return wallet["productCouponCount"]


def coupon_campaign_snapshot(campaign: dict[str, Any]) -> dict[str, Any]:
  campaign_id = str(campaign.get("id") or "")
  codes = [
    item for item in STATE.setdefault("redemptionCodes", [])
    if isinstance(item, dict) and item.get("campaignId") == campaign_id
  ]
  return {
    **campaign,
    "generatedCount": len(codes),
    "availableCount": sum(1 for item in codes if item.get("status") == "available"),
    "redeemedCount": sum(1 for item in codes if item.get("status") == "redeemed"),
    "codes": codes,
  }


def generate_redemption_code(prefix: str = "AICP") -> str:
  clean_prefix = re.sub(r"[^A-Z0-9]+", "", prefix.upper())[:8] or "AICP"
  existing = {str(item.get("code") or "") for item in STATE.setdefault("redemptionCodes", []) if isinstance(item, dict)}
  while True:
    code = f"{clean_prefix}-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}"
    if code not in existing:
      return code


def refund_process_task_credits(user_id: str, task: dict[str, Any], *, reason: str) -> bool:
  cost = optional_int(task.get("costCredits")) or 0
  if cost <= 0 or task.get("creditsRefundedAt"):
    return False
  wallet = ensure_wallet(user_id)
  wallet["aiCredits"] = int(wallet.get("aiCredits") or 0) + cost
  wallet["latestWalletEvent"] = f"图片处理失败，已退回 {cost} 积分。"
  wallet["updatedAt"] = now_label()
  wallet["updatedBy"] = "system"
  task["creditsRefunded"] = cost
  task["creditsRefundedAt"] = now_label()
  task["creditsRefundReason"] = reason
  return True


def agent_plan_cost_credits(plan: dict[str, Any]) -> int:
  total = 0
  for step in plan.get("steps") or []:
    try:
      total += int(step.get("costCredits") or 0)
    except (TypeError, ValueError):
      continue
  return max(0, total)


def expire_stale_process_tasks(tasks: list[dict[str, Any]]) -> bool:
  changed = False
  now = datetime.now()
  for task in tasks:
    if task.get("status") not in {"pending", "processing"}:
      continue
    created_at = parse_local_datetime(task.get("createdAt") or task.get("submittedAt") or task.get("updatedAt"))
    if not created_at:
      continue
    if (now - created_at).total_seconds() <= PROCESS_TASK_STALE_SECONDS:
      continue

    input_count = int(task.get("inputCount") or len(task.get("inputImages") or []) or 0)
    result_count = int(task.get("resultCount") or len(task.get("resultImages") or []) or len(task.get("outputAssetIds") or []) or 0)
    task["status"] = "failed"
    task["finalStatus"] = "timeout"
    task["callbackStatus"] = "已停止"
    task["completedAt"] = task.get("completedAt") or now_label()
    task["errorCode"] = "CLIENT_PROCESS_TASK_EXPIRED"
    if result_count > 0 and input_count > result_count:
      task["errorMessage"] = f"已生成 {result_count}/{input_count} 张，其余图片等待时间过长，已停止。可查看已生成结果或重新提交。"
    else:
      task["errorMessage"] = "这批图片等待时间过长，已停止。请重新提交或换一组图片。"
    params = task.get("params")
    if isinstance(params, dict):
      for item in params.get("queueItems") or []:
        if not isinstance(item, dict):
          continue
        if str(item.get("status") or "").lower() in ACTIVE_PROCESS_ITEM_STATUSES:
          item["status"] = "failed"
          item["completedAt"] = item.get("completedAt") or task["completedAt"]
          item["errorCode"] = "CLIENT_PROCESS_TASK_EXPIRED"
          item["errorMessage"] = "等待时间过长，已停止。"
      queue_items = [item for item in params.get("queueItems") or [] if isinstance(item, dict)]
      if queue_items:
        task["queueSummary"] = {
          "queued": sum(1 for item in queue_items if str(item.get("status") or "").lower() in {"queued", "pending"}),
          "running": sum(1 for item in queue_items if str(item.get("status") or "").lower() in {"dispatching", "running", "submitted", "processing"}),
          "completed": sum(1 for item in queue_items if item.get("status") == "completed"),
          "failed": sum(1 for item in queue_items if item.get("status") == "failed"),
          "maxInFlight": CLIENT_QUEUE_MAX_IN_FLIGHT,
          "dispatchPerTick": CLIENT_QUEUE_DISPATCH_PER_TICK,
        }
    changed = True
  return changed


def reset_stale_dispatching_process_items(tasks: list[dict[str, Any]]) -> bool:
  changed = False
  now = datetime.now()
  for task in tasks:
    params = task.get("params")
    if not isinstance(params, dict):
      continue
    for item in params.get("queueItems") or []:
      if not isinstance(item, dict) or item.get("status") != "dispatching":
        continue
      started_at = parse_local_datetime(item.get("dispatchStartedAt"))
      if started_at and (now - started_at).total_seconds() <= PROCESS_ITEM_DISPATCH_STALE_SECONDS:
        continue
      item["status"] = "queued"
      item["dispatchToken"] = None
      item["dispatchStartedAt"] = None
      item["errorMessage"] = "上次提交没有确认成功，已重新排队。"
      item["retryAt"] = now_label()
      changed = True
  return changed


def normalize_process_task_status_copy(tasks: list[dict[str, Any]]) -> bool:
  changed = False
  replacements = (
    ("已停止等待", "已停止"),
    ("等待中台结果", "等待生成结果"),
    ("中台执行中", "正在生成"),
    ("业务队列等待中", "等待生成"),
    ("中台状态查询暂时失败", "暂时查不到生成进度"),
    ("中台队列繁忙", "图片生成服务繁忙"),
    ("暂时连接不上中台", "暂时连接不上图片生成服务"),
    ("提交中台失败", "提交图片生成失败"),
    ("中台执行失败", "图片生成失败"),
  )
  for task in tasks:
    task_error_text = " ".join(
      str(task.get(key) or "")
      for key in ("errorCode", "errorMessage", "callbackStatus", "finalStatus")
    )
    if task.get("status") == "failed" and task.get("callbackStatus") in {"等待生成结果", "正在生成", "等待生成"}:
      task["callbackStatus"] = "图片生成服务繁忙" if (
        "COMFYUI_QUEUE_FULL" in task_error_text or "ERR|Q1001" in task_error_text
      ) else "生成失败"
      changed = True
    for key in ("callbackStatus", "errorMessage"):
      value = task.get(key)
      if not isinstance(value, str):
        continue
      new_value = value
      if "COMFYUI_QUEUE_FULL" in new_value or "ERR|Q1001" in new_value:
        new_value = "图片生成服务繁忙，请稍后重新提交。"
      for old, new in replacements:
        new_value = new_value.replace(old, new)
      if new_value != value:
        task[key] = new_value
        changed = True
    params = task.get("params")
    if isinstance(params, dict):
      for item in params.get("queueItems") or []:
        if not isinstance(item, dict):
          continue
        value = item.get("errorMessage")
        if not isinstance(value, str):
          continue
        new_value = value
        if "COMFYUI_QUEUE_FULL" in new_value or "ERR|Q1001" in new_value:
          new_value = "图片生成服务繁忙，请稍后重新提交。"
        for old, new in replacements:
          new_value = new_value.replace(old, new)
        if new_value != value:
          item["errorMessage"] = new_value
          changed = True
  return changed


def normalize_process_task_queue_items(tasks: list[dict[str, Any]]) -> bool:
  changed = False
  for task in tasks:
    params = task.get("params")
    if not isinstance(params, dict):
      continue
    queue_items = [item for item in params.get("queueItems") or [] if isinstance(item, dict)]
    if not queue_items:
      continue
    result_images: list[str] = []
    for item in queue_items:
      item_images = [url for url in (item.get("resultImages") or []) if is_probable_image_url(url)]
      if item.get("resultImages") != item_images:
        item["resultImages"] = item_images
        changed = True
      if item_images:
        result_images.extend(item_images)
        if item.get("status") != "completed":
          item["status"] = "completed"
          changed = True
        if item.get("runStatus") not in (None, "", "completed"):
          item["runStatus"] = "completed"
          changed = True
        if not item.get("completedAt"):
          item["completedAt"] = task.get("completedAt") or now_label()
          changed = True
        if item.get("errorMessage"):
          item["errorMessage"] = None
          changed = True
    if result_images:
      deduped_result_images = list(dict.fromkeys(result_images))
      if task.get("resultImages") != deduped_result_images:
        task["resultImages"] = deduped_result_images
        task["resultCount"] = len(deduped_result_images)
        changed = True
    completed_count = sum(
      1
      for item in queue_items
      if item.get("status") == "completed" and any(is_probable_image_url(url) for url in (item.get("resultImages") or []))
    )
    failed_count = sum(1 for item in queue_items if item.get("status") == "failed")
    active_count = sum(1 for item in queue_items if str(item.get("status") or "").lower() in ACTIVE_PROCESS_ITEM_STATUSES)
    if completed_count == len(queue_items) and not failed_count:
      if task.get("status") != "completed":
        task["status"] = "completed"
        changed = True
      if task.get("finalStatus") != "completed":
        task["finalStatus"] = "completed"
        changed = True
      if task.get("callbackStatus") != "结果已入库":
        task["callbackStatus"] = "结果已入库"
        changed = True
      if not task.get("completedAt"):
        task["completedAt"] = now_label()
        changed = True
    elif task.get("status") == "completed" and active_count:
      for item in queue_items:
        if str(item.get("status") or "").lower() in ACTIVE_PROCESS_ITEM_STATUSES and item.get("resultImages"):
          item["status"] = "completed"
          item["runStatus"] = "completed"
          item["completedAt"] = item.get("completedAt") or task.get("completedAt") or now_label()
          changed = True
  return changed


def normalize_process_task_queue_summary(tasks: list[dict[str, Any]]) -> bool:
  changed = normalize_process_task_queue_items(tasks)
  for task in tasks:
    params = task.get("params")
    if not isinstance(params, dict):
      continue
    queue_items = [item for item in params.get("queueItems") or [] if isinstance(item, dict)]
    if not queue_items:
      continue
    summary = {
      "queued": sum(1 for item in queue_items if str(item.get("status") or "").lower() in {"queued", "pending"}),
      "running": sum(1 for item in queue_items if str(item.get("status") or "").lower() in {"dispatching", "running", "submitted", "processing"}),
      "completed": sum(
        1
        for item in queue_items
        if item.get("status") == "completed" and any(is_probable_image_url(url) for url in (item.get("resultImages") or []))
      ),
      "failed": sum(1 for item in queue_items if item.get("status") == "failed"),
      "maxInFlight": CLIENT_QUEUE_MAX_IN_FLIGHT,
      "dispatchPerTick": CLIENT_QUEUE_DISPATCH_PER_TICK,
    }
    if task.get("queueSummary") != summary:
      task["queueSummary"] = summary
      changed = True
  return changed


def find_asset(user_id: str, asset_id: str) -> dict[str, Any] | None:
  for candidate_user in (user_id, "demo-user"):
    for asset in STATE.setdefault("assets", {}).get(candidate_user, []):
      if asset.get("id") == asset_id:
        return asset
  return None


def first_user_asset(user_id: str, asset_ids: list[str] | None = None) -> dict[str, Any] | None:
  wanted = [str(item) for item in (asset_ids or []) if str(item or "").strip()]
  if wanted:
    for asset_id in wanted:
      asset = find_asset(user_id, asset_id)
      if asset:
        return asset
  return None


def user_assets_by_ids(user_id: str, asset_ids: list[str] | None = None) -> list[dict[str, Any]]:
  assets: list[dict[str, Any]] = []
  for asset_id in normalize_id_list(asset_ids or []):
    asset = find_asset(user_id, asset_id)
    if asset:
      assets.append(asset)
  return assets


def normalize_id_list(value: Any) -> list[str]:
  if not isinstance(value, list):
    return []
  return list(dict.fromkeys([str(item) for item in value if str(item or "").strip()]))


def first_non_empty_text(value: Any) -> str:
  if isinstance(value, list):
    for item in value:
      text = str(item or "").strip()
      if text:
        return text
    return ""
  return str(value or "").strip()


def is_design_followup_message(message: str) -> bool:
  text = (message or "").lower()
  return any(word in text for word in (
    "继续", "上一张", "上一版", "刚才", "这个结果", "这个图", "这张", "这版",
    "基于", "再", "第二版", "换成", "改成", "优化一下", "再优化", "不要回到原图",
  ))


def agent_context_asset_ids(session: dict[str, Any], explicit_asset_ids: list[str]) -> tuple[list[str], str, str]:
  if explicit_asset_ids:
    return explicit_asset_ids, "explicit_assets", "source_asset"
  memory = session.get("workingMemory") if isinstance(session.get("workingMemory"), dict) else {}
  for key, source, role in (
    ("currentAssetIds", "working_memory", "previous_result"),
    ("lastResultAssetIds", "working_memory", "previous_result"),
    ("acceptedAssetIds", "working_memory", "accepted_asset"),
  ):
    ids = normalize_id_list(memory.get(key))
    if ids:
      return ids, source, role
  result_ids = normalize_id_list(session.get("resultAssetIds"))
  if result_ids:
    return result_ids, "session_results", "previous_result"
  source_ids = normalize_id_list(session.get("sourceAssetIds"))
  if source_ids:
    return source_ids, "session_source", "source_asset"
  return [], "prompt_only", "prompt_only"


def remember_agent_plan(session: dict[str, Any], plan: dict[str, Any]) -> None:
  memory = session.setdefault("workingMemory", {})
  trace = plan.get("contextTrace") if isinstance(plan.get("contextTrace"), dict) else {}
  context_asset_ids = normalize_id_list(trace.get("assetIds"))
  if context_asset_ids:
    memory["currentAssetIds"] = context_asset_ids
    memory["currentAssetRole"] = trace.get("baseAssetRole") or memory.get("currentAssetRole") or "source_asset"
  assignments = ((plan.get("layoutPlan") or {}).get("surfaceAssignments") or [])
  if assignments:
    memory["activeSurfaceId"] = assignments[0].get("surfaceId") or memory.get("activeSurfaceId")
  memory["lastIntent"] = plan.get("intent")
  memory["lastPlanId"] = plan.get("planId")
  memory["lastSummaryForUser"] = plan.get("summaryForUser")
  memory["contextSource"] = trace.get("source") or memory.get("contextSource")
  if isinstance(plan.get("visionAnalysis"), dict):
    memory["lastVisionAnalysis"] = plan.get("visionAnalysis")


def remember_agent_results(session: dict[str, Any], result_ids: list[str], plan: dict[str, Any]) -> None:
  memory = session.setdefault("workingMemory", {})
  if result_ids:
    memory["lastResultAssetIds"] = result_ids
    memory["currentAssetIds"] = result_ids
    memory["currentAssetRole"] = "previous_result"
  memory["lastIntent"] = plan.get("intent")
  memory["lastPlanId"] = plan.get("planId")
  memory["lastSummaryForUser"] = plan.get("summaryForUser")
  if isinstance(plan.get("visionAnalysis"), dict):
    memory["lastVisionAnalysis"] = plan.get("visionAnalysis")


def product_surface_defaults(product_context: dict[str, Any] | None) -> list[dict[str, Any]]:
  def normalize_surface(item: dict[str, Any]) -> dict[str, Any]:
    surface_name = optional_text(item.get("name")) or optional_text(item.get("id")) or "front"
    surface_label = optional_text(item.get("label")) or optional_text(item.get("title")) or ("把手" if surface_name == "handle" else "正面")
    width = (
      optional_int(item.get("width"))
      or optional_int(item.get("designWidth"))
      or optional_int(item.get("targetWidth"))
      or optional_int(item.get("pixelWidth"))
    )
    height = (
      optional_int(item.get("height"))
      or optional_int(item.get("designHeight"))
      or optional_int(item.get("targetHeight"))
      or optional_int(item.get("pixelHeight"))
    )
    dpi = optional_int(item.get("dpi")) or optional_int(item.get("ppi")) or 150
    return {
      **item,
      "id": surface_name,
      "name": surface_name,
      "label": surface_label,
      "width": width,
      "height": height,
      "dpi": dpi,
      "role": item.get("role") or ("decal" if surface_name == "handle" else "wrap"),
    }

  if isinstance(product_context, dict):
    surfaces = product_context.get("surfaces")
    if isinstance(surfaces, list) and surfaces:
      return [normalize_surface(item) for item in surfaces if isinstance(item, dict)]
  return [
    {"name": "front", "label": "正面", "width": 3378, "height": 1949, "dpi": 150, "role": "wrap"},
    {"name": "handle", "label": "把手", "width": 946, "height": 1949, "dpi": 150, "role": "decal"},
  ]


ALLOWED_AGENT_INTENTS = {
  "print_as_is",
  "clean_and_print",
  "extract_pattern",
  "make_seamless_wrap",
  "generate_variations",
  "ai_recreate",
  "compose_product_design",
  "clarify",
}


def truthy_agent_flag(value: Any) -> bool:
  if isinstance(value, bool):
    return value
  if isinstance(value, (int, float)):
    return value != 0
  text = str(value or "").strip().lower()
  return text in {"1", "true", "yes", "y", "需要", "是", "需确认", "需要确认"}


def agent_quality_risk_level(value: Any) -> str:
  text = str(value or "").strip().lower()
  if not text:
    return "unknown"
  if text in {"high", "medium", "low"}:
    return text
  if any(word in text for word in ("high", "高", "严重", "不适合", "不可", "无法", "误传", "极差", "模糊", "版权")):
    return "high"
  if any(word in text for word in ("medium", "中", "一般", "需要确认", "风险", "偏低", "可能")):
    return "medium"
  return "low"


def has_explicit_route_keywords(message: str, intent: str) -> bool:
  text = (message or "").lower()
  keywords_by_intent = {
    "print_as_is": ("原样", "直接印", "印上去", "logo", "标志", "商标", "头像", "名字", "别做裂变"),
    "clean_and_print": ("清理", "增强", "去背景", "修清楚", "照片", "拍摄", "拍照"),
    "extract_pattern": ("提取花纹", "花纹提取", "抽花", "提取图案", "提出来"),
    "make_seamless_wrap": ("无缝", "连续", "环绕", "满版", "杯身", "接缝", "两方", "四方"),
    "generate_variations": ("裂变", "候选", "多张", "系列", "变体", "变化", "再来几张"),
    "ai_recreate": ("重绘", "二创", "重新设计", "ai", "风格化", "优化", "精修"),
  }
  return any(word in text for word in keywords_by_intent.get(intent, ()))


def requests_reference_based_design(message: str) -> bool:
  text = (message or "").lower()
  return any(word in text for word in (
    "帮我设计", "设计一套", "做一款", "做一个", "生成一套", "出一套",
    "相似", "参考", "参照", "同风格", "风格", "艺术", "创作", "创意",
    "更好看", "更精致", "适合杯子", "产品设计", "元素", "色调", "配色", "色彩",
  ))


def has_multi_reference_role_request(message: str) -> bool:
  text = (message or "").lower()
  first_refs = ("图一", "第一张", "第1张", "1号图", "图1", "第一幅")
  second_refs = ("图二", "第二张", "第2张", "2号图", "图2", "第二幅")
  role_terms = ("色调", "配色", "颜色", "色彩", "元素", "图案", "主体", "内容", "构图", "风格", "氛围")
  return (
    any(ref in text for ref in first_refs)
    and any(ref in text for ref in second_refs)
    and any(term in text for term in role_terms)
  )


def requests_ai_redesign(message: str) -> bool:
  text = (message or "").lower()
  return any(word in text for word in (
    "重绘", "二创", "重新设计", "再设计", "ai设计", "ai 设计", "风格化",
    "优化", "精修", "更精致", "更好看", "做成一套", "生成一套", "出一套",
  ))


def requests_original_print(message: str) -> bool:
  text = (message or "").lower()
  return any(word in text for word in (
    "原样", "直接印", "印上去", "不要改", "不改图", "保持原图",
    "logo", "标志", "商标", "头像", "名字",
  ))


def resolve_agent_intent(
  local_intent: str,
  vision_analysis: dict[str, Any],
  message: str,
) -> str:
  vision_intent = str(vision_analysis.get("recommendedIntent") or "").strip()
  if vision_intent not in ALLOWED_AGENT_INTENTS:
    return local_intent
  vision_confidence = optional_float(vision_analysis.get("confidence"), 0.0)
  risk_level = agent_quality_risk_level(vision_analysis.get("qualityRisk"))
  needs_confirm = truthy_agent_flag(vision_analysis.get("needsUserConfirmation"))
  model_says_block_or_clarify = (
    vision_intent == "clarify"
    and vision_confidence >= 0.68
    and (needs_confirm or risk_level in {"high", "medium"})
  )
  if model_says_block_or_clarify:
    return "clarify"

  if vision_analysis.get("fallback") == "heuristic" and vision_analysis.get("modelError"):
    return "clarify"

  if has_multi_reference_role_request(message):
    return "ai_recreate"

  if requests_ai_redesign(message) and not requests_original_print(message):
    return "ai_recreate"

  if requests_reference_based_design(message) and not requests_original_print(message):
    if local_intent in {"ai_recreate", "generate_variations", "extract_pattern", "make_seamless_wrap"}:
      return local_intent
    if vision_intent in {"print_as_is", "clean_and_print", "compose_product_design"} and risk_level != "high":
      return "ai_recreate"

  explicit_local = has_explicit_route_keywords(message, local_intent)
  if explicit_local and local_intent != "clarify":
    if risk_level == "high" and vision_intent == "clarify" and vision_confidence >= 0.62:
      return "clarify"
    return local_intent

  if local_intent in {"clarify", "compose_product_design"} and vision_intent != "clarify" and vision_confidence >= 0.72:
    return vision_intent
  if local_intent == "extract_pattern" and vision_intent == "make_seamless_wrap" and vision_confidence >= 0.72:
    return vision_intent
  if local_intent == "clean_and_print" and vision_intent in {"print_as_is", "ai_recreate"} and vision_confidence >= 0.82:
    return vision_intent
  return local_intent


def classify_design_intent(message: str, asset: dict[str, Any] | None, context: dict[str, Any] | None = None) -> str:
  text = (message or "").lower()
  title = str(asset.get("title") if asset else "").lower()
  source = str(asset.get("source") if asset else "").lower()
  combined = " ".join([text, title, source])
  context = context if isinstance(context, dict) else {}
  previous_intent = str(context.get("previousIntent") or "")
  followup = bool(context.get("isFollowup")) or is_design_followup_message(message)

  # A prompt-only request has no source image to "print as-is". Handle it
  # before matching words such as "文字" or "Logo", otherwise a negative
  # instruction like "不要文字" can be mistaken for an original-print request.
  if not asset and text.strip():
    # Text-to-image can create a full-bleed design candidate, but it is not a
    # certified seamless texture until the dedicated seamless ability has run.
    return "ai_recreate"

  if followup and asset:
    if any(word in text for word in (
      "换色", "换成", "改成", "优化", "精修", "更", "清新", "高级", "蓝绿", "蓝色", "绿色",
      "风格", "二创", "重绘", "不要回到原图",
    )):
      return "ai_recreate"
    if any(word in combined for word in ("无缝", "连续", "环绕", "满版", "杯身", "接缝", "两方", "四方")):
      return "make_seamless_wrap"
    if any(word in text for word in ("裂变", "候选", "多张", "系列", "变体", "变化", "再来几张")):
      return "generate_variations"
    if previous_intent in {"print_as_is", "clean_and_print", "make_seamless_wrap", "generate_variations", "ai_recreate", "compose_product_design"}:
      return previous_intent
  quality_risk_words = (
    "低清", "低质量", "低像素", "分辨率低", "像素低", "模糊", "虚焦",
    "看不清", "不清晰", "不够清晰", "糊了", "质量差", "噪点",
  )
  if any(word in combined for word in quality_risk_words):
    return "clarify"
  if any(word in combined for word in ("孩子", "儿童", "绘画", "手绘", "小朋友画", "原画感")):
    return "clarify"
  if asset and has_multi_reference_role_request(message):
    return "ai_recreate"
  if asset and requests_reference_based_design(message) and not requests_original_print(message):
    if requests_ai_redesign(message):
      return "ai_recreate"
    if any(word in combined for word in ("裂变", "候选", "多张", "系列", "变体", "变化")):
      return "generate_variations"
    if any(word in combined for word in ("花纹", "无缝", "连续", "环绕", "满版", "杯身", "接缝", "两方", "四方")):
      return "make_seamless_wrap"
    return "ai_recreate"
  if any(word in combined for word in ("logo", "标志", "商标", "文字", "名字", "头像", "原样", "印上去")):
    return "print_as_is"
  if any(word in combined for word in ("照片", "拍摄", "拍照")):
    return "clean_and_print"
  if any(word in combined for word in ("提取花纹", "花纹提取", "抽花", "提取图案", "提取出来")):
    return "extract_pattern"
  if any(word in combined for word in ("无缝", "连续", "环绕", "满版", "杯身", "接缝", "两方", "四方")):
    return "make_seamless_wrap"
  if any(word in combined for word in ("裂变", "候选", "多张", "系列", "变体", "变化")):
    return "generate_variations"
  if any(word in combined for word in ("重绘", "二创", "优化", "更精致", "风格化", "生成")):
    return "ai_recreate"
  if asset and asset.get("type") in {"pattern", "variation"}:
    return "make_seamless_wrap"
  if asset:
    return "ai_recreate"
  return "clarify"


def clamp_agent_output_count(count: int) -> int:
  return max(1, min(8, int(count or 1)))


def requested_agent_output_count(message: str) -> int | None:
  text = (message or "").strip().lower()
  if not text:
    return None
  for matched in re.finditer(r"([1-9]\d?)\s*(?:张|幅)\s*(?:候选|备选|方案|版本|效果|图|图片)?", text):
    return clamp_agent_output_count(int(matched.group(1)))
  for matched in re.finditer(r"([1-9]\d?)\s*(?:款|套)\s*(?:候选|备选|方案|版本|效果|图|图片)", text):
    return clamp_agent_output_count(int(matched.group(1)))

  chinese_counts = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
  }
  for word, count in chinese_counts.items():
    if re.search(fr"{word}\s*(?:张|幅)\s*(?:候选|备选|方案|版本|效果|图|图片)?", text):
      return clamp_agent_output_count(count)
    if re.search(fr"{word}\s*(?:款|套)\s*(?:候选|备选|方案|版本|效果|图|图片)", text):
      return clamp_agent_output_count(count)

  if any(word in text for word in ("多张", "几张", "候选", "备选", "裂变", "系列", "变体")):
    return 4
  return None


def intent_title(intent: str) -> str:
  return {
    "print_as_is": "原图局部印刷",
    "clean_and_print": "清理后局部印刷",
    "extract_pattern": "提取花纹",
    "make_seamless_wrap": "花纹环绕",
    "generate_variations": "裂变候选",
    "ai_recreate": "AI 重绘适配",
    "compose_product_design": "产品贴图布局",
    "clarify": "补充设计意图",
  }.get(intent, "产品设计规划")


def build_design_agent_plan(
  user_id: str,
  session_id: str,
  message: str,
  product_context: dict[str, Any] | None,
  asset_ids: list[str] | None,
  context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  context = context if isinstance(context, dict) else {}
  asset = first_user_asset(user_id, asset_ids)
  intent = classify_design_intent(message, asset, context)
  vision_analysis = context.get("visionAnalysis") if isinstance(context.get("visionAnalysis"), dict) else {}
  # The one-click entry is intentionally phrased as a neutral system request
  # ("please judge this image"). Do not let words such as "design" in that
  # request force an Image2 redraw over a confident visual finding that this is
  # a pattern, logo, photo, or unsuitable screenshot.
  quick_intake = str(context.get("source") or "") == "quick_design"
  vision_intent = str(vision_analysis.get("recommendedIntent") or "")
  vision_confidence = optional_float(vision_analysis.get("confidence"), 0.0)
  if quick_intake and vision_intent in ALLOWED_AGENT_INTENTS and vision_confidence >= 0.68:
    intent = vision_intent
  else:
    intent = resolve_agent_intent(intent, vision_analysis, message)
  rejected_routes: list[dict[str, Any]] = []
  if not asset and intent in {"extract_pattern", "generate_variations"}:
    rejected_routes.append({
      "intent": intent,
      "reason": "这个路线需要一张可读取的参考图；当前只有文字需求，不能直接进入图片处理。",
    })
    intent = "clarify"
  requested_output_count = requested_agent_output_count(message)
  surfaces = product_surface_defaults(product_context)
  default_surface = surfaces[0] if surfaces else {"name": "front", "label": "正面"}
  vision_surface_id = first_non_empty_text(vision_analysis.get("recommendedSurfaceId"))
  matched_surface = next((item for item in surfaces if str(item.get("name") or "") == vision_surface_id), None)
  if matched_surface:
    default_surface = matched_surface
  surface_id = str(default_surface.get("name") or "front")
  surface_label = str(default_surface.get("label") or "正面")
  user_surface_label = "主图案区域" if surface_id != "handle" else "局部图案区域"
  source_ref = asset.get("id") if asset else None
  needs_confirm = intent != "clarify"
  message_text = (message or "").lower()
  clarify_questions = ["你希望这张图是局部印上去，还是做成整杯连续花纹？"]
  seamless_unavailable = False
  prompt_only_generation_unavailable = False
  prompt_only_wrap = intent == "make_seamless_wrap" and not asset
  if intent == "make_seamless_wrap" and asset and not AGENT_BUSINESS_ENDPOINT_BY_ABILITY.get("two_way_seamless"):
    rejected_routes.append({
      "intent": "make_seamless_wrap",
      "reason": "当前业务系统还没有可调用的两方/四方连续生成入口，不能让用户确认一个执行后会失败的方案。",
    })
    seamless_unavailable = True
    intent = "clarify"
    needs_confirm = False
  if not asset and intent in {"ai_recreate", "compose_product_design", "make_seamless_wrap"} and not AGENT_TEXT2IMAGE_AVAILABLE:
    rejected_routes.append({
      "intent": intent,
      "reason": "当前业务系统还没有接通可稳定执行的纯文字原创生图通道；不能让用户确认后再报错。",
    })
    prompt_only_generation_unavailable = True
    intent = "clarify"
    needs_confirm = False

  if intent == "clarify":
    vision_questions = text_list(vision_analysis.get("questions"))
    vision_risks = text_list(vision_analysis.get("risks"))
    vision_image_type = str(vision_analysis.get("imageType") or "").lower()
    vision_quality = str(vision_analysis.get("qualityRisk") or "").lower()
    is_text_screenshot = (
      "text_screenshot" in vision_image_type
      or any(word in vision_image_type for word in ("截图", "表格", "网页", "ui", "screen"))
    )
    is_low_quality = (
      "low_quality" in vision_image_type
      or any(word in vision_quality for word in ("模糊", "低清", "像素"))
      or any(any(word in risk for word in ("模糊", "低清", "像素", "发虚", "锯齿")) for risk in vision_risks)
    )
    is_child_drawing = (
      "child_drawing" in vision_image_type
      or any(word in vision_image_type for word in ("孩子", "儿童", "绘画", "手绘"))
      or any(word in message_text for word in ("孩子", "儿童", "绘画", "手绘", "小朋友画", "原画感"))
    )
    if seamless_unavailable:
      summary = "这张图适合进一步做杯身环绕，但当前两方/四方连续能力还没有接到业务系统。我不会让你确认一个无法执行的方案；可以先生成 4 张杯身候选图，或等连续图能力接通后再做无缝版。"
      clarify_questions = ["先生成 4 张杯身候选图，还是等连续图能力接通后再做无缝版？"]
    elif prompt_only_generation_unavailable:
      summary = "我可以先帮你拆设计方向，但当前纯文字原创生图通道还没有接到业务系统。我不会让你确认一个无法执行的方案；请先上传参考图或从素材库选一张图，我会基于它做 VL 判断、重绘、裂变或贴图适配。"
      clarify_questions = ["先加一张参考图继续，还是只让我整理一版设计方向和需要准备的素材？"]
    elif vision_analysis.get("fallback") == "heuristic" and vision_analysis.get("modelError"):
      summary = "图片理解模型这次没有稳定返回，我不会直接把图贴到杯子上冒充设计。请重试一次，或先告诉我你希望保留原图、重新设计，还是提取花纹。"
      clarify_questions = ["要我重试图片理解，还是先按你的文字目标继续规划？"]
      if vision_risks:
        summary += f" 风险：{vision_risks[0]}"
    elif is_text_screenshot:
      summary = "这张图更像截图、表格或文字资料，不是正常装饰素材。需要先确认是误传，还是要把内容重新排版成可印刷图案。"
      clarify_questions = ["这是误传的截图，还是你希望我把其中内容重新排版成杯子图案？"]
      if vision_risks:
        summary += f" 风险：{vision_risks[0]}"
    elif is_low_quality:
      summary = "这张图存在清晰度或印刷风险。建议先确认：清理增强、AI 重绘一版，还是接受风险按原图印刷。"
      clarify_questions = ["你想先清理增强、AI 重绘一版，还是保持原图直接印？"]
      if vision_risks:
        summary += f" 风险：{vision_risks[0]}"
    elif is_child_drawing:
      summary = "这类图通常有两条路线：保留原画的纪念感，或优化成更适合印刷的干净插画。我建议默认放在杯子正面，不直接做满版花纹。"
      clarify_questions = ["你想保留孩子原画感，还是让我优化成更干净的插画？"]
      if vision_risks:
        summary += f" 风险：{vision_risks[0]}"
    elif vision_questions:
      summary = f"这张图还需要先确认设计方向：{vision_questions[0]}"
      clarify_questions = vision_questions[:2]
      if vision_risks:
        summary += f" 风险：{vision_risks[0]}"
    elif any(word in message_text for word in (
      "低清", "低质量", "低像素", "分辨率低", "像素低", "模糊", "虚焦",
      "看不清", "不清晰", "不够清晰", "糊了", "质量差", "噪点",
    )):
      summary = "这张图可能存在清晰度风险。可以先清理增强、交给 AI 重绘，或仍按原图印刷但需要接受成品风险。"
      clarify_questions = ["你想先清理增强、AI 重绘一版，还是保持原图直接印？"]
    else:
      summary = "我需要先知道你想把图片作为局部图案、整杯环绕花纹，还是希望 AI 重新设计一版。"
  elif intent == "print_as_is":
    summary = f"我会尽量保留原图，把它作为{user_surface_label}放到杯子上，先不做花纹化处理。"
  elif intent == "clean_and_print":
    summary = f"我会先保留照片或手绘的主要内容，清理背景和对比度，再放到{user_surface_label}。"
  elif intent == "extract_pattern":
    summary = "我会先从图片里提取主要花纹，沉淀成可复用素材；确认后再决定是局部贴图还是杯身环绕。"
  elif intent == "make_seamless_wrap":
    if prompt_only_wrap:
      count_text = requested_output_count or 4
      summary = f"我会先生成 {count_text} 张适合杯身环绕的候选图，再按杯型尺寸做后处理和接缝复核；主体元素不会被强行平铺。"
    elif requested_output_count and requested_output_count > 1:
      summary = f"我会先生成 {requested_output_count} 张适合杯身环绕的连续候选图，你选定后再贴到杯子上，避免接缝明显。"
    else:
      summary = "我会先判断花纹质量，再生成适合杯身环绕的连续图，避免接缝明显。"
  elif intent == "generate_variations":
    output_count_text = requested_output_count or 4
    summary = f"我会基于当前图片生成 {output_count_text} 张相似候选，你可以选一张继续做杯子。"
  elif intent == "ai_recreate":
    if context.get("baseAssetRole") == "previous_result":
      summary = "我会基于上一轮你确认或刚生成的结果继续优化，不回到最初原图，再裁切到当前杯型设计面尺寸。"
    else:
      summary = "我会先按你的描述重绘或精修图片，再裁切到当前杯型设计面尺寸。"
  else:
    summary = "我会先基于当前素材和需求生成可选设计，再把确认后的结果适配到这款杯子的贴图面和生产尺寸。"

  steps: list[dict[str, Any]] = [
    {
      "stepId": "s1",
      "type": "quality_check",
      "title": "识别图片和商品约束",
      "targetAbility": "vl_analyze",
      "status": "completed",
      "userStatus": "已完成",
      "costCredits": 0,
      "requiresConfirmationBefore": False,
      "requiresConfirmationAfter": False,
      "summary": "已读取商品贴图面、图片来源、用户目标和图片可生产性。",
    }
  ]
  if intent == "clarify":
    steps.append({
      "stepId": "s2",
      "type": "ask_user",
      "title": "确认设计方向",
      "targetAbility": "ask_user",
      "status": "needs_user",
      "userStatus": "需要你补充",
      "costCredits": 0,
      "requiresConfirmationBefore": False,
      "requiresConfirmationAfter": True,
      "summary": "请选择保留原图、提取花纹、生成候选或 AI 重绘。",
    })
  else:
    ability = {
      "print_as_is": "postprocess_to_surface",
      "clean_and_print": "postprocess_to_surface",
      "extract_pattern": "pattern_extract",
      "make_seamless_wrap": "image2_recreate" if prompt_only_wrap else "two_way_seamless",
      "generate_variations": "variation",
      "ai_recreate": "image2_recreate",
      "compose_product_design": "image2_recreate",
    }.get(intent, "render_product_preview")
    output_count = requested_output_count or (4 if intent in {"generate_variations", "make_seamless_wrap"} and not asset else 1)
    steps.append({
      "stepId": "s2",
      "type": "ability_call",
      "title": intent_title(intent),
      "targetAbility": ability,
      "status": "waiting_confirmation",
      "userStatus": "等待你确认",
      "costCredits": 2 if ability == "postprocess_to_surface" else 5,
      "outputCount": output_count,
      "idempotencyKey": f"{session_id}:s2:{ability}:{source_ref or 'prompt'}",
      "failureFallback": "如果处理失败，会保留原图并提示用户改用原样印刷、重新上传或换一种设计路线。",
      "requiresConfirmationBefore": True,
      "requiresConfirmationAfter": True,
      "summary": "确认后执行图片处理，并把阶段结果回填到对话里。",
    })
    steps.append({
      "stepId": "s3",
      "type": "layout_preview",
      "title": "生成杯子贴图预览",
      "targetAbility": "render_product_preview",
      "status": "pending",
      "userStatus": "等待前一步完成",
      "costCredits": 0,
      "idempotencyKey": f"{session_id}:s3:render_product_preview:{surface_id}",
      "failureFallback": "如果预览生成失败，会保留已确认的设计图，用户可重新生成预览或回到手动设计继续调整。",
      "requiresConfirmationBefore": False,
      "requiresConfirmationAfter": True,
      "summary": "把确认后的图片应用到商品设计面，生成可下单的预览。",
    })

  surface_supports_wrap = bool(default_surface.get("supportsWrap", default_surface.get("role") == "wrap"))
  if intent in {"make_seamless_wrap", "extract_pattern", "generate_variations"}:
    layout_mode = "wrap"
  elif intent == "ai_recreate" and surface_supports_wrap and not requests_original_print(message):
    layout_mode = "wrap"
  elif intent in {"print_as_is", "clean_and_print"}:
    layout_mode = "decal"
  else:
    layout_mode = "fit"
  target_width = optional_int(default_surface.get("width"))
  target_height = optional_int(default_surface.get("height"))
  target_dpi = optional_int(default_surface.get("dpi")) or 150
  risk_reasons: list[str] = []
  if intent in {"clean_and_print", "ai_recreate"}:
    risk_reasons.append("需要确认是否保留原图风格")
  if target_width and target_height:
    risk_reasons.append(f"最终生产图必须后处理到 {target_width}x{target_height}px，不能让用户手工凑尺寸")
  if intent == "make_seamless_wrap":
    risk_reasons.append("杯身环绕需要检查左右接缝；主体图不应直接强行连续化")
  context_asset_ids = normalize_id_list(asset_ids)
  context_source = str(context.get("source") or ("explicit_assets" if context_asset_ids else "prompt_only"))
  base_asset_role = str(context.get("baseAssetRole") or ("source_asset" if context_asset_ids else "prompt_only"))
  plan_output_count = requested_output_count or (4 if intent in {"generate_variations", "make_seamless_wrap"} and not asset else 1)
  return {
    "planId": "plan-" + secrets.token_hex(5),
    "sessionId": session_id,
    "intent": intent,
    "confidence": 0.72 if intent == "clarify" else 0.86,
    "needsUserConfirmation": needs_confirm,
    "status": "needs_confirmation" if needs_confirm else "clarifying",
    "outputCount": plan_output_count,
    "summaryForUser": summary,
    "questions": [] if needs_confirm else clarify_questions,
    "steps": steps,
    "layoutPlan": {
      "surfaceAssignments": [
        {
          "surfaceId": surface_id,
          "surfaceLabel": surface_label,
          "assetRef": source_ref,
          "mode": layout_mode,
          "scale": 1,
          "position": {"x": 0, "y": 0},
          "fullBleed": layout_mode == "wrap",
          "needsSeamless": intent == "make_seamless_wrap",
        }
      ],
      "postprocess": {
        "resizeToSurface": True,
        "targetWidth": target_width,
        "targetHeight": target_height,
        "dpi": target_dpi,
        "strategy": "exact_surface_fit",
        "allowMinorStretch": True,
        "allowPaddingOrCrop": True,
          "seamRiskCheck": intent == "make_seamless_wrap",
          "preferredWrapStrategy": "seamless_background_then_foreground" if intent == "make_seamless_wrap" else "full_bleed_cover" if layout_mode == "wrap" else None,
        "outputCount": plan_output_count,
      },
    },
    "risk": {
      "level": "medium" if intent in {"clean_and_print", "ai_recreate"} or layout_mode == "wrap" else "low",
      "reasons": risk_reasons,
    },
    "rejectedRoutes": rejected_routes,
    "contextTrace": {
      "source": context_source,
      "baseAssetRole": base_asset_role,
      "assetIds": context_asset_ids,
      "sourceAssetId": source_ref,
      "previousIntent": context.get("previousIntent"),
      "isFollowup": bool(context.get("isFollowup")),
    },
    "visionAnalysis": {
      "provider": vision_analysis.get("provider") or "heuristic",
      "model": vision_analysis.get("model") or "local-rules",
      "imageType": vision_analysis.get("imageType") or "unknown",
      "qualityRisk": vision_analysis.get("qualityRisk") or "unknown",
      "recommendedIntent": vision_analysis.get("recommendedIntent") or intent,
      "recommendedSurfaceId": vision_analysis.get("recommendedSurfaceId") or surface_id,
      "layoutMode": vision_analysis.get("layoutMode") or layout_mode,
      "needsSeamless": bool(vision_analysis.get("needsSeamless", layout_mode == "wrap")),
      "needsImage2": bool(vision_analysis.get("needsImage2", intent == "ai_recreate")),
      "confidence": vision_analysis.get("confidence") or (0.72 if intent == "clarify" else 0.86),
      "observations": text_list(vision_analysis.get("observations")),
      "risks": text_list(vision_analysis.get("risks")),
      "questions": text_list(vision_analysis.get("questions")),
      "skippedReason": vision_analysis.get("skippedReason"),
      "fallback": vision_analysis.get("fallback"),
      "modelError": vision_analysis.get("modelError"),
      "sourceAssetIds": normalize_id_list(vision_analysis.get("sourceAssetIds")),
      "imageCount": optional_int(vision_analysis.get("imageCount")) or len(normalize_id_list(asset_ids)),
      "referenceInstruction": vision_analysis.get("referenceInstruction"),
    },
    "modelRouting": {
      "vlProvider": vision_analysis.get("provider") or "heuristic",
      "vlModel": vision_analysis.get("model") or "local-rules",
      "planner": "business-api-state-machine",
      "controlPlane": "podi-business-api",
    },
    "qualityChecklist": {
      "intentMatched": intent != "clarify",
      "productSurfaceKnown": bool(surface_id),
      "usesWorkingMemory": context_source in {"working_memory", "session_results"},
      "requiresCostConfirmation": needs_confirm,
      "hidesSystemTerms": True,
      "sizePostprocessRequired": intent in {"ai_recreate", "make_seamless_wrap", "extract_pattern", "generate_variations"},
      "hasVisionEvidence": bool(vision_analysis),
    },
    "createdAt": now_label(),
  }


def agent_plan_output_count(plan: dict[str, Any]) -> int:
  for step in plan.get("steps") or []:
    if str(step.get("targetAbility") or "") in {"vl_analyze", "ask_user", "render_product_preview"}:
      continue
    value = optional_int(step.get("outputCount")) or 0
    if value:
      return clamp_agent_output_count(value)
  postprocess = plan.get("layoutPlan", {}).get("postprocess") if isinstance(plan.get("layoutPlan"), dict) else {}
  if isinstance(postprocess, dict):
    value = optional_int(postprocess.get("outputCount")) or 0
    if value:
      return clamp_agent_output_count(value)
  return 4 if str(plan.get("intent") or "") == "generate_variations" else 1


def quick_design_recommendation(plan: dict[str, Any]) -> dict[str, Any]:
  """Translate the controlled VL plan into language a product user can act on."""
  intent = str(plan.get("intent") or "clarify")
  assignment = ((plan.get("layoutPlan") or {}).get("surfaceAssignments") or [{}])[0]
  suggested_mode = str(assignment.get("mode") or "")
  if suggested_mode not in {"wrap", "fit", "cover", "decal"}:
    suggested_mode = None
  titles = {
    "print_as_is": "直接放在杯上",
    "clean_and_print": "先修好，再放上杯",
    "extract_pattern": "先提取图案，再设计",
    "make_seamless_wrap": "AI 适配杯身",
    "generate_variations": "先做几版设计",
    "ai_recreate": "AI 重新设计一版",
    "compose_product_design": "合成一套设计",
    "clarify": "先确认怎么做",
  }
  actions = {
    "print_as_is": "按建议放图",
    "clean_and_print": "按建议放图",
    "extract_pattern": "继续 AI 设计",
    "make_seamless_wrap": "按建议处理",
    "generate_variations": "继续 AI 设计",
    "ai_recreate": "继续 AI 设计",
    "compose_product_design": "继续 AI 设计",
    "clarify": "告诉 AI 怎么做",
  }
  risk_reasons = ((plan.get("risk") or {}).get("reasons") or [])
  return {
    "title": titles.get(intent, "AI 设计建议"),
    "actionLabel": actions.get(intent, "继续设计"),
    "reason": str(plan.get("summaryForUser") or "已结合图片和当前杯型给出建议。"),
    "risk": str(risk_reasons[0]) if risk_reasons else None,
    "suggestedMode": suggested_mode,
    # Complex multi-step work keeps using the dedicated conversational runtime;
    # direct placement and verified seamless export stay in the manual workflow.
    "requiresAgent": intent in {"extract_pattern", "generate_variations", "ai_recreate", "compose_product_design", "clarify"},
  }


def design_agent_demo_urls(intent: str, source_url: str | None, output_count: int = 1) -> list[str]:
  if intent == "print_as_is" and source_url:
    return [source_url]
  output_count = clamp_agent_output_count(output_count)
  url_pool = [
    public_demo("/demo/market/pattern-vintage-floral.webp"),
    public_demo("/demo/market/pattern-garden.webp"),
    public_demo("/demo/market/pattern-bloom.webp"),
    public_demo("/demo/market/pattern-dark-botanical.webp"),
  ]
  if intent == "generate_variations":
    return [url_pool[index % len(url_pool)] for index in range(output_count)]
  if intent == "make_seamless_wrap":
    return [url_pool[index % len(url_pool)] for index in range(output_count)]
  if intent == "ai_recreate":
    return [url_pool[(index + 2) % len(url_pool)] for index in range(max(1, output_count))]
  return [url_pool[0]]


def create_agent_result_assets(user_id: str, session: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
  trace = plan.get("contextTrace") if isinstance(plan.get("contextTrace"), dict) else {}
  context_asset_ids = normalize_id_list(trace.get("assetIds"))
  source_asset = first_user_asset(user_id, context_asset_ids or session.get("sourceAssetIds") or [])
  source_url = str(source_asset.get("url")) if source_asset else None
  intent = str(plan.get("intent") or "compose_product_design")
  output_count = agent_plan_output_count(plan)
  asset_type = {
    "generate_variations": "variation",
    "make_seamless_wrap": "pattern",
    "extract_pattern": "pattern",
    "ai_recreate": "ai_generated",
  }.get(intent, "processed")
  assets: list[dict[str, Any]] = []
  for index, url in enumerate(design_agent_demo_urls(intent, source_url, output_count)):
    asset = {
      "id": f"agent-asset-{secrets.token_hex(6)}",
      "type": asset_type,
      "title": f"{intent_title(intent)}结果 {index + 1}",
      "url": url,
      "thumbnailUrl": url,
      "source": "AI 帮我设计",
      "createdAt": now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "created",
      "usedInProducts": 0,
      "metadata": {
        "agentSessionId": session.get("sessionId"),
        "agentPlanId": plan.get("planId"),
        "intent": intent,
        "sourceAssetId": source_asset.get("id") if source_asset else None,
      },
    }
    prepare_asset_for_storage(user_id, asset, reason="agent-demo-result")
    ensure_bucket("assets", user_id).insert(0, asset)
    assets.append(asset)
  return assets


def is_midplatform_readable_image_url(value: Any) -> bool:
  if not is_public_http_url(value):
    return False
  parsed = urlparse(str(value))
  host = (parsed.hostname or "").lower()
  return host not in {"127.0.0.1", "localhost", "::1"} and not host.startswith("10.") and not host.startswith("192.168.")


def agent_primary_source_asset(user_id: str, session: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any] | None:
  trace = plan.get("contextTrace") if isinstance(plan.get("contextTrace"), dict) else {}
  candidate_ids = normalize_id_list(trace.get("assetIds"))
  if not candidate_ids:
    candidate_ids = normalize_id_list(session.get("sourceAssetIds"))
  if not candidate_ids:
    memory = session.get("workingMemory") if isinstance(session.get("workingMemory"), dict) else {}
    candidate_ids = normalize_id_list(memory.get("currentAssetIds")) or normalize_id_list(memory.get("lastResultAssetIds"))
  return first_user_asset(user_id, candidate_ids)


def agent_source_assets(user_id: str, session: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
  trace = plan.get("contextTrace") if isinstance(plan.get("contextTrace"), dict) else {}
  candidate_ids = normalize_id_list(trace.get("assetIds"))
  if not candidate_ids:
    candidate_ids = normalize_id_list(session.get("sourceAssetIds"))
  if not candidate_ids:
    memory = session.get("workingMemory") if isinstance(session.get("workingMemory"), dict) else {}
    candidate_ids = normalize_id_list(memory.get("currentAssetIds")) or normalize_id_list(memory.get("lastResultAssetIds"))
  return user_assets_by_ids(user_id, candidate_ids)


def agent_target_surface(session: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
  product_context = session.get("productContext") if isinstance(session.get("productContext"), dict) else {}
  surfaces = product_surface_defaults(product_context)
  assignments = ((plan.get("layoutPlan") or {}).get("surfaceAssignments") or [])
  target_id = optional_text((assignments[0] if assignments else {}).get("surfaceId"))
  for surface in surfaces:
    if target_id and surface.get("name") == target_id:
      return surface
  return surfaces[0] if surfaces else {"name": "front", "label": "主设计面", "width": 1800, "height": 1800, "dpi": 150}


def agent_latest_user_message(session: dict[str, Any]) -> str:
  for message in reversed(session.get("messages") or []):
    if message.get("role") != "user":
      continue
    message_type = str(message.get("type") or "").strip().lower()
    content = str(message.get("content") or "").strip()
    # Confirmation is an operational acknowledgement, not a new creative
    # instruction. Older sessions stored it as a plain text user message, so
    # keep the content guard for backward compatibility.
    if message_type == "confirmation" or content == "确认这套设计方案，开始生成。":
      continue
    if content:
      return content
  return ""


def reference_role_instruction_from_text(text: str, source_assets: list[dict[str, Any]]) -> str:
  if len(source_assets) < 2:
    return ""
  text = (text or "").lower()
  first_refs = ("图一", "第一张", "第1张", "1号图", "图1", "第一幅")
  second_refs = ("图二", "第二张", "第2张", "2号图", "图2", "第二幅")
  color_terms = ("色调", "配色", "颜色", "色彩", "调色", "氛围")
  element_terms = ("元素", "图案", "主体", "内容", "构图", "花纹", "造型")

  def role_hit(refs: tuple[str, ...], terms: tuple[str, ...]) -> bool:
    return any(ref in text and term in text for ref in refs for term in terms) and any(
      f"{ref}的{term}" in text or f"{ref}{term}" in text or f"{term}{ref}" in text
      for ref in refs
      for term in terms
    )

  first_color = role_hit(first_refs, color_terms)
  first_elements = role_hit(first_refs, element_terms)
  second_color = role_hit(second_refs, color_terms)
  second_elements = role_hit(second_refs, element_terms)

  if first_color and second_elements:
    return (
      "多图参考关系：参考图 1 主要用于色调、配色和整体氛围；参考图 2 主要用于元素、主体和图案。"
      "必须重新设计成一张适合杯子贴图面的完整平面图，不要直接拼贴或照搬任一原图。"
    )
  if first_elements and second_color:
    return (
      "多图参考关系：参考图 1 主要用于元素、主体和图案；参考图 2 主要用于色调、配色和整体氛围。"
      "必须重新设计成一张适合杯子贴图面的完整平面图，不要直接拼贴或照搬任一原图。"
    )
  return (
    f"用户提供了 {len(source_assets)} 张参考图。请先判断每张图承担的角色：色调、元素、构图、主体或风格；"
    "再整合成一张适合当前商品贴图面的完整设计，不要把某一张图原样贴到杯子上。"
  )


def agent_reference_role_instruction(session: dict[str, Any], plan: dict[str, Any], source_assets: list[dict[str, Any]]) -> str:
  return reference_role_instruction_from_text(
    " ".join([
      agent_latest_user_message(session),
      str(plan.get("summaryForUser") or ""),
    ]),
    source_assets,
  )


def create_agent_assets_from_urls(
  user_id: str,
  session: dict[str, Any],
  plan: dict[str, Any],
  urls: list[str],
  asset_type: str,
  business_run_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
  assets: list[dict[str, Any]] = []
  intent = str(plan.get("intent") or "compose_product_design")
  for index, url in enumerate(list(dict.fromkeys(urls))):
    asset = {
      "id": f"agent-asset-{secrets.token_hex(6)}",
      "type": asset_type,
      "title": f"{intent_title(intent)}结果 {index + 1}",
      "url": url,
      "thumbnailUrl": url,
      "source": "AI 帮我设计",
      "createdAt": now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "created",
      "usedInProducts": 0,
      "metadata": {
        "agentSessionId": session.get("sessionId"),
        "agentPlanId": plan.get("planId"),
        "intent": intent,
        "businessRunIds": business_run_ids or [],
        "executionMode": "real",
      },
    }
    prepare_asset_for_storage(user_id, asset, reason="agent-result")
    ensure_bucket("assets", user_id).insert(0, asset)
    assets.append(asset)
  return assets


def agent_business_prompt(session: dict[str, Any], plan: dict[str, Any], step: dict[str, Any]) -> str:
  product_name = str(session.get("productName") or session.get("productId") or "当前商品")
  latest_user_message = agent_latest_user_message(session)
  surface = agent_target_surface(session, plan)
  surface_label = surface.get("label") or surface.get("name") or "主设计面"
  summary = str(plan.get("summaryForUser") or "")
  return (
    f"为 {product_name} 生成可生产的 POD 商品设计素材。"
    f"用户目标：{latest_user_message or summary}。"
    f"当前阶段：{step.get('title') or intent_title(str(plan.get('intent') or 'compose_product_design'))}。"
    f"目标设计面：{surface_label}，尺寸 {surface.get('width') or 1800}x{surface.get('height') or 1800}px，DPI {surface.get('dpi') or 150}。"
    "保持主体清晰、适合印刷，不要文字水印，不要改变用户明确要求保留的主体。"
  )


def agent_image2_size_for_surface(surface: dict[str, Any]) -> str:
  width = optional_int(surface.get("width")) or 1024
  height = optional_int(surface.get("height")) or 1024
  ratio = width / max(1, height)
  if ratio >= 1.18:
    return "1536x1024"
  if ratio <= 0.85:
    return "1024x1536"
  return "1024x1024"


def agent_image2_design_prompt(session: dict[str, Any], plan: dict[str, Any], step: dict[str, Any], index: int, total: int) -> str:
  base_prompt = agent_business_prompt(session, plan, step)
  surface = agent_target_surface(session, plan)
  surface_label = surface.get("label") or surface.get("name") or "主设计面"
  vision = plan.get("visionAnalysis") if isinstance(plan.get("visionAnalysis"), dict) else {}
  observations = "；".join(text_list(vision.get("observations"))[:3])
  risks = "；".join(text_list(vision.get("risks"))[:2])
  source_assets = agent_source_assets(str(session.get("userId") or "demo-user"), session, plan)
  reference_instruction = agent_reference_role_instruction(session, plan, source_assets) or str(vision.get("referenceInstruction") or "")
  variant_note = f"这是第 {index + 1}/{total} 张候选，请和其他候选保持同一主题但构图、元素或色彩有明显差异。" if total > 1 else ""
  prompt_parts = [
    base_prompt,
    f"请输出一张独立的平面设计图，用于 {surface_label} 的杯子贴图面；不要生成杯子样机、产品摄影、UI、边框、价格、文字、水印或 Logo。",
    "如果有参考图或用户描述，必须先转化成适合印刷的完整设计，不要只是把原图直接贴到杯子上。",
    "画面需要干净、清晰、可商用印刷，边缘留有可裁切余量；若是杯身环绕，要优先考虑左右边缘衔接。",
  ]
  if reference_instruction:
    prompt_parts.append(reference_instruction)
  if observations:
    prompt_parts.append(f"图片理解要点：{observations}。")
  if risks:
    prompt_parts.append(f"风险提醒：{risks}，请在设计里规避。")
  if variant_note:
    prompt_parts.append(variant_note)
  return "".join(prompt_parts)


def invoke_midplatform_ability(
  ability_id: str,
  inputs: dict[str, Any],
  *,
  image_url: str | None = None,
  image_urls: list[str] | None = None,
  metadata: dict[str, Any] | None = None,
  timeout: float = 120.0,
) -> dict[str, Any]:
  payload: dict[str, Any] = {
    "inputs": inputs,
    "metadata": metadata or {},
  }
  if image_url:
    payload["imageUrl"] = image_url
  if image_urls:
    payload["images"] = [{"url": url, "name": f"reference-{index + 1}"} for index, url in enumerate(image_urls) if url]
  response = proxy_midplatform(f"/api/abilities/{ability_id}/invoke", payload, timeout=timeout)
  if response is None:
    return {"status": "failed", "message": "暂时连接不上图片生成服务，方案已保留，请稍后重试。"}
  return response


def parse_agent_image_response(response: dict[str, Any], default_message: str = "图片生成服务没有返回可用结果，请稍后重试。") -> dict[str, Any]:
  urls = collect_urls(response.get("images") or response.get("assets") or response.get("raw") or response)
  request_id = read_run_id(response) or str(response.get("requestId") or response.get("logId") or "")
  status = read_payload_status(response)
  error_text = read_payload_error(response)
  if urls:
    return {"status": "completed", "imageUrls": urls, "runIds": [request_id] if request_id else []}
  if status in {"queued", "running", "submitted", "pending"}:
    return {"status": "running", "message": "图片生成任务已提交，正在等待结果。", "runIds": [request_id] if request_id else []}
  if error_text:
    if is_busy_error(error_text):
      return {"status": "queued", "message": "图片生成服务正在排队，我已把任务保留在队列里。", "runIds": [request_id] if request_id else []}
    return {"status": "failed", "message": friendly_agent_error(error_text), "runIds": [request_id] if request_id else []}
  return {"status": "failed", "message": default_message, "runIds": [request_id] if request_id else []}


def preferred_agent_output_urls(payload: Any) -> list[str]:
  """Prefer the middle-platform OSS copy over a vendor's expiring result URL."""
  urls = collect_urls(payload)
  own_domain = OSS_PUBLIC_DOMAIN.rstrip("/")
  owned = [url for url in urls if str(url).startswith(own_domain)]
  return list(dict.fromkeys(owned or urls))


def build_agent_image2_fission_payload(
  *,
  session: dict[str, Any],
  prompt: str,
  surface: dict[str, Any],
  metadata: dict[str, Any],
  trace_id: str,
  source_url: str,
  index: int,
  total: int,
  route: str = "business_fission_image2",
  extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  return {
    "version": AGENT_IMAGE2_BUSINESS_VERSION,
    "imageUrl": source_url,
    "prompt": prompt,
    "variation_strength": "same_series",
    "quality": AGENT_IMAGE2_QUALITY,
    "size": "auto",
    "output_format": "png",
    "outputCount": 1,
    "candidateIndex": index + 1,
    "candidateCount": total,
    "source": "podi-client-agent",
    "channel": "client-agent",
    "traceId": trace_id,
    "requestId": f"{trace_id}-{secrets.token_hex(3)}",
    "clientContextId": session.get("sessionId"),
    "productId": session.get("productId"),
    "productName": session.get("productName"),
    "surfaceId": surface.get("name"),
    "surfaceLabel": surface.get("label"),
    "width": optional_int(surface.get("width")) or 1800,
    "height": optional_int(surface.get("height")) or 1800,
    "dpi": surface.get("dpi") or 150,
    "metadata": {
      **metadata,
      "agentRoute": route,
      "businessVersion": AGENT_IMAGE2_BUSINESS_VERSION,
      "promptPreview": prompt[:600],
      **(extra_metadata or {}),
    },
  }


def build_agent_image2_edit_payload(
  *,
  session: dict[str, Any],
  prompt: str,
  surface: dict[str, Any],
  metadata: dict[str, Any],
  trace_id: str,
  source_url: str,
  reference_urls: list[str] | None,
  index: int,
  total: int,
  route: str = "business_image_edit_image2",
  extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  references = [
    {
      "url": url,
      "label": f"参考图{ref_index + 1}",
      "mention": f"#参考图{ref_index + 1}",
      "role": "reference",
    }
    for ref_index, url in enumerate(reference_urls or [])
    if url and url != source_url
  ]
  reference_hint = ""
  if references:
    reference_hint = " 请综合参考图的元素、色调或构图，但最终只输出一张完整可生产的设计图。"
  return {
    "version": "gpt-image2-editor-v1",
    "imageUrl": source_url,
    "instruction": f"{prompt}{reference_hint}",
    "prompt": f"{prompt}{reference_hint}",
    "skill": "creative_recompose",
    "quality": AGENT_IMAGE2_QUALITY,
    "size": agent_image2_size_for_surface(surface),
    "output_format": "png",
    "source": "podi-client-agent",
    "channel": "client-agent",
    "traceId": trace_id,
    "requestId": f"{trace_id}-{secrets.token_hex(3)}",
    "clientContextId": session.get("sessionId"),
    "productId": session.get("productId"),
    "productName": session.get("productName"),
    "surfaceId": surface.get("name"),
    "surfaceLabel": surface.get("label"),
    "width": optional_int(surface.get("width")) or 1800,
    "height": optional_int(surface.get("height")) or 1800,
    "dpi": surface.get("dpi") or 150,
    "referenceImages": references,
    "inputs": {
      "referenceImages": references,
      "image_urls": [item["url"] for item in references],
      "candidateIndex": index + 1,
      "candidateCount": total,
    },
    "metadata": {
      **metadata,
      "agentRoute": route,
      "businessVersion": "gpt-image2-editor-v1",
      "promptPreview": prompt[:600],
      "referenceImageUrls": [item["url"] for item in references],
      "productionCanvas": agent_production_canvas(surface),
      **(extra_metadata or {}),
    },
  }


def agent_image2_aspect_ratio(surface: dict[str, Any]) -> str:
  width = optional_int(surface.get("width")) or 1024
  height = optional_int(surface.get("height")) or 1024
  ratio = width / max(1, height)
  if ratio >= 1.6:
    return "16:9"
  if ratio >= 1.25:
    return "3:2"
  if ratio <= 0.68:
    return "2:3"
  if ratio <= 0.86:
    return "3:4"
  return "1:1"


def agent_production_canvas(surface: dict[str, Any]) -> dict[str, Any]:
  """Describe the exact print file that the middle platform must export."""
  return {
    "enabled": True,
    "targetWidth": optional_int(surface.get("width")) or 1800,
    "targetHeight": optional_int(surface.get("height")) or 1800,
    "targetDpi": optional_int(surface.get("dpi")) or 150,
    "mode": "cover",
    "purpose": "agent_design_surface",
  }


def submit_agent_text_to_image_task(
  *,
  session: dict[str, Any],
  plan: dict[str, Any],
  step: dict[str, Any],
  prompt: str,
  surface: dict[str, Any],
  metadata: dict[str, Any],
) -> dict[str, Any]:
  if not AGENT_TEXT2IMAGE_AVAILABLE:
    return {
      "status": "failed",
      "message": "AI 原创生图暂时没有可用的中台执行通道，请稍后重试。",
    }
  response = proxy_midplatform(
    "/api/ability-tasks",
    {
      "abilityId": AGENT_TEXT2IMAGE_ABILITY_ID,
      "inputs": {
        "prompt": prompt,
        "aspect_ratio": agent_image2_aspect_ratio(surface),
      },
      "metadata": {
        **metadata,
        "agentRoute": "kie_image2_text_to_image",
        "targetWidth": optional_int(surface.get("width")),
        "targetHeight": optional_int(surface.get("height")),
        "targetDpi": optional_int(surface.get("dpi")) or 150,
        "resultRole": "design_candidate",
        "productionCanvas": agent_production_canvas(surface),
      },
    },
    timeout=30.0,
  )
  if response is None:
    return {"status": "failed", "message": "暂时连接不上 AI 生图服务，请稍后重试。"}
  error_text = read_payload_error(response)
  task_id = str(response.get("id") or response.get("taskId") or "").strip()
  status_text = read_payload_status(response)
  if task_id and status_text not in {"failed", "error", "cancelled"}:
    return {
      "status": "queued" if status_text in {"queued", "pending"} else "running",
      "message": "AI 已开始生成设计候选图，完成后会自动回到当前对话。",
      "runIds": [task_id],
      "abilityTaskIds": [task_id],
    }
  return {
    "status": "failed",
    "message": friendly_agent_error(error_text or "AI 生图任务没有成功创建。"),
  }


def submit_agent_image2_generate(
  user_id: str,
  session: dict[str, Any],
  plan: dict[str, Any],
  step: dict[str, Any],
  *,
  index: int,
  total: int,
) -> dict[str, Any]:
  source_assets = agent_source_assets(user_id, session, plan)
  source_asset = source_assets[0] if source_assets else agent_primary_source_asset(user_id, session, plan)
  source_url = str((source_asset or {}).get("url") or "")
  readable_source_url = source_url if is_midplatform_readable_image_url(source_url) else ""
  readable_source_urls = list(dict.fromkeys([
    str(item.get("url") or item.get("thumbnailUrl") or "")
    for item in source_assets
    if is_midplatform_readable_image_url(item.get("url") or item.get("thumbnailUrl"))
  ]))
  surface = agent_target_surface(session, plan)
  prompt = agent_image2_design_prompt(session, plan, step, index, total)
  trace_id = f"agent-{session.get('sessionId')}-{plan.get('planId')}-{step.get('stepId')}-{index + 1}"
  reference_instruction = agent_reference_role_instruction(session, plan, source_assets)
  metadata = {
    "source": "podi-client-agent",
    "channel": "client-agent",
    "traceId": trace_id,
    "agentSessionId": session.get("sessionId"),
    "agentPlanId": plan.get("planId"),
    "agentStepId": step.get("stepId"),
    "intent": plan.get("intent"),
    "productId": session.get("productId"),
    "productName": session.get("productName"),
    "surfaceId": surface.get("name"),
    "surfaceLabel": surface.get("label"),
    "sourceAssetId": (source_asset or {}).get("id"),
    "sourceAssetIds": [item.get("id") for item in source_assets if item.get("id")],
    "sourceImageCount": len(source_assets),
    "referenceRoleInstruction": reference_instruction,
    "candidateIndex": index + 1,
    "candidateCount": total,
  }
  inputs = {
    "prompt": prompt,
    "size": agent_image2_size_for_surface(surface),
    "quality": AGENT_IMAGE2_QUALITY,
    "background": "opaque",
    "output_format": "png",
    "n": 1,
  }
  if len(readable_source_urls) > 1:
    edit_payload = build_agent_image2_edit_payload(
      session=session,
      prompt=prompt,
      surface=surface,
      metadata=metadata,
      trace_id=trace_id,
      source_url=readable_source_urls[0],
      reference_urls=readable_source_urls[1:],
      index=index,
      total=total,
      route="business_image_edit_multi_reference",
    )
    return submit_agent_business_run("/api/business/image-edit/runs", edit_payload, poll_seconds=0)

  if readable_source_url:
    edit_payload = build_agent_image2_edit_payload(
      session=session,
      prompt=prompt,
      surface=surface,
      metadata=metadata,
      trace_id=trace_id,
      source_url=readable_source_url,
      reference_urls=[],
      index=index,
      total=total,
      route="business_image_edit_single_reference",
    )
    return submit_agent_business_run("/api/business/image-edit/runs", edit_payload, poll_seconds=0)

  if source_url and not readable_source_url:
    return {
      "status": "failed",
      "message": "我已经完成设计规划，但这张参考图目前只是本地预览地址，图片生成服务读不到。请先接通 OSS 上传，或换用已经在云端的素材后再生成。",
    }

  if not readable_source_url:
    return submit_agent_text_to_image_task(
      session=session,
      plan=plan,
      step=step,
      prompt=prompt,
      surface=surface,
      metadata=metadata,
    )

  ability_id = AGENT_IMAGE2_EDIT_ABILITY_ID
  response = invoke_midplatform_ability(
    ability_id,
    inputs,
    image_url=readable_source_url or None,
    metadata=metadata,
    timeout=180.0,
  )
  return parse_agent_image_response(response)


def build_agent_business_payload(
  user_id: str,
  session: dict[str, Any],
  plan: dict[str, Any],
  step: dict[str, Any],
  index: int = 0,
  total: int = 1,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
  ability = str(step.get("targetAbility") or "")
  endpoint = AGENT_BUSINESS_ENDPOINT_BY_ABILITY.get(ability)
  if not endpoint:
    return None, None, "这个设计步骤还没有接入可执行能力。"

  source_asset = agent_primary_source_asset(user_id, session, plan)
  source_url = str((source_asset or {}).get("url") or "")
  # Image2 can generate from a design brief alone. If the user uploaded a local-only
  # image, VL has already extracted the useful context into the prompt; do not block
  # execution only because the remote middle platform cannot fetch the local file.
  source_required = ability not in {"image2_recreate"}
  if source_required and not is_midplatform_readable_image_url(source_url):
    return None, None, "我已经完成设计规划，但这张参考图目前只是本地预览地址，图片处理服务读不到。请先接通 OSS 上传，或换用已经在云端的素材后再生成。"
  if source_url and not is_midplatform_readable_image_url(source_url):
    source_url = ""

  surface = agent_target_surface(session, plan)
  width = optional_int(surface.get("width")) or 1800
  height = optional_int(surface.get("height")) or 1800
  prompt = agent_business_prompt(session, plan, step)
  trace_id = f"agent-{session.get('sessionId')}-{plan.get('planId')}-{step.get('stepId')}-{index + 1}"
  base_payload = {
    "prompt": prompt,
    "instruction": prompt,
    "source": "podi-client-agent",
    "channel": "client-agent",
    "traceId": trace_id,
    "requestId": f"{trace_id}-{secrets.token_hex(3)}",
    "clientContextId": session.get("sessionId"),
    "productId": session.get("productId"),
    "productName": session.get("productName"),
    "surfaceId": surface.get("name"),
    "surfaceLabel": surface.get("label"),
    "width": width,
    "height": height,
    "dpi": surface.get("dpi") or 150,
    "metadata": {
      "agentSessionId": session.get("sessionId"),
      "agentPlanId": plan.get("planId"),
      "agentStepId": step.get("stepId"),
      "intent": plan.get("intent"),
      "sourceAssetId": (source_asset or {}).get("id"),
      "productionCanvas": agent_production_canvas(surface),
    },
  }
  if source_url:
    base_payload["imageUrl"] = source_url
  if ability == "variation":
    base_payload.update({
      "outputCount": 1,
      "candidateIndex": index + 1,
      "candidateCount": total,
      "seed": secrets.randbelow(2_000_000_000),
      "inputs": {"candidateIndex": index + 1, "candidateCount": total},
    })
  elif ability in {"two_way_seamless", "four_way_seamless"}:
    base_payload.update({
      "patternType": "twoway" if ability == "two_way_seamless" else "seamless",
      "mode": "twoway" if ability == "two_way_seamless" else "seamless",
    })
  elif ability in {"image2_recreate", "postprocess_to_surface", "render_product_preview"}:
    base_payload.update({
      "designBrief": prompt,
      # 当前本地中台 product-design 能力没有 cup 枚举；杯子类先按 generic 路由，
      # 业务侧仍在 prompt / productName / surface metadata 中保留具体杯型约束。
      "productType": "generic",
      "scene": "print_mockup",
      "quality": "production",
      "size": "auto",
      "output_format": "png",
    })
  return endpoint, base_payload, None


def submit_agent_business_run(endpoint: str, payload: dict[str, Any], poll_seconds: int = 75) -> dict[str, Any]:
  response = proxy_midplatform(endpoint, payload, timeout=20.0)
  if response is None:
    return {"status": "failed", "message": "暂时连接不上图片处理服务，方案已保留，请稍后重试。"}
  error_text = read_payload_error(response)
  urls = collect_urls(response.get("imageUrls") or response.get("images") or response.get("resultPayload") or response.get("result"))
  run_id = read_run_id(response)
  if urls:
    return {"status": "completed", "imageUrls": urls, "runIds": [run_id] if run_id else []}
  if error_text and not run_id:
    if is_busy_error(error_text):
      return {"status": "queued", "message": "图片处理服务正在排队，我已把任务保留在队列里。", "runIds": []}
    return {"status": "failed", "message": friendly_agent_error(error_text)}
  if not run_id:
    status_text = read_payload_status(response)
    if status_text in {"queued", "running", "submitted", "pending"}:
      return {"status": "running", "message": "图片处理任务已提交，正在等待结果。", "runIds": []}
    return {"status": "failed", "message": "图片处理服务没有返回任务编号或图片结果。"}

  if poll_seconds <= 0:
    return {"status": "running", "message": "图片处理任务已提交，正在等待结果。", "runIds": [run_id]}

  deadline = time.time() + max(5, poll_seconds)
  while time.time() < deadline:
    time.sleep(2.5)
    detail = proxy_midplatform("/api/business/runs/get", {"runId": run_id, "detail": "full"}, timeout=15.0)
    if detail is None:
      continue
    urls = collect_urls(detail.get("imageUrls") or detail.get("images") or detail.get("resultPayload") or detail.get("result"))
    if urls:
      return {"status": "completed", "imageUrls": urls, "runIds": [run_id]}
    status_text = read_payload_status(detail)
    error_text = read_payload_error(detail)
    if status_text in {"failed", "error"} or error_text:
      if is_busy_error(error_text):
        return {"status": "queued", "message": "图片处理服务正在排队，我已把任务保留在队列里。", "runIds": [run_id]}
      return {"status": "failed", "message": friendly_agent_error(error_text or "图片处理失败。"), "runIds": [run_id]}
  return {"status": "running", "message": "图片处理还在进行中，稍后刷新会继续获取结果。", "runIds": [run_id]}


def refresh_running_agent_session(user_id: str, session: dict[str, Any]) -> bool:
  if session.get("status") != "executing":
    return False
  plan_id = str(session.get("currentPlanId") or "")
  plan = next((item for item in session.get("plans") or [] if item.get("planId") == plan_id), None)
  if not plan:
    return False
  execution = plan.get("execution") if isinstance(plan.get("execution"), dict) else {}
  if str(execution.get("status") or "") not in {"running", "queued"}:
    return False
  run_ids = normalize_id_list(execution.get("businessRunIds"))
  ability_task_ids = normalize_id_list(execution.get("abilityTaskIds"))
  if not run_ids and not ability_task_ids:
    return False

  image_urls: list[str] = []
  still_running = False
  failure_message = ""
  for run_id in run_ids:
    detail = proxy_midplatform("/api/business/runs/get", {"runId": run_id, "detail": "full"}, timeout=15.0)
    if detail is None:
      still_running = True
      continue
    urls = collect_urls(detail.get("imageUrls") or detail.get("images") or detail.get("resultPayload") or detail.get("result"))
    if urls:
      image_urls.extend(urls)
      continue
    status_text = read_payload_status(detail)
    error_text = read_payload_error(detail)
    if status_text in {"queued", "running", "submitted", "pending"}:
      still_running = True
      continue
    if status_text in {"failed", "error"} or error_text:
      failure_message = friendly_agent_error(error_text or "图片处理失败，请重新生成或换一种设计路线。")
      continue
    still_running = True

  for task_id in ability_task_ids:
    detail = get_midplatform_ability_task(task_id, timeout=15.0)
    if detail is None:
      still_running = True
      continue
    task_status = str(detail.get("status") or detail.get("finalStatus") or detail.get("final_status") or "").strip().lower()
    result_payload = detail.get("resultPayload") or detail.get("result_payload") or {}
    urls = preferred_agent_output_urls(result_payload)
    if urls:
      image_urls.extend(urls)
      continue
    if task_status in {"queued", "running", "pending", "submitting", "submitted"}:
      still_running = True
      continue
    if task_status in {"failed", "error", "cancelled", "canceled"}:
      failure_message = friendly_agent_error(
        str(detail.get("errorMessage") or detail.get("error_message") or "AI 生图任务执行失败，请稍后重试。")
      )
      continue
    still_running = True

  expected_count = agent_plan_output_count(plan)
  if image_urls and (len(image_urls) >= expected_count or not still_running):
    asset_type = {
      "generate_variations": "variation",
      "make_seamless_wrap": "pattern",
      "extract_pattern": "pattern",
      "ai_recreate": "ai_generated",
    }.get(str(plan.get("intent") or ""), "processed")
    result_refs = list(dict.fromkeys([*run_ids, *ability_task_ids]))
    result_assets = create_agent_assets_from_urls(user_id, session, plan, image_urls, asset_type, result_refs)
    result_ids = [asset["id"] for asset in result_assets]
    session["resultAssetIds"] = list(dict.fromkeys([*result_ids, *(session.get("resultAssetIds") or [])]))
    remember_agent_results(session, result_ids, plan)
    completed_at = now_label()
    for step in executable_agent_steps(plan):
      step["status"] = "completed"
      step["userStatus"] = agent_step_user_status("completed")
      step["completedAt"] = completed_at
    plan["status"] = "preview_ready"
    plan["needsUserConfirmation"] = False
    execution["status"] = "completed"
    execution["userStatus"] = "已生成阶段结果"
    execution["resultAssetIds"] = result_ids
    execution["abilityTaskIds"] = ability_task_ids
    execution["completedAt"] = completed_at
    plan["execution"] = execution
    for tool_call in reversed(session.get("toolCalls") or []):
      if str(tool_call.get("planId") or "") == plan_id and str(tool_call.get("status") or "") in {"running", "queued"}:
        tool_call["status"] = "completed"
        tool_call["userStatus"] = "已生成阶段结果"
        tool_call["resultAssetIds"] = result_ids
        tool_call["completedAt"] = completed_at
        break
    session["steps"] = plan.get("steps") or []
    session["status"] = "preview_ready"
    session["updatedAt"] = completed_at
    if not plan.get("resultMessageId"):
      message_id = "msg-" + secrets.token_hex(5)
      session.setdefault("messages", []).append({
        "messageId": message_id,
        "role": "assistant",
        "type": "result",
        "content": "图片已经生成完成，结果在下面。你可以采用整套设计，也可以继续让我修改。",
        "assetIds": result_ids,
        "planId": plan_id,
        "createdAt": completed_at,
      })
      plan["resultMessageId"] = message_id
    save_state(STATE)
    return True

  if failure_message and not still_running:
    fail_agent_plan_execution(session, plan, failure_message)
    save_state(STATE)
    return True

  return False


def design_agent_sessions_for_bootstrap(user_id: str) -> list[dict[str, Any]]:
  sessions = ensure_bucket("designAgentSessions", user_id)
  changed = False
  for session in sessions:
    changed = refresh_running_agent_session(user_id, session) or changed
  if changed:
    save_state(STATE)

  snapshots: list[dict[str, Any]] = []
  for session in sessions[:20]:
    result_assets = []
    for asset_id in session.get("resultAssetIds") or []:
      asset = find_asset(user_id, str(asset_id))
      if asset:
        result_assets.append(asset)
    preview_asset = find_asset(user_id, str(session.get("currentPreviewAssetId") or ""))
    snapshots.append({
      **session,
      "resultAssets": result_assets,
      "previewAsset": preview_asset,
    })
  return snapshots


def agent_step_user_status(status: str) -> str:
  return {
    "pending": "等待前一步完成",
    "waiting_confirmation": "等待你确认",
    "queued": "已排队",
    "running": "正在生成",
    "completed": "已完成",
    "failed": "处理失败",
    "needs_user": "需要你补充",
  }.get(status, "等待处理")


def agent_execution_mode_label() -> str:
  if AGENT_EXECUTION_MODE in {"real", "midplatform"}:
    return "real"
  return "local_preview"


def validate_agent_plan_steps(plan: dict[str, Any]) -> list[str]:
  errors: list[str] = []
  for step in plan.get("steps") or []:
    ability = str(step.get("targetAbility") or "")
    if ability not in AGENT_ALLOWED_STEP_ABILITIES:
      errors.append(f"不支持的处理动作：{ability or 'unknown'}")
  return errors


def executable_agent_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
  steps: list[dict[str, Any]] = []
  for step in plan.get("steps") or []:
    ability = str(step.get("targetAbility") or "")
    if ability in {"vl_analyze", "ask_user"}:
      continue
    if step.get("status") in {"pending", "waiting_confirmation", "queued", "running"}:
      steps.append(step)
  return steps


def fail_agent_plan_execution(session: dict[str, Any], plan: dict[str, Any], message: str) -> dict[str, Any]:
  now = now_label()
  for step in executable_agent_steps(plan):
    step["status"] = "failed"
    step["userStatus"] = agent_step_user_status("failed")
    step["completedAt"] = now
    step["errorMessage"] = message
  plan["status"] = "failed"
  plan["needsUserConfirmation"] = True
  for tool_call in reversed(session.get("toolCalls") or []):
    if str(tool_call.get("planId") or "") == str(plan.get("planId") or "") and str(tool_call.get("status") or "") in {"running", "queued"}:
      tool_call["status"] = "failed"
      tool_call["userStatus"] = "处理失败"
      tool_call["errorMessage"] = message
      tool_call["completedAt"] = now
      break
  session["steps"] = plan.get("steps") or []
  session["status"] = "execution_failed"
  session["updatedAt"] = now
  session.setdefault("messages", []).append({
    "messageId": "msg-" + secrets.token_hex(5),
    "role": "assistant",
    "type": "notice",
    "content": message,
    "planId": plan.get("planId"),
    "createdAt": now,
  })
  return {"resultAssets": [], "status": "failed", "message": message}


def execute_design_agent_plan(user_id: str, session: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
  validation_errors = validate_agent_plan_steps(plan)
  if validation_errors:
    return fail_agent_plan_execution(session, plan, "这个设计方案包含暂不支持的处理动作，我已保留方案，请重新生成或换一种描述。")

  steps = executable_agent_steps(plan)
  if not steps:
    return fail_agent_plan_execution(session, plan, "这个设计方案没有可执行的处理步骤，请重新生成方案。")

  execution_mode = agent_execution_mode_label()
  started_at = now_label()
  for step in steps:
    step["status"] = "running"
    step["userStatus"] = agent_step_user_status("running")
    step["startedAt"] = started_at

  if execution_mode == "real":
    run_ids: list[str] = []
    ability_task_ids: list[str] = []
    image_urls: list[str] = []
    pending_message = ""
    executable_business_steps = [step for step in steps if str(step.get("targetAbility") or "") != "render_product_preview"] or steps[:1]
    for step in executable_business_steps:
      output_count = clamp_agent_output_count(optional_int(step.get("outputCount")) or agent_plan_output_count(plan))
      ability = str(step.get("targetAbility") or "")
      calls = output_count if ability in {"variation", "image2_recreate"} else 1
      for index in range(calls):
        if ability == "image2_recreate":
          result = submit_agent_image2_generate(user_id, session, plan, step, index=index, total=calls)
        else:
          endpoint, payload, payload_error = build_agent_business_payload(user_id, session, plan, step, index=index, total=calls)
          if payload_error or not endpoint or not payload:
            return fail_agent_plan_execution(session, plan, payload_error or "这个设计步骤还没有可执行的图片处理能力。")
          result = submit_agent_business_run(endpoint, payload, poll_seconds=0)
        run_ids.extend([str(item) for item in (result.get("runIds") or []) if item])
        ability_task_ids.extend([str(item) for item in (result.get("abilityTaskIds") or []) if item])
        if result.get("status") == "completed":
          image_urls.extend([str(url) for url in (result.get("imageUrls") or []) if url])
          continue
        if result.get("status") in {"queued", "running"}:
          pending_message = str(result.get("message") or "图片处理还在进行中，稍后会继续获取结果。")
          step["status"] = "running" if result.get("status") == "running" else "queued"
          step["userStatus"] = agent_step_user_status(str(step["status"]))
          continue
        return fail_agent_plan_execution(session, plan, str(result.get("message") or "图片处理失败，请稍后重试。"))

    if not image_urls:
      plan["status"] = "running"
      plan["needsUserConfirmation"] = False
      session["steps"] = plan.get("steps") or []
      session["status"] = "executing"
      session["updatedAt"] = now_label()
      tool_call = {
        "toolCallId": "tool-" + secrets.token_hex(5),
        "planId": plan.get("planId"),
        "ability": str((executable_business_steps[0] if executable_business_steps else steps[0]).get("targetAbility") or ""),
        "status": "running",
        "userStatus": pending_message or "图片处理还在进行中",
        "executionMode": execution_mode,
        "businessRunIds": run_ids,
        "abilityTaskIds": ability_task_ids,
        "startedAt": started_at,
      }
      session.setdefault("toolCalls", []).append(tool_call)
      plan["toolCall"] = tool_call
      plan["runIds"] = run_ids
      plan["execution"] = {
        "mode": execution_mode,
        "status": "running",
        "userStatus": pending_message or "图片处理还在进行中",
        "businessRunIds": run_ids,
        "abilityTaskIds": ability_task_ids,
        "startedAt": started_at,
      }
      return {"resultAssets": [], "resultAssetIds": [], "toolCall": tool_call, "status": "running", "message": pending_message}

    asset_type = {
      "generate_variations": "variation",
      "make_seamless_wrap": "pattern",
      "extract_pattern": "pattern",
      "ai_recreate": "ai_generated",
    }.get(str(plan.get("intent") or ""), "processed")
    result_assets = create_agent_assets_from_urls(user_id, session, plan, image_urls, asset_type, run_ids)
    result_ids = [asset["id"] for asset in result_assets]
    completed_at = now_label()
    for step in steps:
      step["status"] = "completed"
      step["userStatus"] = agent_step_user_status("completed")
      step["completedAt"] = completed_at
    total_cost = sum(int(step.get("costCredits") or 0) for step in (plan.get("steps") or []))
    primary_ability = str((executable_business_steps[0] if executable_business_steps else steps[0]).get("targetAbility") or "render_product_preview")
    tool_call = {
      "toolCallId": "tool-" + secrets.token_hex(5),
      "planId": plan.get("planId"),
      "ability": primary_ability,
      "abilityLabel": AGENT_ABILITY_USER_LABELS.get(primary_ability, "生成设计结果"),
      "status": "completed",
      "userStatus": "已生成阶段结果",
      "executionMode": execution_mode,
      "businessRunIds": run_ids,
      "idempotencyKeys": [step.get("idempotencyKey") for step in steps if step.get("idempotencyKey")],
      "costCredits": total_cost,
      "resultAssetIds": result_ids,
      "startedAt": started_at,
      "completedAt": completed_at,
    }
    session.setdefault("toolCalls", []).append(tool_call)
    plan["toolCall"] = tool_call
    plan["runIds"] = run_ids
    plan["execution"] = {
      "mode": execution_mode,
      "status": "completed",
      "userStatus": "已生成阶段结果",
      "resultAssetIds": result_ids,
      "businessRunIds": run_ids,
      "completedAt": completed_at,
    }
    return {"resultAssets": result_assets, "resultAssetIds": result_ids, "toolCall": tool_call, "status": "completed"}

  result_assets = create_agent_result_assets(user_id, session, plan)
  result_ids = [asset["id"] for asset in result_assets]
  completed_at = now_label()
  for step in steps:
    step["status"] = "completed"
    step["userStatus"] = agent_step_user_status("completed")
    step["completedAt"] = completed_at

  total_cost = sum(int(step.get("costCredits") or 0) for step in (plan.get("steps") or []))
  primary_ability = str(steps[0].get("targetAbility") or "render_product_preview")
  tool_call = {
    "toolCallId": "tool-" + secrets.token_hex(5),
    "planId": plan.get("planId"),
    "ability": primary_ability,
    "abilityLabel": AGENT_ABILITY_USER_LABELS.get(primary_ability, "生成设计结果"),
    "status": "completed",
    "userStatus": "已生成阶段结果",
    "executionMode": execution_mode,
    "idempotencyKeys": [step.get("idempotencyKey") for step in steps if step.get("idempotencyKey")],
    "costCredits": total_cost,
    "resultAssetIds": result_ids,
    "startedAt": started_at,
    "completedAt": completed_at,
  }
  session.setdefault("toolCalls", []).append(tool_call)
  plan["execution"] = {
    "mode": execution_mode,
    "status": "completed",
    "userStatus": "已生成阶段结果",
    "resultAssetIds": result_ids,
    "completedAt": completed_at,
  }
  return {"resultAssets": result_assets, "resultAssetIds": result_ids, "toolCall": tool_call, "status": "completed"}


def normalize_shipping_address(raw: Any) -> dict[str, Any]:
  if not isinstance(raw, dict):
    return {}
  recipient_name = raw.get("recipientName") or raw.get("recipient")
  phone_number = raw.get("phoneNumber") or raw.get("shipPhoneNumber") or raw.get("phone")
  state = raw.get("state") or raw.get("province") or raw.get("shipState")
  district = raw.get("district") or raw.get("county") or raw.get("shipDistrict")
  postal_code = raw.get("postalCode") or raw.get("shipPostaCode") or raw.get("zipCode")
  return {
    **raw,
    "country": raw.get("country") or raw.get("shipCountry") or "CN",
    "state": state or "",
    "city": raw.get("city") or raw.get("shipCity") or "",
    "district": district or "",
    "postalCode": postal_code or "",
    "address": raw.get("address") or raw.get("shipAddress") or "",
    "phoneNumber": phone_number or "",
    "recipientName": recipient_name or "",
    "email": raw.get("email") or raw.get("shipEmail") or "",
  }


def default_client_display_name(phone: str) -> str:
  digest = hashlib.sha1(phone.encode("utf-8")).hexdigest()
  numeric_id = int(digest[:10], 16) % 1_000_000
  return f"创品达人{numeric_id:06d}"


def create_session(phone: str, display_name: str | None = None) -> dict[str, Any]:
  user_id = f"user-{phone}"
  users = STATE.setdefault("users", {})
  user = users.get(user_id) or {
    "id": user_id,
    "username": phone,
    "email": f"{phone}@podi.local",
    "phone": phone,
    "role": "client",
    "status": "active",
    "displayName": display_name or default_client_display_name(phone),
    "tenantId": "main-site",
    "clientId": "main-site",
    "createdAt": now_iso(),
    "lastLoginAt": None,
  }
  if display_name:
    user["displayName"] = display_name
  user["lastLoginAt"] = now_iso()
  users[user_id] = user

  for bucket_name in ("assets", "tasks", "orders", "publishApplications"):
    STATE.setdefault(bucket_name, {}).setdefault(user_id, [])
  ensure_wallet(user_id)

  access_token = "podi_access_" + secrets.token_urlsafe(24)
  refresh_token = "podi_refresh_" + secrets.token_urlsafe(24)
  STATE.setdefault("sessions", {})[access_token] = {
    "userId": user_id,
    "refreshToken": refresh_token,
    "expiresAt": time.time() + 86400,
  }
  save_state(STATE)
  return {
    "accessToken": access_token,
    "tokenType": "Bearer",
    "expiresIn": 86400,
    "refreshToken": refresh_token,
    "role": "client",
    "user": user,
  }


def create_admin_session(username: str) -> dict[str, Any]:
  user_id = f"admin-{username}"
  user = {
    "id": user_id,
    "username": username,
    "email": f"{username}@podi.local",
    "phone": None,
    "role": "admin",
    "status": "active",
    "displayName": "运营管理员",
    "tenantId": "main-site",
    "clientId": "main-site",
    "createdAt": now_iso(),
    "lastLoginAt": now_iso(),
  }
  STATE.setdefault("users", {})[user_id] = user
  access_token = "podi_admin_" + secrets.token_urlsafe(24)
  refresh_token = "podi_admin_refresh_" + secrets.token_urlsafe(24)
  STATE.setdefault("sessions", {})[access_token] = {
    "userId": user_id,
    "refreshToken": refresh_token,
    "expiresAt": time.time() + 86400,
  }
  save_state(STATE)
  return {
    "accessToken": access_token,
    "tokenType": "Bearer",
    "expiresIn": 86400,
    "refreshToken": refresh_token,
    "role": "admin",
    "user": user,
  }


def user_from_auth(headers: dict[str, str]) -> dict[str, Any] | None:
  auth = headers.get("authorization", "")
  if not auth.lower().startswith("bearer "):
    return None
  token = auth.split(" ", 1)[1].strip()
  session = STATE.setdefault("sessions", {}).get(token)
  if not session or session.get("expiresAt", 0) < time.time():
    return None
  return STATE.setdefault("users", {}).get(session.get("userId"))


def admin_from_auth(headers: dict[str, str]) -> dict[str, Any] | None:
  user = user_from_auth(headers)
  if user and user.get("role") == "admin":
    return user
  return None


def iter_orders(user_id: str | None = None) -> list[tuple[str, dict[str, Any]]]:
  orders_by_user = STATE.setdefault("orders", {})
  rows: list[tuple[str, dict[str, Any]]] = []
  for current_user_id, orders in orders_by_user.items():
    if user_id and current_user_id != user_id:
      continue
    for order in orders:
      rows.append((current_user_id, order))
  rows.sort(key=lambda item: str(item[1].get("createdAt") or ""), reverse=True)
  return rows


def find_order(order_id: str) -> tuple[str | None, dict[str, Any] | None]:
  for user_id, order in iter_orders():
    if order.get("id") == order_id:
      return user_id, order
  return None, None


def find_complaint(complaint_id: str) -> tuple[str | None, dict[str, Any] | None]:
  for user_id, items in STATE.setdefault("complaints", {}).items():
    if not isinstance(items, list):
      continue
    for item in items:
      if isinstance(item, dict) and item.get("id") == complaint_id:
        return user_id, item
  return None, None


def iter_publish_applications(status: str | None = None) -> list[tuple[str, dict[str, Any]]]:
  applications_by_user = STATE.setdefault("publishApplications", {})
  rows: list[tuple[str, dict[str, Any]]] = []
  for user_id, applications in applications_by_user.items():
    for item in applications:
      if status and item.get("status") != status:
        continue
      rows.append((user_id, item))
  rows.sort(key=lambda item: str(item[1].get("submittedAt") or ""), reverse=True)
  return rows


def product_template_id(product_id: Any) -> str:
  text = str(product_id or "").strip()
  return text.removeprefix("cup-") or "10395"


def supply_chain_craft_options_for_template(template_id: str) -> list[dict[str, str]]:
  if template_id in SUPPLY_CHAIN_UV_PRINT_CRAFT_TEMPLATE_IDS:
    return [
      {"firstCraft": "17", "firstCraftName": "360度UV打印", "secondCraft": "2", "secondCraftName": "光油"},
      {"firstCraft": "17", "firstCraftName": "360度UV打印", "secondCraft": "1", "secondCraftName": "哑光"},
    ]
  if template_id in SUPPLY_CHAIN_HEAT_TRANSFER_CRAFT_TEMPLATE_IDS:
    return [
      {"firstCraft": "21", "firstCraftName": "热转印", "secondCraft": "1", "secondCraftName": "热转印"},
    ]
  return []


def resolve_supply_chain_craft(template_id: str, design_config: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
  options = supply_chain_craft_options_for_template(template_id)
  requested_first = optional_text(payload.get("firstCraft")) or optional_text(design_config.get("firstCraft"))
  requested_second = optional_text(payload.get("secondCraft")) or optional_text(design_config.get("secondCraft"))
  has_numeric_request = bool(
    (requested_first and requested_first.isdigit()) or (requested_second and requested_second.isdigit())
  )
  if has_numeric_request:
    if requested_second == SUPPLY_CHAIN_DISABLED_CRAFT_OPTIONS["5d"]["secondCraft"]:
      raise HumcustomError(
        422,
        "CLIENT_SUPPLY_CHAIN_CRAFT_DISABLED",
        "5D 打印暂未开放，请选择光油或哑光后再提交生产。",
      )
    for option in options:
      first_matches = not requested_first or requested_first == option["firstCraft"]
      second_matches = not requested_second or requested_second == option["secondCraft"]
      if first_matches and second_matches:
        return option
    raise HumcustomError(
      422,
      "CLIENT_SUPPLY_CHAIN_CRAFT_UNSUPPORTED",
      "当前杯型不支持所选工艺，请重新选择后再提交生产。",
    )
  if options:
    return options[0]
  raise HumcustomError(
    422,
    "CLIENT_SUPPLY_CHAIN_CRAFT_CONFIG_REQUIRED",
    "当前杯型缺少蜂鸟工艺编码，不能直接提交生产。请先在产品数据中补齐 firstCraft/secondCraft。",
  )


def order_quantity_int(order: dict[str, Any]) -> int:
  quantity = order.get("quantity")
  if isinstance(quantity, int):
    return max(1, quantity)
  match = re.search(r"\d+", str(quantity or ""))
  return max(1, int(match.group(0))) if match else 1


def supply_chain_plat_order_id(order: dict[str, Any]) -> str | None:
  metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
  supply_chain = metadata.get("supplyChain") if isinstance(metadata.get("supplyChain"), dict) else {}
  for key in ("platOrderId", "platformOrderId"):
    value = optional_text(supply_chain.get(key))
    if value:
      return value
  if order.get("supplierOrderId") or metadata.get("supplierSync") in {"submitted", "synced"}:
    return str(order.get("id") or "")
  return None


def order_is_paid(order: dict[str, Any]) -> bool:
  metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
  payment = metadata.get("payment") if isinstance(metadata.get("payment"), dict) else {}
  return payment.get("status") == "paid"


def map_supply_chain_status(status_name: str | None, current_status: str) -> str:
  text = (status_name or "").strip()
  if not text:
    return current_status
  if any(keyword in text for keyword in ("取消", "关闭", "作废", "失败")):
    return "已取消"
  if any(keyword in text for keyword in ("完成", "签收", "已收货")):
    return "已完成"
  if any(keyword in text for keyword in ("发货", "已发出", "运输", "揽收")):
    return "已发出"
  if any(keyword in text for keyword in ("生产", "制作", "待发", "审核", "处理中", "已下单")):
    return "制作中"
  return current_status if current_status not in {"待确认"} else "制作中"


def find_supply_chain_image_url(user_id: str, order: dict[str, Any]) -> str | None:
  metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
  for key in ("sourceAssetUrl", "previewAssetUrl"):
    value = metadata.get(key)
    if is_public_http_url(value) and "127.0.0.1" not in str(value) and "localhost" not in str(value):
      return str(value)
  for key in ("sourceAssetId", "previewAssetId", "assetId"):
    asset_id = optional_text(metadata.get(key))
    asset = find_asset(user_id, asset_id) if asset_id else None
    value = asset.get("url") if asset else None
    if is_public_http_url(value) and "127.0.0.1" not in str(value) and "localhost" not in str(value):
      return str(value)
  value = order.get("image")
  if is_public_http_url(value) and "127.0.0.1" not in str(value) and "localhost" not in str(value):
    return str(value)
  return None


def build_supply_chain_goods(user_id: str, order: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
  metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
  design_config = metadata.get("designConfig") if isinstance(metadata.get("designConfig"), dict) else {}
  if design_config.get("textureMode") == "wrap":
    source_asset_id = optional_text(metadata.get("sourceAssetId"))
    source_asset = find_asset(user_id, source_asset_id) if source_asset_id else None
    source_metadata = source_asset.get("metadata") if isinstance((source_asset or {}).get("metadata"), dict) else {}
    if source_metadata.get("productionValidation") != "verified" or not source_metadata.get("seamlessVerified"):
      raise HumcustomError(
        422,
        "CLIENT_PRODUCTION_ARTWORK_NOT_VERIFIED",
        "AI 连续图尚未完成生产边缘校验，不能提交蜂鸟。",
      )
  provided = payload.get("goodsList")
  if isinstance(provided, list) and provided:
    return [clean_dict(item) for item in provided if isinstance(item, dict)]

  template_id = product_template_id(metadata.get("productId"))
  product_config = dict(SUPPLY_CHAIN_PRODUCT_OVERRIDES.get(template_id) or {})
  configured_sizes = product_config.get("sizes") if isinstance(product_config.get("sizes"), dict) else {}
  requested_size_code = optional_text(design_config.get("sizeLabel")) or optional_text(design_config.get("sizeCode"))
  size_code = requested_size_code or optional_text(product_config.get("sizeCode")) or "OneSize"
  size_config = configured_sizes.get(size_code) if isinstance(configured_sizes.get(size_code), dict) else {}
  if not size_config and configured_sizes:
    default_size_code = optional_text(product_config.get("sizeCode")) or next(iter(configured_sizes.keys()))
    size_code = default_size_code
    size_config = configured_sizes.get(size_code) if isinstance(configured_sizes.get(size_code), dict) else {}
  color_codes = size_config.get("colorCodes") if isinstance(size_config.get("colorCodes"), list) else product_config.get("colorCodes")
  color_codes = [str(code).strip() for code in color_codes] if isinstance(color_codes, list) else []
  requested_color_code = optional_text(design_config.get("baseColorCode")) or optional_text(design_config.get("colorCode"))
  color_code = requested_color_code if requested_color_code and (not color_codes or requested_color_code in color_codes) else None
  color_code = color_code or optional_text(size_config.get("colorCode")) or optional_text(product_config.get("colorCode"))
  if color_codes and (not color_code or color_code not in color_codes):
    color_code = color_codes[0]
  surface_name = optional_text(design_config.get("surfaceName")) or "front"
  image_url = find_supply_chain_image_url(user_id, order)
  if not image_url:
    raise HumcustomError(
      422,
      "CLIENT_SUPPLY_CHAIN_IMAGE_PUBLIC_URL_REQUIRED",
      "提交蜂鸟前需要一张公网可访问的生产图。请先用中台生成/上传到 OSS 后再提交生产。",
    )
  craft_config = resolve_supply_chain_craft(template_id, design_config, payload)
  item = clean_dict({
    "templateNo": product_config.get("templateNo") or template_id,
    "platformSku": product_config.get("platformSku") or template_id,
    "firstCraft": craft_config.get("firstCraft"),
    "secondCraft": craft_config.get("secondCraft"),
    "num": order_quantity_int(order),
    "platItemId": f"{order.get('id')}-1",
    "sizeCode": size_code,
    "colorCode": color_code or "default",
    "imageList": [{"imageUrl": image_url, "surfaceName": surface_name, "viewId": design_config.get("surfaceViewId")}],
  })
  required = ("templateNo", "firstCraft", "secondCraft", "num", "platItemId", "sizeCode", "colorCode", "imageList")
  if not all(item.get(key) not in (None, "", [], {}) for key in required):
    raise HumcustomError(422, "CLIENT_ORDER_SUPPLY_CHAIN_PAYLOAD_INVALID", "缺少可提交蜂鸟的商品明细。")
  return [item]


def state_for_bootstrap(user_id: str) -> dict[str, Any]:
  if user_id in {"guest", "anonymous", "public"}:
    return {
      "userId": user_id,
      "assets": [],
      "processTasks": [],
      "designAgentSessions": [],
      "orders": [],
      "wallet": {
        "userId": user_id,
        "aiCredits": 0,
        "productCouponCount": 0,
        "shareBalance": 0,
        "latestWalletEvent": None,
      },
      "inspirationWorks": [],
      "publishApplications": [],
      "complaints": [],
    }
  assets = ensure_bucket("assets", user_id)
  changed = False
  if user_id == "demo-user":
    default_assets = {str(asset.get("id")): asset for asset in default_state()["assets"]["demo-user"]}
    existing_ids = {str(asset.get("id")) for asset in assets}
    for asset in assets:
      default_asset = default_assets.get(str(asset.get("id")))
      if not default_asset:
        continue
      for key in ("licenseMode", "licenseSource", "licensePoints", "author", "usedInProducts"):
        if key in default_asset:
          if asset.get(key) != default_asset[key]:
            asset[key] = default_asset[key]
            changed = True
    for asset_id in ("asset-7", "asset-8"):
      if asset_id not in existing_ids and asset_id in default_assets:
        assets.append(dict(default_assets[asset_id]))
        changed = True
  for asset in assets:
    asset.setdefault("licenseMode", "private")
    asset.setdefault("licenseSource", "product_snapshot" if asset.get("type") == "product_preview" else "created")
    asset.setdefault("usedInProducts", 1 if asset.get("type") == "product_preview" else 0)
  if backfill_asset_dimensions(assets):
    changed = True
  if normalize_local_demo_urls(assets):
    changed = True
  tasks = ensure_bucket("tasks", user_id)
  if normalize_local_demo_urls(tasks):
    changed = True
  if normalize_process_task_status_copy(tasks):
    changed = True
  if expire_stale_process_tasks(tasks):
    changed = True
  if reset_stale_dispatching_process_items(tasks):
    changed = True
  if normalize_process_task_queue_summary(tasks):
    changed = True
  if changed:
    save_state(STATE)
  orders = ensure_bucket("orders", user_id)
  publish = ensure_bucket("publishApplications", user_id)
  complaints = ensure_bucket("complaints", user_id)
  if normalize_local_demo_urls(orders) or normalize_local_demo_urls(publish) or normalize_local_demo_urls(complaints):
    save_state(STATE)
  inspiration = [
    {
      "id": "work-1",
      "title": "复古花卉杯身",
      "kind": "产品作品",
      "image": public_demo("/demo/market/product-mug-coral-navy.png"),
      "author": "designer_liu",
      "tags": ["杯子", "花卉", "已生成产品"],
      "tries": 128,
      "favorites": 342,
      "earnings": "抵扣 ¥186.40",
      "trend": "本周 38 人试做",
      "licenseMode": "paid_points",
      "pricePoints": 39,
      "rightsLabel": "同款授权 39 积分",
      "complaintCount": 0,
      "sourceAssetId": "asset-1",
      "productId": "cup-10395",
    },
    {
      "id": "work-2",
      "title": "蓝绿抽象花纹",
      "kind": "图片作品",
      "image": public_demo("/demo/market/pattern-garden.webp"),
      "author": "pattern_lab",
      "tags": ["花纹", "可裂变", "图片灵感"],
      "tries": 67,
      "favorites": 204,
      "earnings": "抵扣 ¥72.30",
      "trend": "适合二次裂变",
      "licenseMode": "paid_points",
      "pricePoints": 24,
      "rightsLabel": "授权 24 积分",
      "complaintCount": 1,
      "sourceAssetId": "asset-2",
      "productId": None,
    },
    {
      "id": "work-3",
      "title": "深色植物杯套",
      "kind": "产品作品",
      "image": public_demo("/demo/market/product-can-cooler.png"),
      "author": "outdoor_studio",
      "tags": ["杯套", "礼品", "产品灵感"],
      "tries": 92,
      "favorites": 188,
      "earnings": "抵扣 ¥94.10",
      "trend": "节日礼品方向",
      "licenseMode": "free_reuse",
      "pricePoints": 0,
      "rightsLabel": "免费同款",
      "complaintCount": 0,
      "sourceAssetId": "asset-4",
      "productId": "cup-10245",
    },
    {
      "id": "work-4",
      "title": "水彩花束透明底",
      "kind": "图片作品",
      "image": public_demo("/demo/market/pattern-bloom.webp"),
      "author": "flower_maker",
      "tags": ["透明底", "花卉", "可做产品"],
      "tries": 43,
      "favorites": 151,
      "earnings": "抵扣 ¥38.60",
      "trend": "新图上升中",
      "licenseMode": "free_reuse",
      "pricePoints": 0,
      "rightsLabel": "免费复用",
      "complaintCount": 0,
      "sourceAssetId": "asset-3",
      "productId": None,
    },
  ]
  return {
    "userId": user_id,
    "assets": assets,
    "processTasks": tasks,
    "designAgentSessions": design_agent_sessions_for_bootstrap(user_id),
    "orders": orders,
    "wallet": (lambda wallet: (refresh_wallet_coupon_count(wallet), wallet)[1])(ensure_wallet(user_id)),
    "inspirationWorks": inspiration,
    "publishApplications": publish,
    "complaints": complaints,
  }


def proxy_midplatform_request(
  method: str,
  path: str,
  payload: dict[str, Any] | None = None,
  timeout: float = 20.0,
) -> dict[str, Any] | None:
  if not MIDPLATFORM_BASE:
    return None
  normalized_method = method.upper()
  data = json.dumps(payload).encode("utf-8") if payload is not None else None
  headers = {"Content-Type": "application/json"} if payload is not None else {}
  if MIDPLATFORM_SERVICE_TOKEN:
    headers["Authorization"] = f"Bearer {MIDPLATFORM_SERVICE_TOKEN}"
  request = urllib.request.Request(
    f"{MIDPLATFORM_BASE}{path}",
    data=data,
    headers=headers,
    method=normalized_method,
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      return json.loads(response.read().decode("utf-8") or "{}")
  except urllib.error.HTTPError as error:
    try:
      return json.loads(error.read().decode("utf-8") or "{}")
    except Exception:
      return {"errorCode": f"HTTP_{error.code}", "message": str(error), "status": "failed"}
  except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
    return None


def proxy_midplatform(path: str, payload: dict[str, Any], timeout: float = 20.0) -> dict[str, Any] | None:
  return proxy_midplatform_request("POST", path, payload, timeout)


def get_midplatform_ability_task(task_id: str, timeout: float = 15.0) -> dict[str, Any] | None:
  safe_task_id = str(task_id or "").strip()
  if not safe_task_id:
    return None
  return proxy_midplatform_request(
    "GET",
    f"/api/ability-tasks/{quote(safe_task_id, safe='')}",
    timeout=timeout,
  )


class HumcustomError(Exception):
  def __init__(self, status: int, code: str, message: str) -> None:
    self.status = status
    self.code = code
    self.message = message
    super().__init__(message)


def humcustom_request(
  method: str,
  path: str,
  *,
  params: dict[str, Any] | None = None,
  payload: dict[str, Any] | None = None,
  headers: dict[str, str] | None = None,
  failure_code: str,
  failure_message: str,
) -> dict[str, Any]:
  query = f"?{urlencode(params)}" if params else ""
  url = f"{HUMCUSTOM_BASE}{path}{query}"
  data = json.dumps(payload).encode("utf-8") if payload is not None else None
  request_headers = {"Content-Type": "application/json", **(headers or {})}
  request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
  try:
    with urllib.request.urlopen(request, timeout=HUMCUSTOM_TIMEOUT_SECONDS, context=HUMCUSTOM_SSL_CONTEXT) as response:
      response_payload = json.loads(response.read().decode("utf-8") or "{}")
  except urllib.error.HTTPError as exc:
    raise HumcustomError(502, failure_code, f"{failure_message}HTTP {exc.code}。") from exc
  except urllib.error.URLError as exc:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, ssl.SSLCertVerificationError):
      raise HumcustomError(502, failure_code, f"{failure_message}本机 Python 证书链校验失败，请检查 certifi/系统证书。") from exc
    raise HumcustomError(504, failure_code, f"{failure_message}请求超时或网络不可达。") from exc
  except TimeoutError as exc:
    raise HumcustomError(504, failure_code, f"{failure_message}请求超时或网络不可达。") from exc
  except json.JSONDecodeError as exc:
    raise HumcustomError(502, failure_code, f"{failure_message}响应不是 JSON。") from exc
  if not isinstance(response_payload, dict):
    raise HumcustomError(502, failure_code, f"{failure_message}响应格式异常。")
  code = response_payload.get("code")
  success = response_payload.get("success")
  if code not in (0, "0", None) or success is False:
    message = optional_text(response_payload.get("message")) or failure_message
    if str(code) == "401":
      raise HumcustomError(502, "CLIENT_SUPPLY_CHAIN_AUTH_INVALID", f"供应链授权失效：{message}")
    raise HumcustomError(502, failure_code, message)
  return response_payload


def humcustom_get_access_token() -> str:
  if HUMCUSTOM_ACCESS_TOKEN:
    return HUMCUSTOM_ACCESS_TOKEN
  now_ms = int(time.time() * 1000)
  cached_token = optional_text(HUMCUSTOM_TOKEN_CACHE.get("accessToken"))
  cached_expires = optional_int(HUMCUSTOM_TOKEN_CACHE.get("expiresTime"))
  if cached_token and cached_expires and cached_expires - now_ms > 60_000:
    return cached_token
  if not HUMCUSTOM_APP_KEY or not HUMCUSTOM_APP_SECRET:
    raise HumcustomError(503, "CLIENT_SUPPLY_CHAIN_NOT_CONFIGURED", "供应链未配置 appKey/appSecret，无法提交或同步订单。")
  response = humcustom_request(
    "GET",
    "/open/api/v1/oauth/token",
    params={"appKey": HUMCUSTOM_APP_KEY, "appSecret": HUMCUSTOM_APP_SECRET},
    failure_code="CLIENT_SUPPLY_CHAIN_TOKEN_FAILED",
    failure_message="供应链授权失败。",
  )
  data = response.get("data") if isinstance(response.get("data"), dict) else {}
  access_token = optional_text(data.get("accessToken"))
  if not access_token:
    raise HumcustomError(502, "CLIENT_SUPPLY_CHAIN_TOKEN_FAILED", "供应链授权未返回 accessToken。")
  HUMCUSTOM_TOKEN_CACHE["accessToken"] = access_token
  HUMCUSTOM_TOKEN_CACHE["expiresTime"] = optional_int(data.get("expiresTime"))
  return access_token


def humcustom_place_order(payload: dict[str, Any]) -> dict[str, Any]:
  return humcustom_request(
    "POST",
    "/open/api/v1/order/placeOrder",
    payload=payload,
    headers={"accessToken": humcustom_get_access_token()},
    failure_code="CLIENT_SUPPLY_CHAIN_PLACE_ORDER_FAILED",
    failure_message="供应链下单失败。",
  )


def humcustom_query_order(plat_order_id: str) -> dict[str, Any]:
  return humcustom_request(
    "GET",
    "/open/api/v1/order/queryOrder",
    params={"platOrderId": plat_order_id},
    headers={"accessToken": humcustom_get_access_token()},
    failure_code="CLIENT_SUPPLY_CHAIN_QUERY_FAILED",
    failure_message="供应链订单查询失败。",
  )


def submit_order_to_supply_chain(
  user_id: str,
  order: dict[str, Any],
  payload: dict[str, Any] | None = None,
  *,
  actor: str = "ops:manual-confirmation",
) -> dict[str, Any]:
  request_body = payload or {}
  existing_plat_order_id = supply_chain_plat_order_id(order)
  if existing_plat_order_id:
    return order
  metadata = order.setdefault("metadata", {})
  shipping = normalize_shipping_address(request_body.get("shippingAddress") or metadata.get("shippingAddress"))
  missing = [key for key, label in {
    "country": "国家",
    "state": "省/州",
    "city": "城市",
    "district": "区/县",
    "postalCode": "邮编",
    "address": "详细地址",
    "phoneNumber": "联系电话",
    "recipientName": "收件人",
  }.items() if not shipping.get(key)]
  if missing:
    raise HumcustomError(422, "CLIENT_ORDER_SHIPPING_REQUIRED", f"提交供应链前请补齐：{'、'.join(missing)}。")

  goods_list = build_supply_chain_goods(user_id, order, request_body)
  plat_order_id = optional_text(request_body.get("platOrderId")) or str(order.get("id"))
  org_order_id = optional_text(request_body.get("orgOrderId")) or plat_order_id
  request_payload = clean_dict({
    "apiVersion": optional_text(request_body.get("apiVersion")) or "1",
    "platOrderId": plat_order_id,
    "orgOrderId": org_order_id,
    **supply_chain_shipping_fields(shipping),
    "waybillType": request_body.get("waybillType") or "0",
    "selfSuppliedWaybill": request_body.get("selfSuppliedWaybill"),
    "selfSuppliedPdfUrl": request_body.get("selfSuppliedPdfUrl"),
    "selfSuppliedCarrier": request_body.get("selfSuppliedCarrier"),
    "goodsList": goods_list,
  })
  response = humcustom_place_order(request_payload)
  data = response.get("data") if isinstance(response.get("data"), dict) else {}
  express_result = data.get("expressResult") if isinstance(data.get("expressResult"), dict) else {}
  supplier_order_id = optional_text(express_result.get("orderId") or data.get("orderId"))
  platform_order_id = optional_text(express_result.get("platformOrderId") or data.get("platformOrderId"))
  submitted_at = now_label()
  metadata["supplierSync"] = "submitted"
  metadata["shippingAddress"] = shipping
  metadata["supplyChain"] = {
    "provider": "humcustom",
    "platOrderId": plat_order_id,
    "orgOrderId": org_order_id,
    "orderId": supplier_order_id,
    "platformOrderId": platform_order_id,
    "submittedAt": submitted_at,
    "submittedBy": actor,
    "placeOrderPayloadSummary": {
      **redact_shipping(supply_chain_shipping_fields(shipping)),
      "goodsCount": len(goods_list),
      "waybillType": request_payload.get("waybillType"),
    },
    "raw": response,
  }
  order["metadata"] = metadata
  order["supplierOrderId"] = supplier_order_id or platform_order_id
  order["status"] = "制作中"
  order["eta"] = "已推送蜂鸟，等待供应链确认"
  order["shippingSummary"] = shipping_summary(shipping, order.get("shippingSummary"))
  order["supplierStatusName"] = "已提交"
  order["supplierSyncedAt"] = submitted_at
  materialize_supply_chain_render_assets(user_id, order, response)
  save_state(STATE)
  return order


def midplatform_unavailable_payload(path: str) -> dict[str, Any]:
  return {
    "errorCode": "MIDPLATFORM_UNAVAILABLE",
    "message": "中台能力服务暂时没有连接成功，当前不会返回本地假结果。",
    "path": path,
    "midPlatformBase": MIDPLATFORM_BASE or None,
  }


IMAGE_URL_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif")
IMAGE_URL_KEYS = {
  "imageurl",
  "imageurls",
  "image_url",
  "image_urls",
  "ossurl",
  "storedurl",
  "resulturl",
  "resulturls",
  "thumbnailurl",
  "sourceurl",
  "url",
}
IMAGE_CONTAINER_KEYS = {"images", "assets", "resultpayload", "result", "data", "payload", "raw"}
NON_RESULT_URL_KEYS = {"baseurl", "debugurl", "callbackurl", "endpoint", "publicdomain", "apiurl"}


def is_probable_image_url(value: Any) -> bool:
  if not isinstance(value, str):
    return False
  url = value.strip()
  if not (url.startswith("http://") or url.startswith("https://")):
    return False
  parsed = urlparse(url)
  if not parsed.netloc:
    return False
  path = unquote(parsed.path or "").lower()
  if path.endswith(IMAGE_URL_EXTENSIONS):
    return True
  query = parse_qs(parsed.query or "")
  filename = unquote(str((query.get("filename") or [""])[0])).lower()
  if filename.endswith(IMAGE_URL_EXTENSIONS):
    return True
  content_type = unquote(str((query.get("response-content-type") or [""])[0])).lower()
  return content_type.startswith("image/")


def collect_urls(value: Any, target: list[str] | None = None) -> list[str]:
  if target is None:
    target = []
  if not value:
    return target
  if isinstance(value, str):
    if is_probable_image_url(value):
      target.append(value.strip())
    return target
  if isinstance(value, list):
    for item in value:
      collect_urls(item, target)
    return target
  if isinstance(value, dict):
    for key, item in value.items():
      normalized_key = str(key or "").replace("-", "").replace("_", "").lower()
      if normalized_key in NON_RESULT_URL_KEYS:
        continue
      if normalized_key in IMAGE_URL_KEYS or normalized_key in IMAGE_CONTAINER_KEYS:
        collect_urls(item, target)
  return list(dict.fromkeys(target))


def collect_supplier_render_urls(value: Any, target: list[str] | None = None, parent_key: str = "") -> list[str]:
  if target is None:
    target = []
  normalized_parent = re.sub(r"[^a-z]", "", parent_key.lower())
  render_context = any(token in normalized_parent for token in ("effect", "render", "preview", "mockup"))
  if isinstance(value, str):
    if render_context and is_public_http_url(value):
      target.append(value.strip())
    return list(dict.fromkeys(target))
  if isinstance(value, list):
    for item in value:
      collect_supplier_render_urls(item, target, parent_key)
    return list(dict.fromkeys(target))
  if isinstance(value, dict):
    for key, item in value.items():
      collect_supplier_render_urls(item, target, str(key))
  return list(dict.fromkeys(target))


def materialize_supply_chain_render_assets(user_id: str, order: dict[str, Any], response: dict[str, Any]) -> list[dict[str, Any]]:
  metadata = order.setdefault("metadata", {})
  supply_chain = metadata.setdefault("supplyChain", {})
  source_url = find_supply_chain_image_url(user_id, order)
  candidates = [url for url in collect_supplier_render_urls(response) if url != source_url]
  existing_assets = ensure_bucket("assets", user_id)
  existing_sources = {
    str((asset.get("metadata") or {}).get("supplierSourceUrl") or "")
    for asset in existing_assets
    if isinstance(asset, dict) and isinstance(asset.get("metadata"), dict)
  }
  created: list[dict[str, Any]] = []
  render_asset_ids = [str(item) for item in (supply_chain.get("renderAssetIds") or []) if str(item or "").strip()]
  render_urls = [str(item) for item in (supply_chain.get("renderImageUrls") or []) if str(item or "").strip()]
  for index, url in enumerate(candidates):
    if url in existing_sources:
      continue
    asset = {
      "id": "supplier-render-" + secrets.token_hex(6),
      "type": "supplier_render",
      "title": f"蜂鸟效果图 · {order.get('product') or order.get('id')}",
      "url": url,
      "thumbnailUrl": url,
      "source": "蜂鸟渲染回传",
      "createdAt": now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "supplier_render",
      "usedInProducts": 1,
      "metadata": {
        "orderId": order.get("id"),
        "supplier": "humcustom",
        "supplierSourceUrl": url,
        "renderIndex": index,
      },
    }
    prepare_asset_for_storage(user_id, asset, reason="humcustom-render")
    existing_assets.insert(0, asset)
    created.append(asset)
    render_asset_ids.append(str(asset["id"]))
    render_urls.append(str(asset.get("url") or url))
    existing_sources.add(url)
  if created:
    supply_chain["renderAssetIds"] = list(dict.fromkeys(render_asset_ids))
    supply_chain["renderImageUrls"] = list(dict.fromkeys(render_urls))
    supply_chain["renderSyncedAt"] = now_label()
    # A supplier render is the only order image that may claim to show the finished product.
    order["image"] = str(created[0].get("url") or candidates[0])
    order["imageSource"] = "supplier_render"
  elif render_urls:
    # A previous sync may already have persisted the supplier render. Keep the
    # order card aligned with it instead of falling back to the catalog mockup.
    order["image"] = render_urls[0]
    order["imageSource"] = "supplier_render"
  return created


def probe_image_dimensions(url: Any) -> dict[str, int]:
  if not is_probable_image_url(url):
    return {}
  try:
    from PIL import Image  # type: ignore
  except Exception:
    return {}

  request = urllib.request.Request(
    str(url).strip(),
    headers={"User-Agent": "PODI-BusinessAPI/asset-dimension-probe"},
  )
  try:
    parsed = urlparse(str(url))
    context = HUMCUSTOM_SSL_CONTEXT if parsed.scheme == "https" else None
    open_kwargs = {"timeout": 12}
    if context is not None:
      open_kwargs["context"] = context
    with urllib.request.urlopen(request, **open_kwargs) as response:  # type: ignore[arg-type]
      data = response.read(ASSET_DIMENSION_PROBE_MAX_BYTES)
    with Image.open(BytesIO(data)) as image:
      width, height = image.size
      dpi_value = None
      dpi = image.info.get("dpi")
      if isinstance(dpi, tuple) and dpi:
        dpi_value = optional_int(dpi[0])
      elif dpi is not None:
        dpi_value = optional_int(dpi)
      result = {"width": int(width), "height": int(height)}
      if dpi_value:
        result["dpi"] = int(dpi_value)
      return result
  except Exception:
    return {}


def enrich_asset_dimensions(asset: dict[str, Any]) -> bool:
  width = optional_int(asset.get("width"))
  height = optional_int(asset.get("height"))
  if width and height:
    if asset.get("width") != width:
      asset["width"] = width
    if asset.get("height") != height:
      asset["height"] = height
    return False

  source_url = asset.get("url") or asset.get("thumbnailUrl")
  metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
  dimensions = probe_image_dimensions(source_url)
  if not dimensions:
    if source_url and not metadata.get("dimensionProbeFailedAt"):
      metadata["dimensionProbeFailedAt"] = now_label()
      asset["metadata"] = metadata
      return True
    return False

  changed = False
  for key in ("width", "height", "dpi"):
    value = optional_int(dimensions.get(key))
    if value and asset.get(key) != value:
      asset[key] = value
      changed = True
  metadata.pop("dimensionProbeFailedAt", None)
  metadata["dimensionSource"] = "server_probe"
  asset["metadata"] = metadata
  return changed


def backfill_asset_dimensions(assets: list[dict[str, Any]], limit: int = ASSET_DIMENSION_BOOTSTRAP_LIMIT) -> bool:
  changed = False
  inspected = 0
  for asset in assets:
    if inspected >= limit:
      break
    if not isinstance(asset, dict):
      continue
    if optional_int(asset.get("width")) and optional_int(asset.get("height")):
      continue
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    if metadata.get("dimensionProbeFailedAt"):
      continue
    inspected += 1
    if enrich_asset_dimensions(asset):
      changed = True
  return changed


def read_run_id(payload: dict[str, Any] | None) -> str | None:
  if not isinstance(payload, dict):
    return None
  for key in ("runId", "id", "taskId"):
    value = payload.get(key)
    if isinstance(value, str) and value:
      return value
  for key in ("run", "data", "result", "payload"):
    nested = payload.get(key)
    if isinstance(nested, dict):
      nested_run_id = read_run_id(nested)
      if nested_run_id:
        return nested_run_id
  return None


def read_payload_status(payload: dict[str, Any] | None) -> str:
  if not isinstance(payload, dict):
    return ""
  for key in ("status", "taskStatus", "state"):
    value = payload.get(key)
    if isinstance(value, str):
      return value.lower()
  for key in ("run", "data", "result", "payload"):
    nested = payload.get(key)
    if isinstance(nested, dict):
      nested_status = read_payload_status(nested)
      if nested_status:
        return nested_status
  return ""


def read_payload_error(payload: dict[str, Any] | None) -> str:
  if not isinstance(payload, dict):
    return ""
  top_code = payload.get("errorCode") or payload.get("code")
  top_message = payload.get("message") or payload.get("error")
  if top_code and top_message and payload.get("success") is False:
    return f"{top_code}: {top_message}"
  if top_code and payload.get("success") is False:
    return str(top_code)
  for key in ("detail", "error", "errorMessage", "message", "errorCode", "code"):
    value = payload.get(key)
    if value:
      if isinstance(value, dict):
        nested_code = value.get("errorCode") or value.get("code")
        nested_message = value.get("message") or value.get("error") or value.get("detail")
        if nested_code and nested_message:
          return f"{nested_code}: {nested_message}"
        if nested_code:
          return str(nested_code)
        nested_error = read_payload_error(value)
        if nested_error:
          return nested_error
      if isinstance(value, str):
        text_value = value.strip()
        if text_value.startswith("{") and text_value.endswith("}"):
          try:
            parsed_value = ast.literal_eval(text_value)
          except (SyntaxError, ValueError):
            parsed_value = None
          if isinstance(parsed_value, dict):
            parsed_error = read_payload_error(parsed_value)
            if parsed_error:
              return parsed_error
      return str(value)
  for key in ("run", "data", "result", "payload"):
    nested = payload.get(key)
    if isinstance(nested, dict):
      nested_error = read_payload_error(nested)
      if nested_error:
        return nested_error
  return ""


def friendly_agent_error(message: str) -> str:
  text = str(message or "").strip()
  upper = text.upper()
  if not text:
    return "图片处理失败，请稍后重试或换一种设计路线。"
  if "PRODUCT_DESIGN_PRODUCT_TYPE_INVALID" in upper:
    return "当前商品设计路线暂时没有匹配到可用的生成参数，我已保留方案，请稍后重试或先改用提取花纹、裂变候选路线。"
  if "PRODUCT_DESIGN_SCENE_INVALID" in upper:
    return "当前设计场景参数暂时不被图片服务支持，我已保留方案，请稍后重试。"
  if "PRODUCT_DESIGN_BRIEF_REQUIRED" in upper:
    return "这次生成缺少明确的设计要求，请补充你想保留什么、避免什么，再重新确认。"
  if "BUSINESS_IMAGE_URL_REQUIRED" in upper:
    return "当前图片生成入口需要一张云端参考图；纯文字设计还要接入文生图通道，上传图片则需要先落到 OSS。方案已保留，可以换一张云端素材后继续。"
  if "VENDOR_API_KEY_MISSING" in upper:
    return "图片生成通道配置异常，未扣除本次积分。请稍后重试；系统会优先切换到可用的图片生成通道。"
  if "ABILITY_TASK_FAILED" in upper:
    return "图片生成任务没有完成，未扣除本次积分。请稍后重试；如果问题持续出现，我们会切换到备用图片生成通道。"
  if "PRODUCTION_CANVAS_" in upper:
    return "图片已生成，但生产文件校验没有完成。本次不会进入设计篮或扣除积分，方案已保留。当前通道恢复后可重试；备用通道接入后会自动参与切换。"
  if is_authorization_error(text):
    return "这次需要的图片生成通道还没有完全开通，我已保留设计方案；可以稍后重试，或先用已上传的素材继续生成。"
  if "RATE LIMIT" in upper or "TOO MANY" in upper or "429" in upper:
    return "图片服务当前请求过多，我已保留方案，请稍后重试。"
  if is_busy_error(text):
    return "图片处理服务正在排队，我已把任务保留在队列里。"
  return text if len(text) <= 120 else text[:117] + "..."


def is_busy_error(message: str) -> bool:
  text = message.upper()
  return any(token in text for token in ("Q1001", "Q1002", "COMFYUI_QUEUE_FULL", "EXECUTOR_BUSY", "QUEUE_FULL"))


def is_authorization_error(message: str) -> bool:
  text = str(message or "").upper()
  return any(token in text for token in ("AUTHORIZATION_REQUIRED", "INVALID_TOKEN", "FORBIDDEN", "PERMISSION_DENIED", "UNAUTHORIZED"))


def read_positive_int(value: Any, default: int = 1, maximum: int = 12) -> int:
  try:
    parsed = int(value)
  except (TypeError, ValueError):
    return default
  return max(1, min(maximum, parsed))


def read_process_candidate_count(task_type: str, body: dict[str, Any], params: dict[str, Any]) -> int:
  if task_type != "variation":
    return 1
  template = params.get("requestPayloadTemplate") if isinstance(params.get("requestPayloadTemplate"), dict) else {}
  for value in (
    params.get("candidateCount"),
    params.get("perImageOutputCount"),
    template.get("candidateCount"),
    template.get("outputCount"),
  ):
    if value is not None:
      return read_positive_int(value)
  # Top-level outputCount is kept as a fallback for old clients. New clients send
  # per-image candidate count inside params to avoid confusing it with total count.
  return read_positive_int(body.get("outputCount"))


def process_task_credit_cost(task_type: str, body: dict[str, Any], params: dict[str, Any], input_images: list[Any]) -> int:
  per_image_cost = PROCESS_TASK_CREDITS_BY_TYPE.get(task_type, 2)
  input_count = len([item for item in input_images if item])
  if input_count <= 0:
    input_count = max(1, optional_int(body.get("inputCount")) or 0)
  return max(0, per_image_cost * input_count)


def task_queue_items(task: dict[str, Any]) -> list[dict[str, Any]]:
  params = task.setdefault("params", {})
  if not isinstance(params, dict):
    params = {}
    task["params"] = params
  items = params.get("queueItems")
  if isinstance(items, list) and items:
    return items

  input_images = list(task.get("inputImages") or [])
  run_ids = list(params.get("businessRunIds") or [])
  candidate_count = read_process_candidate_count(str(task.get("type") or ""), {}, params)
  items = []
  for image_index, image_url in enumerate(input_images):
    for variant_index in range(candidate_count):
      index = image_index * candidate_count + variant_index
      run_id = run_ids[index] if index < len(run_ids) else None
      status = "running" if run_id else "queued"
      items.append({
        "index": index,
        "inputIndex": image_index,
        "variantIndex": variant_index,
        "variantCount": candidate_count,
        "inputImage": image_url,
        "status": status,
        "runId": run_id,
        "attempts": 1 if run_id else 0,
        "resultImages": [],
        "errorMessage": None,
        "submittedAt": task.get("createdAt") if run_id else None,
        "completedAt": None,
      })
  params["queueItems"] = items
  params["candidateCount"] = candidate_count
  params["expectedOutputCount"] = len(items)
  params["businessRunIds"] = [item.get("runId") for item in items if item.get("runId")]
  return items


def materialize_task_assets(user_id: str, task: dict[str, Any]) -> None:
  result_images = [url for url in (task.get("resultImages") or []) if is_probable_image_url(url)]
  task["resultImages"] = result_images
  task["resultCount"] = len(result_images)
  if task.get("status") != "completed" or not result_images:
    return
  asset_type = str(task.get("resultType") or "processed")
  output_asset_ids: list[str] = list(task.get("outputAssetIds") or [])
  existing_asset_ids = {str(asset.get("id")) for asset in ensure_bucket("assets", user_id)}
  for index, url in enumerate(result_images):
    asset_id = output_asset_ids[index] if index < len(output_asset_ids) else f"asset-{task.get('id')}-{index + 1}"
    if asset_id not in output_asset_ids:
      output_asset_ids.append(asset_id)
    if asset_id in existing_asset_ids:
      continue
    asset = {
      "id": asset_id,
      "type": asset_type,
      "title": f"{task.get('abilityTitle') or task.get('optionLabel') or '图片处理'}结果 {index + 1}",
      "url": url,
      "thumbnailUrl": url,
      "source": task.get("abilityTitle") or task.get("optionLabel") or "图片处理",
      "createdAt": task.get("completedAt") or now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "batchId": task.get("id"),
      "licenseMode": "private",
      "licenseSource": "created",
      "usedInProducts": 0,
    }
    prepare_asset_for_storage(user_id, asset, reason="process-result")
    enrich_asset_dimensions(asset)
    ensure_bucket("assets", user_id).insert(0, asset)
  task["outputAssetIds"] = output_asset_ids


class Handler(BaseHTTPRequestHandler):
  server_version = "PodiBusinessAPI/0.1"

  def log_message(self, fmt: str, *args: Any) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

  def _origin(self) -> str:
    return self.headers.get("Origin") or "*"

  def _headers(
    self,
    status: int = 200,
    content_type: str = "application/json",
    extra_headers: dict[str, str] | None = None,
  ) -> None:
    self.send_response(status)
    self.send_header("Access-Control-Allow-Origin", self._origin())
    self.send_header("Access-Control-Allow-Credentials", "true")
    self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-PODI-API-Key")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
    self.send_header("Content-Type", content_type)
    for name, value in (extra_headers or {}).items():
      self.send_header(name, value)
    self.end_headers()

  def _json(self, payload: dict[str, Any], status: int = 200) -> None:
    self._headers(status)
    self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

  def _read_json(self) -> dict[str, Any]:
    length = int(self.headers.get("Content-Length") or "0")
    if length <= 0:
      return {}
    raw = self.rfile.read(length)
    try:
      return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
      return {}

  def _auth_headers(self) -> dict[str, str]:
    return {key.lower(): value for key, value in self.headers.items()}

  def do_OPTIONS(self) -> None:  # noqa: N802
    self._headers(204)

  def do_GET(self) -> None:  # noqa: N802
    parsed = urlparse(self.path)
    path = parsed.path
    if path == "/health":
      active_vl_model = AGENT_PLANNER_MODEL if AGENT_VL_PROVIDER in {"volcengine-doubao-turbo", "doubao-turbo", "turbo"} else AGENT_VL_MODEL
      self._json({
        "status": "ok",
        "service": "podi-business-api",
        "role": "client-business-system",
        "midPlatformBase": MIDPLATFORM_BASE or None,
        "agentVl": {
          "provider": AGENT_VL_PROVIDER or "heuristic",
          "model": active_vl_model,
          "liteModel": AGENT_VL_MODEL,
          "plannerModel": AGENT_PLANNER_MODEL,
          "configured": bool(VOLCENGINE_ARK_API_KEY) if AGENT_VL_PROVIDER not in {"", "heuristic", "local"} else True,
        },
        "agentExecution": {
          "mode": agent_execution_mode_label(),
          "configured": agent_execution_mode_label() != "real" or bool(MIDPLATFORM_BASE),
          "controlPlane": "podi-business-api",
        },
      })
      return
    if path == "/api/auth/me":
      user = user_from_auth(self._auth_headers())
      if not user:
        status, body = json_error("INVALID_TOKEN", "登录状态已失效。", 401)
        self._json(body, status)
        return
      self._json(user)
      return
    if path == "/api/admin/client/orders":
      self._handle_admin_list_orders(parsed)
      return
    if path == "/api/admin/client/commerce-config":
      self._handle_admin_get_commerce_config()
      return
    if path == "/api/admin/client/product-pricing":
      self._handle_admin_list_product_pricing()
      return
    if path == "/api/admin/client/coupon-campaigns":
      self._handle_admin_list_coupon_campaigns()
      return
    if path == "/api/admin/client/publish-applications":
      self._handle_admin_list_publish_applications(parsed)
      return
    if path == "/api/admin/client/complaints":
      self._handle_admin_list_complaints(parsed)
      return
    if path == "/api/admin/client/users":
      self._handle_admin_list_users(parsed)
      return
    if path == "/api/admin/client/assets":
      self._handle_admin_list_assets(parsed)
      return
    if path == "/api/client/v1/bootstrap":
      query = parse_qs(parsed.query)
      user_id = (query.get("userId") or ["guest"])[0] or "guest"
      self._json(state_for_bootstrap(user_id))
      return
    if path == "/api/client/v1/commerce-config":
      self._json(commerce_config_snapshot())
      return
    if path == "/api/client/v1/product-pricing":
      self._json(public_product_pricing_snapshot())
      return
    if re.fullmatch(r"/api/client/v1/assets/[^/]+/preview", path):
      asset_id = unquote(path.split("/")[-2])
      self._handle_client_asset_preview(asset_id, parsed)
      return
    if re.fullmatch(r"/api/client/v1/product-design-agent/sessions/[^/]+", path):
      session_id = unquote(path.rsplit("/", 1)[-1])
      self._handle_get_design_agent_session(session_id, parsed)
      return
    if path.startswith("/media/uploads/"):
      self._serve_upload(path)
      return
    self._json({"errorCode": "NOT_FOUND", "message": "接口不存在。"}, 404)

  def do_PUT(self) -> None:  # noqa: N802
    parsed = urlparse(self.path)
    path = parsed.path
    body = self._read_json()
    if path == "/api/admin/client/commerce-config":
      self._handle_admin_update_commerce_config(body)
      return
    if re.fullmatch(r"/api/admin/client/product-pricing/[^/]+", path):
      product_id = unquote(path.rsplit("/", 1)[-1])
      self._handle_admin_update_product_pricing(product_id, body)
      return
    self._json({"errorCode": "NOT_FOUND", "message": "接口不存在。"}, 404)

  def do_POST(self) -> None:  # noqa: N802
    parsed = urlparse(self.path)
    path = parsed.path
    body = self._read_json()

    if path == "/api/auth/sms-code":
      phone = str(body.get("phone") or "").strip()
      scene = str(body.get("scene") or "login").strip()
      if not re.fullmatch(r"1\d{10}", phone):
        status, payload = json_error("PHONE_INVALID", "请输入正确的 11 位手机号。", 422)
        self._json(payload, status)
        return
      try:
        self._json(request_sms_code(phone, scene))
      except SmsError as exc:
        status, payload = json_error(exc.code, exc.message, exc.status)
        self._json(payload, status)
      return

    if path == "/api/auth/phone-login":
      phone = str(body.get("phone") or "").strip()
      code = str(body.get("code") or "").strip()
      if not re.fullmatch(r"1\d{10}", phone):
        status, payload = json_error("PHONE_INVALID", "请输入正确的 11 位手机号。", 422)
        self._json(payload, status)
        return
      try:
        verify_sms_code(phone, code)
      except SmsError as exc:
        status, payload = json_error(exc.code, exc.message, exc.status)
        self._json(payload, status)
        return
      self._json(create_session(phone, str(body.get("displayName") or "").strip() or None))
      return

    if path == "/api/auth/refresh":
      refresh = str(body.get("refreshToken") or "")
      for token, session in list(STATE.setdefault("sessions", {}).items()):
        if session.get("refreshToken") == refresh:
          user = STATE.setdefault("users", {}).get(session["userId"])
          if not user:
            break
          STATE["sessions"].pop(token, None)
          if user.get("role") == "admin":
            self._json(create_admin_session(str(user.get("username") or "admin")))
            return
          self._json(create_session(str(user.get("phone") or user.get("username") or ""), user.get("displayName")))
          return
      status, payload = json_error("INVALID_REFRESH_TOKEN", "登录状态已失效。", 401)
      self._json(payload, status)
      return

    if path == "/api/auth/logout":
      auth = self.headers.get("Authorization", "")
      if auth.lower().startswith("bearer "):
        STATE.setdefault("sessions", {}).pop(auth.split(" ", 1)[1].strip(), None)
        save_state(STATE)
      self._json({"ok": True})
      return

    if path == "/api/auth/login":
      username = str(body.get("username") or "").strip()
      password = str(body.get("password") or "").strip()
      if not PODI_OPS_ADMIN_USERNAME or not PODI_OPS_ADMIN_PASSWORD:
        status, payload = json_error("OPS_ADMIN_AUTH_NOT_CONFIGURED", "运营后台管理员尚未配置。", 503)
        self._json(payload, status)
        return
      if hmac.compare_digest(username, PODI_OPS_ADMIN_USERNAME) and hmac.compare_digest(password, PODI_OPS_ADMIN_PASSWORD):
        self._json(create_admin_session(PODI_OPS_ADMIN_USERNAME))
        return
      status, payload = json_error("OPS_ADMIN_LOGIN_INVALID", "账号或密码错误。", 401)
      self._json(payload, status)
      return

    if path == "/api/auth/register":
      status, payload = json_error("PHONE_LOGIN_ONLY", "当前主站只开放手机号验证码登录。", 400)
      self._json(payload, status)
      return

    if path == "/api/media/v1/upload-key":
      proxied = proxy_midplatform(path, body, timeout=8.0)
      if proxied is not None:
        self._json(proxied)
        return
      self._json({
        "uploadKey": "local-upload-" + secrets.token_urlsafe(12),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        "expiresIn": 900,
      })
      return

    if path == "/api/media/v1/sts":
      proxied = proxy_midplatform(path, body, timeout=8.0)
      if proxied is not None:
        self._json(proxied)
        return
      filename = Path(str(body.get("fileName") or "upload.png")).name
      safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-") or "upload.png"
      object_key = f"local/{int(time.time() * 1000)}-{secrets.token_hex(4)}-{safe_name}"
      self._json({
        "ossCredentials": {
          "accessKeyId": "",
          "accessKeySecret": "",
          "securityToken": None,
          "endpoint": "",
          "publicDomain": f"http://{self.headers.get('Host', '127.0.0.1:8240')}",
          "bucket": "local",
          "region": "local",
          "expiration": int(time.time()) + 900,
          "isTemporary": True,
          "rootPrefix": "local",
        },
        "objectKey": object_key,
        "host": f"http://{self.headers.get('Host', '127.0.0.1:8240')}",
      })
      return

    if path == "/api/media/v1/local-upload":
      self._handle_local_upload(body)
      return

    if path.startswith("/api/business/"):
      self._handle_business(path, body)
      return

    if path == "/api/client/v1/product-design-agent/sessions":
      self._handle_create_design_agent_session(body)
      return

    if path == "/api/client/v1/product-design-intakes":
      self._handle_create_product_design_intake(body)
      return

    if re.fullmatch(r"/api/client/v1/product-design-agent/sessions/[^/]+/messages", path):
      session_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_design_agent_message(session_id, body)
      return

    if re.fullmatch(r"/api/client/v1/product-design-agent/sessions/[^/]+/plans/[^/]+/confirm", path):
      parts = path.strip("/").split("/")
      session_id = unquote(parts[-4])
      plan_id = unquote(parts[-2])
      self._handle_confirm_design_agent_plan(session_id, plan_id, body)
      return

    if re.fullmatch(r"/api/client/v1/product-design-agent/sessions/[^/]+/steps/[^/]+/confirm", path):
      parts = path.strip("/").split("/")
      session_id = unquote(parts[-4])
      step_id = unquote(parts[-2])
      self._handle_confirm_design_agent_step(session_id, step_id, body)
      return

    if re.fullmatch(r"/api/client/v1/product-design-agent/sessions/[^/]+/apply-preview", path):
      session_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_apply_design_agent_preview(session_id, body)
      return

    if path == "/api/client/v1/assets":
      self._handle_create_asset(body)
      return
    if path == "/api/client/v1/production-artwork/seamless":
      self._handle_create_verified_seamless_artwork(body)
      return

    if path == "/api/client/v1/process-tasks":
      self._handle_create_process_task(body)
      return

    if path == "/api/client/v1/process-tasks/advance":
      self._handle_advance_process_task(body)
      return

    if path == "/api/client/v1/process-tasks/update":
      self._handle_update_process_task(body)
      return

    if path == "/api/client/v1/product-samples":
      self._handle_product_sample(body)
      return

    if path == "/api/client/v1/orders":
      self._handle_create_order(body)
      return

    if path == "/api/client/v1/coupons/redeem":
      self._handle_redeem_coupon_code(body)
      return

    if re.fullmatch(r"/api/client/v1/orders/[^/]+/pay", path):
      order_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_pay_order(order_id, body)
      return

    if path == "/api/client/v1/publish-applications":
      self._handle_publish_application(body)
      return

    if path == "/api/client/v1/complaints":
      self._handle_create_complaint(body)
      return

    if re.fullmatch(r"/api/admin/client/complaints/[^/]+/review", path):
      complaint_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_review_complaint(complaint_id, body)
      return

    if re.fullmatch(r"/api/admin/client/publish-applications/[^/]+/review", path):
      application_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_review_publish_application(application_id, body)
      return

    if re.fullmatch(r"/api/admin/client/orders/[^/]+/sync", path):
      order_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_sync_order(order_id)
      return

    if re.fullmatch(r"/api/admin/client/orders/[^/]+/submit-supply-chain", path):
      order_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_submit_supply_chain(order_id, body)
      return

    if path == "/api/admin/client/product-pricing/apply-recommended":
      self._handle_admin_apply_recommended_pricing()
      return

    if path == "/api/admin/client/coupon-campaigns":
      self._handle_admin_create_coupon_campaign(body)
      return

    if re.fullmatch(r"/api/admin/client/users/[^/]+/wallet", path):
      user_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_update_user_wallet(user_id, body)
      return

    if path == "/api/admin/client/assets/ensure-oss":
      self._handle_admin_ensure_assets_oss(body)
      return

    if re.fullmatch(r"/api/admin/client/assets/[^/]+/delete", path):
      asset_id = unquote(path.rsplit("/", 2)[-2])
      self._handle_admin_delete_asset(asset_id, body)
      return

    self._json({"errorCode": "NOT_FOUND", "message": "接口不存在。"}, 404)

  def _require_admin(self) -> dict[str, Any] | None:
    admin = admin_from_auth(self._auth_headers())
    if not admin:
      status, payload = json_error("ADMIN_AUTH_REQUIRED", "请先登录运营后台。", 401)
      self._json(payload, status)
      return None
    return admin

  def _order_snapshot(self, user_id: str, order: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(order.get("metadata") or {})
    metadata.setdefault("userId", user_id)
    supply_chain = metadata.get("supplyChain") if isinstance(metadata.get("supplyChain"), dict) else {}
    snapshot = {
      **order,
      "shippingSummary": order.get("shippingSummary") or shipping_summary(metadata.get("shippingAddress")),
      "supplierStatusName": order.get("supplierStatusName") or supply_chain.get("orderStatusName"),
      "supplierSyncedAt": order.get("supplierSyncedAt") or supply_chain.get("syncedAt"),
      "metadata": metadata,
    }
    # Older local test orders predate the payment contract. They must never look ready for supplier submission.
    if not order_is_paid(order) and not supply_chain_plat_order_id(order):
      snapshot["status"] = "待支付"
      snapshot["eta"] = "等待用户支付积分后进入运营核对"
    return snapshot

  def _handle_admin_list_orders(self, parsed: Any) -> None:
    if not self._require_admin():
      return
    query = parse_qs(parsed.query)
    user_id = optional_text((query.get("userId") or [None])[0])
    orders_bucket = STATE.setdefault("orders", {})
    if normalize_local_demo_urls(orders_bucket):
      save_state(STATE)
    orders = [self._order_snapshot(current_user_id, order) for current_user_id, order in iter_orders(user_id)]
    self._json(orders)

  def _handle_admin_get_commerce_config(self) -> None:
    if not self._require_admin():
      return
    self._json(commerce_config_snapshot())

  def _handle_admin_update_commerce_config(self, body: dict[str, Any]) -> None:
    if not self._require_admin():
      return
    config = commerce_config()
    requested_options = body.get("shippingOptions")
    if requested_options is not None:
      if not isinstance(requested_options, list):
        status, payload = json_error("CLIENT_SHIPPING_FEE_INVALID", "物流方式必须包含中通和顺丰的费用。", 422)
        self._json(payload, status)
        return
      labels = {item["id"]: item["label"] for item in DEFAULT_SHIPPING_OPTIONS}
      next_options: list[dict[str, Any]] = []
      seen: set[str] = set()
      for raw in requested_options:
        if not isinstance(raw, dict):
          continue
        option_id = str(raw.get("id") or "").strip().lower()
        fee_cents = optional_int(raw.get("feeCents"))
        if option_id not in labels or option_id in seen or fee_cents is None or fee_cents < 0 or fee_cents > 200000:
          status, payload = json_error("CLIENT_SHIPPING_FEE_INVALID", "物流费用必须是 0 到 2000 元之间的整数分。", 422)
          self._json(payload, status)
          return
        next_options.append({"id": option_id, "label": labels[option_id], "feeCents": fee_cents})
        seen.add(option_id)
      if set(labels) != seen:
        status, payload = json_error("CLIENT_SHIPPING_FEE_INVALID", "必须同时配置中通和顺丰。", 422)
        self._json(payload, status)
        return
      config["shippingOptions"] = next_options
    else:
      shipping_fee_cents = optional_int(body.get("shippingFeeCents"))
      if shipping_fee_cents is None or shipping_fee_cents < 0 or shipping_fee_cents > 200000:
        status, payload = json_error("CLIENT_SHIPPING_FEE_INVALID", "物流费用必须是 0 到 2000 元之间的整数分。", 422)
        self._json(payload, status)
        return
      config["shippingOptions"] = [
        {**item, "feeCents": shipping_fee_cents if item["id"] == "zto" else item["feeCents"]}
        for item in config["shippingOptions"]
      ]
    config["shippingFeeCents"] = next(item["feeCents"] for item in config["shippingOptions"] if item["id"] == "zto")
    config["shippingConfigured"] = True
    save_state(STATE)
    self._json(commerce_config_snapshot())

  def _handle_admin_list_product_pricing(self) -> None:
    if not self._require_admin():
      return
    self._json(product_pricing_snapshot())

  def _handle_admin_update_product_pricing(self, product_id: str, body: dict[str, Any]) -> None:
    if not self._require_admin():
      return
    if product_id not in SUPPLY_CHAIN_PRODUCT_OVERRIDES:
      status, payload = json_error("CLIENT_PRODUCT_NOT_FOUND", "商品不存在或未接入。", 404)
      self._json(payload, status)
      return
    sale_price_points = optional_int(body.get("salePricePoints"))
    sale_price_cents = sale_price_points * 100 if sale_price_points is not None else optional_int(body.get("salePriceCents"))
    if sale_price_cents is None or sale_price_cents <= 0 or sale_price_cents > 100000000:
      status, payload = json_error("CLIENT_PRODUCT_SALE_PRICE_INVALID", "商品售价必须大于 0。", 422)
      self._json(payload, status)
      return
    config = commerce_config()
    prices = config.setdefault("productPrices", {})
    prices[product_id] = sale_price_cents
    save_state(STATE)
    self._json(next(item for item in product_pricing_snapshot() if item["productId"] == product_id))

  def _handle_admin_apply_recommended_pricing(self) -> None:
    admin = self._require_admin()
    if not admin:
      return
    prices = commerce_config().setdefault("productPrices", {})
    updated = 0
    for product_id, product in SUPPLY_CHAIN_PRODUCT_OVERRIDES.items():
      cost_price_cents, _ = product_cost_quote(product_id, str(product.get("name") or ""))
      prices[product_id] = recommended_sale_price_points(cost_price_cents) * 100
      updated += 1
    save_state(STATE)
    self._json({
      "updated": updated,
      "updatedBy": admin.get("username"),
      "pricing": product_pricing_snapshot(),
    })

  def _handle_admin_list_coupon_campaigns(self) -> None:
    if not self._require_admin():
      return
    campaigns = [
      coupon_campaign_snapshot(item)
      for item in STATE.setdefault("couponCampaigns", [])
      if isinstance(item, dict)
    ]
    campaigns.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    self._json(campaigns)

  def _handle_admin_create_coupon_campaign(self, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    name = optional_text(body.get("name"))
    quantity = optional_int(body.get("quantity"))
    value_points = optional_int(body.get("valuePoints"))
    if not name:
      status, payload = json_error("CLIENT_COUPON_NAME_REQUIRED", "请填写产品券名称。", 422)
      self._json(payload, status)
      return
    if quantity is None or quantity < 1 or quantity > 500:
      status, payload = json_error("CLIENT_COUPON_QUANTITY_INVALID", "单批产品券数量必须在 1 到 500 之间。", 422)
      self._json(payload, status)
      return
    if value_points is None or value_points < 1 or value_points > 100000:
      status, payload = json_error("CLIENT_COUPON_VALUE_INVALID", "产品券抵扣积分必须在 1 到 100000 之间。", 422)
      self._json(payload, status)
      return
    product_id = optional_text(body.get("productId"))
    if product_id and product_template_id(product_id) not in SUPPLY_CHAIN_PRODUCT_OVERRIDES:
      status, payload = json_error("CLIENT_PRODUCT_NOT_FOUND", "指定商品不存在或未接入。", 404)
      self._json(payload, status)
      return
    expires_at = optional_text(body.get("expiresAt"))
    if expires_at:
      try:
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
      except ValueError:
        status, payload = json_error("CLIENT_COUPON_EXPIRES_AT_INVALID", "产品券有效期格式不正确。", 422)
        self._json(payload, status)
        return
    campaign_id = "coupon-campaign-" + secrets.token_hex(5)
    campaign = {
      "id": campaign_id,
      "name": name,
      "type": "product",
      "valuePoints": value_points,
      "productId": product_template_id(product_id) if product_id else None,
      "expiresAt": expires_at,
      "status": "active",
      "createdAt": now_label(),
      "createdBy": admin.get("username"),
    }
    STATE.setdefault("couponCampaigns", []).insert(0, campaign)
    prefix = optional_text(body.get("prefix")) or "AICP"
    for _ in range(quantity):
      STATE.setdefault("redemptionCodes", []).append({
        "code": generate_redemption_code(prefix),
        "campaignId": campaign_id,
        "status": "available",
        "createdAt": now_label(),
      })
    save_state(STATE)
    self._json(coupon_campaign_snapshot(campaign), 201)

  def _handle_redeem_coupon_code(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "").strip()
    code = str(body.get("code") or "").strip().upper()
    if not user_id or user_id in {"guest", "anonymous", "public", "demo-user"}:
      status, payload = json_error("CLIENT_AUTH_REQUIRED", "请先登录后再兑换产品券。", 401)
      self._json(payload, status)
      return
    if not code:
      status, payload = json_error("CLIENT_REDEMPTION_CODE_REQUIRED", "请输入兑换码。", 422)
      self._json(payload, status)
      return
    code_item = next(
      (item for item in STATE.setdefault("redemptionCodes", []) if isinstance(item, dict) and str(item.get("code") or "").upper() == code),
      None,
    )
    if not code_item:
      status, payload = json_error("CLIENT_REDEMPTION_CODE_NOT_FOUND", "兑换码不存在。", 404)
      self._json(payload, status)
      return
    if code_item.get("status") != "available":
      status, payload = json_error("CLIENT_REDEMPTION_CODE_USED", "兑换码已被使用或停用。", 409)
      self._json(payload, status)
      return
    campaign = next(
      (item for item in STATE.setdefault("couponCampaigns", []) if isinstance(item, dict) and item.get("id") == code_item.get("campaignId")),
      None,
    )
    if not campaign or campaign.get("status") != "active":
      status, payload = json_error("CLIENT_COUPON_CAMPAIGN_UNAVAILABLE", "该产品券活动已停止。", 409)
      self._json(payload, status)
      return
    expires_at = optional_text(campaign.get("expiresAt"))
    if expires_at:
      try:
        if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
          status, payload = json_error("CLIENT_REDEMPTION_CODE_EXPIRED", "兑换码已过期。", 409)
          self._json(payload, status)
          return
      except ValueError:
        pass
    wallet = ensure_wallet(user_id)
    if code in wallet.setdefault("redeemedCodes", []):
      status, payload = json_error("CLIENT_REDEMPTION_CODE_USED", "当前账号已经兑换过该兑换码。", 409)
      self._json(payload, status)
      return
    coupon = {
      "id": "coupon-" + secrets.token_hex(6),
      "campaignId": campaign.get("id"),
      "type": "product",
      "name": campaign.get("name"),
      "scope": campaign.get("productId") or "全部已上架产品",
      "productId": campaign.get("productId"),
      "valuePoints": campaign.get("valuePoints"),
      "value": f"抵扣 {campaign.get('valuePoints')} 积分",
      "status": "available",
      "expiresAt": campaign.get("expiresAt"),
      "source": "兑换码",
      "redeemedAt": now_label(),
    }
    wallet.setdefault("coupons", []).insert(0, coupon)
    wallet["redeemedCodes"].append(code)
    wallet["latestWalletEvent"] = f"兑换成功：{coupon['name']}，可抵扣 {coupon['valuePoints']} 积分。"
    wallet["updatedAt"] = now_label()
    wallet["updatedBy"] = "coupon-redemption"
    refresh_wallet_coupon_count(wallet)
    code_item["status"] = "redeemed"
    code_item["redeemedBy"] = user_id
    code_item["redeemedAt"] = now_label()
    save_state(STATE)
    self._json({"coupon": coupon, "wallet": dict(wallet)})

  def _handle_admin_list_publish_applications(self, parsed: Any) -> None:
    if not self._require_admin():
      return
    query = parse_qs(parsed.query)
    status = optional_text((query.get("status") or [None])[0])
    publish_bucket = STATE.setdefault("publishApplications", {})
    if normalize_local_demo_urls(publish_bucket):
      save_state(STATE)
    rows = []
    for user_id, item in iter_publish_applications(status):
      rows.append({**item, "metadata": {"userId": user_id}})
    self._json(rows)

  def _handle_admin_list_complaints(self, parsed: Any) -> None:
    if not self._require_admin():
      return
    query = parse_qs(parsed.query)
    status_filter = optional_text((query.get("status") or [None])[0])
    complaints_bucket = STATE.setdefault("complaints", {})
    if normalize_local_demo_urls(complaints_bucket):
      save_state(STATE)
    rows: list[dict[str, Any]] = []
    for user_id, items in complaints_bucket.items():
      if not isinstance(items, list):
        continue
      for item in items:
        if status_filter and item.get("status") != status_filter:
          continue
        rows.append({**item, "metadata": {"userId": user_id}})
    rows.sort(key=lambda item: str(item.get("submittedAt") or ""), reverse=True)
    self._json(rows)

  def _handle_admin_list_users(self, parsed: Any) -> None:
    if not self._require_admin():
      return
    query = parse_qs(parsed.query)
    keyword = str((query.get("q") or [""])[0] or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for user_id, user in STATE.setdefault("users", {}).items():
      if not isinstance(user, dict) or user.get("role") == "admin":
        continue
      searchable = " ".join(
        str(user.get(key) or "")
        for key in ("id", "username", "displayName", "phone", "email", "status")
      ).lower()
      if keyword and keyword not in searchable:
        continue
      wallet = ensure_wallet(user_id)
      refresh_wallet_coupon_count(wallet)
      rows.append({
        **user,
        "wallet": dict(wallet),
        "assetCount": len(STATE.setdefault("assets", {}).get(user_id, []) or []),
        "taskCount": len(STATE.setdefault("tasks", {}).get(user_id, []) or []),
        "orderCount": len(STATE.setdefault("orders", {}).get(user_id, []) or []),
        "publishCount": len(STATE.setdefault("publishApplications", {}).get(user_id, []) or []),
        "complaintCount": len(STATE.setdefault("complaints", {}).get(user_id, []) or []),
      })
    rows.sort(key=lambda item: str(item.get("lastLoginAt") or item.get("createdAt") or ""), reverse=True)
    self._json(rows)

  def _asset_snapshot(self, user_id: str, asset: dict[str, Any]) -> dict[str, Any]:
    metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
    return {
      **asset,
      "userId": user_id,
      "storageStatus": asset_storage_status(asset),
      "ossKey": metadata.get("ossKey") or oss_object_key_from_url(asset.get("url")),
      "ossUrl": metadata.get("ossUrl") or (asset.get("url") if is_oss_asset_url(asset.get("url")) else None),
      "removedAt": asset.get("removedAt"),
      "metadata": metadata,
    }

  def _handle_admin_list_assets(self, parsed: Any) -> None:
    if not self._require_admin():
      return
    query = parse_qs(parsed.query)
    keyword = str((query.get("q") or [""])[0] or "").strip().lower()
    user_filter = optional_text((query.get("userId") or [None])[0])
    storage_filter = optional_text((query.get("storage") or [None])[0])
    include_deleted = str((query.get("includeDeleted") or ["1"])[0]).lower() not in {"0", "false", "no"}
    assets_bucket = STATE.setdefault("assets", {})
    if normalize_local_demo_urls(assets_bucket):
      save_state(STATE)
    rows: list[dict[str, Any]] = []
    for user_id, assets in assets_bucket.items():
      if user_filter and user_id != user_filter:
        continue
      if not isinstance(assets, list):
        continue
      for asset in assets:
        if not isinstance(asset, dict):
          continue
        snapshot = self._asset_snapshot(user_id, asset)
        if not include_deleted and snapshot.get("storageStatus") == "deleted":
          continue
        if storage_filter and snapshot.get("storageStatus") != storage_filter:
          continue
        searchable = " ".join(
          str(snapshot.get(key) or "")
          for key in ("id", "title", "type", "source", "userId", "storageStatus", "ossKey")
        ).lower()
        if keyword and keyword not in searchable:
          continue
        rows.append(snapshot)
    rows.sort(key=lambda item: str(item.get("createdAt") or item.get("removedAt") or ""), reverse=True)
    self._json(rows)

  def _handle_admin_update_user_wallet(self, user_id: str, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    user = STATE.setdefault("users", {}).get(user_id)
    if not user or user.get("role") == "admin":
      status, payload = json_error("CLIENT_USER_NOT_FOUND", "用户不存在。", 404)
      self._json(payload, status)
      return
    ai_delta = optional_int(body.get("aiCreditsDelta")) or 0
    coupon_delta = optional_int(body.get("productCouponDelta")) or 0
    share_delta = optional_float(body.get("shareBalanceDelta"), 0.0)
    if ai_delta == 0 and coupon_delta == 0 and share_delta == 0:
      status, payload = json_error("CLIENT_WALLET_DELTA_REQUIRED", "请填写需要调整的积分、产品券或抵扣金额。", 422)
      self._json(payload, status)
      return
    wallet = ensure_wallet(user_id)
    wallet["aiCredits"] = max(0, int(wallet.get("aiCredits") or 0) + ai_delta)
    if coupon_delta > 0:
      for _ in range(coupon_delta):
        wallet.setdefault("coupons", []).insert(0, {
          "id": "coupon-manual-" + secrets.token_hex(5),
          "type": "product",
          "name": "运营补发产品券",
          "scope": "全部已上架产品",
          "valuePoints": 50,
          "value": "抵扣 50 积分",
          "status": "available",
          "source": "运营手动发放",
        })
    elif coupon_delta < 0:
      coupons_to_consume = available_wallet_coupons(wallet)[: abs(coupon_delta)]
      for coupon in coupons_to_consume:
        coupon["status"] = "used"
        coupon["usedAt"] = now_label()
        coupon["usedReason"] = "运营手动扣减"
      remaining = max(0, abs(coupon_delta) - len(coupons_to_consume))
      if remaining:
        wallet["legacyProductCouponCount"] = max(0, optional_int(wallet.get("legacyProductCouponCount")) or 0) - remaining
    refresh_wallet_coupon_count(wallet)
    wallet["shareBalance"] = round(max(0.0, optional_float(wallet.get("shareBalance"), 0.0) + share_delta), 2)
    note = optional_text(body.get("note")) or "运营手动调整权益"
    wallet["latestWalletEvent"] = note
    wallet["updatedAt"] = now_label()
    wallet["updatedBy"] = admin.get("username")
    save_state(STATE)
    self._json({"userId": user_id, "wallet": dict(wallet)})

  def _iter_admin_target_assets(self, body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    asset_ids = {str(item).strip() for item in (body.get("assetIds") or []) if str(item or "").strip()}
    single_asset_id = optional_text(body.get("assetId"))
    if single_asset_id:
      asset_ids.add(single_asset_id)
    user_filter = optional_text(body.get("userId"))
    targets: list[tuple[str, dict[str, Any]]] = []
    for user_id, assets in STATE.setdefault("assets", {}).items():
      if user_filter and user_id != user_filter:
        continue
      if not isinstance(assets, list):
        continue
      for asset in assets:
        if not isinstance(asset, dict):
          continue
        if asset_ids and str(asset.get("id") or "") not in asset_ids:
          continue
        targets.append((user_id, asset))
    return targets

  def _handle_admin_ensure_assets_oss(self, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    raw_limit = optional_int(body.get("limit"))
    limit = max(1, min(raw_limit or 25, 100))
    targets = self._iter_admin_target_assets(body)
    if not body.get("assetIds") and not body.get("assetId"):
      targets = [
        (user_id, asset)
        for user_id, asset in targets
        if asset_storage_status(asset) in {"local", "external", "unknown"}
      ]
    targets = targets[:limit]
    migrated = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    for user_id, asset in targets:
      try:
        changed = ensure_asset_oss(user_id, asset, reason=f"ops:{admin.get('username') or 'admin'}")
        if changed:
          migrated += 1
        else:
          skipped += 1
      except Exception as exc:  # noqa: BLE001 - keep batch migration visible
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        metadata["ossStatus"] = "failed"
        metadata["ossLastError"] = str(exc)
        metadata["ossLastErrorAt"] = now_label()
        asset["metadata"] = metadata
        errors.append({"assetId": str(asset.get("id") or ""), "userId": user_id, "message": str(exc)})
    save_state(STATE)
    self._json({
      "migrated": migrated,
      "skipped": skipped,
      "failed": len(errors),
      "errors": errors[:20],
      "assets": [self._asset_snapshot(user_id, asset) for user_id, asset in targets],
    })

  def _handle_admin_delete_asset(self, asset_id: str, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    user_filter = optional_text(body.get("userId"))
    target_user_id = ""
    target_asset: dict[str, Any] | None = None
    for user_id, asset in self._iter_admin_target_assets({"assetId": asset_id, "userId": user_filter}):
      target_user_id = user_id
      target_asset = asset
      break
    if not target_asset:
      status, payload = json_error("CLIENT_ASSET_NOT_FOUND", "资产不存在。", 404)
      self._json(payload, status)
      return
    metadata = target_asset.get("metadata") if isinstance(target_asset.get("metadata"), dict) else {}
    delete_object = bool(body.get("deleteObject"))
    delete_result: dict[str, Any] | None = None
    if delete_object and not metadata.get("ossDeletedAt"):
      try:
        delete_result = delete_oss_objects_for_asset(target_asset)
        metadata["ossDeletedAt"] = now_label()
        metadata["ossDeletedBy"] = admin.get("username")
        metadata["ossDeleteResult"] = delete_result
      except Exception as exc:  # noqa: BLE001 - surface object deletion failure
        metadata["ossDeleteError"] = str(exc)
        metadata["ossDeleteErrorAt"] = now_label()
        target_asset["metadata"] = metadata
        save_state(STATE)
        status, payload = json_error("CLIENT_ASSET_OSS_DELETE_FAILED", f"OSS 文件删除失败：{exc}", 502)
        self._json(payload, status)
        return
    target_asset["visibility"] = "deleted"
    target_asset["selected"] = False
    target_asset["removedAt"] = target_asset.get("removedAt") or now_label()
    target_asset["removedBy"] = admin.get("username")
    target_asset["removeReason"] = optional_text(body.get("reason")) or "运营后台删除"
    metadata["deletedByOps"] = True
    metadata["deletedAt"] = target_asset["removedAt"]
    metadata["deletedBy"] = admin.get("username")
    target_asset["metadata"] = metadata
    save_state(STATE)
    response = self._asset_snapshot(target_user_id, target_asset)
    if delete_result is not None:
      response["ossDeleteResult"] = delete_result
    self._json(response)

  def _handle_admin_review_publish_application(self, application_id: str, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    next_status = str(body.get("status") or "").strip()
    if next_status not in {"approved", "rejected"}:
      status, payload = json_error("CLIENT_PUBLISH_REVIEW_STATUS_INVALID", "审核状态只能是 approved 或 rejected。", 422)
      self._json(payload, status)
      return
    for user_id, item in iter_publish_applications():
      if item.get("id") == application_id:
        item["status"] = next_status
        item["reviewNote"] = body.get("reviewNote") or ("审核通过" if next_status == "approved" else "审核驳回")
        item["reviewedAt"] = now_label()
        item["reviewer"] = admin.get("username")
        save_state(STATE)
        self._json({**item, "metadata": {"userId": user_id}})
        return
    status, payload = json_error("CLIENT_PUBLISH_APPLICATION_NOT_FOUND", "公开申请不存在。", 404)
    self._json(payload, status)

  def _handle_admin_review_complaint(self, complaint_id: str, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    next_status = str(body.get("status") or "").strip()
    status_labels = {
      "processing": "处理中",
      "hidden": "已临时隐藏",
      "resolved": "已结案",
      "rejected": "已驳回",
    }
    if next_status not in status_labels:
      status, payload = json_error("CLIENT_COMPLAINT_REVIEW_STATUS_INVALID", "投诉状态只能是 processing、hidden、resolved 或 rejected。", 422)
      self._json(payload, status)
      return
    user_id, item = find_complaint(complaint_id)
    if not item or not user_id:
      status, payload = json_error("CLIENT_COMPLAINT_NOT_FOUND", "投诉记录不存在。", 404)
      self._json(payload, status)
      return
    note = optional_text(body.get("opsNote")) or status_labels[next_status]
    item["status"] = next_status
    item["opsNote"] = note
    item["handledAt"] = now_label()
    item["handler"] = admin.get("username")
    save_state(STATE)
    self._json({**item, "metadata": {"userId": user_id}})

  def _handle_admin_sync_order(self, order_id: str) -> None:
    if not self._require_admin():
      return
    user_id, order = find_order(order_id)
    if not order or not user_id:
      status, payload = json_error("CLIENT_ORDER_NOT_FOUND", "订单不存在。", 404)
      self._json(payload, status)
      return
    plat_order_id = supply_chain_plat_order_id(order)
    if not plat_order_id:
      status, payload = json_error("CLIENT_ORDER_NOT_SUBMITTED_TO_SUPPLIER", "订单尚未提交供应链，无法同步生产或物流状态。", 409)
      self._json(payload, status)
      return
    try:
      response = humcustom_query_order(plat_order_id)
    except HumcustomError as exc:
      self._json({"errorCode": exc.code, "message": exc.message}, exc.status)
      return
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    items = data.get("orderDetailList")
    selected = None
    if isinstance(items, list):
      for item in items:
        if isinstance(item, dict) and str(item.get("platOrderId") or "").strip() == plat_order_id:
          selected = item
          break
      if selected is None:
        selected = next((item for item in items if isinstance(item, dict)), None)
    if not isinstance(selected, dict):
      status, payload = json_error("CLIENT_SUPPLY_CHAIN_ORDER_NOT_FOUND", "供应链未返回该订单记录。", 404)
      self._json(payload, status)
      return
    metadata = order.setdefault("metadata", {})
    supply_chain = dict(metadata.get("supplyChain") or {})
    synced_at = now_label()
    supply_chain.update({
      "provider": "humcustom",
      "platOrderId": str(selected.get("platOrderId") or plat_order_id),
      "orderStatusName": optional_text(selected.get("orderStatusName")),
      "waybillNo": optional_text(selected.get("waybillNo")),
      "syncedAt": synced_at,
      "raw": response,
    })
    metadata["supplierSync"] = "synced"
    metadata["supplyChain"] = supply_chain
    order["metadata"] = metadata
    order["supplierStatusName"] = supply_chain.get("orderStatusName")
    order["logisticsNo"] = supply_chain.get("waybillNo") or order.get("logisticsNo")
    order["supplierSyncedAt"] = synced_at
    order["status"] = map_supply_chain_status(order.get("supplierStatusName"), str(order.get("status") or "待确认"))
    materialize_supply_chain_render_assets(user_id, order, response)
    save_state(STATE)
    self._json(self._order_snapshot(user_id, order))

  def _handle_admin_submit_supply_chain(self, order_id: str, body: dict[str, Any]) -> None:
    admin = self._require_admin()
    if not admin:
      return
    user_id, order = find_order(order_id)
    if not order or not user_id:
      status, payload = json_error("CLIENT_ORDER_NOT_FOUND", "订单不存在。", 404)
      self._json(payload, status)
      return
    if not order_is_paid(order):
      status, payload = json_error("CLIENT_ORDER_PAYMENT_REQUIRED", "用户尚未完成平台支付，不能推送蜂鸟。", 409)
      self._json(payload, status)
      return
    try:
      submit_order_to_supply_chain(
        user_id,
        order,
        body,
        actor=f"ops:{admin.get('username') or 'admin'}",
      )
    except HumcustomError as exc:
      self._json({"errorCode": exc.code, "message": exc.message}, exc.status)
      return
    self._json(self._order_snapshot(user_id, order))

  def _handle_local_upload(self, body: dict[str, Any]) -> None:
    data_url = str(body.get("dataUrl") or "")
    match = re.match(r"data:([^;,]+)?;base64,(.+)", data_url, re.S)
    if not match:
      status, payload = json_error("CLIENT_ASSET_URL_INVALID", "图片上传数据格式不正确。", 422)
      self._json(payload, status)
      return
    mime = match.group(1) or "application/octet-stream"
    suffix = mimetypes.guess_extension(mime) or Path(str(body.get("fileName") or "")).suffix or ".bin"
    object_key = str(body.get("objectKey") or f"local/{int(time.time() * 1000)}-{secrets.token_hex(4)}{suffix}")
    safe_parts = [re.sub(r"[^A-Za-z0-9._-]+", "-", part) for part in object_key.split("/") if part]
    local_path = UPLOAD_DIR.joinpath(*safe_parts)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
      local_path.write_bytes(base64.b64decode(match.group(2)))
    except Exception:
      status, payload = json_error("UPLOAD_DECODE_FAILED", "图片上传数据无法解析。", 422)
      self._json(payload, status)
      return
    url_path = "/media/uploads/" + "/".join(quote(part) for part in safe_parts)
    self._json({"url": f"http://{self.headers.get('Host', '127.0.0.1:8240')}{url_path}", "objectKey": object_key})

  def _handle_client_asset_preview(self, asset_id: str, parsed: Any) -> None:
    query = parse_qs(parsed.query)
    user_id = optional_text((query.get("userId") or [None])[0])
    if not user_id:
      status, payload = json_error("CLIENT_ASSET_USER_REQUIRED", "缺少当前用户，无法读取素材预览。", 422)
      self._json(payload, status)
      return

    asset = next(
      (
        item
        for item in STATE.setdefault("assets", {}).get(user_id, [])
        if isinstance(item, dict) and item.get("id") == asset_id and not item.get("removedAt") and item.get("visibility") != "removed"
      ),
      None,
    )
    if not asset:
      status, payload = json_error("CLIENT_ASSET_NOT_FOUND", "当前素材不存在或不属于此账号。", 404)
      self._json(payload, status)
      return

    source_url = str(asset.get("url") or asset.get("thumbnailUrl") or "").strip()
    object_key = oss_object_key_from_url(source_url)
    if not object_key or not (OSS_ACCESS_KEY and OSS_SECRET_KEY and OSS_BUCKET):
      status, payload = json_error("CLIENT_ASSET_PREVIEW_UNAVAILABLE", "当前素材暂时无法用于 3D 预览，请重新上传后再试。", 503)
      self._json(payload, status)
      return

    try:
      auth = oss2.Auth(OSS_ACCESS_KEY, OSS_SECRET_KEY)
      bucket = oss2.Bucket(auth, _oss_endpoint(), OSS_BUCKET, connect_timeout=20)
      response = bucket.get_object(object_key)
      content_type = str(response.headers.get("Content-Type") or mimetypes.guess_type(object_key)[0] or "image/png").split(";", 1)[0].strip().lower()
      image_bytes = response.read(CLIENT_ASSET_PREVIEW_MAX_BYTES + 1)
    except Exception:  # noqa: BLE001 - external storage errors must not leak to clients
      status, payload = json_error("CLIENT_ASSET_PREVIEW_UNAVAILABLE", "素材预览服务暂时不可用，请稍后重试。", 502)
      self._json(payload, status)
      return

    if len(image_bytes) > CLIENT_ASSET_PREVIEW_MAX_BYTES:
      status, payload = json_error("CLIENT_ASSET_PREVIEW_TOO_LARGE", "图片文件过大，暂时不能用于 3D 预览。", 413)
      self._json(payload, status)
      return
    if not content_type.startswith("image/") or content_type == "image/svg+xml":
      status, payload = json_error("CLIENT_ASSET_PREVIEW_UNAVAILABLE", "当前素材不是可用于预览的图片格式。", 422)
      self._json(payload, status)
      return

    self._headers(
      200,
      content_type,
      {
        "Cache-Control": "private, max-age=600",
        "Content-Length": str(len(image_bytes)),
        "X-Content-Type-Options": "nosniff",
      },
    )
    self.wfile.write(image_bytes)

  def _serve_upload(self, path: str) -> None:
    relative = unquote(path.removeprefix("/media/uploads/"))
    target = (UPLOAD_DIR / relative).resolve()
    if not str(target).startswith(str(UPLOAD_DIR.resolve())) or not target.exists() or not target.is_file():
      self._json({"errorCode": "NOT_FOUND", "message": "文件不存在。"}, 404)
      return
    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    self._headers(200, content_type)
    self.wfile.write(target.read_bytes())

  def _handle_business(self, path: str, body: dict[str, Any]) -> None:
    if path == "/api/business/runs/get":
      proxied = proxy_midplatform(path, body)
      if proxied is not None:
        self._json(proxied)
        return
      self._json(midplatform_unavailable_payload(path), 503)
      return
    proxied = proxy_midplatform(path, body)
    if proxied is not None:
      self._json(proxied)
      return
    self._json(midplatform_unavailable_payload(path), 503)

  def _design_agent_bucket(self, user_id: str) -> list[dict[str, Any]]:
    return ensure_bucket("designAgentSessions", user_id)

  def _find_design_agent_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
    for session in self._design_agent_bucket(user_id):
      if session.get("sessionId") == session_id:
        return session
    if user_id != "demo-user":
      for session in self._design_agent_bucket("demo-user"):
        if session.get("sessionId") == session_id:
          return session
    return None

  def _agent_session_snapshot(self, session: dict[str, Any]) -> dict[str, Any]:
    user_id = str(session.get("userId") or "demo-user")
    refresh_running_agent_session(user_id, session)
    result_assets = []
    for asset_id in session.get("resultAssetIds") or []:
      asset = find_asset(user_id, str(asset_id))
      if asset:
        result_assets.append(asset)
    preview_asset = find_asset(user_id, str(session.get("currentPreviewAssetId") or ""))
    return {
      **session,
      "resultAssets": result_assets,
      "previewAsset": preview_asset,
    }

  def _handle_create_product_design_intake(self, body: dict[str, Any]) -> None:
    """One-shot VL intake for the manual product-design workflow.

    This endpoint intentionally returns a recommendation only. It does not spend
    credits or start a generation task before the user confirms the displayed route.
    """
    user_id = str(body.get("userId") or "demo-user")
    product_id = str(body.get("productId") or "").strip()
    if not product_id:
      status, payload = json_error("CLIENT_PRODUCT_REQUIRED", "请先选择商品，再让 AI 帮你判断图片怎么设计。", 422)
      self._json(payload, status)
      return
    source_asset_ids = normalize_id_list(body.get("sourceAssetIds") or body.get("assetIds") or [])
    if len(source_asset_ids) > 6:
      status, payload = json_error("CLIENT_DESIGN_INTAKE_ASSET_LIMIT_EXCEEDED", "一次最多分析 6 张图片，请先选择最关键的图片。", 400)
      self._json(payload, status)
      return
    for asset_id in source_asset_ids:
      if not find_asset(user_id, asset_id):
        status, payload = json_error("CLIENT_ASSET_NOT_FOUND", "当前素材不存在或不属于你的素材库。", 404)
        self._json(payload, status)
        return

    product_context = body.get("productContext") if isinstance(body.get("productContext"), dict) else {}
    message = str(body.get("message") or "").strip() or "请先判断这张图片最适合怎样做成当前杯子的可生产设计。"
    intake_id = "intake-" + secrets.token_hex(6)
    initial_context = {
      "source": "quick_design",
      "baseAssetRole": "source_asset" if source_asset_ids else "prompt_only",
      "assetIds": source_asset_ids,
      "previousIntent": None,
      "isFollowup": False,
    }
    intent_hint = classify_design_intent(message, first_user_asset(user_id, source_asset_ids), initial_context)
    initial_context["visionAnalysis"] = (
      analyze_agent_visual_context(user_id, source_asset_ids, message, product_context, intent_hint)
      if source_asset_ids
      else prompt_only_agent_analysis(message, product_context, intent_hint)
    )
    plan = build_design_agent_plan(user_id, intake_id, message, product_context, source_asset_ids, initial_context)
    self._json({
      "intakeId": intake_id,
      "source": "vl_design_intake",
      "plan": plan,
      "recommendation": quick_design_recommendation(plan),
    })

  def _handle_create_design_agent_session(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    product_id = str(body.get("productId") or "").strip()
    if not product_id:
      status, payload = json_error("CLIENT_PRODUCT_REQUIRED", "请先选择商品，再进入 AI 帮我设计。", 422)
      self._json(payload, status)
      return
    message = str(body.get("message") or body.get("initialMessage") or "").strip()
    if not message:
      message = "请根据当前商品和素材，帮我规划一套适合生产的设计方案。"
    source_asset_ids = [str(item) for item in (body.get("sourceAssetIds") or body.get("assetIds") or []) if str(item or "").strip()]
    product_context = body.get("productContext") if isinstance(body.get("productContext"), dict) else {}
    session_id = "agent-" + secrets.token_hex(6)
    initial_context = {
      "source": "explicit_assets" if source_asset_ids else "prompt_only",
      "baseAssetRole": "source_asset" if source_asset_ids else "prompt_only",
      "assetIds": source_asset_ids,
      "previousIntent": None,
      "isFollowup": False,
    }
    intent_hint = classify_design_intent(message, first_user_asset(user_id, source_asset_ids), initial_context)
    initial_context["visionAnalysis"] = (
      analyze_agent_visual_context(
        user_id,
        source_asset_ids,
        message,
        product_context,
        intent_hint,
      )
      if source_asset_ids
      else prompt_only_agent_analysis(message, product_context, intent_hint)
    )
    plan = build_design_agent_plan(user_id, session_id, message, product_context, source_asset_ids, initial_context)
    now = now_label()
    session = {
      "sessionId": session_id,
      "userId": user_id,
      "productId": product_id,
      "productName": body.get("productName") or product_context.get("productName") or product_id,
      "productContext": product_context,
      "sourceAssetIds": source_asset_ids,
      "sourceImageUrls": body.get("sourceImageUrls") or [],
      "status": "planning",
      "currentPlanId": plan["planId"],
      "messages": [
        {
          "messageId": "msg-" + secrets.token_hex(5),
          "role": "user",
          "type": "text",
          "content": message,
          "assetIds": source_asset_ids,
          "createdAt": now,
        },
        {
          "messageId": "msg-" + secrets.token_hex(5),
          "role": "assistant",
          "type": "plan",
          "content": plan["summaryForUser"],
          "planId": plan["planId"],
          "createdAt": now,
        },
      ],
      "plans": [plan],
      "steps": plan.get("steps") or [],
      "toolCalls": [],
      "workingMemory": {
        "activeSurfaceId": (plan.get("layoutPlan", {}).get("surfaceAssignments") or [{}])[0].get("surfaceId"),
        "currentAssetIds": source_asset_ids,
        "currentAssetRole": "source_asset" if source_asset_ids else "prompt_only",
        "lastIntent": plan.get("intent"),
        "lastPlanId": plan.get("planId"),
        "lastResultAssetIds": [],
        "acceptedAssetIds": [],
        "confirmedSurfaceAssignments": [],
        "contextSource": initial_context["source"],
      },
      "resultAssetIds": [],
      "currentPreviewAssetId": None,
      "createdAt": now,
      "updatedAt": now,
    }
    self._design_agent_bucket(user_id).insert(0, session)
    save_state(STATE)
    self._json(self._agent_session_snapshot(session))

  def _handle_get_design_agent_session(self, session_id: str, parsed: Any) -> None:
    query = parse_qs(parsed.query)
    user_id = (query.get("userId") or ["demo-user"])[0] or "demo-user"
    session = self._find_design_agent_session(user_id, session_id)
    if not session:
      for candidate_user_id, sessions in (STATE.get("designAgentSessions") or {}).items():
        if candidate_user_id == user_id or not isinstance(sessions, list):
          continue
        session = next((item for item in sessions if item.get("sessionId") == session_id), None)
        if session:
          user_id = str(candidate_user_id)
          break
    if not session:
      status, payload = json_error("CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND", "这个 AI 设计会话不存在。", 404)
      self._json(payload, status)
      return
    self._json(self._agent_session_snapshot(session))

  def _handle_design_agent_message(self, session_id: str, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    session = self._find_design_agent_session(user_id, session_id)
    if not session:
      status, payload = json_error("CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND", "这个 AI 设计会话不存在。", 404)
      self._json(payload, status)
      return
    message = str(body.get("message") or "").strip()
    if not message:
      status, payload = json_error("CLIENT_DESIGN_AGENT_MESSAGE_REQUIRED", "请先输入你想怎么设计。", 422)
      self._json(payload, status)
      return
    new_asset_ids = normalize_id_list(body.get("sourceAssetIds") or body.get("assetIds") or [])
    if new_asset_ids:
      session["sourceAssetIds"] = list(dict.fromkeys([*(session.get("sourceAssetIds") or []), *new_asset_ids]))
    context_asset_ids, context_source, base_asset_role = agent_context_asset_ids(session, new_asset_ids)
    memory = session.get("workingMemory") if isinstance(session.get("workingMemory"), dict) else {}
    followup = is_design_followup_message(message) or bool(context_source in {"working_memory", "session_results"} and not new_asset_ids)
    planner_context = {
      "source": context_source,
      "baseAssetRole": base_asset_role,
      "assetIds": context_asset_ids,
      "previousIntent": memory.get("lastIntent"),
      "isFollowup": followup,
    }
    intent_hint = classify_design_intent(message, first_user_asset(user_id, context_asset_ids), planner_context)
    product_context = session.get("productContext") if isinstance(session.get("productContext"), dict) else {}
    planner_context["visionAnalysis"] = (
      analyze_agent_visual_context(
        user_id,
        context_asset_ids,
        message,
        product_context,
        intent_hint,
      )
      if context_asset_ids
      else prompt_only_agent_analysis(message, product_context, intent_hint)
    )
    plan = build_design_agent_plan(
      user_id,
      session_id,
      message,
      product_context,
      context_asset_ids,
      planner_context,
    )
    now = now_label()
    session.setdefault("messages", []).append({
      "messageId": "msg-" + secrets.token_hex(5),
      "role": "user",
      "type": "text",
      "content": message,
      "assetIds": new_asset_ids,
      "createdAt": now,
    })
    session.setdefault("messages", []).append({
      "messageId": "msg-" + secrets.token_hex(5),
      "role": "assistant",
      "type": "plan",
      "content": plan["summaryForUser"],
      "planId": plan["planId"],
      "createdAt": now,
    })
    session.setdefault("plans", []).append(plan)
    remember_agent_plan(session, plan)
    session["steps"] = plan.get("steps") or []
    session["currentPlanId"] = plan["planId"]
    session["status"] = "planning"
    session["updatedAt"] = now
    save_state(STATE)
    self._json(self._agent_session_snapshot(session))

  def _handle_confirm_design_agent_plan(self, session_id: str, plan_id: str, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    session = self._find_design_agent_session(user_id, session_id)
    if not session:
      status, payload = json_error("CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND", "这个 AI 设计会话不存在。", 404)
      self._json(payload, status)
      return
    plan = next((item for item in session.get("plans") or [] if item.get("planId") == plan_id), None)
    if not plan:
      status, payload = json_error("CLIENT_DESIGN_AGENT_PLAN_NOT_FOUND", "这个设计方案不存在，请重新生成方案。", 404)
      self._json(payload, status)
      return
    with STATE_LOCK:
      if plan.get("intent") == "clarify":
        status, payload = json_error("CLIENT_DESIGN_AGENT_CLARIFY_REQUIRED", "这个方案还需要先补充设计方向。", 409)
        self._json(payload, status)
        return
      existing_execution = plan.get("execution") if isinstance(plan.get("execution"), dict) else {}
      existing_status = str(plan.get("status") or "")
      if existing_status in {"executing", "running"} or str(existing_execution.get("status") or "") in {"queued", "running"}:
        self._json({
          "session": self._agent_session_snapshot(session),
          "resultAssets": [],
          "status": "running",
          "message": "这套设计方案已经在生成中，完成后会回到当前会话。",
          "wallet": ensure_wallet(user_id),
        })
        return
      if existing_status == "preview_ready" or str(existing_execution.get("status") or "") == "completed":
        self._json({
          "session": self._agent_session_snapshot(session),
          "resultAssets": [],
          "status": "completed",
          "message": "这套设计方案已经生成过，可以直接查看结果或继续修改。",
          "wallet": ensure_wallet(user_id),
        })
        return
      plan_cost = agent_plan_cost_credits(plan)
      wallet = ensure_wallet(user_id)
      if plan_cost > 0 and not plan.get("walletCharge"):
        available_credits = int(wallet.get("aiCredits") or 0)
        if available_credits < plan_cost:
          status, payload = json_error("CLIENT_WALLET_CREDITS_NOT_ENOUGH", f"这次设计需要 {plan_cost} 积分，当前积分不足。", 402)
          self._json(payload, status)
          return
        wallet["aiCredits"] = available_credits - plan_cost
        wallet["latestWalletEvent"] = f"AI 设计已使用 {plan_cost} 积分。"
        wallet["updatedAt"] = now_label()
        plan["walletCharge"] = {
          "costCredits": plan_cost,
          "chargedAt": wallet["updatedAt"],
          "event": wallet["latestWalletEvent"],
        }
      confirm_message_id = "msg-" + secrets.token_hex(5)
      session.setdefault("messages", []).append({
        "messageId": confirm_message_id,
        "role": "user",
        "type": "confirmation",
        "content": "确认这套设计方案，开始生成。",
        "assetIds": [],
        "planId": plan_id,
        "createdAt": now_label(),
      })
      plan["confirmationMessageId"] = confirm_message_id
      plan["status"] = "executing"
      plan["needsUserConfirmation"] = False
      session["status"] = "executing"
      session["steps"] = plan.get("steps") or []
      session["updatedAt"] = now_label()
      save_state(STATE)
    execution = execute_design_agent_plan(user_id, session, plan)
    if execution.get("status") == "failed":
      wallet_charge = plan.get("walletCharge") if isinstance(plan.get("walletCharge"), dict) else None
      if wallet_charge and not wallet_charge.get("refundedAt"):
        refund_credits = int(wallet_charge.get("costCredits") or 0)
        wallet = ensure_wallet(user_id)
        wallet["aiCredits"] = int(wallet.get("aiCredits") or 0) + refund_credits
        wallet["latestWalletEvent"] = f"AI 设计执行失败，已退回 {refund_credits} 积分。"
        wallet["updatedAt"] = now_label()
        wallet_charge["refundedAt"] = wallet["updatedAt"]
      save_state(STATE)
      self._json({
        "session": self._agent_session_snapshot(session),
        "resultAssets": [],
        "status": "failed",
        "message": str(execution.get("message") or "设计方案暂时执行失败，请稍后重试。"),
        "wallet": ensure_wallet(user_id),
      })
      return
    now = now_label()
    result_assets = list(execution.get("resultAssets") or [])
    result_ids = [asset["id"] for asset in result_assets]
    session["resultAssetIds"] = list(dict.fromkeys([*result_ids, *(session.get("resultAssetIds") or [])]))
    if result_ids:
      remember_agent_results(session, result_ids, plan)
    plan["status"] = "preview_ready"
    plan["needsUserConfirmation"] = False
    execution_mode = str((execution.get("toolCall") or {}).get("executionMode") or agent_execution_mode_label())
    if execution.get("status") in {"queued", "running"}:
      result_message = str(execution.get("message") or "我已经把任务提交给图片处理服务，正在等待生成结果。")
      plan["status"] = "running"
      session["status"] = "executing"
      message_type = "notice"
    elif execution_mode == "real":
      result_message = "我已经按确认的方案完成生成，结果在下面。你可以采用整套设计，也可以继续让我修改。"
      session["status"] = "preview_ready"
      message_type = "result"
    else:
      result_message = "我已经确认这套方案；当前处于本地演示模式，下面只是流程预览，不会冒充真实生成结果。"
      session["status"] = "preview_ready"
      message_type = "result"
    session["steps"] = plan.get("steps") or []
    session.setdefault("messages", []).append({
      "messageId": "msg-" + secrets.token_hex(5),
      "role": "assistant",
      "type": message_type,
      "content": result_message,
      "assetIds": result_ids,
      "planId": plan_id,
      "createdAt": now,
    })
    session["updatedAt"] = now
    save_state(STATE)
    self._json({"session": self._agent_session_snapshot(session), "resultAssets": result_assets, "wallet": ensure_wallet(user_id)})

  def _handle_confirm_design_agent_step(self, session_id: str, step_id: str, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    session = self._find_design_agent_session(user_id, session_id)
    if not session:
      status, payload = json_error("CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND", "这个 AI 设计会话不存在。", 404)
      self._json(payload, status)
      return
    asset_id = optional_text(body.get("assetId"))
    surface_id = optional_text(body.get("surfaceId")) or "front"
    mode = optional_text(body.get("mode")) or "fit"
    if asset_id and not find_asset(user_id, asset_id):
      status, payload = json_error("CLIENT_ASSET_NOT_FOUND", "当前素材不存在，请重新选择。", 404)
      self._json(payload, status)
      return
    plan = next((item for item in session.get("plans") or [] if item.get("planId") == session.get("currentPlanId")), None)
    if plan:
      assignments = plan.setdefault("layoutPlan", {}).setdefault("surfaceAssignments", [])
      matched = next((item for item in assignments if item.get("surfaceId") == surface_id), None)
      if not matched:
        matched = {"surfaceId": surface_id, "surfaceLabel": body.get("surfaceLabel") or surface_id}
        assignments.append(matched)
      matched.update({
        "assetRef": asset_id,
        "mode": mode,
        "fullBleed": bool(body.get("fullBleed", mode == "wrap")),
        "needsSeamless": bool(body.get("needsSeamless", mode == "wrap")),
        "scale": body.get("scale") or matched.get("scale") or 1,
        "position": body.get("position") if isinstance(body.get("position"), dict) else matched.get("position") or {"x": 0, "y": 0},
      })
    confirmed = session.setdefault("workingMemory", {}).setdefault("confirmedSurfaceAssignments", [])
    confirmed.append({
      "stepId": step_id,
      "surfaceId": surface_id,
      "assetId": asset_id,
      "mode": mode,
      "confirmedAt": now_label(),
    })
    memory = session.setdefault("workingMemory", {})
    if asset_id:
      memory["acceptedAssetIds"] = list(dict.fromkeys([asset_id, *normalize_id_list(memory.get("acceptedAssetIds"))]))
      memory["currentAssetIds"] = [asset_id]
      memory["currentAssetRole"] = "accepted_asset"
    memory["activeSurfaceId"] = surface_id
    memory["lastLayoutMode"] = mode
    session.setdefault("messages", []).append({
      "messageId": "msg-" + secrets.token_hex(5),
      "role": "assistant",
      "type": "notice",
      "content": "已采用为当前产品设计。你可以继续让我微调，也可以放入设计篮。",
      "assetIds": [asset_id] if asset_id else [],
      "createdAt": now_label(),
    })
    session["status"] = "surface_confirmed"
    session["updatedAt"] = now_label()
    save_state(STATE)
    self._json(self._agent_session_snapshot(session))

  def _handle_apply_design_agent_preview(self, session_id: str, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    session = self._find_design_agent_session(user_id, session_id)
    if not session:
      status, payload = json_error("CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND", "这个 AI 设计会话不存在。", 404)
      self._json(payload, status)
      return
    product_id = str(session.get("productId") or body.get("productId") or "cup-10395")
    product_name = str(session.get("productName") or body.get("productName") or product_id)
    plan = next((item for item in session.get("plans") or [] if item.get("planId") == session.get("currentPlanId")), None)
    source_asset_id = optional_text(body.get("assetId"))
    if not source_asset_id:
      assignments = ((plan or {}).get("layoutPlan") or {}).get("surfaceAssignments") or []
      source_asset_id = optional_text(next((item.get("assetRef") for item in assignments if item.get("assetRef")), None))
    if not source_asset_id and session.get("resultAssetIds"):
      source_asset_id = str(session["resultAssetIds"][0])
    source_asset = find_asset(user_id, source_asset_id) if source_asset_id else None
    # A generated design is the only truthful preview before the supplier returns
    # its rendered product image. Never present a fixed catalog mockup as the
    # user's newly-created design.
    preview_url = str(
      (source_asset or {}).get("url")
      or (source_asset or {}).get("thumbnailUrl")
      or catalog_product_render_url(product_id)
      or ""
    )
    if not preview_url:
      status, payload = json_error("CLIENT_PRODUCT_RENDER_UNAVAILABLE", "当前设计稿缺少可展示图片，请重新生成后再试。", 409)
      self._json(payload, status)
      return
    asset = {
      "id": "agent-preview-" + secrets.token_hex(6),
      "type": "product_preview",
      "title": f"{product_name} · AI 设计预览",
      "url": preview_url,
      "thumbnailUrl": preview_url,
      "source": "AI 帮我设计",
      "createdAt": now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "product_snapshot",
      "usedInProducts": 1,
      "metadata": {
        "agentSessionId": session_id,
        "agentPlanId": (plan or {}).get("planId"),
        "productId": product_id,
        "productName": product_name,
        "sourceAssetId": source_asset_id,
        "sourceAssetTitle": source_asset.get("title") if source_asset else None,
        "sourceAssetUrl": source_asset.get("url") if source_asset else None,
        "previewKind": "design_artwork",
        "supplierRenderPending": True,
        "designConfig": body.get("designConfig") or {},
        "layoutPlan": (plan or {}).get("layoutPlan") or {},
      },
    }
    prepare_asset_for_storage(user_id, asset, reason="agent-preview")
    ensure_bucket("assets", user_id).insert(0, asset)
    session["currentPreviewAssetId"] = asset["id"]
    memory = session.setdefault("workingMemory", {})
    memory["previewAssetId"] = asset["id"]
    memory["lastPreviewSourceAssetId"] = source_asset_id
    session["status"] = "preview_applied"
    session["updatedAt"] = now_label()
    session.setdefault("messages", []).append({
      "messageId": "msg-" + secrets.token_hex(5),
      "role": "assistant",
      "type": "preview",
      "content": "产品预览已生成，可以放入设计篮，也可以继续修改。",
      "assetIds": [asset["id"]],
      "createdAt": now_label(),
    })
    save_state(STATE)
    self._json({"session": self._agent_session_snapshot(session), "previewAsset": asset})

  def _handle_create_asset(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    asset = {
      "id": body.get("id") or "asset-" + secrets.token_hex(6),
      "type": body.get("type") or "original",
      "title": body.get("title") or "未命名素材",
      "url": body.get("url") or body.get("thumbnailUrl") or public_demo("/demo/market/pattern-vintage-floral.webp"),
      "thumbnailUrl": body.get("thumbnailUrl") or body.get("url") or public_demo("/demo/market/pattern-vintage-floral.webp"),
      "source": body.get("source") or "用户上传",
      "createdAt": now_label(),
      "selected": True,
      "favorite": False,
      "visibility": body.get("visibility") or "private",
      "licenseMode": body.get("licenseMode") or "private",
      "licenseSource": body.get("licenseSource") or "uploaded",
      "licensePoints": body.get("licensePoints"),
      "author": body.get("author"),
      "acquiredAt": body.get("acquiredAt"),
      "removedAt": body.get("removedAt"),
      "usedInProducts": optional_int(body.get("usedInProducts")) or 0,
      "width": body.get("width"),
      "height": body.get("height"),
      "dpi": body.get("dpi"),
      "metadata": body.get("metadata") or {},
    }
    prepare_asset_for_storage(user_id, asset, reason="client-asset-create")
    enrich_asset_dimensions(asset)
    ensure_bucket("assets", user_id).insert(0, asset)
    save_state(STATE)
    self._json(asset)

  def _handle_create_verified_seamless_artwork(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    source_url = optional_text(body.get("sourceUrl"))
    if not source_url:
      status, payload = json_error("CLIENT_PRODUCTION_ARTWORK_SOURCE_REQUIRED", "请先提供 AI 生成的连续图。", 422)
      self._json(payload, status)
      return
    width = optional_int(body.get("width")) or 0
    height = optional_int(body.get("height")) or 0
    dpi = optional_int(body.get("dpi")) or 150
    try:
      asset = create_verified_seamless_artwork(
        user_id=user_id,
        source_url=source_url,
        title=optional_text(body.get("title")) or "AI 四方连续生产图",
        width=width,
        height=height,
        dpi=dpi,
        source_asset_id=optional_text(body.get("sourceAssetId")),
        business_run_id=optional_text(body.get("businessRunId")),
      )
    except ValueError as exc:
      status, payload = json_error(str(exc), "生产图尺寸不符合当前设计面要求。", 422)
      self._json(payload, status)
      return
    except RuntimeError as exc:
      code = str(exc)
      message = "生产图边缘校验暂时不可用。" if code == "CLIENT_PRODUCTION_ARTWORK_PROCESS_UNAVAILABLE" else "生产图导出失败，请稍后重试。"
      status, payload = json_error(code, message, 502)
      self._json(payload, status)
      return
    self._json(asset)

  def _handle_create_process_task(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    task_type = str(body.get("type") or "extract")
    candidate_count = read_process_candidate_count(task_type, body, params)
    real_business_run = bool(params.get("realBusinessRun"))
    result_images = [url for url in (params.get("resultImages") or []) if is_probable_image_url(url)]
    input_images = list(body.get("inputImages") or [])
    cost_credits = process_task_credit_cost(task_type, body, params, input_images)

    if real_business_run:
      active_count = sum(
        1
        for item in ensure_bucket("tasks", user_id)
        if item.get("status") in {"pending", "processing"}
      )
      if active_count >= CLIENT_QUEUE_MAX_TASKS:
        status, payload = json_error("CLIENT_QUEUE_LIMIT_REACHED", "当前排队任务较多，请稍后再提交。", 429)
        self._json(payload, status)
        return
      wallet = ensure_wallet(user_id)
      available_credits = int(wallet.get("aiCredits") or 0)
      if cost_credits > available_credits:
        status, payload = json_error(
          "CLIENT_WALLET_CREDITS_NOT_ENOUGH",
          f"这次图片处理需要 {cost_credits} 积分，当前可用 {available_credits} 积分。请充值后再提交。",
          402,
        )
        payload["requiredCredits"] = cost_credits
        payload["availableCredits"] = available_credits
        self._json(payload, status)
        return
      if cost_credits > 0:
        wallet["aiCredits"] = available_credits - cost_credits
        wallet["latestWalletEvent"] = f"图片批处理已使用 {cost_credits} 积分。"
        wallet["updatedAt"] = now_label()

    if not result_images and not real_business_run:
      fallback = {
        "extract": public_demo("/demo/market/pattern-vintage-floral.webp"),
        "variation": public_demo("/demo/market/pattern-garden.webp"),
        "extend": (body.get("inputImages") or [public_demo("/demo/market/pattern-bloom.webp")])[0],
      }.get(str(task_type), public_demo("/demo/market/pattern-vintage-floral.webp"))
      result_images = [fallback]
    task_id = "PODI-" + secrets.token_hex(5)
    output_asset_ids: list[str] = []
    result_type = {
      "extract": "pattern",
      "variation": "variation",
      "image_edit": "processed",
    }.get(str(body.get("type")), "processed")
    for index, url in enumerate(result_images):
      asset = {
        "id": f"asset-{task_id}-{index + 1}",
        "type": result_type,
        "title": f"{body.get('optionLabel') or '图片处理'}结果 {index + 1}",
        "url": url,
        "thumbnailUrl": url,
        "source": body.get("optionLabel") or "图片批处理",
        "createdAt": now_label(),
        "selected": False,
        "favorite": False,
        "visibility": "private",
        "licenseMode": "private",
        "licenseSource": "created",
        "usedInProducts": 0,
        "batchId": task_id,
      }
      prepare_asset_for_storage(user_id, asset, reason="process-immediate-result")
      enrich_asset_dimensions(asset)
      ensure_bucket("assets", user_id).insert(0, asset)
      output_asset_ids.append(asset["id"])
    task_status = "completed" if result_images else ("pending" if real_business_run else "processing")
    completed_at = now_label() if result_images else None
    queue_items = []
    if real_business_run and not result_images:
      queue_items = [
        {
          "index": image_index * candidate_count + variant_index,
          "inputIndex": image_index,
          "variantIndex": variant_index,
          "variantCount": candidate_count,
          "inputImage": image_url,
          "requestPayload": params.get("requestPayloadTemplate") if task_type == "image_edit" else None,
          "status": "queued",
          "runId": None,
          "attempts": 0,
          "resultImages": [],
          "errorMessage": None,
          "submittedAt": None,
          "completedAt": None,
        }
        for image_index, image_url in enumerate(input_images)
        for variant_index in range(candidate_count)
      ]
      params = {
        **params,
        "candidateCount": candidate_count,
        "expectedOutputCount": len(queue_items),
        "queueItems": queue_items,
        "businessRunIds": [],
        "queuePolicy": {
          "maxInFlight": CLIENT_QUEUE_MAX_IN_FLIGHT,
          "dispatchPerTick": CLIENT_QUEUE_DISPATCH_PER_TICK,
          "maxAttempts": CLIENT_QUEUE_MAX_ATTEMPTS,
          "vipPriority": params.get("vipPriority") or "normal",
        },
      }
    task = {
      "id": task_id,
      "type": task_type,
      "status": task_status,
      "inputAssetIds": body.get("inputAssetIds") or [],
      "outputAssetIds": output_asset_ids,
      "createdAt": now_label(),
      "completedAt": completed_at,
      "abilityTitle": body.get("abilityTitle") or body.get("optionLabel") or "图片批处理",
      "outputLabel": body.get("outputLabel") or "处理结果",
      "inputCount": len(queue_items) if queue_items else len(input_images or body.get("inputAssetIds") or []),
      "sourceInputCount": len(input_images or body.get("inputAssetIds") or []),
      "resultCount": len(result_images),
      "optionLabel": body.get("optionLabel"),
      "sizeLabel": body.get("sizeLabel"),
      "resultType": result_type,
      "inputImages": input_images,
      "resultImages": result_images,
      "submitStatus": "提交成功",
      "callbackStatus": "结果已入库" if result_images else ("已进入生成队列" if real_business_run else "等待生成结果"),
      "finalStatus": "completed" if result_images else ("queued" if real_business_run else "processing"),
      "params": params,
      "costCredits": cost_credits,
    }
    ensure_bucket("tasks", user_id).insert(0, task)
    save_state(STATE)
    self._json({**task, "wallet": ensure_wallet(user_id)})

  def _handle_advance_process_task(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    task_id = str(body.get("taskId") or body.get("id") or "")
    tasks = ensure_bucket("tasks", user_id)
    task = next((item for item in tasks if item.get("id") == task_id), None)
    if not task:
      status, payload = json_error("CLIENT_TASK_NOT_FOUND", "图片处理任务不存在。", 404)
      self._json(payload, status)
      return
    changed_before_advance = normalize_process_task_status_copy(tasks)
    if expire_stale_process_tasks(tasks):
      changed_before_advance = True
    if reset_stale_dispatching_process_items(tasks):
      changed_before_advance = True
    if changed_before_advance:
      if task.get("status") == "failed":
        refund_process_task_credits(user_id, task, reason=str(task.get("errorCode") or "process_task_failed"))
      save_state(STATE)
      if task.get("status") in {"completed", "failed"}:
        self._json(task)
        return
    if task.get("status") in {"completed", "failed"}:
      if task.get("status") == "failed" and refund_process_task_credits(user_id, task, reason=str(task.get("errorCode") or "process_task_failed")):
        save_state(STATE)
      self._json(task)
      return

    params = task.get("params") if isinstance(task.get("params"), dict) else {}
    if not params.get("realBusinessRun"):
      self._json(task)
      return

    items = task_queue_items(task)
    business_key = str(params.get("businessKey") or "")
    endpoint = str(BUSINESS_ENDPOINT_BY_KEY.get(business_key) or "")
    if not endpoint:
      task["status"] = "failed"
      task["completedAt"] = now_label()
      task["errorCode"] = "CLIENT_BUSINESS_ENDPOINT_MISSING"
      task["errorMessage"] = "当前图片处理能力缺少业务接口配置。"
      task["finalStatus"] = "failed"
      task["callbackStatus"] = "业务接口未配置"
      refund_process_task_credits(user_id, task, reason="business_endpoint_missing")
      save_state(STATE)
      self._json(task)
      return

    advance_lock_key = f"{user_id}:{task_id}"
    advance_lock_token = time.monotonic()
    with STATE_LOCK:
      previous_lock = PROCESS_TASK_ADVANCE_LOCKS.get(advance_lock_key)
      if previous_lock and advance_lock_token - previous_lock < PROCESS_TASK_ADVANCE_LOCK_SECONDS:
        self._json(task)
        return
      PROCESS_TASK_ADVANCE_LOCKS[advance_lock_key] = advance_lock_token

    # 1. Refresh in-flight runs.
    for item in items:
      if item.get("status") not in {"submitted", "running"} or not item.get("runId"):
        continue
      payload = proxy_midplatform("/api/business/runs/get", {"runId": item["runId"], "detail": "full"}, timeout=15.0)
      if payload is None:
        item["status"] = "running"
        item["runStatus"] = "query_retry"
        item["errorMessage"] = "暂时查不到生成进度，下一轮会继续查询。"
        continue
      status_text = read_payload_status(payload)
      error_text = read_payload_error(payload)
      image_urls = collect_urls(payload.get("imageUrls") or payload.get("images") or payload.get("resultPayload") or payload.get("result"))
      if image_urls:
        item["status"] = "completed"
        item["runStatus"] = "completed"
        item["resultImages"] = image_urls
        item["completedAt"] = now_label()
        item["errorMessage"] = None
      elif status_text in {"succeeded", "success", "completed", "done"}:
        item["status"] = "failed"
        item["resultImages"] = []
        item["completedAt"] = now_label()
        item["errorMessage"] = "图片服务显示已完成，但没有返回可展示的结果图，请重新生成。"
      elif status_text in {"failed", "error"} or error_text:
        if is_busy_error(error_text) and int(item.get("attempts") or 0) < CLIENT_QUEUE_MAX_ATTEMPTS:
          failed_run_id = payload.get("runId") or payload.get("id") or item.get("runId")
          item["status"] = "queued"
          item["runId"] = None
          if failed_run_id:
            item.setdefault("failedRunIds", []).append(failed_run_id)
          item["errorMessage"] = "图片生成服务繁忙，已重新排队等待。"
          item["retryAt"] = now_label()
        else:
          item["status"] = "failed"
          item["errorMessage"] = error_text or "图片生成失败。"
          item["completedAt"] = now_label()
      else:
        item["status"] = "running"
        item["runStatus"] = status_text or item.get("runStatus") or "running"

    # 2. Dispatch a small number of queued images to mid-platform.
    in_flight = sum(1 for item in items if item.get("status") in {"dispatching", "submitted", "running"})
    available_slots = max(0, CLIENT_QUEUE_MAX_IN_FLIGHT - in_flight)
    dispatch_limit = min(CLIENT_QUEUE_DISPATCH_PER_TICK, available_slots)
    dispatched = 0
    for item in items:
      if dispatched >= dispatch_limit:
        break
      if item.get("status") != "queued":
        continue
      dispatch_token = "dispatch-" + secrets.token_hex(8)
      request_payload: dict[str, Any] | None = None
      with STATE_LOCK:
        current_items = task_queue_items(task)
        current_item = next((candidate for candidate in current_items if candidate.get("index") == item.get("index")), None)
        if not current_item or current_item.get("status") != "queued":
          items = current_items
          continue
        attempts = int(current_item.get("attempts") or 0)
        if attempts >= CLIENT_QUEUE_MAX_ATTEMPTS:
          current_item["status"] = "failed"
          current_item["errorMessage"] = "超过业务侧重试次数，请稍后重新提交。"
          current_item["completedAt"] = now_label()
          params["queueItems"] = current_items
          task["params"] = params
          save_state(STATE)
          items = current_items
          continue
        request_payload = dict(current_item.get("requestPayload") or params.get("requestPayloadTemplate") or {})
        if business_key == "fission":
          request_payload["outputCount"] = 1
          request_payload["candidateIndex"] = int(current_item.get("variantIndex") or 0) + 1
          request_payload["candidateCount"] = int(current_item.get("variantCount") or params.get("candidateCount") or 1)
          request_payload.setdefault("seed", secrets.randbelow(2_000_000_000))
          request_inputs = request_payload.get("inputs") if isinstance(request_payload.get("inputs"), dict) else {}
          request_inputs.update({
            "candidateIndex": request_payload["candidateIndex"],
            "candidateCount": request_payload["candidateCount"],
          })
          request_payload["inputs"] = request_inputs
        base_request_id = request_payload.get("requestId") or f"client-{business_key}-{task.get('id')}-{current_item.get('index')}"
        request_payload.update({
          "imageUrl": request_payload.get("imageUrl") or current_item.get("inputImage"),
          "source": request_payload.get("source") or "podi-client-web",
          "channel": request_payload.get("channel") or "client-web",
          "traceId": request_payload.get("traceId") or f"client-{business_key}-{user_id}-{task.get('id')}-{current_item.get('index')}",
          "requestId": f"{base_request_id}-{attempts + 1}",
        })
        try:
          model_input_rewrites: list[dict[str, str]] = []
          request_payload = normalize_model_input_urls(request_payload, user_id=user_id, rewrites=model_input_rewrites)
          if model_input_rewrites:
            current_item["inputImage"] = request_payload.get("imageUrl") or current_item.get("inputImage")
            current_item.setdefault("modelInputRewrites", []).extend(model_input_rewrites)
            request_payload.setdefault("metadata", {})
            if isinstance(request_payload["metadata"], dict):
              request_payload["metadata"]["modelInputRewrites"] = model_input_rewrites
        except Exception as exc:  # noqa: BLE001 - keep client task readable
          current_item["status"] = "failed"
          current_item["dispatchToken"] = None
          current_item["dispatchStartedAt"] = None
          current_item["errorMessage"] = f"本地图片转云端失败：{exc}"
          current_item["completedAt"] = now_label()
          params["queueItems"] = current_items
          task["params"] = params
          save_state(STATE)
          items = current_items
          continue
        current_item["status"] = "dispatching"
        current_item["dispatchToken"] = dispatch_token
        current_item["dispatchStartedAt"] = now_label()
        current_item["errorMessage"] = "正在提交图片生成请求。"
        params["queueItems"] = current_items
        task["params"] = params
        save_state(STATE)
        items = current_items
      payload = proxy_midplatform(endpoint, request_payload, timeout=20.0)
      with STATE_LOCK:
        current_items = task_queue_items(task)
        current_item = next((candidate for candidate in current_items if candidate.get("dispatchToken") == dispatch_token), None)
        if not current_item:
          items = current_items
          continue
        attempts = int(current_item.get("attempts") or 0)
        if payload is None:
          current_item["status"] = "queued"
          current_item["dispatchToken"] = None
          current_item["dispatchStartedAt"] = None
          current_item["errorMessage"] = "暂时连接不上图片生成服务，继续排队等待。"
          current_item["retryAt"] = now_label()
          params["queueItems"] = current_items
          task["params"] = params
          save_state(STATE)
          items = current_items
          break
        error_text = read_payload_error(payload)
        image_urls = collect_urls(payload.get("imageUrls") or payload.get("images") or payload.get("resultPayload") or payload.get("result"))
        run_id = read_run_id(payload)
        current_item["attempts"] = attempts + 1
        current_item["dispatchToken"] = None
        current_item["dispatchStartedAt"] = None
        if image_urls:
          current_item["status"] = "completed"
          current_item["runStatus"] = "completed"
          current_item["resultImages"] = image_urls
          current_item["completedAt"] = now_label()
          current_item["errorMessage"] = None
          dispatched += 1
        elif run_id:
          current_item["status"] = "running"
          current_item["runId"] = run_id
          current_item["submittedAt"] = now_label()
          current_item["errorMessage"] = None
          dispatched += 1
        elif is_busy_error(error_text):
          current_item["status"] = "queued"
          current_item["errorMessage"] = "图片生成服务繁忙，继续排队等待。"
          current_item["retryAt"] = now_label()
          params["queueItems"] = current_items
          task["params"] = params
          save_state(STATE)
          items = current_items
          break
        else:
          current_item["status"] = "failed"
          current_item["errorMessage"] = error_text or "提交图片生成失败。"
          current_item["completedAt"] = now_label()
          dispatched += 1
        params["queueItems"] = current_items
        task["params"] = params
        save_state(STATE)
        items = current_items

    normalize_process_task_queue_items([task])
    business_run_ids = [str(item.get("runId")) for item in items if item.get("runId")]
    result_images = [
      url
      for item in items
      for url in (item.get("resultImages") or [])
      if is_probable_image_url(url)
    ]
    failed_items = [item for item in items if item.get("status") == "failed"]
    queued_items = [item for item in items if item.get("status") == "queued"]
    running_items = [item for item in items if item.get("status") in {"dispatching", "submitted", "running"}]
    completed_items = [
      item
      for item in items
      if item.get("status") == "completed" and any(is_probable_image_url(url) for url in (item.get("resultImages") or []))
    ]

    params["queueItems"] = items
    params["businessRunIds"] = business_run_ids
    task["params"] = params
    task["resultImages"] = result_images
    task["resultCount"] = len(result_images)
    task["inputCount"] = len(items)

    if len(completed_items) == len(items) and not failed_items:
      task["status"] = "completed"
      task["completedAt"] = task.get("completedAt") or now_label()
      task["finalStatus"] = "completed"
      task["callbackStatus"] = "结果已入库"
      task["errorMessage"] = None
      materialize_task_assets(user_id, task)
    elif failed_items and not queued_items and not running_items:
      task["status"] = "failed"
      task["completedAt"] = now_label()
      task["finalStatus"] = "failed"
      task["callbackStatus"] = "部分图片处理失败"
      task["errorCode"] = "CLIENT_BATCH_FAILED"
      task["errorMessage"] = failed_items[0].get("errorMessage") or "图片处理失败。"
      refund_process_task_credits(user_id, task, reason="process_task_failed")
    elif running_items:
      task["status"] = "processing"
      task["finalStatus"] = "running"
      task["callbackStatus"] = f"正在生成 {len(running_items)} 张，等待 {len(queued_items)} 张"
    else:
      task["status"] = "pending"
      task["finalStatus"] = "queued"
      task["callbackStatus"] = f"等待生成 {len(queued_items)} 张"

    task["queueSummary"] = {
      "queued": len(queued_items),
      "running": len(running_items),
      "completed": len(completed_items),
      "failed": len(failed_items),
      "maxInFlight": CLIENT_QUEUE_MAX_IN_FLIGHT,
      "dispatchPerTick": CLIENT_QUEUE_DISPATCH_PER_TICK,
    }
    with STATE_LOCK:
      if PROCESS_TASK_ADVANCE_LOCKS.get(advance_lock_key) == advance_lock_token:
        PROCESS_TASK_ADVANCE_LOCKS.pop(advance_lock_key, None)
    save_state(STATE)
    self._json(task)

  def _handle_update_process_task(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    task_id = str(body.get("taskId") or body.get("id") or "")
    patch = body.get("patch") if isinstance(body.get("patch"), dict) else {}
    tasks = ensure_bucket("tasks", user_id)
    task = next((item for item in tasks if item.get("id") == task_id), None)
    if not task:
      status, payload = json_error("CLIENT_TASK_NOT_FOUND", "图片处理任务不存在。", 404)
      self._json(payload, status)
      return

    previous_status = str(task.get("status") or "")
    incoming_status = str(patch.get("status") or "")
    if previous_status in {"completed", "failed"} and incoming_status in {"pending", "processing"}:
      # 已有最终态的任务不能被轮询中的临时状态覆盖，避免刷新/返回后倒退。
      self._json(task)
      return

    allowed_fields = {
      "status",
      "completedAt",
      "abilityTitle",
      "outputLabel",
      "inputCount",
      "resultCount",
      "optionLabel",
      "sizeLabel",
      "resultType",
      "inputImages",
      "resultImages",
      "submitStatus",
      "callbackStatus",
      "finalStatus",
      "errorCode",
      "errorMessage",
      "params",
    }
    for key in allowed_fields:
      if key in patch:
        task[key] = patch[key]

    result_images = [url for url in (task.get("resultImages") or []) if is_probable_image_url(url)]
    task["resultImages"] = result_images
    if task.get("status") == "completed" and result_images:
      asset_type = str(task.get("resultType") or "processed")
      output_asset_ids: list[str] = list(task.get("outputAssetIds") or [])
      existing_asset_ids = {
        str(asset.get("id"))
        for asset in ensure_bucket("assets", user_id)
      }
      for index, url in enumerate(result_images):
        asset_id = output_asset_ids[index] if index < len(output_asset_ids) else f"asset-{task_id}-{index + 1}"
        if asset_id not in output_asset_ids:
          output_asset_ids.append(asset_id)
        if asset_id in existing_asset_ids:
          continue
        asset = {
          "id": asset_id,
          "type": asset_type,
          "title": f"{task.get('abilityTitle') or task.get('optionLabel') or '图片处理'}结果 {index + 1}",
          "url": url,
          "thumbnailUrl": url,
          "source": task.get("abilityTitle") or task.get("optionLabel") or "图片处理",
          "createdAt": task.get("completedAt") or now_label(),
          "selected": False,
          "favorite": False,
          "visibility": "private",
          "batchId": task_id,
          "licenseMode": "private",
          "licenseSource": "created",
          "usedInProducts": 0,
        }
        prepare_asset_for_storage(user_id, asset, reason="process-result-patch")
        ensure_bucket("assets", user_id).insert(0, asset)
      task["outputAssetIds"] = output_asset_ids
      task["resultCount"] = len(result_images)
      task["completedAt"] = task.get("completedAt") or now_label()
      task["callbackStatus"] = task.get("callbackStatus") or "结果已入库"
      task["finalStatus"] = task.get("finalStatus") or "completed"
    elif task.get("status") == "failed":
      refund_process_task_credits(user_id, task, reason=str(task.get("errorCode") or "process_task_failed"))

    save_state(STATE)
    self._json(task)

  def _handle_product_sample(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    product_id = str(body.get("productId") or "cup-10395")
    if product_template_id(product_id) in DISCONTINUED_PRODUCT_TEMPLATE_IDS:
      status, payload = json_error("CLIENT_PRODUCT_DISCONTINUED", "该商品已下架，暂不支持试做。", 409)
      self._json(payload, status)
      return
    product_name = str(body.get("productName") or product_id)
    asset_id = str(body.get("assetId") or "")
    source_asset = find_asset(user_id, asset_id)
    source_asset_title = str(body.get("sourceAssetTitle") or (source_asset.get("title") if source_asset else "") or "素材")
    source_asset_url = str(body.get("sourceAssetUrl") or (source_asset.get("url") if source_asset else "") or "")
    design_config = body.get("designConfig") if isinstance(body.get("designConfig"), dict) else {}
    preview_url = source_asset_url or catalog_product_render_url(product_id, optional_text(body.get("sizeLabel")))
    if not preview_url:
      status, payload = json_error("CLIENT_PRODUCT_RENDER_UNAVAILABLE", "当前商品缺少可展示的模板图，请先补齐模型渲染图。", 409)
      self._json(payload, status)
      return
    asset = {
      "id": "sample-" + secrets.token_hex(6),
      "type": "product_preview",
      "title": f"{product_name} · 产品预览",
      "url": preview_url,
      "thumbnailUrl": preview_url,
      "source": "产品试做预览",
      "createdAt": now_label(),
      "selected": False,
      "favorite": False,
      "visibility": "private",
      "licenseMode": "private",
      "licenseSource": "product_snapshot",
      "usedInProducts": 1,
      "metadata": {
        "productId": product_id,
        "productName": product_name,
        "sourceAssetId": asset_id,
        "sourceAssetTitle": source_asset_title,
        "sourceAssetUrl": source_asset_url or None,
        "surfaceName": body.get("surfaceName"),
        "sizeLabel": body.get("sizeLabel"),
        "designConfig": design_config,
        "previewKind": "design_artwork",
      },
    }
    prepare_asset_for_storage(user_id, asset, reason="product-sample")
    ensure_bucket("assets", user_id).insert(0, asset)
    save_state(STATE)
    self._json(asset)

  def _handle_create_order(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    request_id = str(body.get("clientRequestId") or "")
    orders = ensure_bucket("orders", user_id)
    if request_id:
      for order in orders:
        if order.get("metadata", {}).get("clientRequestId") == request_id:
          self._json(order)
          return
    product_id = str(body.get("productId") or "cup-10395")
    product_name = str(body.get("productName") or product_id or "杯子试做")
    template_id = product_template_id(product_id)
    if template_id in DISCONTINUED_PRODUCT_TEMPLATE_IDS:
      status, payload = json_error("CLIENT_PRODUCT_DISCONTINUED", "该商品已下架，暂不支持下单。", 409)
      self._json(payload, status)
      return
    config = commerce_config()
    sale_price_cents = optional_int((config.get("productPrices") or {}).get(template_id))
    if sale_price_cents is None or sale_price_cents <= 0:
      status, payload = json_error("CLIENT_PRODUCT_SALE_PRICE_NOT_CONFIGURED", "该商品售价尚未由运营设置，暂不能提交订单。", 409)
      self._json(payload, status)
      return
    sale_price_points = max(1, int(round(sale_price_cents / 100)))
    preview_asset_id = str(body.get("assetId") or "")
    asset = find_asset(user_id, preview_asset_id)
    asset_metadata = asset.get("metadata") if isinstance((asset or {}).get("metadata"), dict) else {}
    source_asset_id = str(body.get("sourceAssetId") or asset_metadata.get("sourceAssetId") or "")
    source_asset = find_asset(user_id, source_asset_id) if source_asset_id else None
    source_asset_url = str(
      body.get("sourceAssetUrl")
      or asset_metadata.get("sourceAssetUrl")
      or (source_asset.get("url") if source_asset else "")
      or ""
    )
    source_asset_title = str(
      body.get("sourceAssetTitle")
      or asset_metadata.get("sourceAssetTitle")
      or (source_asset.get("title") if source_asset else "")
      or (asset.get("title") if asset else "")
      or body.get("assetId")
      or "产品预览图"
    )
    shipping = normalize_shipping_address(body.get("shippingAddress"))
    if not shipping or not shipping.get("recipientName") or not shipping.get("address"):
      status, payload = json_error("CLIENT_SHIPPING_ADDRESS_REQUIRED", "请先填写收件人和详细地址。", 422)
      self._json(payload, status)
      return
    quantity = max(1, optional_int(body.get("quantity")) or 1)
    checkout_group_id = optional_text(body.get("checkoutGroupId")) or request_id or f"checkout-{secrets.token_hex(6)}"
    shipping_fee_cents = 0
    quantity_discount_rate = 0.88 if quantity >= 50 else 0.94 if quantity >= 10 else 1.0
    subtotal_points = sale_price_points * quantity
    product_payable_points = int(round(subtotal_points * quantity_discount_rate))
    shipping_fee_points = max(0, int(round(shipping_fee_cents / 100)))
    wallet = ensure_wallet(user_id)
    refresh_wallet_coupon_count(wallet)
    selected_coupon: dict[str, Any] | None = None
    coupon_discount_points = 0
    if body.get("useProductCoupon"):
      detailed_coupons = available_wallet_coupons(wallet, product_id)
      if detailed_coupons:
        selected_coupon = detailed_coupons[0]
        coupon_discount_points = max(1, optional_int(selected_coupon.get("valuePoints")) or 50)
      elif max(0, optional_int(wallet.get("legacyProductCouponCount")) or 0) > 0:
        coupon_discount_points = 50
      else:
        status, payload = json_error("CLIENT_PRODUCT_COUPON_UNAVAILABLE", "当前没有适用于该商品的产品抵扣券。", 409)
        self._json(payload, status)
        return
    coupon_discount_points = min(coupon_discount_points, product_payable_points)
    payable_points = max(0, product_payable_points - coupon_discount_points)
    subtotal_cents = subtotal_points * 100
    product_payable_cents = product_payable_points * 100
    payable_cents = payable_points * 100
    order = {
      "id": "order-" + secrets.token_hex(5),
      "product": product_name,
      "asset": source_asset_title,
      "quantity": f"{quantity} 件",
      "status": "待支付",
      "eta": "完成平台支付后进入运营核对",
      "image": catalog_product_render_url(product_id, optional_text(asset_metadata.get("sizeLabel"))) or (asset or {}).get("url"),
      "imageSource": "catalog_render",
      "createdAt": now_label(),
      "shippingSummary": f"{shipping.get('country', '')} {shipping.get('state', '')} {shipping.get('city', '')}".strip(),
      "discount": f"产品券抵扣 {coupon_discount_points} 积分" if coupon_discount_points else "未使用产品券",
      "usedProductCoupon": bool(body.get("useProductCoupon")),
      "supplierOrderId": None,
      "logisticsNo": None,
      "supplierStatusName": None,
      "supplierSyncedAt": None,
      "metadata": {
        "clientRequestId": request_id or None,
        "checkoutGroupId": checkout_group_id,
        "productId": product_id,
        "productName": product_name,
        "assetId": preview_asset_id or None,
        "previewAssetId": preview_asset_id or None,
        "previewAssetUrl": (asset or {}).get("url"),
        "sourceAssetId": source_asset_id or None,
        "sourceAssetTitle": source_asset_title,
        "sourceAssetUrl": source_asset_url or None,
        "designConfig": asset_metadata.get("designConfig") or {},
        "surfaceName": asset_metadata.get("surfaceName"),
        "sizeLabel": asset_metadata.get("sizeLabel"),
        "shippingAddress": shipping,
        "fulfillmentMode": "ops_confirmed_supplier",
        "shippingMethod": {"id": "supplier", "label": "蜂鸟后台选择"},
        "paymentMethod": None,
        "payment": {
          "status": "unpaid",
          "unitPriceCents": sale_price_cents,
          "unitPricePoints": sale_price_points,
          "quantity": quantity,
          "subtotalCents": subtotal_cents,
          "subtotalPoints": subtotal_points,
          "quantityDiscountRate": quantity_discount_rate,
          "productPayableCents": product_payable_cents,
          "productPayablePoints": product_payable_points,
          "shippingFeeCents": shipping_fee_cents,
          "shippingFeePoints": shipping_fee_points,
          "couponDiscountPoints": coupon_discount_points,
          "shippingMethod": "supplier",
          "payableCents": payable_cents,
          "payablePoints": payable_points,
          "currency": "POINT",
        },
        "couponId": selected_coupon.get("id") if selected_coupon else None,
      },
    }
    orders.insert(0, order)
    save_state(STATE)
    self._json(self._order_snapshot(user_id, order))

  def _handle_pay_order(self, order_id: str, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    for order in ensure_bucket("orders", user_id):
      if order.get("id") == order_id:
        metadata = order.setdefault("metadata", {})
        payment = metadata.get("payment") if isinstance(metadata.get("payment"), dict) else {}
        wallet = ensure_wallet(user_id)
        refresh_wallet_coupon_count(wallet)
        payable_points = max(0, optional_int(payment.get("payablePoints")) or int(round((optional_int(payment.get("payableCents")) or 0) / 100)))
        if payment.get("status") != "paid":
          available_points = max(0, optional_int(wallet.get("aiCredits")) or 0)
          if available_points < payable_points:
            status, payload = json_error(
              "CLIENT_POINTS_INSUFFICIENT",
              f"积分不足：当前 {available_points} 积分，本次需要 {payable_points} 积分。",
              409,
            )
            self._json(payload, status)
            return
          if order.get("usedProductCoupon") and not metadata.get("productCouponSettled"):
            coupon_id = optional_text(metadata.get("couponId"))
            coupon = next(
              (item for item in wallet.setdefault("coupons", []) if isinstance(item, dict) and item.get("id") == coupon_id),
              None,
            )
            if coupon:
              if not coupon_is_available(coupon, metadata.get("productId")):
                status, payload = json_error("CLIENT_PRODUCT_COUPON_UNAVAILABLE", "所选产品券已使用、过期或不适用于该商品。", 409)
                self._json(payload, status)
                return
              coupon["status"] = "used"
              coupon["usedAt"] = now_label()
              coupon["orderId"] = order_id
            else:
              wallet["legacyProductCouponCount"] = max(0, optional_int(wallet.get("legacyProductCouponCount")) or 0) - 1
            metadata["productCouponSettled"] = True
          wallet["aiCredits"] = available_points - payable_points
          wallet["latestWalletEvent"] = f"订单 {order_id} 已支付 {payable_points} 积分。"
          wallet["updatedAt"] = now_label()
          wallet["updatedBy"] = "order-payment"
          wallet_ledger_entry(wallet, "产品订单支付", -payable_points, str(order.get("product") or order_id))
          refresh_wallet_coupon_count(wallet)
          payment["status"] = "paid"
          payment["paidPoints"] = payable_points
          payment["paidAt"] = now_label()
          metadata["payment"] = payment
          metadata["paymentMethod"] = body.get("method") or "wallet"
          order["status"] = "待确认"
          order["eta"] = "积分已支付，等待运营核对后推送蜂鸟"
          metadata["supplierSubmission"] = {"status": "pending_ops_review", "createdAt": now_label()}
        save_state(STATE)
        self._json({**self._order_snapshot(user_id, order), "wallet": dict(wallet)})
        return
    status, payload = json_error("CLIENT_ORDER_NOT_FOUND", "订单不存在。", 404)
    self._json(payload, status)

  def _handle_publish_application(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    item = {
      "id": "pub-" + secrets.token_hex(5),
      "kind": body.get("kind") or "图片作品",
      "title": body.get("title") or "未命名作品",
      "tags": body.get("tags") or "",
      "usage": body.get("usage") or "",
      "image": body.get("image") or public_demo("/demo/market/pattern-vintage-floral.webp"),
      "licenseMode": body.get("licenseMode") or "free_reuse",
      "pricePoints": max(0, optional_int(body.get("pricePoints")) or 0),
      "submittedAt": now_label(),
      "status": "pending",
      "reviewNote": None,
    }
    ensure_bucket("publishApplications", user_id).insert(0, item)
    save_state(STATE)
    self._json(item)

  def _handle_create_complaint(self, body: dict[str, Any]) -> None:
    user_id = str(body.get("userId") or "demo-user")
    work_id = optional_text(body.get("workId"))
    contact = optional_text(body.get("contact"))
    evidence = optional_text(body.get("evidence"))
    if not work_id or not contact or not evidence:
      status, payload = json_error("CLIENT_COMPLAINT_EVIDENCE_REQUIRED", "请提供作品、联系方式和侵权证据。", 422)
      self._json(payload, status)
      return
    item = {
      "id": "complaint-" + secrets.token_hex(5),
      "workId": work_id,
      "workTitle": body.get("workTitle") or "未命名作品",
      "workKind": body.get("workKind") or "图片作品",
      "author": body.get("author"),
      "image": body.get("image"),
      "type": body.get("type") or "版权侵权",
      "contact": contact,
      "evidence": evidence,
      "detail": body.get("detail") or "",
      "status": "pending",
      "submittedAt": now_label(),
      "opsNote": "待运营人工联系双方核验。",
    }
    ensure_bucket("complaints", user_id).insert(0, item)
    save_state(STATE)
    self._json(item)


def main() -> None:
  parser = argparse.ArgumentParser(description="Run local PODI business API")
  parser.add_argument("--host", default=os.getenv("PODI_BUSINESS_HOST", "127.0.0.1"))
  parser.add_argument("--port", type=int, default=int(os.getenv("PODI_BUSINESS_PORT", "8240")))
  args = parser.parse_args()
  server = ThreadingHTTPServer((args.host, args.port), Handler)
  print(f"PODI business API listening on http://{args.host}:{args.port}")
  print(f"Client origin: {CLIENT_ORIGIN}")
  print(f"Mid-platform proxy: {MIDPLATFORM_BASE or 'disabled'}")
  server.serve_forever()


if __name__ == "__main__":
  main()
