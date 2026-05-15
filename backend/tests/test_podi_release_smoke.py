from __future__ import annotations

import importlib.util
import json
from pathlib import Path


AUTH_BUSINESS_API_POLICY = [
    {
        "key": "client_user_bound_scope",
        "title": "业务方账号只能使用绑定范围",
        "detail": "强制使用账号绑定范围",
        "enforced": True,
    },
    {
        "key": "unscoped_client_user_blocked",
        "title": "未绑定业务方的账号不能调用业务 API",
        "detail": "缺 tenantId 时拒绝调用",
        "enforced": True,
    },
    {
        "key": "admin_service_can_act_as_tenant",
        "title": "管理员和服务 Token 可代业务方发起任务",
        "detail": "允许后台任务显式指定范围",
        "enforced": True,
    },
]

AUTH_ROLE_BOUNDARY = [
    {
        "key": "admin_user",
        "title": "管理员账号",
        "principal": "管理端管理员",
        "allowed": "维护用户和发布门禁",
        "blocked": "不能把自己降权或停用",
        "enforced": True,
    },
    {
        "key": "client_user",
        "title": "业务方账号",
        "principal": "业务接入方",
        "allowed": "只能调用绑定业务方范围",
        "blocked": "不能越权传入其他 tenantId/clientId",
        "enforced": True,
    },
    {
        "key": "service_token",
        "title": "服务 Token",
        "principal": "巡检脚本和后台任务",
        "allowed": "可代业务方排障",
        "blocked": "不能发给业务方当登录账号",
        "enforced": True,
    },
    {
        "key": "coze_toolbox",
        "title": "Coze 工具箱",
        "principal": "Coze 工作流",
        "allowed": "只调用中台工具箱",
        "blocked": "不能直连 ComfyUI 或厂商通道",
        "enforced": True,
    },
]


def _load_smoke_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "podi_release_smoke.py"
    spec = importlib.util.spec_from_file_location("podi_release_smoke", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_eval_workflow_catalog_check_accepts_public_roles() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {"workflow_id": "wf_prod", "governance": {"role": "production"}, "presentation": {"visible": True}},
            {"workflow_id": "wf_candidate", "governance": {"role": "candidate"}, "presentation": {"visible": True}},
        ]
    )

    assert ok is True
    assert "production" in detail


def test_eval_workflow_catalog_check_blocks_leaked_internal_roles() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {"workflow_id": "wf_prod", "governance": {"role": "production"}, "presentation": {"visible": True}},
            {"workflow_id": "wf_aux", "governance": {"role": "auxiliary"}, "presentation": {"visible": True}},
        ]
    )

    assert ok is False
    assert "non-public roles leaked" in detail


def test_eval_workflow_catalog_check_blocks_duplicate_workflow_ids() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod",
                "category": "四方/两方连续图类",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
        ]
    )

    assert ok is False
    assert "duplicated workflow ids" in detail


def test_eval_workflow_catalog_check_requires_a_production_entry() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [{"workflow_id": "wf_candidate", "governance": {"role": "candidate"}, "presentation": {"visible": True}}]
    )

    assert ok is False
    assert "no production workflow" in detail


def test_eval_workflow_catalog_check_blocks_too_many_production_entries_per_category() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod_1",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_2",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_3",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
        ],
        max_production_per_category=2,
    )

    assert ok is False
    assert "too many production workflows" in detail


def test_eval_workflow_catalog_check_allows_configured_production_limit() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_eval_workflow_catalog(
        [
            {
                "workflow_id": "wf_prod_1",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_prod_2",
                "category": "图裂变",
                "governance": {"role": "production"},
                "presentation": {"visible": True},
            },
            {
                "workflow_id": "wf_candidate",
                "category": "图裂变",
                "governance": {"role": "candidate"},
                "presentation": {"visible": True},
            },
        ],
        max_production_per_category=2,
    )

    assert ok is True
    assert "productionByCategory" in detail


