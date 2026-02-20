"""Unit tests for aieng_platform_onboard.utils module."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from google.cloud.firestore import Client as FirestoreClient
from rich.console import Console

from aieng_platform_onboard.utils import (
    _parse_env_example,
    check_onboarded_status,
    create_env_file,
    exchange_custom_token_for_id_token,
    fetch_token_from_service,
    get_all_participants_with_status,
    get_console,
    get_github_user,
    get_global_keys,
    get_participant_data,
    get_team_data,
    initialize_firestore_admin,
    initialize_firestore_with_token,
    update_onboarded_status,
    validate_env_file,
)


class TestGetConsole:
    """Tests for get_console function."""

    def test_get_console_returns_console_instance(self) -> None:
        """Test that get_console returns a Console instance."""
        console = get_console()
        assert isinstance(console, Console)

    def test_get_console_returns_same_instance(self) -> None:
        """Test that get_console returns the same global instance."""
        console1 = get_console()
        console2 = get_console()
        assert console1 is console2


class TestGetGithubUser:
    """Tests for get_github_user function."""

    def test_get_github_user_from_github_user_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting GitHub user from GITHUB_USER environment variable."""
        monkeypatch.setenv("GITHUB_USER", "test-user")
        assert get_github_user() == "test-user"

    def test_get_github_user_from_gh_user_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting GitHub user from GH_USER environment variable."""
        monkeypatch.delenv("GITHUB_USER", raising=False)
        monkeypatch.setenv("GH_USER", "test-user-gh")
        assert get_github_user() == "test-user-gh"

    def test_get_github_user_from_user_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting GitHub user from USER environment variable."""
        monkeypatch.delenv("GITHUB_USER", raising=False)
        monkeypatch.delenv("GH_USER", raising=False)
        monkeypatch.setenv("USER", "test-user-system")
        assert get_github_user() == "test-user-system"

    def test_get_github_user_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting GitHub user when no env variable is set."""
        monkeypatch.delenv("GITHUB_USER", raising=False)
        monkeypatch.delenv("GH_USER", raising=False)
        monkeypatch.delenv("USER", raising=False)
        assert get_github_user() is None


class TestFetchTokenFromService:
    """Tests for fetch_token_from_service function."""

    def test_fetch_token_success_with_service_account(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
    ) -> None:
        """Test successful token fetch with service account credentials."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default to return service account credentials
        mock_credentials = Mock()
        mock_credentials.service_account_email = "test@example.iam.gserviceaccount.com"
        mock_credentials.signer = Mock()

        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )

        # Mock JWT encoding
        monkeypatch.setattr(
            "google.auth.jwt.encode", lambda signer, payload: "test-id-token"
        )

        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {"token": "test-token"}
        mock_requests_post.return_value.content = b'{"token": "test-token"}'

        success, token, error = fetch_token_from_service("test-user")

        assert success is True
        assert token == "test-token"
        assert error is None
        mock_requests_post.assert_called_once()

    def test_fetch_token_from_config_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
        tmp_path: Path,
    ) -> None:
        """Test token fetch reading service URL from config file."""
        monkeypatch.delenv("TOKEN_SERVICE_URL", raising=False)

        # Create config file
        config_file = tmp_path / ".token-service-url"
        config_file.write_text("https://token-service-from-file.example.com")

        # Mock Path.home() to return tmp_path
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        # Mock google.auth.default
        mock_credentials = Mock()
        mock_credentials.service_account_email = "test@example.iam.gserviceaccount.com"
        mock_credentials.signer = Mock()
        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )
        monkeypatch.setattr(
            "google.auth.jwt.encode", lambda signer, payload: "test-id-token"
        )

        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {"token": "test-token"}
        mock_requests_post.return_value.content = b'{"token": "test-token"}'

        success, token, error = fetch_token_from_service("test-user")

        assert success is True
        assert token == "test-token"
        assert error is None

    def test_fetch_token_with_user_credentials(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
    ) -> None:
        """Test token fetch with user credentials uses gcloud without --audiences flag.

        The --audiences flag is only supported for service accounts; passing it
        for user accounts causes gcloud to error. This test verifies the command
        is called as plain `gcloud auth print-identity-token`.
        """
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default to return user credentials (no signer)
        mock_credentials = Mock(spec=[])  # No signer attribute

        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )

        # Mock subprocess.run for gcloud command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "gcloud-identity-token"
        mock_result.stderr = ""

        mock_subprocess = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_subprocess)

        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {"token": "test-token"}
        mock_requests_post.return_value.content = b'{"token": "test-token"}'

        success, token, error = fetch_token_from_service("test-user")

        assert success is True
        assert token == "test-token"
        assert error is None

        # Verify exact gcloud command — no --audiences flag for user credentials
        cmd = mock_subprocess.call_args[0][0]
        assert cmd == ["gcloud", "auth", "print-identity-token"]

    def test_fetch_token_gcloud_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test token fetch when gcloud command fails."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default to return user credentials
        mock_credentials = Mock(spec=[])

        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )

        # Mock subprocess.run to fail
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "gcloud auth error"

        mock_subprocess = Mock(return_value=mock_result)
        monkeypatch.setattr("subprocess.run", mock_subprocess)

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Failed to get identity token" in str(error)

    def test_fetch_token_gcloud_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test token fetch when gcloud command raises exception."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default
        mock_credentials = Mock(spec=[])

        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )

        # Mock subprocess.run to raise exception
        def mock_subprocess_error(*args, **kwargs):
            raise Exception("subprocess error")

        monkeypatch.setattr("subprocess.run", mock_subprocess_error)

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Failed to run gcloud" in str(error)

    def test_fetch_token_no_id_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test token fetch when identity token is empty."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default
        mock_credentials = Mock(spec=[])

        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )

        # Mock subprocess.run to return empty token
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "   \n  "  # Whitespace that strips to empty
        mock_result.stderr = ""

        monkeypatch.setattr("subprocess.run", Mock(return_value=mock_result))

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Failed to get identity token for authentication" in str(error)

    def test_fetch_token_no_token_in_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
    ) -> None:
        """Test token fetch when service response has no token."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default
        mock_credentials = Mock()
        mock_credentials.service_account_email = "test@example.iam.gserviceaccount.com"
        mock_credentials.signer = Mock()
        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )
        monkeypatch.setattr(
            "google.auth.jwt.encode", lambda signer, payload: "test-id-token"
        )

        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {}  # No token
        mock_requests_post.return_value.content = b"{}"

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "No token in service response" in str(error)

    def test_fetch_token_generic_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
    ) -> None:
        """Test token fetch with generic exception."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default to raise exception
        def mock_auth_error():
            raise Exception("Auth error")

        monkeypatch.setattr("google.auth.default", mock_auth_error)

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Failed to fetch token from service" in str(error)

    def test_fetch_token_no_service_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test token fetch failure when service URL is not configured."""
        monkeypatch.delenv("TOKEN_SERVICE_URL", raising=False)
        monkeypatch.setattr("pathlib.Path.home", lambda: Path("/nonexistent"))

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Token service URL not found" in str(error)

    def test_fetch_token_service_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_requests_post: Mock,
    ) -> None:
        """Test token fetch with service error response."""
        monkeypatch.setenv("TOKEN_SERVICE_URL", "https://token-service.example.com")

        # Mock google.auth.default
        mock_credentials = Mock()
        mock_credentials.service_account_email = "test@example.iam.gserviceaccount.com"
        mock_credentials.signer = Mock()
        monkeypatch.setattr(
            "google.auth.default", lambda: (mock_credentials, "test-project")
        )
        monkeypatch.setattr(
            "google.auth.jwt.encode", lambda signer, payload: "test-id-token"
        )

        mock_requests_post.return_value.status_code = 404
        mock_requests_post.return_value.json.return_value = {"message": "Not found"}
        mock_requests_post.return_value.content = b'{"message": "Not found"}'

        success, token, error = fetch_token_from_service("test-user")

        assert success is False
        assert token is None
        assert "Token service error" in str(error)


class TestExchangeCustomTokenForIdToken:
    """Tests for exchange_custom_token_for_id_token function."""

    def test_exchange_token_success(self, mock_requests_post: Mock) -> None:
        """Test successful token exchange."""
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {"idToken": "test-id-token"}

        success, id_token, error = exchange_custom_token_for_id_token(
            "custom-token", "test-api-key"
        )

        assert success is True
        assert id_token == "test-id-token"
        assert error is None

    def test_exchange_token_firebase_error(self, mock_requests_post: Mock) -> None:
        """Test token exchange with Firebase error."""
        mock_requests_post.return_value.status_code = 400
        mock_requests_post.return_value.json.return_value = {
            "error": {"message": "Invalid token"}
        }

        success, id_token, error = exchange_custom_token_for_id_token(
            "invalid-token", "test-api-key"
        )

        assert success is False
        assert id_token is None
        assert "Invalid token" in str(error)

    def test_exchange_token_no_id_token_in_response(
        self, mock_requests_post: Mock
    ) -> None:
        """Test token exchange when response has no ID token."""
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {}  # No idToken

        success, id_token, error = exchange_custom_token_for_id_token(
            "custom-token", "test-api-key"
        )

        assert success is False
        assert id_token is None
        assert "No ID token in response" in str(error)

    def test_exchange_token_generic_exception(self, mock_requests_post: Mock) -> None:
        """Test token exchange with generic exception."""
        mock_requests_post.side_effect = Exception("Network error")

        success, id_token, error = exchange_custom_token_for_id_token(
            "custom-token", "test-api-key"
        )

        assert success is False
        assert id_token is None
        assert "Network error" in str(error)


class TestInitializeFirestoreWithToken:
    """Tests for initialize_firestore_with_token function."""

    def test_initialize_firestore_success(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test successful Firestore initialization with token."""
        monkeypatch.setenv("FIREBASE_WEB_API_KEY", "test-api-key")

        # Mock exchange function
        def mock_exchange(
            token: str, api_key: str
        ) -> tuple[bool, str | None, str | None]:
            return True, "test-id-token", None

        monkeypatch.setattr(
            "aieng_platform_onboard.utils.exchange_custom_token_for_id_token",
            mock_exchange,
        )

        # Mock Firestore client
        mock_client = Mock(spec=FirestoreClient)
        monkeypatch.setattr(
            "aieng_platform_onboard.utils.FirestoreClient", lambda **kwargs: mock_client
        )

        # Mock oauth2_credentials.Credentials
        monkeypatch.setattr(
            "google.oauth2.credentials.Credentials",
            lambda token: Mock(),
        )

        client = initialize_firestore_with_token(
            "custom-token", "test-project", "test-db", "test-api-key"
        )

        assert client is not None

    def test_initialize_firestore_no_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test Firestore initialization failure without API key."""
        monkeypatch.delenv("FIREBASE_WEB_API_KEY", raising=False)

        with pytest.raises(Exception, match="Firebase Web API key required"):
            initialize_firestore_with_token("custom-token", "test-project", "test-db")

    def test_initialize_firestore_exchange_failure(
        self, monkeypatch: pytest.MonkeyPatch, mock_console: Mock
    ) -> None:
        """Test Firestore initialization when token exchange fails."""
        monkeypatch.setenv("FIREBASE_WEB_API_KEY", "test-api-key")

        # Mock exchange function to fail
        def mock_exchange_fail(
            token: str, api_key: str
        ) -> tuple[bool, str | None, str | None]:
            return False, None, "Exchange failed"

        monkeypatch.setattr(
            "aieng_platform_onboard.utils.exchange_custom_token_for_id_token",
            mock_exchange_fail,
        )

        with pytest.raises(Exception, match="Failed to exchange custom token"):
            initialize_firestore_with_token(
                "custom-token", "test-project", "test-db", "test-api-key"
            )


class TestInitializeFirestoreAdmin:
    """Tests for initialize_firestore_admin function."""

    def test_initialize_firestore_admin_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful admin Firestore initialization."""
        mock_client = Mock(spec=FirestoreClient)
        monkeypatch.setattr(
            "aieng_platform_onboard.utils.FirestoreClient", lambda **kwargs: mock_client
        )

        client = initialize_firestore_admin()

        assert client is not None

    def test_initialize_firestore_admin_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test admin Firestore initialization failure."""

        def mock_client_error(**kwargs: Any) -> None:
            raise Exception("Connection failed")

        monkeypatch.setattr(
            "aieng_platform_onboard.utils.FirestoreClient", mock_client_error
        )

        with pytest.raises(
            Exception, match="Failed to initialize Firestore admin client"
        ):
            initialize_firestore_admin()


class TestGetParticipantData:
    """Tests for get_participant_data function."""

    def test_get_participant_data_success(
        self, mock_firestore_client: Mock, sample_participant_data: dict[str, Any]
    ) -> None:
        """Test successful participant data retrieval."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_participant_data

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_participant_data(mock_firestore_client, "test-user")

        assert result == sample_participant_data
        mock_firestore_client.collection.assert_called_once_with("participants")

    def test_get_participant_data_not_found(self, mock_firestore_client: Mock) -> None:
        """Test participant data retrieval when participant not found."""
        mock_doc = Mock()
        mock_doc.exists = False

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_participant_data(mock_firestore_client, "nonexistent-user")

        assert result is None

    def test_get_participant_data_exception(
        self, mock_firestore_client: Mock, mock_console: Mock
    ) -> None:
        """Test participant data retrieval with exception."""
        mock_firestore_client.collection.side_effect = Exception("Database error")

        result = get_participant_data(mock_firestore_client, "test-user")

        assert result is None
        mock_console.print.assert_called()


