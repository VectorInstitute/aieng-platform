"""Shared utilities for participant onboarding scripts."""

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import google.auth
import requests
from google.auth import jwt as google_jwt
from google.cloud import firestore
from google.oauth2 import credentials as oauth2_credentials
from rich.console import Console


# Constants
FIRESTORE_PROJECT_ID = "coderd"
FIRESTORE_DATABASE_ID = "onboarding"
FIREBASE_AUTH_EXCHANGE_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
)

# Global console instance for rich output
console = Console()


def get_console() -> Console:
    """
    Get the global console instance for rich output.

    Returns
    -------
    Console
        Rich Console instance for formatted output.
    """
    return console


def get_github_user() -> str | None:
    """
    Get GitHub username from environment variable.

    Returns
    -------
    str | None
        GitHub username if found, None otherwise.
    """
    github_user = os.environ.get("GITHUB_USER")
    if not github_user:
        # Try alternative environment variables
        github_user = os.environ.get("GH_USER") or os.environ.get("USER")
    return github_user


def fetch_token_from_service(  # noqa: PLR0911
    github_handle: str, token_service_url: str | None = None
) -> tuple[bool, str | None, str | None]:
    """
    Fetch fresh Firebase token from Cloud Run token service.

    This generates tokens on-demand using the workspace service account identity.
    Tokens are always fresh (< 1 hour old).

    Parameters
    ----------
    github_handle : str
        GitHub handle of the participant.
    token_service_url : str | None, optional
        Token service URL. If not provided, reads from TOKEN_SERVICE_URL env var
        or .token-service-url file.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, token_value, error_message).
    """
    try:
        # Get token service URL
        if not token_service_url:
            token_service_url = os.environ.get("TOKEN_SERVICE_URL")

        if not token_service_url:
            # Try reading from config file
            config_file = Path.home() / ".token-service-url"
            if config_file.exists():
                token_service_url = config_file.read_text().strip()

        if not token_service_url:
            return (
                False,
                None,
                (
                    "Token service URL not found. Set TOKEN_SERVICE_URL environment "
                    "variable or ensure .token-service-url file exists."
                ),
            )

        # Get identity token for authentication
        # Try to get identity token
        # In workspaces, this will use the compute service account
        credentials, project_id = google.auth.default()  # type: ignore[no-untyped-call]

        # Request an identity token instead of an access token
        # This is required for Cloud Run authentication
        if hasattr(credentials, "signer"):
            # Service account - can create identity tokens
            now = int(time.time())
            payload = {
                "iss": credentials.service_account_email,
                "sub": credentials.service_account_email,
                "aud": token_service_url,
                "iat": now,
                "exp": now + 3600,
            }
            id_token = google_jwt.encode(credentials.signer, payload)  # type: ignore[no-untyped-call]
        else:
            # User credentials or other - use gcloud
            try:
                result = subprocess.run(
                    [
                        "gcloud",
                        "auth",
                        "print-identity-token",
                        f"--audiences={token_service_url}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    return False, None, f"Failed to get identity token: {result.stderr}"
                id_token = result.stdout.strip()
            except Exception as e:
                return False, None, f"Failed to run gcloud: {str(e)}"

        if not id_token:
            return False, None, "Failed to get identity token for authentication"

        # Call token service
        url = f"{token_service_url.rstrip('/')}/generate-token"
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        }
        payload = {"github_handle": github_handle}

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code != 200:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
            return False, None, f"Token service error: {error_msg}"

        data = response.json()
        token = data.get("token")

        if not token:
            return False, None, "No token in service response"

        return True, token, None

    except Exception as e:
        return False, None, f"Failed to fetch token from service: {str(e)}"


def exchange_custom_token_for_id_token(
    custom_token: str, api_key: str
) -> tuple[bool, str | None, str | None]:
    """
    Exchange Firebase custom token for ID token via Firebase Auth REST API.

    Parameters
    ----------
    custom_token : str
        Firebase custom token.
    api_key : str
        Firebase Web API key.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, id_token, error_message).
    """
    try:
        url = f"{FIREBASE_AUTH_EXCHANGE_URL}?key={api_key}"
        payload = {"token": custom_token, "returnSecureToken": True}

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code != 200:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return False, None, f"Firebase Auth API error: {error_msg}"

        data = response.json()
        id_token = data.get("idToken")

        if not id_token:
            return False, None, "No ID token in response"

        return True, id_token, None

    except Exception as e:
        return False, None, str(e)


def initialize_firestore_with_token(
    custom_token: str,
    project_id: str,
    database_id: str,
    firebase_api_key: str | None = None,
) -> firestore.Client:
    """
    Initialize Firestore client with Firebase authentication token.

    This function exchanges the Firebase custom token for an ID token and uses it
    to authenticate Firestore requests, ensuring security rules are enforced.

    Parameters
    ----------
    custom_token : str
        Firebase custom token from Secret Manager.
    project_id : str
        GCP project ID.
    database_id : str
        Firestore database ID.
    firebase_api_key : str | None, optional
        Firebase Web API key for token exchange. If not provided, will attempt
        to read from FIREBASE_WEB_API_KEY environment variable.

    Returns
    -------
    firestore.Client
        Authenticated Firestore client with security rules enforced.

    Raises
    ------
    Exception
        If initialization or token exchange fails.
    """
    try:
        # Get Firebase Web API key
        if not firebase_api_key:
            firebase_api_key = os.environ.get("FIREBASE_WEB_API_KEY")

        if not firebase_api_key:
            raise Exception(
                "Firebase Web API key required for token exchange. "
                "Set FIREBASE_WEB_API_KEY environment variable or pass as parameter."
            )

        # Exchange custom token for ID token
        console.print("[dim]Exchanging custom token for ID token...[/dim]")
        success, id_token, error = exchange_custom_token_for_id_token(
            custom_token, firebase_api_key
        )

        if not success or not id_token:
            raise Exception(f"Failed to exchange custom token: {error}")

        # Create OAuth2 credentials with the ID token
        # Firebase ID tokens can be used as bearer tokens for Google APIs
        creds = oauth2_credentials.Credentials(token=id_token)  # type: ignore[no-untyped-call]

        # Initialize Firestore client with the credentials
        return firestore.Client(
            project=project_id, database=database_id, credentials=creds
        )

    except Exception as e:
        raise Exception(f"Failed to initialize Firestore client: {e}") from e


def get_participant_data(
    db: firestore.Client, github_handle: str
) -> dict[str, Any] | None:
    """
    Retrieve participant document from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handle : str
        GitHub handle of the participant.

    Returns
    -------
    dict[str, Any] | None
        Participant data or None if not found.
    """
    try:
        doc_ref = db.collection("participants").document(github_handle)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        console.print(f"[red]✗ Failed to fetch participant data:[/red] {e}")
        return None


def get_team_data(db: firestore.Client, team_name: str) -> dict[str, Any] | None:
    """
    Retrieve team document from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    team_name : str
        Name of the team.

    Returns
    -------
    dict[str, Any] | None
        Team data or None if not found.
    """
    try:
        doc_ref = db.collection("teams").document(team_name)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        console.print(f"[red]✗ Failed to fetch team data:[/red] {e}")
        return None


def get_global_keys(db: firestore.Client) -> dict[str, Any] | None:
    """
    Retrieve global keys from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.

    Returns
    -------
    dict[str, Any] | None
        Global keys data or None if not found.
    """
    try:
        doc_ref = db.collection("global_keys").document("bootcamp-shared")
        doc = doc_ref.get()

        if not doc.exists:
            return None

        return doc.to_dict()

    except Exception as e:
        console.print(f"[red]✗ Failed to fetch global keys:[/red] {e}")
        return None


def _add_embedding_section(
    key_list: list[str], filtered_global_keys: dict[str, Any]
) -> str:
    """Build embedding section of .env file."""
    if not key_list:
        return ""
    content = "# Embedding model\n"
    for key in sorted(key_list):
        content += f'{key}="{filtered_global_keys[key]}"\n'
    content += "\n"
    return content


def _add_langfuse_section(
    key_list: list[str],
    filtered_global_keys: dict[str, Any],
    team_data: dict[str, Any],
) -> str:
    """Build LangFuse section of .env file."""
    has_team_keys = team_data.get("langfuse_secret_key") or team_data.get(
        "langfuse_public_key"
    )
    if not key_list and not has_team_keys:
        return ""

    content = "# LangFuse\n"
    # Team-specific keys first
    if team_data.get("langfuse_secret_key"):
        content += f'LANGFUSE_SECRET_KEY="{team_data.get("langfuse_secret_key", "")}"\n'
    if team_data.get("langfuse_public_key"):
        content += f'LANGFUSE_PUBLIC_KEY="{team_data.get("langfuse_public_key", "")}"\n'
    # Then global keys
    for key in sorted(key_list):
        content += f'{key}="{filtered_global_keys[key]}"\n'
    content += "\n"
    return content


def _add_web_search_section(
    key_list: list[str],
    filtered_global_keys: dict[str, Any],
    team_data: dict[str, Any],
) -> str:
    """Build Web Search section of .env file."""
    if not key_list and not team_data.get("web_search_api_key"):
        return ""

    content = "# Web Search\n"
    # Global keys first
    for key in sorted(key_list):
        content += f'{key}="{filtered_global_keys[key]}"\n'
    # Then team-specific key
    if team_data.get("web_search_api_key"):
        content += f'WEB_SEARCH_API_KEY="{team_data.get("web_search_api_key", "")}"\n'
    content += "\n"
    return content


def _add_weaviate_section(
    key_list: list[str], filtered_global_keys: dict[str, Any]
) -> str:
    """Build Weaviate section of .env file."""
    if not key_list:
        return ""
    content = "# Weaviate\n"
    for key in sorted(key_list):
        content += f'{key}="{filtered_global_keys[key]}"\n'
    content += "\n"
    return content


def _add_other_keys_section(
    key_list: list[str], filtered_global_keys: dict[str, Any]
) -> str:
    """Build section for other uncategorized keys."""
    if not key_list:
        return ""
    content = "# Other Configuration\n"
    for key in sorted(key_list):
        content += f'{key}="{filtered_global_keys[key]}"\n'
    content += "\n"
    return content


def create_env_file(
    output_path: Path,
    team_data: dict[str, Any],
    global_keys: dict[str, Any],
) -> bool:
    """
    Create .env file with API keys and configuration.

    Parameters
    ----------
    output_path : Path
        Path where .env file should be created.
    team_data : dict[str, Any]
        Team data containing team-specific keys.
    global_keys : dict[str, Any]
        Global keys shared across all participants.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    try:
        # Metadata fields to exclude from .env file
        metadata_fields = {"created_at", "updated_at"}

        # Filter out metadata fields from global keys
        filtered_global_keys = {
            k: v for k, v in global_keys.items() if k not in metadata_fields
        }

        # Categorize global keys by prefix for organized output
        key_categories: dict[str, list[str]] = {
            "EMBEDDING": [],
            "LANGFUSE": [],
            "WEAVIATE": [],
            "WEB_SEARCH": [],
        }
        other_keys = []

        for key in filtered_global_keys:
            categorized = False
            for prefix, category_list in key_categories.items():
                if key.startswith(prefix):
                    category_list.append(key)
                    categorized = True
                    break
            if not categorized:
                other_keys.append(key)

        # Build .env content
        env_content = "#!/bin/bash\n"
        env_content += "# OpenAI-compatible LLM (Gemini)\n"
        env_content += 'OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"\n'
        env_content += f'OPENAI_API_KEY="{team_data.get("openai_api_key", "")}"\n\n'

        # Add sections using helper functions
        env_content += _add_embedding_section(
            key_categories["EMBEDDING"], filtered_global_keys
        )
        env_content += _add_langfuse_section(
            key_categories["LANGFUSE"], filtered_global_keys, team_data
        )
        env_content += _add_web_search_section(
            key_categories["WEB_SEARCH"], filtered_global_keys, team_data
        )
        env_content += _add_weaviate_section(
            key_categories["WEAVIATE"], filtered_global_keys
        )
        env_content += _add_other_keys_section(other_keys, filtered_global_keys)

        # Write to file
        with open(output_path, "w") as f:
            f.write(env_content)

        return True

    except Exception as e:
        console.print(f"[red]✗ Failed to create .env file:[/red] {e}")
        return False


def check_onboarded_status(
    db: firestore.Client, github_handle: str
) -> tuple[bool, bool]:
    """
    Check if participant is already onboarded.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handle : str
        GitHub handle of the participant.

    Returns
    -------
    tuple[bool, bool]
        Tuple of (success, is_onboarded).
    """
    try:
        doc_ref = db.collection("participants").document(github_handle)
        doc = doc_ref.get()

        if not doc.exists:
            return True, False

        data = doc.to_dict()
        is_onboarded = data.get("onboarded", False) if data else False
        return True, is_onboarded

    except Exception as e:
        console.print(f"[yellow]⚠ Failed to check onboarded status:[/yellow] {e}")
        return False, False


def validate_env_file(env_path: Path) -> tuple[bool, list[str]]:
    """
    Validate if .env file exists and contains all required keys.

    Parameters
    ----------
    env_path : Path
        Path to the .env file.

    Returns
    -------
    tuple[bool, list[str]]
        Tuple of (is_complete, missing_keys).
    """
    if not env_path.exists():
        return False, ["File does not exist"]

    # Core required keys that must always be present
    # Note: This could be made more dynamic by fetching from Firestore,
    # but we maintain a minimal set here for basic validation
    required_keys = [
        "OPENAI_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_HOST",
        "WEB_SEARCH_BASE_URL",
        "WEB_SEARCH_API_KEY",
        "WEAVIATE_HTTP_HOST",
        "WEAVIATE_GRPC_HOST",
        "WEAVIATE_API_KEY",
    ]

    try:
        with open(env_path) as f:
            content = f.read()

        missing_keys = []
        for key in required_keys:
            # Check if key exists and has a non-empty value
            if f'{key}=""' in content or key not in content:
                missing_keys.append(key)

        return len(missing_keys) == 0, missing_keys

    except Exception as e:
        console.print(f"[yellow]⚠ Failed to validate .env file:[/yellow] {e}")
        return False, [str(e)]


def update_onboarded_status(
    db: firestore.Client, github_handle: str
) -> tuple[bool, str | None]:
    """
    Update participant's onboarded status in Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handle : str
        GitHub handle of the participant.

    Returns
    -------
    tuple[bool, str | None]
        Tuple of (success, error_message).
    """
    try:
        doc_ref = db.collection("participants").document(github_handle)
        doc_ref.update(
            {
                "onboarded": True,
                "onboarded_at": datetime.now(timezone.utc),
            }
        )
        return True, None

    except Exception as e:
        return False, str(e)


def initialize_firestore_admin(
    project_id: str = FIRESTORE_PROJECT_ID,
    database_id: str = FIRESTORE_DATABASE_ID,
) -> firestore.Client:
    """
    Initialize Firestore client with admin (service account) credentials.

    This function uses default Google Cloud credentials, typically a service
    account, to connect to Firestore with full admin access. This bypasses
    security rules and should only be used by authorized administrators.

    Parameters
    ----------
    project_id : str, optional
        GCP project ID, by default FIRESTORE_PROJECT_ID.
    database_id : str, optional
        Firestore database ID, by default FIRESTORE_DATABASE_ID.

    Returns
    -------
    firestore.Client
        Authenticated Firestore client with admin access.

    Raises
    ------
    Exception
        If initialization fails or credentials are not available.
    """
    try:
        return firestore.Client(project=project_id, database=database_id)
    except Exception as e:
        raise Exception(
            f"Failed to initialize Firestore admin client: {e}\n"
            "Ensure you have proper GCP service account credentials configured."
        ) from e


def get_all_participants_with_status(db: firestore.Client) -> list[dict[str, Any]]:
    """
    Retrieve all participants with their onboarding status.

    This function fetches all participant documents from Firestore and
    returns them with their GitHub handle, team name, and onboarding status.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance with admin access.

    Returns
    -------
    list[dict[str, Any]]
        List of participant data dictionaries containing:
        - github_handle: GitHub username
        - team_name: Assigned team name
        - onboarded: Boolean onboarding status
        - onboarded_at: Timestamp of onboarding (if onboarded)

    Raises
    ------
    Exception
        If fetching participant data fails.
    """
    try:
        participants_ref = db.collection("participants")
        participants = []

        for doc in participants_ref.stream():
            participant_data = doc.to_dict()
            if participant_data:
                participants.append(
                    {
                        "github_handle": doc.id,
                        "team_name": participant_data.get("team_name", "N/A"),
                        "onboarded": participant_data.get("onboarded", False),
                        "onboarded_at": participant_data.get("onboarded_at"),
                    }
                )

        # Sort by team name, then by github handle
        participants.sort(key=lambda x: (x["team_name"], x["github_handle"]))
        return participants

    except Exception as e:
        raise Exception(f"Failed to fetch participant data: {e}") from e
