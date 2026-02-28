from app.services.eval_seed import DEFAULT_EVAL_WORKFLOW_BY_ID


def _field_by_name(workflow: dict, name: str) -> dict:
    fields = ((workflow or {}).get("parameters_schema") or {}).get("fields") or []
    for field in fields:
        if isinstance(field, dict) and field.get("name") == name:
            return field
    return {}


def test_shengtu_workflow_supports_banana2_and_reference_images():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7602916576198656000"]

    moxing = _field_by_name(workflow, "moxing")
    options = moxing.get("options") or []
    values = {str(item.get("value")) for item in options if isinstance(item, dict)}
    assert {"1", "2", "3", "4"} <= values

    cankaotu = _field_by_name(workflow, "cankaotu")
    assert cankaotu.get("type") == "textarea"
    assert cankaotu.get("supportedModels") == ["1", "2", "4"]

    aspect_ratio = _field_by_name(workflow, "aspect_ratio")
    resolution = _field_by_name(workflow, "resolution")
    assert isinstance(aspect_ratio.get("modelOptions"), dict)
    assert isinstance(resolution.get("modelOptions"), dict)
    assert "4" in aspect_ratio.get("modelOptions")
    assert "4" in resolution.get("modelOptions")


def test_lora_query_workflow_output_contract():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7612002440056930304"]

    params = ((workflow or {}).get("parameters_schema") or {}).get("fields") or []
    assert params == []

    outputs = ((workflow or {}).get("output_schema") or {}).get("fields") or []
    names = [field.get("name") for field in outputs if isinstance(field, dict)]
    assert names == ["items", "lora_names"]

