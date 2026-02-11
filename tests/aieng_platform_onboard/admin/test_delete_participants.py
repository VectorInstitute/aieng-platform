"""Unit tests for admin delete_participants module."""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from aieng_platform_onboard.admin.delete_participants import (
    delete_empty_team,
    delete_participant_from_team,
    delete_participants,
    delete_participants_from_csv,
    display_summary_table,
    validate_csv_data,
)


class TestValidateCSVData:
    """Tests for validate_csv_data function."""

    def test_validate_csv_data_valid(self) -> None:
        """Test validation with valid CSV data."""
        csv_data = """github_handle
user1
user2
user3"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_csv_data_missing_required_column(self) -> None:
        """Test validation with missing required column."""
        csv_data = """wrong_column
user1"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Missing required column" in error for error in errors)

    def test_validate_csv_data_invalid_github_handle(self) -> None:
        """Test validation with invalid GitHub handle."""
        csv_data = """github_handle
-invalid"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Invalid github_handle" in error for error in errors)

    def test_validate_csv_data_empty_github_handle(self) -> None:
        """Test validation with empty GitHub handle."""
        csv_data = """github_handle
,"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Missing github_handle" in error for error in errors)

    def test_validate_csv_data_duplicate_handles(self) -> None:
        """Test validation with duplicate GitHub handles."""
        csv_data = """github_handle
user1
user1"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is False
        assert any("Duplicate github_handles" in error for error in errors)

    def test_validate_csv_data_multiple_handles(self) -> None:
        """Test validation with multiple valid handles."""
        csv_data = """github_handle
user1
user-2
user3"""
        df = pd.read_csv(StringIO(csv_data))

        is_valid, errors = validate_csv_data(df)

        assert is_valid is True
        assert len(errors) == 0


class TestDeleteParticipantFromTeam:
    """Tests for delete_participant_from_team function."""

    def test_delete_participant_from_team_success(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test successfully removing participant from team."""
        github_handle = "user1"
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": ["user1", "user2"],
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            mock_team_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_team_ref
            mock_firestore_client.collection.return_value = mock_collection

            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=False
            )

            assert success is True
            assert team_is_empty is False
            mock_team_ref.update.assert_called_once()
            # Verify updated participants list doesn't contain user1
            call_args = mock_team_ref.update.call_args[0][0]
            assert "user1" not in call_args["participants"]
            assert "user2" in call_args["participants"]

    def test_delete_participant_from_team_results_in_empty_team(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test removing last participant makes team empty."""
        github_handle = "user1"
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": ["user1"],  # Only one participant
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            mock_team_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_team_ref
            mock_firestore_client.collection.return_value = mock_collection

            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=False
            )

            assert success is True
            assert team_is_empty is True
            mock_team_ref.update.assert_called_once()

    def test_delete_participant_from_team_not_in_participants_list(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test removing participant not in team's participants list."""
        github_handle = "user3"
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": ["user1", "user2"],
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=False
            )

            assert success is True
            assert team_is_empty is False
            # Should not call update since participant not in list
            mock_firestore_client.collection.assert_not_called()

    def test_delete_participant_from_team_team_not_found(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test removing participant when team doesn't exist."""
        github_handle = "user1"
        team_name = "nonexistent-team"

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=None,
        ):
            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=False
            )

            assert success is True
            assert team_is_empty is False

    def test_delete_participant_from_team_dry_run(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test dry run mode doesn't modify team."""
        github_handle = "user1"
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": ["user1", "user2"],
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=True
            )

            assert success is True
            assert team_is_empty is False
            # Should not call any Firestore operations in dry-run
            mock_firestore_client.collection.assert_not_called()

    def test_delete_participant_from_team_error(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test error handling when deletion fails."""
        github_handle = "user1"
        team_name = "team-a"

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            side_effect=Exception("Firestore error"),
        ):
            success, team_is_empty = delete_participant_from_team(
                mock_firestore_client, github_handle, team_name, dry_run=False
            )

            assert success is False
            assert team_is_empty is False


class TestDeleteEmptyTeam:
    """Tests for delete_empty_team function."""

    def test_delete_empty_team_success(self, mock_firestore_client: Mock) -> None:
        """Test successfully deleting empty team."""
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": [],
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            mock_team_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_team_ref
            mock_firestore_client.collection.return_value = mock_collection

            success = delete_empty_team(mock_firestore_client, team_name, dry_run=False)

            assert success is True
            mock_team_ref.delete.assert_called_once()

    def test_delete_empty_team_not_found(self, mock_firestore_client: Mock) -> None:
        """Test deleting team that doesn't exist."""
        team_name = "nonexistent-team"

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=None,
        ):
            success = delete_empty_team(mock_firestore_client, team_name, dry_run=False)

            assert success is True

    def test_delete_empty_team_dry_run(self, mock_firestore_client: Mock) -> None:
        """Test dry run mode doesn't delete team."""
        team_name = "team-a"

        existing_team = {
            "id": "team-a",
            "team_name": "team-a",
            "participants": [],
        }

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            return_value=existing_team,
        ):
            success = delete_empty_team(mock_firestore_client, team_name, dry_run=True)

            assert success is True
            # Should not call any Firestore operations in dry-run
            mock_firestore_client.collection.assert_not_called()

    def test_delete_empty_team_error(self, mock_firestore_client: Mock) -> None:
        """Test error handling when deletion fails."""
        team_name = "team-a"

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
            side_effect=Exception("Firestore error"),
        ):
            success = delete_empty_team(mock_firestore_client, team_name, dry_run=False)

            assert success is False