class TestGetTeamData:
    """Tests for get_team_data function."""

    def test_get_team_data_success(
        self, mock_firestore_client: Mock, sample_team_data: dict[str, Any]
    ) -> None:
        """Test successful team data retrieval."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_team_data

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_team_data(mock_firestore_client, "test-team")

        assert result == sample_team_data

    def test_get_team_data_not_found(self, mock_firestore_client: Mock) -> None:
        """Test team data retrieval when team not found."""
        mock_doc = Mock()
        mock_doc.exists = False

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_team_data(mock_firestore_client, "nonexistent-team")

        assert result is None

    def test_get_team_data_exception(
        self, mock_firestore_client: Mock, mock_console: Mock
    ) -> None:
        """Test team data retrieval with exception."""
        mock_firestore_client.collection.side_effect = Exception("Database error")

        result = get_team_data(mock_firestore_client, "test-team")

        assert result is None
        mock_console.print.assert_called()


class TestGetGlobalKeys:
    """Tests for get_global_keys function."""

    def test_get_global_keys_success(
        self, mock_firestore_client: Mock, sample_global_keys: dict[str, Any]
    ) -> None:
        """Test successful global keys retrieval."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_global_keys

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_global_keys(mock_firestore_client, "test-bootcamp")

        assert result == sample_global_keys

    def test_get_global_keys_not_found(self, mock_firestore_client: Mock) -> None:
        """Test global keys retrieval when document not found."""
        mock_doc = Mock()
        mock_doc.exists = False

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        result = get_global_keys(mock_firestore_client, "test-bootcamp")

        assert result is None

    def test_get_global_keys_exception(
        self, mock_firestore_client: Mock, mock_console: Mock
    ) -> None:
        """Test global keys retrieval with exception."""
        mock_firestore_client.collection.side_effect = Exception("Database error")

        result = get_global_keys(mock_firestore_client, "test-bootcamp")

        assert result is None
        mock_console.print.assert_called()

    def test_bootcamp_name_used_as_document_id(
        self, mock_firestore_client: Mock, sample_global_keys: dict[str, Any]
    ) -> None:
        """Test that the bootcamp_name argument is used as the Firestore document ID."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_global_keys

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        get_global_keys(mock_firestore_client, "my-bootcamp")

        mock_collection.document.assert_called_once_with("my-bootcamp")


class TestGetAllParticipantsWithStatus:
    """Tests for get_all_participants_with_status function."""

    def test_get_all_participants_success(self, mock_firestore_client: Mock) -> None:
        """Test successful retrieval of all participants with status."""
        mock_doc1 = Mock()
        mock_doc1.id = "user1"
        mock_doc1.to_dict.return_value = {
            "team_name": "team-a",
            "onboarded": True,
            "onboarded_at": datetime.now(timezone.utc),
        }

        mock_doc2 = Mock()
        mock_doc2.id = "user2"
        mock_doc2.to_dict.return_value = {
            "team_name": "team-b",
            "onboarded": False,
        }

        mock_collection = Mock()
        mock_collection.stream.return_value = [mock_doc1, mock_doc2]

        mock_firestore_client.collection.return_value = mock_collection

        result = get_all_participants_with_status(mock_firestore_client)

        assert len(result) == 2
        assert result[0]["github_handle"] == "user1"
        assert result[0]["onboarded"] is True
        assert result[1]["github_handle"] == "user2"
        assert result[1]["onboarded"] is False

    def test_get_all_participants_empty(self, mock_firestore_client: Mock) -> None:
        """Test retrieval when no participants exist."""
        mock_collection = Mock()
        mock_collection.stream.return_value = []

        mock_firestore_client.collection.return_value = mock_collection

        result = get_all_participants_with_status(mock_firestore_client)

        assert result == []


class TestParseEnvExample:
    """Tests for _parse_env_example function."""

    def test_basic_key_extraction(self, tmp_path: Path) -> None:
        """Test that keys are extracted from KEY=value lines in order."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('FOO=""\nBAR=""\n')

        keys = _parse_env_example(env_example)

        assert keys == ["FOO", "BAR"]

    def test_blank_and_comment_lines_skipped(self, tmp_path: Path) -> None:
        """Test that blank lines and '#'-prefixed comment lines produce no keys."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('# Section\n\nFOO=""\n# Another\nBAR=""\n')

        keys = _parse_env_example(env_example)

        assert keys == ["FOO", "BAR"]

    def test_lines_without_equals_skipped(self, tmp_path: Path) -> None:
        """Test that lines with no '=' character are ignored."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('SOME_TEXT\nFOO=""\n')

        keys = _parse_env_example(env_example)

        assert keys == ["FOO"]

    def test_inline_comment_does_not_corrupt_key(self, tmp_path: Path) -> None:
        """Test that a trailing inline comment doesn't affect key parsing."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('API_KEY="..."  # use this or GEMINI_API_KEY\n')

        keys = _parse_env_example(env_example)

        assert keys == ["API_KEY"]

    def test_first_equals_used_as_separator(self, tmp_path: Path) -> None:
        """Test that only the first '=' is used when the value itself contains '='."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('KEY="value=with=equals"\n')

        keys = _parse_env_example(env_example)

        assert keys == ["KEY"]

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """Test that an empty .env.example returns an empty list."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("")

        assert _parse_env_example(env_example) == []


class TestCreateEnvFile:
    """Tests for create_env_file function."""

    def test_create_env_file_success(
        self,
        tmp_path: Path,
        sample_env_example_path: Path,
        sample_team_data: dict[str, Any],
        sample_global_keys: dict[str, Any],
    ) -> None:
        """Test successful .env file creation."""
        env_path = tmp_path / ".env"

        result = create_env_file(
            env_path, sample_env_example_path, sample_team_data, sample_global_keys
        )

        assert result is True
        assert env_path.exists()

        content = env_path.read_text()
        assert "OPENAI_API_KEY" in content
        assert "test-openai-key" in content
        assert "LANGFUSE_SECRET_KEY" in content
        assert "WEAVIATE_HTTP_HOST" in content

    def test_create_env_file_overwrite(
        self,
        tmp_path: Path,
        sample_env_example_path: Path,
        sample_team_data: dict[str, Any],
        sample_global_keys: dict[str, Any],
    ) -> None:
        """Test .env file creation overwrites existing file."""
        env_path = tmp_path / ".env"
        env_path.write_text("old content")

        result = create_env_file(
            env_path, sample_env_example_path, sample_team_data, sample_global_keys
        )

        assert result is True
        content = env_path.read_text()
        assert "old content" not in content
        assert "OPENAI_API_KEY" in content

    def test_global_keys_take_priority_over_team_data(self, tmp_path: Path) -> None:
        """Test that global_keys wins over team_data when both supply the same key."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('SHARED_KEY=""\n')
        env_path = tmp_path / ".env"

        create_env_file(
            env_path,
            env_example,
            team_data={"shared_key": "team-value"},
            global_keys={"SHARED_KEY": "global-value"},
        )

        content = env_path.read_text()
        assert 'SHARED_KEY="global-value"' in content
        assert "team-value" not in content

    def test_key_absent_from_both_sources_written_as_empty(
        self, tmp_path: Path
    ) -> None:
        """Test that a key not found in global_keys or team_data is written as empty."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('UNKNOWN_KEY=""\n')
        env_path = tmp_path / ".env"

        create_env_file(env_path, env_example, team_data={}, global_keys={})

        assert 'UNKNOWN_KEY=""' in env_path.read_text()

    def test_comments_and_blank_lines_preserved(self, tmp_path: Path) -> None:
        """Test that comment and blank lines from .env.example are preserved."""
        env_example = tmp_path / ".env.example"
        env_example.write_text('# Section header\n\nAPI_KEY=""\n')
        env_path = tmp_path / ".env"

        create_env_file(env_path, env_example, team_data={}, global_keys={})

        content = env_path.read_text()
        assert "# Section header\n" in content
        assert "\n\n" in content  # blank line preserved

    def test_metadata_fields_excluded_from_global_keys(
        self, tmp_path: Path, sample_env_example_path: Path
    ) -> None:
        """Test that metadata fields from global_keys are excluded from .env."""
        env_path = tmp_path / ".env"
        global_keys_with_metadata = {
            "EMBEDDING_BASE_URL": "https://embedding.example.com",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        create_env_file(
            env_path,
            sample_env_example_path,
            team_data={},
            global_keys=global_keys_with_metadata,
        )

        content = env_path.read_text()
        assert "created_at" not in content
        assert "updated_at" not in content

    def test_write_failure_returns_false(
        self,
        tmp_path: Path,
        sample_env_example_path: Path,
        sample_team_data: dict[str, Any],
        sample_global_keys: dict[str, Any],
        mock_console: Mock,
    ) -> None:
        """Test that a filesystem error during write returns False and logs."""
        env_path = tmp_path / "nonexistent_dir" / ".env"

        result = create_env_file(
            env_path, sample_env_example_path, sample_team_data, sample_global_keys
        )

        assert result is False
        mock_console.print.assert_called()


class TestValidateEnvFile:
    """Tests for validate_env_file function."""

    def test_validate_env_file_complete(
        self, tmp_path: Path, sample_env_example_path: Path
    ) -> None:
        """Test validation of complete .env file."""
        env_path = tmp_path / ".env"
        content = (
            'OPENAI_API_KEY="test-key"\n'
            'EMBEDDING_BASE_URL="https://example.com"\n'
            'EMBEDDING_API_KEY="test-key"\n'
            'WEAVIATE_HTTP_HOST="example.com"\n'
            'WEAVIATE_GRPC_HOST="example.com"\n'
            'WEAVIATE_API_KEY="test-key"\n'
            'LANGFUSE_SECRET_KEY="test-key"\n'
            'LANGFUSE_PUBLIC_KEY="test-key"\n'
            'WEB_SEARCH_API_KEY="test-key"\n'
        )
        env_path.write_text(content)

        is_complete, missing = validate_env_file(env_path, sample_env_example_path)

        assert is_complete is True
        assert missing == []

    def test_validate_env_file_missing_keys(
        self, tmp_path: Path, sample_env_example_path: Path
    ) -> None:
        """Test validation of incomplete .env file."""
        env_path = tmp_path / ".env"
        content = 'OPENAI_API_KEY="test-key"\nEMBEDDING_BASE_URL=""\n'
        env_path.write_text(content)

        is_complete, missing = validate_env_file(env_path, sample_env_example_path)

        assert is_complete is False
        assert "EMBEDDING_BASE_URL" in missing
        assert "EMBEDDING_API_KEY" in missing

    def test_validate_env_file_not_exists(
        self, tmp_path: Path, sample_env_example_path: Path
    ) -> None:
        """Test validation when file doesn't exist."""
        env_path = tmp_path / "nonexistent.env"

        is_complete, missing = validate_env_file(env_path, sample_env_example_path)

        assert is_complete is False
        assert "File does not exist" in missing

    def test_key_with_empty_value_reported_missing(
        self, tmp_path: Path, sample_env_example_path: Path
    ) -> None:
        """Test that KEY="" (empty quoted value) is treated as a missing key."""
        env_path = tmp_path / ".env"
        env_path.write_text('OPENAI_API_KEY=""\n')

        is_complete, missing = validate_env_file(env_path, sample_env_example_path)

        assert is_complete is False
        assert "OPENAI_API_KEY" in missing


