"""OpenAPI tool generator for Unity MCP Server.

This module parses OpenAPI specifications and generates MCP tool definitions
with enhanced descriptions for LLM context.

Example:
    >>> from unity_mcp.tool_generator import ToolGenerator, load_openapi_spec
    >>> spec = load_openapi_spec("openapi.json")
    >>> generator = ToolGenerator(spec)
    >>> tools = generator.generate_tools()
    >>> print(f"Generated {len(tools)} tools")

Note:
    Only GET methods are generated for safe read-only operations.
    Each tool includes credential parameters (host, username, password)
    that must be provided per-request.

    Unity API uses different path conventions:
    - /api/types/{resource}/instances - Collection queries
    - /api/instances/{resource}/{id} - Instance queries
    - /api/instances/{resource}/{id}/action/{action} - Actions
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .exceptions import OpenAPILoadError, OpenAPIParseError
from .logging_config import get_logger

logger = get_logger(__name__)

# Maximum number of fields to show in description
MAX_FIELDS_DISPLAY = 20
MAX_KEY_FIELDS = 10
MAX_ENUM_VALUES = 5


class ToolGenerator:
    """Generate MCP tools from OpenAPI specification.

    This class parses an OpenAPI 2.0/3.0 specification and generates
    MCP tool definitions for configured HTTP methods. Tools include enhanced
    descriptions with schema information for better LLM understanding.

    Attributes:
        spec: The parsed OpenAPI specification.
        tool_names: Dictionary tracking tool name usage for uniqueness.
        allowed_methods: List of HTTP methods to generate tools for.

    Example:
        >>> generator = ToolGenerator(spec, allowed_methods=["GET"])
        >>> tools = generator.generate_tools()
        >>> for tool in tools:
        ...     print(f"{tool['name']}: {tool['description'][:50]}...")
    """

    # Default to GET only for safe read-only operations
    DEFAULT_ALLOWED_METHODS = ["GET"]

    def __init__(
        self,
        spec: dict[str, Any],
        allowed_methods: list[str] | None = None
    ) -> None:
        """Initialize tool generator with OpenAPI spec.

        Args:
            spec: Parsed OpenAPI specification dictionary.
            allowed_methods: List of HTTP methods to generate tools for.
                           Defaults to ["GET"] for safe read-only operations.
                           Set to ["GET", "POST", "DELETE", "PATCH", "PUT"]
                           to enable all operations.
        """
        self.spec = spec
        self.tool_names: dict[str, int] = {}
        self.allowed_methods = [m.lower() for m in (allowed_methods or self.DEFAULT_ALLOWED_METHODS)]

    def generate_tools(self) -> list[dict[str, Any]]:
        """Generate MCP tools from OpenAPI spec for configured methods.

        Returns:
            List of MCP tool definitions.

        Note:
            Only methods specified in allowed_methods are included.
            Default is GET only for safe read-only operations.
        """
        tools: list[dict[str, Any]] = []
        paths = self.spec.get("paths", {})

        for path, path_item in paths.items():
            # Generate tools for each allowed method
            for method in self.allowed_methods:
                if method in path_item:
                    operation = path_item[method]
                    tool = self._generate_tool_from_operation(path, method, operation)
                    if tool:
                        tools.append(tool)

        logger.info(
            "Generated MCP tools from OpenAPI spec",
            extra={"tool_count": len(tools), "methods": [m.upper() for m in self.allowed_methods]},
        )
        return tools

    def _generate_tool_from_operation(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Generate a single MCP tool from an OpenAPI operation.

        Args:
            path: API endpoint path (e.g., "/api/types/lun/instances").
            method: HTTP method (lowercase).
            operation: OpenAPI operation object.

        Returns:
            MCP tool definition or None if generation fails.
        """
        try:
            # Generate tool name from operationId or path + method
            tool_name = operation.get("operationId") or self._generate_tool_name_from_path(
                path, method
            )

            # Make tool name unique if duplicate exists
            tool_name = self._make_unique_name(tool_name, path)

            # Generate base description
            base_description = (
                operation.get("summary")
                or operation.get("description")
                or f"{method.upper()} {path}"
            )

            # Detect if this is a collection query (ends with /instances)
            is_collection_query = path.endswith("/instances")

            # Get resource name from path
            resource_name = self._get_resource_name_from_path(path)

            # Build enhanced description with schema info
            description = self._build_enhanced_description(
                base_description, resource_name, is_collection_query
            )

            # Generate input schema from parameters
            input_schema = self._generate_input_schema(operation, is_collection_query, resource_name)

            return {
                "name": tool_name,
                "description": description,
                "inputSchema": input_schema,
            }

        except Exception as e:
            logger.warning(
                f"Failed to generate tool for {method.upper()} {path}",
                extra={"error": str(e), "path": path, "method": method},
            )
            return None

    def _get_resource_name_from_path(self, path: str) -> str:
        """Extract resource name from API path.

        Unity API paths follow patterns like:
        - /api/types/{resource}/instances
        - /api/instances/{resource}/{id}

        Args:
            path: API endpoint path.

        Returns:
            Resource name (e.g., "lun", "alert", "storagePool").
        """
        parts = path.split("/")

        # Handle /api/types/{resource}/instances pattern
        if "types" in parts:
            type_idx = parts.index("types")
            if type_idx + 1 < len(parts):
                return parts[type_idx + 1]

        # Handle /api/instances/{resource}/{id} pattern
        if "instances" in parts:
            inst_idx = parts.index("instances")
            if inst_idx + 1 < len(parts):
                resource = parts[inst_idx + 1]
                # Skip if it's a path parameter like {id}
                if not resource.startswith("{"):
                    return resource

        # Fallback: filter out common segments and parameters
        filtered = [p for p in parts if p and not p.startswith("{") and p not in ("api", "types", "instances", "action")]
        return filtered[0] if filtered else ""

    def _build_enhanced_description(
        self,
        base_description: str,
        resource_name: str,
        is_collection_query: bool,
    ) -> str:
        """Build enhanced description with schema info for LLM context.

        Args:
            base_description: Original operation description.
            resource_name: Name of the resource (e.g., "lun", "alert").
            is_collection_query: Whether this is a collection query.

        Returns:
            Enhanced description with available fields and filter info.
        """
        description = base_description

        # Try to find schema definition for this resource
        # OpenAPI 3.0 uses components/schemas, Swagger 2.0 uses definitions
        definitions = self.spec.get("components", {}).get("schemas", {}) or self.spec.get("definitions", {})

        # Try various naming conventions (Unity uses simple names like 'alert', 'lun')
        instance_def = (
            definitions.get(resource_name, {}) or
            definitions.get(f"{resource_name}_instance", {}) or
            definitions.get(f"{resource_name}Instance", {})
        )
        properties = instance_def.get("properties", {})

        if properties and is_collection_query:
            # Add available fields for 'fields' parameter (Unity uses 'fields' not 'select')
            field_names = sorted(properties.keys())
            fields_summary = ", ".join(field_names[:MAX_FIELDS_DISPLAY])
            if len(field_names) > MAX_FIELDS_DISPLAY:
                fields_summary += f", ... ({len(field_names)} total fields)"

            description += f"\n\nAvailable fields for 'fields' parameter: {fields_summary}"

            # Add key fields with descriptions for common use cases
            key_fields = self._get_key_fields(properties, resource_name)
            if key_fields:
                description += f"\n\nKey fields:\n{key_fields}"

            # Add filter examples based on resource type
            filter_examples = self._get_filter_examples(resource_name, properties)
            if filter_examples:
                description += f"\n\nFilter examples (queryParams):\n{filter_examples}"

        return description

    def _get_key_fields(
        self, properties: dict[str, Any], resource_name: str
    ) -> str:
        """Get formatted list of key fields with descriptions.

        Args:
            properties: Schema properties dict.
            resource_name: Name of the resource.

        Returns:
            Formatted string of key fields.
        """
        # Priority fields that are commonly useful for Unity resources
        priority_fields = [
            "id",
            "name",
            "health",
            "state",
            "status",
            "severity",
            "type",
            "description",
            "message",
            "isAcknowledged",
            "resource",
            "timestamp",
            "sizeTotal",
            "sizeUsed",
            "sizeFree",
            "pool",
            "storageResource",
        ]

        lines: list[str] = []
        for field in priority_fields:
            if field in properties:
                prop = properties[field]
                desc = prop.get("description", "")[:80]
                enum = prop.get("enum")
                enum_ref = prop.get("$ref", "")

                field_info = f"- {field}"
                if desc:
                    field_info += f": {desc}"
                if enum:
                    enum_str = ", ".join(str(e) for e in enum[:MAX_ENUM_VALUES])
                    field_info += f" (values: {enum_str})"
                elif "Enum" in enum_ref:
                    # Extract enum name from $ref
                    enum_name = enum_ref.split("/")[-1]
                    # OpenAPI 3.0 uses components/schemas, Swagger 2.0 uses definitions
                    definitions = self.spec.get("components", {}).get("schemas", {}) or self.spec.get("definitions", {})
                    enum_def = definitions.get(enum_name, {})
                    enum_values = enum_def.get("enum", [])
                    if enum_values:
                        enum_str = ", ".join(
                            str(e) for e in enum_values[:MAX_ENUM_VALUES]
                        )
                        field_info += f" (values: {enum_str})"

                lines.append(field_info)

        return "\n".join(lines[:MAX_KEY_FIELDS])

    def _get_filter_examples(
        self, resource_name: str, properties: dict[str, Any]
    ) -> str:
        """Generate filter examples based on resource type.

        Unity uses different filter syntax than PowerStore:
        - filter=name eq "MyLun"
        - filter=severity eq 4

        Args:
            resource_name: Name of the resource.
            properties: Schema properties.

        Returns:
            Filter examples string.
        """
        examples: list[str] = []

        # Resource-specific filter examples for Unity
        if resource_name == "alert":
            examples = [
                '{"filter": "isAcknowledged eq false"} - Unacknowledged alerts only',
                '{"filter": "severity eq 4"} - Critical severity only',
                '{"filter": "state eq 0"} - Active alerts only',
            ]
        elif resource_name == "lun":
            examples = [
                '{"filter": "name lk \\"*prod*\\""} - LUNs with prod in name',
                '{"filter": "pool.id eq \\"pool_1\\""} - LUNs in specific pool',
            ]
        elif resource_name == "storagePool" or resource_name == "pool":
            examples = [
                '{"filter": "health.value eq 5"} - Healthy pools only',
            ]
        elif resource_name == "filesystem":
            examples = [
                '{"filter": "name lk \\"*share*\\""} - Filesystems with share in name',
            ]
        elif resource_name == "nasServer":
            examples = [
                '{"filter": "health.value eq 5"} - Healthy NAS servers',
            ]
        elif "health" in properties or "state" in properties:
            examples = ['{"filter": "health.value eq 5"} - Filter by health status']

        return "\n".join(f"- {ex}" for ex in examples) if examples else ""

    def _make_unique_name(self, tool_name: str, path: str) -> str:
        """Make tool name unique by adding suffix if needed.

        Args:
            tool_name: Original tool name.
            path: API path for generating suffix.

        Returns:
            Unique tool name.
        """
        if tool_name in self.tool_names:
            count = self.tool_names[tool_name] + 1
            self.tool_names[tool_name] = count

            # Add path-based suffix to make it unique
            path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
            path_suffix = "_".join(path_parts[-2:]) if len(path_parts) >= 2 else str(count)
            tool_name = f"{tool_name}_{path_suffix}"
        else:
            self.tool_names[tool_name] = 0

        return tool_name

    def _generate_tool_name_from_path(self, path: str, method: str) -> str:
        """Generate tool name from path and method.

        Args:
            path: API endpoint path.
            method: HTTP method.

        Returns:
            Generated tool name in camelCase.
        """
        # Extract meaningful parts from Unity API paths
        # /api/types/lun/instances -> getLunInstances
        # /api/instances/lun/{id} -> getLunById

        parts = path.split("/")
        meaningful_parts = [p for p in parts if p and not p.startswith("{") and p not in ("api",)]

        # Combine method and path parts
        name_parts = [method] + meaningful_parts

        # Convert to camelCase
        name = ""
        for i, part in enumerate(name_parts):
            # Clean non-alphanumeric characters
            cleaned = "".join(c if c.isalnum() else "_" for c in part)

            if i == 0:
                name = cleaned.lower()
            else:
                name += cleaned.capitalize()

        return name

    def _generate_input_schema(
        self, operation: dict[str, Any], is_collection_query: bool = False, resource_name: str = ""
    ) -> dict[str, Any]:
        """Generate input schema from operation parameters.

        Args:
            operation: OpenAPI operation object.
            is_collection_query: Whether this is a collection query.
            resource_name: Name of the resource (e.g., "lun", "alert").

        Returns:
            JSON Schema for tool input.
        """
        properties: dict[str, Any] = {
            "host": {
                "type": "string",
                "description": "Unity host (e.g., unity.example.com)",
            },
            "username": {
                "type": "string",
                "description": "Unity username",
            },
            "password": {
                "type": "string",
                "description": "Unity password",
            },
        }
        required = ["host", "username", "password"]

        # Add parameters from OpenAPI spec
        parameters = operation.get("parameters", [])
        for param in parameters:
            param_name = param.get("name")
            if not param_name:
                continue

            param_in = param.get("in")
            if param_in not in ["query", "path"]:
                continue

            # Build parameter schema
            param_schema: dict[str, Any] = {
                "type": self._convert_openapi_type(param.get("type", "string")),
                "description": param.get("description", ""),
            }

            # Add enum if present
            if "enum" in param:
                param_schema["enum"] = param["enum"]

            properties[param_name] = param_schema

            # Add to required if parameter is required
            if param.get("required", False):
                required.append(param_name)

        # Add Unity standard query parameters for collection queries
        if is_collection_query:
            # Build dynamic fields description with available field names
            fields_description = "Comma-separated list of field names to return (e.g., 'id,name,health')"

            # Try to find schema definition for this resource to get available fields
            if resource_name:
                definitions = self.spec.get("components", {}).get("schemas", {}) or self.spec.get("definitions", {})
                instance_def = (
                    definitions.get(resource_name, {}) or
                    definitions.get(f"{resource_name}_instance", {}) or
                    definitions.get(f"{resource_name}Instance", {})
                )
                schema_properties = instance_def.get("properties", {})

                if schema_properties:
                    field_names = sorted(schema_properties.keys())
                    fields_list = ", ".join(field_names[:MAX_FIELDS_DISPLAY])
                    if len(field_names) > MAX_FIELDS_DISPLAY:
                        fields_list += f", ... ({len(field_names)} total)"
                    fields_description = f"Comma-separated list of field names to return. Available fields: {fields_list}"

            properties["fields"] = {
                "type": "string",
                "description": fields_description,
            }
            properties["per_page"] = {
                "type": "integer",
                "description": "Maximum number of results per page (default: 2000)",
            }
            properties["page"] = {
                "type": "integer",
                "description": "Page number for pagination (starts at 1)",
            }
            properties["queryParams"] = {
                "type": "object",
                "description": (
                    "Additional query filters using Unity filter syntax "
                    "(e.g., {'filter': 'severity eq 4', 'compact': 'true'})"
                ),
                "additionalProperties": {"type": "string"},
            }

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            # Allow additional properties - n8n and other clients may pass extra metadata
            "additionalProperties": True,
        }

    def _convert_openapi_type(self, openapi_type: str) -> str:
        """Convert OpenAPI type to JSON Schema type.

        Args:
            openapi_type: OpenAPI type string.

        Returns:
            JSON Schema type string.
        """
        type_mapping = {
            "integer": "number",
            "number": "number",
            "string": "string",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
        }
        return type_mapping.get(openapi_type, "string")


def load_openapi_spec(file_path: str) -> dict[str, Any]:
    """Load OpenAPI specification from file.

    Supports both JSON and YAML formats. The format is determined
    by the file extension.

    Args:
        file_path: Path to OpenAPI spec file (JSON or YAML).

    Returns:
        Parsed OpenAPI specification.

    Raises:
        OpenAPILoadError: If file doesn't exist or cannot be read.
        OpenAPIParseError: If file format is invalid.

    Example:
        >>> spec = load_openapi_spec("openapi.json")
        >>> print(spec["info"]["title"])
        "Dell Unity REST API"
    """
    path = Path(file_path)

    if not path.exists():
        raise OpenAPILoadError(file_path, message=f"OpenAPI spec file not found: {file_path}")

    try:
        with open(path, encoding="utf-8") as f:
            if path.suffix in [".yaml", ".yml"]:
                return yaml.safe_load(f)
            elif path.suffix == ".json":
                return json.load(f)
            else:
                # Try JSON first, then YAML
                content = f.read()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return yaml.safe_load(content)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise OpenAPIParseError(file_path, e) from e
    except OSError as e:
        raise OpenAPILoadError(file_path, e) from e
