"""Default business quality samples."""

from __future__ import annotations

from typing import Any

from app.schemas.business import BusinessQualitySampleImportItem, BusinessQualitySampleImportRequest
from app.services.business_runs import BusinessRunService, get_business_run_service


PRODUCT_DESIGN_QUALITY_SAMPLE_ITEMS: list[dict[str, Any]] = [
    {
        "sampleKey": "product-design-apparel-floral-v1",
        "label": "服装面料 · 花卉图案",
        "description": "验证花卉素材上到服装/面料时，图案识别度、材质贴合和商业展示是否稳定。",
        "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/2d53fbcf8c764fb3b2e2bccc1bc0c970/20260528/1c62a4c3-1779928629.png",
        "prompt": "把主图花纹应用到一款适合电商展示的连衣裙或面料产品图，保留花型识别度，材质自然。",
        "inputTags": ["服装", "面料", "花卉", "电商候选"],
        "defaultParams": {
            "productType": "apparel",
            "scene": "studio_product",
            "designBrief": "把主图花纹应用到一款适合电商展示的连衣裙或面料产品图，保留花型识别度，材质自然，产品结构可信。",
            "quality": "production",
            "size": "auto",
            "output_format": "png",
        },
        "sortOrder": 10,
    },
    {
        "sampleKey": "product-design-home-textile-check-v1",
        "label": "家纺软装 · 格纹纹理",
        "description": "验证格纹/几何纹理上到抱枕、床品或窗帘时，透视、重复和材质是否可信。",
        "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg",
        "prompt": "把主图纹理应用到家纺软装产品图，适合抱枕或床品展示，纹理连续，材质柔和。",
        "inputTags": ["家纺", "软装", "格纹", "材质贴合"],
        "defaultParams": {
            "productType": "home_textile",
            "scene": "lifestyle",
            "designBrief": "把主图纹理应用到家纺软装产品图，适合抱枕、床品或窗帘展示，纹理连续，材质柔和，环境干净。",
            "quality": "production",
            "size": "auto",
            "output_format": "png",
        },
        "sortOrder": 20,
    },
    {
        "sampleKey": "product-design-bag-pattern-v1",
        "label": "箱包 · 满版图案",
        "description": "验证满版图案用于托特包、手袋或背包时，产品结构、边缘和图案缩放是否合理。",
        "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/d405d98f5ed54d14a68f8559c8c0abdb/20260522/96bbb599-1779409039.png",
        "prompt": "把主图图案应用到一款托特包产品图，保留图案特征，产品边缘和缝线自然。",
        "inputTags": ["箱包", "满版图案", "结构可信", "候选"],
        "defaultParams": {
            "productType": "bag",
            "scene": "studio_product",
            "designBrief": "把主图图案应用到一款托特包或手袋产品图，保留图案特征，产品边缘、缝线和材质自然，适合电商展示。",
            "quality": "production",
            "size": "auto",
            "output_format": "png",
        },
        "sortOrder": 30,
    },
    {
        "sampleKey": "product-design-packaging-floral-v1",
        "label": "包装 · 图案延展",
        "description": "验证花纹素材转包装盒、包装袋或标签时，版面干净、图案不脏、不变形。",
        "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/d405d98f5ed54d14a68f8559c8c0abdb/20260522/a5804a4d-1779408183.png",
        "prompt": "把主图花纹转成适合包装盒或包装袋的产品设计图，图案清晰，版面高级。",
        "inputTags": ["包装", "图案延展", "商业展示", "版面干净"],
        "defaultParams": {
            "productType": "packaging",
            "scene": "ecommerce",
            "designBrief": "把主图花纹转成适合包装盒、包装袋或标签的产品设计图，图案清晰，版面高级，背景干净，适合电商主图。",
            "quality": "production",
            "size": "auto",
            "output_format": "png",
        },
        "sortOrder": 40,
    },
    {
        "sampleKey": "product-design-ecommerce-mockup-v1",
        "label": "电商主图 · 产品 Mockup",
        "description": "验证素材作为产品 mockup 主图时，主体明确、背景克制、可直接做业务质量对照。",
        "imageUrl": "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/d405d98f5ed54d14a68f8559c8c0abdb/20260522/4ab21bec-1779401079.png",
        "prompt": "把主图图案做成一个适合电商主图的产品 mockup，主体清晰，背景简洁。",
        "inputTags": ["电商主图", "mockup", "主体清晰", "对照样例"],
        "defaultParams": {
            "productType": "generic",
            "scene": "ecommerce",
            "designBrief": "把主图图案做成一个适合电商主图的产品 mockup，主体清晰，背景简洁，保留图案识别度，整体商业质感更强。",
            "quality": "production",
            "size": "auto",
            "output_format": "png",
        },
        "sortOrder": 50,
    },
]


def build_product_design_quality_sample_request(*, dry_run: bool = False) -> BusinessQualitySampleImportRequest:
    return BusinessQualitySampleImportRequest(
        businessKey="product_design",
        dryRun=dry_run,
        changeNote="v0.6 收口：补齐产品设计固定质量样例",
        items=[BusinessQualitySampleImportItem(**item) for item in PRODUCT_DESIGN_QUALITY_SAMPLE_ITEMS],
    )


def ensure_default_product_design_quality_samples(
    *,
    service: BusinessRunService | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    runner = service or get_business_run_service()
    return runner.import_quality_samples(build_product_design_quality_sample_request(dry_run=dry_run))
