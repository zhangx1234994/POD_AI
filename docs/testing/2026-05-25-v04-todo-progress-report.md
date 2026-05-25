# v0.4 TODO 推进报告（2026-05-25）

## 结论

- 本轮按唯一 TODO 继续推进 v0.4 封版准备，重点收口图编辑 `canvas_outpaint` 巡检、业务运行摘要性能风险、接口文档错误码一致性和本地门禁。
- 5090 独立 ComfyUI 扩图失败已归因为节点插件/Schema 不同构，当前不调整中台路由，也不把扩图固定到 4090。
- 当前仍不建议进入 114 更新：真实 GPT Image 2 低质量样例、Coze 工具箱抽测、测评端核心视觉走查还未完成。

## 本轮已处理

1. 图编辑扩展画布巡检
   - 发布巡检脚本新增 `canvas_outpaint_all_sides`、`canvas_outpaint_left`、`canvas_outpaint_horizontal`、`canvas_outpaint_vertical` 四类样例。
   - 新增单测校验图编辑巡检 case 清单、扩图 payload、未知 case 拦截，防止封版前只覆盖旧四种图编辑模式。
   - 交付文档的封版样例要求从旧四类图编辑扩展为至少八类：局部修改、参考图替换、删除修补、补色校正、四边扩图、单边扩图、横向扩图、纵向扩图。

2. 业务运行摘要性能
   - 业务运行摘要列表不再默认加载 `result_payload`，减少列表和管理端总览扫描大 JSON 的风险。
   - 近 24 小时接口用量观察：`/api/business/runs/get` 约 1401 次，平均约 146ms，最大约 4.8s，未见 5s 以上记录。
   - 直接对 `business_runs` 大 JSON 字段做排序/长度扫描会触发 MySQL `Out of sort memory`，后续仍需把“长 payload 不参与列表查询”作为硬约束继续治理。

3. 对外接口文档门禁
   - 补齐 `IMAGE_EDIT_CANVAS_TOO_SMALL`、`IMAGE_EDIT_CANVAS_PLACEMENT_INVALID`、`IMAGE_EDIT_CANVAS_BUILD_FAILED` 在业务接口常见错误列表和业务枚举文档中的入口。
   - 错误码总表、业务接口文档、图编辑内部交付文档目前已对齐。

4. 5090 扩图问题归因
   - 近 10 小时失败集中在 158/5090，233/4090 同期可跑通。
   - 5090 的 `DrawMaskOnImage` 节点要求必填 `opacity`，4090 同节点不要求；当前 workflow 节点 104 未写 `opacity`。
   - 节点刚补齐前还出现过 `missing_node_type: Draw Mask On Image`，补节点后转为 `required_input_missing: opacity`。
   - 处理策略：由服务器侧做 ComfyUI 节点/插件同构；中台不写单机特判，不调整优先路由。

## 本轮验证

- `python3 scripts/check_error_catalog.py`：通过。
- `python3 scripts/check_doc_entry_references.py`：通过。
- `backend/.venv/bin/python -m pytest backend/tests/test_patrol_image_edit_business.py backend/tests/test_business_api_contract.py backend/tests/test_podi_release_smoke.py -q`：112 passed，11 warnings。
- `podi-admin-web npm run lint`：通过。
- `podi-eval-web npm run lint`：通过。
- `podi-admin-web npm run build`：通过。
- `podi-eval-web npm run build`：通过。

## 未覆盖风险

- 尚未真实调用 GPT Image 2 跑 `canvas_outpaint` 低质量样例，因此图像质量、耗时、成本和结果导出还不能作为封版证据。
- 尚未做 Coze 工具箱抽测。
- 尚未做测评端核心视觉走查和管理端业务链路图草稿闭环真实写入验证。
- 业务摘要性能只处理了列表重 payload 风险；`usage-summary`、索引和缓存策略还需要下一轮继续压测。

## 下一步

1. 跑真实 GPT Image 2 图编辑八类样例，导出原图、参考图、mask、编译提示词、结果图、耗时和成本。
2. 完成 Coze 工具箱抽测与测评端核心路径视觉走查。
3. 继续治理 `business/runs` 与 `usage-summary` 的长字段、索引和缓存策略。
4. 补业务链路图“复制草稿 -> 修改步骤 -> 保存 -> 试运行 -> 验收”的真实闭环证据。
