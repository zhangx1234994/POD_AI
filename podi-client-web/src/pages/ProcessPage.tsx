/**
 * 图片批处理页 — 能力入口 → 单能力批量处理
 */
import { useCallback, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import ImageUploader from "../components/ImageUploader";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import { demo } from "../data/mock-data";
import { abilities, assetTypeLabels } from "../utils/constants";
import {
  clientAssetToAssetItem,
  createClientAsset,
  hasAccessToken,
  hasApiKey,
  fetchClientWallet,
  getBusinessRun,
  submitBusinessRun,
  uploadClientImage,
} from "../api";
import type { ApiResult, AssetItem, AssetType, BatchGoalId } from "../types";

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
    productFits: ["杯子", "T 恤", "毛毯", "抱枕"],
    params: [
      { label: "输出尺寸", value: "默认 1800×1800" },
      { label: "模型", value: "默认花纹提取" },
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
      { label: "路由配置", value: "智能风险路由" },
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

const demoImages = [demo("floral-pattern"), demo("geometric-pattern"), demo("stripe-pattern"), demo("floral-pattern")];

const extendPresetPaddings: Record<string, { top: string; right: string; bottom: string; left: string }> = {
  四周等距: { top: "256", right: "256", bottom: "256", left: "256" },
  只扩上方: { top: "512", right: "0", bottom: "0", left: "0" },
  左右扩宽: { top: "0", right: "512", bottom: "0", left: "512" },
  上下扩高: { top: "512", right: "0", bottom: "512", left: "0" },
};

const realBusinessEntries: Partial<Record<BatchGoalId, string>> = {
  extend: "/api/business/outpaint/runs",
  extract: "/api/business/pattern-extract/runs",
  variation: "/api/business/fission/runs",
  seamless2: "/api/business/seamless/runs",
  seamless4: "/api/business/seamless/runs",
};

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function parsePixel(value: string) {
  const numberValue = Number.parseInt(value, 10);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : undefined;
}

function parseSelectedSize(mode: SizeMode, selectedSize: string, customSize: { width: string; height: string }) {
  if (mode === "custom") {
    return {
      width: parsePixel(customSize.width),
      height: parsePixel(customSize.height),
    };
  }
  const match = selectedSize.match(/(\d{3,5})\s*×\s*(\d{3,5})/);
  if (!match) return {};
  return {
    width: parsePixel(match[1]),
    height: parsePixel(match[2]),
  };
}

function normalizeBusinessStatus(status: string | undefined) {
  const value = String(status || "").toLowerCase();
  if (["succeeded", "success", "completed", "done"].includes(value)) return "completed";
  if (["failed", "error", "cancelled", "canceled", "timeout"].includes(value)) return "failed";
  if (["running", "processing", "in_progress", "submitted"].includes(value)) return "processing";
  return "pending";
}

function mapWalletForState(wallet: Awaited<ReturnType<typeof fetchClientWallet>>) {
  return {
    aiCredits: wallet.pointBalance,
    productCouponCount: wallet.productCouponCount,
    coupons: wallet.productCoupons.map((coupon) => ({
      id: coupon.id,
      type: "product" as const,
      name: coupon.name || "产品券",
      scope: coupon.businessKey || coupon.packageKey,
      value: `${coupon.remainingUnits} ${coupon.unitName || "张"}`,
      status: coupon.remainingUnits > 0 ? ("available" as const) : ("used" as const),
      expiresAt: coupon.expiresAt || "长期有效",
      source: coupon.source || "账户权益",
    })),
    ledger: wallet.ledger.map((entry) => ({
      id: entry.id,
      time: entry.createdAt || "",
      action: entry.description || "账户变动",
      amount: entry.points,
      note: entry.traceId || entry.taskId || "",
    })),
  };
}

async function pollBusinessRun(runId: string): Promise<ApiResult> {
  for (let index = 0; index < 80; index += 1) {
    const result = await getBusinessRun(runId);
    const status = normalizeBusinessStatus(result.status);
    if (!result.ok || status === "failed" || status === "completed") {
      return result;
    }
    await wait(index < 6 ? 1800 : 3200);
  }
  return {
    ok: false,
    runId,
    status: "timeout",
    imageUrls: [],
    videoUrls: [],
    error: "任务轮询超时，请在任务中心稍后刷新或到管理端查看 runId。",
  };
}

export default function ProcessPage() {
  const { state, navigate, dispatch } = useApp();
  const [activeAbilityId, setActiveAbilityId] = useState<BatchGoalId | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [uploadedCount, setUploadedCount] = useState(0);
  const [uploadedAssets, setUploadedAssets] = useState<AssetItem[]>([]);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "ready" | "error">("idle");
  const [uploadMessage, setUploadMessage] = useState("");
  const [selectedPreset, setSelectedPreset] = useState("");
  const [sizeMode, setSizeMode] = useState<SizeMode>("preset");
  const [selectedSize, setSelectedSize] = useState("");
  const [customSize, setCustomSize] = useState({ width: "1800", height: "1800" });
  const [variationStrength, setVariationStrength] = useState(60);
  const [outputCount, setOutputCount] = useState("4");
  const [lockStrategy, setLockStrategy] = useState("颜色和结构");
  const [extendPadding, setExtendPadding] = useState(extendPresetPaddings.四周等距);

  const activeAbility = useMemo(
    () => abilities.find((ability) => ability.id === activeAbilityId) ?? null,
    [activeAbilityId]
  );
  const sameStyleWork = state.sameStyleWork?.kind === "图片作品" ? state.sameStyleWork : null;

  const activePresentation = activeAbilityId ? abilityPresentation[activeAbilityId] : null;
  const UploadStatusIcon = uploadStatus === "error" ? AlertCircle : CheckCircle2;
  const businessApiReady = hasAccessToken() || hasApiKey();
  const supportsRealBusinessRun = activeAbilityId ? Boolean(realBusinessEntries[activeAbilityId]) : false;
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
          : "默认处理";
  const canSubmit =
    uploaded &&
    businessApiReady &&
    supportsRealBusinessRun &&
    (activeAbilityId === "extend"
      ? Object.values(extendPadding).some((value) => Number(value) > 0)
      : sizeMode === "preset" || (Number(customSize.width) > 0 && Number(customSize.height) > 0));

  const refreshWallet = useCallback(async () => {
    if (!hasAccessToken()) return;
    try {
      const wallet = await fetchClientWallet();
      dispatch({ type: "SET_CLIENT_WALLET", ...mapWalletForState(wallet) });
    } catch {
      // Wallet refresh is best-effort; task state should still finish visibly.
    }
  }, [dispatch]);

  const openAbility = (goal: BatchGoalId) => {
    const presentation = abilityPresentation[goal];
    setActiveAbilityId(goal);
    setUploaded(false);
    setUploadedCount(0);
    setUploadedAssets([]);
    setUploadStatus("idle");
    setUploadMessage("");
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
    setUploadedAssets([]);
    setUploadStatus("idle");
    setUploadMessage("");
  };

  const handleFilesSelected = useCallback(async (files: File[]) => {
    setUploadedAssets([]);
    setUploadMessage("");
    setUploaded(true);
    setUploadedCount(files.length);

    if (!businessApiReady) {
      setUploadStatus("error");
      setUploadMessage("请先登录账户，再提交真实中台任务。");
      return;
    }

    setUploaded(false);
    setUploadStatus("uploading");
    setUploadMessage(`正在保存 ${files.length} 张图片`);

    try {
      const savedAssets = await Promise.all(
        files.map(async (file) => {
          const upload = await uploadClientImage(file);
          if (hasAccessToken()) {
            const asset = await createClientAsset({
              assetType: "input_image",
              url: upload.url,
              contentType: file.type || "application/octet-stream",
              fileName: file.name,
              inputTags: [activeAbilityId || "process"],
              metadata: {
                size: file.size,
                objectKey: upload.objectKey,
                uploadName: upload.name,
              },
            });
            return {
              ...clientAssetToAssetItem(asset),
              selected: true,
              source: "本次上传",
            };
          }
          return {
            id: `upload-${upload.objectKey}`,
            type: "original" as const,
            title: file.name || "上传图片",
            url: upload.url,
            thumbnailUrl: upload.url,
            createdAt: new Date().toLocaleString("zh-CN"),
            selected: true,
            source: "本次上传",
            favorite: false,
            visibility: "private" as const,
          };
        })
      );

      dispatch({ type: "ADD_ASSETS", assets: savedAssets });
      setUploadedAssets(savedAssets);
      setUploaded(true);
      setUploadedCount(savedAssets.length);
      setUploadStatus("ready");
      setUploadMessage(`已保存 ${savedAssets.length} 张图片`);
    } catch (error) {
      setUploaded(false);
      setUploadStatus("error");
      setUploadMessage(error instanceof Error ? error.message : "图片保存失败");
    }
  }, [activeAbilityId, dispatch]);

  const buildBusinessPayload = (asset: AssetItem, requestIndex: number) => {
    if (!activeAbilityId) return null;
    const size = parseSelectedSize(sizeMode, selectedSize, customSize);
    const basePayload: Record<string, unknown> = {
      imageUrl: asset.url,
      source: "podi-client-web",
      channel: "client-web",
      traceId: `client-${Date.now()}-${requestIndex}`,
      requestId: `podi-client-${Date.now()}-${requestIndex}`,
      metadata: {
        clientTaskType: activeAbilityId,
        optionLabel: activeOptionLabel,
        sizeLabel: activeSizeLabel,
      },
    };

    if (activeAbilityId === "extract") {
      return {
        ...basePayload,
        ...size,
        batch: 1,
        timeout: 600,
      };
    }

    if (activeAbilityId === "extend") {
      return {
        ...basePayload,
        prompt: "在原图基础上自然补全外扩区域，保持主体、纹理走势和色彩密度一致。",
        expand_top: parsePixel(extendPadding.top) || 0,
        expand_right: parsePixel(extendPadding.right) || 0,
        expand_bottom: parsePixel(extendPadding.bottom) || 0,
        expand_left: parsePixel(extendPadding.left) || 0,
        timeout: 600,
      };
    }

    if (activeAbilityId === "variation") {
      return {
        ...basePayload,
        ...size,
        mode: "fission",
        bili: `${variationStrength}%`,
        profile: "pattern_risk_routed_v4",
        reference_lock: lockStrategy === "自由探索" ? 0.3 : lockStrategy === "只锁定结构" ? 0.46 : 0.42,
        color_lock: lockStrategy === "自由探索" ? 0.55 : lockStrategy === "只锁定结构" ? 0.65 : 0.86,
        timeout: 600,
      };
    }

    if (activeAbilityId === "seamless2" || activeAbilityId === "seamless4") {
      const patternType = activeAbilityId === "seamless2" ? "twoway" : "seamless";
      return {
        ...basePayload,
        ...size,
        patternType,
        pattern_type: patternType,
        prompt:
          activeAbilityId === "seamless2"
            ? "保持花纹主体、颜色和纹理密度，让左右边缘自然连续，适合杯身环绕贴图。"
            : "保持花纹主体、颜色和纹理密度，让上下左右边缘自然连续，适合布料和壁纸平铺。",
        timeout: 600,
      };
    }

    return null;
  };

  const startProcessing = async () => {
    if (!activeAbility || !activeAbilityId || !activePresentation || !canSubmit) return;
    const endpoint = realBusinessEntries[activeAbilityId];
    if (!endpoint) {
      setUploadStatus("error");
      setUploadMessage("这个能力还没有真实业务入口，不能用演示数据代替。");
      return;
    }

    const sourceAssets = uploadedAssets.filter((asset) => asset.url);
    if (sourceAssets.length === 0) {
      setUploadStatus("error");
      setUploadMessage("图片还没有保存到 OSS，不能提交真实业务任务。请重新上传。");
      return;
    }

    const nextTaskId = `PODI-${Date.now().toString().slice(-8)}`;
    const createdAt = new Date().toLocaleString("zh-CN");
    const variationRunsPerImage = activeAbilityId === "variation" ? Number(outputCount) : 1;
    const taskResultCount = sourceAssets.length * Math.max(1, variationRunsPerImage);
    const taskInputImages = sourceAssets.slice(0, 6).map((asset) => asset.thumbnailUrl);

    dispatch({
      type: "ADD_PROCESS_TASK",
      task: {
        id: nextTaskId,
        runIds: [],
        type: activeAbilityId,
        status: "pending",
        inputAssetIds: sourceAssets.map((asset) => asset.id),
        outputAssetIds: [],
        createdAt,
        abilityTitle: activeAbility.title,
        outputLabel: activeAbility.output,
        inputCount: sourceAssets.length,
        resultCount: taskResultCount,
        optionLabel: activeOptionLabel,
        sizeLabel: activeSizeLabel,
        resultType: activePresentation.resultType,
        inputImages: taskInputImages,
        resultImages: [],
        executionMode: "business",
      },
    });

    navigate("tasks");

    try {
      const requests = sourceAssets.flatMap((asset) =>
        Array.from({ length: Math.max(1, variationRunsPerImage) }).map((_, index) => ({
          asset,
          payload: buildBusinessPayload(asset, index),
        }))
      );
      const invalidRequest = requests.find((item) => !item.payload);
      if (invalidRequest) {
        throw new Error("任务参数生成失败，请检查能力配置。");
      }

      dispatch({
        type: "UPDATE_PROCESS_TASK",
        id: nextTaskId,
        patch: { status: "processing" },
      });

      const submitted = [];
      for (const [index, request] of requests.entries()) {
        const submitResult = await submitBusinessRun(endpoint, request.payload || {});
        if (!submitResult.ok || !submitResult.runId) {
          throw new Error(submitResult.error || "业务任务提交失败，未返回 runId。");
        }
        submitted.push(submitResult.runId);
        dispatch({
          type: "UPDATE_PROCESS_TASK",
          id: nextTaskId,
          patch: { runIds: submitted },
        });
        if (index < requests.length - 1) await wait(350);
      }

      const finalResults = await Promise.all(submitted.map((runId) => pollBusinessRun(runId)));
      const failed = finalResults.find((result) => !result.ok || normalizeBusinessStatus(result.status) === "failed");
      if (failed) {
        throw new Error(failed.error || `业务任务失败：${failed.runId || "unknown run"}`);
      }

      const resultImages = Array.from(new Set(finalResults.flatMap((result) => result.imageUrls))).slice(0, 24);
      if (resultImages.length === 0) {
        throw new Error("业务任务已返回，但没有拿到图片结果 URL。");
      }

      const completedAt = new Date().toLocaleString("zh-CN");
      const outputAssets = resultImages.map((image, index) => ({
        id: `business-${nextTaskId}-${index}`,
        type: activePresentation.resultType,
        title: `${assetTypeLabels[activePresentation.resultType]} · ${activeAbility.title} ${String(index + 1).padStart(2, "0")}`,
        url: image,
        thumbnailUrl: image,
        source: activeAbility.title,
        createdAt: completedAt,
        selected: false,
        favorite: false,
        visibility: "private" as const,
        batchId: nextTaskId,
      }));

      dispatch({
        type: "ADD_ASSETS",
        assets: outputAssets,
      });
      dispatch({
        type: "UPDATE_PROCESS_TASK",
        id: nextTaskId,
        patch: {
          status: "completed",
          completedAt,
          outputAssetIds: outputAssets.map((asset) => asset.id),
          resultImages,
        },
      });
      await refreshWallet();
    } catch (error) {
      dispatch({
        type: "UPDATE_PROCESS_TASK",
        id: nextTaskId,
        patch: {
          status: "failed",
          completedAt: new Date().toLocaleString("zh-CN"),
          errorMessage: error instanceof Error ? error.message : "真实业务任务执行失败",
        },
      });
      await refreshWallet();
    }
  };

  const passiveAbilityNote =
    activeAbilityId === "extract"
      ? "花纹提取使用默认花纹提取模型。这里不需要选择 LoRA，先确定输出尺寸即可。"
      : activeAbilityId === "seamless2"
        ? "两方连续固定处理左右接缝。核心决策是输出尺寸，适合杯身、瓶身这类横向环绕产品。"
        : activeAbilityId === "seamless4"
          ? "四方连续固定处理上下左右平铺。核心决策是输出尺寸，适合布料、壁纸和大面积印花。"
          : "";
  const configIntro =
    activeAbilityId === "extend"
      ? "选择扩图预设，或直接填写上、右、下、左各扩多少像素。"
      : activeAbilityId === "variation"
        ? "先确定输出尺寸，再设置裂变幅度、候选张数和锁定策略。"
        : activeAbilityId === "clean"
          ? "先确定输出尺寸，再选择标准化方式、DPI 和输出格式。"
          : "先确定输出尺寸。常用尺寸后续会跟产品模板和设计面数据联动。";

  const applyExtendPreset = (preset: string) => {
    setSelectedPreset(preset);
    setExtendPadding(extendPresetPaddings[preset] ?? extendPresetPaddings.四周等距);
  };

  const updateExtendPadding = (side: keyof typeof extendPadding, value: string) => {
    setSelectedPreset("自定义扩图");
    setExtendPadding((padding) => ({ ...padding, [side]: value }));
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
          eyebrow="图片素材批量处理"
          title="先选能力，再批量处理。"
          desc="每个能力都有独立页面。只处理图片也可以，结果会进入素材库，不强制做产品。"
        />

        <section className="process-capability-hero">
          <div>
            <span>能力入口</span>
            <strong>选择处理能力</strong>
            <p>花纹提取、裂变、两方连续和四方连续分别解决不同生产问题。先选能力，后续上传、参数和结果都会围绕该能力展开。</p>
          </div>
          <img src="/demo/market/podi-ai-workflow.webp" alt="图片批处理示例" />
        </section>

        <section className="process-capability-grid" aria-label="图片批处理能力">
          {abilities.map((ability) => {
            const Icon = ability.icon;
            const presentation = abilityPresentation[ability.id];
            return (
              <button key={ability.id} className="process-capability-card" onClick={() => openAbility(ability.id)}>
                <div className="process-capability-visual">
                  <img src={presentation.cover} alt={`${ability.title} 示例`} />
                  <span>
                    <Icon size={18} />
                    {presentation.eyebrow}
                  </span>
                </div>
                <div className="process-capability-body">
                  <small>{ability.cost}</small>
                  <strong>{ability.title}</strong>
                  <p>{presentation.entryCopy}</p>
                  <div className="process-card-tags">
                    {presentation.bestFor.map((item) => (
                      <em key={item}>{item}</em>
                    ))}
                  </div>
                  <div className="process-card-scenes">
                    <b>适合</b>
                    <span>{presentation.productFits.join(" / ")}</span>
                  </div>
                  <div className="process-card-params">
                    {presentation.params.slice(0, 2).map((param) => (
                      <span key={param.label}>
                        <b>{param.label}</b>
                        {param.value}
                      </span>
                    ))}
                  </div>
                  <span className="process-card-action">
                    进入功能 <ArrowRight size={15} />
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
        desc={activePresentation.summary}
      />

      <section className="process-run-layout">
        <div className="process-run-main">
          <section className="process-upload-section">
            <div className="process-section-label">
              <small>STEP 1</small>
              <strong>上传要处理的图片</strong>
              <span>支持多张图片。当前只会调用「{activeAbility.title}」，不会混用其他能力。</span>
            </div>
            <ImageUploader onFilesSelected={handleFilesSelected} />
            {uploadStatus !== "idle" && (
              <div className={`process-upload-status ${uploadStatus}`} role={uploadStatus === "error" ? "alert" : "status"}>
                <UploadStatusIcon size={16} />
                <span>{uploadMessage || (uploadStatus === "uploading" ? "正在保存图片" : "图片已就绪")}</span>
              </div>
            )}
          </section>

          <section className="process-config-section">
            <div className="process-section-label">
              <small>STEP 2</small>
              <strong>设置本次处理参数</strong>
              <span>{configIntro}</span>
            </div>

            {activeAbilityId === "extend" ? (
              <div className="process-setting-block">
                <div className="setting-block-head">
                  <strong>扩图范围</strong>
                  <span>扩图是在原图基础上向四个方向补画面。填 0 表示该方向不扩。</span>
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
                  <span>可以沿用原图，也可以选常用产品尺寸或自定义像素。</span>
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
                  <span>{activeAbilityId === "variation" ? "控制裂变相似度、变化幅度和输出数量。" : "只做基础整理，不改变图片创意方向。"}</span>
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

            {passiveAbilityNote && <div className="process-ability-note">{passiveAbilityNote}</div>}
          </section>

          <section className="process-action-section">
            <div className="process-section-label compact">
              <small>STEP 3</small>
              <strong>提交批处理任务</strong>
              <span>
                {!businessApiReady
                  ? "请先登录账户，再提交真实中台任务。"
                  : !supportsRealBusinessRun
                    ? "这个能力还没有真实业务入口，暂不允许用演示结果代替。"
                    : !uploaded
                  ? "上传图片后即可提交任务。"
                  : `将使用「${activeAbility.title} / ${activeOptionLabel} / ${activeSizeLabel}」处理 ${uploadedCount} 张图片，结果会自动进入素材库。`}
              </span>
            </div>
            <button className="primary" disabled={!canSubmit} onClick={startProcessing}>
              提交真实任务
              <ArrowRight size={18} />
            </button>
          </section>
        </div>

        <aside className="process-run-aside">
          <div className="process-ability-summary">
            <span>当前能力</span>
            <strong>{activeAbility.title}</strong>
            <p>{activeAbility.desc}</p>
            <div>
              <em>输出：{activeAbility.output}</em>
              <em>{activeAbility.cost}</em>
            </div>
          </div>

          <div className="process-ability-checklist">
            <strong>适合处理</strong>
            {activePresentation.bestFor.map((item) => (
              <span key={item}>
                <CheckCircle2 size={14} />
                {item}
              </span>
            ))}
          </div>

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
              状态 <b>{uploadStatus === "uploading" ? "保存图片中" : uploaded ? "可提交" : "等待上传"}</b>
            </span>
            <p>提交后会创建中台业务 run，并在任务页轮询真实结果。</p>
          </div>
        </aside>
      </section>
    </main>
  );
}
