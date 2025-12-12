"""Unit tests for admin setup_participants module."""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from aieng_platform_onboard.admin.setup_participants import (
    create_or_update_participants,
    create_or_update_teams,
    display_summary_table,
    group_participants_by_team,
    setup_participants_from_csv,
    validate_csv_data,
)


class TestValidateCSVData:
    """Tests for validate_csv_data function."""

    def test_validate_csv_data_valid(self) -> None:
        """Test validation with valid CSV data."""
        csv_data = """github_handle,team_name,email
user1,team-a,user1@example.com
user2,team-b,user2@example.com"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_csv_data_missing_required_columns(self) -> None:
        """Test validation with missing required columns."""
        csv_data = """github_handle,email
user1,user1@example.com"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Missing required columns" in error for error in errors)

    def test_validate_csv_data_invalid_github_handle(self) -> None:
        """Test validation with invalid GitHub handle."""
        csv_data = """github_handle,team_name
-invalid,team-a"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Invalid github_handle" in error for error in errors)

    def test_validate_csv_data_invalid_team_name(self) -> None:
        """Test validation with invalid team name."""
        csv_data = """github_handle,team_name
user1,team@invalid"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Invalid team_name" in error for error in errors)

    def test_validate_csv_data_invalid_email(self) -> None:
        """Test validation with invalid email."""
        csv_data = """github_handle,team_name,email
user1,team-a,invalid-email"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Invalid email" in error for error in errors)

    def test_validate_csv_data_duplicate_handles(self) -> None:
        """Test validation with duplicate GitHub handles."""
        csv_data = """github_handle,team_name
user1,team-a
user1,team-b"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Duplicate github_handles" in error for error in errors)

    def test_validate_csv_data_optional_fields(self) -> None:
        """Test validation with optional fields."""
        csv_data = """github_handle,team_name,email,first_name,last_name
user1,team-a,user1@example.com,John,Doe
user2,team-b,,,"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_csv_data_extra_columns(self) -> None:
        """Test validation with extra columns (should warn but pass)."""
        csv_data = """github_handle,team_name,extra_column
user1,team-a,extra_value"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is True
        assert len(errors) == 0


class TestGroupParticipantsByTeam:
    """Tests for group_participants_by_team function."""

    def test_group_participants_by_team(self) -> None:
        """Test grouping participants by team."""
        csv_data = """github_handle,team_name,email,first_name,last_name
user1,team-a,user1@example.com,John,Doe
user2,team-a,user2@example.com,Jane,Smith
user3,team-b,user3@example.com,Bob,Johnson"""
        df = pd.read_csv(StringIO(csv_data))

        teams_data = group_participants_by_team(df)

        assert len(teams_data) == 2
        assert "team-a" in teams_data
        assert "team-b" in teams_data
        assert len(teams_data["team-a"]) == 2
        assert len(teams_data["team-b"]) == 1
        assert teams_data["team-a"][0]["github_handle"] == "user1"
        assert teams_data["team-a"][0]["email"] == "user1@example.com"
        assert teams_data["team-a"][0]["first_name"] == "John"
        assert teams_data["team-a"][0]["last_name"] == "Doe"

    def test_group_participants_normalizes_handles(self) -> None:
        """Test that GitHub handles are normalized to lowercase."""
        csv_data = """github_handle,team_name
User1,team-a
USER2,team-a"""
        df = pd.read_csv(StringIO(csv_data))

        teams_data = group_participants_by_team(df)

        assert teams_data["team-a"][0]["github_handle"] == "user1"
        assert teams_data["team-a"][1]["github_handle"] == "user2"


