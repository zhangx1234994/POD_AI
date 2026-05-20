# 每日早检 SOP

## 目标

每天开始开发前，先确认前一天线上业务有没有异常，再进入当天 TODO。早检不是发版动作，只读数据库和日志，不重启服务、不改配置。

## 固定顺序

1. 确认 114 控制面健康和当前部署版本。
2. 导出前一天运营数据包。
3. 查看业务运行、能力调用、测评运行、业务 API Key 调用是否有异常。
4. 对异常逐条归因：真实业务失败、巡检误报、上游限流、历史脏数据收口、排队超时。
5. 把结论写入早检报告或问题日志。
6. 再进入当天开发 TODO。

## 标准命令

在 114 控制面执行：

```bash
cd /srv/pod
backend/.venv/bin/python backend/scripts/morning_ops_check.py \
  --date 2026-05-13 \
  --json
```

不传 `--date` 时默认检查业务时区的前一天。

输出位置：

```text
reports/morning-check/YYYYMMDD/
reports/morning-check/YYYYMMDD.zip
```

## 导出包结构

```text
YYYYMMDD/
  summary.md
  raw/
    summary.json
    business_runs.json
    business_issues.json
    ability_summary.json
    ability_issues.json
    ability_pending.json
    eval_summary.json
    eval_issues.json
    business_api_key_usage_summary.json
    business_api_key_usage_issues.json
  csv/
    business_runs.csv
    business_issues.csv
    ability_issues.csv
    eval_issues.csv
    ...
```

## 判定口径

- 业务运行异常：`business_runs.status != succeeded`、回调失败、成功但没有图片/视频/文本结果。
- 能力调用异常：`ability_invocation_logs.status` 不是 `success/succeeded`、回调失败、仍有超过 30 分钟的 pending 残留。
- 测评运行异常：`eval_run.status != succeeded`，或成功但没有图片/文本/结构化结果。
- API Key 异常：状态码非 2xx、缺状态码或存在错误码。

## 归因规则

- 如果业务最终成功、OSS 已回填，但测评端失败，多数是测评等待窗口或巡检参数问题，不直接判业务失败。
- 如果是 `RequestBurstTooFast`、`TooManyRequests`、`429`，优先归为上游限流或流量突增保护。
- 如果是 `ABILITY_LOG_STALE_PENDING`，优先归为历史 pending 收口结果；需要确认同时间段是否有真实业务失败。
- 如果是缺图、缺参数类错误，先确认巡检脚本是否按接口 schema 构造了必填字段。

## 今日已知样例

2026-05-14 早检发现：

- 2026-05-13 业务运行 188 条，业务失败 0 条。
- 能力异常 6 条，其中 4 条是历史 pending 残留被收口，1 条是火山 VL 突增保护，1 条是裂变评分巡检缺双图参数。
- 测评异常 1 条，为裂变评分巡检缺双图参数。
- 另有一条测评端 30 分钟超时但底层业务随后成功回图的历史记录，已通过恢复逻辑补全为成功，不再计入当天失败。

本日线上核验结论：

- 114 后端、管理端、测评端健康。
- 158 / 233 两台 ComfyUI 均在线，队列为空，后端队列汇总识别容量 20、空闲 20。
- 业务 route-preview：花纹提取、图裂变、扩图 3 条主业务均可命中默认版本。

2026-05-20 早检发现：

- 滚动 24 小时内 `fission / gpt-image2-vl-v2` 存在间歇性 `VENDOR_API_CLIENT_FORBIDDEN`；同批也有成功记录，说明不是 OpenAI 或业务接口整体不可用。
- 本地开发机残留 `uvicorn app.main:app --reload --port 8099`，且本地 `.env` 连接线上数据库，存在误消费线上任务和写入线上日志风险；已立即停止。
- 当发现 vendor-api 白名单拒绝时，必须先排查是否有非生产后端实例消费线上任务，再考虑扩大白名单。
- 早检后续改进项：本地后端连接线上库时默认禁用后台任务消费；`vendor-api-ops` 记录来源 IP、路径和拒绝原因。
