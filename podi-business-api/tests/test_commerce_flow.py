import importlib.util
from pathlib import Path
import unittest


SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"
SPEC = importlib.util.spec_from_file_location("podi_business_server", SERVER_PATH)
assert SPEC and SPEC.loader
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class CommerceFlowTests(unittest.TestCase):
  def setUp(self):
    self.original_state = server.STATE
    self.original_place_order = server.humcustom_place_order
    self.original_prepare_asset = server.prepare_asset_for_storage
    self.original_save_state = server.save_state
    self.original_build_goods = server.build_supply_chain_goods
    self.original_analyze_visual = server.analyze_agent_visual_context
    self.original_proxy_midplatform = server.proxy_midplatform
    self.original_get_ability_task = server.get_midplatform_ability_task
    self.original_text2image_available = server.AGENT_TEXT2IMAGE_AVAILABLE
    self.original_text2image_ability_id = server.AGENT_TEXT2IMAGE_ABILITY_ID
    server.STATE = server.default_state()
    server.save_state = lambda _state: None

  def tearDown(self):
    server.STATE = self.original_state
    server.humcustom_place_order = self.original_place_order
    server.prepare_asset_for_storage = self.original_prepare_asset
    server.save_state = self.original_save_state
    server.build_supply_chain_goods = self.original_build_goods
    server.analyze_agent_visual_context = self.original_analyze_visual
    server.proxy_midplatform = self.original_proxy_midplatform
    server.get_midplatform_ability_task = self.original_get_ability_task
    server.AGENT_TEXT2IMAGE_AVAILABLE = self.original_text2image_available
    server.AGENT_TEXT2IMAGE_ABILITY_ID = self.original_text2image_ability_id

  def test_coupon_count_uses_available_detailed_and_legacy_coupons(self):
    wallet = {
      "productCouponCount": 2,
      "coupons": [
        {"id": "active", "status": "available"},
        {"id": "used", "status": "used"},
      ],
    }

    self.assertEqual(server.refresh_wallet_coupon_count(wallet), 2)
    self.assertEqual(wallet["legacyProductCouponCount"], 1)

    wallet["coupons"][0]["status"] = "used"
    self.assertEqual(server.refresh_wallet_coupon_count(wallet), 1)

  def test_supplier_render_urls_ignore_non_render_payload_images(self):
    response = {
      "data": {
        "sourceImageUrl": "https://example.com/source.jpg",
        "effectImageUrl": "https://example.com/effect.jpg",
        "renderImages": ["https://example.com/render-2.png"],
      }
    }
    self.assertEqual(
      server.collect_supplier_render_urls(response),
      ["https://example.com/effect.jpg", "https://example.com/render-2.png"],
    )

  def test_supplier_submission_requires_a_paid_platform_order(self):
    self.assertFalse(server.order_is_paid({"metadata": {}}))
    self.assertFalse(server.order_is_paid({"metadata": {"payment": {"status": "unpaid"}}}))
    self.assertTrue(server.order_is_paid({"metadata": {"payment": {"status": "paid"}}}))

  def test_discontinued_mugs_are_not_in_public_pricing(self):
    self.assertNotIn("10341", {item["productId"] for item in server.product_pricing_snapshot()})
    self.assertNotIn("10342", {item["productId"] for item in server.product_pricing_snapshot()})

  def test_cn_supplier_payload_keeps_district(self):
    shipping = server.normalize_shipping_address({
      "country": "CN",
      "state": "江苏省",
      "city": "南京市",
      "district": "浦口区",
      "postalCode": "210000",
      "address": "测试路 1 号",
      "phoneNumber": "13800000000",
      "recipientName": "测试用户",
    })

    self.assertEqual(shipping["district"], "浦口区")
    self.assertEqual(server.supply_chain_shipping_fields(shipping)["shipDistrict"], "浦口区")

  def test_platform_payment_waits_for_ops_confirmation_before_supplier_submission(self):
    class CaptureHandler:
      def __init__(self):
        self.responses = []

      def _json(self, payload, _status=200):
        self.responses.append(payload)

      def _order_snapshot(self, _user_id, order):
        return dict(order)

    handler = CaptureHandler()
    server.commerce_config()["productPrices"] = {"10395": 5900}
    server.ensure_wallet("user-test")["aiCredits"] = 200
    server.humcustom_place_order = lambda _payload: self.fail("蜂鸟不能在平台支付前被调用")
    request = {
      "userId": "user-test",
      "productId": "cup-10395",
      "productName": "20oz 测试杯",
      "assetId": "asset-1",
      "quantity": 1,
      "shippingAddress": {
        "country": "CN", "state": "江苏省", "city": "南京市", "postalCode": "210000",
        "district": "浦口区", "address": "测试路 1 号", "phoneNumber": "13800000000", "recipientName": "测试用户",
      },
    }

    server.Handler._handle_create_order(handler, request)
    created = handler.responses[-1]
    self.assertEqual(created["status"], "待支付")
    self.assertNotIn("supplyChain", created["metadata"])

    server.Handler._handle_pay_order(handler, created["id"], {"userId": "user-test", "method": "mock"})
    paid = handler.responses[-1]
    self.assertEqual(paid["status"], "待确认")
    self.assertEqual(paid["metadata"]["payment"]["status"], "paid")
    self.assertNotIn("supplyChain", paid["metadata"])

  def test_confirmed_supplier_submission_persists_returned_render_asset(self):
    server.humcustom_place_order = lambda _payload: {
      "data": {
        "orderId": "FN-ORDER-1",
        "effectImageUrl": "https://example.com/fengniao-render.jpg",
      }
    }
    server.prepare_asset_for_storage = lambda _user_id, asset, **_kwargs: asset
    order = {
      "id": "order-test-1",
      "product": "20oz 测试杯",
      "metadata": {
        "shippingAddress": {
          "country": "CN",
          "state": "江苏省",
          "city": "南京市",
          "district": "浦口区",
          "postalCode": "210000",
          "address": "测试路 1 号",
          "phoneNumber": "13800000000",
          "recipientName": "测试用户",
        },
      },
    }
    server.build_supply_chain_goods = lambda *_args, **_kwargs: [{"templateNo": "10167", "num": 1}]

    server.submit_order_to_supply_chain("user-test", order, actor="ops:admin")

    self.assertEqual(order["status"], "制作中")
    self.assertEqual(order["supplierOrderId"], "FN-ORDER-1")
    self.assertEqual(order["metadata"]["supplierSync"], "submitted")
    self.assertEqual(order["metadata"]["supplyChain"]["submittedBy"], "ops:admin")
    self.assertEqual(order["image"], "https://example.com/fengniao-render.jpg")
    self.assertEqual(order["imageSource"], "supplier_render")
    assets = server.ensure_bucket("assets", "user-test")
    self.assertEqual(len(assets), 1)
    self.assertEqual(assets[0]["type"], "supplier_render")
    self.assertEqual(assets[0]["metadata"]["supplierSourceUrl"], "https://example.com/fengniao-render.jpg")

  def test_agent_preview_uses_design_artwork_until_supplier_render_is_returned(self):
    class CaptureHandler:
      def __init__(self):
        self.responses = []

      def _json(self, payload, _status=200):
        self.responses.append((payload, _status))

      def _find_design_agent_session(self, user_id, session_id):
        return next((item for item in server.ensure_bucket("designAgentSessions", user_id) if item["sessionId"] == session_id), None)

      def _agent_session_snapshot(self, session):
        return dict(session)

    user_id = "user-test"
    server.ensure_bucket("assets", user_id).append({
      "id": "generated-artwork",
      "title": "AI 生成花纹",
      "url": "https://example.com/generated-artwork.png",
      "thumbnailUrl": "https://example.com/generated-artwork.png",
    })
    server.ensure_bucket("designAgentSessions", user_id).append({
      "sessionId": "agent-session-1",
      "userId": user_id,
      "productId": "cup-10395",
      "productName": "20oz 测试杯",
      "resultAssetIds": ["generated-artwork"],
      "plans": [],
    })
    server.prepare_asset_for_storage = lambda _user_id, asset, **_kwargs: asset

    handler = CaptureHandler()
    server.Handler._handle_apply_design_agent_preview(handler, "agent-session-1", {"userId": user_id})

    payload, status = handler.responses[-1]
    self.assertEqual(status, 200)
    preview = payload["previewAsset"]
    self.assertEqual(preview["url"], "https://example.com/generated-artwork.png")
    self.assertEqual(preview["metadata"]["previewKind"], "design_artwork")
    self.assertTrue(preview["metadata"]["supplierRenderPending"])

  def test_quick_design_intake_returns_user_language_for_wrap_artwork(self):
    class CaptureHandler:
      def __init__(self):
        self.responses = []

      def _json(self, payload, _status=200):
        self.responses.append((payload, _status))

    server.ensure_bucket("assets", "user-test").append({
      "id": "asset-pattern",
      "url": "https://example.com/pattern.png",
      "thumbnailUrl": "https://example.com/pattern.png",
      "title": "花纹参考",
      "type": "pattern",
      "source": "测试",
    })
    server.analyze_agent_visual_context = lambda *_args, **_kwargs: {
      "provider": "test-vl",
      "model": "test-model",
      "imageType": "pattern_asset",
      "printable": True,
      "qualityRisk": "low",
      "recommendedIntent": "make_seamless_wrap",
      "recommendedSurfaceId": "front",
      "layoutMode": "wrap",
      "needsSeamless": True,
      "needsImage2": False,
      "needsUserConfirmation": True,
      "confidence": 0.96,
      "observations": ["图案适合环绕"],
      "risks": [],
      "questions": [],
    }

    handler = CaptureHandler()
    server.Handler._handle_create_product_design_intake(handler, {
      "userId": "user-test",
      "productId": "10395",
      "productName": "20oz 测试杯",
      "productContext": {
        "surfaces": [{"name": "front", "label": "正面", "width": 3378, "height": 1949, "dpi": 150}],
      },
      "sourceAssetIds": ["asset-pattern"],
      "message": "请根据这张图判断最适合的杯子设计方式。",
    })

    payload, status = handler.responses[-1]
    self.assertEqual(status, 200)
    self.assertEqual(payload["source"], "vl_design_intake")
    self.assertEqual(payload["recommendation"]["title"], "AI 适配杯身")
    self.assertEqual(payload["recommendation"]["actionLabel"], "按建议处理")
    self.assertEqual(payload["recommendation"]["suggestedMode"], "wrap")

  def test_prompt_only_agent_uses_governed_packy_image2_task(self):
    captured = {}

    def fake_proxy(path, payload, timeout=20.0):
      captured["path"] = path
      captured["payload"] = payload
      return {"id": "ability-task-123", "status": "queued"}

    server.proxy_midplatform = fake_proxy
    server.AGENT_TEXT2IMAGE_AVAILABLE = True
    server.AGENT_TEXT2IMAGE_ABILITY_ID = "packy_gpt_image_2_generate"

    result = server.submit_agent_text_to_image_task(
      session={"sessionId": "agent-1", "productId": "10385", "productName": "12oz 水瓶罐"},
      plan={"planId": "plan-1", "intent": "ai_recreate"},
      step={"stepId": "s2", "targetAbility": "image2_recreate"},
      prompt="设计一张西安兵马俑主题杯身平面图。",
      surface={"name": "front", "label": "正面", "width": 2717, "height": 1476, "dpi": 300},
      metadata={"source": "test"},
    )

    self.assertEqual(captured["path"], "/api/ability-tasks")
    self.assertEqual(captured["payload"]["abilityId"], "packy_gpt_image_2_generate")
    self.assertEqual(captured["payload"]["inputs"]["aspect_ratio"], "16:9")
    self.assertEqual(captured["payload"]["metadata"]["targetWidth"], 2717)
    self.assertEqual(captured["payload"]["metadata"]["productionCanvas"]["targetHeight"], 1476)
    self.assertEqual(captured["payload"]["metadata"]["productionCanvas"]["targetDpi"], 300)
    self.assertEqual(result["abilityTaskIds"], ["ability-task-123"])
    self.assertEqual(result["status"], "queued")

  def test_agent_image_edit_defaults_to_packy_and_hides_vendor_key_error(self):
    self.assertEqual(server.AGENT_IMAGE2_EDIT_ABILITY_ID, "packy_gpt_image_2_edit")
    self.assertIn("未扣除本次积分", server.friendly_agent_error("VENDOR_API_KEY_MISSING: openai key missing"))
    self.assertIn("生产文件校验", server.friendly_agent_error("PRODUCTION_CANVAS_NORMALIZATION_FAILED"))

  def test_prompt_only_request_never_routes_to_original_print_for_negative_text_instruction(self):
    server.AGENT_TEXT2IMAGE_AVAILABLE = True
    plan = server.build_design_agent_plan(
      "user-prompt-only",
      "agent-prompt-only",
      "为夏日文旅礼品设计一张野花与蝴蝶平面花纹，适合完整铺满杯身，不要文字和产品样机。",
      {"surfaces": [{"name": "front", "width": 2717, "height": 1476, "dpi": 150, "role": "wrap"}]},
      [],
      {"source": "prompt_only", "baseAssetRole": "prompt_only", "visionAnalysis": {"recommendedIntent": "ai_recreate", "confidence": 0.72}},
    )

    self.assertEqual(plan["intent"], "ai_recreate")
    self.assertEqual(plan["steps"][1]["targetAbility"], "image2_recreate")
    self.assertFalse(plan["layoutPlan"]["surfaceAssignments"][0]["needsSeamless"])
    self.assertFalse(plan["layoutPlan"]["postprocess"]["seamRiskCheck"])

  def test_vl_prompt_requires_structured_style_and_product_constraints(self):
    prompt = server.agent_vl_prompt(
      {
        "productName": "20oz 手柄杯",
        "sizeLabel": "20OZ",
        "material": "不锈钢",
        "colors": [{"code": "white", "label": "白色"}],
        "craftOptions": [{"name": "360度UV打印-光油"}],
        "surfaces": [{"name": "front", "label": "正面", "width": 3378, "height": 1949, "dpi": 150}],
      },
      "为西安文旅设计一款杯子",
    )

    self.assertIn("20oz 手柄杯", prompt)
    self.assertIn("不锈钢", prompt)
    self.assertIn("3378", prompt)
    self.assertIn("styleName", prompt)
    self.assertIn("plannedOperations", prompt)
    self.assertIn("生产事实只能来自商品与生产约束", prompt)
    self.assertIn("不得自行声称食品级", prompt)

  def test_image2_prompt_executes_confirmed_structured_design_brief(self):
    prompt = server.agent_image2_design_prompt(
      {
        "userId": "user-brief",
        "productId": "10395",
        "productName": "20oz 手柄杯",
        "messages": [{"role": "user", "type": "text", "content": "给我的猫做一款有艺术感的杯子"}],
        "productContext": {
          "surfaces": [{"name": "front", "label": "正面", "width": 3378, "height": 1949, "dpi": 150}],
        },
      },
      {
        "planId": "plan-brief",
        "intent": "ai_recreate",
        "summaryForUser": "制作一款猫咪主题杯身设计",
        "designBrief": {
          "title": "橘猫的午后花园",
          "styleName": "治愈系水彩插画",
          "palette": ["暖橙", "米白", "鼠尾草绿"],
          "composition": "猫咪居中，植物纹理向两侧自然延伸",
          "operations": [
            {"title": "重绘猫咪主体", "purpose": "保留五官特征"},
            {"title": "补充环绕背景", "purpose": "适配杯身比例"},
          ],
        },
        "layoutPlan": {"surfaceAssignments": [{"surfaceId": "front"}]},
      },
      {"stepId": "s2", "title": "AI 重绘适配"},
      0,
      1,
    )

    self.assertIn("严格执行用户已经确认的设计方案", prompt)
    self.assertIn("橘猫的午后花园", prompt)
    self.assertIn("治愈系水彩插画", prompt)
    self.assertIn("暖橙、米白、鼠尾草绿", prompt)
    self.assertIn("重绘猫咪主体；补充环绕背景", prompt)

  def test_agent_plan_exposes_free_planning_and_structured_design_brief(self):
    server.AGENT_TEXT2IMAGE_AVAILABLE = True
    plan = server.build_design_agent_plan(
      "user-brief",
      "agent-brief",
      "给年轻游客设计一款西安文旅杯，现代但不要俗气",
      {
        "productName": "20oz 手柄杯",
        "sizeLabel": "20OZ",
        "material": "不锈钢",
        "surfaces": [{"name": "front", "label": "正面", "width": 3378, "height": 1949, "dpi": 150}],
      },
      [],
      {
        "source": "prompt_only",
        "baseAssetRole": "prompt_only",
        "visionAnalysis": {
          "recommendedIntent": "ai_recreate",
          "confidence": 0.91,
          "designConcept": "长安新印象",
          "audience": "来西安旅行的年轻人",
          "occasion": "旅行纪念与伴手礼",
          "styleName": "新中式版画",
          "styleRationale": "用克制线条表现城墙与瓦当。",
          "palette": ["朱砂红", "城墙灰", "米白"],
          "composition": "城墙作为连续背景，局部保留印章式主体。",
          "materialNotes": "为不锈钢白底保留高对比轮廓。",
          "plannedOperations": [
            {"title": "提炼城市符号", "purpose": "从城墙与瓦当中确定主视觉"},
            {"title": "生成杯身图案", "purpose": "形成适合正面设计面的平面稿"},
          ],
        },
      },
    )

    brief = plan["designBrief"]
    self.assertEqual(brief["planningCredits"], 0)
    self.assertEqual(brief["generationCredits"], 5)
    self.assertEqual(brief["styleName"], "新中式版画")
    self.assertEqual(brief["productFit"]["width"], 3378)
    self.assertEqual(len(brief["operations"]), 2)

  def test_failed_agent_execution_closes_running_state_for_retry(self):
    plan = {
      "planId": "plan-retry",
      "status": "running",
      "needsUserConfirmation": False,
      "steps": [{"stepId": "s2", "targetAbility": "image2_recreate", "status": "running"}],
      "execution": {"status": "running", "businessRunIds": ["run-1"]},
    }
    session = {
      "sessionId": "agent-retry",
      "status": "executing",
      "steps": plan["steps"],
      "toolCalls": [{"planId": "plan-retry", "status": "running"}],
      "messages": [],
    }

    result = server.fail_agent_plan_execution(session, plan, "ABILITY_TASK_FAILED")

    self.assertEqual(result["status"], "failed")
    self.assertEqual(plan["status"], "failed")
    self.assertEqual(plan["execution"]["status"], "failed")
    self.assertEqual(session["status"], "execution_failed")

  def test_running_prompt_only_agent_session_reads_middle_platform_task_result(self):
    server.prepare_asset_for_storage = lambda _user_id, asset, **_kwargs: asset
    server.get_midplatform_ability_task = lambda _task_id, timeout=15.0: {
      "status": "succeeded",
      "result_payload": {
        "raw": {"resultUrls": ["https://vendor.example.com/temporary-result.png"]},
        "images": [{"url": f"{server.OSS_PUBLIC_DOMAIN}/agent-result.png"}],
      },
    }
    plan = {
      "planId": "plan-1",
      "intent": "ai_recreate",
      "status": "running",
      "needsUserConfirmation": False,
      "steps": [{"stepId": "s2", "targetAbility": "image2_recreate", "status": "running", "outputCount": 1}],
      "execution": {"status": "running", "abilityTaskIds": ["ability-task-123"], "businessRunIds": []},
    }
    session = {
      "sessionId": "agent-1",
      "userId": "user-test",
      "productId": "10385",
      "status": "executing",
      "currentPlanId": "plan-1",
      "plans": [plan],
      "toolCalls": [{"planId": "plan-1", "status": "running"}],
      "resultAssetIds": [],
      "messages": [],
      "workingMemory": {},
    }

    changed = server.refresh_running_agent_session("user-test", session)

    self.assertTrue(changed)
    self.assertEqual(session["status"], "preview_ready")
    self.assertEqual(plan["execution"]["status"], "completed")
    self.assertEqual(len(session["resultAssetIds"]), 1)
    self.assertEqual(
      server.find_asset("user-test", session["resultAssetIds"][0])["url"],
      f"{server.OSS_PUBLIC_DOMAIN}/agent-result.png",
    )

  def test_agent_prompt_ignores_operational_confirmation_message(self):
    session = {
      "messages": [
        {"role": "user", "type": "text", "content": "我想做一个西安文旅杯，主体要有兵马俑和城墙。"},
        {"role": "user", "type": "confirmation", "content": "确认这套设计方案，开始生成。"},
      ],
    }

    self.assertEqual(
      server.agent_latest_user_message(session),
      "我想做一个西安文旅杯，主体要有兵马俑和城墙。",
    )


if __name__ == "__main__":
  unittest.main()
