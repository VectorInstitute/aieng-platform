"""Unit tests for admin CLI module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from aieng_platform_onboard.admin.cli import main


class TestAdminCLI:
    """Tests for admin CLI main function."""

    def test_admin_cli_no_command(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test admin CLI with no command."""
        monkeypatch.setattr("sys.argv", ["onboard admin"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert (
            "required" in captured.err.lower()
            or "invalid choice" in captured.err.lower()
        )

    def test_admin_cli_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test admin CLI with --help flag."""
        monkeypatch.setattr("sys.argv", ["onboard admin", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Admin commands" in captured.out or "admin" in captured.out.lower()
        assert "setup-participants" in captured.out

    def test_admin_cli_setup_participants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test admin CLI with setup-participants command."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "setup-participants", str(csv_file)]
        )

        # Mock the setup_participants_from_csv function
        with patch(
            "aieng_platform_onboard.admin.cli.setup_participants_from_csv",
            return_value=0,
        ) as mock_setup:
            exit_code = main()

            assert exit_code == 0
            mock_setup.assert_called_once_with(str(csv_file), dry_run=False)

    def test_admin_cli_setup_participants_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test admin CLI with setup-participants --dry-run."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        monkeypatch.setattr(
            "sys.argv",
            ["onboard admin", "setup-participants", str(csv_file), "--dry-run"],
        )

        # Mock the setup_participants_from_csv function
        with patch(
            "aieng_platform_onboard.admin.cli.setup_participants_from_csv",
            return_value=0,
        ) as mock_setup:
            exit_code = main()

            assert exit_code == 0
            mock_setup.assert_called_once_with(str(csv_file), dry_run=True)

    def test_admin_cli_setup_participants_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test admin CLI with setup-participants command that fails."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle,team_name\n-invalid,team@bad")

        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "setup-participants", str(csv_file)]
        )

        # Mock the setup_participants_from_csv function to return error
        with patch(
            "aieng_platform_onboard.admin.cli.setup_participants_from_csv",
            return_value=1,
        ):
            exit_code = main()

            assert exit_code == 1

    def test_admin_cli_setup_participants_missing_csv(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test admin CLI with setup-participants but missing CSV argument."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "setup-participants", "--dry-run"]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        # argparse exits with code 2 for missing required arguments
        assert exc_info.value.code == 2


class TestDeleteParticipantsCommand:
    """Tests for delete-participants command."""

    def test_delete_participants_basic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-participants command with basic arguments."""
        csv_file = tmp_path / "delete.csv"
        csv_file.write_text("github_handle\nuser1\nuser2")

        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "delete-participants", str(csv_file)]
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_participants_from_csv",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                str(csv_file), delete_empty_teams=True, dry_run=False
            )

    def test_delete_participants_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-participants command with --dry-run flag."""
        csv_file = tmp_path / "delete.csv"
        csv_file.write_text("github_handle\nuser1")

        monkeypatch.setattr(
            "sys.argv",
            ["onboard admin", "delete-participants", str(csv_file), "--dry-run"],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_participants_from_csv",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                str(csv_file), delete_empty_teams=True, dry_run=True
            )

    def test_delete_participants_keep_empty_teams(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-participants with --keep-empty-teams flag."""
        csv_file = tmp_path / "delete.csv"
        csv_file.write_text("github_handle\nuser1")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-participants",
                str(csv_file),
                "--keep-empty-teams",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_participants_from_csv",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                str(csv_file), delete_empty_teams=False, dry_run=False
            )

    def test_delete_participants_all_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-participants with multiple flags combined."""
        csv_file = tmp_path / "delete.csv"
        csv_file.write_text("github_handle\nuser1")

        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-participants",
                str(csv_file),
                "--dry-run",
                "--keep-empty-teams",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_participants_from_csv",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                str(csv_file), delete_empty_teams=False, dry_run=True
            )

    def test_delete_participants_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-participants command with error return."""
        csv_file = tmp_path / "delete.csv"
        csv_file.write_text("github_handle\nuser1")

        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "delete-participants", str(csv_file)]
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_participants_from_csv",
            return_value=1,
        ):
            exit_code = main()

            assert exit_code == 1

    def test_delete_participants_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test delete-participants help message."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "delete-participants", "--help"]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "delete-participants" in captured.out.lower()
        assert "--dry-run" in captured.out
        assert "--keep-empty-teams" in captured.out


