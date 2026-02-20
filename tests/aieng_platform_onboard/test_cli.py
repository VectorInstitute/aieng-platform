"""Unit tests for aieng_platform_onboard.cli module."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from aieng_platform_onboard.cli import (
    _run_tests_and_finalize,
    _validate_onboard_args,
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

    def test_run_integration_test_with_marker_passes_m_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a marker is forwarded as -m <marker> to pytest."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed"
        mock_result.stderr = ""

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        success, _ = run_integration_test(test_script, marker="integration_test")

        assert success is True
        cmd = mock_run.call_args[0][0]
        # The command is [python, "-m", "pytest", script, "-m", "integration_test"].
        # Two "-m" flags: one for module invocation, one for the marker.
        assert cmd.count("-m") == 2
        assert "integration_test" in cmd
        # Marker value must immediately follow the second -m flag
        assert cmd[-2:] == ["-m", "integration_test"]

    def test_run_integration_test_without_marker_omits_m_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that omitting marker does not add a second -m flag to pytest."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed"
        mock_result.stderr = ""

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        run_integration_test(test_script)  # marker defaults to None

        cmd = mock_run.call_args[0][0]
        # Only one "-m" in the command: the "python -m pytest" module invocation.
        assert cmd.count("-m") == 1

    def test_run_integration_test_base_command_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the base pytest command is always [python, -m, pytest, script]."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        run_integration_test(test_script, marker="smoke")

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1:3] == ["-m", "pytest"]
        assert str(test_script) in cmd


class TestRunTestsAndFinalize:
    """Tests for _run_tests_and_finalize function."""

    def test_marker_forwarded_to_run_integration_test(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test that test_marker is forwarded to run_integration_test."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        captured_marker: list[str | None] = []

        def mock_run_integration_test(
            script: Path, marker: str | None = None
        ) -> tuple[bool, str]:
            captured_marker.append(marker)
            return True, "passed"

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.run_integration_test", mock_run_integration_test
        )
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        mock_db = Mock()
        result = _run_tests_and_finalize(
            mock_db,
            "test-user",
            skip_test=False,
            test_script=str(test_script),
            test_marker="smoke",
        )

        assert result is True
        assert captured_marker == ["smoke"]

    def test_no_marker_passes_none_to_run_integration_test(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test that omitting test_marker passes None to run_integration_test."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        captured_marker: list[str | None] = []

        def mock_run_integration_test(
            script: Path, marker: str | None = None
        ) -> tuple[bool, str]:
            captured_marker.append(marker)
            return True, "passed"

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.run_integration_test", mock_run_integration_test
        )
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        mock_db = Mock()
        result = _run_tests_and_finalize(
            mock_db, "test-user", skip_test=False, test_script=str(test_script)
        )

        assert result is True
        assert captured_marker == [None]

    def test_skip_test_does_not_call_run_integration_test(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test that skip_test=True bypasses run_integration_test entirely."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        mock_run_integration_test = Mock(return_value=(True, "passed"))
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.run_integration_test", mock_run_integration_test
        )
        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        mock_db = Mock()
        result = _run_tests_and_finalize(
            mock_db,
            "test-user",
            skip_test=True,
            test_script=str(test_script),
            test_marker="smoke",
        )

        assert result is True
        mock_run_integration_test.assert_not_called()


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


class TestValidateOnboardArgs:
    """Tests for _validate_onboard_args function."""

    def test_missing_bootcamp_name_errors(self, capsys: pytest.CaptureFixture) -> None:
        """Test that omitting --bootcamp-name causes a parser error."""
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(
            bootcamp_name=None, test_script="test.py", env_example=".env.example"
        )

        with pytest.raises(SystemExit) as exc_info:
            _validate_onboard_args(parser, args)

        assert exc_info.value.code == 2
        assert "--bootcamp-name is required" in capsys.readouterr().err

    def test_missing_test_script_errors(self, capsys: pytest.CaptureFixture) -> None:
        """Test that omitting --test-script causes a parser error."""
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(
            bootcamp_name="bootcamp", test_script=None, env_example=".env.example"
        )

        with pytest.raises(SystemExit) as exc_info:
            _validate_onboard_args(parser, args)

        assert exc_info.value.code == 2
        assert "--test-script is required" in capsys.readouterr().err

    def test_missing_env_example_errors(self, capsys: pytest.CaptureFixture) -> None:
        """Test that omitting --env-example causes a parser error."""
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(
            bootcamp_name="bootcamp", test_script="test.py", env_example=None
        )

        with pytest.raises(SystemExit) as exc_info:
            _validate_onboard_args(parser, args)

        assert exc_info.value.code == 2
        assert "--env-example is required" in capsys.readouterr().err

    def test_all_args_present_does_not_error(self) -> None:
        """Test that no error is raised when all three required args are present."""
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(
            bootcamp_name="bootcamp", test_script="test.py", env_example=".env.example"
        )
        # Should complete without raising
        _validate_onboard_args(parser, args)


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

    def test_main_missing_env_example(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test main errors with a clear message when --env-example is omitted."""
        monkeypatch.setattr(
            "sys.argv",
            ["onboard", "--bootcamp-name", "test", "--test-script", "test.py"],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        assert "--env-example is required" in capsys.readouterr().err

    def test_main_check_already_onboarded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main when participant is already onboarded."""
        # Create a .env.example with the required keys
        env_example = tmp_path / ".env.example"
        env_example.write_text(
            'OPENAI_API_KEY=""\n'
            'EMBEDDING_BASE_URL=""\n'
            'EMBEDDING_API_KEY=""\n'
            'LANGFUSE_SECRET_KEY=""\n'
            'LANGFUSE_PUBLIC_KEY=""\n'
            'LANGFUSE_HOST=""\n'
            'WEB_SEARCH_BASE_URL=""\n'
            'WEB_SEARCH_API_KEY=""\n'
            'WEAVIATE_HTTP_HOST=""\n'
            'WEAVIATE_GRPC_HOST=""\n'
            'WEAVIATE_API_KEY=""\n'
        )

        # Create a complete .env file matching all keys in .env.example
        env_file = tmp_path / ".env"
        env_content = (
            'OPENAI_API_KEY="test-key"\n'
            'EMBEDDING_BASE_URL="https://example.com"\n'
            'EMBEDDING_API_KEY="test-key"\n'
            'LANGFUSE_SECRET_KEY="test-key"\n'
            'LANGFUSE_PUBLIC_KEY="test-key"\n'
            'LANGFUSE_HOST="https://example.com"\n'
            'WEB_SEARCH_BASE_URL="https://example.com"\n'
            'WEB_SEARCH_API_KEY="test-key"\n'
            'WEAVIATE_HTTP_HOST="example.com"\n'
            'WEAVIATE_GRPC_HOST="example.com"\n'
            'WEAVIATE_API_KEY="test-key"\n'
        )
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
                "--env-example",
                str(env_example),
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

        env_example = tmp_path / ".env.example"
        env_example.write_text(
            'OPENAI_API_KEY=""\n'
            'EMBEDDING_BASE_URL=""\n'
            'EMBEDDING_API_KEY=""\n'
            'WEAVIATE_HTTP_HOST=""\n'
            'WEAVIATE_GRPC_HOST=""\n'
            'WEAVIATE_API_KEY=""\n'
            'LANGFUSE_SECRET_KEY=""\n'
            'LANGFUSE_PUBLIC_KEY=""\n'
            'WEB_SEARCH_API_KEY=""\n'
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--env-example",
                str(env_example),
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
            lambda db, bootcamp_name: {
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

        env_example = tmp_path / ".env.example"
        env_example.write_text('OPENAI_API_KEY=""\n')

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--env-example",
                str(env_example),
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

        env_example = tmp_path / ".env.example"
        env_example.write_text('OPENAI_API_KEY=""\n')

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--env-example",
                str(env_example),
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

    def test_main_test_marker_passed_to_subprocess(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test that --test-marker is forwarded as -m <marker> to pytest."""
        test_script = tmp_path / "test.py"
        test_script.write_text("")

        env_example = tmp_path / ".env.example"
        env_example.write_text(
            'OPENAI_API_KEY=""\n'
            'EMBEDDING_BASE_URL=""\n'
            'EMBEDDING_API_KEY=""\n'
            'WEAVIATE_HTTP_HOST=""\n'
            'WEAVIATE_GRPC_HOST=""\n'
            'WEAVIATE_API_KEY=""\n'
            'LANGFUSE_SECRET_KEY=""\n'
            'LANGFUSE_PUBLIC_KEY=""\n'
            'WEB_SEARCH_API_KEY=""\n'
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--env-example",
                str(env_example),
                "--output-dir",
                str(tmp_path),
                "--firebase-api-key",
                "test-key",
                "--test-marker",
                "integration_test",
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
            lambda db, user: {"github_handle": "test-user", "team_name": "test-team"},
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
            lambda db, bootcamp_name: {
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

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "1 passed"
        mock_result.stderr = ""
        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_run)

        monkeypatch.setattr(
            "aieng_platform_onboard.cli.update_onboarded_status",
            lambda db, user: (True, None),
        )

        exit_code = main()

        assert exit_code == 0
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        assert "integration_test" in cmd

    def test_main_skip_test_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mock_console: Mock,
    ) -> None:
        """Test main with --skip-test flag."""
        test_script = tmp_path / "test.py"
        test_script.write_text("print('test')")

        env_example = tmp_path / ".env.example"
        env_example.write_text(
            'OPENAI_API_KEY=""\n'
            'EMBEDDING_BASE_URL=""\n'
            'EMBEDDING_API_KEY=""\n'
            'WEAVIATE_HTTP_HOST=""\n'
            'WEAVIATE_GRPC_HOST=""\n'
            'WEAVIATE_API_KEY=""\n'
            'LANGFUSE_SECRET_KEY=""\n'
            'LANGFUSE_PUBLIC_KEY=""\n'
            'WEB_SEARCH_API_KEY=""\n'
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard",
                "--bootcamp-name",
                "test",
                "--test-script",
                str(test_script),
                "--env-example",
                str(env_example),
                "--output-dir",
                str(tmp_path),
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
            lambda db, bootcamp_name: {
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