class TestCreateOrUpdateTeams:
    """Tests for create_or_update_teams function."""

    def test_create_teams(self, mock_firestore_client: Mock) -> None:
        """Test creating new teams."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
                {"github_handle": "user2", "email": "user2@example.com"},
            ],
        }

        # Mock get_team_by_name to return None (team doesn't exist)
        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
            return_value=None,
        ):
            # Mock collection and document
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            team_ids = create_or_update_teams(
                mock_firestore_client, teams_data, dry_run=False
            )

            assert "team-a" in team_ids
            assert team_ids["team-a"] == "team-a"
            mock_doc_ref.set.assert_called_once()

    def test_update_existing_teams(self, mock_firestore_client: Mock) -> None:
        """Test updating existing teams."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
            ],
        }

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": ["old-user"],
        }

        # Mock get_team_by_name to return existing team
        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
            return_value=existing_team,
        ):
            # Mock collection and document
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            team_ids = create_or_update_teams(
                mock_firestore_client, teams_data, dry_run=False
            )

            assert "team-a" in team_ids
            mock_doc_ref.update.assert_called_once()

    def test_create_teams_dry_run(self, mock_firestore_client: Mock) -> None:
        """Test creating teams in dry run mode."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
            ],
        }

        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
            return_value=None,
        ):
            team_ids = create_or_update_teams(
                mock_firestore_client, teams_data, dry_run=True
            )

            assert "team-a" in team_ids
            assert team_ids["team-a"] == "dry-run-team-a"
            # Verify no actual Firestore operations were called
            mock_firestore_client.collection.assert_not_called()


class TestCreateOrUpdateParticipants:
    """Tests for create_or_update_participants function."""

    def test_create_participants(self, mock_firestore_client: Mock) -> None:
        """Test creating new participants."""
        teams_data = {
            "team-a": [
                {
                    "github_handle": "user1",
                    "email": "user1@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                },
            ],
        }

        # Mock team existence check
        mock_team_doc = Mock()
        mock_team_doc.exists = True
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        # Mock participant lookup (doesn't exist)
        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_participant_by_handle",
            return_value=None,
        ):
            # Mock collection and document
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.side_effect = [mock_team_ref, mock_doc_ref]
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = create_or_update_participants(
                mock_firestore_client, teams_data, dry_run=False
            )

            assert success_count == 1
            assert failed_count == 0
            mock_doc_ref.set.assert_called_once()

    def test_update_existing_participants(self, mock_firestore_client: Mock) -> None:
        """Test updating existing participants."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
            ],
        }

        existing_participant = {
            "github_handle": "user1",
            "team_name": "old-team",
            "onboarded": False,
        }

        # Mock team existence check
        mock_team_doc = Mock()
        mock_team_doc.exists = True
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_participant_by_handle",
            return_value=existing_participant,
        ):
            # Mock collection and document
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.side_effect = [mock_team_ref, mock_doc_ref]
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = create_or_update_participants(
                mock_firestore_client, teams_data, dry_run=False
            )

            assert success_count == 1
            assert failed_count == 0
            mock_doc_ref.update.assert_called_once()

    def test_skip_participants_when_team_not_found(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test skipping participants when team doesn't exist."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
            ],
        }

        # Mock team existence check (team doesn't exist)
        mock_team_doc = Mock()
        mock_team_doc.exists = False
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_team_ref
        mock_firestore_client.collection.return_value = mock_collection

        success_count, failed_count = create_or_update_participants(
            mock_firestore_client, teams_data, dry_run=False
        )

        assert success_count == 0
        assert failed_count == 1

    def test_create_participants_with_team_check_error(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test handling error when checking if team exists."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
            ],
        }

        # Mock team ref that raises error on get()
        mock_team_ref = Mock()
        mock_team_ref.get.side_effect = Exception("Firestore error")

        mock_collection = Mock()
        mock_collection.document.return_value = mock_team_ref
        mock_firestore_client.collection.return_value = mock_collection

        success_count, failed_count = create_or_update_participants(
            mock_firestore_client, teams_data, dry_run=False
        )

        assert success_count == 0
        assert failed_count == 1