class TestDeleteWorkspacesCommand:
    """Tests for delete-workspaces command."""

    def test_delete_workspaces_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete-workspaces command with basic arguments."""
        monkeypatch.setattr(
            "sys.argv",
            ["onboard admin", "delete-workspaces", "--before", "2024-01-01"],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_workspaces_before_date",
            return_value=0,
        ) as mock_delete:
            exit_code = main()

            assert exit_code == 0
            mock_delete.assert_called_once_with(
                before_date="2024-01-01",
                orphan=False,
                auto_orphan_on_failure=True,
                dry_run=False,
            )

    def test_delete_workspaces_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete-workspaces with --dry-run flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2024-01-01",
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
                before_date="2024-01-01",
                orphan=False,
                auto_orphan_on_failure=True,
                dry_run=True,
            )

    def test_delete_workspaces_orphan(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete-workspaces with --orphan flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2024-01-01",
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
                before_date="2024-01-01",
                orphan=True,
                auto_orphan_on_failure=True,
                dry_run=False,
            )

    def test_delete_workspaces_no_auto_orphan(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delete-workspaces with --no-auto-orphan flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2024-01-01",
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
                before_date="2024-01-01",
                orphan=False,
                auto_orphan_on_failure=False,
                dry_run=False,
            )

    def test_delete_workspaces_all_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete-workspaces with all flags combined."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "delete-workspaces",
                "--before",
                "2024-01-01",
                "--dry-run",
                "--orphan",
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
                before_date="2024-01-01",
                orphan=True,
                auto_orphan_on_failure=False,
                dry_run=True,
            )

    def test_delete_workspaces_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete-workspaces command with error return."""
        monkeypatch.setattr(
            "sys.argv",
            ["onboard admin", "delete-workspaces", "--before", "2024-01-01"],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.delete_workspaces_before_date",
            return_value=1,
        ):
            exit_code = main()

            assert exit_code == 1

    def test_delete_workspaces_missing_date(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test delete-workspaces without required --before argument."""
        monkeypatch.setattr("sys.argv", ["onboard admin", "delete-workspaces"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    def test_delete_workspaces_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test delete-workspaces help message."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "delete-workspaces", "--help"]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "delete-workspaces" in captured.out.lower()
        assert "--before" in captured.out
        assert "--dry-run" in captured.out
        assert "--orphan" in captured.out
        assert "--no-auto-orphan" in captured.out


class TestCreateGeminiKeysCommand:
    """Tests for create-gemini-keys command."""

    def test_create_gemini_keys_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create-gemini-keys command with basic arguments."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=False,
                skip_validation=False,
                overwrite_existing=False,
                team_names=None,
            )

    def test_create_gemini_keys_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create-gemini-keys with --dry-run flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--dry-run",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=True,
                skip_validation=False,
                overwrite_existing=False,
                team_names=None,
            )

    def test_create_gemini_keys_skip_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test create-gemini-keys with --skip-validation flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--skip-validation",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=False,
                skip_validation=True,
                overwrite_existing=False,
                team_names=None,
            )

    def test_create_gemini_keys_overwrite_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test create-gemini-keys with --overwrite-existing flag."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--overwrite-existing",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=False,
                skip_validation=False,
                overwrite_existing=True,
                team_names=None,
            )

    def test_create_gemini_keys_specific_teams(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test create-gemini-keys with --teams argument."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--teams",
                "team-a,team-b,team-c",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=False,
                skip_validation=False,
                overwrite_existing=False,
                team_names=["team-a", "team-b", "team-c"],
            )

    def test_create_gemini_keys_teams_with_spaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test create-gemini-keys with --teams having spaces."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--teams",
                "team-a, team-b , team-c",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            # Verify spaces are stripped
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=False,
                skip_validation=False,
                overwrite_existing=False,
                team_names=["team-a", "team-b", "team-c"],
            )

    def test_create_gemini_keys_all_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test create-gemini-keys with all flags combined."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
                "--dry-run",
                "--skip-validation",
                "--overwrite-existing",
                "--teams",
                "team-a,team-b",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=0,
        ) as mock_create:
            exit_code = main()

            assert exit_code == 0
            mock_create.assert_called_once_with(
                project_id="test-project",
                bootcamp_name="agent-bootcamp",
                dry_run=True,
                skip_validation=True,
                overwrite_existing=True,
                team_names=["team-a", "team-b"],
            )

    def test_create_gemini_keys_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test create-gemini-keys command with error return."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--project",
                "test-project",
                "--bootcamp",
                "agent-bootcamp",
            ],
        )

        with patch(
            "aieng_platform_onboard.admin.cli.create_gemini_keys_for_teams",
            return_value=1,
        ):
            exit_code = main()

            assert exit_code == 1

    def test_create_gemini_keys_missing_project(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test create-gemini-keys without required --project argument."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "onboard admin",
                "create-gemini-keys",
                "--bootcamp",
                "agent-bootcamp",
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    def test_create_gemini_keys_missing_bootcamp(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test create-gemini-keys without required --bootcamp argument."""
        monkeypatch.setattr(
            "sys.argv",
            ["onboard admin", "create-gemini-keys", "--project", "test-project"],
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "required" in captured.err.lower()

    def test_create_gemini_keys_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Test create-gemini-keys help message."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "create-gemini-keys", "--help"]
        )

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "create-gemini-keys" in captured.out.lower()
        assert "--project" in captured.out
        assert "--bootcamp" in captured.out
        assert "--dry-run" in captured.out
        assert "--skip-validation" in captured.out
        assert "--overwrite-existing" in captured.out
        assert "--teams" in captured.out


class TestMainEntryPoint:
    """Tests for main entry point behavior."""

    def test_main_as_script(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that main can be called as a script."""
        monkeypatch.setattr(
            "sys.argv", ["onboard admin", "create-gemini-keys", "--help"]
        )

        with pytest.raises(SystemExit) as exc_info:
            # Simulate running as __main__
            sys.exit(main())

        # Should exit with 0 for help
        assert exc_info.value.code == 0
