/**
 * 公开申请 — 精简版
 */
import { useState, useEffect } from "react";
import { CheckCircle2, Share2, ShieldCheck } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { demo } from "../data/mock-data";
import type { WorkKind } from "../types";
import PageHeader from "../components/PageHeader";

export default function PublishPage() {
  const { navigate, state, dispatch } = useApp();
  const [publishType, setPublishType] = useState<WorkKind>(state.publishDraftKind);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [usage, setUsage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    setPublishType(state.publishDraftKind);
  }, [state.publishDraftKind]);

  const previewImage = state.publishDraftSource?.image ?? (publishType === "产品作品" ? demo("geometric-pattern") : demo("floral-pattern"));
  const displayTitle = title.trim() || state.publishDraftSource?.title || (publishType === "产品作品" ? "产品样例作品" : "图片素材作品");
  const displayTags = tags.trim() || state.publishDraftSource?.tags || "花卉 / 杯子 / 礼品";
  const displayUsage = usage.trim() || state.publishDraftSource?.usage || (publishType === "产品作品" ? "别人可以用同款试做或换图案。" : "别人可以用同款处理或继续裂变。");

  const handleSubmit = () => {
    dispatch({
      type: "SUBMIT_PUBLISH",
      application: {
        id: `publish-${Date.now()}`,
        kind: publishType,
        title: displayTitle,
        tags: displayTags,
        usage: displayUsage,
        image: previewImage,
        submittedAt: new Date().toLocaleString("zh-CN"),
        status: "待审核",
      },
    });
    setSubmitted(true);
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
          </div>
        </div>

        <aside className="publish-review-side">
          <h3>提交前确认</h3>
          <div className="review-checklist">
            <span>确认作品没有未授权的素材</span>
            <span>确认只公开当前卡片</span>
            <span>抵扣权益留在站内，不可提现</span>
          </div>
          <label className="policy-confirm">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            <span>我确认可以公开展示并提交审核</span>
          </label>
          <button className="primary full" disabled={!confirmed || submitted} onClick={handleSubmit}>
            {submitted ? "已提交审核" : "提交审核"}
          </button>
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
