"""Shared utilities for participant onboarding scripts."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from google.cloud import firestore, secretmanager  # type: ignore[attr-defined]
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


def fetch_token_from_secret_manager(
    github_handle: str, bootcamp_name: str, project_id: str
) -> tuple[bool, str | None, str | None]:
    """
    Fetch Firebase token from GCP Secret Manager.

    Parameters
    ----------
    github_handle : str
        GitHub handle of the participant.
    bootcamp_name : str
        Name of the bootcamp.
    project_id : str
        GCP project ID.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, token_value, error_message).
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"{bootcamp_name}-token-{github_handle}"
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": name})
        token = response.payload.data.decode("UTF-8")

        return True, token, None

    except Exception as e:
        return False, None, str(e)


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
        # Build .env content
        env_content = "#!/bin/bash\n"
        env_content += "# OpenAI-compatible LLM (Gemini)\n"
        env_content += 'OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"\n'
        env_content += f'OPENAI_API_KEY="{team_data.get("openai_api_key", "")}"\n\n'

        env_content += "# Embedding model\n"
        env_content += (
            f'EMBEDDING_BASE_URL="{global_keys.get("EMBEDDING_BASE_URL", "")}"\n'
        )
        env_content += (
            f'EMBEDDING_API_KEY="{global_keys.get("EMBEDDING_API_KEY", "")}"\n\n'
        )

        env_content += "# LangFuse\n"
        env_content += (
            f'LANGFUSE_SECRET_KEY="{team_data.get("langfuse_secret_key", "")}"\n'
        )
        env_content += (
            f'LANGFUSE_PUBLIC_KEY="{team_data.get("langfuse_public_key", "")}"\n'
        )
        env_content += f'LANGFUSE_HOST="{global_keys.get("LANGFUSE_HOST", "")}"\n\n'

        env_content += "# Weaviate\n"
        env_content += (
            f'WEAVIATE_HTTP_HOST="{global_keys.get("WEAVIATE_HTTP_HOST", "")}"\n'
        )
        env_content += (
            f'WEAVIATE_GRPC_HOST="{global_keys.get("WEAVIATE_GRPC_HOST", "")}"\n'
        )
        env_content += f'WEAVIATE_API_KEY="{global_keys.get("WEAVIATE_API_KEY", "")}"\n'
        env_content += (
            f'WEAVIATE_HTTP_PORT="{global_keys.get("WEAVIATE_HTTP_PORT", "")}"\n'
        )
        env_content += (
            f'WEAVIATE_GRPC_PORT="{global_keys.get("WEAVIATE_GRPC_PORT", "")}"\n'
        )
        env_content += (
            f'WEAVIATE_HTTP_SECURE="{global_keys.get("WEAVIATE_HTTP_SECURE", "")}"\n'
        )
        env_content += (
            f'WEAVIATE_GRPC_SECURE="{global_keys.get("WEAVIATE_GRPC_SECURE", "")}"\n'
        )

        # Write to file
        with open(output_path, "w") as f:
            f.write(env_content)

        return True

    except Exception as e:
        console.print(f"[red]✗ Failed to create .env file:[/red] {e}")
        return False


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