def test_internal_eval_workflow_catalog_requires_auxiliary_tools() -> None:
    module = _load_smoke_module()

    rows = [
        {"workflow_id": "wf_prod", "category": "图裂变", "governance": {"role": "production"}, "presentation": {"visible": True}},
        {"workflow_id": "wf_candidate", "category": "通用类", "governance": {"role": "candidate"}, "presentation": {"visible": True}},
    ]
    for workflow_id in module.REQUIRED_INTERNAL_EVAL_AUXILIARY_WORKFLOW_IDS:
        rows.append(
            {
                "workflow_id": workflow_id,
                "category": "通用类",
                "governance": {"role": "auxiliary"},
                "presentation": {"visible": False, "categoryLabel": "通用类"},
            }
        )

    ok, detail = module._validate_internal_eval_workflow_catalog(rows)

    assert ok is True
    assert "auxiliary" in detail


def test_internal_eval_workflow_catalog_blocks_hidden_public_workflows() -> None:
    module = _load_smoke_module()

    rows = [
        {"workflow_id": "wf_prod", "category": "图裂变", "governance": {"role": "production"}, "presentation": {"visible": False}},
    ]
    for workflow_id in module.REQUIRED_INTERNAL_EVAL_AUXILIARY_WORKFLOW_IDS:
        rows.append(
            {
                "workflow_id": workflow_id,
                "category": "通用类",
                "governance": {"role": "auxiliary"},
                "presentation": {"visible": False},
            }
        )

    ok, detail = module._validate_internal_eval_workflow_catalog(rows)

    assert ok is False
    assert "hidden public workflows" in detail


def test_internal_eval_workflow_catalog_blocks_missing_auxiliary_tool() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_internal_eval_workflow_catalog(
        [
            {"workflow_id": "wf_prod", "category": "图裂变", "governance": {"role": "production"}, "presentation": {"visible": True}},
            {"workflow_id": "wf_candidate", "category": "通用类", "governance": {"role": "candidate"}, "presentation": {"visible": True}},
        ]
    )

    assert ok is False
    assert "missing required auxiliary workflows" in detail


def test_internal_eval_workflow_catalog_blocks_legacy_leak() -> None:
    module = _load_smoke_module()

    rows = [
        {"workflow_id": "wf_prod", "category": "图裂变", "governance": {"role": "production"}, "presentation": {"visible": True}},
        {"workflow_id": "wf_legacy", "category": "图延伸类", "governance": {"role": "legacy"}, "presentation": {"visible": True}},
    ]
    for workflow_id in module.REQUIRED_INTERNAL_EVAL_AUXILIARY_WORKFLOW_IDS:
        rows.append(
            {
                "workflow_id": workflow_id,
                "category": "通用类",
                "governance": {"role": "auxiliary"},
                "presentation": {"visible": True},
            }
        )

    ok, detail = module._validate_internal_eval_workflow_catalog(rows)

    assert ok is False
    assert "unexpected roles" in detail


def test_comfyui_queue_summary_check_allows_single_node_degraded_route() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_233"}],
            "supportedServers": 1,
            "unsupportedServers": 1,
            "backendBlockedServers": 0,
            "totalCapacity": 10,
            "totalIdleSlots": 9,
            "utilization": 0.1,
            "diagnostics": [{"code": "COMFYUI_EXECUTOR_UNAVAILABLE"}],
        }
    )

    assert ok is True
    assert "unsupportedServers=1" in detail


def test_comfyui_queue_summary_check_blocks_when_no_supported_executor() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_158"}],
            "supportedServers": 0,
            "unsupportedServers": 1,
            "backendBlockedServers": 0,
            "diagnostics": [{"code": "COMFYUI_EXECUTOR_UNAVAILABLE"}],
        }
    )

    assert ok is False
    assert "no supported ComfyUI server" in detail


def test_comfyui_queue_summary_check_blocks_backend_running_not_visible() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_158"}],
            "supportedServers": 1,
            "unsupportedServers": 0,
            "backendBlockedServers": 1,
            "diagnostics": [{"code": "COMFYUI_BACKEND_RUNNING_NOT_VISIBLE"}],
        }
    )

    assert ok is False
    assert "backendBlockedServers=1" in detail


def test_comfyui_queue_summary_check_allows_feed_gap_as_warning_detail() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_queue_summary(
        {
            "servers": [{"executorId": "executor_158"}, {"executorId": "executor_233"}],
            "supportedServers": 2,
            "unsupportedServers": 0,
            "backendBlockedServers": 0,
            "feedGapServers": 1,
            "totalCapacity": 20,
            "totalIdleSlots": 8,
            "utilization": 0.6,
            "diagnostics": [{"code": "COMFYUI_FEED_GAP"}],
        }
    )

    assert ok is True
    assert "feedGapServers=1" in detail


