"""Tests for the configuration module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from unity_mcp.config import (
    Config,
    UnityConfig,
    ServerConfig,
    load_config,
)
from unity_mcp.exceptions import ConfigurationError, EnvironmentVariableError


class TestUnityConfig:
    """Tests for UnityConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = UnityConfig()

        assert config.host == "localhost"
        assert config.username is None
        assert config.password is None
        assert config.tls_verify is False

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = UnityConfig(
            host="unity.example.com",
            username="admin",
            password="secret",
            tls_verify=True,
        )

        assert config.host == "unity.example.com"
        assert config.username == "admin"
        assert config.tls_verify is True


class TestServerConfig:
    """Tests for ServerConfig."""

    def test_default_values(self) -> None:
        """Test default server configuration values."""
        config = ServerConfig()

        assert config.port == 3000
        assert config.log_level == "INFO"
        assert config.max_retries == 3
        assert config.request_timeout == 30000

    def test_custom_values(self) -> None:
        """Test custom server configuration values."""
        config = ServerConfig(
            port=8080,
            log_level="DEBUG",
            max_retries=5,
            request_timeout=60000,
        )

        assert config.port == 8080
        assert config.log_level == "DEBUG"
        assert config.max_retries == 5

    def test_log_level_validation(self) -> None:
        """Test log level validation."""
        # Valid log levels should work
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = ServerConfig(log_level=level)
            assert config.log_level == level

        # Invalid log level should raise error
        with pytest.raises(ValueError):
            ServerConfig(log_level="INVALID")

    def test_port_validation(self) -> None:
        """Test port number validation."""
        # Valid ports should work
        config = ServerConfig(port=8080)
        assert config.port == 8080

        # Invalid port should raise error
        with pytest.raises(ValueError):
            ServerConfig(port=70000)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test loading configuration from environment variables."""
        # Create a temporary spec file
        spec_file = tmp_path / "openapi.json"
        spec_file.write_text('{"paths": {}}')

        # Set environment variables
        monkeypatch.setenv("LOCAL_OPENAPI_SPEC_PATH", str(spec_file))
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("HTTP_SERVER_PORT", "8080")
        monkeypatch.setenv("UNITY_HOST", "unity.example.com")

        config = load_config()

        assert config.server.log_level == "DEBUG"
        assert config.server.port == 8080
        assert config.unity.host == "unity.example.com"

    def test_load_config_missing_spec_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test error when LOCAL_OPENAPI_SPEC_PATH is missing or empty."""
        # Set LOCAL_OPENAPI_SPEC_PATH to empty string to simulate missing
        monkeypatch.setenv("LOCAL_OPENAPI_SPEC_PATH", "")

        # Change to temp dir to avoid loading .env from workspace
        monkeypatch.chdir(tmp_path)

        with pytest.raises(EnvironmentVariableError):
            load_config()

    def test_load_config_invalid_spec_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test error when spec file doesn't exist."""
        monkeypatch.setenv("LOCAL_OPENAPI_SPEC_PATH", "/nonexistent/path.json")

        with pytest.raises(ConfigurationError):
            load_config()


class TestConfigModel:
    """Tests for the Config model."""

    def test_config_creation(self, tmp_path: Path) -> None:
        """Test creating a complete configuration."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text('{"paths": {}}')

        config = Config(
            unity=UnityConfig(
                host="unity.example.com",
                local_spec_path=str(spec_file),
            ),
            server=ServerConfig(
                port=3000,
                log_level="INFO",
            ),
        )

        assert config.unity.host == "unity.example.com"
        assert config.server.port == 3000

    def test_config_extra_fields_ignored(self, tmp_path: Path) -> None:
        """Test that extra fields are ignored."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text('{"paths": {}}')

        # Extra fields should be ignored
        config = Config(
            unity=UnityConfig(
                host="example.com",
                local_spec_path=str(spec_file),
            ),
            server=ServerConfig(),
        )

        assert hasattr(config, "unity")
        assert hasattr(config, "server")
