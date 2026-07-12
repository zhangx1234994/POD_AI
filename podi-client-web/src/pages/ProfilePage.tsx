/**
 * 作者主页 — 精简版
 */
import { useState } from "react";
import { Share2, CheckCircle2, ShieldCheck } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { inspirationWorks } from "../data/mock-data";
import PageHeader from "../components/PageHeader";

export default function ProfilePage() {
  const { navigate, state, dispatch } = useApp();
  const [shareNotice, setShareNotice] = useState(false);

  const imageWorks = inspirationWorks.filter((w) => w.kind === "图片作品");
  const productWorks = inspirationWorks.filter((w) => w.kind === "产品作品");
  const pendingApp = state.publishApplications[0] ?? null;

  const handleShare = () => {
    setShareNotice(true);
    setTimeout(() => setShareNotice(false), 2400);
  };

  const useWork = (work: typeof inspirationWorks[0]) => {
    dispatch({ type: "SET_SAME_STYLE_WORK", work });
    navigate(work.kind === "产品作品" ? "productDesign" : "process");
  };

  return (
    <main className="page-shell">
      <section className="profile-hero">
        <div className="profile-identity">
          <div className="profile-avatar large">张</div>
          <p className="eyebrow">作者主页</p>
          <h1>张鑫的公开作品</h1>
          <p>公开展示已审核的图片素材和产品作品。其他用户可从这里进入同款草稿，来源会保留用于站内抵扣。</p>
          <div className="profile-actions">
            <button className="primary" onClick={handleShare}><Share2 size={16} /> 分享主页</button>
            <button className="secondary" onClick={() => navigate("publish")}><ShieldCheck size={16} /> 发布作品</button>
          </div>
          {shareNotice && (
            <div className="profile-share-notice" role="status">
              <CheckCircle2 size={16} />
              <span>分享链接已准备好</span>
            </div>
          )}
        </div>
        <div className="profile-showcase">
          {inspirationWorks.slice(0, 3).map((w) => (
            <img key={w.id} src={w.image} alt={w.title} />
          ))}
        </div>
      </section>

      <section className="profile-metrics">
        {[["18", "公开作品"], ["342", "收藏"], ["¥186.40", "站内抵扣"]].map(([v, l]) => (
          <article key={l}><strong>{v}</strong><span>{l}</span></article>
        ))}
      </section>

      {pendingApp && (
        <section className="profile-review-panel">
          <p className="eyebrow">审核进度</p>
          <h2>1 件作品等待审核</h2>
          <article className="pending-work-card">
            <img src={pendingApp.image} alt={pendingApp.title} />
            <div>
              <span className="type-tag">{pendingApp.status}</span>
              <h3>{pendingApp.title}</h3>
              <p>{pendingApp.submittedAt}</p>
            </div>
          </article>
        </section>
      )}

      <section className="profile-section">
        <div className="section-heading">
          <div><p className="eyebrow">图片作品</p><h2>图片灵感</h2></div>
          <button className="secondary" onClick={() => navigate("process")}>进入批量处理</button>
        </div>
        <div className="work-grid">
          {imageWorks.map((w) => (
            <article key={w.id} className="profile-work-card">
              <img src={w.image} alt={w.title} />
              <div>
                <span className="type-tag">{w.kind}</span>
                <h3>{w.title}</h3>
                <p>{w.tags.join(" / ")}</p>
                <button className="primary full" onClick={() => useWork(w)}>用同款处理</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="profile-section">
        <div className="section-heading">
          <div><p className="eyebrow">产品作品</p><h2>产品灵感</h2></div>
          <button className="secondary" onClick={() => navigate("products")}>进入做产品</button>
        </div>
        <div className="work-grid">
          {productWorks.map((w) => (
            <article key={w.id} className="profile-work-card">
              <img src={w.image} alt={w.title} />
              <div>
                <span className="type-tag product">{w.kind}</span>
                <h3>{w.title}</h3>
                <p>{w.tags.join(" / ")}</p>
                <button className="primary full" onClick={() => useWork(w)}>用同款试做</button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
