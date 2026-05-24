# 错误码总表（Error Catalog）

> 说明：本表是**全局权威错误码目录**。新增/变更错误必须同步更新本表，并在接口文档中引用。

---

## 0. 规则

- **强约束错误**：必须使用 `ERR|<CODE>|<message>` 格式（如队列/并发限制）。
- **关键字错误**：使用大写关键字（如 `TASK_NOT_FOUND`），出现在 `detail` / `error_message` / `debugResponse`。
- `*_HTTP_*` / `*_STATUS_*` 表示带动态后缀（如 `COMFYUI_HISTORY_HTTP_502`）。

---

## 1. 队列/并发

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| Q1001 | ComfyUI 队列已满（单机 >= 10） | 强约束，写入 `taskId` |
| Q2001 | 商业模型队列已满（单机 >= 10） | 强约束，写入 `taskId` |

---

## 2. 鉴权/访问

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| AUTHORIZATION_REQUIRED | 缺少鉴权 | 401 |
| UNAUTHORIZED | 未授权（评测公共接口） | 401 |
| INVALID_TOKEN | token 无效 | 401 |
| INVALID_TOKEN_PAYLOAD | token payload 异常 | 401 |
| INVALID_CREDENTIALS | 登录凭证错误 | 401 |
| LOGIN_IDENTIFIER_REQUIRED | 登录缺少用户名或邮箱 | 400 |
| LOGIN_RATE_LIMITED | 登录失败次数过多，请稍后再试 | 429 |
| INVALID_REFRESH_TOKEN | refreshToken 无效 | 401 |
| SESSION_NOT_FOUND | 登录会话不存在 | 404 |
| SESSION_REVOKED | 登录会话已注销或被轮换 | 401 |
| SESSION_EXPIRED | 登录会话已过期 | 401 |
| USER_ID_REQUIRED | 管理员调整用户时缺少用户 ID | 400 |
| USER_NOT_FOUND | 用户不存在 | 404 |
| USER_INACTIVE | 用户被禁用 | 403 |
| USER_STATUS_INVALID | 用户状态不在允许范围内 | 400 |
| USERNAME_REQUIRED | 注册缺少用户名 | 400 |
| PASSWORD_TOO_SHORT | 注册密码长度不足 | 400 |
| USER_ALREADY_EXISTS | 用户名或邮箱已存在 | 409 |
| ROLE_INVALID | 角色不在允许范围内 | 400 |
| AUTH_SELF_LOCKOUT_FORBIDDEN | 管理员不能停用或降权自己 | 409 |
| INVITE_CODE_INVALID | 邀请码不存在或为空 | 400 |
| INVITE_CODE_NOT_FOUND | 邀请码记录不存在 | 404 |
| INVITE_CODE_INACTIVE | 邀请码未启用 | 409 |
| INVITE_CODE_EXPIRED | 邀请码已过期 | 409 |
| INVITE_CODE_USED | 邀请码使用次数已达上限 | 409 |
| INVITE_CODE_GENERATE_FAILED | 邀请码生成失败 | 500 |
| ADMIN_ONLY | 仅管理员可访问 | 403 |
| INTERNAL_ONLY | 仅内网可访问 | 401 |
| VENDOR_API_AUTH_REQUIRED | 第三方 API 执行服务缺少服务 token | 401，vendor-api-ops 敏感接口 |
| VENDOR_API_CLIENT_FORBIDDEN | 第三方 API 执行服务拒绝非白名单来源 | 403，vendor-api-ops 只接受中台等固定服务调用 |

---

