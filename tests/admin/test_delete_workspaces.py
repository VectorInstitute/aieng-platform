"""Unit tests for admin delete_workspaces module."""

import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from aieng_platform_onboard.admin.cli import main
from aieng_platform_onboard.admin.delete_workspaces import (
    delete_workspace_cli,
    delete_workspaces,
    delete_workspaces_before_date,
    display_workspace_table,
    fetch_all_workspaces,
    filter_workspaces_by_date,
    parse_date,
    parse_workspace_created_at,
    run_coder_command,
)


class TestRunCoderCommand:
    """Tests for run_coder_command function."""

    def test_run_coder_command_success(self) -> None:
        """Test successful coder command execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="test output", stderr="")

            result = run_coder_command(["version"])

            mock_run.assert_called_once_with(
                ["coder", "version"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout == "test output"

    def test_run_coder_command_not_found(self) -> None:
        """Test error when coder CLI is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError("coder not found")):
            with pytest.raises(RuntimeError) as exc_info:
                run_coder_command(["version"])

            assert "Coder CLI not found" in str(exc_info.value)

    def test_run_coder_command_failure(self) -> None:
        """Test error when coder command fails."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "coder", stderr="error"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                run_coder_command(["delete", "test"])

            assert "Coder command failed" in str(exc_info.value)

    def test_run_coder_command_no_check(self) -> None:
        """Test running command without checking return code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="error message"
            )

            result = run_coder_command(["delete", "test"], check=False)

            assert result.returncode == 1
            mock_run.assert_called_once_with(
                ["coder", "delete", "test"],
                capture_output=True,
                text=True,
                check=False,
            )


class TestFetchAllWorkspaces:
    """Tests for fetch_all_workspaces function."""

    def test_fetch_all_workspaces_success(self) -> None:
        """Test successfully fetching workspaces."""
        workspaces = [
            {"id": "ws1", "name": "workspace1", "owner_name": "user1"},
            {"id": "ws2", "name": "workspace2", "owner_name": "user2"},
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout=json.dumps(workspaces))

            result = fetch_all_workspaces()

            assert result == workspaces
            mock_run.assert_called_once_with(["list", "-a", "-o", "json"])

    def test_fetch_all_workspaces_empty(self) -> None:
        """Test fetching workspaces when none exist."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout="[]")

            result = fetch_all_workspaces()

            assert result == []

    def test_fetch_all_workspaces_invalid_json(self) -> None:
        """Test error when response is not valid JSON."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout="invalid json")

            with pytest.raises(RuntimeError) as exc_info:
                fetch_all_workspaces()

            assert "Failed to parse workspace data" in str(exc_info.value)

    def test_fetch_all_workspaces_command_error(self) -> None:
        """Test error when coder command fails."""
        with (
            patch(
                "aieng_platform_onboard.admin.delete_workspaces.run_coder_command",
                side_effect=RuntimeError("Command failed"),
            ),
            pytest.raises(RuntimeError),
        ):
            fetch_all_workspaces()


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_date_valid(self) -> None:
        """Test parsing valid date string."""
        result = parse_date("2025-01-15")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_date_invalid_format(self) -> None:
        """Test error with invalid date format."""
        with pytest.raises(ValueError) as exc_info:
            parse_date("01-15-2025")

        assert "Invalid date format" in str(exc_info.value)
        assert "Use YYYY-MM-DD" in str(exc_info.value)

    def test_parse_date_invalid_date(self) -> None:
        """Test error with invalid date."""
        with pytest.raises(ValueError) as exc_info:
            parse_date("2025-13-01")  # Invalid month

        assert "Invalid date format" in str(exc_info.value)

    def test_parse_date_empty_string(self) -> None:
        """Test error with empty string."""
        with pytest.raises(ValueError):
            parse_date("")


class TestParseWorkspaceCreatedAt:
    """Tests for parse_workspace_created_at function."""

    def test_parse_workspace_created_at_with_z(self) -> None:
        """Test parsing timestamp with Z suffix."""
        result = parse_workspace_created_at("2025-01-15T10:30:00Z")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_workspace_created_at_with_offset(self) -> None:
        """Test parsing timestamp with timezone offset."""
        result = parse_workspace_created_at("2025-01-15T10:30:00+00:00")

        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_workspace_created_at_with_microseconds(self) -> None:
        """Test parsing timestamp with microseconds."""
        result = parse_workspace_created_at("2025-01-15T10:30:00.123456Z")

        assert result.year == 2025
        assert result.microsecond == 123456


