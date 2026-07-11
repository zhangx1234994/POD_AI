/**
 * 灵感广场 — 精简版
 */
import { useState } from "react";
import { Share2, Eye, Bookmark, ChevronRight } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { inspirationWorks } from "../data/mock-data";
import type { WorkKind } from "../types";
import PageHeader from "../components/PageHeader";

export default function InspirePage() {
  const { navigate, dispatch } = useApp();
  const [workKind, setWorkKind] = useState<WorkKind | "全部">("全部");
  const [sort, setSort] = useState("热门");

  const works = workKind === "全部" ? inspirationWorks : inspirationWorks.filter((w) => w.kind === workKind);

  const useWork = (work: typeof inspirationWorks[0]) => {
    dispatch({ type: "SET_SAME_STYLE_WORK", work });
    if (work.kind === "产品作品") {
      navigate("products");
    } else {
      navigate("process");
    }
  };

  return (
    <main className="page-shell">
      <PageHeader
        eyebrow="灵感广场"
        title="看到喜欢的图，可以直接试同款。"
        desc="这里展示审核通过的图片素材和产品作品。图片可进入批处理，产品可进入试做草稿，来源会保留用于站内抵扣。"
      />

      <section className="inspire-content">
        <div className="inspire-feed">
          <div className="inspire-top-bar">
            <div className="kind-row">
              {(["全部", "图片作品", "产品作品"] as const).map((item) => (
                <button key={item} className={workKind === item ? "active" : ""} onClick={() => setWorkKind(item)}>
                  {item}
                </button>
              ))}
            </div>
            <div className="sort-row">
              {["热门", "最新", "最多使用", "最多收藏"].map((item) => (
                <button key={item} className={sort === item ? "active" : ""} onClick={() => setSort(item)}>
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="work-grid large">
            {works.map((work) => (
              <article key={work.id} className="work-card">
                <img src={work.image} alt={work.title} />
                <div className="work-body">
                  <span className={work.kind === "产品作品" ? "type-tag product" : "type-tag"}>{work.kind}</span>
                  <h3>{work.title}</h3>
                  <div className="creator-line">
                    <span>{work.author}</span>
                  </div>
                  <div className="tag-row">{work.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
                  <div className="work-stats">
                    <span><Eye size={14} /> {work.tries}</span>
                    <span><Bookmark size={14} /> {work.favorites}</span>
                    <span>{work.trend}</span>
                  </div>
                  <div className="creator-earnings">
                    <strong>{work.earnings}</strong>
                  </div>
                  <button className="primary full" onClick={() => useWork(work)}>
                    {work.kind === "产品作品" ? "带入产品草稿" : "带入批处理草稿"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="inspire-side">
          <button className="primary full" onClick={() => navigate("publish")}>
            <Share2 size={16} /> 发布我的作品
          </button>
          <div className="inspire-rules">
            <h3>同款会进入哪里</h3>
            <div className="rule-item">
              <strong>图片作品</strong>
              <span>进入图片批处理草稿，可提取、裂变、连续化或扩图</span>
            </div>
            <div className="rule-item">
              <strong>产品作品</strong>
              <span>进入产品草稿，可换素材、换杯型或生成预览</span>
            </div>
            <div className="rule-item">
              <strong>站内抵扣</strong>
              <span>同款来源会被记录，后续用于抵扣和分成</span>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
