# Gap Log

状态：active

## GAP-20260602-01: 客户端文件直传到业务资产链路未确认

Status: open
Priority: P1
Client Page: `/workbench/:projectId/abilities/pattern_extract`
User Action:
用户希望直接上传本地图片作为源图。

Expected Client Behavior:
用户选择本地图片后，客户端通过受控 `/api/media/*` 上传到 OSS，再调用 `/api/business/projects/{projectId}/assets` 登记为 `input_image`。

Needed API/Data:
稳定的客户端媒体上传流程，包括上传凭证、OSS URL 返回、contentType/fileName 和错误处理口径。

Current API Limitation:
当前后端存在 `/api/media/v1/upload-key` 与 STS 相关接口，但客户端直传流程、业务 API Key/登录态下的用户归属和前端实现细节未在本轮确认。

Suggested Mid-Platform API:
提供面向业务客户端的上传说明或统一上传接口，返回可直接登记到业务资产的 URL。

Temporary Client Behavior:
第一版只允许登记公网图片 URL，不做假上传。

Evidence:
- Screenshot: `output/playwright/podi-studio-preview-20260602/workbench-after-error-copy.png`

## GAP-20260602-02: 花纹提取提交前预计消耗与余额数据缺失

Status: open
Priority: P1
Client Page: `/workbench/:projectId/abilities/pattern_extract`
User Action:
用户提交花纹提取前希望知道本次预计消耗和余额是否足够。

Expected Client Behavior:
提交前显示预计消耗，提交后显示实际消耗与余额变化，余额不足时保留表单并给出回流路径。

Needed API/Data:
业务能力价格/预计消耗接口、当前业务方余额或额度、失败返还规则。

Current API Limitation:
当前业务能力文档强调 API Key、配额和业务方限制，但客户端尚无稳定余额/计费展示接口口径。

Suggested Mid-Platform API:
提供 `/api/business/billing/estimate` 或在 route-preview/business run response 中返回 estimatedCost/actualCost/quotaBalance。

Temporary Client Behavior:
页面显示“预计消耗由业务侧策略计算”，不展示虚假余额。

Evidence:
- Client Page: `/workbench/:projectId/abilities/pattern_extract`

## GAP-20260602-03: 业务工作单表未迁移导致真实联调阻塞

Status: open
Priority: P0
Client Page: `/workbench`
User Action:
用户进入工作台后，需要读取最近工作单或创建第一条工作单。

Expected Client Behavior:
`GET /api/business/projects` 正常返回工作单列表，空数据时返回 `items: []`，用户可以继续创建工作单。

Needed API/Data:
数据库存在 `business_projects` 及相关业务工作单表结构，后端业务项目 API 可以稳定返回。

Current API Limitation:
后端 `/health` 正常，但 `/api/business/projects?scenario=pattern_to_product&limit=3` 返回 500。后端日志显示：
`Table 'ai_zhongtai.business_projects' doesn't exist`。

Temporary Client Behavior:
客户端显示可读错误，提示检查后端日志；不在客户端绕过真实业务 API。

Evidence:
- Backend Health: `GET /health` 返回 `{"status":"ok"}`
- Backend Error: `business_projects` 表不存在
- Screenshot: `output/playwright/podi-studio-preview-20260602-mvp/workbench-final.png`

## GAP-20260602-04: 产品图生产能力未开放

Status: open
Priority: P1
Client Page: `/workbench/:projectId`
User Action:
用户完成裂变候选选择后，希望继续生成产品图或套图。

Expected Client Behavior:
用户选择候选后，可以进入产品图生产页，提交候选资产并生成产品图结果。

Needed API/Data:
产品图生产业务 API、输入资产要求、消耗规则、结果资产类型、失败错误码。

Current API Limitation:
当前 MVP 只确认花纹提取、裂变候选、候选选择、交付草稿接口路径；产品图生产暂不开放入口。

Temporary Client Behavior:
工作单页标记产品图为能力缺口，不提供无法兑现的提交按钮。

Evidence:
- Client Page: `/workbench/:projectId`
