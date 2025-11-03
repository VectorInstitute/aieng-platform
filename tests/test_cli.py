"""Unit tests for aieng_platform_onboard.cli module."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from aieng_platform_onboard.cli import (
    display_onboarding_status_report,
    get_version,
    main,
    run_integration_test,
)


class TestGetVersion:
    """Tests for get_version function."""

    def test_get_version_success(self) -> None:
        """Test successful version retrieval."""
        version = get_version()
        # Should return a valid version string (not 'unknown')
        assert version != "unknown"
        assert len(version) > 0

    def test_get_version_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test version retrieval when package is not installed."""

        def mock_version_error(package: str) -> None:
            raise Exception("Package not found")

        monkeypatch.setattr("aieng_platform_onboard.cli.version", mock_version_error)

        version = get_version()
        assert version == "unknown"


class TestRunIntegrationTest:
    """Tests for run_integration_test function."""

    def test_run_integration_test_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful integration test execution."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "test passed"
        mock_result.stderr = ""

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        success, output = run_integration_test(test_script)

        assert success is True
        assert "test passed" in output

    def test_run_integration_test_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test integration test execution failure."""
        test_script = tmp_path / "test.py"
        test_script.write_text("import sys; sys.exit(1)")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "test failed"

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        success, output = run_integration_test(test_script)

        assert success is False
        assert "test failed" in output

    def test_run_integration_test_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test integration test timeout."""
        test_script = tmp_path / "test.py"
        test_script.write_text("while True: pass")

        def mock_run(*args: Any, **kwargs: Any) -> None:
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=60)

        monkeypatch.setattr("subprocess.run", mock_run)

        success, output = run_integration_test(test_script)

        assert success is False
        assert "timed out" in output


class TestDisplayOnboardingStatusReport:
    """Tests for display_onboarding_status_report function."""

    def test_display_status_report_success(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test successful display of onboarding status report."""
        # Mock initialize_firestore_admin
        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_admin",
            lambda **kwargs: mock_db,
        )

        # Mock get_all_participants_with_status
        mock_participants = [
            {
                "github_handle": "user1",
                "team_name": "team-a",
                "onboarded": True,
                "onboarded_at": None,
            },
            {
                "github_handle": "user2",
                "team_name": "team-a",
                "onboarded": False,
                "onboarded_at": None,
            },
            {
                "github_handle": "user3",
                "team_name": "team-b",
                "onboarded": True,
                "onboarded_at": None,
            },
        ]
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_all_participants_with_status",
            lambda db: mock_participants,
        )

        exit_code = display_onboarding_status_report("test-project")

        assert exit_code == 0
        # Verify console.print was called (output was displayed)
        assert mock_console.print.call_count > 0

    def test_display_status_report_no_participants(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test status report display when no participants exist."""
        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_admin",
            lambda **kwargs: mock_db,
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_all_participants_with_status",
            lambda db: [],
        )

        exit_code = display_onboarding_status_report("test-project")

        assert exit_code == 0

    def test_display_status_report_firestore_error(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test status report display with Firestore connection error."""

        def mock_init_error(**kwargs: Any) -> None:
            raise Exception("Connection failed")

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_admin", mock_init_error
        )

        exit_code = display_onboarding_status_report("test-project")

        assert exit_code == 1

    def test_display_status_report_fetch_error(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test status report display with data fetch error."""
        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_admin",
            lambda **kwargs: mock_db,
        )

        def mock_fetch_error(db: Any) -> None:
            raise Exception("Failed to fetch participants")

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_all_participants_with_status",
            mock_fetch_error,
        )

        exit_code = display_onboarding_status_report("test-project")

        assert exit_code == 1


