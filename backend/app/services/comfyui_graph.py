from __future__ import annotations

from typing import Any


def normalize_comfyui_prompt_graph(definition: dict[str, Any] | None) -> dict[str, Any]:
    if not definition:
        return {}
    graph = definition.get("graph")
    if isinstance(graph, dict):
        return graph
    if _is_prompt_graph(definition):
        return definition
    if _is_ui_definition(definition):
        return _convert_ui_to_prompt(definition)
    return {}


def _is_prompt_graph(definition: dict[str, Any]) -> bool:
    for value in definition.values():
        if isinstance(value, dict) and "class_type" in value:
            return True
    return False


def _is_ui_definition(definition: dict[str, Any]) -> bool:
    nodes = definition.get("nodes")
    if not isinstance(nodes, list):
        return False
    return any(isinstance(node, dict) and "id" in node for node in nodes)


def _convert_ui_to_prompt(definition: dict[str, Any]) -> dict[str, Any]:
    nodes = definition.get("nodes") or []
    links = definition.get("links") or []
    link_map: dict[str, tuple[str, int]] = {}
    if isinstance(links, list):
        for item in links:
            if not isinstance(item, list) or len(item) < 3:
                continue
            link_id, from_node, from_slot = item[0], item[1], item[2]
            if link_id is None:
                continue
            try:
                slot = int(from_slot)
            except (TypeError, ValueError):
                slot = 0
            link_map[str(link_id)] = (str(from_node), slot)
    graph: dict[str, Any] = {}
    if isinstance(nodes, list):
        for raw_node in nodes:
            if not isinstance(raw_node, dict):
                continue
            node_id = raw_node.get("id")
            if node_id is None:
                continue
            class_type = raw_node.get("type") or raw_node.get("class_type") or ""
            inputs: dict[str, Any] = {}
            input_list = raw_node.get("inputs")
            widget_values = raw_node.get("widgets_values") if isinstance(raw_node.get("widgets_values"), list) else []
            widget_index = 0
            if isinstance(input_list, list):
                for input_item in input_list:
                    if not isinstance(input_item, dict):
                        continue
                    key = input_item.get("name")
                    if not isinstance(key, str) or not key:
                        if input_item.get("widget") is not None:
                            widget_index += 1
                        continue
                    link_id = input_item.get("link")
                    link_ref = link_map.get(str(link_id)) if link_id is not None else None
                    if link_ref:
                        inputs[key] = [link_ref[0], link_ref[1]]
                    if input_item.get("widget") is not None:
                        value = widget_values[widget_index] if widget_index < len(widget_values) else None
                        widget_index += 1
                        if not link_ref:
                            inputs[key] = value
            elif isinstance(input_list, dict):
                inputs.update(input_list)
            graph[str(node_id)] = {"class_type": class_type, "inputs": inputs}
    return graph
