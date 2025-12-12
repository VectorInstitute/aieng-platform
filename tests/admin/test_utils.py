"""Unit tests for admin utils module."""

from unittest.mock import Mock, patch

import pytest

from aieng_platform_onboard.admin.utils import (
    format_api_key_name,
    get_all_participants,
    get_all_teams,
    get_console,
    get_firestore_client,
    get_participant_by_handle,
    get_team_by_name,
    mask_sensitive_value,
    normalize_github_handle,
    validate_email,
    validate_github_handle,
    validate_team_name,
)


class TestGetConsole:
    """Tests for get_console function."""

    def test_get_console_returns_console(self) -> None:
        """Test that get_console returns a Console instance."""
        console = get_console()
        assert console is not None


class TestNormalizeGithubHandle:
    """Tests for normalize_github_handle function."""

    def test_normalize_lowercase(self) -> None:
        """Test normalizing already lowercase handle."""
        assert normalize_github_handle("user123") == "user123"

    def test_normalize_uppercase(self) -> None:
        """Test normalizing uppercase handle."""
        assert normalize_github_handle("USER123") == "user123"

    def test_normalize_mixed_case(self) -> None:
        """Test normalizing mixed case handle."""
        assert normalize_github_handle("UserName") == "username"


class TestGetFirestoreClient:
    """Tests for get_firestore_client function."""

    def test_get_firestore_client_success(self) -> None:
        """Test successful Firestore client initialization."""
        with patch(
            "aieng_platform_onboard.admin.utils.firestore.Client"
        ) as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            client = get_firestore_client()

            assert client == mock_instance
            mock_client.assert_called_once_with(
                project="coderd",
                database="onboarding",
            )

    def test_get_firestore_client_failure(self) -> None:
        """Test Firestore client initialization failure."""
        with patch(
            "aieng_platform_onboard.admin.utils.firestore.Client"
        ) as mock_client:
            mock_client.side_effect = Exception("Connection failed")

            with pytest.raises(Exception) as exc_info:
                get_firestore_client()

            assert "Failed to initialize Firestore client" in str(exc_info.value)


class TestValidateTeamName:
    """Tests for validate_team_name function."""

    def test_validate_team_name_valid(self) -> None:
        """Test valid team names."""
        assert validate_team_name("team-alpha") is True
        assert validate_team_name("team_beta") is True
        assert validate_team_name("team123") is True
        assert validate_team_name("Team-1") is True

    def test_validate_team_name_invalid(self) -> None:
        """Test invalid team names."""
        assert validate_team_name("") is False
        assert validate_team_name("team@invalid") is False
        assert validate_team_name("team name") is False
        assert validate_team_name("team!") is False

    def test_validate_team_name_none(self) -> None:
        """Test None team name."""
        assert validate_team_name(None) is False  # type: ignore[arg-type]

    def test_validate_team_name_non_string(self) -> None:
        """Test non-string team name."""
        assert validate_team_name(123) is False  # type: ignore[arg-type]


class TestValidateGithubHandle:
    """Tests for validate_github_handle function."""

    def test_validate_github_handle_valid(self) -> None:
        """Test valid GitHub handles."""
        assert validate_github_handle("user123") is True
        assert validate_github_handle("user-name") is True
        assert validate_github_handle("a") is True
        assert validate_github_handle("a" * 39) is True

    def test_validate_github_handle_invalid(self) -> None:
        """Test invalid GitHub handles."""
        assert validate_github_handle("") is False
        assert validate_github_handle("-user") is False
        assert validate_github_handle("a" * 40) is False
        assert validate_github_handle("user_name") is False
        assert validate_github_handle("user@name") is False

    def test_validate_github_handle_none(self) -> None:
        """Test None GitHub handle."""
        assert validate_github_handle(None) is False  # type: ignore[arg-type]

    def test_validate_github_handle_non_string(self) -> None:
        """Test non-string GitHub handle."""
        assert validate_github_handle(123) is False  # type: ignore[arg-type]


class TestValidateEmail:
    """Tests for validate_email function."""

    def test_validate_email_valid(self) -> None:
        """Test valid email addresses."""
        assert validate_email("user@example.com") is True
        assert validate_email("test.user@example.co.uk") is True
        assert validate_email("user+tag@example.com") is True

    def test_validate_email_invalid(self) -> None:
        """Test invalid email addresses."""
        assert validate_email("") is False
        assert validate_email("invalid") is False
        assert validate_email("invalid@") is False
        assert validate_email("user@domain") is False

    def test_validate_email_none(self) -> None:
        """Test None email."""
        assert validate_email(None) is False  # type: ignore[arg-type]

    def test_validate_email_non_string(self) -> None:
        """Test non-string email."""
        assert validate_email(123) is False  # type: ignore[arg-type]


class TestGetAllTeams:
    """Tests for get_all_teams function."""

    def test_get_all_teams_success(self) -> None:
        """Test retrieving all teams."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_doc1 = Mock()
        mock_doc1.id = "team-a"
        mock_doc1.to_dict.return_value = {
            "team_name": "team-a",
            "participants": ["user1"],
        }

        mock_doc2 = Mock()
        mock_doc2.id = "team-b"
        mock_doc2.to_dict.return_value = {
            "team_name": "team-b",
            "participants": ["user2"],
        }

        mock_collection.stream.return_value = [mock_doc1, mock_doc2]

        teams = get_all_teams(mock_db)

        assert len(teams) == 2
        assert teams[0]["id"] == "team-a"
        assert teams[0]["team_name"] == "team-a"
        assert teams[1]["id"] == "team-b"
        mock_db.collection.assert_called_once_with("teams")

    def test_get_all_teams_empty(self) -> None:
        """Test retrieving teams when none exist."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection
        mock_collection.stream.return_value = []

        teams = get_all_teams(mock_db)

        assert len(teams) == 0


