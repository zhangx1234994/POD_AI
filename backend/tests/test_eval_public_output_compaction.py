from __future__ import annotations

from app.routers.evals_public import _compact_eval_output_for_list


def test_eval_list_output_compaction_removes_heavy_business_step_payloads() -> None:
    output = {
        "businessRunId": "run_1",
        "status": "succeeded",
        "imageUrls": ["https://example.com/out.png"],
        "steps": [
            {
                "displayName": "GPT Image 2",
                "status": "succeeded",
                "request_payload": {"prompt": "x" * 6000},
                "result_payload": {"raw": "y" * 6000},
            }
        ],
    }

    compact = _compact_eval_output_for_list(output)

    assert compact["businessRunId"] == "run_1"
    assert compact["imageUrls"] == ["https://example.com/out.png"]
    assert compact["stepCount"] == 1
    assert compact["steps"] == [{"displayName": "GPT Image 2", "status": "succeeded"}]
