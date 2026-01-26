"""Shared utilities for admin commands."""

from typing import Any

from google.cloud import firestore  # type: ignore[attr-defined]
from google.cloud.firestore_v1.base_query import FieldFilter
from rich.console import Console


# Constants
FIRESTORE_PROJECT_ID = "coderd"
FIRESTORE_DATABASE_ID = "onboarding"

# Collection names
COLLECTION_TEAMS = "teams"
COLLECTION_PARTICIPANTS = "participants"
COLLECTION_GLOBAL_KEYS = "global_keys"

# Document IDs
GLOBAL_KEYS_DOC_ID = "bootcamp-shared"

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


def normalize_github_handle(github_handle: str) -> str:
    """
    Normalize GitHub handle to lowercase for case-insensitive matching.

    GitHub handles are case-insensitive but case-preserving. This function
    ensures consistent lookups in Firestore by normalizing to lowercase.

    Parameters
    ----------
    github_handle : str
        GitHub handle in any case.

    Returns
    -------
    str
        Normalized (lowercase) GitHub handle.
    """
    return github_handle.lower()


def get_firestore_client() -> firestore.Client:
    """
    Initialize and return a Firestore client.

    Returns
    -------
    firestore.Client
        Initialized Firestore client.

    Raises
    ------
    Exception
        If Firestore client initialization fails.
    """
    try:
        return firestore.Client(
            project=FIRESTORE_PROJECT_ID,
            database=FIRESTORE_DATABASE_ID,
        )
    except Exception as e:
        raise Exception(f"Failed to initialize Firestore client: {e}") from e


def validate_team_name(team_name: str) -> bool:
    """
    Validate team name format.

    Parameters
    ----------
    team_name : str
        Team name to validate.

    Returns
    -------
    bool
        True if valid, False otherwise.
    """
    if not team_name or not isinstance(team_name, str):
        return False
    # Team name should be alphanumeric with hyphens and underscores only
    return team_name.replace("-", "").replace("_", "").isalnum()


def validate_github_handle(handle: str) -> bool:
    """
    Validate GitHub handle format.

    Parameters
    ----------
    handle : str
        GitHub handle to validate.

    Returns
    -------
    bool
        True if valid, False otherwise.
    """
    if not handle or not isinstance(handle, str):
        return False
    # GitHub handles can contain alphanumeric and hyphens, max 39 chars
    if len(handle) > 39:
        return False
    # Cannot start with hyphen
    if handle.startswith("-"):
        return False
    return handle.replace("-", "").isalnum()


def validate_email(email: str) -> bool:
    """
    Validate email address format (basic validation).

    Parameters
    ----------
    email : str
        Email address to validate.

    Returns
    -------
    bool
        True if valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    return "@" in email and "." in email.split("@")[1]


def get_all_teams(db: firestore.Client) -> list[dict[str, Any]]:
    """
    Retrieve all teams from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.

    Returns
    -------
    list[dict[str, Any]]
        List of team documents with their IDs.
    """
    teams_ref = db.collection(COLLECTION_TEAMS)
    teams = []
    for doc in teams_ref.stream():
        team_data = doc.to_dict()
        if team_data:
            team_data["id"] = doc.id
            teams.append(team_data)
    return teams


def get_team_by_name(db: firestore.Client, team_name: str) -> dict[str, Any] | None:
    """
    Retrieve a specific team by name.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    team_name : str
        Name of the team to retrieve.

    Returns
    -------
    dict[str, Any] | None
        Team document data or None if not found.
    """
    teams_ref = db.collection(COLLECTION_TEAMS)
    query = teams_ref.where(filter=FieldFilter("team_name", "==", team_name))
    results = list(query.stream())

    if not results:
        return None

    team_data = results[0].to_dict()
    if team_data:
        team_data["id"] = results[0].id
    return team_data


def get_all_participants(db: firestore.Client) -> list[dict[str, Any]]:
    """
    Retrieve all participants from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.

    Returns
    -------
    list[dict[str, Any]]
        List of participant documents with their IDs.
    """
    participants_ref = db.collection(COLLECTION_PARTICIPANTS)
    participants = []
    for doc in participants_ref.stream():
        participant_data = doc.to_dict()
        if participant_data:
            participant_data["id"] = doc.id
            participants.append(participant_data)
    return participants


def get_participant_by_handle(
    db: firestore.Client, github_handle: str
) -> dict[str, Any] | None:
    """
    Retrieve a specific participant by GitHub handle.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handle : str
        GitHub handle of the participant.

    Returns
    -------
    dict[str, Any] | None
        Participant document data or None if not found.
    """
    # Normalize GitHub handle for case-insensitive matching
    github_handle_normalized = normalize_github_handle(github_handle)
    participant_ref = db.collection(COLLECTION_PARTICIPANTS).document(
        github_handle_normalized
    )
    doc = participant_ref.get()

    if not doc.exists:
        return None

    participant_data = doc.to_dict()
    if participant_data:
        participant_data["id"] = doc.id
    return participant_data


def format_api_key_name(
    bootcamp_name: str, team_name: str, key_type: str = "gemini"
) -> str:
    """
    Format API key name consistently.

    Parameters
    ----------
    bootcamp_name : str
        Name of the bootcamp.
    team_name : str
        Name of the team.
    key_type : str, optional
        Type of the key, by default "gemini".

    Returns
    -------
    str
        Formatted API key name.
    """
    return f"{bootcamp_name}-{team_name}-{key_type}"


def mask_sensitive_value(value: str, visible_chars: int = 8) -> str:
    """
    Mask sensitive values for display.

    Parameters
    ----------
    value : str
        The sensitive value to mask.
    visible_chars : int, optional
        Number of characters to show at the start, by default 8.

    Returns
    -------
    str
        Masked value.
    """
    if not value:
        return "NOT SET"
    if len(value) <= visible_chars:
        return value
    return f"{value[:visible_chars]}..."