class TestDeleteParticipants:
    """Tests for delete_participants function."""

    def test_delete_participants_success(self, mock_firestore_client: Mock) -> None:
        """Test successfully deleting participants."""
        github_handles = ["user1", "user2"]

        # Mock participant lookups
        def mock_get_participant(db: Mock, handle: str) -> dict | None:
            if handle == "user1":
                return {
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                }
            if handle == "user2":
                return {
                    "github_handle": "user2",
                    "team_name": "team-b",
                    "onboarded": False,
                }
            return None

        # Mock team lookup
        def mock_get_team(db: Mock, team_name: str) -> dict | None:
            return {
                "id": team_name,
                "team_name": team_name,
                "participants": ["user1", "user2"],
            }

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                side_effect=mock_get_participant,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                side_effect=mock_get_team,
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=False,
                dry_run=False,
            )

            assert success_count == 2
            assert failed_count == 0
            # Should be called twice (once per participant)
            assert mock_doc_ref.delete.call_count == 2

    def test_delete_participants_with_empty_team_cleanup(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test deleting participants with empty team cleanup."""
        github_handles = ["user1"]

        # Mock participant lookup
        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                return_value={
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                },
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1"],  # Only one participant
                },
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=True,
                dry_run=False,
            )

            assert success_count == 1
            assert failed_count == 0
            # Should delete participant and team (2 deletes total)
            assert mock_doc_ref.delete.call_count == 2

    def test_delete_participants_not_found(self, mock_firestore_client: Mock) -> None:
        """Test deleting participants that don't exist."""
        github_handles = ["nonexistent-user"]

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
            return_value=None,
        ):
            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=False,
                dry_run=False,
            )

            assert success_count == 1  # Counted as success (already deleted)
            assert failed_count == 0

    def test_delete_participants_dry_run(self, mock_firestore_client: Mock) -> None:
        """Test dry run mode doesn't delete anything."""
        github_handles = ["user1"]

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                return_value={
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                },
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1", "user2"],
                },
            ),
        ):
            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=False,
                dry_run=True,
            )

            assert success_count == 1
            assert failed_count == 0
            # Should not call any Firestore operations in dry-run
            mock_firestore_client.collection.assert_not_called()

    def test_delete_participants_with_errors(self, mock_firestore_client: Mock) -> None:
        """Test handling errors during deletion."""
        github_handles = ["user1", "user2"]

        def mock_get_participant(_db: Mock, handle: str) -> dict | None:
            if handle == "user1":
                return {
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                }
            raise Exception("Firestore error")

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                side_effect=mock_get_participant,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1", "user2"],
                },
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=False,
                dry_run=False,
            )

            assert success_count == 1
            assert failed_count == 1

    def test_delete_participants_without_team(
        self, mock_firestore_client: Mock
    ) -> None:
        """Test deleting participant with no team assignment."""
        github_handles = ["user1"]

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
            return_value={
                "github_handle": "user1",
                "team_name": None,  # No team
                "onboarded": True,
            },
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            success_count, failed_count = delete_participants(
                mock_firestore_client,
                github_handles,
                delete_empty_teams=False,
                dry_run=False,
            )

            assert success_count == 1
            assert failed_count == 0
            # Should only delete participant (not try to update team)
            assert mock_doc_ref.delete.call_count == 1


class TestDisplaySummaryTable:
    """Tests for display_summary_table function."""

    def test_display_summary_table_few_handles(self) -> None:
        """Test displaying summary table with few handles."""
        github_handles = ["user1", "user2", "user3"]

        # Should not raise any exceptions
        display_summary_table(github_handles)

    def test_display_summary_table_many_handles(self) -> None:
        """Test displaying summary table with many handles."""
        github_handles = [f"user{i}" for i in range(20)]

        # Should not raise any exceptions (should truncate to 10 + "and X more")
        display_summary_table(github_handles)

    def test_display_summary_table_empty(self) -> None:
        """Test displaying summary table with no handles."""
        github_handles: list[str] = []

        # Should not raise any exceptions
        display_summary_table(github_handles)


