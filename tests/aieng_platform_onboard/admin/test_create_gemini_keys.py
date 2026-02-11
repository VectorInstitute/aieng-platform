"""Unit tests for admin create_gemini_keys module."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
import requests

from aieng_platform_onboard.admin.create_gemini_keys import (
    APIKeyCreationError,
    PrerequisiteError,
    create_gemini_api_key,
    create_gemini_keys_for_teams,
    display_results_summary,
    get_api_key_string,
    get_teams_to_process,
    should_process_team,
    update_team_with_key,
    validate_gemini_api_key,
    validate_prerequisites,
)


class TestValidatePrerequisites:
    """Tests for validate_prerequisites function."""

    @patch("subprocess.run")
    def test_validate_prerequisites_success(self, mock_run: Mock) -> None:
        """Test successful prerequisites validation."""
        # Mock all subprocess calls
        mock_run.side_effect = [
            # gcloud version
            Mock(returncode=0, stdout="Google Cloud SDK 450.0.0\n"),
            # gcloud projects describe
            Mock(returncode=0, stdout='{"projectId": "test-project"}\n'),
            # gcloud services list (API Keys)
            Mock(returncode=0, stdout='[{"name": "apikeys.googleapis.com"}]\n'),
            # gcloud services list (Generative Language)
            Mock(
                returncode=0, stdout='[{"name": "generativelanguage.googleapis.com"}]\n'
            ),
        ]

        # Should not raise any exception
        validate_prerequisites("test-project")

        assert mock_run.call_count == 4

    @patch("subprocess.run")
    def test_validate_prerequisites_gcloud_not_installed(self, mock_run: Mock) -> None:
        """Test prerequisites check when gcloud is not installed."""
        mock_run.side_effect = FileNotFoundError("gcloud not found")

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites("test-project")

        assert "gcloud CLI is not installed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_prerequisites_project_not_accessible(
        self, mock_run: Mock
    ) -> None:
        """Test prerequisites check when project is not accessible."""
        mock_run.side_effect = [
            # gcloud version succeeds
            Mock(returncode=0, stdout="Google Cloud SDK 450.0.0\n"),
            # gcloud projects describe fails
            subprocess.CalledProcessError(
                1,
                ["gcloud", "projects", "describe"],
                stderr="ERROR: Project not found",
            ),
        ]

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites("test-project")

        assert "Cannot access GCP project" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_prerequisites_api_keys_service_not_enabled(
        self, mock_run: Mock
    ) -> None:
        """Test prerequisites check when API Keys service is not enabled."""
        mock_run.side_effect = [
            # gcloud version
            Mock(returncode=0, stdout="Google Cloud SDK 450.0.0\n"),
            # gcloud projects describe
            Mock(returncode=0, stdout='{"projectId": "test-project"}\n'),
            # gcloud services list (API Keys) - empty list
            Mock(returncode=0, stdout="[]\n"),
        ]

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites("test-project")

        assert "API Keys service is not enabled" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_prerequisites_generative_language_not_enabled(
        self, mock_run: Mock
    ) -> None:
        """Test prerequisites check when Generative Language API is not enabled."""
        mock_run.side_effect = [
            # gcloud version
            Mock(returncode=0, stdout="Google Cloud SDK 450.0.0\n"),
            # gcloud projects describe
            Mock(returncode=0, stdout='{"projectId": "test-project"}\n'),
            # gcloud services list (API Keys)
            Mock(returncode=0, stdout='[{"name": "apikeys.googleapis.com"}]\n'),
            # gcloud services list (Generative Language) - empty list
            Mock(returncode=0, stdout="[]\n"),
        ]

        with pytest.raises(PrerequisiteError) as exc_info:
            validate_prerequisites("test-project")

        assert "Generative Language API is not enabled" in str(exc_info.value)


class TestCreateGeminiApiKey:
    """Tests for create_gemini_api_key function."""

    @patch("subprocess.run")
    def test_create_gemini_api_key_success(self, mock_run: Mock) -> None:
        """Test successful API key creation."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(
                {"name": "projects/test-project/locations/global/keys/test-key"}
            ),
        )

        result = create_gemini_api_key("test-project", "bootcamp-1", "team-1")

        assert result == "projects/test-project/locations/global/keys/test-key"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_create_gemini_api_key_dry_run(self, mock_run: Mock) -> None:
        """Test API key creation in dry-run mode."""
        result = create_gemini_api_key(
            "test-project", "bootcamp-1", "team-1", dry_run=True
        )

        assert result is None
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_create_gemini_api_key_already_exists(self, mock_run: Mock) -> None:
        """Test API key creation when key already exists."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1,
            ["gcloud", "alpha", "services", "api-keys", "create"],
            stderr="ERROR: Key already exists (ALREADY_EXISTS)",
        )

        with pytest.raises(APIKeyCreationError) as exc_info:
            create_gemini_api_key("test-project", "bootcamp-1", "team-1")

        assert "already exists" in str(exc_info.value)

    @patch("subprocess.run")
    def test_create_gemini_api_key_permission_denied(self, mock_run: Mock) -> None:
        """Test API key creation with permission denied."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1,
            ["gcloud", "alpha", "services", "api-keys", "create"],
            stderr="ERROR: Permission denied (PERMISSION_DENIED)",
        )

        with pytest.raises(APIKeyCreationError) as exc_info:
            create_gemini_api_key("test-project", "bootcamp-1", "team-1")

        assert "Permission denied" in str(exc_info.value)

    @patch("subprocess.run")
    def test_create_gemini_api_key_quota_exceeded(self, mock_run: Mock) -> None:
        """Test API key creation with quota exceeded."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1,
            ["gcloud", "alpha", "services", "api-keys", "create"],
            stderr="ERROR: Quota exceeded (QUOTA_EXCEEDED)",
        )

        with pytest.raises(APIKeyCreationError) as exc_info:
            create_gemini_api_key("test-project", "bootcamp-1", "team-1")

        assert "Quota exceeded" in str(exc_info.value)


class TestGetApiKeyString:
    """Tests for get_api_key_string function."""

    @patch("subprocess.run")
    def test_get_api_key_string_success(self, mock_run: Mock) -> None:
        """Test successful API key string retrieval."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="AIzaSyABC123def456GHI789jkl012MNO345pqr\n",
        )

        result = get_api_key_string(
            "projects/test-project/locations/global/keys/test-key"
        )

        assert result == "AIzaSyABC123def456GHI789jkl012MNO345pqr"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_api_key_string_dry_run(self, mock_run: Mock) -> None:
        """Test API key string retrieval in dry-run mode."""
        result = get_api_key_string(
            "projects/test-project/locations/global/keys/test-key", dry_run=True
        )

        assert result == "AIza-dry-run-key-string"
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_get_api_key_string_empty(self, mock_run: Mock) -> None:
        """Test API key string retrieval with empty result."""
        mock_run.return_value = Mock(returncode=0, stdout="\n")

        with pytest.raises(APIKeyCreationError) as exc_info:
            get_api_key_string("projects/test-project/locations/global/keys/test-key")

        assert "Failed to retrieve key string" in str(exc_info.value)

    @patch("subprocess.run")
    def test_get_api_key_string_failure(self, mock_run: Mock) -> None:
        """Test API key string retrieval failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1,
            ["gcloud", "alpha", "services", "api-keys", "get-key-string"],
            stderr="ERROR: Key not found",
        )

        with pytest.raises(APIKeyCreationError) as exc_info:
            get_api_key_string("projects/test-project/locations/global/keys/test-key")

        assert "Failed to retrieve key string" in str(exc_info.value)


class TestValidateGeminiApiKey:
    """Tests for validate_gemini_api_key function."""

    @patch("requests.get")
    def test_validate_gemini_api_key_success(self, mock_get: Mock) -> None:
        """Test successful API key validation."""
        mock_get.return_value = Mock(status_code=200)

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is True
        assert status == "Valid"
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_validate_gemini_api_key_skip_validation(self, mock_get: Mock) -> None:
        """Test API key validation with skip_validation flag."""
        is_valid, status = validate_gemini_api_key("AIzaTest123", skip_validation=True)

        assert is_valid is True
        assert status == "Validation skipped"
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_validate_gemini_api_key_dry_run(self, mock_get: Mock) -> None:
        """Test API key validation in dry-run mode."""
        is_valid, status = validate_gemini_api_key("AIzaTest123", dry_run=True)

        assert is_valid is True
        assert status == "Validation skipped"
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_validate_gemini_api_key_permission_denied(self, mock_get: Mock) -> None:
        """Test API key validation with permission denied."""
        mock_get.return_value = Mock(status_code=403)

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is False
        assert "Permission denied" in status

    @patch("requests.get")
    def test_validate_gemini_api_key_invalid_key(self, mock_get: Mock) -> None:
        """Test API key validation with invalid key."""
        mock_get.return_value = Mock(status_code=400)

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is False
        assert "Invalid key" in status

    @patch("requests.get")
    @patch("time.sleep")
    def test_validate_gemini_api_key_retry_on_500(
        self, mock_sleep: Mock, mock_get: Mock
    ) -> None:
        """Test API key validation with retry on HTTP 500."""
        mock_get.side_effect = [
            Mock(status_code=500),
            Mock(status_code=500),
            Mock(status_code=200),
        ]

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is True
        assert status == "Valid"
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("requests.get")
    @patch("time.sleep")
    def test_validate_gemini_api_key_timeout(
        self, mock_sleep: Mock, mock_get: Mock
    ) -> None:
        """Test API key validation with timeout."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is False
        assert "Timeout" in status
        assert mock_get.call_count == 3

    @patch("requests.get")
    @patch("time.sleep")
    def test_validate_gemini_api_key_network_error(
        self, mock_sleep: Mock, mock_get: Mock
    ) -> None:
        """Test API key validation with network error."""
        mock_get.side_effect = requests.RequestException("Network error")

        is_valid, status = validate_gemini_api_key("AIzaTest123")

        assert is_valid is False
        assert "Network error" in status
        assert mock_get.call_count == 3


