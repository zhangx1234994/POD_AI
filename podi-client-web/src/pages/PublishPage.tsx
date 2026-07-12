/**
 * 公开申请 — 精简版
 */
import { useState, useEffect } from "react";
import { CheckCircle2, Share2, ShieldCheck } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { demo } from "../data/mock-data";
import type { AssetLicenseMode, WorkKind } from "../types";
import PageHeader from "../components/PageHeader";
import { submitClientPublishApplication } from "../api";

export default function PublishPage() {
  const { navigate, state, dispatch, activeUserId, isAuthenticated } = useApp();
  const [publishType, setPublishType] = useState<WorkKind>(state.publishDraftKind);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [usage, setUsage] = useState("");
  const [licenseMode, setLicenseMode] = useState<AssetLicenseMode>("free_reuse");
  const [pricePoints, setPricePoints] = useState("24");
  const [confirmed, setConfirmed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    setPublishType(state.publishDraftKind);
  }, [state.publishDraftKind]);

  const previewImage = state.publishDraftSource?.image ?? (publishType === "产品作品" ? demo("geometric-pattern") : demo("floral-pattern"));
  const displayTitle = title.trim() || state.publishDraftSource?.title || (publishType === "产品作品" ? "产品样例作品" : "图片素材作品");
  const displayTags = tags.trim() || state.publishDraftSource?.tags || "花卉 / 杯子 / 礼品";
  const displayUsage = usage.trim() || state.publishDraftSource?.usage || (publishType === "产品作品" ? "别人可以用同款试做或换图案。" : "别人可以用同款处理或继续裂变。");
  const normalizedPricePoints = Math.max(0, Math.round(Number(pricePoints) || 0));

  const handleSubmit = async () => {
    if (!isAuthenticated) {
      setSubmitError("请先登录，登录后才能提交公开审核。");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    setSubmitting(true);
    setSubmitError("");
    try {
      const application = await submitClientPublishApplication({
        userId: activeUserId,
        kind: publishType,
        title: displayTitle,
        tags: displayTags,
        usage: displayUsage,
        image: previewImage,
        licenseMode,
        pricePoints: licenseMode === "paid_points" ? normalizedPricePoints : 0,
      });
      dispatch({ type: "SUBMIT_PUBLISH", application });
      setSubmitted(true);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "提交失败，已先保存在本地审核列表。");
      dispatch({
        type: "SUBMIT_PUBLISH",
        application: {
          id: `publish-${Date.now()}`,
          kind: publishType,
          title: displayTitle,
          tags: displayTags,
          usage: displayUsage,
          image: previewImage,
          licenseMode,
          pricePoints: licenseMode === "paid_points" ? normalizedPricePoints : 0,
          submittedAt: new Date().toLocaleString("zh-CN"),
          status: "待审核",
        },
      });
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="page-shell">
      <PageHeader
        eyebrow="公开申请"
        title="公开作品前，先说清用途。"
        desc="作品默认私有，审核通过后才进入灵感广场"
      />

      <section className="publish-layout">
        <div className="publish-form-area">
          <div className="publish-preview-card">
            <img src={previewImage} alt="待公开作品" />
            <div>
              <span className={publishType === "产品作品" ? "type-tag product" : "type-tag"}>{publishType}</span>
              <h3>{displayTitle}</h3>
              <p>{displayUsage}</p>
              <em>{displayTags}</em>
            </div>
          </div>

          <div className="publish-type-switch">
            {(["图片作品", "产品作品"] as WorkKind[]).map((type) => (
              <button key={type} className={publishType === type ? "active" : ""} onClick={() => { setPublishType(type); setConfirmed(false); setSubmitted(false); }}>
                <strong>{type}</strong>
                <span>{type === "图片作品" ? "进入批量处理" : "进入同款试做"}</span>
              </button>
            ))}
          </div>

          <div className="publish-fields">
            <label><span>标题</span><input value={title} onChange={(e) => { setTitle(e.target.value); setSubmitted(false); }} placeholder="例如：复古花卉马克杯" /></label>
            <label><span>标签</span><input value={tags} onChange={(e) => { setTags(e.target.value); setSubmitted(false); }} placeholder="花卉 / 杯子 / 礼品" /></label>
            <label><span>用途说明</span><textarea value={usage} onChange={(e) => { setUsage(e.target.value); setSubmitted(false); }} placeholder="说明别人可以如何使用" /></label>
            <div className="publish-license-options" role="group" aria-label="授权方式">
              {([
                { id: "display_only", title: "仅展示", desc: "别人只能看，不能保存或同款。" },
                { id: "free_reuse", title: "免费复用", desc: "别人可加入素材库，适合换曝光。" },
                { id: "paid_points", title: "积分授权", desc: "别人支付积分后使用，作者收益为站内积分。" },
              ] as Array<{ id: AssetLicenseMode; title: string; desc: string }>).map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={licenseMode === option.id ? "active" : ""}
                  onClick={() => {
                    setLicenseMode(option.id);
                    setSubmitted(false);
                  }}
                >
                  <strong>{option.title}</strong>
                  <span>{option.desc}</span>
                </button>
              ))}
            </div>
            {licenseMode === "paid_points" && (
              <label>
                <span>授权积分</span>
                <input
                  value={pricePoints}
                  onChange={(event) => {
                    setPricePoints(event.target.value);
                    setSubmitted(false);
                  }}
                  inputMode="numeric"
                  placeholder="例如 24"
                />
              </label>
            )}
          </div>
        </div>

        <aside className="publish-review-side">
          <h3>提交前确认</h3>
          <div className="review-checklist">
            <span>确认作品没有未授权的素材</span>
            <span>确认只公开当前卡片</span>
            <span>作者收益只结算为站内积分，不支持提现</span>
            <span>收到侵权投诉后，运营会人工联系双方核验证据</span>
          </div>
          <label className="policy-confirm">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            <span>我确认可以公开展示并提交审核</span>
          </label>
          <button className="primary full" disabled={!confirmed || submitted || submitting} onClick={handleSubmit}>
            {submitting ? "正在提交" : submitted ? "已提交审核" : "提交审核"}
          </button>
          {submitError && <div className="publish-success warning">{submitError}</div>}
          {submitted && (
            <div className="publish-success">
              <CheckCircle2 size={16} />
              <span>已提交，通过前仍是私有</span>
            </div>
          )}
          <div className="publish-nav-links">
            {submitted ? (
              <>
                <button className="secondary full" onClick={() => navigate("profile")}>查看审核进度</button>
                <button className="secondary full" onClick={() => navigate("inspire")}>继续逛灵感</button>
              </>
            ) : (
              <button className="secondary full" onClick={() => navigate("inspire")}>查看灵感广场</button>
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}
