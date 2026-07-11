/**
 * 图编辑器 — 单图精修
 * 三栏：左侧工具面板 / 中间画布 / 右侧参数
 */
import { useState } from "react";
import {
  Crop,
  RotateCw,
  Sliders,
  Type,
  Sticker,
  Eraser,
  Save,
  ShoppingBag,
  RefreshCw,
  ArrowLeft,
  CheckCircle2,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import PageHeader from "../components/PageHeader";

const tools = [
  { id: "crop", label: "裁剪", icon: Crop },
  { id: "rotate", label: "旋转", icon: RotateCw },
  { id: "adjust", label: "调色", icon: Sliders },
  { id: "text", label: "文字", icon: Type },
  { id: "sticker", label: "贴纸", icon: Sticker },
  { id: "erase", label: "擦除", icon: Eraser },
];

export default function EditorPage() {
  const { navigate, state } = useApp();
  const [activeTool, setActiveTool] = useState("crop");
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState("");

  // 取第一张选中的素材作为编辑对象
  const editingAsset =
    state.assets.find((a) => state.selectedAssetIds.includes(a.id)) ?? state.assets[0];

  const showNotice = (msg: string) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 2600);
  };

  const handleSave = () => {
    setSaved(true);
    showNotice("编辑已保存");
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <main className="editor-page">
      <div className="editor-topbar">
        <button className="editor-back" onClick={() => navigate("assets")}>
          <ArrowLeft size={16} />
          返回素材库
        </button>
        <span className="editor-filename">{editingAsset?.title ?? "未命名图片"}</span>
        <div className="editor-topbar-actions">
          <button className="secondary" onClick={() => navigate("process")}>
            <RefreshCw size={14} /> 继续处理
          </button>
          <button className="secondary" onClick={() => navigate("products")}>
            <ShoppingBag size={14} /> 做产品
          </button>
          <button className="primary" onClick={handleSave}>
            <Save size={14} />
            {saved ? "已保存" : "保存"}
          </button>
        </div>
      </div>

      {notice && (
        <div className="editor-notice" role="status">
          <CheckCircle2 size={14} />
          <span>{notice}</span>
        </div>
      )}

      <div className="editor-layout">
        {/* 左侧工具面板 */}
        <aside className="editor-tools">
          {tools.map((tool) => {
            const Icon = tool.icon;
            return (
              <button
                key={tool.id}
                className={activeTool === tool.id ? "active" : ""}
                onClick={() => setActiveTool(tool.id)}
                title={tool.label}
              >
                <Icon size={18} />
                <span>{tool.label}</span>
              </button>
            );
          })}
        </aside>

        {/* 中间画布 */}
        <section className="editor-canvas">
          <div className="canvas-area">
            <img
              src={editingAsset?.thumbnailUrl ?? "/demo/floral-pattern.png"}
              alt="编辑中"
              className="canvas-image"
            />
            <div className="canvas-overlay">
              <span>画布区域 — 后续接入 Canvas 编辑</span>
            </div>
          </div>
        </section>

        {/* 右侧参数面板 */}
        <aside className="editor-params">
          <h3>参数</h3>
          {activeTool === "crop" && (
            <div className="param-group">
              <label>
                <span>宽度</span>
                <input type="number" defaultValue={800} />
              </label>
              <label>
                <span>高度</span>
                <input type="number" defaultValue={600} />
              </label>
              <label>
                <span>比例锁定</span>
                <select>
                  <option>自由</option>
                  <option>1:1</option>
                  <option>4:3</option>
                  <option>16:9</option>
                </select>
              </label>
            </div>
          )}
          {activeTool === "rotate" && (
            <div className="param-group">
              <label>
                <span>旋转角度</span>
                <input type="range" min="-180" max="180" defaultValue={0} />
              </label>
              <label>
                <span>翻转</span>
                <div className="flip-btns">
                  <button>水平翻转</button>
                  <button>垂直翻转</button>
                </div>
              </label>
            </div>
          )}
          {activeTool === "adjust" && (
            <div className="param-group">
              <label><span>亮度</span><input type="range" min={-100} max={100} defaultValue={0} /></label>
              <label><span>对比度</span><input type="range" min={-100} max={100} defaultValue={0} /></label>
              <label><span>饱和度</span><input type="range" min={-100} max={100} defaultValue={0} /></label>
              <label><span>色温</span><input type="range" min={-100} max={100} defaultValue={0} /></label>
            </div>
          )}
          {(activeTool === "text" || activeTool === "sticker" || activeTool === "erase") && (
            <div className="param-group">
              <p className="param-placeholder">
                {activeTool === "text" && "在画布上点击添加文字"}
                {activeTool === "sticker" && "在画布上点击添加贴纸"}
                {activeTool === "erase" && "在画布上涂抹要擦除的区域"}
              </p>
            </div>
          )}

          <div className="param-output">
            <h3>输出设置</h3>
            <label>
              <span>格式</span>
              <select>
                <option>PNG</option>
                <option>JPG</option>
                <option>WebP</option>
              </select>
            </label>
            <label>
              <span>质量</span>
              <select>
                <option>高</option>
                <option>中</option>
                <option>低</option>
              </select>
            </label>
          </div>
        </aside>
      </div>
    </main>
  );
}