## 3. 资源/参数

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| NOT_FOUND | 通用不存在 | 404 |
| RUN_NOT_FOUND | 评测 run 不存在 | 404 |
| WORKFLOW_ID_MISSING | 缺少 workflow_id | 400 |
| WORKFLOW_VERSION_NOT_FOUND | workflow 版本不存在 | 404 |
| WORKFLOW_NOT_FOUND | workflow 不存在 | 404 |
| EXECUTOR_NOT_FOUND | 执行节点不存在 | 404 |
| EXECUTOR_BUSY | 执行节点繁忙 | 409 |
| EXECUTOR_ADAPTER_MISSING | 执行器适配缺失 | 500 |
| EXECUTOR_TYPE_NOT_BAIDU | 执行器类型不匹配（百度） | 400 |
| EXECUTOR_TYPE_NOT_COMFYUI | 执行器类型不匹配（ComfyUI） | 400 |
| EXECUTOR_TYPE_NOT_KIE | 执行器类型不匹配（KIE） | 400 |
| EXECUTOR_TYPE_NOT_VOLCENGINE | 执行器类型不匹配（火山） | 400 |
| ABILITY_NOT_FOUND | 能力不存在 | 404 |
| ABILITY_NOT_FOUND_OR_INACTIVE | 能力不存在或未激活 | 404 |
| ABILITY_INACTIVE | 能力未激活 | 403 |
| ABILITY_ID_MISSING | 评测或能力调用缺少能力 ID | 评测端触发能力任务前校验 |
| ABILITY_TEMPLATE_INVALID | 能力模板校验失败 | 400 |
| ABILITY_TEMPLATE_NOT_FOUND | 能力模板快照不存在 | 404 |
| ABILITY_EXECUTOR_NOT_CONFIGURED | 能力未配置执行节点 | 400 |
| ABILITY_LOG_NOT_FOUND | 能力日志不存在 | 404 |
| ABILITY_LOG_NOT_COMFYUI | 日志非 ComfyUI | 400 |
| ABILITY_TASK_ID_MISSING | 能力任务提交后未返回任务 ID | 评测端无法进入轮询时使用 |
| BUSINESS_IMAGE_URL_REQUIRED | 业务任务缺少主图 URL | 400，花纹提取/图裂变/扩图提交 |
| BUSINESS_KEY_REQUIRED | 业务版本缺少业务标识 | 400 |
| BUSINESS_VERSION_REQUIRED | 业务版本缺少版本号 | 400 |
| BUSINESS_DISPLAY_NAME_REQUIRED | 业务版本缺少展示名称 | 400 |
| BUSINESS_CAPABILITY_ID_REQUIRED | 业务版本自定义 ID 为空 | 400 |
| BUSINESS_CAPABILITY_VERSION_DUPLICATED | 同一业务标识下版本号重复 | 409 |
| BUSINESS_CAPABILITY_NOT_FOUND | 业务能力版本不存在或未启用 | 404 |
| BUSINESS_CAPABILITY_NOT_RUNNABLE | 业务能力版本不可试运行 | 409，管理端草稿试运行拒绝 disabled/deprecated 版本 |
| FISSION_ASPECT_SOURCE_IMAGE_LOAD_FAILED | 图裂变比例重构分支无法读取原图 | 400，自有业务接口图裂变在目标比例与原图差异较大时触发 |
| FISSION_ASPECT_RECOMPOSE_GUIDE_FAILED | 图裂变比例重构分支生成或上传引导图失败 | 400，自有业务接口图裂变进入比例重构分支前置处理失败 |
| BUSINESS_ROLLBACK_TARGET_NOT_FOUND | 没有可回滚的上一业务版本 | 409 |
| BUSINESS_STATUS_INVALID | 业务版本状态非法 | 400 |
| BUSINESS_ACCEPTANCE_STATUS_INVALID | 业务版本验收状态非法 | 400，允许 `passed` / `failed` / `warning` / `waived` |
| BUSINESS_ACCEPTANCE_REQUIRED | 业务版本缺少最近一次“验收通过”记录 | 409，默认版本切换申请或直接设默认前必须先记录验收 |
| BUSINESS_RELEASE_ACCEPTANCE_REQUIRED | 业务版本发布缺少验收证据 | 发布门禁提示码，需先登记真实样本或人工验收 |
| BUSINESS_RELEASE_GATE_BLOCKED | 业务版本完整上线门禁未通过 | 409，默认版本切换、审批申请或直接设默认前必须补齐治理阻断项 |
| HEALTH_WATCH_SYSTEMD_UNAVAILABLE | 当前环境无法读取 systemd | `/api/admin/dashboard/health-watch/status` 响应内状态，不作为 HTTP 错误抛出 |
| HEALTH_WATCH_UNIT_UNAVAILABLE | 自检守护单元未安装或不可加载 | `/api/admin/dashboard/health-watch/status` 响应内状态，不作为 HTTP 错误抛出 |
| HEALTH_WATCH_UNIT_DISABLED | 自检守护定时器未启用 | `/api/admin/dashboard/health-watch/status` 响应内状态，不作为 HTTP 错误抛出 |
| HEALTH_WATCH_UNIT_FAILED | 自检守护最近一次执行失败 | `/api/admin/dashboard/health-watch/status` 响应内状态，不作为 HTTP 错误抛出 |
| BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE | 默认业务版本必须是 active 状态 | 400 |
| BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE | 线上默认业务版本的控制项不可直接修改 | 409，主能力、配方、业务标识、版本号、输入/输出 schema 或取消默认都必须通过新草稿版本和默认切换流程完成 |
| BUSINESS_DRAFT_ONLY_EDITABLE | 只有草稿业务版本允许修改编排配方 | 409，线上默认版本或历史 active 版本必须先复制为草稿，再修改受控编排字段 |
| BUSINESS_DEFAULT_ALREADY_ACTIVE | 目标业务版本已经是默认版本 | 409，默认版本审批申请 |
| BUSINESS_DEFAULT_APPROVAL_PENDING | 目标业务版本已有待审批的默认切换申请 | 409，避免重复申请 |
| BUSINESS_DEFAULT_APPROVAL_NOT_FOUND | 默认版本审批记录不存在 | 404 |
| BUSINESS_DEFAULT_APPROVAL_ALREADY_DECIDED | 默认版本审批记录已处理，不能重复审批/驳回 | 409 |
| BUSINESS_RECIPE_INVALID | 业务能力配方非法 | 400，缺少 primaryAbilityId/steps、步骤类型非法或步骤结构非法 |
| BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE | 业务配方指向的原子能力不可用 | 400，主能力/步骤能力/VL 辅助能力不存在 |
| BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING | 业务治理提示：业务版本未绑定主能力 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND | 业务治理提示：主能力编号不存在 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE | 业务治理提示：主能力未启用 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING | 业务治理提示：配方没有可执行步骤 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_STEP_ABILITY_MISSING | 业务治理提示：配方步骤缺少能力编号 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND | 业务治理提示：配方步骤引用的能力不存在 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_STEP_ABILITY_INACTIVE | 业务治理提示：配方步骤引用的能力未启用 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_RECIPE_STEP_ID_DUPLICATED | 业务治理提示：配方步骤编号重复 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_RECIPE_PRIMARY_STEP_MISMATCH | 业务治理提示：主能力和主步骤绑定不一致 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND | 业务治理提示：绑定的第三方模型不存在 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE | 业务治理提示：绑定的第三方模型未启用 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED | 业务治理提示：第三方模型缺少验收通过记录 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING | 业务治理提示：第三方模型缺少成本策略 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING | 业务治理提示：第三方模型没有可用密钥 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED | 业务治理提示：第三方出网模型缺少最近一次带密钥出网验证成功记录 | `/api/admin/business/capabilities` 响应内提示，不作为 HTTP 错误抛出 |
| BUSINESS_CLIENT_ID_REQUIRED | 业务方配置自定义 ID 为空 | 400 |
| BUSINESS_CLIENT_TENANT_REQUIRED | 业务方配置缺少 tenantId | 400 |
| BUSINESS_CLIENT_DISPLAY_NAME_REQUIRED | 业务方配置缺少展示名称 | 400 |
| BUSINESS_CLIENT_STATUS_INVALID | 业务方状态非法 | 400 |
| BUSINESS_CLIENT_DUPLICATED | 业务方 tenantId/clientId 配置重复 | 409 |
| BUSINESS_CLIENT_NOT_FOUND | 业务方配置不存在 | 404 |
| BUSINESS_CLIENT_DISABLED | 业务方已停用，不允许提交任务 | 403 |
| BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED | 业务方未开通当前业务能力 | 403 |
| BUSINESS_USER_SCOPE_REQUIRED | 业务方账号缺少 tenantId，不能直接调用业务 API | 403 |
| BUSINESS_USER_SCOPE_FORBIDDEN | 业务方账号传入的 tenantId/clientId 超出自身绑定范围 | 403 |
| BUSINESS_CLIENT_CONCURRENCY_LIMITED | 业务方并发任务达到上限 | 429 |
| BUSINESS_CLIENT_DAILY_RUN_LIMITED | 业务方当日调用次数达到上限 | 429 |
| BUSINESS_CLIENT_DAILY_QUOTA_LIMITED | 业务方当日额度达到上限 | 429 |
| BUSINESS_API_KEY_INACTIVE | 业务 API Key 未启用或已停用 | 401 |
| BUSINESS_API_KEY_EXPIRED | 业务 API Key 已过期 | 401 |
| BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED | 业务 API Key 未授权调用当前业务 | 403 |
| BUSINESS_API_KEY_DUPLICATED | 业务 API Key 重复 | 409 |
| BUSINESS_API_KEY_NOT_FOUND | 业务 API Key 不存在 | 404 |
| BUSINESS_REQUEST_PAYLOAD_INVALID | 业务任务保存的请求载荷不可恢复 | 500，阻塞式 VL 前置完成后无法重建主任务入参 |
| BUSINESS_VL_PREPROCESS_FAILED | VL 前置分析失败，主任务未提交 | 500，`vlAssist.waitForResult=true` 或 `mode=vl_then_primary` |
| TEXT_FISSION_PROMPT_REQUIRED | 文字强化裂变缺少用户确认后的提示词 | 400，第二步 `/api/business/text-fission/runs` 必须传 `editable_prompt` 或兼容字段 |
| TEXT_FISSION_PROMPT_EMPTY | VL 返回结果中没有可用的可编辑提示词 | 500，第一步 `/api/business/text-fission/prompts` 返回异常 |
| TEXT_FISSION_PROMPT_PREPARE_FAILED | 文字强化裂变提示词草稿生成失败 | 500，第一步调用 VL 或解析结构化结果失败 |
| IMAGE_EDIT_INSTRUCTION_REQUIRED | 图编辑缺少编辑指令 | 400，普通改图必须传 `instruction` 或兼容字段；`canvas_outpaint` 可省略 |
| IMAGE_EDIT_SKILL_INVALID | 图编辑技能枚举非法 | 400，允许 `local_modify` / `reference_element_transfer` / `remove_inpaint` / `color_reference_correction` / `canvas_outpaint` |
| IMAGE_EDIT_REFERENCE_REQUIRED | 图编辑缺少参考图 | 400，参考图替换和补色校正必须传 `referenceImages` |
| IMAGE_EDIT_TARGET_REQUIRED | 图编辑缺少目标区域 | 400，删除修补必须传 `selectionHints` 或 `maskUrl` |
| IMAGE_EDIT_SIZE_INVALID | 图编辑尺寸非法 | 400，自定义尺寸必须满足最大边、16 倍数、比例和总像素约束 |
| IMAGE_EDIT_CANVAS_TOO_SMALL | 图编辑扩展画布尺寸过小 | 400，`canvas_outpaint` 的目标画布不能小于原图，也不能小于原图 + 指定扩展边距 |
| IMAGE_EDIT_CANVAS_PLACEMENT_INVALID | 图编辑扩展画布放置非法 | 400，原图放入目标画布的位置越界，或 `anchor/placementX/placementY` 不合法 |
| IMAGE_EDIT_CANVAS_BUILD_FAILED | 图编辑扩展画布生成失败 | 400，原图读取、目标画布生成或 mask 上传失败 |
| IMAGE_EDIT_MASK_SIZE_MISMATCH | 图编辑蒙版尺寸与主图不一致 | 400，mask 必须与主图同尺寸 |
| IMAGE_EDIT_MASK_ALPHA_REQUIRED | 图编辑蒙版缺少 Alpha 通道 | 400，mask 必须是有效透明蒙版 |
| IMAGE_EDIT_QUALITY_INVALID | 图编辑质量档位非法 | 400，允许 `auto` / `preview` / `production` / `premium` |
| IMAGE_EDIT_OUTPUT_FORMAT_INVALID | 图编辑输出格式非法 | 400，允许 `png` / `jpeg` / `webp` |
| BUSINESS_RUN_ID_REQUIRED | 查询业务任务缺少 runId | 400 |
| BUSINESS_RUN_NOT_FOUND | 业务任务不存在 | 404 |
| BUSINESS_RUN_FORBIDDEN | 业务任务无访问权限 | 403 |
| BUSINESS_RUN_TEMPORARY_UNAVAILABLE | 业务任务结果查询临时不可用，可稍后重试 | 503 |
| BUSINESS_RUN_IDS_REQUIRED | 批量业务任务操作缺少 runId 列表 | 400 |
| BUSINESS_RUN_BULK_LIMIT_EXCEEDED | 批量业务任务操作超过单次 100 条限制 | 400 |
| BUSINESS_RUN_RETEST_PAYLOAD_INVALID | 业务复测无法从原任务还原有效入参 | 409 |
| BUSINESS_CALLBACK_NOT_CONFIGURED | 业务任务没有配置回调地址，无法重试回调 | 409 |
| BUSINESS_RUN_NOT_FINISHED | 业务任务仍在排队或执行中，不能重试终态回调 | 409 |
| BUSINESS_RUN_NOT_BILLABLE | 业务任务当前状态不允许扣费 | 409，失败/取消/超时任务不向业务方计费 |
| BUSINESS_RUN_UNPRICED | 业务任务成功但缺少成本或额度，不能自动扣费 | 409 |
| BUSINESS_RUN_USER_REQUIRED | 业务任务缺少 userId，无法归属钱包账户 | 400 |
| BUSINESS_WALLET_SETTLEMENT_NOT_FOUND | 业务任务没有可退回的钱包扣费记录 | 409 |
| BUSINESS_PACKAGE_SETTLEMENT_NOT_FOUND | 业务任务套餐扣减记录不存在，无法退回套餐 | 409 |
| BUSINESS_PACKAGE_SETTLEMENT_INVALID | 业务任务套餐扣减记录缺少套餐 ID 或扣减次数 | 409 |
| PROMPT_REQUIRED | 缺少提示词 | 400，人工测试/模型调用缺少必填 prompt |
| INVALID_WORKFLOW_OR_EXECUTOR | workflow 或 executor 无效 | 400 |
| BATCH_NOT_FOUND | 批测批次不存在 | 404 |
| BATCH_FORBIDDEN | 批测批次无权限 | 403 |
| BATCH_ACTIVE_EXISTS | 已有进行中的批次，拒绝重复创建 | 409 |
| BATCH_STOPPED | 批次已停止，不允许写入 | 409 |
| BATCH_NOT_READY | 批次素材未就绪 | 400 |
| BATCH_ASSETS_EMPTY | 素材列表为空 | 400 |
| BATCH_ASSET_LIMIT_EXCEEDED | 素材条数超上限 | 400 |
| BATCH_ASSET_UPLOAD_STATUS_INVALID | 素材上传状态非法 | 400 |
| BATCH_ASSET_URL_REQUIRED | 上传成功素材缺少 URL | 400 |
| BATCH_ITEM_SUBMIT_FAILED | 执行项提交失败 | 500 |
| BATCH_REVIEWS_EMPTY | 批次标注写入请求为空 | 400 |
| BATCH_REVIEWS_LIMIT_EXCEEDED | 批次标注写入条数超限 | 400 |
| BATCH_REVIEW_RUN_ITEM_REQUIRED | 批次标注缺少执行项 ID | 400 |
| BATCH_REVIEW_RUN_ITEM_INVALID | 批次标注执行项不属于当前批次 | 400 |
| BATCH_REVIEW_VERDICT_INVALID | 批次标注 verdict 非法 | 400 |
| BATCH_REVIEW_NOT_READY | 批次未结束，暂不可进入标注分页 | 409 |
| BATCH_REVIEW_PAGE_INVALID | 标注分页页码非法（越界/completed_page > current_page） | 400 |
| WALLET_INSUFFICIENT | 钱包可用余额不足 | 402 |
| WALLET_HOLD_NOT_FOUND | 冻结记录不存在或已处理 | 404 |
| WALLET_TRACE_ID_REQUIRED | 钱包扣费/调账缺少 traceId 或 taskId，无法安全防重 | 400 |
| WALLET_ADJUSTMENT_DIRECTION_INVALID | 钱包调账方向非法 | 400，仅支持 increase/decrease/refund/deduct 等同义值 |
| RECHARGE_AMOUNT_INVALID | 充值金额非法（<=0） | 400 |
| RECHARGE_ORDER_NOT_FOUND | 充值订单不存在 | 404 |
| RECHARGE_STATUS_INVALID | 充值订单状态非法（仅支持 pending/paid/failed/canceled） | 400 |
| RECHARGE_ORDER_STATUS_CONFLICT | 充值订单状态流转冲突（终态不可逆） | 409 |
| RECHARGE_CALLBACK_UNAUTHORIZED | 充值回调鉴权失败（WALLET_CALLBACK_TOKEN 不匹配） | 401 |
| RECHARGE_CALLBACK_SIGNATURE_INVALID | 充值回调签名非法（缺失/错误） | 401 |
| RECHARGE_CALLBACK_SIGNATURE_EXPIRED | 充值回调签名过期（时间戳超窗） | 401 |
| BILL_MONTH_INVALID | 账单月份格式非法（需 YYYY-MM） | 400 |
| BILLING_DATETIME_INVALID | 账单/套餐时间格式非法 | 400 |
| BILLING_USER_ID_REQUIRED | 套餐订单缺少用户 ID | 400 |
| PACKAGE_KEY_REQUIRED | 套餐发放或套餐订单缺少套餐标识 | 400 |
| PACKAGE_UNITS_INVALID | 套餐额度非法（<=0） | 400 |
| PACKAGE_AMOUNT_INVALID | 套餐金额非法（<0） | 400 |
| PACKAGE_VALIDITY_DAYS_INVALID | 套餐有效期天数非法（<=0） | 400 |
| PACKAGE_CATALOG_NAME_REQUIRED | 套餐目录缺少套餐名称 | 400 |
| PACKAGE_CATALOG_STATUS_INVALID | 套餐目录状态非法 | 400，仅支持 active/inactive |
| PACKAGE_CATALOG_NOT_FOUND | 套餐目录不存在 | 404 |
| PACKAGE_PURCHASE_ORDER_NOT_FOUND | 套餐购买订单不存在 | 404 |
| PACKAGE_PURCHASE_ORDER_STATUS_INVALID | 套餐购买订单状态非法 | 400，仅支持 pending/paid/cancelled/failed |
| MONTHLY_SETTLEMENT_NOT_FOUND | 月结记录不存在 | 404 |
| MONTHLY_SETTLEMENT_STATUS_INVALID | 月结记录状态非法 | 400，仅支持 issued/paid/cancelled |
| BILLING_INVOICE_TITLE_REQUIRED | 发票申请缺少发票抬头 | 400 |
| BILLING_INVOICE_REQUEST_NOT_FOUND | 发票申请不存在 | 404 |
| BILLING_INVOICE_STATUS_INVALID | 发票申请状态非法 | 400，仅支持 requested/issued/cancelled |
| BILLING_NOTIFICATION_CONFIG_INVALID | 账单通知配置格式非法 | 400 |
| RELEASE_DECISION_STATUS_INVALID | 上线结论登记状态非法 | 400，仅允许 approved/deferred/blocked |

