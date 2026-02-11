"""Create Gemini API keys for teams in Firestore."""

import json
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

import requests
from google.cloud.firestore import Client as FirestoreClient
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aieng_platform_onboard.admin.utils import (
    COLLECTION_TEAMS,
    console,
    format_api_key_name,
    get_firestore_client,
    mask_sensitive_value,
    validate_team_name,
)


# Constants
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
VALIDATION_RETRIES = 3
VALIDATION_TIMEOUT = 10
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds


class PrerequisiteError(Exception):
    """Raised when prerequisites are not met."""

    pass


class APIKeyCreationError(Exception):
    """Raised when API key creation fails."""

    pass


class APIKeyValidationError(Exception):
    """Raised when API key validation fails."""

    pass


def validate_prerequisites(project_id: str) -> None:
    """
    Validate prerequisites before creating API keys.

    Checks:
    - gcloud CLI is installed and accessible
    - GCP project exists and user has access
    - API Keys service is enabled
    - Generative Language API is enabled
    - User has necessary IAM permissions

    Parameters
    ----------
    project_id : str
        GCP project ID where keys will be created.

    Raises
    ------
    PrerequisiteError
        If any prerequisite check fails.
    """
    # Check gcloud CLI is installed
    try:
        result = subprocess.run(
            ["gcloud", "version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        console.print("[green]✓[/green] gcloud CLI is installed")
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as e:
        raise PrerequisiteError(
            "gcloud CLI is not installed or not accessible. "
            "Install it from https://cloud.google.com/sdk/docs/install"
        ) from e

    # Check project access
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, "--format=json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        console.print(f"[green]✓[/green] Project '{project_id}' is accessible")
    except subprocess.CalledProcessError as e:
        raise PrerequisiteError(
            f"Cannot access GCP project '{project_id}'. "
            f"Ensure the project exists and you have access. Error: {e.stderr}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise PrerequisiteError(
            f"Timeout while checking project '{project_id}'. "
            "Check your network connection."
        ) from e

    # Check if API Keys service is enabled
    try:
        result = subprocess.run(
            [
                "gcloud",
                "services",
                "list",
                "--enabled",
                "--filter=name:apikeys.googleapis.com",
                "--format=json",
                f"--project={project_id}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        services = json.loads(result.stdout)
        if not services:
            raise PrerequisiteError(
                f"API Keys service is not enabled in project '{project_id}'. "
                f"Enable it with: gcloud services enable apikeys.googleapis.com --project={project_id}"
            )
        console.print("[green]✓[/green] API Keys service is enabled")
    except subprocess.CalledProcessError as e:
        raise PrerequisiteError(
            f"Failed to check if API Keys service is enabled: {e.stderr}"
        ) from e
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        raise PrerequisiteError(f"Failed to parse API Keys service status: {e}") from e

    # Check if Generative Language API is enabled
    try:
        result = subprocess.run(
            [
                "gcloud",
                "services",
                "list",
                "--enabled",
                "--filter=name:generativelanguage.googleapis.com",
                "--format=json",
                f"--project={project_id}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        services = json.loads(result.stdout)
        if not services:
            raise PrerequisiteError(
                f"Generative Language API is not enabled in project '{project_id}'. "
                f"Enable it with: gcloud services enable generativelanguage.googleapis.com --project={project_id}"
            )
        console.print("[green]✓[/green] Generative Language API is enabled")
    except subprocess.CalledProcessError as e:
        raise PrerequisiteError(
            f"Failed to check if Generative Language API is enabled: {e.stderr}"
        ) from e
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        raise PrerequisiteError(
            f"Failed to parse Generative Language API status: {e}"
        ) from e

    console.print("[green]✓[/green] All prerequisites validated")


def get_existing_api_key(project_id: str, key_display_name: str) -> str | None:
    """
    Check if an API key with the given display name already exists.

    Parameters
    ----------
    project_id : str
        GCP project ID where to search for the key.
    key_display_name : str
        Display name of the key to search for.

    Returns
    -------
    str | None
        The API key resource name if found, None otherwise.
    """
    try:
        result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "services",
                "api-keys",
                "list",
                f"--project={project_id}",
                f"--filter=displayName={key_display_name}",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        keys = json.loads(result.stdout)
        if keys and isinstance(keys, list) and len(keys) > 0:
            return keys[0].get("name")
        return None

    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ):
        return None


def delete_api_key(project_id: str, key_resource_name: str) -> None:
    """
    Delete an API key.

    Parameters
    ----------
    project_id : str
        GCP project ID where the key exists.
    key_resource_name : str
        The API key resource name to delete.

    Raises
    ------
    APIKeyCreationError
        If key deletion fails.
    """
    try:
        subprocess.run(
            [
                "gcloud",
                "alpha",
                "services",
                "api-keys",
                "delete",
                key_resource_name,
                f"--project={project_id}",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise APIKeyCreationError(
            f"Failed to delete existing API key '{key_resource_name}': {e.stderr}"
        ) from e


def _handle_existing_key(
    project_id: str,
    key_display_name: str,
    existing_key: str,
    overwrite_existing: bool,
    dry_run: bool,
) -> str | None:
    """
    Handle existing API key logic.

    Returns the existing key resource name if it should be reused,
    None if a new key should be created.
    """
    if not overwrite_existing:
        console.print(f"  [cyan]Using existing[/cyan] API key '{key_display_name}'")
        return existing_key

    # overwrite_existing is True, delete the old key
    if dry_run:
        console.print(
            f"  [blue]Would delete[/blue] existing API key '{key_display_name}'"
        )
    else:
        console.print(
            f"  [yellow]Deleting existing[/yellow] API key '{key_display_name}'"
        )
        delete_api_key(project_id, existing_key)

    return None


def _wait_for_operation_and_get_key(
    project_id: str, key_display_name: str, operation_name: str
) -> str:
    """Wait for operation completion and retrieve key resource name."""
    # Wait for the operation to complete
    subprocess.run(
        [
            "gcloud",
            "alpha",
            "services",
            "operations",
            "wait",
            operation_name,
            f"--project={project_id}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )

    # List keys to find the one we just created
    list_result = subprocess.run(
        [
            "gcloud",
            "alpha",
            "services",
            "api-keys",
            "list",
            f"--project={project_id}",
            f"--filter=displayName={key_display_name}",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    keys = json.loads(list_result.stdout)
    if not keys or not isinstance(keys, list) or len(keys) == 0:
        raise APIKeyCreationError(
            f"Failed to find created API key '{key_display_name}' after operation completed"
        )

    key_resource_name = keys[0].get("name")
    if not key_resource_name:
        raise APIKeyCreationError(
            f"Failed to get key resource name from list results: {list_result.stdout}"
        )

    return key_resource_name


def _handle_creation_error(
    error_msg: str, key_display_name: str, project_id: str
) -> None:
    """Handle common API key creation errors."""
    if "ALREADY_EXISTS" in error_msg or "already exists" in error_msg:
        raise APIKeyCreationError(
            f"API key '{key_display_name}' already exists in project '{project_id}'. "
            "Use --overwrite-existing to recreate it or delete the existing key first."
        )
    if "PERMISSION_DENIED" in error_msg:
        raise APIKeyCreationError(
            f"Permission denied when creating API key. "
            f"Ensure you have 'serviceusage.apiKeysAdmin' or 'owner' role on project '{project_id}'."
        )
    if "QUOTA_EXCEEDED" in error_msg:
        raise APIKeyCreationError(
            f"Quota exceeded when creating API key in project '{project_id}'. "
            "Check your API key quota limits in the GCP Console."
        )

    raise APIKeyCreationError(
        f"Failed to create API key '{key_display_name}': {error_msg}"
    )


def create_gemini_api_key(
    project_id: str,
    bootcamp_name: str,
    team_name: str,
    dry_run: bool = False,
    overwrite_existing: bool = False,
) -> str | None:
    """
    Create a Gemini API key in GCP.

    Parameters
    ----------
    project_id : str
        GCP project ID where the key will be created.
    bootcamp_name : str
        Name of the bootcamp.
    team_name : str
        Name of the team.
    dry_run : bool, optional
        If True, only simulate key creation.
    overwrite_existing : bool, optional
        If True, delete existing key with same name before creating new one.

    Returns
    -------
    str | None
        The API key resource name (e.g., projects/.../locations/.../keys/...)
        or None if dry_run is True.

    Raises
    ------
    APIKeyCreationError
        If key creation fails.
    """
    key_display_name = format_api_key_name(bootcamp_name, team_name, "gemini")

    # Check if key already exists
    existing_key = get_existing_api_key(project_id, key_display_name)
    if existing_key:
        result = _handle_existing_key(
            project_id, key_display_name, existing_key, overwrite_existing, dry_run
        )
        if result:
            return result

    if dry_run:
        console.print(
            f"  [blue]Would create[/blue] API key '{key_display_name}' in project '{project_id}'"
        )
        return None

    try:
        create_result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "services",
                "api-keys",
                "create",
                f"--project={project_id}",
                f"--display-name={key_display_name}",
                "--api-target=service=generativelanguage.googleapis.com",
                "--format=json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        response = json.loads(create_result.stdout)
        resource_name = response.get("name")

        if not resource_name:
            raise APIKeyCreationError(
                f"Failed to get resource name from response: {create_result.stdout}"
            )

        # Check if this is an operation (long-running) or the actual key
        if resource_name.startswith("operations/"):
            key_resource_name = _wait_for_operation_and_get_key(
                project_id, key_display_name, resource_name
            )
        else:
            key_resource_name = resource_name

        console.print(f"  [green]✓[/green] Created API key '{key_display_name}'")
        return key_resource_name

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        _handle_creation_error(error_msg, key_display_name, project_id)

    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        raise APIKeyCreationError(
            f"Failed to create API key '{key_display_name}': {e}"
        ) from e

    # This should never be reached due to the except blocks above
    return None


def get_api_key_string(key_resource_name: str, dry_run: bool = False) -> str | None:
    """
    Retrieve the API key string from GCP.

    Parameters
    ----------
    key_resource_name : str
        The API key resource name (from create_gemini_api_key).
    dry_run : bool, optional
        If True, return a dummy key string.

    Returns
    -------
    str | None
        The API key string or None if retrieval fails.

    Raises
    ------
    APIKeyCreationError
        If key string retrieval fails.
    """
    if dry_run:
        return "AIza-dry-run-key-string"

    try:
        result = subprocess.run(
            [
                "gcloud",
                "alpha",
                "services",
                "api-keys",
                "get-key-string",
                key_resource_name,
                "--format=value(keyString)",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )

        key_string = result.stdout.strip()

        if not key_string:
            raise APIKeyCreationError(
                f"Failed to retrieve key string for '{key_resource_name}'"
            )

        return key_string

    except subprocess.CalledProcessError as e:
        raise APIKeyCreationError(
            f"Failed to retrieve key string for '{key_resource_name}': {e.stderr}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise APIKeyCreationError(
            f"Timeout while retrieving key string for '{key_resource_name}'"
        ) from e


def _handle_retry_logic(attempt: int, error_msg: str) -> tuple[bool, str | None]:
    """Handle retry logic for validation attempts."""
    is_last_attempt = attempt >= VALIDATION_RETRIES - 1

    if not is_last_attempt:
        delay = RETRY_DELAYS[attempt]
        console.print(
            f"  [yellow]⚠[/yellow] Validation attempt {attempt + 1} failed "
            f"({error_msg}), retrying in {delay}s..."
        )
        time.sleep(delay)
        return True, None

    return False, f"{error_msg} after {VALIDATION_RETRIES} attempts"


def _perform_validation_request(api_key: str, attempt: int) -> tuple[bool, str | None]:
    """
    Perform a single validation request attempt.

    Returns tuple of (should_retry, error_message).
    If should_retry is False and error_message is None, validation succeeded.
    """
    try:
        response = requests.get(
            GEMINI_API_ENDPOINT,
            params={"key": api_key},
            timeout=VALIDATION_TIMEOUT,
        )

        if response.status_code == 200:
            return False, None  # Success

        # Non-retryable errors
        if response.status_code in (403, 400):
            error_msg = (
                "Permission denied" if response.status_code == 403 else "Invalid key"
            )
            return False, f"{error_msg} (HTTP {response.status_code})"

        # Retryable HTTP error
        return _handle_retry_logic(attempt, f"HTTP {response.status_code}")

    except requests.Timeout:
        return _handle_retry_logic(attempt, "Timeout")

    except requests.RequestException as e:
        return _handle_retry_logic(attempt, f"Network error: {e}")


def validate_gemini_api_key(
    api_key: str, skip_validation: bool = False, dry_run: bool = False
) -> tuple[bool, str]:
    """
    Validate that the API key works with the Gemini API.

    Parameters
    ----------
    api_key : str
        The API key to validate.
    skip_validation : bool, optional
        If True, skip validation and return success.
    dry_run : bool, optional
        If True, skip validation and return success.

    Returns
    -------
    tuple[bool, str]
        Tuple of (is_valid, status_message).
    """
    if dry_run or skip_validation:
        return True, "Validation skipped"

    masked_key = mask_sensitive_value(api_key)

    for attempt in range(VALIDATION_RETRIES):
        should_retry, error_message = _perform_validation_request(api_key, attempt)

        if error_message is None:
            # Success
            console.print(f"  [green]✓[/green] Validated API key {masked_key}")
            return True, "Valid"

        if not should_retry:
            # Non-retryable error
            return False, error_message

    return False, "Unknown error"


def update_team_with_key(
    db: FirestoreClient,
    team_name: str,
    api_key: str,
    api_key_name: str,
    dry_run: bool = False,
) -> None:
    """
    Update team document in Firestore with the API key.

    Parameters
    ----------
    db : FirestoreClient
        Firestore client instance.
    team_name : str
        Name of the team.
    api_key : str
        The API key string.
    api_key_name : str
        Display name of the API key.
    dry_run : bool, optional
        If True, only simulate the update.

    Raises
    ------
    Exception
        If Firestore update fails.
    """
    if dry_run:
        console.print(f"  [blue]Would update[/blue] team '{team_name}' with API key")
        return

    try:
        team_ref = db.collection(COLLECTION_TEAMS).document(team_name)
        update_data = {
            "openai_api_key": api_key,
            "openai_api_key_name": api_key_name,
            "updated_at": datetime.now(timezone.utc),
        }
        team_ref.update(update_data)
        console.print(f"  [green]✓[/green] Updated team '{team_name}' in Firestore")
    except Exception as e:
        raise Exception(f"Failed to update team '{team_name}' in Firestore: {e}") from e


def should_process_team(
    project_id: str,
    bootcamp_name: str,
    team_name: str,
    overwrite_existing: bool = False,
) -> tuple[bool, str]:
    """
    Check if a team should be processed for API key creation.

    Checks if the key exists in GCP, not in Firestore.

    Parameters
    ----------
    project_id : str
        GCP project ID where keys are created.
    bootcamp_name : str
        Name of the bootcamp.
    team_name : str
        Name of the team.
    overwrite_existing : bool, optional
        If True, process team even if it has an existing key in GCP.

    Returns
    -------
    tuple[bool, str]
        Tuple of (should_process, reason).
    """
    key_display_name = format_api_key_name(bootcamp_name, team_name, "gemini")
    existing_key = get_existing_api_key(project_id, key_display_name)

    if existing_key and not overwrite_existing:
        return False, "Key already exists in GCP"

    if existing_key and overwrite_existing:
        return True, "Overwriting existing GCP key"

    return True, "No key in GCP"


def get_teams_to_process(
    db: FirestoreClient,
    bootcamp_name: str | None = None,
    team_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Get teams to process based on filters.

    Parameters
    ----------
    db : FirestoreClient
        Firestore client instance.
    bootcamp_name : str | None, optional
        Filter teams by bootcamp name.
    team_names : list[str] | None, optional
        Filter to specific team names.

    Returns
    -------
    list[dict[str, Any]]
        List of team documents to process.
    """
    teams_ref = db.collection(COLLECTION_TEAMS)

    # If specific teams are requested
    if team_names:
        teams = []
        for team_name in team_names:
            team_ref = teams_ref.document(team_name)
            doc = team_ref.get()
            if doc.exists:
                team_data = doc.to_dict()
                if team_data:
                    team_data["id"] = doc.id
                    teams.append(team_data)
            else:
                console.print(
                    f"[yellow]⚠ Warning:[/yellow] Team '{team_name}' not found in Firestore"
                )
        return teams

    # Get all teams
    teams = []
    for doc in teams_ref.stream():
        team_data = doc.to_dict()
        if team_data:
            team_data["id"] = doc.id

            # Filter by bootcamp if specified
            if bootcamp_name:
                team_bootcamp = team_data.get("bootcamp_name", "")
                if team_bootcamp != bootcamp_name:
                    continue

            teams.append(team_data)

    return teams


def _initialize_environment(
    project_id: str, bootcamp_name: str, dry_run: bool
) -> FirestoreClient | int:
    """
    Initialize and validate the environment for key creation.

    Returns FirestoreClient on success, or exit code (int) on failure.
    """
    # Validate bootcamp name format
    if not validate_team_name(bootcamp_name):
        console.print(
            f"[red]✗[/red] Invalid bootcamp name '{bootcamp_name}'. "
            "Must contain only alphanumeric characters, hyphens, and underscores."
        )
        return 1

    if dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo changes will be made",
                border_style="yellow",
            )
        )
        console.print()

    # Validate prerequisites
    console.print("[cyan]Validating prerequisites...[/cyan]")
    try:
        validate_prerequisites(project_id)
    except PrerequisiteError as e:
        console.print(f"[red]✗ Prerequisite check failed:[/red] {e}")
        return 1
    console.print()

    # Initialize Firestore client
    try:
        console.print("[cyan]Connecting to Firestore...[/cyan]")
        db = get_firestore_client()
        console.print("[green]✓ Connected to Firestore[/green]")
        console.print()
        return db
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return 1


def _process_single_team(
    team: dict[str, Any],
    project_id: str,
    bootcamp_name: str,
    db: FirestoreClient,
    overwrite_existing: bool,
    skip_validation: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """
    Process a single team for API key creation.

    Returns a dict with 'status' and relevant data for the result.
    """
    team_name = team.get("team_name") or team.get("id", "unknown")

    # Check if team should be processed (check GCP, not Firestore)
    should_process, reason = should_process_team(
        project_id, bootcamp_name, team_name, overwrite_existing
    )

    if not should_process:
        console.print(f"  [dim]Skipped '{team_name}': {reason}[/dim]")
        return {"status": "skipped", "team": team_name, "reason": reason}

    # Create API key
    try:
        key_display_name = format_api_key_name(bootcamp_name, team_name, "gemini")
        key_resource_name = create_gemini_api_key(
            project_id,
            bootcamp_name,
            team_name,
            dry_run=dry_run,
            overwrite_existing=overwrite_existing,
        )

        if dry_run:
            return {
                "status": "success",
                "team": team_name,
                "key": "dry-run",
                "validation_status": "Dry run",
            }

        # Type check: key_resource_name should not be None at this point
        if key_resource_name is None:
            raise APIKeyCreationError("Key resource name is None after creation")

        # Get key string
        api_key_result = get_api_key_string(key_resource_name, dry_run=dry_run)
        if not api_key_result:
            raise APIKeyCreationError("Failed to retrieve API key string")

        # Type narrowing: api_key_result is now str, not str | None
        api_key: str = api_key_result

        # Validate key
        is_valid, validation_status = validate_gemini_api_key(
            api_key, skip_validation=skip_validation, dry_run=dry_run
        )

        if not is_valid:
            console.print(
                f"  [yellow]⚠[/yellow] Warning: Key validation failed for '{team_name}': {validation_status}"
            )

        # Update Firestore
        update_team_with_key(
            db,
            team_name,
            api_key,
            key_display_name,
            dry_run=dry_run,
        )

        return {
            "status": "success",
            "team": team_name,
            "key": mask_sensitive_value(api_key),
            "validation_status": validation_status,
        }

    except (APIKeyCreationError, APIKeyValidationError, Exception) as e:
        console.print(f"  [red]✗ Failed for '{team_name}':[/red] {e}")
        return {"status": "failed", "team": team_name, "error": str(e)}


def create_gemini_keys_for_teams(  # noqa: PLR0913
    project_id: str,
    bootcamp_name: str,
    dry_run: bool = False,
    skip_validation: bool = False,
    overwrite_existing: bool = False,
    team_names: list[str] | None = None,
) -> int:
    """
    Create Gemini API keys for teams.

    Parameters
    ----------
    project_id : str
        GCP project ID where keys will be created.
    bootcamp_name : str
        Name of the bootcamp.
    dry_run : bool, optional
        If True, validate and show what would be done without making changes.
    skip_validation : bool, optional
        If True, skip API key validation against Gemini API.
    overwrite_existing : bool, optional
        If True, recreate keys for teams that already have them.
    team_names : list[str] | None, optional
        Filter to specific team names.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Create Gemini API Keys[/bold cyan]\n"
            "Automatically create and configure Gemini API keys for teams",
            border_style="cyan",
        )
    )
    console.print()

    # Initialize environment
    db_or_exit = _initialize_environment(project_id, bootcamp_name, dry_run)
    if isinstance(db_or_exit, int):
        return db_or_exit
    db = db_or_exit

    # Get teams to process
    console.print("[cyan]Fetching teams...[/cyan]")
    teams = get_teams_to_process(db, bootcamp_name=None, team_names=team_names)

    if not teams:
        console.print("[yellow]⚠ No teams found to process[/yellow]")
        return 0

    console.print(f"[green]✓ Found {len(teams)} team(s)[/green]")
    console.print()

    # Process teams
    results: dict[str, list[dict[str, Any]]] = {
        "success": [],
        "skipped": [],
        "failed": [],
    }

    console.print(f"[bold]Processing {len(teams)} team(s)...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Creating API keys...", total=len(teams))

        for team in teams:
            result = _process_single_team(
                team,
                project_id,
                bootcamp_name,
                db,
                overwrite_existing,
                skip_validation,
                dry_run,
            )

            if result["status"] == "success":
                results["success"].append(
                    {
                        "team": result["team"],
                        "key": result["key"],
                        "status": result["validation_status"],
                    }
                )
            elif result["status"] == "skipped":
                results["skipped"].append(
                    {"team": result["team"], "reason": result["reason"]}
                )
            else:  # failed
                results["failed"].append(
                    {"team": result["team"], "error": result["error"]}
                )

            progress.update(task, advance=1)

    console.print()

    # Display summary
    display_results_summary(results, dry_run=dry_run)

    return 1 if results["failed"] else 0


def display_results_summary(
    results: dict[str, list[dict]], dry_run: bool = False
) -> None:
    """
    Display summary table of results.

    Parameters
    ----------
    results : dict[str, list[dict]]
        Dictionary with 'success', 'skipped', and 'failed' lists.
    dry_run : bool, optional
        If True, display dry run summary.
    """
    # Create summary table
    table = Table(
        title="Results Summary",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Team Name", style="yellow")
    table.add_column("Status", style="cyan")
    table.add_column("Details", style="dim")

    # Add successful teams
    for item in results["success"]:
        table.add_row(
            item["team"],
            "[green]✓ Success[/green]",
            f"Key: {item['key']}, Validation: {item['status']}",
        )

    # Add skipped teams
    for item in results["skipped"]:
        table.add_row(
            item["team"],
            "[dim]○ Skipped[/dim]",
            item["reason"],
        )

    # Add failed teams
    for item in results["failed"]:
        table.add_row(
            item["team"],
            "[red]✗ Failed[/red]",
            item["error"],
        )

    console.print(table)
    console.print()

    # Print final summary panel
    success_count = len(results["success"])
    skipped_count = len(results["skipped"])
    failed_count = len(results["failed"])
    total = success_count + skipped_count + failed_count

    if dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Total teams: {total}\n"
                f"Would create: {success_count}\n"
                f"Would skip: {skipped_count}\n"
                f"Would fail: {failed_count}\n\n"
                "[dim]No changes were made[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    elif failed_count > 0:
        console.print(
            Panel.fit(
                "[yellow]COMPLETED WITH ERRORS[/yellow]\n"
                f"Total teams: {total}\n"
                f"Success: {success_count}\n"
                f"Skipped: {skipped_count}\n"
                f"Failed: {failed_count}\n\n"
                "[dim]Review errors above for details[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[green]ALL TEAMS PROCESSED[/green]\n"
                f"Total teams: {total}\n"
                f"Success: {success_count}\n"
                f"Skipped: {skipped_count}",
                border_style="green",
                title="✓ Success",
            )
        )
