# 项目 / 数据库 / OSS 清理治理

## 目标

把“脏东西”从临时动作变成固定治理动作，避免项目目录、数据库状态和 OSS 存储长期堆积，影响排查、发版和业务判断。

## 清理分层

| 层级 | 可直接清理 | 必须复核 | 禁止直接删除 |
| --- | --- | --- | --- |
| 项目文件 | `dist`、`__pycache__`、`.pytest_cache`、Playwright 日志、`.DS_Store`、`*.log` | 大 zip、交付包、一次性报告 | `.venv`、`node_modules`、未提交源码 |
| 数据库 | 空草稿批次、明显孤儿子表记录 | 长期 running/pending、成功但无结果、过期 Key | 业务运行主表、账单、API Key 使用日志的物理删除 |
| OSS | 超过保留窗口、数据库无引用、测试前缀对象 | 质量样本包、业务交付图、测评复盘图 | 业务返回给客户/AI 团队的稳定链接 |

## 固定审计命令

只审计项目和数据库，不列举 OSS：

```bash
python3 backend/scripts/audit_cleanup_candidates.py \
  --output-dir reports/cleanup-audit/$(date +%Y%m%d_%H%M%S)
```

审计项目、数据库和 OSS 抽样：

```bash
python3 backend/scripts/audit_cleanup_candidates.py \
  --list-oss \
  --oss-max-objects 1000 \
  --oss-delete-batch-size 100 \
  --reference-scan-limit 20000 \
  --output-dir reports/cleanup-audit/$(date +%Y%m%d_%H%M%S)
```

只审计本地项目文件：

```bash
python3 backend/scripts/audit_cleanup_candidates.py \
  --skip-db \
  --output-dir reports/cleanup-audit/local-only
```

## 删除前规则

1. 先生成审计报告，保留 `summary.md`、`cleanup_candidates.csv` 和 `raw/*.json`。
2. 本地低风险产物可以直接删，但删完必须复扫确认候选为 0。
3. 数据库默认不做物理删除，优先修正状态、标记归档或转历史表。
4. OSS 删除前必须满足三条件：数据库无引用、超过保留窗口、不是交付或复盘样本。
5. OSS 删除必须先导出对象清单，再小批量删除，首批建议不超过 100 个。
6. 删除后必须跑早检和核心业务 smoke，确认业务、测评、回填不受影响。

## OSS 复核清单

审计脚本会额外生成两类文件：

- `raw/oss_candidate_groups.json`：按对象前缀和月份聚合，先判断候选对象是否集中在测试目录、临时目录或历史批量测试目录。
- `oss_delete_review_manifest.csv`：按小批量生成复核清单，每行默认 `decision=review_required`、`delete_allowed=no`，只用于人工确认，不代表已经允许删除。

复核流程：

1. 先看 `summary.md` 的 OSS 候选分组 Top 20，确认主要候选来自测试前缀。
2. 打开 `oss_delete_review_manifest.csv`，只把确定可删的行改为 `delete_allowed=yes`。
3. 首批删除不超过 100 个对象。
4. 删除后必须重新跑清理审计、每日早检和核心业务 smoke。

## 2026-05-14 首轮审计结果

- 本地低风险产物：24 项，约 17.69MB，已清理并复扫为 0。
- 本地需复核大文件：`deliverables/comfyui_fission_quality_pack_20260513.zip`，属于质量样本包，暂不按垃圾删除。
- 数据库：未发现长时间未收口业务、能力、测评记录；未发现孤儿业务步骤；未发现过期仍 active 的 API Key。
- OSS：抽样前 1000 个 `test/` 对象中，880 个超过保留窗口且未在主要数据库引用中出现，约 516MB。该结论仍需二次抽查和小批量删除验证，暂不直接删除。
- 2026-05-14 追加：审计脚本已支持生成 OSS 候选分组和小批量复核清单，仍保持只读，不执行删除。

## 后续动作

- 将 OSS 清理做成“候选清单 -> 人工确认 -> 小批量删除 -> 业务回归”的闭环。
- 管理端后续可增加“存储治理”页面，展示测试前缀对象、估算容量、保留策略和删除记录。
- 发布 SOP 中加入“发版前本地脏产物复扫”，避免构建产物、日志和缓存混入发布包。