def test_comfyui_workflow_compatibility_blocks_failed_workflows() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_workflow_compatibility(
        {
            "totalWorkflows": 2,
            "okCount": 1,
            "warningCount": 0,
            "failedCount": 1,
            "servers": [{"executorId": "executor_158", "reachable": True}],
            "workflows": [
                {
                    "abilityId": "comfyui_ok",
                    "workflowKey": "ok",
                    "status": "ok",
                    "incompatibleExecutorIds": [],
                },
                {
                    "abilityId": "comfyui_bad",
                    "workflowKey": "bad",
                    "status": "failed",
                    "incompatibleExecutorIds": ["executor_233"],
                    "servers": [
                        {
                            "executorId": "executor_233",
                            "compatible": False,
                            "reachable": True,
                            "missingNodes": [{"nodeId": "9", "classType": "MissingNode"}],
                            "missingModels": [{"nodeId": "1", "classType": "UNETLoader", "inputName": "unet_name", "value": "missing.safetensors"}],
                        }
                    ],
                },
            ],
        }
    )

    assert ok is False
    assert "failed=1" in detail
    assert "comfyui_bad" in detail
    assert "MissingNode" in detail
    assert "missing.safetensors" in detail


def test_comfyui_workflow_compatibility_blocks_warnings_by_default() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_workflow_compatibility(
        {
            "totalWorkflows": 1,
            "okCount": 0,
            "warningCount": 1,
            "failedCount": 0,
            "servers": [{"executorId": "executor_158", "reachable": True}],
            "workflows": [
                {
                    "abilityId": "comfyui_partial",
                    "workflowKey": "partial",
                    "status": "warning",
                    "incompatibleExecutorIds": ["executor_233"],
                    "servers": [
                        {
                            "executorId": "executor_233",
                            "compatible": False,
                            "reachable": True,
                            "missingNodes": [],
                            "missingModels": [{"nodeId": "1", "classType": "LoraLoader", "inputName": "lora_name", "value": "missing-lora.safetensors"}],
                        }
                    ],
                }
            ],
        }
    )

    assert ok is False
    assert "warnings=1" in detail
    assert "missing-lora.safetensors" in detail


def test_comfyui_workflow_compatibility_can_allow_warnings_explicitly() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_comfyui_workflow_compatibility(
        {
            "totalWorkflows": 1,
            "okCount": 0,
            "warningCount": 1,
            "failedCount": 0,
            "servers": [{"executorId": "executor_158", "reachable": True}],
            "workflows": [
                {
                    "abilityId": "comfyui_partial",
                    "workflowKey": "partial",
                    "status": "warning",
                    "incompatibleExecutorIds": ["executor_233"],
                }
            ],
        },
        allow_warnings=True,
    )

    assert ok is True
    assert "warnings=1" in detail


def test_business_usage_summary_check_accepts_clean_summary() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_usage_summary(
        {
            "total": 10,
            "failed": 0,
            "running": 0,
            "queued": 0,
            "byIssue": [{"key": "none", "label": "暂无明显问题", "total": 10}],
            "unresolvedIssues": [],
            "recentUnresolvedIssues": [],
        }
    )

    assert ok is True
    assert "unresolved=0" in detail


def test_business_usage_summary_check_blocks_unresolved_issues_by_default() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_usage_summary(
        {
            "total": 10,
            "failed": 1,
            "running": 0,
            "queued": 0,
            "byIssue": [{"key": "executor", "label": "执行节点问题", "total": 1}],
            "unresolvedIssues": [{"key": "executor", "label": "执行节点问题", "total": 1, "retested": 0}],
            "recentUnresolvedIssues": [
                {
                    "id": "run_a",
                    "businessKey": "fission",
                    "issueCategory": "executor",
                    "issueLabel": "执行节点问题",
                    "createdAt": "2026-05-04T10:00:00",
                }
            ],
        }
    )

    assert ok is False
    assert "unresolved=1" in detail