class TestFilterWorkspacesByDate:
    """Tests for filter_workspaces_by_date function."""

    def test_filter_workspaces_by_date_filters_old(self) -> None:
        """Test filtering keeps only old workspaces."""
        workspaces = [
            {"id": "ws1", "name": "old", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "ws2", "name": "new", "created_at": "2025-06-01T00:00:00Z"},
        ]
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date(workspaces, cutoff)

        assert len(result) == 1
        assert result[0]["name"] == "old"

    def test_filter_workspaces_by_date_all_old(self) -> None:
        """Test filtering when all workspaces are old."""
        workspaces = [
            {"id": "ws1", "name": "old1", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "ws2", "name": "old2", "created_at": "2024-06-01T00:00:00Z"},
        ]
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date(workspaces, cutoff)

        assert len(result) == 2

    def test_filter_workspaces_by_date_none_old(self) -> None:
        """Test filtering when no workspaces are old."""
        workspaces = [
            {"id": "ws1", "name": "new1", "created_at": "2025-06-01T00:00:00Z"},
            {"id": "ws2", "name": "new2", "created_at": "2025-07-01T00:00:00Z"},
        ]
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date(workspaces, cutoff)

        assert len(result) == 0

    def test_filter_workspaces_by_date_skips_missing_date(self) -> None:
        """Test filtering skips workspaces without created_at."""
        workspaces = [
            {"id": "ws1", "name": "old", "created_at": "2024-01-01T00:00:00Z"},
            {"id": "ws2", "name": "no-date"},  # No created_at
        ]
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date(workspaces, cutoff)

        assert len(result) == 1
        assert result[0]["name"] == "old"

    def test_filter_workspaces_by_date_empty_list(self) -> None:
        """Test filtering empty workspace list."""
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date([], cutoff)

        assert result == []

    def test_filter_workspaces_by_date_exact_cutoff(self) -> None:
        """Test that workspace created at exact cutoff time is not included."""
        workspaces = [
            {"id": "ws1", "name": "exact", "created_at": "2025-01-01T00:00:00Z"},
        ]
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = filter_workspaces_by_date(workspaces, cutoff)

        # Workspace created at exact cutoff should NOT be included (< not <=)
        assert len(result) == 0


class TestDeleteWorkspaceCli:
    """Tests for delete_workspace_cli function."""

    def test_delete_workspace_cli_success(self) -> None:
        """Test successful workspace deletion."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = delete_workspace_cli("user1", "workspace1")

            assert result is True
            mock_run.assert_called_once_with(
                ["delete", "user1/workspace1", "-y"], check=False
            )

    def test_delete_workspace_cli_with_orphan(self) -> None:
        """Test workspace deletion with orphan flag."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = delete_workspace_cli("user1", "workspace1", orphan=True)

            assert result is True
            mock_run.assert_called_once_with(
                ["delete", "user1/workspace1", "-y", "--orphan"], check=False
            )

    def test_delete_workspace_cli_dry_run(self) -> None:
        """Test dry run mode doesn't delete."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            result = delete_workspace_cli("user1", "workspace1", dry_run=True)

            assert result is True
            mock_run.assert_not_called()

    def test_delete_workspace_cli_dry_run_with_orphan(self) -> None:
        """Test dry run mode with orphan flag."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            result = delete_workspace_cli(
                "user1", "workspace1", orphan=True, dry_run=True
            )

            assert result is True
            mock_run.assert_not_called()

    def test_delete_workspace_cli_failure(self) -> None:
        """Test workspace deletion failure."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="workspace not found"
            )

            result = delete_workspace_cli("user1", "workspace1")

            assert result is False

    def test_delete_workspace_cli_runtime_error(self) -> None:
        """Test workspace deletion with runtime error."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command",
            side_effect=RuntimeError("CLI error"),
        ):
            result = delete_workspace_cli("user1", "workspace1")

            assert result is False

    def test_delete_workspace_cli_terraform_error_auto_orphan(self) -> None:
        """Test auto-orphan retry when Terraform fails."""
        call_count = 0

        def mock_run_side_effect(args: list, check: bool = True):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with Terraform error
                return Mock(
                    returncode=1,
                    stdout="",
                    stderr="error: initialize terraform: exit status 1",
                )
            # Second call (with --orphan) succeeds
            return Mock(returncode=0, stdout="", stderr="")

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command",
            side_effect=mock_run_side_effect,
        ):
            result = delete_workspace_cli(
                "user1", "workspace1", auto_orphan_on_failure=True
            )

            assert result is True
            assert call_count == 2

    def test_delete_workspace_cli_terraform_error_no_auto_orphan(self) -> None:
        """Test no retry when auto_orphan_on_failure is False."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="error: initialize terraform: exit status 1",
            )

            result = delete_workspace_cli(
                "user1", "workspace1", auto_orphan_on_failure=False
            )

            assert result is False
            # Should only be called once (no retry)
            assert mock_run.call_count == 1

    def test_delete_workspace_cli_non_terraform_error_no_retry(self) -> None:
        """Test no auto-orphan retry for non-Terraform errors."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="error: workspace not found",
            )

            result = delete_workspace_cli(
                "user1", "workspace1", auto_orphan_on_failure=True
            )

            assert result is False
            # Should only be called once (no retry for non-Terraform errors)
            assert mock_run.call_count == 1


