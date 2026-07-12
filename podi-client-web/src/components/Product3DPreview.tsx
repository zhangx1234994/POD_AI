import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ModelUvCalibration } from "../data/model-uv-calibrations";
import { doesMaterialMatchSurface, hasExplicitMaterialBindings } from "../data/model-material-bindings";

type Product3DPreviewProps = {
  productName: string;
  modelFile?: string | null;
  modelUrl: string | null;
  textureUrl: string | null;
  textureLabel: string;
  surfaceTextures?: SurfaceTextureAssignment[];
  expectedSurfaceCount?: number;
  onTextureLoadStateChange?: (state: { expected: number; loaded: number; failedSurfaceNames: string[] }) => void;
  surfaceName?: string;
  surfaceLabel: string;
  printWidth?: number | null;
  printHeight?: number | null;
  baseColor?: string;
  textureMode?: TexturePlacementMode;
  textureScale?: number;
  textureOffsetX?: number;
  textureOffsetY?: number;
};

type SurfaceTextureAssignment = {
  surfaceName: string;
  surfaceLabel: string;
  textureUrl: string;
  textureLabel: string;
  printWidth?: number | null;
  printHeight?: number | null;
  uvCalibration?: ModelUvCalibration | null;
};

type LoadedSurfaceTexture = SurfaceTextureAssignment & { texture: THREE.Texture };
type SurfaceTextureLoadResult =
  | { assignment: SurfaceTextureAssignment; texture: THREE.Texture; error?: undefined }
  | { assignment: SurfaceTextureAssignment; texture?: undefined; error: unknown };

type RenderState = "idle" | "loading" | "ready" | "unsupported" | "error";
type TexturePlacementMode = "wrap" | "fit" | "cover" | "decal";

type TextureCapableMaterial =
  | THREE.MeshStandardMaterial
  | THREE.MeshPhysicalMaterial
  | THREE.MeshBasicMaterial
  | THREE.MeshLambertMaterial
  | THREE.MeshPhongMaterial;

function canUseTexture(material: THREE.Material): material is TextureCapableMaterial {
  return "map" in material;
}

function canUseBaseColor(material: THREE.Material): material is TextureCapableMaterial & { color: THREE.Color } {
  return "color" in material && material.color instanceof THREE.Color;
}

function surfaceWantsHandle(surfaceName?: string, surfaceLabel?: string) {
  const key = `${surfaceName ?? ""} ${surfaceLabel ?? ""}`.toLowerCase();
  return key.includes("handle") || key.includes("handshank") || key.includes("shank") || key.includes("grip") || key.includes("把手") || key.includes("手柄");
}

function surfaceWantsBody(surfaceName?: string, surfaceLabel?: string) {
  return !surfaceWantsHandle(surfaceName, surfaceLabel);
}

function shouldApplyToSurface(
  material: THREE.Material,
  meshName: string,
  surfaceName?: string,
  surfaceLabel?: string
) {
  const key = `${material.name} ${meshName}`.toLowerCase();
  if (surfaceWantsHandle(surfaceName, surfaceLabel)) {
    return key.includes("handle") || key.includes("handshank") || key.includes("shank") || key.includes("grip") || key.includes("手柄") || key.includes("把手");
  }
  return key.includes("front") || key.includes("body") || key.includes("main");
}

function shouldKeepOriginalMaterial(material: THREE.Material, meshName: string) {
  const key = `${material.name} ${meshName}`.toLowerCase();
  return [
    "lid",
    "cap",
    "straw",
    "mouth",
    "ring",
    "steel",
    "metal",
    "stainless",
    "silver",
    "transparent",
    "glass",
  ].some((word) => key.includes(word));
}

function shouldApplyBaseColor(material: THREE.Material, meshName: string) {
  if (shouldKeepOriginalMaterial(material, meshName)) return false;
  const key = `${material.name} ${meshName}`.toLowerCase();
  return [
    "front",
    "body",
    "main",
    "cup",
    "tumbler",
    "shell",
    "outer",
    "handle",
    "handshank",
    "shank",
    "grip",
    "else",
    "手柄",
    "把手",
  ].some((word) => key.includes(word));
}

