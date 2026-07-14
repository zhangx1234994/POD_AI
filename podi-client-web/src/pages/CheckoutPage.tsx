import { Suspense, lazy, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  MapPin,
  PackageCheck,
  Ticket,
  Trash2,
  WalletCards,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import { cupProducts } from "../data/cup-products";
import { modelUvCalibrationForSurface } from "../data/model-uv-calibrations";
import type { AssetItem, ClientShippingAddress, ProductOrderDraft } from "../types";
import { createClientOrder, getClientAssetPreviewUrl, payClientOrder } from "../api";
import { readStoredAddress, writeStoredAddress } from "../utils/addressBook";

const Product3DPreview = lazy(() => import("../components/Product3DPreview"));

function validateAddress(address: ClientShippingAddress) {
  const errors: Partial<Record<keyof ClientShippingAddress, string>> = {};
  const phone = address.phoneNumber.trim();
  const email = address.email.trim();
  const country = address.country.trim();
  const postalCode = address.postalCode.trim();
  if (!address.recipientName.trim()) errors.recipientName = "请填写收货人姓名";
  if (!phone) errors.phoneNumber = "请填写联系电话";
  else if (!/^[0-9+\-\s()]{7,24}$/.test(phone)) errors.phoneNumber = "联系电话格式不正确";
  if (!country) errors.country = "请填写国家或地区";
  else if (!/^[A-Za-z]{2,3}$/.test(country)) errors.country = "请使用 CN / US 这类国家代码";
  if (!address.state.trim()) errors.state = "请填写省/州";
  if (!address.city.trim()) errors.city = "请填写城市";
  if (country.toUpperCase() === "CN" && !address.district.trim()) errors.district = "请填写区/县";
  if (!postalCode) errors.postalCode = "请填写邮编";
  else if (!/^[A-Za-z0-9\-\s]{3,16}$/.test(postalCode)) errors.postalCode = "邮编格式不正确";
  if (!address.address.trim()) errors.address = "请填写详细地址";
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "邮箱格式不正确";
  return errors;
}

function isLocalPreviewDraft(draft: ProductOrderDraft) {
  return draft.previewAssetId.startsWith("local-preview-") || draft.previewImageUrl.startsWith("data:");
}

type CheckoutMode = "together" | "split";

function formatMoney(cents: number) {
  return `${Math.round(Math.max(0, cents) / 100)} 积分`;
}

function designConfigString(config: Record<string, unknown>, key: string) {
  return typeof config[key] === "string" ? config[key] : "";
}

function DesignDraftPreview({ draft, assets, userId }: { draft: ProductOrderDraft; assets: AssetItem[]; userId: string }) {
  const product = cupProducts.find((item) => item.id === draft.productId);
  const sizeLabel = designConfigString(draft.designConfig, "sizeLabel");
  const size = product?.sizes.find((item) => item.label === sizeLabel) ?? product?.sizes[0] ?? null;
  const modelFile = size?.modelFile || product?.modelFile || "";
  const surfaceAssignments = draft.designConfig.surfaceAssignments;
  const assignmentMap = surfaceAssignments && typeof surfaceAssignments === "object" && !Array.isArray(surfaceAssignments)
    ? surfaceAssignments as Record<string, unknown>
    : {};
  const assetsById = new Map(assets.map((asset) => [asset.id, asset]));
  const textureAssignments = size?.surfaces.flatMap((surface) => {
    const assignedValue = assignmentMap[surface.name];
    const assignedId = typeof assignedValue === "string" ? assignedValue : "";
    const assetId = assignedId || (surface.name === designConfigString(draft.designConfig, "surfaceName") ? draft.sourceAssetId : "");
    if (!assetId) return [];
    const asset = assetsById.get(assetId);
    const textureUrl = asset && userId
      ? getClientAssetPreviewUrl(assetId, userId)
      : asset?.url || (assetId === draft.sourceAssetId ? draft.sourceAssetUrl : "");
    if (!textureUrl) return [];
    return [{
      surfaceName: surface.name,
      surfaceLabel: surface.label,
      textureUrl,
      textureLabel: asset?.title || draft.sourceAssetTitle || "设计稿",
      printWidth: surface.width,
      printHeight: surface.height,
      uvCalibration: modelUvCalibrationForSurface(modelFile, surface.name),
    }];
  }) ?? [];
  const baseColor = designConfigString(draft.designConfig, "baseColor") || "#f8f7f2";
  const configuredTextureMode = designConfigString(draft.designConfig, "textureMode");
  const textureMode: "wrap" | "fit" | "cover" | "decal" =
    configuredTextureMode === "fit" || configuredTextureMode === "cover" || configuredTextureMode === "decal"
      ? configuredTextureMode
      : "wrap";

  if (!product || !modelFile || !textureAssignments.length) {
    return <img className="checkout-draft-preview__fallback" src={draft.sourceAssetUrl} alt={`${draft.productName} 设计稿`} />;
  }

  return (
    <Suspense fallback={<div className="checkout-draft-preview__loading">正在生成产品预览</div>}>
      <Product3DPreview
        productName={draft.productName}
        modelFile={modelFile}
        modelUrl={`/models/product-3d/${modelFile}`}
        textureUrl={null}
        textureLabel={draft.sourceAssetTitle || "设计稿"}
        surfaceTextures={textureAssignments}
        surfaceName={designConfigString(draft.designConfig, "surfaceName") || undefined}
        surfaceLabel={designConfigString(draft.designConfig, "surfaceLabel") || "设计面"}
        printWidth={typeof draft.designConfig.surfaceWidth === "number" ? draft.designConfig.surfaceWidth : null}
        printHeight={typeof draft.designConfig.surfaceHeight === "number" ? draft.designConfig.surfaceHeight : null}
        baseColor={baseColor}
        textureMode={textureMode}
        textureScale={typeof draft.designConfig.textureScale === "number" ? draft.designConfig.textureScale : 1}
        textureOffsetX={typeof draft.designConfig.textureOffsetX === "number" ? draft.designConfig.textureOffsetX : 0}
        textureOffsetY={typeof draft.designConfig.textureOffsetY === "number" ? draft.designConfig.textureOffsetY : 0}
      />
    </Suspense>
  );
}

export default function CheckoutPage() {
  const { state, dispatch, navigate, activeUserId, isAuthenticated } = useApp();
  const draft = (state.checkoutDraft ?? state.orderDrafts[0] ?? null) as ProductOrderDraft | null;
  const [checkoutMode, setCheckoutMode] = useState<CheckoutMode>("together");
  const [address, setAddress] = useState<ClientShippingAddress>(() => readStoredAddress());
  const [addressErrors, setAddressErrors] = useState<Partial<Record<keyof ClientShippingAddress, string>>>({});
  const [useProductCoupon, setUseProductCoupon] = useState(Boolean(draft?.useProductCoupon && state.productCouponCount > 0));
  const [submitting, setSubmitting] = useState(false);
  const [checkoutError, setCheckoutError] = useState("");
  const [createdOrderId, setCreatedOrderId] = useState("");
  const submitLockRef = useRef(false);

  const removeDraft = (draftId: string) => {
    dispatch({ type: "REMOVE_ORDER_DRAFT", draftId });
    setCheckoutError("");
  };

  if (!draft) {
    return (
      <main className="page-shell checkout-page">
        <PageHeader
          eyebrow="设计篮"
          title="设计篮里还没有产品。"
          desc="先选择杯型、放入素材并确认设计，产品会出现在这里。"
        />
        <section className="checkout-empty">
          <PackageCheck size={28} />
          <strong>设计篮还是空的</strong>
          <p>你可以先去全部商品选择杯型，或先处理一张图片作为产品素材。</p>
          <div>
            <button className="primary" onClick={() => navigate("products")}>选择杯型</button>
            <button className="secondary" onClick={() => navigate("process")}>处理图片</button>
          </div>
        </section>
      </main>
    );
  }

  const draftPool = state.orderDrafts.length > 0 ? state.orderDrafts : [draft];
  const selectedDrafts = checkoutMode === "together" ? draftPool : [draft];
  const selectedQuantity = selectedDrafts.reduce((total, item) => total + item.quantity, 0);
  const productTotalCents = selectedDrafts.reduce((total, item) => total + item.payableCents, 0);
  const couponDiscountCents = useProductCoupon ? Math.min(5000, productTotalCents) : 0;
  const finalPayableCents = Math.max(0, productTotalCents - couponDiscountCents);
  const updateAddress = (field: keyof ClientShippingAddress, value: string) => {
    setAddress((current) => ({ ...current, [field]: field === "country" ? value.toUpperCase() : value }));
    setAddressErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
    if (checkoutError) setCheckoutError("");
  };

  const submitCheckout = async () => {
    if (submitting || submitLockRef.current || createdOrderId) return;
    if (!isAuthenticated) {
      setCheckoutError("请先登录，再提交订单。");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    const errors = validateAddress(address);
    setAddressErrors(errors);
    if (Object.keys(errors).length > 0) {
      setCheckoutError("请先修正收货信息中的错误。");
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setCheckoutError("");
    try {
      const normalizedAddress = writeStoredAddress(address);
      const shippingSignature = [
        normalizedAddress.recipientName,
        normalizedAddress.phoneNumber,
        normalizedAddress.country,
        normalizedAddress.state,
        normalizedAddress.city,
        normalizedAddress.district,
        normalizedAddress.postalCode,
        normalizedAddress.address,
      ].join("|");
      const checkoutGroupId = `checkout:${activeUserId}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
      if (selectedDrafts.some(isLocalPreviewDraft)) {
        submitLockRef.current = false;
        setCheckoutError("当前设计还只是本地预览，请先回到产品试做页保存为真实素材后再提交订单。");
        return;
      }
      const createdOrders = [];
      for (const item of selectedDrafts) {
        const clientRequestId = `checkout:${activeUserId}:${item.draftId}:${item.productId}:${item.previewAssetId}:${item.quantity}:${shippingSignature}`;
        const order = await createClientOrder({
          userId: activeUserId,
          productId: item.productId,
          productName: item.productName,
          assetId: item.previewAssetId,
          sourceAssetId: item.sourceAssetId,
          sourceAssetUrl: item.sourceAssetUrl,
          sourceAssetTitle: item.sourceAssetTitle,
          clientRequestId,
          checkoutGroupId,
          quantity: item.quantity,
          useProductCoupon: Boolean(useProductCoupon && item.draftId === selectedDrafts[0]?.draftId),
          shippingAddress: {
            country: normalizedAddress.country,
            state: normalizedAddress.state,
            city: normalizedAddress.city,
            district: normalizedAddress.district || undefined,
            postalCode: normalizedAddress.postalCode,
            address: normalizedAddress.address,
            phoneNumber: normalizedAddress.phoneNumber,
            recipientName: normalizedAddress.recipientName,
            email: normalizedAddress.email || undefined,
          },
        });
        const paidOrder = await payClientOrder({
          userId: activeUserId,
          orderId: order.id,
          method: "mock",
        });
        createdOrders.push(paidOrder);
      }
      createdOrders.forEach((order) => dispatch({ type: "ADD_ORDER", order }));
      selectedDrafts.forEach((item) => dispatch({ type: "REMOVE_ORDER_DRAFT", draftId: item.draftId }));
      if (!draft.draftId) dispatch({ type: "CLEAR_CHECKOUT_DRAFT" });
      setCreatedOrderId(createdOrders[0]?.id || "orders");
      window.setTimeout(() => navigate("orders"), 900);
    } catch (error) {
      submitLockRef.current = false;
      setCheckoutError(error instanceof Error ? error.message : "订单提交失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="page-shell checkout-page">
      <button className="product-back-link" onClick={() => navigate("productDesign")}>
        <ArrowLeft size={16} />
        返回继续调整
      </button>
      <PageHeader
        eyebrow="结算"
        title="确认设计、地址和支付。"
        desc="支付成功后自动提交蜂鸟安排生产。"
      />

      <section className="checkout-shell">
        <div className="checkout-main">
          <article className="checkout-product-card">
            <div className="checkout-draft-preview">
              <DesignDraftPreview draft={draft} assets={state.assets} userId={activeUserId} />
            </div>
            <div>
              <small>当前处理</small>
              <strong>{draft.productName}</strong>
              <p>素材：{draft.sourceAssetTitle}</p>
              <span>{draft.quantity} 件 · 已保存设计稿</span>
            </div>
          </article>

          {state.orderDrafts.length > 0 && (
            <section className="design-basket-list">
              <div className="checkout-section-head">
                <PackageCheck size={18} />
                <div>
                  <strong>设计篮</strong>
                  <span>{state.orderDrafts.length > 1 ? "核对每件设计；需要分开发货时再切换拆单。" : "核对当前设计，确认无误后填写地址并结算。"}</span>
                </div>
              </div>
              {state.orderDrafts.length > 1 && (
                <div className="checkout-mode-switch" role="group" aria-label="提交方式">
                  <button
                    type="button"
                    className={checkoutMode === "together" ? "active" : ""}
                    onClick={() => setCheckoutMode("together")}
                  >
                    一起寄给同一个人
                  </button>
                  <button
                    type="button"
                    className={checkoutMode === "split" ? "active" : ""}
                    onClick={() => setCheckoutMode("split")}
                  >
                    逐件拆单代发
                  </button>
                </div>
              )}
              <div className="design-basket-list__items">
                {state.orderDrafts.map((item) => (
                  <div className={`design-basket-list__item ${checkoutMode === "together" || item.draftId === draft.draftId ? "active" : ""}`} key={item.draftId}>
                    <button
                      className="design-basket-list__select"
                      type="button"
                      onClick={() => {
                        setCheckoutMode("split");
                        dispatch({ type: "SET_CHECKOUT_DRAFT", draft: item });
                      }}
                    >
                      <img src={item.sourceAssetUrl} alt={`${item.productName} 设计稿`} />
                      <span>
                        <strong>{item.productName}</strong>
                        <small>{item.quantity} 件 · 设计稿：{item.sourceAssetTitle}</small>
                      </span>
                    </button>
                    <button className="design-basket-list__remove" type="button" onClick={() => removeDraft(item.draftId)} aria-label={`从设计篮移除 ${item.productName}`} title="从设计篮移除">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="checkout-address-card">
            <div className="checkout-section-head">
              <MapPin size={18} />
              <div>
                <strong>收货地址</strong>
                <span>
                  {checkoutMode === "together"
                    ? `当前地址会应用到 ${selectedDrafts.length} 个设计、共 ${selectedQuantity} 件。`
                    : "当前只提交选中的 1 个设计；切换设计后可以填写另一个地址。"}
                </span>
              </div>
            </div>
            <div className="sample-order-fields checkout-fields">
              <label>
                <span>收货人</span>
                <input className={addressErrors.recipientName ? "invalid" : ""} value={address.recipientName} onChange={(event) => updateAddress("recipientName", event.target.value)} placeholder="姓名" />
                {addressErrors.recipientName && <em className="field-error">{addressErrors.recipientName}</em>}
              </label>
              <label>
                <span>联系电话</span>
                <input className={addressErrors.phoneNumber ? "invalid" : ""} value={address.phoneNumber} onChange={(event) => updateAddress("phoneNumber", event.target.value)} placeholder="手机号或国际号码" />
                {addressErrors.phoneNumber && <em className="field-error">{addressErrors.phoneNumber}</em>}
              </label>
              <label>
                <span>国家</span>
                <input className={addressErrors.country ? "invalid" : ""} value={address.country} onChange={(event) => updateAddress("country", event.target.value)} placeholder="CN / US" />
                {addressErrors.country && <em className="field-error">{addressErrors.country}</em>}
              </label>
              <label>
                <span>省/州</span>
                <input className={addressErrors.state ? "invalid" : ""} value={address.state} onChange={(event) => updateAddress("state", event.target.value)} placeholder="省份或州" />
                {addressErrors.state && <em className="field-error">{addressErrors.state}</em>}
              </label>
              <label>
                <span>城市</span>
                <input className={addressErrors.city ? "invalid" : ""} value={address.city} onChange={(event) => updateAddress("city", event.target.value)} placeholder="城市" />
                {addressErrors.city && <em className="field-error">{addressErrors.city}</em>}
              </label>
              <label>
                <span>区/县{address.country === "CN" ? "" : "（可选）"}</span>
                <input className={addressErrors.district ? "invalid" : ""} value={address.district} onChange={(event) => updateAddress("district", event.target.value)} placeholder="区或县" />
                {addressErrors.district && <em className="field-error">{addressErrors.district}</em>}
              </label>
              <label>
                <span>邮编</span>
                <input className={addressErrors.postalCode ? "invalid" : ""} value={address.postalCode} onChange={(event) => updateAddress("postalCode", event.target.value)} placeholder="邮编" />
                {addressErrors.postalCode && <em className="field-error">{addressErrors.postalCode}</em>}
              </label>
              <label className="wide">
                <span>详细地址</span>
                <input className={addressErrors.address ? "invalid" : ""} value={address.address} onChange={(event) => updateAddress("address", event.target.value)} placeholder="街道、门牌号、收件补充信息" />
                {addressErrors.address && <em className="field-error">{addressErrors.address}</em>}
              </label>
              <label className="wide">
                <span>邮箱（可选）</span>
                <input className={addressErrors.email ? "invalid" : ""} value={address.email} onChange={(event) => updateAddress("email", event.target.value)} placeholder="用于接收订单通知" />
                {addressErrors.email && <em className="field-error">{addressErrors.email}</em>}
              </label>
            </div>
          </section>
        </div>

        <aside className="checkout-summary-card">
          <div className="checkout-section-head">
            <CreditCard size={18} />
            <div>
              <strong>支付确认</strong>
              <span>测试支付与正式支付共用同一条自动履约链路。</span>
            </div>
          </div>
          <div className="checkout-line">
            <span>商品金额</span>
            <strong>{formatMoney(productTotalCents)}</strong>
          </div>
          <div className="checkout-line muted">
            <span>配送方式</span>
            <strong>蜂鸟后台选择</strong>
          </div>
          {selectedDrafts.length > 1 && (
            <div className="checkout-line muted">
              <span>{checkoutMode === "together" ? "整批提交" : "当前拆单"}</span>
              <strong>{selectedDrafts.length} 个设计 / {selectedQuantity} 件</strong>
            </div>
          )}
          <label className={state.productCouponCount > 0 ? "checkout-coupon-row" : "checkout-coupon-row disabled"}>
            <span><Ticket size={15} />产品券抵扣</span>
            <input type="checkbox" checked={useProductCoupon} disabled={state.productCouponCount <= 0} onChange={(event) => setUseProductCoupon(event.target.checked)} />
            <em>{state.productCouponCount > 0 ? `可用 ${state.productCouponCount} 张` : "暂无可用"}</em>
          </label>
          <div className="checkout-line muted">
            <span>产品券抵扣</span>
            <strong>-{formatMoney(couponDiscountCents)}</strong>
          </div>
          <div className="checkout-line total">
            <span>本次支付</span>
            <strong>{formatMoney(finalPayableCents)}</strong>
          </div>
          <div className="checkout-payment-method">
            <WalletCards size={16} />
            <span>测试支付 · 成功后自动提交蜂鸟</span>
          </div>
          {checkoutError && (
            <div className="sample-order-error" role="alert">
              <AlertCircle size={15} />
              <span>{checkoutError}</span>
            </div>
          )}
          {createdOrderId && (
            <div className="checkout-success" role="status">
              <CheckCircle2 size={16} />
              <span>支付完成，正在进入订单页。</span>
            </div>
          )}
          <button className="primary full" disabled={submitting || Boolean(createdOrderId)} onClick={submitCheckout}>
            {submitting
              ? "正在提交订单"
              : createdOrderId
                ? "订单已提交"
              : selectedDrafts.length > 1
                  ? `提交 ${selectedDrafts.length} 个设计并测试支付`
                  : "提交订单并测试支付"}
          </button>
          <p>支付成功后平台自动提交蜂鸟；如供应链暂时失败，订单保持已支付并由平台重试。蜂鸟效果图回传后会替换当前商品示意图。</p>
        </aside>
      </section>
    </main>
  );
}
