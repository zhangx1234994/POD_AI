from app.services.ability_presentation import (
    get_public_display_name,
    get_public_field_schema,
    get_public_presentation,
)


def test_public_display_name_hides_provider_prefix() -> None:
    assert get_public_display_name("KIE · Nano Banana Pro 图生图") == "Nano Banana Pro 图生图"


def test_public_field_schema_prefers_user_friendly_copy() -> None:
    schema = {
        "fields": [
            {
                "name": "prompt",
                "label": "提示词 Prompt",
                "description": "节点 111 · TextEncodeQwenImageEditPlus.prompt",
                "placeholder": "请输入中文/英文提示词 Enter prompt text",
                "type": "textarea",
            },
            {
                "name": "seed",
                "label": "随机种子 Seed",
                "description": "不填则自动随机。",
                "type": "number",
            },
        ]
    }

    normalized = get_public_field_schema(schema, metadata={})
    fields = {item["name"]: item for item in normalized["fields"]}

    assert fields["prompt"]["label"] == "提示词"
    assert "description" not in fields["prompt"]
    assert fields["prompt"]["placeholder"] == "请输入中文/英文提示词"
    assert fields["seed"]["advanced"] is True


def test_public_presentation_uses_metadata_when_available() -> None:
    payload = get_public_presentation(
        display_name="火山 · Doubao Seedream 4.5",
        description="生成品牌方向图",
        metadata={
            "presentation": {
                "name": "以文生款",
                "summary": "适合先出方向稿。",
                "formIntro": "先描述你要的风格方向。",
                "surfaces": {"client": True, "coze": False},
            }
        },
    )

    assert payload == {
        "name": "以文生款",
        "summary": "适合先出方向稿。",
        "formIntro": "先描述你要的风格方向。",
        "surfaces": {"client": True, "coze": False},
    }