---

## 4. 评测/Coze

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| COZE_SUBMIT_FAILED | Coze 提交失败 | /v1/workflow/run |
| COZE_SUBMIT_MISSING_EXECUTE_ID | 缺少 execute_id | Coze 返回异常 |
| COZE_HISTORY_FAILED | Coze history 查询失败 | /v1/workflow/history |
| COZE_EXECUTION_FAILED | Coze 执行失败 | run_status=failed |
| COZE_FAILED | Coze 返回 code!=0 | |
| COZE_RUN_* | Coze 状态异常 | failed/canceled/timeout |
| COZE_ASYNC_TIMEOUT | 异步轮询超时 | |
| COZE_ASYNC_EMPTY | 异步轮询空响应 | |
| COZE_WORKFLOW_ERROR | workflow output 内含 error | |
| COZE_WORKFLOW_ID_MISSING | 缺少 workflow_id | |
| COZE_NOT_CONFIGURED | Coze 未配置 | |
| COZE_REQUEST_FAILED | Coze 请求失败 | |
| COZE_RESPONSE_NOT_JSON | Coze 返回非 JSON | |
| COZE_INVALID_RESPONSE | Coze 返回体异常 | |
| COZE_HTTP_* | Coze HTTP 非 200 | |
| FANOUT_EMPTY | 批量子任务全部失败 | |
| FANOUT_PARTIAL_FAILED | 批量部分失败 | |
| EVAL_NO_RECENT_RUNS | 最近窗口内没有评测运行 | 评测运行健康检查，提示巡检可能未执行 |
| EVAL_NO_RECENT_SUCCESS | 最近窗口内有有效失败但没有成功记录 | 评测运行健康检查，视为主链路不可用 |
| EVAL_SUCCEEDED_WITHOUT_OUTPUT | 评测运行成功但没有图片或结构化结果 | 全量巡检/健康检查必须阻断 |