class TestDeleteWorkspaces:
    """Tests for delete_workspaces function."""

    def test_delete_workspaces_success(self) -> None:
        """Test successfully deleting multiple workspaces."""
        workspaces = [
            {"id": "ws1", "name": "workspace1", "owner_name": "user1"},
            {"id": "ws2", "name": "workspace2", "owner_name": "user2"},
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli",
            return_value=True,
        ) as mock_delete:
            success, failed = delete_workspaces(workspaces)

            assert success == 2
            assert failed == 0
            assert mock_delete.call_count == 2

    def test_delete_workspaces_partial_failure(self) -> None:
        """Test deleting workspaces with some failures."""
        workspaces = [
            {"id": "ws1", "name": "workspace1", "owner_name": "user1"},
            {"id": "ws2", "name": "workspace2", "owner_name": "user2"},
        ]

        def mock_delete_side_effect(
            owner_name: str, workspace_name: str, **kwargs
        ) -> bool:
            return workspace_name == "workspace1"

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli",
            side_effect=mock_delete_side_effect,
        ):
            success, failed = delete_workspaces(workspaces)

            assert success == 1
            assert failed == 1

    def test_delete_workspaces_dry_run(self) -> None:
        """Test dry run mode."""
        workspaces = [
            {"id": "ws1", "name": "workspace1", "owner_name": "user1"},
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli",
            return_value=True,
        ) as mock_delete:
            success, failed = delete_workspaces(workspaces, dry_run=True)

            assert success == 1
            assert failed == 0
            mock_delete.assert_called_once_with(
                owner_name="user1",
                workspace_name="workspace1",
                orphan=False,
                auto_orphan_on_failure=True,
                dry_run=True,
            )

    def test_delete_workspaces_with_orphan(self) -> None:
        """Test deletion with orphan flag."""
        workspaces = [
            {"id": "ws1", "name": "workspace1", "owner_name": "user1"},
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli",
            return_value=True,
        ) as mock_delete:
            success, failed = delete_workspaces(workspaces, orphan=True)

            assert success == 1
            mock_delete.assert_called_once_with(
                owner_name="user1",
                workspace_name="workspace1",
                orphan=True,
                auto_orphan_on_failure=True,
                dry_run=False,
            )

    def test_delete_workspaces_missing_name(self) -> None:
        """Test handling workspace with missing name."""
        workspaces = [
            {"id": "ws1", "owner_name": "user1"},  # Missing name
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli"
        ) as mock_delete:
            success, failed = delete_workspaces(workspaces)

            assert success == 0
            assert failed == 1
            mock_delete.assert_not_called()

    def test_delete_workspaces_missing_owner(self) -> None:
        """Test handling workspace with missing owner."""
        workspaces = [
            {"id": "ws1", "name": "workspace1"},  # Missing owner_name
        ]

        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli"
        ) as mock_delete:
            success, failed = delete_workspaces(workspaces)

            assert success == 0
            assert failed == 1
            mock_delete.assert_not_called()

    def test_delete_workspaces_empty_list(self) -> None:
        """Test deleting empty workspace list."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.delete_workspace_cli"
        ) as mock_delete:
            success, failed = delete_workspaces([])

            assert success == 0
            assert failed == 0
            mock_delete.assert_not_called()


class TestDisplayWorkspaceTable:
    """Tests for display_workspace_table function."""

    def test_display_workspace_table_few_workspaces(self) -> None:
        """Test displaying table with few workspaces."""
        workspaces = [
            {
                "owner_name": "user1",
                "name": "workspace1",
                "template_name": "bootcamp",
                "created_at": "2024-01-01T00:00:00Z",
                "latest_build": {"status": "running"},
            },
        ]

        # Should not raise any exceptions
        display_workspace_table(workspaces, "2025-01-01")

    def test_display_workspace_table_many_workspaces(self) -> None:
        """Test displaying table with many workspaces (truncated)."""
        workspaces = [
            {
                "owner_name": f"user{i}",
                "name": f"workspace{i}",
                "template_name": "bootcamp",
                "created_at": "2024-01-01T00:00:00Z",
                "latest_build": {"status": "running"},
            }
            for i in range(30)
        ]

        # Should not raise any exceptions (should truncate to 20 + "and X more")
        display_workspace_table(workspaces, "2025-01-01")

    def test_display_workspace_table_empty(self) -> None:
        """Test displaying table with no workspaces."""
        # Should not raise any exceptions
        display_workspace_table([], "2025-01-01")

    def test_display_workspace_table_missing_fields(self) -> None:
        """Test displaying table with missing optional fields."""
        workspaces = [
            {"owner_name": "user1", "name": "workspace1"},  # Missing most fields
        ]

        # Should not raise any exceptions
        display_workspace_table(workspaces, "2025-01-01")


class TestDeleteWorkspacesBeforeDate:
    """Tests for delete_workspaces_before_date function."""

    def test_delete_workspaces_before_date_invalid_date(self) -> None:
        """Test with invalid date format."""
        exit_code = delete_workspaces_before_date("invalid-date")

        assert exit_code == 1

    def test_delete_workspaces_before_date_cli_not_available(self) -> None:
        """Test when Coder CLI is not available."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command",
            side_effect=RuntimeError("Coder CLI not found"),
        ):
            exit_code = delete_workspaces_before_date("2025-01-01")

            assert exit_code == 1

    def test_delete_workspaces_before_date_cli_version_error(self) -> None:
        """Test when Coder CLI version check fails."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="version check failed"
            )

            exit_code = delete_workspaces_before_date("2025-01-01")

            assert exit_code == 1

    def test_delete_workspaces_before_date_no_workspaces(self) -> None:
        """Test when no workspaces match the date filter."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            # First call: version check
            # Second call: list workspaces
            mock_run.side_effect = [
                Mock(returncode=0, stdout="Coder v2.0.0"),
                Mock(stdout="[]"),  # Empty workspace list
            ]

            with patch(
                "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                return_value=[
                    {"id": "ws1", "name": "new", "created_at": "2025-06-01T00:00:00Z"}
                ],
            ):
                exit_code = delete_workspaces_before_date("2025-01-01")

                assert exit_code == 0

    def test_delete_workspaces_before_date_fetch_error(self) -> None:
        """Test when fetching workspaces fails."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            with patch(
                "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                side_effect=RuntimeError("Fetch failed"),
            ):
                exit_code = delete_workspaces_before_date("2025-01-01")

                assert exit_code == 1

    def test_delete_workspaces_before_date_dry_run_success(self) -> None:
        """Test successful dry run."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            workspaces = [
                {
                    "id": "ws1",
                    "name": "old",
                    "owner_name": "user1",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]

            with (
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                    return_value=workspaces,
                ),
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.delete_workspaces",
                    return_value=(1, 0),
                ) as mock_delete,
            ):
                exit_code = delete_workspaces_before_date("2025-01-01", dry_run=True)

                assert exit_code == 0
                mock_delete.assert_called_once()
                # Verify dry_run was passed
                call_kwargs = mock_delete.call_args[1]
                assert call_kwargs["dry_run"] is True

    def test_delete_workspaces_before_date_user_cancels(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test user cancelling deletion."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            workspaces = [
                {
                    "id": "ws1",
                    "name": "old",
                    "owner_name": "user1",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]

            # Mock input to return something other than "DELETE"
            monkeypatch.setattr("builtins.input", lambda: "CANCEL")

            with patch(
                "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                return_value=workspaces,
            ):
                exit_code = delete_workspaces_before_date("2025-01-01", dry_run=False)

                assert exit_code == 0  # Cancelled successfully

    def test_delete_workspaces_before_date_success_with_confirmation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful deletion with user confirmation."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            workspaces = [
                {
                    "id": "ws1",
                    "name": "old",
                    "owner_name": "user1",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]

            # Mock input to return "DELETE"
            monkeypatch.setattr("builtins.input", lambda: "DELETE")

            with (
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                    return_value=workspaces,
                ),
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.delete_workspaces",
                    return_value=(1, 0),
                ),
            ):
                exit_code = delete_workspaces_before_date("2025-01-01", dry_run=False)

                assert exit_code == 0

    def test_delete_workspaces_before_date_with_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test deletion with some failures."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            workspaces = [
                {
                    "id": "ws1",
                    "name": "old",
                    "owner_name": "user1",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]

            # Mock input to return "DELETE"
            monkeypatch.setattr("builtins.input", lambda: "DELETE")

            with (
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                    return_value=workspaces,
                ),
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.delete_workspaces",
                    return_value=(0, 1),  # All failed
                ),
            ):
                exit_code = delete_workspaces_before_date("2025-01-01", dry_run=False)

                assert exit_code == 1

    def test_delete_workspaces_before_date_with_orphan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test deletion with orphan flag."""
        with patch(
            "aieng_platform_onboard.admin.delete_workspaces.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Coder v2.0.0")

            workspaces = [
                {
                    "id": "ws1",
                    "name": "old",
                    "owner_name": "user1",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]

            # Mock input to return "DELETE"
            monkeypatch.setattr("builtins.input", lambda: "DELETE")

            with (
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.fetch_all_workspaces",
                    return_value=workspaces,
                ),
                patch(
                    "aieng_platform_onboard.admin.delete_workspaces.delete_workspaces",
                    return_value=(1, 0),
                ) as mock_delete,
            ):
                exit_code = delete_workspaces_before_date(
                    "2025-01-01", orphan=True, dry_run=False
                )

                assert exit_code == 0
                # Verify orphan was passed
                call_kwargs = mock_delete.call_args[1]
                assert call_kwargs["orphan"] is True


class TestAdminCLIDeleteWorkspaces:
    """Tests for delete-workspaces CLI command integration."""

    def test_cli_delete_workspaces_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test CLI with delete-workspaces --help."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "delete-workspaces", "--help"]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--before" in captured.out
        assert "--dry-run" in captured.out
        assert "--orphan" in captured.out

    def test_cli_delete_workspaces_missing_before(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test CLI with missing --before argument."""
        monkeypatch.setattr("sys.argv", ["onboard admin", "delete-workspaces"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower() or "--before" in captured.err

    def test_cli_delete_workspaces_calls_function(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI calls delete_workspaces_before_date with correct args."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2025-01-01",
                "--dry-run",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_workspaces_before_date",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                before_date="2025-01-01",
                orphan=False,
                auto_orphan_on_failure=True,
                dry_run=True,
            )

    def test_cli_delete_workspaces_with_orphan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI with --orphan flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2025-01-01",
                "--orphan",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_workspaces_before_date",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                before_date="2025-01-01",
                orphan=True,
                auto_orphan_on_failure=True,
                dry_run=False,
            )

    def test_cli_delete_workspaces_no_auto_orphan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI with --no-auto-orphan flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2025-01-01",
                "--no-auto-orphan",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_workspaces_before_date",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                before_date="2025-01-01",
                orphan=False,
                auto_orphan_on_failure=False,
                dry_run=False,
            )
