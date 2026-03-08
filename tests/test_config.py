"""Tests for configuration module."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from dads_money.config import Config


class TestConfigPaths:
    """Tests for configuration path handling."""

    def test_config_app_name(self) -> None:
        """Test application name constant."""
        assert Config.APP_NAME == "Dad's Money"
        assert isinstance(Config.APP_NAME, str)

    def test_config_app_version(self) -> None:
        """Test application version constant."""
        assert Config.APP_VERSION == "0.1.0"
        assert isinstance(Config.APP_VERSION, str)

    def test_get_user_data_dir_returns_path(self) -> None:
        """Test that get_user_data_dir returns a Path object."""
        result = Config.get_user_data_dir()
        assert isinstance(result, Path)

    def test_get_user_data_dir_ends_with_dadsmoney(self) -> None:
        """Test that user data dir ends with DadsMoney."""
        result = Config.get_user_data_dir()
        assert result.name == "DadsMoney"

    def test_get_user_data_dir_creates_directory(self) -> None:
        """Test that get_user_data_dir creates the directory if it doesn't exist."""
        data_dir = Config.get_user_data_dir()
        assert data_dir.exists()
        assert data_dir.is_dir()

    def test_get_database_path_consistency(self) -> None:
        """Test that database path is consistent."""
        db_path1 = Config.get_database_path()
        db_path2 = Config.get_database_path()
        assert db_path1 == db_path2

    def test_get_database_path_is_db_file(self) -> None:
        """Test that database path ends with .db."""
        db_path = Config.get_database_path()
        assert db_path.suffix == ".db"
        assert db_path.name == "dadsmoney.db"

    def test_get_database_path_under_data_dir(self) -> None:
        """Test that database path is under the data directory."""
        db_path = Config.get_database_path()
        data_dir = Config.get_user_data_dir()
        assert db_path.parent == data_dir

    def test_get_log_path_is_log_file(self) -> None:
        """Test that log path ends with .log."""
        log_path = Config.get_log_path()
        assert log_path.suffix == ".log"
        assert log_path.name == "dadsmoney.log"

    def test_get_log_path_under_data_dir(self) -> None:
        """Test that log path is under the data directory."""
        log_path = Config.get_log_path()
        data_dir = Config.get_user_data_dir()
        assert log_path.parent == data_dir

    def test_multiple_calls_same_paths(self) -> None:
        """Test that subsequent calls return the same paths."""
        data_dir1 = Config.get_user_data_dir()
        data_dir2 = Config.get_user_data_dir()
        db_path1 = Config.get_database_path()
        db_path2 = Config.get_database_path()
        log_path1 = Config.get_log_path()
        log_path2 = Config.get_log_path()

        assert data_dir1 == data_dir2
        assert db_path1 == db_path2
        assert log_path1 == log_path2

    @patch("os.name", "nt")
    @patch.dict(os.environ, {"APPDATA": "C:\\Users\\TestUser\\AppData\\Roaming"})
    def test_windows_path_handling(self) -> None:
        """Test Windows path handling with mocked os.name."""
        # This test mocks the os.name to 'nt' (Windows)
        # Note: This is a simplified test - full Windows path testing
        # would require more complex mocking
        result = Config.get_user_data_dir()
        assert isinstance(result, Path)
        assert result.name == "DadsMoney"

    @patch("os.name", "posix")
    @patch("os.uname")
    def test_posix_path_handling(self, mock_uname) -> None:
        """Test POSIX path handling."""
        # Mock uname to return non-Darwin for Linux test
        mock_uname.return_value = type("obj", (object,), {"sysname": "Linux"})()

        result = Config.get_user_data_dir()
        assert isinstance(result, Path)
        assert result.name == "DadsMoney"

    def test_paths_are_absolute(self) -> None:
        """Test that all returned paths are absolute."""
        data_dir = Config.get_user_data_dir()
        db_path = Config.get_database_path()
        log_path = Config.get_log_path()

        assert data_dir.is_absolute()
        assert db_path.is_absolute()
        assert log_path.is_absolute()


class TestConfigIntegration:
    """Integration tests for configuration."""

    def test_config_database_path_writable(self) -> None:
        """Test that database path location is writable."""
        db_path = Config.get_database_path()
        # Directory should exist and be writable
        assert db_path.parent.exists()
        # Try to check write permissions
        assert os.access(db_path.parent, os.W_OK)

    def test_config_all_paths_same_parent(self) -> None:
        """Test that all config paths are under the same parent directory."""
        data_dir = Config.get_user_data_dir()
        db_path = Config.get_database_path()
        log_path = Config.get_log_path()

        assert db_path.parent == data_dir
        assert log_path.parent == data_dir

    def test_config_values_match_constants(self) -> None:
        """Test that config name/version match expected values."""
        assert Config.APP_NAME == "Dad's Money"
        assert "0.1.0" in Config.APP_VERSION
