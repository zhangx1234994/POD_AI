from app.services.ability_logs import AbilityLogService


def test_extract_stored_url_from_images_when_assets_missing():
    svc = AbilityLogService()
    payload = {
        "images": [
            {"ossUrl": "https://oss.example.com/a.png"},
            {"sourceUrl": "https://raw.example.com/b.png"},
        ]
    }
    assert svc._extract_stored_url(payload) == "https://oss.example.com/a.png"


def test_extract_stored_url_from_image_urls_when_no_object_assets():
    svc = AbilityLogService()
    payload = {"imageUrls": ["https://oss.example.com/a.png", "https://oss.example.com/b.png"]}
    assert svc._extract_stored_url(payload) == "https://oss.example.com/a.png"


def test_extract_assets_fallback_from_images_and_result_urls():
    svc = AbilityLogService()
    from_images = svc._extract_assets({"images": [{"ossUrl": "https://oss.example.com/a.png", "tag": "comfyui"}]})
    assert isinstance(from_images, list) and from_images[0]["ossUrl"] == "https://oss.example.com/a.png"
    from_urls = svc._extract_assets({"resultUrls": ["https://oss.example.com/c.png"]})
    assert isinstance(from_urls, list) and from_urls[0]["url"] == "https://oss.example.com/c.png"
