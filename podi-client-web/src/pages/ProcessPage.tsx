/**
 * 图片批处理页 — 能力入口 → 单能力批量处理
 */
import { useCallback, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import ImageUploader from "../components/ImageUploader";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import { demo, productDemo } from "../data/mock-data";
import { abilities, assetTypeLabels } from "../utils/constants";
import type { AssetType, BatchGoalId, ProcessTask } from "../types";
import { createClientProcessTask, uploadClientImage, type ClientBootstrap } from "../api";

type SizeMode = "preset" | "custom";

const abilityPresentation: Record<
  BatchGoalId,
  {
    eyebrow: string;
    headline: string;
    summary: string;
    entryCopy: string;
    bestFor: string[];
    productFits: string[];
    params: Array<{ label: string; value: string }>;
    presets: string[];
    sizePresets: string[];
    defaultCustomSize: { width: string; height: string };
    cover: string;
    resultType: AssetType;
  }
> = {
  clean: {
    eyebrow: "图片标准化",
    headline: "把原图整理成统一规格素材。",
    summary: "适合去背景、统一尺寸、DPI 标记和轻量压缩。它不是创意生成，主要用于把杂乱原图整理成可下载、可继续生产的素材。",
    entryCopy: "把原始图片整理成统一规格，便于下载、入库或继续做产品。",
    bestFor: ["去背景", "统一尺寸", "DPI 标记"],
    productFits: ["素材入库", "商品主图", "后续套版"],
    params: [
      { label: "处理内容", value: "去背景 / 统一规格" },
      { label: "输出尺寸", value: "原图 / 常用 / 自定义" },
      { label: "DPI", value: "150 / 300" },
    ],
    presets: ["保留原图", "统一规格", "生产优先"],
    sizePresets: ["原图尺寸", "1024×1024", "2000×2000", "3000×3000", "杯子设计面 2717×1476"],
    defaultCustomSize: { width: "2000", height: "2000" },
    cover: demo("floral-pattern"),
    resultType: "processed",
  },
  extend: {
    eyebrow: "扩图",
    headline: "在原图四周按方向扩出画面。",
    summary: "扩图是在原图基础上向上、下、左、右补出新画面，原图主体应尽量不变。适合补边、加留白和适配版面。",
    entryCopy: "在原图四周按方向补边，适配商品图或留白版面。",
    bestFor: ["上方补边", "左右扩宽", "四周留白"],
    productFits: ["商品主图", "社媒封面", "生产留白"],
    params: [
      { label: "扩展范围", value: "上 / 右 / 下 / 左" },
      { label: "扩展像素", value: "预设 / 自定义" },
      { label: "主体保护", value: "默认开启" },
    ],
    presets: ["四周等距", "只扩上方", "左右扩宽", "上下扩高"],
    sizePresets: [],
    defaultCustomSize: { width: "0", height: "0" },
    cover: demo("stripe-pattern"),
    resultType: "processed",
  },
  extract: {
    eyebrow: "花纹提取",
    headline: "把喜欢的花纹提取出来，变成素材。",
    summary: "适合从衣服、杯子、抱枕、场景照片里提取图案。提取后的花纹可以继续裂变、连续化或直接套到产品上。",
    entryCopy: "喜欢某张图的花纹，就把它提出来沉淀成素材。",
    bestFor: ["产品图提花", "参考图提花", "素材沉淀"],
    productFits: ["杯子", "服饰", "毛毯", "抱枕"],
    params: [
      { label: "输出尺寸", value: "默认 1800×1800" },
      { label: "提取方案", value: "平台默认" },
      { label: "尺寸", value: "原图 / 常用 / 自定义" },
    ],
    presets: [],
    sizePresets: ["原图尺寸", "1800×1800", "2400×2400", "3000×3000", "杯子设计面 2717×1476"],
    defaultCustomSize: { width: "1800", height: "1800" },
    cover: demo("geometric-pattern"),
    resultType: "pattern",
  },
  variation: {
    eyebrow: "裂变生成",
    headline: "基于一张图，生成相似风格图。",
    summary: "适合围绕一个已验证方向快速扩展系列图。可以控制变化幅度、颜色锁定和结构保留，先批量找方向再精选。",
    entryCopy: "用一张参考图生成同风格候选图，快速做系列。",
    bestFor: ["相似图生成", "风格探索", "系列扩展"],
    productFits: ["杯子系列", "伴手礼套装", "节日主题图"],
    params: [
      { label: "重绘幅度", value: "30 / 60 / 80%" },
      { label: "处理方式", value: "稳定优先" },
      { label: "锁定策略", value: "颜色 / 结构可控" },
    ],
    presets: ["保守同款", "同系列变化", "创意扩展"],
    sizePresets: ["原图尺寸", "1024×1024", "1800×1800", "杯子设计面 2717×1476", "保温杯设计面 3378×1949"],
    defaultCustomSize: { width: "1800", height: "1800" },
    cover: demo("floral-pattern"),
    resultType: "variation",
  },
  seamless2: {
    eyebrow: "两方连续",
    headline: "让杯子一圈更顺，不容易看到接缝。",
    summary: "适合杯子、瓶身、圆柱包装等横向环绕产品。重点处理左右边缘衔接，让图案绕一圈时更自然。",
    entryCopy: "用于杯子、瓶身这类圆柱产品，解决左右接缝。",
    bestFor: ["左右衔接", "杯身环绕", "减少接缝"],
    productFits: ["马克杯", "吸管杯", "保温杯", "包装筒"],
    params: [
      { label: "连续方式", value: "左右连续" },
      { label: "输出尺寸", value: "原图 / 常用 / 自定义" },
      { label: "适配", value: "杯身 / 圆柱包装" },
    ],
    presets: [],
    sizePresets: ["原图尺寸", "杯身横向 2717×1476", "保温杯设计面 3378×1949", "长条包装 3000×1500"],
    defaultCustomSize: { width: "2048", height: "1024" },
    cover: demo("stripe-pattern"),
    resultType: "pattern",
  },
  seamless4: {
    eyebrow: "四方连续",
    headline: "让图案上下左右都能无限平铺。",
    summary: "适合窗帘、布料、壁纸、毛毯和大面积印花。输出后的图案可以横向、纵向重复铺开，不容易看到边缘断裂。",
    entryCopy: "用于布料、窗帘、壁纸和大面积印花，解决无限平铺。",
    bestFor: ["无限平铺", "布料印花", "大面积图案"],
    productFits: ["窗帘", "毛毯", "布料", "壁纸"],
    params: [
      { label: "连续方式", value: "上下左右连续" },
      { label: "输出尺寸", value: "原图 / 常用 / 自定义" },
      { label: "适配", value: "布料 / 壁纸 / 大面积印花" },
    ],
    presets: [],
    sizePresets: ["原图尺寸", "2048×2048", "3000×3000", "布料纵向 2048×4096", "横向墙纸 4096×2048"],
    defaultCustomSize: { width: "2048", height: "2048" },
    cover: demo("geometric-pattern"),
    resultType: "pattern",
  },
};

const visibleAbilities = abilities.filter((ability) => ability.id !== "clean");

const capabilityVisualExamples: Record<
  BatchGoalId,
  {
    source: string;
    results: string[];
    mode: "single" | "multi" | "tile" | "extend";
    sourceLabel: string;
    resultLabel: string;
  }
> = {
  clean: {
    source: demo("floral-pattern"),
    results: [demo("floral-pattern")],
    mode: "single",
    sourceLabel: "杂乱原图",
    resultLabel: "统一素材",
  },
  extend: {
    source: demo("stripe-pattern"),
    results: [demo("stripe-pattern")],
    mode: "extend",
    sourceLabel: "原图",
    resultLabel: "四周补边",
  },
  extract: {
    source: productDemo("product-tote"),
    results: [demo("geometric-pattern")],
    mode: "single",
    sourceLabel: "产品图",
    resultLabel: "花纹素材",
  },
  variation: {
    source: demo("floral-pattern"),
    results: [demo("floral-pattern"), demo("stripe-pattern"), demo("geometric-pattern"), productDemo("product-pillow")],
    mode: "multi",
    sourceLabel: "参考图",
    resultLabel: "4 张候选",
  },
  seamless2: {
    source: demo("stripe-pattern"),
    results: [demo("stripe-pattern"), demo("stripe-pattern")],
    mode: "tile",
    sourceLabel: "原图",
    resultLabel: "左右连续",
  },
  seamless4: {
    source: demo("geometric-pattern"),
    results: [demo("geometric-pattern"), demo("geometric-pattern"), demo("geometric-pattern"), demo("geometric-pattern")],
    mode: "tile",
    sourceLabel: "原图",
    resultLabel: "四方平铺",
  },
};

const extendPresetPaddings: Record<string, { top: string; right: string; bottom: string; left: string }> = {
  四周等距: { top: "256", right: "256", bottom: "256", left: "256" },
  只扩上方: { top: "512", right: "0", bottom: "0", left: "0" },
  左右扩宽: { top: "0", right: "512", bottom: "0", left: "512" },
  上下扩高: { top: "512", right: "0", bottom: "512", left: "0" },
};

function parsePixel(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.round(parsed)) : 0;
}