class TestGetTeamByName:
    """Tests for get_team_by_name function."""

    def test_get_team_by_name_found(self) -> None:
        """Test retrieving team by name when it exists."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_query = Mock()
        mock_collection.where.return_value = mock_query

        mock_doc = Mock()
        mock_doc.id = "team-a"
        mock_doc.to_dict.return_value = {
            "team_name": "team-a",
            "participants": ["user1"],
        }
        mock_query.stream.return_value = [mock_doc]

        team = get_team_by_name(mock_db, "team-a")

        assert team is not None
        assert team["id"] == "team-a"
        assert team["team_name"] == "team-a"

    def test_get_team_by_name_not_found(self) -> None:
        """Test retrieving team by name when it doesn't exist."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_query = Mock()
        mock_collection.where.return_value = mock_query
        mock_query.stream.return_value = []

        team = get_team_by_name(mock_db, "nonexistent")

        assert team is None


class TestGetAllParticipants:
    """Tests for get_all_participants function."""

    def test_get_all_participants_success(self) -> None:
        """Test retrieving all participants."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_doc1 = Mock()
        mock_doc1.id = "user1"
        mock_doc1.to_dict.return_value = {
            "github_handle": "user1",
            "team_name": "team-a",
        }

        mock_doc2 = Mock()
        mock_doc2.id = "user2"
        mock_doc2.to_dict.return_value = {
            "github_handle": "user2",
            "team_name": "team-b",
        }

        mock_collection.stream.return_value = [mock_doc1, mock_doc2]

        participants = get_all_participants(mock_db)

        assert len(participants) == 2
        assert participants[0]["id"] == "user1"
        assert participants[0]["github_handle"] == "user1"
        assert participants[1]["id"] == "user2"
        mock_db.collection.assert_called_once_with("participants")

    def test_get_all_participants_empty(self) -> None:
        """Test retrieving participants when none exist."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection
        mock_collection.stream.return_value = []

        participants = get_all_participants(mock_db)

        assert len(participants) == 0


class TestGetParticipantByHandle:
    """Tests for get_participant_by_handle function."""

    def test_get_participant_by_handle_found(self) -> None:
        """Test retrieving participant by handle when it exists."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.id = "user1"
        mock_doc.to_dict.return_value = {
            "github_handle": "user1",
            "team_name": "team-a",
        }
        mock_doc_ref.get.return_value = mock_doc

        participant = get_participant_by_handle(mock_db, "user1")

        assert participant is not None
        assert participant["id"] == "user1"
        assert participant["github_handle"] == "user1"

    def test_get_participant_by_handle_not_found(self) -> None:
        """Test retrieving participant by handle when it doesn't exist."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        mock_doc = Mock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc

        participant = get_participant_by_handle(mock_db, "nonexistent")

        assert participant is None

    def test_get_participant_by_handle_normalizes(self) -> None:
        """Test that handle is normalized to lowercase."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.collection.return_value = mock_collection

        mock_doc_ref = Mock()
        mock_collection.document.return_value = mock_doc_ref

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.id = "user1"
        mock_doc.to_dict.return_value = {"github_handle": "user1"}
        mock_doc_ref.get.return_value = mock_doc

        get_participant_by_handle(mock_db, "USER1")

        mock_collection.document.assert_called_once_with("user1")


class TestFormatApiKeyName:
    """Tests for format_api_key_name function."""

    def test_format_api_key_name_default(self) -> None:
        """Test formatting API key name with default key type."""
        name = format_api_key_name("fall-2025", "team-alpha")
        assert name == "fall-2025-team-alpha-gemini"

    def test_format_api_key_name_custom_type(self) -> None:
        """Test formatting API key name with custom key type."""
        name = format_api_key_name("fall-2025", "team-alpha", "openai")
        assert name == "fall-2025-team-alpha-openai"


class TestMaskSensitiveValue:
    """Tests for mask_sensitive_value function."""

    def test_mask_sensitive_value_long(self) -> None:
        """Test masking long sensitive value."""
        masked = mask_sensitive_value("this-is-a-long-secret-key-value")
        assert masked == "this-is-..."

    def test_mask_sensitive_value_short(self) -> None:
        """Test masking short sensitive value."""
        masked = mask_sensitive_value("short")
        assert masked == "short"

    def test_mask_sensitive_value_exact_length(self) -> None:
        """Test masking value exactly at visible chars length."""
        masked = mask_sensitive_value("12345678")
        assert masked == "12345678"

    def test_mask_sensitive_value_empty(self) -> None:
        """Test masking empty value."""
        masked = mask_sensitive_value("")
        assert masked == "NOT SET"

    def test_mask_sensitive_value_custom_visible_chars(self) -> None:
        """Test masking with custom visible chars."""
        masked = mask_sensitive_value("this-is-a-secret", visible_chars=4)
        assert masked == "this..."