---

## 5. Task/回调

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| TASK_ID_REQUIRED | 缺少 taskId | |
| TASK_NOT_FOUND | 任务不存在 | |
| TASK_FAILED | 任务执行失败 | |
| ABILITY_TASK_FAILED | 能力异步任务执行失败 | 任务中心/能力调用统一口径 |
| ABILITY_TASK_CANCELLED | 能力异步任务被取消 | 任务中心/能力调用统一口径 |
| TASK_TIMEOUT | 任务超时 | |
| TASK_IMAGES_EMPTY | 任务无图片 | |
| RUN_CREATE_FAILED | 任务创建失败（未进入执行） | 调度阶段错误 |
| CALLBACK_OUTPUT_EMPTY | 回调 task id 为空 | |
| CALLBACK_FAILED | 回调阶段失败（兜底错误码） | 无明确上游错误码时使用 |
| CALLBACK_IMAGES_EMPTY | 回调解析不到图片 | |
| CALLBACK_TASK_NOT_RESOLVED | task id 无法解析/失效 | |

---

## 6. Agent/服务器管理

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| AGENT_TOKEN_REQUIRED | 缺少 Agent token | 401 |
| AGENT_TOKEN_INVALID | Agent token 无效 | 401 |
| AGENT_TOKEN_EXPIRED | Agent token 已过期 | 401 |
| AGENT_TOKEN_KID_REQUIRED | 缺少 kid（多密钥模式） | 401 |
| AGENT_TOKEN_KID_INVALID | kid 不存在 | 401 |
| AGENT_TOKEN_SCOPE_INVALID | token scope 不匹配 | 403 |
| AGENT_TOKEN_PAYLOAD_INVALID | token payload 异常 | 401 |
| AGENT_TOKEN_PAYLOAD_MISMATCH | token 声明与请求体不一致 | 403 |
| AGENT_NOT_FOUND | Agent 不存在 | 404 |
| AGENT_ALREADY_EXISTS | Agent 已存在 | 409 |
| AGENT_NOT_ALLOWED | Agent 被禁用/不在白名单 | 403 |
| AGENT_BASE_URL_MISSING | Agent base_url 缺失 | 400 |
| AGENT_MANIFEST_NOT_FOUND | Manifest 不存在 | 404 |
| AGENT_MANIFEST_FORBIDDEN | Manifest 不匹配 task | 403 |
| AGENT_MANIFEST_ROLE_MISMATCH | rollback 目标与当前清单角色不一致 | 400 |
| AGENT_ENROLL_CODE_REQUIRED | 缺少注册码 | 400 |
| AGENT_ENROLL_CODE_NOT_FOUND | 注册码不存在 | 404 |
| AGENT_ENROLL_CODE_INACTIVE | 注册码状态不可用 | 409 |
| AGENT_ENROLL_CODE_EXPIRED | 注册码已过期 | 409 |
| AGENT_ENROLL_CODE_USED | 注册码使用次数已达上限 | 409 |
| AGENT_BOOTSTRAP_INSTALL_KEY_REQUIRED | 缺少安装密钥 | 400 |
| AGENT_BOOTSTRAP_INSTALL_KEY_INVALID | 安装密钥无效 | 403 |
| AGENT_BOOTSTRAP_INSTALL_KEY_NOT_CONFIGURED | 服务端未配置安装密钥 | 503 |
| AGENT_DESKTOP_RELEASE_NOT_FOUND | 桌面端发布包不存在 | 404 |
| AGENT_DESKTOP_RELEASE_FILE_NOT_FOUND | 桌面端安装包文件不存在 | 404 |
| AGENT_DESKTOP_RELEASE_FILE_EMPTY | 上传的安装包为空 | 400 |
| AGENT_DESKTOP_RELEASE_FILE_TOO_LARGE | 上传的安装包超过大小限制 | 413 |
| AGENT_TASK_NOT_FOUND | Task 不存在 | 404 |
| AGENT_TASK_FORBIDDEN | Task 不属于该 Agent | 403 |
| AGENT_TASK_EXPIRED | Task 已过期 | 409 |
| AGENT_PUSH_FAILED | 任务推送失败 | 502 |
| COMFYUI_REPAIR_JOB_NOT_FOUND | 修复任务不存在 | 404 |