class TestDeleteParticipantsFromCSV:
    """Tests for delete_participants_from_csv function."""

    def test_delete_participants_csv_not_found(self) -> None:
        """Test when CSV file doesn't exist."""
        exit_code = delete_participants_from_csv("nonexistent.csv")

        assert exit_code == 1

    def test_delete_participants_invalid_csv(self, tmp_path: Path) -> None:
        """Test with invalid CSV data."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("github_handle\n-invalid")

        exit_code = delete_participants_from_csv(str(csv_file), dry_run=True)

        assert exit_code == 1

    def test_delete_participants_csv_read_error(self, tmp_path: Path) -> None:
        """Test CSV read error."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("invalid,csv,data\n")

        with patch(
            "aieng_platform_onboard.admin.delete_participants.pd.read_csv",
            side_effect=Exception("CSV parse error"),
        ):
            exit_code = delete_participants_from_csv(str(csv_file))

            assert exit_code == 1

    def test_delete_participants_success_dry_run(
        self, tmp_path: Path, mock_firestore_client: Mock
    ) -> None:
        """Test successful dry run deletion."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1\nuser2")

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                return_value={
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                },
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1", "user2"],
                },
            ),
        ):
            exit_code = delete_participants_from_csv(str(csv_file), dry_run=True)

            assert exit_code == 0
            # Should not call any Firestore operations in dry-run
            mock_firestore_client.collection.assert_not_called()

    def test_delete_participants_user_cancels(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test user cancelling deletion."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1")

        # Mock input to return something other than "DELETE"
        monkeypatch.setattr("builtins.input", lambda: "CANCEL")

        exit_code = delete_participants_from_csv(str(csv_file), dry_run=False)

        assert exit_code == 0  # Cancelled successfully, not an error

    def test_delete_participants_success_with_confirmation(
        self,
        tmp_path: Path,
        mock_firestore_client: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successful deletion with user confirmation."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1")

        # Mock input to return "DELETE"
        monkeypatch.setattr("builtins.input", lambda: "DELETE")

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                return_value={
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                },
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1", "user2"],
                },
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = delete_participants_from_csv(
                str(csv_file), delete_empty_teams=False, dry_run=False
            )

            assert exit_code == 0
            # Should delete participant
            mock_doc_ref.delete.assert_called_once()

    def test_delete_participants_firestore_connection_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Firestore connection failure."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1")

        # Mock input to return "DELETE"
        monkeypatch.setattr("builtins.input", lambda: "DELETE")

        with patch(
            "aieng_platform_onboard.admin.delete_participants.get_firestore_client",
            side_effect=Exception("Connection failed"),
        ):
            exit_code = delete_participants_from_csv(str(csv_file))

            assert exit_code == 1

    def test_delete_participants_with_failures(
        self,
        tmp_path: Path,
        mock_firestore_client: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test deletion with some failures."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1\nuser2")

        # Mock input to return "DELETE"
        monkeypatch.setattr("builtins.input", lambda: "DELETE")

        def mock_get_participant(db: Mock, handle: str) -> dict | None:
            if handle == "user1":
                return {
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                }
            raise Exception("Firestore error")

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                side_effect=mock_get_participant,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1"],
                },
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = delete_participants_from_csv(
                str(csv_file), delete_empty_teams=False, dry_run=False
            )

            # Should fail because some participants failed
            assert exit_code == 1

    def test_delete_participants_keep_empty_teams(
        self,
        tmp_path: Path,
        mock_firestore_client: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test deletion with keep_empty_teams flag."""
        csv_file = tmp_path / "participants.csv"
        csv_file.write_text("github_handle\nuser1")

        # Mock input to return "DELETE"
        monkeypatch.setattr("builtins.input", lambda: "DELETE")

        with (
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_firestore_client",
                return_value=mock_firestore_client,
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_participant_by_handle",
                return_value={
                    "github_handle": "user1",
                    "team_name": "team-a",
                    "onboarded": True,
                },
            ),
            patch(
                "aieng_platform_onboard.admin.delete_participants.get_team_by_name",
                return_value={
                    "id": "team-a",
                    "team_name": "team-a",
                    "participants": ["user1"],  # Only participant
                },
            ),
        ):
            mock_doc_ref = Mock()
            mock_collection = Mock()
            mock_collection.document.return_value = mock_doc_ref
            mock_firestore_client.collection.return_value = mock_collection

            exit_code = delete_participants_from_csv(
                str(csv_file), delete_empty_teams=False, dry_run=False
            )

            assert exit_code == 0
            # Should only delete participant, not team
            assert mock_doc_ref.delete.call_count == 1
