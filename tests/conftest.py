"""Pytest configuration and fixtures for aieng_platform_onboard tests."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

import pytest
from google.cloud import firestore


@pytest.fixture
def mock_firestore_client() -> Mock:
    """
    Create a mock Firestore client for testing.

    Returns
    -------
    Mock
        Mock Firestore client instance.
    """
    return Mock(spec=firestore.Client)


@pytest.fixture
def mock_firestore_document() -> Mock:
    """
    Create a mock Firestore document for testing.

    Returns
    -------
    Mock
        Mock Firestore document instance.
    """
    mock_doc = Mock()
    mock_doc.exists = True
    mock_doc.id = "test-handle"
    mock_doc.to_dict.return_value = {
        "github_handle": "test-handle",
        "team_name": "test-team",
        "onboarded": False,
        "email": "test@example.com",
    }
    return mock_doc


@pytest.fixture
def sample_participant_data() -> dict[str, Any]:
    """
    Sample participant data for testing.

    Returns
    -------
    dict[str, Any]
        Sample participant data dictionary.
    """
    return {
        "github_handle": "test-user",
        "team_name": "test-team",
        "onboarded": False,
        "email": "test@example.com",
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_team_data() -> dict[str, Any]:
    """
    Sample team data for testing.

    Returns
    -------
    dict[str, Any]
        Sample team data dictionary.
    """
    return {
        "team_name": "test-team",
        "openai_api_key": "test-openai-key",
        "langfuse_secret_key": "test-langfuse-secret",
        "langfuse_public_key": "test-langfuse-public",
        "langfuse_url": "https://test-langfuse.example.com",
        "web_search_api_key": "test-search-key",
        "participants": ["test-user", "test-user-2"],
    }


@pytest.fixture
def sample_global_keys() -> dict[str, Any]:
    """
    Sample global keys for testing.

    Returns
    -------
    dict[str, Any]
        Sample global keys dictionary.
    """
    return {
        "EMBEDDING_BASE_URL": "https://embedding.example.com",
        "EMBEDDING_API_KEY": "test-embedding-key",
        "WEAVIATE_HTTP_HOST": "weaviate.example.com",
        "WEAVIATE_GRPC_HOST": "weaviate-grpc.example.com",
        "WEAVIATE_API_KEY": "test-weaviate-key",
        "WEAVIATE_HTTP_PORT": "443",
        "WEAVIATE_GRPC_PORT": "50051",
        "WEAVIATE_HTTP_SECURE": "true",
        "WEAVIATE_GRPC_SECURE": "true",
    }


@pytest.fixture
def mock_requests_post(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """
    Mock requests.post for testing HTTP requests.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    -------
    Mock
        Mock requests.post function.
    """
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token": "test-token"}

    mock_post = Mock(return_value=mock_response)
    monkeypatch.setattr("requests.post", mock_post)
    return mock_post


@pytest.fixture
def mock_google_auth(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, str]:
    """
    Mock google.auth.default for testing authentication.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    -------
    tuple[Mock, str]
        Tuple of (mock_credentials, project_id).
    """
    mock_credentials = Mock()
    mock_credentials.service_account_email = "test@example.iam.gserviceaccount.com"
    mock_credentials.signer = Mock()

    def mock_default() -> tuple[Mock, str]:
        return mock_credentials, "test-project"

    monkeypatch.setattr("google.auth.default", mock_default)
    return mock_credentials, "test-project"


@pytest.fixture
def mock_subprocess_run(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """
    Mock subprocess.run for testing command execution.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    -------
    Mock
        Mock subprocess.run function.
    """
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "test output"
    mock_result.stderr = ""

    mock_run = Mock(return_value=mock_result)
    monkeypatch.setattr("subprocess.run", mock_run)
    return mock_run


@pytest.fixture
def mock_console(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """
    Mock Rich console for testing output.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    -------
    Mock
        Mock console instance.
    """
    mock_console_instance = Mock()
    monkeypatch.setattr("aieng_platform_onboard.utils.console", mock_console_instance)
    monkeypatch.setattr("aieng_platform_onboard.cli.console", mock_console_instance)
    return mock_console_instance