class TestUpdateTeamWithKey:
    """Tests for update_team_with_key function."""

    def test_update_team_with_key_success(self) -> None:
        """Test successful team update."""
        mock_db = Mock()
        mock_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_ref

        update_team_with_key(
            mock_db,
            "team-1",
            "AIzaTest123",
            "test-project",
            "Valid",
        )

        mock_db.collection.assert_called_once_with("teams")
        mock_db.collection.return_value.document.assert_called_once_with("team-1")
        mock_ref.update.assert_called_once()

        # Check update data
        update_call = mock_ref.update.call_args
        update_data = update_call[0][0]
        assert update_data["openai_api_key"] == "AIzaTest123"
        assert update_data["openai_api_key_project"] == "test-project"
        assert update_data["openai_api_key_validation_status"] == "Valid"

    def test_update_team_with_key_dry_run(self) -> None:
        """Test team update in dry-run mode."""
        mock_db = Mock()

        update_team_with_key(
            mock_db,
            "team-1",
            "AIzaTest123",
            "test-project",
            "Valid",
            dry_run=True,
        )

        mock_db.collection.assert_not_called()

    def test_update_team_with_key_failure(self) -> None:
        """Test team update failure."""
        mock_db = Mock()
        mock_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_ref
        mock_ref.update.side_effect = Exception("Firestore error")

        with pytest.raises(Exception) as exc_info:
            update_team_with_key(
                mock_db,
                "team-1",
                "AIzaTest123",
                "test-project",
                "Valid",
            )

        assert "Failed to update team" in str(exc_info.value)