def test_business_usage_summary_check_allows_configured_unresolved_threshold() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_usage_summary(
        {
            "total": 10,
            "failed": 1,
            "running": 0,
            "queued": 0,
            "byIssue": [{"key": "executor", "label": "执行节点问题", "total": 1}],
            "unresolvedIssues": [{"key": "executor", "label": "执行节点问题", "total": 1, "retested": 1}],
            "recentUnresolvedIssues": [
                {
                    "id": "run_a",
                    "businessKey": "fission",
                    "issueCategory": "executor",
                    "issueLabel": "执行节点问题",
                    "createdAt": "2026-05-04T10:00:00",
                }
            ],
        },
        max_unresolved_issues=1,
    )

    assert ok is True
    assert "unresolved=1" in detail


def test_business_usage_summary_check_blocks_recent_unresolved_schema_gap() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_usage_summary(
        {
            "total": 1,
            "failed": 1,
            "running": 0,
            "queued": 0,
            "byIssue": [{"key": "executor", "label": "执行节点问题", "total": 1}],
            "unresolvedIssues": [{"key": "executor", "label": "执行节点问题", "total": 1}],
            "recentUnresolvedIssues": [{"id": "run_a", "businessKey": "fission"}],
        },
        max_unresolved_issues=10,
    )

    assert ok is False
    assert "schema gaps" in detail


def test_business_api_usage_center_check_accepts_empty_window() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_api_usage_center(
        {
            "items": [],
            "total": 0,
            "offset": 0,
            "limit": 10,
            "pagination": {"total": 0, "offset": 0, "limit": 10, "hasMore": False, "nextOffset": None},
            "summary": {
                "total": 0,
                "successCount": 0,
                "errorCount": 0,
                "submitCount": 0,
                "pollCount": 0,
                "callbackCount": 0,
                "uniqueRunCount": 0,
                "averageDurationMs": None,
            },
            "groups": [],
        }
    )

    assert ok is True
    assert "total=0" in detail


def test_business_api_usage_center_check_accepts_grouped_business_calls() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_api_usage_center(
        {
            "items": [
                {
                    "id": 1,
                    "method": "POST",
                    "path": "/api/business/fission/runs",
                    "statusCode": 200,
                    "businessKey": "fission",
                    "runId": "run_001",
                    "createdAt": "2026-05-15T10:00:00",
                }
            ],
            "total": 2,
            "offset": 0,
            "limit": 10,
            "pagination": {"total": 2, "offset": 0, "limit": 10, "hasMore": False, "nextOffset": None},
            "summary": {
                "total": 2,
                "successCount": 2,
                "errorCount": 0,
                "submitCount": 1,
                "pollCount": 1,
                "callbackCount": 0,
                "uniqueRunCount": 1,
                "averageDurationMs": 120.0,
            },
            "groups": [
                {
                    "runId": "run_001",
                    "businessKey": "fission",
                    "totalCount": 2,
                    "submitCount": 1,
                    "pollCount": 1,
                    "callbackCount": 0,
                    "errorCount": 0,
                    "needsAttention": False,
                    "lastSeenAt": "2026-05-15T10:01:00",
                }
            ],
        }
    )

    assert ok is True
    assert "runs=1" in detail
    assert "groups=1" in detail


def test_business_api_usage_center_check_blocks_missing_group_when_runs_exist() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_api_usage_center(
        {
            "items": [],
            "total": 1,
            "offset": 0,
            "limit": 10,
            "pagination": {"total": 1, "offset": 0, "limit": 10, "hasMore": False, "nextOffset": None},
            "summary": {
                "total": 1,
                "successCount": 1,
                "errorCount": 0,
                "submitCount": 1,
                "pollCount": 0,
                "callbackCount": 0,
                "uniqueRunCount": 1,
                "averageDurationMs": 120.0,
            },
            "groups": [],
        }
    )

    assert ok is False
    assert "run groups are empty" in detail


def test_business_api_usage_center_check_blocks_schema_gap() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_api_usage_center(
        {
            "items": [{"id": 1, "method": "POST"}],
            "pagination": {"total": 1, "offset": 0, "limit": 10, "hasMore": False, "nextOffset": None},
            "summary": {
                "total": 1,
                "successCount": 1,
                "errorCount": 0,
                "submitCount": 1,
                "pollCount": 0,
                "callbackCount": 0,
                "uniqueRunCount": 0,
                "averageDurationMs": 120.0,
            },
            "groups": [],
        }
    )

    assert ok is False
    assert "schema gaps" in detail


