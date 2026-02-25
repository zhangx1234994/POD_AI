from app.routers.evals_public import _derive_batch_status


def test_batch_finishes_failed_when_upload_failed_assets_exist() -> None:
    status = _derive_batch_status(
        current_status="running",
        planned_image_count=12,
        uploaded_count=10,
        upload_failed_count=2,
        upload_in_progress_count=0,
        repeat_count=3,
        submitted_count=30,
        running_count=0,
        succeeded_count=30,
        failed_count=0,
        canceled_count=0,
    )
    assert status == "failed"


def test_batch_finishes_failed_when_all_assets_upload_failed() -> None:
    status = _derive_batch_status(
        current_status="uploading",
        planned_image_count=12,
        uploaded_count=0,
        upload_failed_count=12,
        upload_in_progress_count=0,
        repeat_count=3,
        submitted_count=0,
        running_count=0,
        succeeded_count=0,
        failed_count=0,
        canceled_count=0,
    )
    assert status == "failed"


def test_batch_finishes_succeeded_when_all_runnable_runs_completed() -> None:
    status = _derive_batch_status(
        current_status="running",
        planned_image_count=12,
        uploaded_count=12,
        upload_failed_count=0,
        upload_in_progress_count=0,
        repeat_count=3,
        submitted_count=36,
        running_count=0,
        succeeded_count=36,
        failed_count=0,
        canceled_count=0,
    )
    assert status == "succeeded"


def test_batch_keeps_uploading_while_assets_still_in_progress() -> None:
    status = _derive_batch_status(
        current_status="uploading",
        planned_image_count=100,
        uploaded_count=40,
        upload_failed_count=3,
        upload_in_progress_count=57,
        repeat_count=2,
        submitted_count=0,
        running_count=0,
        succeeded_count=0,
        failed_count=0,
        canceled_count=0,
    )
    assert status == "uploading"