function materialWantsHandle(material: THREE.Material, meshName: string) {
  const key = `${material.name} ${meshName}`.toLowerCase();
  return key.includes("handle") || key.includes("handshank") || key.includes("shank") || key.includes("grip") || key.includes("手柄") || key.includes("把手");
}

function materialWantsBody(material: THREE.Material, meshName: string) {
  if (shouldKeepOriginalMaterial(material, meshName)) return false;
  const key = `${material.name} ${meshName}`.toLowerCase();
  return ["front", "body", "main", "cup", "tumbler", "shell", "outer"].some((word) => key.includes(word));
}

function matchingSurfaceTexture(
  modelFile: string | null | undefined,
  material: THREE.Material,
  meshName: string,
  surfaceTextures: LoadedSurfaceTexture[]
) {
  return surfaceTextures.find((surface) =>
    doesMaterialMatchSurface(modelFile, material.name, meshName, surface.surfaceName)
  );
}

function meshVisualSize(mesh: THREE.Mesh) {
  try {
    const box = new THREE.Box3().setFromObject(mesh);
    const size = box.getSize(new THREE.Vector3());
    return Math.max(0, size.x * size.y * size.z);
  } catch {
    return 0;
  }
}

function pickTextureFallbackMesh(meshes: THREE.Mesh[], surfaceName?: string, surfaceLabel?: string) {
  const wantsHandle = surfaceWantsHandle(surfaceName, surfaceLabel);
  const candidates = meshes
    .map((mesh) => {
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const material = materials.find((item) => {
        if (!item || !canUseTexture(item)) return false;
        if (wantsHandle) {
          const key = `${item.name} ${mesh.name}`.toLowerCase();
          return key.includes("handle") || key.includes("handshank") || key.includes("shank") || key.includes("grip") || key.includes("手柄") || key.includes("把手");
        }
        return !shouldKeepOriginalMaterial(item, mesh.name);
      });
      if (!material) return null;
      const key = `${material.name} ${mesh.name}`.toLowerCase();
      const semanticWords = wantsHandle ? ["handle", "handshank", "shank", "grip", "手柄", "把手"] : ["front", "body", "main", "cup", "tumbler", "shell", "outer"];
      const semanticScore = semanticWords.some((word) => key.includes(word))
        ? 1000
        : 0;
      return { mesh, material, score: semanticScore + meshVisualSize(mesh) };
    })
    .filter((item): item is { mesh: THREE.Mesh; material: THREE.Material; score: number } => Boolean(item));
  return candidates.sort((a, b) => b.score - a.score)[0] ?? null;
}

function modeLabel(mode: TexturePlacementMode) {
  return {
    wrap: "AI 优化连续图",
    fit: "单图适配",
    cover: "平铺",
    decal: "贴图",
  }[mode];
}