class TestShouldProcessTeam:
    """Tests for should_process_team function."""

    def test_should_process_team_no_key(self) -> None:
        """Test should process team when it has no key."""
        team_data = {"team_name": "team-1"}

        should_process, reason = should_process_team(team_data)

        assert should_process is True
        assert reason == "No key"

    def test_should_process_team_has_key_no_overwrite(self) -> None:
        """Test should not process team when it has a key and no overwrite."""
        team_data = {"team_name": "team-1", "openai_api_key": "AIzaTest123"}

        should_process, reason = should_process_team(
            team_data, overwrite_existing=False
        )

        assert should_process is False
        assert reason == "Already has key"

    def test_should_process_team_has_key_with_overwrite(self) -> None:
        """Test should process team when it has a key and overwrite is enabled."""
        team_data = {"team_name": "team-1", "openai_api_key": "AIzaTest123"}

        should_process, reason = should_process_team(team_data, overwrite_existing=True)

        assert should_process is True
        assert reason == "Overwriting existing key"


class TestGetTeamsToProcess:
    """Tests for get_teams_to_process function."""

    def test_get_teams_to_process_all_teams(self) -> None:
        """Test getting all teams."""
        mock_db = Mock()
        mock_doc1 = Mock()
        mock_doc1.id = "team-1"
        mock_doc1.to_dict.return_value = {"team_name": "team-1"}
        mock_doc2 = Mock()
        mock_doc2.id = "team-2"
        mock_doc2.to_dict.return_value = {"team_name": "team-2"}

        mock_db.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

        teams = get_teams_to_process(mock_db)

        assert len(teams) == 2
        assert teams[0]["id"] == "team-1"
        assert teams[1]["id"] == "team-2"

    def test_get_teams_to_process_specific_teams(self) -> None:
        """Test getting specific teams."""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.id = "team-1"
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"team_name": "team-1"}

        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        teams = get_teams_to_process(mock_db, team_names=["team-1"])

        assert len(teams) == 1
        assert teams[0]["id"] == "team-1"

    def test_get_teams_to_process_team_not_found(self) -> None:
        """Test getting teams when a team is not found."""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.exists = False

        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        teams = get_teams_to_process(mock_db, team_names=["non-existent"])

        assert len(teams) == 0