---

## 7. ComfyUI

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| COMFYUI_BASE_URL_MISSING | 缺少 ComfyUI Base URL | |
| COMFYUI_WORKFLOW_EMPTY | workflow 为空 | |
| COMFYUI_SUBMIT_ERROR | 提交失败 | /prompt |
| COMFYUI_SUBMIT_NODE_ERROR | 节点错误 | /prompt node_errors |
| COMFYUI_HISTORY_HTTP_* | history 非 200 | /history/<id> |
| COMFYUI_HISTORY_INVALID | history JSON 异常 | |
| COMFYUI_STATUS_* | status 异常 | running/error/unknown |
| COMFYUI_IMAGES_EMPTY | history 无 images | |
| COMFYUI_ASSETS_EMPTY | OSS 入库为空 | |
| COMFYUI_TIMEOUT | 轮询超时 | |
| COMFYUI_IMAGE_REQUIRED | 缺少图片 | |
| COMFYUI_PROMPT_REQUIRED | 缺少 ComfyUI 文生图提示词 | 400，文字强化文生图节点执行前校验 |
| COMFYUI_OBJECT_INFO_ERROR | /object_info 异常 | |
| COMFYUI_OBJECT_INFO_INVALID | /object_info JSON 异常 | |
| COMFYUI_QUEUE_STATUS_ERROR | /queue/status 异常 | |
| COMFYUI_QUEUE_STATUS_INVALID | queue JSON 异常 | |
| COMFYUI_QUEUE_FULL | ComfyUI 队列已满 | 业务 API、Coze 工具箱或能力调用应提示稍后重试，不允许静默丢任务 |
| COMFYUI_QUEUE_HEALTH_UNAVAILABLE | ComfyUI 队列健康检查整体失败 | 评测健康检查无法读取队列汇总 |
| COMFYUI_EXECUTOR_UNREACHABLE | 部分 ComfyUI 执行节点不可用 | 评测健康检查发现 active 节点队列不可读 |
| COMFYUI_NO_AVAILABLE_EXECUTOR | 没有可用 ComfyUI 执行节点 | 所有 active ComfyUI 节点队列不可读 |
| COMFYUI_FEED_GAP | 中台有待下发任务但 ComfyUI 仍有空闲容量 | 管理端队列诊断项，不是对外接口错误 |
| COMFYUI_WORKFLOW_GRAPH_MISSING | ComfyUI 能力没有可检查的工作流图 | 管理端能力对齐检查诊断项 |
| COMFYUI_NO_ROUTED_EXECUTOR | ComfyUI 能力没有可检查的路由执行节点 | 管理端能力对齐检查诊断项 |
| COMFYUI_ROUTING_BINDING_MISMATCH | 能力允许节点与 workflow 绑定节点不一致 | 管理端能力对齐检查诊断项 |
| COMFYUI_BACKEND_RUNNING_NOT_VISIBLE | 中台显示执行中但 ComfyUI 队列不可见 | 管理端队列诊断项，优先排查下发和结果回填 |
| COMFYUI_EXECUTOR_EMPTY | 没有配置 active ComfyUI 执行节点 | 管理端队列诊断项 |
| COMFYUI_ADAPTER_MISSING | adapter 未注册 | |
| COMFYUI_PROMPT_ID_REQUIRED | 缺少 prompt_id | |
| COMFYUI_BASE_URL_REQUIRED | 缺少 base_url | |
| COMFYUI_ERROR | ComfyUI 执行错误 | |
| COMFYUI_EXECUTOR_NOT_MATCHED | 执行节点不匹配 | |
| COMFYUI_NOT_READY | ComfyUI 未就绪 | |
| COMFYUI_SYSTEM_STATS_ERROR | ComfyUI 系统状态异常 | |
| COMFYUI_TEST_FAILED | ComfyUI 测试失败 | |
| COMFYUI_WORKFLOW_KEY_MISSING | workflow_key 缺失 | |
| COMFYUI_VERSION_SOURCE_INVALID | ComfyUI 版本源地址无效 | |
| COMFYUI_VERSION_SYNC_FAILED | ComfyUI 版本同步失败 | |
| COMFYUI_RESOURCE_TYPE_INVALID | 资源选项 type 非法 | |
| COMFYUI_REPAIR_MODE_NOT_SUPPORTED | 修复模式暂不支持（仅 additive） | |
| COMFYUI_REPAIR_ITEMS_REQUIRED | 修复任务缺少可执行项 | |
| COMFYUI_REPAIR_NOTHING_TO_DO | 节点无需修复（自动跳过） | |