def _write_business_delivery_fixture(tmp_path: Path, *, omit_sample: str | None = None, omit_error_code: bool = False) -> None:
    module = _load_smoke_module()
    base = tmp_path / "docs" / "api" / "examples" / "fission-business-delivery"
    base.mkdir(parents=True)
    (base / "README.md").write_text(
        "统一说明：runId /api/business/runs/get status 错误码",
        encoding="utf-8",
    )
    samples = {
        "request.example.json": {"imageUrl": "https://example.com/input.png"},
        "submit.response.example.json": {
            "runId": "run_001",
            "taskId": "run_001",
            "status": "queued",
            "taskStatus": "queued",
            "retryAfterSeconds": 5,
        },
        "poll.request.example.json": {"runId": "run_001"},
        "poll.running.response.example.json": {"runId": "run_001", "status": "running"},
        "poll.succeeded.response.example.json": {"runId": "run_001", "status": "succeeded"},
        "poll.failed.response.example.json": {
            "runId": "run_001",
            "status": "failed",
            "errorCode": "ABILITY_TASK_FAILED",
            "errorMessage": "failed",
        },
    }
    for spec in module.BUSINESS_DELIVERY_DOC_SPECS:
        folder = base / spec["folder"]
        folder.mkdir(parents=True)
        enum_text = " ".join(spec["enum_fields"])
        error_codes = list(spec["error_codes"])
        if omit_error_code and spec["key"] == "fission_generated_image_score":
            error_codes = error_codes[1:]
        error_text = " ".join(error_codes)
        (folder / "README.md").write_text(
            f"{spec['path']}\n参数说明\n枚举说明 {enum_text}\n常见错误 {error_text}\nrunId status\n",
            encoding="utf-8",
        )
        for sample_name, payload in samples.items():
            if omit_sample == sample_name and spec["key"] == "gpt_image2_controlled_fission":
                continue
            (folder / sample_name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_business_delivery_docs_check_accepts_current_repo() -> None:
    module = _load_smoke_module()
    repo_root = Path(__file__).resolve().parents[2]

    ok, detail = module._validate_business_delivery_docs(repo_root)

    assert ok is True
    assert "contracts=3" in detail


def test_business_delivery_docs_check_blocks_missing_sample(tmp_path: Path) -> None:
    module = _load_smoke_module()
    _write_business_delivery_fixture(tmp_path, omit_sample="poll.failed.response.example.json")

    ok, detail = module._validate_business_delivery_docs(tmp_path)

    assert ok is False
    assert "missing sample=poll.failed.response.example.json" in detail


def test_business_delivery_docs_check_blocks_missing_error_code(tmp_path: Path) -> None:
    module = _load_smoke_module()
    _write_business_delivery_fixture(tmp_path, omit_error_code=True)

    ok, detail = module._validate_business_delivery_docs(tmp_path)

    assert ok is False
    assert "VL_EVAL_IMAGE_REQUIRED" in detail


def test_per_feature_release_checklist_accepts_current_repo() -> None:
    module = _load_smoke_module()
    repo_root = Path(__file__).resolve().parents[2]

    ok, detail = module._validate_per_feature_release_checklist(repo_root)

    assert ok is True
    assert "per-feature-release-checklist.md" in detail


def test_per_feature_release_checklist_blocks_missing_required_tokens(tmp_path: Path) -> None:
    module = _load_smoke_module()
    checklist = tmp_path / "docs" / "standards" / "per-feature-release-checklist.md"
    checklist.parent.mkdir(parents=True)
    checklist.write_text("# 逐功能上线检查表\n\n只有标题，没有节点和功能明细。\n", encoding="utf-8")

    ok, detail = module._validate_per_feature_release_checklist(tmp_path)

    assert ok is False
    assert "String" in detail


def _accepted_release_gate() -> dict:
    return {
        "latestAcceptance": {"status": "passed", "note": "测试通过"},
        "releaseGate": {"status": "ready", "blockers": []},
    }


def test_business_capability_governance_accepts_ready_core_defaults() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_capability_governance(
        {
            "items": [
                {
                    "id": "biz_pattern_extract_v1",
                    "businessKey": "pattern_extract",
                    "version": "v1",
                    "displayName": "花纹提取",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_pattern",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
                {
                    "id": "biz_fission_v1",
                    "businessKey": "fission",
                    "version": "v1",
                    "displayName": "图裂变",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_fission",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
                {
                    "id": "biz_outpaint_v1",
                    "businessKey": "outpaint",
                    "version": "v1",
                    "displayName": "扩图",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_outpaint",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
            ]
        }
    )

    assert ok is True
    assert "defaults=3" in detail


def test_business_capability_governance_blocks_missing_default() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_capability_governance(
        {
            "items": [
                {
                    "id": "biz_fission_v1",
                    "businessKey": "fission",
                    "version": "v1",
                    "displayName": "图裂变",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_fission",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                }
            ]
        }
    )

    assert ok is False
    assert "missing core business defaults" in detail


def test_business_capability_governance_blocks_default_runtime_issue() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_capability_governance(
        {
            "items": [
                {
                    "id": "biz_pattern_extract_v1",
                    "businessKey": "pattern_extract",
                    "version": "v1",
                    "displayName": "花纹提取",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_pattern",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
                {
                    "id": "biz_fission_v1",
                    "businessKey": "fission",
                    "version": "v1",
                    "displayName": "图裂变",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_fission",
                    "governanceStatus": "blocker",
                    "governanceIssues": ["BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING"],
                    **_accepted_release_gate(),
                },
                {
                    "id": "biz_outpaint_v1",
                    "businessKey": "outpaint",
                    "version": "v1",
                    "displayName": "扩图",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_outpaint",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
            ]
        }
    )

    assert ok is False
    assert "business governance blockers" in detail


def test_business_capability_governance_blocks_missing_acceptance() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_business_capability_governance(
        {
            "items": [
                {
                    "id": "biz_pattern_extract_v1",
                    "businessKey": "pattern_extract",
                    "version": "v1",
                    "displayName": "花纹提取",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_pattern",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                },
                {
                    "id": "biz_fission_v1",
                    "businessKey": "fission",
                    "version": "v1",
                    "displayName": "图裂变",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_fission",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
                {
                    "id": "biz_outpaint_v1",
                    "businessKey": "outpaint",
                    "version": "v1",
                    "displayName": "扩图",
                    "status": "active",
                    "isDefault": True,
                    "primaryAbilityId": "ability_outpaint",
                    "governanceStatus": "ready",
                    "governanceIssues": [],
                    **_accepted_release_gate(),
                },
            ]
        }
    )

    assert ok is False
    assert "acceptance-required" in detail


def test_commercial_report_check_accepts_clean_report() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_commercial_report(
        {
            "runCount": 8,
            "billableRunCount": 6,
            "chargedRunCount": 6,
            "unpricedRunCount": 0,
            "billingIssueCount": 0,
            "paidPackageOrderCount": 2,
            "pendingPackageOrderCount": 0,
            "costByCurrency": [{"currency": "USD", "amount": 0.5}],
            "packageOrderRevenueByCurrency": [{"currency": "CNY", "amountCents": 39800}],
            "pendingPackageRevenueByCurrency": [],
            "businessRows": [
                {
                    "businessKey": "fission",
                    "runCount": 8,
                    "chargedRunCount": 6,
                    "billingIssueCount": 0,
                }
            ],
            "riskItems": [],
        }
    )

    assert ok is True
    assert "billingIssues=0" in detail


def test_commercial_report_check_blocks_billing_issues_by_default() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_commercial_report(
        {
            "runCount": 2,
            "billableRunCount": 1,
            "chargedRunCount": 0,
            "unpricedRunCount": 1,
            "billingIssueCount": 1,
            "paidPackageOrderCount": 0,
            "pendingPackageOrderCount": 0,
            "costByCurrency": [],
            "packageOrderRevenueByCurrency": [],
            "pendingPackageRevenueByCurrency": [],
            "businessRows": [
                {
                    "businessKey": "fission",
                    "runCount": 2,
                    "chargedRunCount": 0,
                    "billingIssueCount": 1,
                }
            ],
            "riskItems": [{"runId": "run_a", "issueLabel": "成功任务未扣费"}],
        }
    )

    assert ok is False
    assert "billingIssues=1" in detail


def test_commercial_report_check_blocks_schema_gap() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_commercial_report(
        {
            "runCount": 1,
            "billableRunCount": 1,
            "chargedRunCount": 1,
            "unpricedRunCount": 0,
            "billingIssueCount": 0,
            "paidPackageOrderCount": 0,
            "pendingPackageOrderCount": 0,
            "costByCurrency": [],
            "packageOrderRevenueByCurrency": [],
            "pendingPackageRevenueByCurrency": [],
            "businessRows": [{"businessKey": "fission"}],
            "riskItems": [],
        }
    )

    assert ok is False
    assert "schema gaps" in detail


def test_auth_scope_summary_check_accepts_healthy_summary() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": True,
            "blockingRiskCount": 0,
            "warningRiskCount": 0,
            "totals": {
                "users": 3,
                "activeUsers": 3,
                "adminUsers": 1,
                "clientUsers": 1,
                "unscopedClientUsers": 0,
                "activeSessions": 2,
                "activeInvites": 1,
                "unscopedActiveInvites": 0,
                "expiredActiveInvites": 0,
            },
            "roles": [{"role": "admin", "count": 1, "activeCount": 1}],
            "tenants": [{"tenantId": "tenant-a", "clientId": "client-web", "userCount": 1}],
            "risks": [{"key": "ok", "title": "账号范围正常", "severity": "success", "count": 0, "detail": "正常"}],
            "checklist": [
                {
                    "key": "admin_login_available",
                    "title": "管理员可登录",
                    "passed": True,
                    "detail": "正常",
                    "action": "无需处理",
                }
            ],
            "businessApiPolicy": AUTH_BUSINESS_API_POLICY,
            "roleBoundary": AUTH_ROLE_BOUNDARY,
        }
    )

    assert ok is True
    assert "admins=1" in detail
    assert "policies=3" in detail
    assert "boundaries=4" in detail


def test_auth_scope_summary_check_blocks_missing_admin() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": False,
            "blockingRiskCount": 1,
            "warningRiskCount": 0,
            "totals": {
                "users": 3,
                "activeUsers": 3,
                "adminUsers": 0,
                "clientUsers": 1,
                "unscopedClientUsers": 0,
                "activeSessions": 2,
                "activeInvites": 1,
                "unscopedActiveInvites": 0,
                "expiredActiveInvites": 0,
            },
            "roles": [{"role": "client", "count": 1, "activeCount": 1}],
            "tenants": [],
            "risks": [{"key": "no_admin_user", "title": "没有管理员账号", "severity": "danger", "count": 1, "detail": "异常"}],
            "checklist": [
                {
                    "key": "admin_login_available",
                    "title": "管理员可登录",
                    "passed": False,
                    "detail": "异常",
                    "action": "恢复管理员",
                }
            ],
            "businessApiPolicy": AUTH_BUSINESS_API_POLICY,
            "roleBoundary": AUTH_ROLE_BOUNDARY,
        }
    )

    assert ok is False
    assert "no admin users" in detail


def test_auth_scope_summary_check_blocks_schema_gap() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": True,
            "blockingRiskCount": 0,
            "warningRiskCount": 0,
            "totals": {
                "users": 1,
                "activeUsers": 1,
                "adminUsers": 1,
                "activeSessions": 0,
            },
            "roles": [{"count": 1}],
            "tenants": [],
            "risks": [{"key": "risk_without_detail"}],
            "checklist": [{"key": "check_without_detail"}],
            "businessApiPolicy": [{"key": "policy_without_detail"}],
            "roleBoundary": [{"key": "boundary_without_detail"}],
        }
    )

    assert ok is False
    assert "schema gaps" in detail


def test_auth_scope_summary_check_blocks_release_not_ready() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": False,
            "blockingRiskCount": 0,
            "warningRiskCount": 1,
            "totals": {
                "users": 3,
                "activeUsers": 3,
                "adminUsers": 1,
                "clientUsers": 1,
                "unscopedClientUsers": 1,
                "activeSessions": 2,
                "activeInvites": 1,
                "unscopedActiveInvites": 0,
                "expiredActiveInvites": 0,
            },
            "roles": [{"role": "admin", "count": 1, "activeCount": 1}],
            "tenants": [{"tenantId": None, "clientId": None, "userCount": 1}],
            "risks": [
                {
                    "key": "unscoped_client_users",
                    "title": "业务方账号未绑定",
                    "severity": "warning",
                    "count": 1,
                    "detail": "需要绑定",
                }
            ],
            "checklist": [
                {
                    "key": "client_users_scoped",
                    "title": "业务方账号已绑定范围",
                    "passed": False,
                    "detail": "需要绑定",
                    "action": "补 tenantId/clientId",
                }
            ],
            "businessApiPolicy": AUTH_BUSINESS_API_POLICY,
            "roleBoundary": AUTH_ROLE_BOUNDARY,
        }
    )

    assert ok is False
    assert "auth not release ready" in detail


def test_auth_scope_summary_check_blocks_missing_business_api_policy() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": True,
            "blockingRiskCount": 0,
            "warningRiskCount": 0,
            "totals": {
                "users": 3,
                "activeUsers": 3,
                "adminUsers": 1,
                "clientUsers": 1,
                "unscopedClientUsers": 0,
                "activeSessions": 2,
                "activeInvites": 1,
                "unscopedActiveInvites": 0,
                "expiredActiveInvites": 0,
            },
            "roles": [{"role": "admin", "count": 1, "activeCount": 1}],
            "tenants": [{"tenantId": "tenant-a", "clientId": "client-web", "userCount": 1}],
            "risks": [{"key": "ok", "title": "账号范围正常", "severity": "success", "count": 0, "detail": "正常"}],
            "checklist": [
                {
                    "key": "admin_login_available",
                    "title": "管理员可登录",
                    "passed": True,
                    "detail": "正常",
                    "action": "无需处理",
                }
            ],
            "businessApiPolicy": [
                {
                    "key": "client_user_bound_scope",
                    "title": "业务方账号只能使用绑定范围",
                    "detail": "强制使用账号绑定范围",
                    "enforced": True,
                }
            ],
            "roleBoundary": AUTH_ROLE_BOUNDARY,
        }
    )

    assert ok is False
    assert "businessApiPolicy missing required policies" in detail