class TestDisplaySummaryTable:
    """Tests for display_summary_table function."""

    def test_display_summary_table(self) -> None:
        """Test displaying summary table."""
        teams_data = {
            "team-a": [
                {"github_handle": "user1", "email": "user1@example.com"},
                {"github_handle": "user2", "email": "user2@example.com"},
            ],
            "team-b": [
                {"github_handle": "user3", "email": "user3@example.com"},
            ],
        }

        # Should not raise any exceptions
        display_summary_table(teams_data)


class TestSetupParticipantsFromCSV:
    """Tests for setup_participants_from_csv function."""

    def test_setup_participants_csv_not_found(self) -> None:
        """Test when CSV file doesn't exist."""
        exit_code = setup_participants_from_csv("nonexistent.csv")

        assert exit_code == 1

    def test_setup_participants_invalid_csv(self, tmp_path: Path) -> None:
        """Test with invalid CSV data."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("github_handle,team_name\n-invalid,team@bad")

        exit_code = setup_participants_from_csv(str(csv_file))

        assert exit_code == 1

    def test_setup_participants_success(
        self, tmp_path: Path, mock_firestore_client: Mock
    ) -> None:
        """Test successful participant setup."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        # Mock team existence check
        mock_team_doc = Mock()
        mock_team_doc.exists = True
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        with (
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
                return_value=None,
            ),
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_participant_by_handle",
                return_value=None,
            ),
        ):
            # Mock collection and document
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.side_effect = [
                mock_doc_ref,  # For team creation
                mock_team_ref,  # For team existence check
                mock_doc_ref,  # For participant creation
            ]
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = setup_participants_from_csv(str(csv_file), dry_run=False)

            assert exit_code == 0

    def test_setup_participants_dry_run(
        self, tmp_path: Path, mock_firestore_client: Mock
    ) -> None:
        """Test dry run mode."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        # Mock team existence check
        mock_team_doc = Mock()
        mock_team_doc.exists = True
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        with (
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
                return_value=None,
            ),
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_participant_by_handle",
                return_value=None,
            ),
        ):
            # Mock collection and document for team existence check
            mock_collection = Mock()
            mock_collection.document.return_value = mock_team_ref
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = setup_participants_from_csv(str(csv_file), dry_run=True)

            assert exit_code == 0

    def test_setup_participants_firestore_connection_error(
        self, tmp_path: Path
    ) -> None:
        """Test Firestore connection failure."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        with patch(
            "aieng_platform_onboard.admin.setup_participants.get_firestore_client",
            side_effect=Exception("Connection failed"),
        ):
            exit_code = setup_participants_from_csv(str(csv_file))

            assert exit_code == 1

    def test_setup_participants_csv_read_error(self, tmp_path: Path) -> None:
        """Test CSV read error."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("invalid,csv,data\nwith,bad,structure\n")

        # Create malformed CSV that pandas can't parse properly
        with patch(
            "aieng_platform_onboard.admin.setup_participants.pd.read_csv",
            side_effect=Exception("CSV parse error"),
        ):
            exit_code = setup_participants_from_csv(str(csv_file))

            assert exit_code == 1

    def test_setup_participants_with_failures(
        self, tmp_path: Path, mock_firestore_client: Mock
    ) -> None:
        """Test setup with some failed participants."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text(
            "github_handle,team_name,email\nuser1,team-a,user1@example.com"
        )

        # Mock team existence check - team doesn't exist
        mock_team_doc = Mock()
        mock_team_doc.exists = False
        mock_team_ref = Mock()
        mock_team_ref.get.return_value = mock_team_doc

        with (
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.setup_participants.get_team_by_name",
                return_value=None,
            ),
        ):
            # Mock collection and document for team existence check
            mock_collection = Mock()
            mock_collection.document.return_value = mock_team_ref
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = setup_participants_from_csv(str(csv_file), dry_run=False)

            # Should fail because team doesn't exist
            assert exit_code == 1