function createTextureVariant(
  texture: THREE.Texture,
  mode: TexturePlacementMode,
  scale: number,
  offsetX: number,
  offsetY: number,
  maxAnisotropy: number,
  printWidth?: number | null,
  printHeight?: number | null,
  uvCalibration?: ModelUvCalibration | null,
  baseColor = "#f8f7f2"
) {
  const normalizedScale = Math.min(2.4, Math.max(0.45, scale || 1));
  const normalizedOffsetX = Math.min(0.45, Math.max(-0.45, offsetX || 0));
  const normalizedOffsetY = Math.min(0.45, Math.max(-0.45, offsetY || 0));
  const image = texture.image as { width?: number; height?: number } | undefined;
  const sourceWidth = image?.width ?? 0;
  const sourceHeight = image?.height ?? 0;
  const targetAspect = printWidth && printHeight ? printWidth / printHeight : 1;

  // The GLB UV map describes where a texture lands, while the supplier design
  // size describes the print canvas. Compose a bounded canvas at the supplier
  // aspect ratio before applying it to UV, so user controls do not depend on a
  // model's arbitrary geometry scale.
  if (sourceWidth > 0 && sourceHeight > 0 && typeof document !== "undefined") {
    const longEdge = 2048;
    const canvas = document.createElement("canvas");
    if (targetAspect >= 1) {
      canvas.width = longEdge;
      canvas.height = Math.max(1, Math.round(longEdge / targetAspect));
    } else {
      canvas.height = longEdge;
      canvas.width = Math.max(1, Math.round(longEdge * targetAspect));
    }
    const context = canvas.getContext("2d");
    if (context) {
      const canvasWidth = canvas.width;
      const canvasHeight = canvas.height;
      const sourceAspect = sourceWidth / sourceHeight;
      const offsetPxX = normalizedOffsetX * canvasWidth;
      const offsetPxY = normalizedOffsetY * canvasHeight;

      // A material map replaces the entire print surface. For a local decal,
      // preserve the selected cup color beneath the image instead of leaving
      // transparent canvas pixels to punch holes through the 3D mesh.
      context.fillStyle = baseColor;
      context.fillRect(0, 0, canvasWidth, canvasHeight);

      if (mode === "decal") {
        const shortEdge = Math.min(canvasWidth, canvasHeight);
        const imageHeight = shortEdge * normalizedScale * 0.52;
        const imageWidth = imageHeight * sourceAspect;
        context.drawImage(
          texture.image as CanvasImageSource,
          (canvasWidth - imageWidth) / 2 + offsetPxX,
          (canvasHeight - imageHeight) / 2 + offsetPxY,
          imageWidth,
          imageHeight
        );
      } else {
        const coverScale = Math.max(canvasWidth / sourceWidth, canvasHeight / sourceHeight);
        const imageWidth = sourceWidth * coverScale;
        const imageHeight = sourceHeight * coverScale;
        context.drawImage(
          texture.image as CanvasImageSource,
          (canvasWidth - imageWidth) / 2 + offsetPxX,
          (canvasHeight - imageHeight) / 2 + offsetPxY,
          imageWidth,
          imageHeight
        );
      }

      const next = new THREE.CanvasTexture(canvas);
      next.colorSpace = THREE.SRGBColorSpace;
      next.flipY = false;
      next.anisotropy = maxAnisotropy;
      next.wrapS = THREE.ClampToEdgeWrapping;
      next.wrapT = THREE.ClampToEdgeWrapping;
      if (uvCalibration) {
        const uSpan = uvCalibration.uMax - uvCalibration.uMin;
        const vSpan = uvCalibration.vMax - uvCalibration.vMin;
        next.repeat.set(1 / uSpan, 1 / vSpan);
        next.offset.set(-uvCalibration.uMin / uSpan, -uvCalibration.vMin / vSpan);
      }
      next.needsUpdate = true;
      return next;
    }
  }

  const next = texture.clone();

  next.colorSpace = THREE.SRGBColorSpace;
  next.flipY = false;
  next.anisotropy = maxAnisotropy;
  next.center.set(0.5, 0.5);

  if (uvCalibration) {
    const uSpan = uvCalibration.uMax - uvCalibration.uMin;
    const vSpan = uvCalibration.vMax - uvCalibration.vMin;
    next.wrapS = THREE.ClampToEdgeWrapping;
    next.wrapT = THREE.ClampToEdgeWrapping;
    next.repeat.set(1 / uSpan, 1 / vSpan);
    next.offset.set(-uvCalibration.uMin / uSpan, -uvCalibration.vMin / vSpan);
    next.needsUpdate = true;
    return next;
  }

  if (mode === "wrap") {
    next.wrapS = THREE.RepeatWrapping;
    next.wrapT = THREE.RepeatWrapping;
    next.repeat.set(normalizedScale, normalizedScale);
    next.offset.set(normalizedOffsetX, normalizedOffsetY);
  } else {
    const zoom = Math.max(0.28, Math.min(1.8, 1 / normalizedScale));
    const coverZoom = mode === "cover" ? zoom * 0.72 : mode === "decal" ? zoom * 0.62 : zoom;
    next.wrapS = THREE.ClampToEdgeWrapping;
    next.wrapT = THREE.ClampToEdgeWrapping;
    next.repeat.set(coverZoom, coverZoom);
    next.offset.set(0.5 - coverZoom / 2 + normalizedOffsetX, 0.5 - coverZoom / 2 + normalizedOffsetY);
  }

  next.needsUpdate = true;
  return next;
}

function fitModelToStage(object: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(object);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxAxis = Math.max(size.x, size.y, size.z) || 1;
  object.position.sub(center);
  object.scale.setScalar(2.65 / maxAxis);
}