class TestMain:
    """Tests for main function."""

    def test_main_version_flag(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test main with --version flag."""
        monkeypatch.setattr("sys.argv", ["onboard", "--version"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Should contain "onboard" and a version number
        assert "onboard" in captured.out
        assert len(captured.out.strip()) > 0

    def test_main_admin_status_report(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test main with --admin-status-report flag."""
        monkeypatch.setattr(
            "sys.argv", ["onboard", "--admin-status-report", "--gcp-project", "test"]
        )

        # Mock the display function
        mock_display = Mock(return_value=0)
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.display_onboarding_status_report",
            mock_display,
        )

        exit_code = main()

        assert exit_code == 0
        mock_display.assert_called_once_with("test")

    def test_main_missing_required_args(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test main with missing required arguments."""
        monkeypatch.setattr("sys.argv", ["onboard"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "--bootcamp-name is required" in captured.err

    def test_main_check_already_onboarded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main when participant is already onboarded."""
        # Create a complete .env file
        env_file = tmp_path / ".env"
        env_content = """
OPENAI_API_KEY="test-key"
EMBEDDING_BASE_URL="https://example.com"
EMBEDDING_API_KEY="test-key"
LANGFUSE_SECRET_KEY="test-key"
LANGFUSE_PUBLIC_KEY="test-key"
LANGFUSE_HOST="https://example.com"
WEB_SEARCH_API_KEY="test-key"
WEAVIATE_HTTP_HOST="example.com"
WEAVIATE_GRPC_HOST="example.com"
WEAVIATE_API_KEY="test-key"
"""
        env_file.write_text(env_content)

        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--output-dir",
                str(tmp_path),
            ],
        )

        exit_code = main()

        assert exit_code == 0

    def test_main_successful_onboarding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test successful participant onboarding flow."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--output-dir",
                str(tmp_path),
                "--firebase-api-key",
                "test-key",
            ],
        )

        # Mock environment
        monkeypatch.setenv("GITHUB_USER", "test-user")

        # Mock fetch_token_from_service
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.fetch_token_from_service",
            lambda user: (True, "test-token", None),
        )

        # Mock initialize_firestore_with_token
        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_with_token",
            lambda *args, **kwargs: mock_db,
        )

        # Mock check_onboarded_status
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.check_onboarded_status",
            lambda db, user: (True, False),
        )

        # Mock get_participant_data
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_participant_data",
            lambda db, user: {
                "github_handle": "test-user",
                "team_name": "test-team",
                "onboarded": False,
            },
        )

        # Mock get_team_data
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_team_data",
            lambda db, team: {
                "team_name": "test-team",
                "openai_api_key": "test-key",
                "langfuse_secret_key": "test-secret",
                "langfuse_public_key": "test-public",
                "langfuse_url": "https://test.example.com",
                "web_search_api_key": "test-search",
            },
        )

        # Mock get_global_keys
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_global_keys",
            lambda db: {
                "EMBEDDING_BASE_URL": "https://embedding.example.com",
                "EMBEDDING_API_KEY": "test-embedding",
                "WEAVIATE_HTTP_HOST": "weaviate.example.com",
                "WEAVIATE_GRPC_HOST": "weaviate-grpc.example.com",
                "WEAVIATE_API_KEY": "test-weaviate",
                "WEAVIATE_HTTP_PORT": "443",
                "WEAVIATE_GRPC_PORT": "50051",
                "WEAVIATE_HTTP_SECURE": "true",
                "WEAVIATE_GRPC_SECURE": "true",
            },
        )

        # Mock subprocess.run for integration test
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "test passed"
        mock_result.stderr = ""
        monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_result)

        # Mock update_onboarded_status
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        exit_code = main()

        assert exit_code == 0
        # Verify .env file was created
        env_file = tmp_path / ".env"
        assert env_file.exists()

    def test_main_authentication_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main with authentication failure."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--output-dir",
                str(tmp_path),
                "--firebase-api-key",
                "test-key",
            ],
        )

        monkeypatch.setenv("GITHUB_USER", "test-user")

        # Mock failed authentication
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.fetch_token_from_service",
            lambda user: (False, None, "Authentication failed"),
        )

        exit_code = main()

        assert exit_code == 1

    def test_main_participant_not_found(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main when participant is not found in Firestore."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--output-dir",
                str(tmp_path),
                "--firebase-api-key",
                "test-key",
            ],
        )

        monkeypatch.setenv("GITHUB_USER", "test-user")

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.fetch_token_from_service",
            lambda user: (True, "test-token", None),
        )

        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_with_token",
            lambda *args, **kwargs: mock_db,
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.check_onboarded_status",
            lambda db, user: (True, False),
        )

        # Return None for participant not found
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_participant_data",
            lambda db, user: None,
        )

        exit_code = main()

        assert exit_code == 1

    def test_main_skip_test_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main with --skip-test flag."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--skip-test",
                "--firebase-api-key",
                "test-key",
            ],
        )

        monkeypatch.setenv("GITHUB_USER", "test-user")

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.fetch_token_from_service",
            lambda user: (True, "test-token", None),
        )

        mock_db = Mock()
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.initialize_firestore_with_token",
            lambda *args, **kwargs: mock_db,
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.check_onboarded_status",
            lambda db, user: (True, False),
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_participant_data",
            lambda db, user: {
                "github_handle": "test-user",
                "team_name": "test-team",
            },
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_team_data",
            lambda db, team: {
                "team_name": "test-team",
                "openai_api_key": "test-key",
                "langfuse_secret_key": "test-secret",
                "langfuse_public_key": "test-public",
                "langfuse_url": "https://test.example.com",
                "web_search_api_key": "test-search",
            },
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.get_global_keys",
            lambda db: {
                "EMBEDDING_BASE_URL": "https://embedding.example.com",
                "EMBEDDING_API_KEY": "test-embedding",
                "WEAVIATE_HTTP_HOST": "weaviate.example.com",
                "WEAVIATE_GRPC_HOST": "weaviate-grpc.example.com",
                "WEAVIATE_API_KEY": "test-weaviate",
                "WEAVIATE_HTTP_PORT": "443",
                "WEAVIATE_GRPC_PORT": "50051",
                "WEAVIATE_HTTP_SECURE": "true",
                "WEAVIATE_GRPC_SECURE": "true",
            },
        )

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        exit_code = main()

        assert exit_code == 0
