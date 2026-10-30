"""Small Swagger 2 response validator for live API calls."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class OpenAPISpec:
    """Load a Swagger/OpenAPI document and validate response data."""

    def __init__(self, path: Path) -> None:
        """Load the spec from *path*."""
        self.path = path
        self.spec = json.loads(path.read_text(encoding="utf-8"))
        self.paths: dict[str, dict[str, Any]] = self.spec.get("paths", {})
        self.definitions: dict[str, Any] = self.spec.get("definitions", {})

    def _operation(self, method: str, path: str) -> tuple[str, dict[str, Any]]:
        method = method.lower()
        for template, operations in self.paths.items():
            operation = operations.get(method)
            if operation is None:
                continue
            pattern = "^" + re.sub(r"\\{[^}]+\\}", "[^/]+", re.escape(template)) + "$"
            if re.fullmatch(pattern, path):
                return template, operation
        raise AssertionError(f"{method.upper()} {path} is not present in {self.path}")

    def _resolve(self, schema: dict[str, Any]) -> dict[str, Any]:
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return schema
        prefix = "#/definitions/"
        if not ref.startswith(prefix):
            raise AssertionError(f"Unsupported schema reference: {ref}")
        name = ref[len(prefix) :]
        resolved = self.definitions.get(name)
        if not isinstance(resolved, dict):
            raise AssertionError(f"Unknown schema definition: {name}")
        return resolved

    def _check(self, value: Any, schema: dict[str, Any], location: str) -> None:
        schema = self._resolve(schema)
        # Swagger 2.0 treats absent-from-required fields as optional, and the
        # server legitimately returns null for unset optional fields. Accept it.
        if value is None:
            return
        expected = schema.get("type")
        if expected == "object":
            if not isinstance(value, dict):
                raise AssertionError(f"{location}: expected object, got {type(value).__name__}")
            for key in schema.get("required") or []:
                if key not in value:
                    raise AssertionError(f"{location}: missing required field '{key}'")
            properties = schema.get("properties") or {}
            for key, child in properties.items():
                if key in value:
                    self._check(value[key], child, f"{location}.{key}")
        elif expected == "array":
            if not isinstance(value, list):
                raise AssertionError(f"{location}: expected array, got {type(value).__name__}")
            items = schema.get("items")
            if isinstance(items, dict):
                for index, item in enumerate(value):
                    self._check(item, items, f"{location}[{index}]")
        elif expected == "string":
            if not isinstance(value, str):
                raise AssertionError(f"{location}: expected string, got {type(value).__name__}")
        elif expected == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise AssertionError(f"{location}: expected integer, got {type(value).__name__}")
        elif expected == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise AssertionError(f"{location}: expected number, got {type(value).__name__}")
        elif expected == "boolean":
            if not isinstance(value, bool):
                raise AssertionError(f"{location}: expected boolean, got {type(value).__name__}")

        enum = schema.get("enum")
        if enum is not None and value not in enum:
            raise AssertionError(f"{location}: {value!r} is not one of {enum!r}")

        for part in schema.get("allOf") or []:
            self._check(value, part, location)

        for keyword in ("oneOf", "anyOf"):
            options = schema.get(keyword)
            if not isinstance(options, list):
                continue
            failures = []
            for option in options:
                try:
                    self._check(value, option, location)
                    break
                except AssertionError as exc:
                    failures.append(str(exc))
            else:
                raise AssertionError(
                    f"{location}: value does not match any {keyword} schema: {failures}"
                )

    def validate(self, method: str, path: str, data: Any) -> None:
        """Validate unwrapped response *data* against the matching response schema."""
        if isinstance(data, str):
            raise AssertionError(
                f"{method.upper()} {path} returned a non-JSON body (a plain string); "
                "the endpoint is not returning the expected API payload"
            )
        template, operation = self._operation(method, path)
        responses = operation.get("responses", {})
        response = None
        for code in ("200", "201", "202", "203", "204"):
            if code in responses:
                response = responses[code]
                break
        if response is None:
            response = responses.get("default")
        if not response or not isinstance(response, dict):
            return

        schema = response.get("schema")
        if not isinstance(schema, dict) or schema.get("type") == "file":
            return

        envelope = {
            "status": "success",
            "data": data,
            "message": "",
            "error": "",
        }
        try:
            self._check(envelope, schema, f"{method.upper()} {path} ({template})")
        except AssertionError as exc:
            raise AssertionError(f"Swagger response mismatch: {exc}") from exc