---

## 8. 第三方/媒资

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| BAIDU_TEST_FAILED | 百度测试失败 | |
| BAIDU_API_ERROR | 百度 API 错误 | |
| BAIDU_API_KEY_MISSING | 百度 API Key 缺失 | |
| BAIDU_ENDPOINT_MISSING | 百度 endpoint 缺失 | |
| BAIDU_TOKEN_ERROR | 百度 token 异常 | |
| VOLCENGINE_REQUEST_FAILED | 火山请求失败 | |
| VOLCENGINE_API_KEY_MISSING | 火山 API Key 缺失 | |
| VOLCENGINE_HTTP_ERROR | 火山 HTTP 错误 | |
| VOLCENGINE_HTTP_* | 火山 HTTP 非 200 | |
| VOLCENGINE_API_TYPE_UNSUPPORTED | 火山 API 类型不支持 | |
| VOLCENGINE_MODEL_REQUIRED | 火山模型必填 | |
| VOLCENGINE_MODEL_SYNC_HTTP_ERROR | 火山模型列表同步请求失败 | 管理端模型弹药库 |
| VOLCENGINE_MODEL_SYNC_HTTP_* | 火山模型列表同步返回非 2xx | 管理端模型弹药库 |
| VOLCENGINE_MODEL_SYNC_RESPONSE_INVALID | 火山模型列表同步响应不是 JSON | 管理端模型弹药库 |
| VOLCENGINE_MODEL_SYNC_DATA_INVALID | 火山模型列表同步响应结构不符合预期 | 管理端模型弹药库 |
| KIE_TASK_CREATE_FAILED | KIE 创建任务失败 | |
| KIE_ABILITY_NOT_CONFIGURED | KIE 能力未配置（缺 workflow/model 参数） | 调度前校验失败 |
| KIE_EXECUTION_FAILED | KIE 执行适配器调用失败 | 旧工作流 dispatcher 调用 KIE 测试服务失败 |
| KIE_TASK_FAILED | KIE 任务执行失败 | 返回 state=failed/canceled 等 |
| KIE_TASK_ID_MISSING | KIE 返回 task id 为空 | |
| KIE_API_KEY_MISSING | KIE API Key 缺失 | |
| KIE_MODEL_REQUIRED | KIE 模型必填 | |
| KIE_RESPONSE_INVALID | KIE 返回结构异常 | |
| KIE_STATUS_EMPTY | KIE 状态为空 | |
| KIE_STATUS_ERROR | KIE 状态异常 | |
| KIE_TIMEOUT | KIE 任务硬超时 | 默认 15 分钟 |
| KIE_MODEL_KEY_REQUIRED | KIE 查询缺少 modelKey | `/api/coze/podi/kie/models/schema` |
| KIE_MODEL_NOT_FOUND | KIE 查询模型不存在 | `/api/coze/podi/kie/models/schema` |
| VENDOR_API_EXECUTOR_UNAVAILABLE | 第三方 API 执行服务不可用 | vendor-api-ops 或对应 executor 不可达 |
| VENDOR_API_EXECUTOR_NOT_CONFIGURED | 第三方 API 执行节点未配置 | OpenAI/OpenAI-compatible 等 global-egress 能力无可用 vendor_api executor |
| VENDOR_API_EXECUTOR_NOT_CONFIGURED_LEGACY_ALLOWED | 第三方 API 执行节点未配置但允许旧链路兜底 | 仅 Baidu/Volcengine/KIE 迁移期使用，OpenAI 不允许 |
| VENDOR_API_PROVIDER_NOT_SUPPORTED | 第三方 API provider 暂不支持 | vendor-api-ops provider 未注册 |
| VENDOR_API_INVOCATION_NOT_FOUND | 第三方 API 调用记录不存在 | backend 轮询 vendorInvocationId 时使用 |
| VENDOR_API_EXECUTION_FAILED | 第三方 API 执行失败 | 业务 API/OpenAPI 对底层 vendor-api-ops 失败的通用归类 |
| VENDOR_API_CONCURRENCY_LIMITED | 第三方 API provider/model 并发已满 | 不允许静默 fallback 到本机执行 |
| VENDOR_API_KEY_CONCURRENCY_LIMITED | 第三方 API Key 并发已满 | 可重试；等待释放或确认厂商额度后提高 Key 并发 |
| VENDOR_API_KEY_DISABLED | 第三方 API Key 不可用 | disabled/cooldown/exhausted/error 均需可读提示 |
| VENDOR_API_KEY_MISSING | 第三方 API Key 缺失 | 不暴露 Key 明文 |
| VENDOR_API_KEY_NOT_FOUND | 第三方 API Key 记录不存在 | 单条 Key 编辑、验证 |
| VENDOR_API_AUTH_FAILED | 第三方 API Key 验证失败 | Key 错误、Secret 错误、账号被禁用或额度异常 |
| VENDOR_CREDITS_INSUFFICIENT | 第三方账号余额不足 | KIE/OpenAI-compatible/中转站等返回余额不足时用于健康分类 |
| VENDOR_API_INPUT_INVALID | 第三方 API 入参不合法 | 缺少图片、蒙版、任务必填字段等 provider 级校验失败 |
| VENDOR_API_RATE_LIMITED | 第三方 API 限流 | 应进入 Key 冷却或切换 Key |
| VENDOR_API_TIMEOUT | 第三方 API 调用超时 | 常见于网络出口或代理异常 |
| VENDOR_API_UPSTREAM_ERROR | 第三方 API 上游异常 | 非平台侧参数错误 |
| VENDOR_API_PROXY_UNAVAILABLE | 第三方 API 代理不可用 | 检查 HTTP_PROXY/HTTPS_PROXY 或国际出口节点 |
| VENDOR_API_RESPONSE_INVALID | 第三方 API 返回结构异常 | 需要保留截断 debugResponse |
| VENDOR_PROVIDER_REGISTRY_UNAVAILABLE | 第三方供应商注册表不可读 | 管理端治理摘要降级提示，不中断页面 |
| VENDOR_KEY_STATUS_UNAVAILABLE | 第三方密钥状态不可读 | 管理端治理摘要降级提示，不返回明文 |
| VENDOR_USAGE_SUMMARY_UNAVAILABLE | 第三方调用统计不可读 | 管理端治理摘要降级提示 |
| VENDOR_GOVERNANCE_DB_UNAVAILABLE | 第三方治理摘要读取数据库失败 | 管理端治理摘要降级提示 |
| VENDOR_API_RECENT_FAILURES | 第三方 API 最近调用全失败 | 治理摘要风险提示，需检查密钥/余额/网络出口 |
| VENDOR_API_KEY_QUOTA_EXHAUSTED | 第三方 API Key 配额已用完 | 治理摘要风险提示，需补额度或切换备用 Key |
| VENDOR_API_KEY_QUOTA_NEAR_LIMIT | 第三方 API Key 配额接近上限 | 治理摘要风险提示，需准备备用 Key 或降流量 |
| VENDOR_API_KEY_RECENT_ERROR | 第三方 API Key 最近验证或调用报错 | 治理摘要风险提示，需做单条 Key 验证 |
| VENDOR_MODEL_COST_POLICY_MISSING | 第三方模型缺少计价策略 | 治理摘要风险提示，成功调用前后都可能出现 |
| VENDOR_API_UNCOSTED_SUCCESS_CALLS | 第三方 API 已有成功调用但未计价 | 治理摘要风险提示，收费上线前必须补计价 |
| VENDOR_API_TASKS_QUEUED | 第三方 API 任务排队中 | 治理摘要风险提示，检查厂商并发、Key 并发和重试节奏 |
| VENDOR_API_TASKS_RUNNING_LONG | 第三方 API 任务长时间运行 | 治理摘要风险提示，检查厂商轮询和终态回填 |
| VENDOR_API_TASK_FAILURES | 第三方 API 异步任务失败 | 治理摘要风险提示，查看失败样本和上游错误 |
| VENDOR_MODEL_DUPLICATED | 第三方模型目录项重复 | provider + model 必须唯一 |
| VENDOR_MODEL_NOT_FOUND | 第三方模型目录项不存在 | 管理端编辑模型配置时使用 |
| VENDOR_MODEL_BULK_ACTION_INVALID | 第三方模型批量操作类型非法 | 仅允许启用、停用、记录验收、应用计价 |
| VENDOR_MODEL_BULK_MODEL_IDS_REQUIRED | 第三方模型批量操作缺少模型 ID | 管理端批量处理模型目录 |
| VENDOR_MODEL_INACTIVE | 第三方模型目录项未启用 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_COST_POLICY_INVALID | 第三方模型计价规则非法 | 单价/额度不能小于 0，数字字段必须是数字 |
| VENDOR_MODEL_ACCEPTANCE_STATUS_INVALID | 第三方模型验收状态非法 | 仅允许 `passed/failed/warning/waived` |
| VENDOR_MODEL_ACCEPTANCE_REQUIRED | 第三方模型缺少验收通过记录 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_ACCEPTANCE_MISSING | 第三方模型缺少验收通过记录 | 发版静态审计风险提示 |
| VENDOR_ABILITY_MODEL_UNBOUND | 第三方能力未绑定模型目录 | 发版静态审计风险提示 |
| VENDOR_ABILITY_MODEL_NOT_FOUND | 第三方能力绑定的模型目录不存在 | 发版静态审计风险提示 |
| VENDOR_ABILITY_MODEL_INACTIVE | 第三方能力绑定了未启用模型 | 发版静态审计风险提示 |
| VENDOR_MODEL_RUNTIME_KEY_MISSING | 第三方模型缺少可用运行密钥 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_KEY_CHECK_FAILED | 第三方模型所有可用密钥最近验证失败 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_KEY_CHECK_PARTIAL_FAILED | 第三方模型部分密钥最近验证失败 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_KEY_NEVER_CHECKED | 第三方模型存在未验证密钥 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_KEY_CHECK_STALE | 第三方模型密钥验证过期 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_API_TYPES_MISSING | 第三方模型缺少能力类型描述 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_EXECUTION_MODE_MISSING | 第三方模型缺少返回方式描述 | 模型弹药库上线门禁风险提示 |
| VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED | 第三方模型需要出网节点 | 模型弹药库上线门禁风险提示 |
| VL_IMAGE_REQUIRED | VL 图像理解缺少图片 | `vl_analyze_image` |
| VL_EVAL_IMAGE_REQUIRED | 裂变生成图评估缺少原图或生成图 | `vl_fission_generated_image_evaluate` |
| VL_PROVIDER_ABILITY_NOT_FOUND | VL provider 依赖的原子能力不存在 | 如火山 VL 映射能力缺失 |
| VL_COZE_WORKFLOW_NOT_CONFIGURED | Coze VL 未配置 workflow id | 使用 `coze_vl` provider 时 |
| VL_PROVIDER_UNSUPPORTED | VL provider 暂不支持 | provider 值非法 |
| MEDIA_CALLBACK_BUCKET_MISMATCH | OSS 回调 bucket 与当前配置不一致 | `/api/media/v1/oss-callback` |
| MEDIA_CALLBACK_OBJECT_REQUIRED | OSS 回调缺少 object key | `/api/media/v1/oss-callback` |
| MEDIA_CALLBACK_OBJECT_INVALID | OSS 回调 object key 格式非法 | `/api/media/v1/oss-callback` |
| MEDIA_CALLBACK_OBJECT_OUT_OF_SCOPE | OSS 回调 object key 不在当前上传前缀内 | `/api/media/v1/oss-callback` |
| MEDIA_CALLBACK_SIZE_INVALID | OSS 回调文件大小无效 | `/api/media/v1/oss-callback` |
| IMAGE_OPS_BASE_URL_NOT_CONFIGURED | 图像处理服务地址未配置 | 中台调用 image-ops-service 前置校验失败 |
| IMAGE_OPS_INVALID_RESPONSE | 图像处理服务返回结构异常 | 需查看 image-ops-service 日志和响应结构 |
| IMAGE_OPS_CONTENT_MISSING | 图像处理服务没有返回可入库内容 | 需确认上游服务是否真正产出图片或文件 |
| IMAGE_OPS_CONTENT_INVALID | 图像处理服务返回内容无法解析 | Base64、URL 或文件内容格式异常 |
| IMAGE_DOWNLOAD_FAILED | 下载图片失败 | |
| EXPAND_MASK_RENDER_FAILED | 扩边占位图渲染失败 | PODI 扩边占位工具在 Pillow/图像处理阶段异常。 |
| EXPAND_MASK_UPLOAD_FAILED | 扩边占位图上传失败 | PODI 扩边占位工具在 OSS 上传阶段异常。 |
| IMAGE_BASE64_INVALID | Base64 图片无效 | |
| IMAGE_REQUIRED | 缺少图片 | |
| PODI_IMAGE_TOOLS_IMPORT_FAILED | 图像工具导入失败 | |
| PODI_UTILITY_UNSUPPORTED | 不支持的工具/能力 | |

---

## 9. 维护要求

- 新增/变更错误码：必须更新本表 + 接口文档 + 测试
- 若发现错误码缺失：**视为流程问题**，必须补齐