export default function Product3DPreview({
  productName,
  modelFile,
  modelUrl,
  textureUrl,
  textureLabel,
  surfaceTextures = [],
  expectedSurfaceCount,
  onTextureLoadStateChange,
  surfaceName,
  surfaceLabel,
  baseColor = "#f8f7f2",
  textureMode = "wrap",
  textureScale = 1,
  textureOffsetX = 0,
  textureOffsetY = 0,
  printWidth = null,
  printHeight = null,
}: Product3DPreviewProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [renderState, setRenderState] = useState<RenderState>(modelUrl ? "loading" : "unsupported");
  const [slotMessage, setSlotMessage] = useState("等待模型加载");
  const surfaceTextureKey = surfaceTextures
    .map((item) => `${item.surfaceName}:${item.textureUrl}:${item.printWidth ?? ""}x${item.printHeight ?? ""}:${item.uvCalibration ? `${item.uvCalibration.uMin},${item.uvCalibration.vMin},${item.uvCalibration.uMax},${item.uvCalibration.vMax}` : ""}`)
    .join("|");
  const activeSurfaceTexture = surfaceTextures.find((item) => item.surfaceName === surfaceName);
  const retainedTextureSummary = surfaceTextures
    .map((item) => `${item.surfaceLabel || item.surfaceName}：${item.textureLabel}`)
    .join(" / ");
  const textureBadgeTitle = activeSurfaceTexture ? `${activeSurfaceTexture.surfaceLabel || surfaceLabel}素材` : surfaceTextures.length > 0 ? "已绑定贴图" : "当前素材";
  const textureBadgeValue = activeSurfaceTexture?.textureLabel || retainedTextureSummary || textureLabel || "未选择";

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !modelUrl) {
      setRenderState("unsupported");
      setSlotMessage("当前杯型暂未接入 3D 模型");
      return;
    }

    let disposed = false;
    let animationFrame = 0;
    let activeModel: THREE.Object3D | null = null;
    const generatedTextures: THREE.Texture[] = [];

    setRenderState("loading");
    setSlotMessage("正在加载 3D 模型");

    const scene = new THREE.Scene();
    scene.background = null;

    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, 1.4, 6.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.65;
    controls.enablePan = false;
    controls.minDistance = 3.6;
    controls.maxDistance = 8.5;
    controls.target.set(0, 0, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xdde5ee, 2.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(3.4, 5, 4.2);
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0xc7d8ff, 1.2);
    rimLight.position.set(-4, 3.2, -2.4);
    scene.add(rimLight);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(2.8, 64),
      new THREE.MeshBasicMaterial({ color: 0xeef3f8, transparent: true, opacity: 0.68 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.55;
    scene.add(floor);

    const resize = () => {
      if (disposed || !mount.clientWidth || !mount.clientHeight) return;
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();

    const textureLoader = new THREE.TextureLoader();
    textureLoader.setCrossOrigin("anonymous");
    const fallbackTexturePromise = textureUrl
      ? textureLoader.loadAsync(textureUrl).catch(() => null)
      : Promise.resolve(null);
    const surfaceTexturePromises = surfaceTextures
      .filter((item) => item.textureUrl)
      .map((item) =>
        textureLoader
          .loadAsync(item.textureUrl)
          .then((texture): SurfaceTextureLoadResult => ({ assignment: item, texture }))
          .catch((error): SurfaceTextureLoadResult => ({ assignment: item, error }))
      );

    const makeTextureVariant = (texture: THREE.Texture, assignment?: SurfaceTextureAssignment) => {
      const next = createTextureVariant(
        texture,
        textureMode,
        textureScale,
        textureOffsetX,
        textureOffsetY,
        renderer.capabilities.getMaxAnisotropy(),
        assignment?.printWidth ?? printWidth,
        assignment?.printHeight ?? printHeight,
        assignment?.uvCalibration,
        baseColor
      );
      generatedTextures.push(next);
      return next;
    };

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath("/draco/");
    const gltfLoader = new GLTFLoader();
    gltfLoader.setDRACOLoader(dracoLoader);

    Promise.all([gltfLoader.loadAsync(modelUrl), fallbackTexturePromise, Promise.all(surfaceTexturePromises)])
      .then(([gltf, texture, loadedSurfaceTextureResults]) => {
        if (disposed) return;
        const model = gltf.scene;
        activeModel = model;
        const validSurfaceTextures = loadedSurfaceTextureResults
          .filter((result): result is Extract<SurfaceTextureLoadResult, { texture: THREE.Texture }> => Boolean(result.texture))
          .map((result) => ({ ...result.assignment, texture: result.texture }));
        const failedSurfaceTextures = loadedSurfaceTextureResults.filter(
          (result): result is Extract<SurfaceTextureLoadResult, { error: unknown }> => Boolean(result.error)
        );
        onTextureLoadStateChange?.({
          expected: surfaceTextures.length,
          loaded: validSurfaceTextures.length,
          failedSurfaceNames: failedSurfaceTextures.map((item) => item.assignment.surfaceName),
        });
        const hasExplicitBindings = hasExplicitMaterialBindings(modelFile);
        const bodySurface = validSurfaceTextures.find((item) => surfaceWantsBody(item.surfaceName, item.surfaceLabel));
        const handleSurface = validSurfaceTextures.find((item) => surfaceWantsHandle(item.surfaceName, item.surfaceLabel));
        const activeSurfaceHasTexture = validSurfaceTextures.some((item) => item.surfaceName === surfaceName);

        if (texture || validSurfaceTextures.length > 0) {
          const meshes: THREE.Mesh[] = [];
          let applied = 0;
          let baseApplied = 0;

          model.traverse((node) => {
            const mesh = node as THREE.Mesh;
            if (!mesh.isMesh) return;
            meshes.push(mesh);
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const nextMaterials = materials.map((material) => {
              if (!material) {
                return material;
              }
              const next = material.clone();
              if (shouldApplyBaseColor(material, mesh.name) && canUseBaseColor(next)) {
                next.color.set(baseColor);
                baseApplied += 1;
              }
              const explicitSurface = hasExplicitBindings
                ? matchingSurfaceTexture(modelFile, material, mesh.name, validSurfaceTextures)
                : null;
              const surfaceTexture = explicitSurface
                ? explicitSurface.texture
                : hasExplicitBindings
                  ? null
                  : materialWantsHandle(material, mesh.name)
                    ? handleSurface?.texture
                    : materialWantsBody(material, mesh.name)
                      ? bodySurface?.texture
                      : null;
              const textureForMaterial =
                surfaceTexture ||
                (!hasExplicitBindings && shouldApplyToSurface(material, mesh.name, surfaceName, surfaceLabel) ? texture : null);
              if (textureForMaterial && canUseTexture(next)) {
                next.map = makeTextureVariant(
                  textureForMaterial,
                  explicitSurface ?? (materialWantsHandle(material, mesh.name) ? handleSurface : bodySurface)
                );
                if (canUseBaseColor(next)) next.color.set(0xffffff);
                next.transparent = false;
                next.alphaTest = 0;
                applied += 1;
              }
              if (applied || baseApplied) next.needsUpdate = true;
              return next;
            });
            mesh.material = Array.isArray(mesh.material) ? nextMaterials : nextMaterials[0];
          });

          if (!applied) {
            const preferredTexture =
              handleSurface?.texture && surfaceWantsHandle(surfaceName, surfaceLabel)
                ? handleSurface.texture
                : bodySurface?.texture || texture;
            const fallback = pickTextureFallbackMesh(meshes, surfaceName, surfaceLabel);
            const fallbackMesh = fallback?.mesh;
            const material = fallback?.material;
            if (material && canUseTexture(material) && preferredTexture) {
              const next = material.clone();
              next.map = makeTextureVariant(
                preferredTexture,
                surfaceWantsHandle(surfaceName, surfaceLabel) ? handleSurface : bodySurface
              );
              if (canUseBaseColor(next)) next.color.set(0xffffff);
              next.transparent = false;
              next.alphaTest = 0;
              next.needsUpdate = true;
              if (fallbackMesh) {
                const originalMaterials = Array.isArray(fallbackMesh.material) ? fallbackMesh.material : [fallbackMesh.material];
                const replaced = originalMaterials.map((item) => (item === material ? next : item));
                fallbackMesh.material = Array.isArray(fallbackMesh.material) ? replaced : next;
              }
              applied = 1;
              setSlotMessage(surfaceWantsHandle(surfaceName, surfaceLabel) ? "未识别把手槽，已回退到可贴图区域" : "未识别 front 槽，已回退到杯身可贴图区域");
            }
          } else {
            const expectedCount = Math.max(expectedSurfaceCount || 0, validSurfaceTextures.length);
            setSlotMessage(
              expectedCount > validSurfaceTextures.length
                ? `${modeLabel(textureMode)} · 已覆盖 ${validSurfaceTextures.length}/${expectedCount} 个设计面，其余保留底色`
                : validSurfaceTextures.length > 1
                  ? `${modeLabel(textureMode)} · 已覆盖 ${validSurfaceTextures.length} 个设计面`
                : validSurfaceTextures.length === 1 && !activeSurfaceHasTexture
                  ? `${modeLabel(textureMode)} · 已保留已绑定设计面贴图`
                  : `${modeLabel(textureMode)} · 已贴到 ${surfaceLabel || "front"} 设计面`
            );
          }

          if (!baseApplied) {
            const fallbackBase = pickTextureFallbackMesh(meshes, "front", "正面");
            const material = fallbackBase?.material;
            const mesh = fallbackBase?.mesh;
            if (material && mesh && canUseBaseColor(material)) {
              const next = material.clone();
              next.color.set(baseColor);
              next.needsUpdate = true;
              const originalMaterials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
              const replaced = originalMaterials.map((item) => (item === material ? next : item));
              mesh.material = Array.isArray(mesh.material) ? replaced : next;
            }
          }
        } else {
          model.traverse((node) => {
            const mesh = node as THREE.Mesh;
            if (!mesh.isMesh) return;
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const nextMaterials = materials.map((material) => {
              if (!material || !shouldApplyBaseColor(material, mesh.name) || !canUseBaseColor(material)) {
                return material;
              }
              const next = material.clone();
              next.color.set(baseColor);
              next.needsUpdate = true;
              return next;
            });
            mesh.material = Array.isArray(mesh.material) ? nextMaterials : nextMaterials[0];
          });
          setSlotMessage(
            failedSurfaceTextures.length
              ? "素材预览读取失败，请重新选择或上传图片后重试"
              : "未选择素材，显示当前杯体底色"
          );
        }

        fitModelToStage(model);
        scene.add(model);
        setRenderState("ready");
      })
      .catch((error) => {
        console.error("Product 3D preview failed", error);
        if (!disposed) {
          setRenderState("error");
          setSlotMessage("3D 模型加载失败，请检查模型文件或贴图资源");
        }
      });

    const render = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      controls.dispose();
      dracoLoader.dispose();
      if (activeModel) {
        activeModel.traverse((node) => {
          const mesh = node as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.geometry?.dispose();
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          materials.forEach((material) => material?.dispose());
        });
      }
      generatedTextures.forEach((texture) => texture.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [baseColor, expectedSurfaceCount, modelUrl, onTextureLoadStateChange, surfaceLabel, surfaceName, surfaceTextureKey, surfaceTextures.length, textureMode, textureOffsetX, textureOffsetY, textureScale, textureUrl]);

  if (!modelUrl) {
    return (
      <div className="product-3d-preview product-3d-preview--empty">
        <strong>{productName}</strong>
        <span>该杯型 3D 模型待供应链补齐，当前只展示 2D 图片预览。</span>
      </div>
    );
  }

  return (
    <div className="product-3d-preview">
      <div ref={mountRef} className="product-3d-preview__canvas" aria-label={`${productName} 3D 贴图预览`} />
      <div className="product-3d-preview__badge">
        <strong>{renderState === "ready" ? "3D 贴图预览" : renderState === "error" ? "预览异常" : "模型加载中"}</strong>
        <span>{slotMessage}</span>
      </div>
      <div className="product-3d-preview__texture">
        <span>{textureBadgeTitle}</span>
        <strong>{textureBadgeValue}</strong>
      </div>
      <div className="product-3d-preview__base-color">
        <span style={{ backgroundColor: baseColor }} />
        <strong>底杯颜色</strong>
      </div>
    </div>
  );
}