function parseSizePreset(value: string): { width?: number; height?: number } {
  if (!value || value.includes("原图尺寸")) return {};
  const match = value.match(/(\d{2,5})\s*[×xX]\s*(\d{2,5})/);
  if (!match) return {};
  const width = parsePixel(match[1]);
  const height = parsePixel(match[2]);
  return width > 0 && height > 0 ? { width, height } : {};
}

function renderCapabilityVisual(goal: BatchGoalId) {
  const visual = capabilityVisualExamples[goal];
  return (
    <div className={`process-flow-visual ${visual.mode}`}>
      <div className="process-flow-cell source">
        <img src={visual.source} alt={`${abilityPresentation[goal].headline}原图示例`} />
        <small>{visual.sourceLabel}</small>
      </div>
      <span className="process-flow-arrow">→</span>
      <div className={`process-flow-results ${visual.mode}`}>
        {visual.results.map((image, index) => (
          <div className="process-flow-cell result" key={`${goal}-result-${index}`}>
            <img src={image} alt={`${abilityPresentation[goal].headline}结果示例 ${index + 1}`} />
            <small>{index === 0 ? visual.resultLabel : `候选 ${index + 1}`}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

const realBusinessAbilityConfig: Partial<Record<BatchGoalId, { businessKey: string; label: string }>> = {
  extend: { businessKey: "outpaint", label: "可真实生成" },
  extract: { businessKey: "pattern_extract", label: "可真实生成" },
  variation: { businessKey: "fission", label: "可真实生成" },
  seamless2: { businessKey: "seamless", label: "可真实生成" },
  seamless4: { businessKey: "seamless", label: "可真实生成" },
};

const pendingBusinessAbilityReason: Partial<Record<BatchGoalId, string>> = {};
type ProcessTaskWithWallet = ProcessTask & { wallet?: ClientBootstrap["wallet"] };
const processCreditCostByAbility: Record<BatchGoalId, number> = {
  clean: 1,
  extend: 2,
  extract: 3,
  variation: 3,
  seamless2: 2,
  seamless4: 3,
};

export default function ProcessPage() {
  const { state, navigate, dispatch, activeUserId, isAuthenticated } = useApp();
  const [activeAbilityId, setActiveAbilityId] = useState<BatchGoalId | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [uploadedCount, setUploadedCount] = useState(0);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [sizeMode, setSizeMode] = useState<SizeMode>("preset");
  const [selectedSize, setSelectedSize] = useState("");
  const [customSize, setCustomSize] = useState({ width: "1800", height: "1800" });
  const [variationStrength, setVariationStrength] = useState(60);
  const [outputCount, setOutputCount] = useState("4");
  const [lockStrategy, setLockStrategy] = useState("颜色和结构");
  const [extendPadding, setExtendPadding] = useState(extendPresetPaddings.四周等距);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const submitLockRef = useRef(false);

  const activeAbility = useMemo(
    () => abilities.find((ability) => ability.id === activeAbilityId) ?? null,
    [activeAbilityId]
  );
  const sameStyleWork = state.sameStyleWork?.kind === "图片作品" ? state.sameStyleWork : null;

  const activePresentation = activeAbilityId ? abilityPresentation[activeAbilityId] : null;
  const activeRealConfig = activeAbilityId ? realBusinessAbilityConfig[activeAbilityId] : null;
  const activeSizeLabel =
    activeAbilityId === "extend"
      ? `上${extendPadding.top}px / 右${extendPadding.right}px / 下${extendPadding.bottom}px / 左${extendPadding.left}px`
      : sizeMode === "custom"
      ? `${customSize.width || "-"}×${customSize.height || "-"}`
      : selectedSize || activePresentation?.sizePresets[0] || "默认尺寸";
  const activeOptionLabel =
    activeAbilityId === "variation"
      ? selectedPreset || "默认裂变"
      : activeAbilityId === "extend"
        ? selectedPreset || "自定义扩图"
        : activeAbilityId === "clean"
          ? selectedPreset || "默认标准化"
          : activeAbility?.title || "图片处理";
  const canSubmit =
    uploaded &&
    (activeAbilityId === "extend"
      ? Object.values(extendPadding).some((value) => Number(value) > 0)
      : sizeMode === "preset" || (Number(customSize.width) > 0 && Number(customSize.height) > 0));
  const estimatedCreditCost = activeAbilityId ? uploadedCount * processCreditCostByAbility[activeAbilityId] : 0;
  const creditBalanceAfterSubmit = state.aiCredits - estimatedCreditCost;

  const openAbility = (goal: BatchGoalId) => {
    const presentation = abilityPresentation[goal];
    setActiveAbilityId(goal);
    setUploaded(false);
    setUploadedCount(0);
    setSelectedFiles([]);
    setSubmitError("");
    setSelectedPreset(presentation.presets[0] ?? "");
    setSelectedSize(presentation.sizePresets[0] ?? "");
    setCustomSize(presentation.defaultCustomSize);
    setSizeMode("preset");
    setVariationStrength(goal === "variation" ? 60 : 50);
    setOutputCount(goal === "variation" ? "4" : "1");
    setLockStrategy("颜色和结构");
    setExtendPadding(extendPresetPaddings[presentation.presets[0]] ?? extendPresetPaddings.四周等距);
    window.setTimeout(() => window.scrollTo({ top: 0, behavior: "smooth" }), 0);
  };

  const closeAbility = () => {
    setActiveAbilityId(null);
    setUploaded(false);
    setUploadedCount(0);
    setSelectedFiles([]);
    setSubmitError("");
  };

  const handleFilesSelected = useCallback((files: File[]) => {
    setUploaded(true);
    setUploadedCount(files.length);
    setSelectedFiles(files);
    setSubmitError("");
  }, []);

  const startProcessing = async () => {
    if (!activeAbility || !activeAbilityId || !activePresentation || !canSubmit || submitting || submitLockRef.current) return;
    if (!isAuthenticated) {
      setSubmitError("请先登录，任务结果会保存到你的素材库。");
      window.setTimeout(() => navigate("account"), 600);
      return;
    }
    if (estimatedCreditCost > state.aiCredits) {
      setSubmitError(`积分不足：本次需要 ${estimatedCreditCost} 积分，当前可用 ${state.aiCredits} 积分。请先充值后再提交。`);
      window.setTimeout(() => navigate("wallet"), 900);
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setSubmitError("");
    try {
      const uploads = selectedFiles.length > 0
        ? await Promise.all(selectedFiles.map((file) => uploadClientImage(file, activeUserId)))
        : [];
      const inputImages = uploads.map((item) => item.url);
      if (!activeRealConfig) {
        throw new Error(`${activeAbility.title}暂未开放真实生成。本版本不会返回本地假结果，开放后可在这里直接提交。`);
      }
      const task = await submitRealBusinessTask(inputImages, activeRealConfig);
      dispatch({ type: "ADD_PROCESS_TASK", task });
      if (task.wallet) dispatch({ type: "SET_WALLET", wallet: task.wallet });
      if (task.resultImages?.length) {
        const createdAt = task.completedAt || new Date().toLocaleString("zh-CN");
        dispatch({
          type: "ADD_ASSETS",
          assets: task.resultImages.map((image, index) => ({
            id: task.outputAssetIds[index] || `asset-${task.id}-${index}`,
            type: task.resultType || activePresentation.resultType,
            title: `${assetTypeLabels[task.resultType || activePresentation.resultType]} · ${activeAbility.title} ${String(index + 1).padStart(2, "0")}`,
            url: image,
            thumbnailUrl: image,
            source: activeAbility.title,
            createdAt,
            selected: false,
            favorite: false,
            visibility: "private" as const,
            batchId: task.id,
          })),
        });
      }
      navigate("tasks");
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "任务提交失败，请稍后重试。");
    } finally {
      submitLockRef.current = false;
      setSubmitting(false);
    }
  };

  const applyExtendPreset = (preset: string) => {
    setSelectedPreset(preset);
    setExtendPadding(extendPresetPaddings[preset] ?? extendPresetPaddings.四周等距);
  };

  const updateExtendPadding = (side: keyof typeof extendPadding, value: string) => {
    setSelectedPreset("自定义扩图");
    setExtendPadding((padding) => ({ ...padding, [side]: value }));
  };

  const submitRealBusinessTask = async (
    inputImages: string[],
    config: { businessKey: string; label: string }
  ): Promise<ProcessTaskWithWallet> => {
    if (!activeAbilityId) throw new Error("请先选择图片处理能力。");
    const perImageOutputCount = activeAbilityId === "variation" ? Math.max(1, Number(outputCount) || 1) : 1;
    const expectedOutputCount = Math.max(inputImages.length, 1) * perImageOutputCount;

    const padding = {
      expand_top: parsePixel(extendPadding.top),
      expand_right: parsePixel(extendPadding.right),
      expand_bottom: parsePixel(extendPadding.bottom),
      expand_left: parsePixel(extendPadding.left),
    };
    const extendPayload =
      activeAbilityId === "extend"
        ? {
            preserveOriginal: true,
            ...padding,
          }
        : {};
    const outputSize =
      sizeMode === "custom"
        ? { width: parsePixel(customSize.width), height: parsePixel(customSize.height) }
        : parseSizePreset(selectedSize || activeSizeLabel);
    const normalizedOutputSize =
      outputSize.width && outputSize.height ? outputSize : {};
    const seamlessPayload =
      activeAbilityId === "seamless2" || activeAbilityId === "seamless4"
        ? {
            patternType: activeAbilityId === "seamless2" ? "twoway" : "seamless",
            mode: activeAbilityId === "seamless2" ? "twoway" : "seamless",
          }
        : {};
    return createClientProcessTask({
      userId: activeUserId,
      type: activeAbilityId,
      abilityTitle: activeAbility?.title || activeOptionLabel,
      outputLabel: activePresentation?.resultType === "pattern" ? "花纹素材" : "处理结果",
      inputImages,
      optionLabel: activeOptionLabel,
      sizeLabel: activeSizeLabel,
      outputCount: expectedOutputCount,
      params: {
        realBusinessRun: true,
        businessKey: config.businessKey,
        candidateCount: perImageOutputCount,
        expectedOutputCount,
        costCredits: estimatedCreditCost,
        businessRunIds: [],
        resultImages: [],
        submitMode: `real-${config.businessKey}`,
        requestPayloadTemplate: {
          prompt:
            activeAbilityId === "extend"
              ? "自然补全外扩区域，保持原图主体、颜色、纹理和构图关系一致；不要改动原图核心内容。"
              : activeAbilityId === "extract"
                ? "提取图中可复用花纹和图案，去除拍摄背景、模特、透视和无关物体，保留可用于 POD 产品的平面设计素材。"
                : activeAbilityId === "seamless2"
                  ? "生成左右无缝连续图，适配杯身环绕，避免明显接缝。"
                  : activeAbilityId === "seamless4"
                    ? "生成上下左右无缝连续图，适配布料、壁纸和可无限平铺纹理。"
                    : "基于参考图生成同系列图案，保持主体风格、色彩气质和商业可用性，避免直接复制原图细节。",
          version: undefined,
          quality: "preview",
          size: activeSizeLabel,
          ...normalizedOutputSize,
          bili: activeAbilityId === "variation" ? variationStrength : undefined,
          variation_strength: activeAbilityId === "variation" ? String(variationStrength) : undefined,
          outputCount: 1,
          ...extendPayload,
          ...seamlessPayload,
          inputs: {
            ...extendPayload,
            ...seamlessPayload,
            ...normalizedOutputSize,
            optionLabel: activeOptionLabel,
            sizeLabel: activeSizeLabel,
            sizeMode,
            selectedSize,
            customSize,
            variationStrength,
            candidateCount: perImageOutputCount,
            lockStrategy,
          },
        },
        extendPadding,
        variationStrength,
        lockStrategy,
        sizeMode,
        selectedSize,
        customSize,
      },
    });
  };

  const renderAbilityControls = () => {
    if (!activeAbilityId) return null;

    if (activeAbilityId === "variation") {
      return (
        <>
          <div className="process-control-field wide">
            <div>
              <strong>裂变幅度</strong>
              <span>数值越高，画面变化越大；做系列款通常从 50-65 开始。</span>
            </div>
            <div className="range-control">
              <input
                type="range"
                min="20"
                max="90"
                step="5"
                value={variationStrength}
                onChange={(event) => setVariationStrength(Number(event.target.value))}
              />
              <b>{variationStrength}%</b>
            </div>
          </div>
          <label className="process-control-field">
            <span>输出组数</span>
            <select value={outputCount} onChange={(event) => setOutputCount(event.target.value)}>
              <option value="4">4 张候选</option>
              <option value="6">6 张候选</option>
              <option value="8">8 张候选</option>
            </select>
          </label>
          <label className="process-control-field">
            <span>锁定策略</span>
            <select value={lockStrategy} onChange={(event) => setLockStrategy(event.target.value)}>
              <option value="颜色和结构">锁定颜色和结构</option>
              <option value="只锁定结构">只锁定结构</option>
              <option value="自由探索">自由探索</option>
            </select>
          </label>
        </>
      );
    }

    if (activeAbilityId === "extract") {
      return null;
    }

    if (activeAbilityId === "seamless2" || activeAbilityId === "seamless4") {
      return null;
    }

    if (activeAbilityId === "extend") {
      return null;
    }

    return (
      <>
        <label className="process-control-field">
          <span>DPI 标记</span>
          <select defaultValue="300">
            <option value="150">150 DPI，常规输出</option>
            <option value="300">300 DPI，生产优先</option>
          </select>
        </label>
        <label className="process-control-field">
          <span>输出格式</span>
          <select defaultValue="png">
            <option value="png">PNG，适合生产</option>
            <option value="webp">WebP，适合预览</option>
          </select>
        </label>
      </>
    );
  };

  if (!activeAbility || !activeAbilityId || !activePresentation) {
    return (
      <main className="page-shell process-page process-capability-page">
        {sameStyleWork && (
          <section className="same-style-draft-banner">
            <img src={sameStyleWork.image} alt={sameStyleWork.title} />
            <div>
              <small>同款草稿</small>
              <strong>{sameStyleWork.title}</strong>
              <p>来自 {sameStyleWork.author} 的公开图片作品。你可以在这里选择花纹提取、裂变、连续图或扩图能力，生成结果会进入自己的素材库。</p>
            </div>
            <button className="secondary" onClick={() => dispatch({ type: "SET_SAME_STYLE_WORK", work: null })}>
              清除草稿
            </button>
          </section>
        )}

        <PageHeader
          eyebrow="图片处理"
          title="把图片变成可以继续创作的素材。"
          desc="提取花纹、扩展画面或生成连续图。处理结果会保存到你的素材库。"
        />

        <section className="process-capability-hero">
          <div>
            <span>选择一种处理方式</span>
            <strong>先把喜欢的图，变成更好用的设计素材。</strong>
            <p>每种能力只解决一个问题。选择后再上传图片和调整参数，不需要先理解复杂的生产术语。</p>
          </div>
          <img src="/demo/market/podi-ai-workflow.webp" alt="图片批处理示例" />
        </section>

        <section className="process-capability-grid" aria-label="图片批处理能力">
          {visibleAbilities.map((ability) => {
            const Icon = ability.icon;
            const presentation = abilityPresentation[ability.id];
            const realConfig = realBusinessAbilityConfig[ability.id];
            return (
              <button
                key={ability.id}
                className={`process-capability-card${realConfig ? "" : " unavailable"}`}
                onClick={() => realConfig && openAbility(ability.id)}
                disabled={!realConfig}
                aria-disabled={!realConfig}
              >
                <div className="process-capability-visual">
                  {renderCapabilityVisual(ability.id)}
                  <span className="process-capability-badge">
                    <Icon size={18} />
                    {presentation.eyebrow}
                  </span>
                </div>
                <div className="process-capability-body">
                  <small>{ability.cost}</small>
                  <strong>{ability.title}</strong>
                  <p>{presentation.entryCopy}</p>
                  <div className="process-card-tags">
                    <em>{presentation.bestFor.slice(0, 2).join(" · ")}</em>
                  </div>
                  <div className={realConfig ? "process-card-runtime real" : "process-card-runtime pending"}>
                    {realConfig?.label ?? pendingBusinessAbilityReason[ability.id] ?? "待开放"}
                  </div>
                  <span className="process-card-action">
                    开始处理 <ArrowRight size={15} />
                  </span>
                </div>
              </button>
            );
          })}
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell process-page process-run-page">
      <button className="process-back-link" onClick={closeAbility}>
        <ArrowLeft size={16} />
        返回图片处理能力
      </button>

      <PageHeader
        eyebrow={activePresentation.eyebrow}
        title={activePresentation.headline}
        desc={activePresentation.entryCopy}
      />

      <section className="process-run-layout">
        <div className="process-run-main">
          <section className="process-upload-section">
            <ImageUploader compact onFilesSelected={handleFilesSelected} />
            {submitError && <p className="process-submit-error">{submitError}</p>}
          </section>

          <section className="process-config-section">
            <div className="process-compact-head">
              <strong>{activeAbilityId === "extend" ? "扩图范围" : "输出尺寸"}</strong>
            </div>

            {activeAbilityId === "extend" ? (
              <div className="process-setting-block">
                <div className="setting-block-head">
                  <strong>扩图预设</strong>
                  <span>0 表示不扩</span>
                </div>
                <div className="process-preset-row strategy">
                  {activePresentation.presets.map((preset) => (
                    <button
                      key={preset}
                      className={selectedPreset === preset ? "active" : ""}
                      onClick={() => applyExtendPreset(preset)}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <div className="extend-direction-panel">
                  <label className="extend-side top">
                    <span>上</span>
                    <input value={extendPadding.top} type="number" min="0" onChange={(event) => updateExtendPadding("top", event.target.value)} />
                    <em>px</em>
                  </label>
                  <label className="extend-side left">
                    <span>左</span>
                    <input value={extendPadding.left} type="number" min="0" onChange={(event) => updateExtendPadding("left", event.target.value)} />
                    <em>px</em>
                  </label>
                  <div className="extend-origin-preview">
                    <strong>原图</strong>
                    <span>主体保持不变</span>
                  </div>
                  <label className="extend-side right">
                    <span>右</span>
                    <input value={extendPadding.right} type="number" min="0" onChange={(event) => updateExtendPadding("right", event.target.value)} />
                    <em>px</em>
                  </label>
                  <label className="extend-side bottom">
                    <span>下</span>
                    <input value={extendPadding.bottom} type="number" min="0" onChange={(event) => updateExtendPadding("bottom", event.target.value)} />
                    <em>px</em>
                  </label>
                </div>
              </div>
            ) : (
              <div className="process-setting-block">
                <div className="setting-block-head">
                  <strong>输出尺寸</strong>
                </div>
                <div className="size-mode-tabs">
                  <button className={sizeMode === "preset" ? "active" : ""} onClick={() => setSizeMode("preset")}>
                    常用尺寸
                  </button>
                  <button className={sizeMode === "custom" ? "active" : ""} onClick={() => setSizeMode("custom")}>
                    自定义尺寸
                  </button>
                </div>
                {sizeMode === "preset" ? (
                  <div className="process-preset-row">
                    {activePresentation.sizePresets.map((preset) => (
                      <button
                        key={preset}
                        className={selectedSize === preset ? "active" : ""}
                        onClick={() => setSelectedSize(preset)}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="custom-size-row">
                    <label>
                      <span>宽度 px</span>
                      <input
                        type="number"
                        min="256"
                        value={customSize.width}
                        onChange={(event) => setCustomSize((size) => ({ ...size, width: event.target.value }))}
                      />
                    </label>
                    <label>
                      <span>高度 px</span>
                      <input
                        type="number"
                        min="256"
                        value={customSize.height}
                        onChange={(event) => setCustomSize((size) => ({ ...size, height: event.target.value }))}
                      />
                    </label>
                  </div>
                )}
              </div>
            )}

            {(activeAbilityId === "variation" || activeAbilityId === "clean") && (
              <div className="process-setting-block">
                <div className="setting-block-head">
                  <strong>{activeAbilityId === "variation" ? "裂变策略" : "标准化选项"}</strong>
                </div>
                <div className="process-preset-row strategy">
                  {activePresentation.presets.map((preset) => (
                    <button
                      key={preset}
                      className={selectedPreset === preset ? "active" : ""}
                      onClick={() => setSelectedPreset(preset)}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <div className="process-controls-grid">{renderAbilityControls()}</div>
              </div>
            )}

          </section>

        </div>

        <aside className="process-run-aside">
          <div className="process-job-summary">
            <strong>本次任务</strong>
            <span>
              输入 <b>{uploaded ? `${uploadedCount} 张图片` : "等待上传"}</b>
            </span>
            <span>
              {activeAbilityId === "extend" ? "扩图" : "尺寸"} <b>{activeSizeLabel}</b>
            </span>
            <span>
              参数 <b>{activeOptionLabel}</b>
            </span>
            <span>
              状态 <b>{submitting ? "正在上传并提交" : uploaded ? "可提交" : "等待上传"}</b>
            </span>
            <span>
              积分 <b>{uploaded ? `${estimatedCreditCost} 积分` : "待计算"}</b>
            </span>
            {uploaded && (
              <p className={creditBalanceAfterSubmit < 0 ? "process-credit-note warning" : "process-credit-note"}>
                当前可用 {state.aiCredits} 积分，本次预计扣 {estimatedCreditCost} 积分
                {creditBalanceAfterSubmit >= 0 ? `，提交后剩余 ${creditBalanceAfterSubmit} 积分。` : "，积分不足。"}
              </p>
            )}
            <p>完成后在任务中心查看结果。</p>
            <button className="primary full process-aside-submit" disabled={!canSubmit || submitting} onClick={startProcessing}>
              {submitting ? "正在提交" : "提交任务"}
              <ArrowRight size={16} />
            </button>
          </div>

          <div className="process-ability-mini">
            <strong>{activeAbility.title}</strong>
            <span>输出：{activeAbility.output}</span>
            <span>{activeAbility.cost}</span>
            <em>{activeRealConfig?.label ?? "暂未开放"}</em>
          </div>
        </aside>
      </section>
    </main>
  );
}