def test_auth_scope_summary_check_blocks_missing_role_boundary() -> None:
    module = _load_smoke_module()

    ok, detail = module._validate_auth_scope_summary(
        {
            "releaseReady": True,
            "blockingRiskCount": 0,
            "warningRiskCount": 0,
            "totals": {
                "users": 3,
                "activeUsers": 3,
                "adminUsers": 1,
                "clientUsers": 1,
                "unscopedClientUsers": 0,
                "activeSessions": 2,
                "activeInvites": 1,
                "unscopedActiveInvites": 0,
                "expiredActiveInvites": 0,
            },
            "roles": [{"role": "admin", "count": 1, "activeCount": 1}],
            "tenants": [{"tenantId": "tenant-a", "clientId": "client-web", "userCount": 1}],
            "risks": [{"key": "ok", "title": "账号范围正常", "severity": "success", "count": 0, "detail": "正常"}],
            "checklist": [
                {
                    "key": "admin_login_available",
                    "title": "管理员可登录",
                    "passed": True,
                    "detail": "正常",
                    "action": "无需处理",
                }
            ],
            "businessApiPolicy": AUTH_BUSINESS_API_POLICY,
            "roleBoundary": [
                {
                    "key": "admin_user",
                    "title": "管理员账号",
                    "principal": "管理端管理员",
                    "allowed": "维护用户",
                    "blocked": "不能停用自己",
                    "enforced": True,
                }
            ],
        }
    )

    assert ok is False
    assert "roleBoundary missing required boundaries" in detail


def test_release_smoke_write_report_creates_parent_directory(tmp_path) -> None:
    module = _load_smoke_module()
    report_path = tmp_path / "nested" / "release_smoke.json"

    written = module._write_report({"ok": True, "checks": [{"name": "health", "ok": True}]}, str(report_path))

    assert written == str(report_path)
    assert report_path.exists()
    assert '"ok": true' in report_path.read_text(encoding="utf-8")
