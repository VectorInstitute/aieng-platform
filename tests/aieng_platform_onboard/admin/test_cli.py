"""Unit tests for admin CLI module."""

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
