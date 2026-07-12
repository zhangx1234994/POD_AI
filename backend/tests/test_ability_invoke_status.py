from app.services.ability_invocation import ability_invocation_service


def test_normalize_public_status_success_variants():
    for value in ("success", "succeeded", "completed", "ok"):
        assert ability_invocation_service._normalize_public_status(value) == "succeeded"


def test_normalize_public_status_failure_variants():
    for value in ("failed", "error", "timeout", "rejected"):
        assert ability_invocation_service._normalize_public_status(value) == "failed"


def test_normalize_public_status_running_variants():
    assert ability_invocation_service._normalize_public_status("processing") == "running"
    assert ability_invocation_service._normalize_public_status("queued") == "queued"
    assert ability_invocation_service._normalize_public_status("canceled") == "cancelled"


def test_extract_response_error_message_from_vendor_raw():
    assert (
        ability_invocation_service._extract_response_error_message(
            {
                "raw": {
                    "vendorApi": {
                        "response": {
                            "error": {
                                "code": "invalid_value",
                                "message": "The model does not exist.",
                            }
                        }
                    }
                }
            }
        )
        == "The model does not exist."
    )


def test_extract_image_assets_prefers_persisted_oss_url():
    oss_url = "https://aichuangpin.oss-cn-hangzhou.aliyuncs.com/prelaunch/service/example.png"
    vendor_url = "https://vendor.example.com/result.png"

    images = ability_invocation_service._extract_output_assets(
        {
            "resultUrls": [oss_url],
            "assets": [
                {
                    "ossUrl": oss_url,
                    "sourceUrl": vendor_url,
                    "contentType": "image/png",
                    "tag": "vendor-output",
                }
            ],
        },
        target="image",
    )

    assert len(images) == 1
    assert images[0].ossUrl == oss_url
    assert images[0].sourceUrl == vendor_url
