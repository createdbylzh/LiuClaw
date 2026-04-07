from __future__ import annotations

from typing import Any

from ai.types import Tool


class SchemaValidationError(ValueError):
    """表示工具参数未通过 JSON Schema 校验。"""



def validate_tool_arguments(tool: Tool, arguments: dict[str, Any]) -> bool:
    """校验工具参数是否满足工具定义中的 JSON Schema。"""

    schema = tool.inputSchema or {}
    _validate_schema(schema, arguments, path="$")
    return True



def _validate_schema(schema: dict[str, Any], value: Any, *, path: str) -> None:
    """递归校验一个值是否满足给定的简化 JSON Schema。"""

    schema_type = schema.get("type")
    if schema_type is None:
        return

    if schema_type == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path} must be an object")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise SchemaValidationError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        additional_properties = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _validate_schema(properties[key], item, path=f"{path}.{key}")
            elif additional_properties is False:
                raise SchemaValidationError(f"{path}.{key} is not allowed")
        return

    if schema_type == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path} must be an array")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_schema(item_schema, item, path=f"{path}[{index}]")
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            raise SchemaValidationError(f"{path} must contain at least {min_items} items")
        max_items = schema.get("maxItems")
        if max_items is not None and len(value) > max_items:
            raise SchemaValidationError(f"{path} must contain at most {max_items} items")
        return

    if schema_type == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path} must be a string")
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            raise SchemaValidationError(f"{path} must be at least {min_length} characters")
        max_length = schema.get("maxLength")
        if max_length is not None and len(value) > max_length:
            raise SchemaValidationError(f"{path} must be at most {max_length} characters")
        enum_values = schema.get("enum")
        if enum_values is not None and value not in enum_values:
            raise SchemaValidationError(f"{path} must be one of {enum_values}")
        return

    if schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(f"{path} must be an integer")
        _validate_numeric_bounds(schema, value, path=path)
        return

    if schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaValidationError(f"{path} must be a number")
        _validate_numeric_bounds(schema, float(value), path=path)
        return

    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path} must be a boolean")
        return

    if schema_type == "null":
        if value is not None:
            raise SchemaValidationError(f"{path} must be null")
        return



def _validate_numeric_bounds(schema: dict[str, Any], value: float, *, path: str) -> None:
    """校验数值类型的边界限制。"""

    minimum = schema.get("minimum")
    if minimum is not None and value < minimum:
        raise SchemaValidationError(f"{path} must be >= {minimum}")
    maximum = schema.get("maximum")
    if maximum is not None and value > maximum:
        raise SchemaValidationError(f"{path} must be <= {maximum}")