class TestDisplayResultsSummary:
    """Tests for display_results_summary function."""

    def test_display_results_summary_success(self) -> None:
        """Test displaying results summary with successes."""
        results = {
            "success": [
                {"team": "team-1", "key": "AIza...", "status": "Valid"},
            ],
            "skipped": [],
            "failed": [],
        }

        # Should not raise any exception
        display_results_summary(results)

    def test_display_results_summary_mixed(self) -> None:
        """Test displaying results summary with mixed results."""
        results = {
            "success": [
                {"team": "team-1", "key": "AIza...", "status": "Valid"},
            ],
            "skipped": [
                {"team": "team-2", "reason": "Already has key"},
            ],
            "failed": [
                {"team": "team-3", "error": "Permission denied"},
            ],
        }

        # Should not raise any exception
        display_results_summary(results)

    def test_display_results_summary_dry_run(self) -> None:
        """Test displaying results summary in dry-run mode."""
        results = {
            "success": [
                {"team": "team-1", "key": "dry-run", "status": "Dry run"},
            ],
            "skipped": [],
            "failed": [],
        }

        # Should not raise any exception
        display_results_summary(results, dry_run=True)


class TestCreateGeminiKeysForTeams:
    """Tests for create_gemini_keys_for_teams function."""

    @patch("aieng_platform_onboard.admin.create_gemini_keys.get_firestore_client")
    @patch("aieng_platform_onboard.admin.create_gemini_keys.validate_prerequisites")
    @patch("aieng_platform_onboard.admin.create_gemini_keys.get_teams_to_process")
    def test_create_gemini_keys_for_teams_dry_run(
        self,
        mock_get_teams: Mock,
        mock_validate: Mock,
        mock_get_db: Mock,
    ) -> None:
        """Test creating keys in dry-run mode."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        mock_team = {"id": "team-1", "team_name": "team-1"}
        mock_get_teams.return_value = [mock_team]

        exit_code = create_gemini_keys_for_teams(
            project_id="test-project",
            bootcamp_name="test-bootcamp",
            dry_run=True,
        )

        assert exit_code == 0
        mock_validate.assert_called_once_with("test-project")
        mock_get_teams.assert_called_once()

    @patch("aieng_platform_onboard.admin.create_gemini_keys.get_firestore_client")
    @patch("aieng_platform_onboard.admin.create_gemini_keys.validate_prerequisites")
    @patch("aieng_platform_onboard.admin.create_gemini_keys.get_teams_to_process")
    def test_create_gemini_keys_for_teams_no_teams(
        self,
        mock_get_teams: Mock,
        mock_validate: Mock,
        mock_get_db: Mock,
    ) -> None:
        """Test creating keys when no teams are found."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_get_teams.return_value = []

        exit_code = create_gemini_keys_for_teams(
            project_id="test-project",
            bootcamp_name="test-bootcamp",
        )

        assert exit_code == 0

    @patch("aieng_platform_onboard.admin.create_gemini_keys.validate_prerequisites")
    def test_create_gemini_keys_for_teams_invalid_bootcamp_name(
        self,
        mock_validate: Mock,
    ) -> None:
        """Test creating keys with invalid bootcamp name."""
        exit_code = create_gemini_keys_for_teams(
            project_id="test-project",
            bootcamp_name="invalid@name",
        )

        assert exit_code == 1
        mock_validate.assert_not_called()

    @patch("aieng_platform_onboard.admin.create_gemini_keys.validate_prerequisites")
    def test_create_gemini_keys_for_teams_prerequisite_failure(
        self,
        mock_validate: Mock,
    ) -> None:
        """Test creating keys when prerequisites fail."""
        mock_validate.side_effect = PrerequisiteError("gcloud not found")

        exit_code = create_gemini_keys_for_teams(
            project_id="test-project",
            bootcamp_name="test-bootcamp",
        )

        assert exit_code == 1
