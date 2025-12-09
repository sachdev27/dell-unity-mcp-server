"""Tests for the tool generator module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unity_mcp.exceptions import OpenAPILoadError, OpenAPIParseError
from unity_mcp.tool_generator import ToolGenerator, load_openapi_spec


class TestToolGenerator:
    """Tests for the ToolGenerator class."""

    def test_generate_tools_from_spec(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test generating tools from OpenAPI spec."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        # Should generate tools for GET methods only
        assert len(tools) >= 3  # alert, alert/{id}, volume, appliance

    def test_generated_tool_has_required_fields(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test that generated tools have all required fields."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]

    def test_tools_include_credentials(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test that all tools include credential parameters."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        for tool in tools:
            props = tool["inputSchema"]["properties"]
            required = tool["inputSchema"]["required"]

            assert "host" in props
            assert "username" in props
            assert "password" in props
            assert "host" in required
            assert "username" in required
            assert "password" in required

    def test_collection_tools_include_query_params(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test that collection tools include query parameters."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        # Find a collection tool (no {id} in path)
        collection_tools = [t for t in tools if "InstanceQuery" not in t["name"]]
        assert len(collection_tools) > 0

        for tool in collection_tools:
            props = tool["inputSchema"]["properties"]
            # Unity uses fields, page, per_page instead of select/limit/offset
            assert "fields" in props
            assert "per_page" in props
            assert "page" in props
            assert "queryParams" in props

    def test_unique_tool_names(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test that all tool names are unique."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        names = [t["name"] for t in tools]
        assert len(names) == len(set(names))

    def test_generate_tool_name_from_path(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test tool name generation from path."""
        generator = ToolGenerator(sample_openapi_spec)

        name = generator._generate_tool_name_from_path("/lun/instances", "get")
        assert name == "getLunInstances"

        name = generator._generate_tool_name_from_path("/storageResource/instances/{id}", "get")
        # Tool generator uses lowercase for camelCase path segments
        assert name == "getStorageresourceInstances"

    def test_enhanced_description_includes_fields(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test that generated tools have descriptions."""
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        # Find the alert tool
        alert_tool = next((t for t in tools if t["name"] == "alertCollectionQuery"), None)
        assert alert_tool is not None

        # Description should be present (from operation summary)
        desc = alert_tool["description"]
        assert len(desc) > 0
        assert "alert" in desc.lower()

    def test_get_resource_name_from_path(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test resource name extraction from path."""
        generator = ToolGenerator(sample_openapi_spec)

        assert generator._get_resource_name_from_path("/alert/instances") == "alert"
        assert generator._get_resource_name_from_path("/lun/instances/{id}") == "lun"
        assert generator._get_resource_name_from_path("/storageResource/instances") == "storageResource"


class TestLoadOpenAPISpec:
    """Tests for the load_openapi_spec function."""

    def test_load_json_spec(self, tmp_path: Path, sample_openapi_spec: dict[str, Any]) -> None:
        """Test loading JSON OpenAPI spec."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(sample_openapi_spec))

        spec = load_openapi_spec(str(spec_file))
        assert spec["info"]["title"] == "Test Unity API"

    def test_load_yaml_spec(self, tmp_path: Path) -> None:
        """Test loading YAML OpenAPI spec."""
        yaml_content = """
swagger: "2.0"
info:
  title: Test API
  version: "1.0.0"
paths: {}
"""
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_content)

        spec = load_openapi_spec(str(spec_file))
        assert spec["info"]["title"] == "Test API"

    def test_load_nonexistent_file(self) -> None:
        """Test loading non-existent file raises error."""
        with pytest.raises(OpenAPILoadError):
            load_openapi_spec("/nonexistent/path/spec.json")

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises error."""
        spec_file = tmp_path / "invalid.json"
        spec_file.write_text("not valid json {{{")

        with pytest.raises((OpenAPILoadError, OpenAPIParseError, ValueError, json.JSONDecodeError)):
            load_openapi_spec(str(spec_file))


class TestToolGeneratorEdgeCases:
    """Edge case tests for ToolGenerator."""

    def test_empty_paths(self) -> None:
        """Test handling spec with no paths."""
        spec: dict[str, Any] = {"paths": {}}
        generator = ToolGenerator(spec)
        tools = generator.generate_tools()
        assert tools == []

    def test_no_get_methods(self) -> None:
        """Test handling spec with no GET methods."""
        spec: dict[str, Any] = {
            "paths": {
                "/volume": {
                    "post": {"summary": "Create volume"},
                    "delete": {"summary": "Delete volume"},
                }
            }
        }
        generator = ToolGenerator(spec)
        tools = generator.generate_tools()
        assert tools == []

    def test_missing_operationId(self, sample_openapi_spec: dict[str, Any]) -> None:
        """Test handling operations without operationId."""
        # The /lun/instances endpoint in sample spec has no operationId
        generator = ToolGenerator(sample_openapi_spec)
        tools = generator.generate_tools()

        lun_tool = next((t for t in tools if "lun" in t["name"].lower()), None)
        assert lun_tool is not None
        assert lun_tool["name"] == "getLunInstances"

    def test_duplicate_operationId_handling(self) -> None:
        """Test handling duplicate operationIds."""
        spec: dict[str, Any] = {
            "paths": {
                "/resource1": {
                    "get": {"operationId": "getResource"},
                },
                "/resource2": {
                    "get": {"operationId": "getResource"},
                },
            }
        }
        generator = ToolGenerator(spec)
        tools = generator.generate_tools()

        names = [t["name"] for t in tools]
        assert len(names) == len(set(names))  # All unique