class TestCheckOnboardedStatus:
    """Tests for check_onboarded_status function."""

    def test_check_onboarded_status_true(self, mock_firestore_client: Mock) -> None:
        """Test checking onboarded status when participant is onboarded."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"onboarded": True}

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        success, is_onboarded = check_onboarded_status(
            mock_firestore_client, "test-user"
        )

        assert success is True
        assert is_onboarded is True

    def test_check_onboarded_status_false(self, mock_firestore_client: Mock) -> None:
        """Test checking onboarded status when participant is not onboarded."""
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"onboarded": False}

        mock_ref = Mock()
        mock_ref.get.return_value = mock_doc

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        success, is_onboarded = check_onboarded_status(
            mock_firestore_client, "test-user"
        )

        assert success is True
        assert is_onboarded is False


class TestUpdateOnboardedStatus:
    """Tests for update_onboarded_status function."""

    def test_update_onboarded_status_success(self, mock_firestore_client: Mock) -> None:
        """Test successful update of onboarded status."""
        mock_ref = Mock()
        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        success, error = update_onboarded_status(mock_firestore_client, "test-user")

        assert success is True
        assert error is None
        mock_ref.update.assert_called_once()

    def test_update_onboarded_status_failure(self, mock_firestore_client: Mock) -> None:
        """Test failed update of onboarded status."""
        mock_ref = Mock()
        mock_ref.update.side_effect = Exception("Update failed")

        mock_collection = Mock()
        mock_collection.document.return_value = mock_ref

        mock_firestore_client.collection.return_value = mock_collection

        success, error = update_onboarded_status(mock_firestore_client, "test-user")

        assert success is False
        assert "Update failed" in str(error)
