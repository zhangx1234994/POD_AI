# Agent Image 2 Production Canvas Gate

Date: 2026-07-13

## Goal

Make every Agent Image 2 candidate that is intended for a product design surface pass one deterministic delivery step before it can be placed in the design basket:

1. Model output is persisted to first-party OSS.
2. Middle platform normalizes it to the product surface's exact pixel dimensions and target DPI.
3. The normalized production PNG is read back and preflighted.
4. Only the verified production asset is returned as the task result.

The model may choose a nearby supported aspect ratio. That candidate is never the production file by itself.

## Contract

Business client attaches `metadata.productionCanvas` to Image 2 Agent calls:

```json
{
  "enabled": true,
  "targetWidth": 2717,
  "targetHeight": 1476,
  "targetDpi": 150,
  "mode": "cover",
  "purpose": "agent_design_surface"
}
```

The middle platform replaces `images/assets/imageUrls/resultUrls` with the normalized OSS asset and records `_productionCanvas` with source URL, exact dimensions, DPI, mode and preflight evidence.

## Failure Contract

- Invalid declared canvas: `PRODUCTION_CANVAS_CONFIG_INVALID`.
- No model output image: `PRODUCTION_CANVAS_SOURCE_MISSING`.
- Source, normalization, OSS or preflight failure: the corresponding `PRODUCTION_CANVAS_*` or `PRODUCTION_PREFLIGHT_*` code.
- These are terminal failures for this attempt. The task is not billable as a successful result and cannot enter the design basket or order flow.
- Client copy must remain user-facing. It must not show raw values such as `ABILITY_TASK_FAILED` or vendor HTTP details.

## Regression Coverage

- Unit: candidate output is replaced by the exact target asset and preflight evidence is attached.
- Unit: no explicit contract leaves ordinary image tasks unchanged.
- Unit: enabled but incomplete contract is rejected rather than silently skipped.
- Business routing: a prompt-only request must never choose the original-print path because its wording contains a negative instruction such as "不要文字".
- Business truthfulness: a text-to-image full-bleed candidate is not marked as a seamless texture. "无缝" can only be shown after the dedicated continuity ability and its edge validation have succeeded.
- Paid production regression passed on 2026-07-13:
  - Agent session: `agent-8002a8cafe06`.
  - Ability task: `377ba9a877e84b2d9f16d6cae49ea1dc`.
  - Prompt-only route: `ai_recreate -> image2_recreate`; it did not enter the original-print path and did not claim seamless validation.
  - Requested / preflighted surface: `2717x1476`, `150 DPI`, `cover`.
  - Final OSS file: `prelaunch/system/20260712/80210969-1783850140.png`; downloaded verification returned PNG `2717x1476` with PNG DPI metadata approximately `150.0124`.
  - Agent plan reached `preview_ready`, created one private design asset, and the result was visually reviewed as a clean flat floral product pattern without text, watermark, or product mockup.

## Fallback Readiness

KIE is the current primary Image 2 route. Later Image 2 intermediary providers must be registered as middle-platform abilities/executors and comply with this same output contract. Failover must be controlled by the platform routing policy, include retry/attempt evidence, avoid duplicate billing, and never expose upstream error text directly to the client.
