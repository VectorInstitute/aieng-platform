#!/usr/bin/env python3
"""
Generate Gemini API keys for each team.

This script creates Google Cloud API keys for the Gemini API
(generativelanguage.googleapis.com) for each team in Firestore and stores
them in the team documents.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

from google.cloud import firestore  # type: ignore[attr-defined]
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from utils import (
    COLLECTION_TEAMS,
    console,
    format_api_key_name,
    get_all_teams,
    get_firestore_client,
)


def check_gcloud_auth() -> tuple[bool, str]:
    """
    Check if gcloud is authenticated and has the required permissions.

    Returns
    -------
    tuple[bool, str]
        Tuple of (is_authenticated, account_email).
    """
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        account = result.stdout.strip()
        return bool(account), account
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, ""


def create_api_key(  # noqa: PLR0911
    key_name: str, gcp_project: str, dry_run: bool = False
) -> tuple[bool, str | None, str | None]:
    """
    Create a new Google Cloud API key restricted to Gemini API.

    Parameters
    ----------
    key_name : str
        Display name for the API key.
    gcp_project : str
        GCP project ID where the key should be created.
    dry_run : bool, optional
        If True, only log what would be done without creating the key.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, api_key_value, error_message).
    """
    if dry_run:
        return True, "dry-run-api-key-value", None

    try:
        # Build the gcloud command
        cmd = [
            "gcloud",
            "services",
            "api-keys",
            "create",
            "--display-name",
            key_name,
            "--project",
            gcp_project,
            "--api-target",
            "service=generativelanguage.googleapis.com",
            "--format",
            "json",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60
        )

        # Parse the response to get the key name (resource path)
        response = json.loads(result.stdout)
        key_resource_name = response.get("name")

        if not key_resource_name:
            return False, None, "Failed to get key resource name from response"

        # Get the actual key string value (with retry for eventual consistency)
        get_key_cmd = [
            "gcloud",
            "services",
            "api-keys",
            "get-key-string",
            key_resource_name,
            "--project",
            gcp_project,
            "--format",
            "value(keyString)",
        ]

        # Retry up to 3 times with delays to handle eventual consistency
        max_retries = 3
        for attempt in range(max_retries):
            try:
                key_result = subprocess.run(
                    get_key_cmd, capture_output=True, text=True, check=True, timeout=30
                )
                api_key = key_result.stdout.strip()

                if api_key:
                    return True, api_key, None

                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
                else:
                    error_msg = e.stderr if e.stderr else str(e)
                    return False, None, f"gcloud command failed: {error_msg}"

        return False, None, "Failed to retrieve key string after retries"

    except subprocess.TimeoutExpired:
        return False, None, "Command timed out"
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        return False, None, f"gcloud command failed: {error_msg}"
    except json.JSONDecodeError as e:
        return False, None, f"Failed to parse gcloud response: {e}"
    except Exception as e:
        return False, None, f"Unexpected error: {e}"


def check_if_key_exists(key_name: str, gcp_project: str) -> str | None:
    """
    Check if an API key with the given display name already exists.

    Parameters
    ----------
    key_name : str
        Display name of the API key to check.
    gcp_project : str
        GCP project ID to check in.

    Returns
    -------
    str | None
        Key resource name if exists, None otherwise.
    """
    try:
        cmd = [
            "gcloud",
            "services",
            "api-keys",
            "list",
            "--project",
            gcp_project,
            "--filter",
            f"displayName={key_name}",
            "--format",
            "value(name)",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )

        key_resource = result.stdout.strip()
        return key_resource if key_resource else None

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def retrieve_existing_key(
    key_resource_name: str, gcp_project: str
) -> tuple[bool, str | None, str | None]:
    """
    Retrieve the key string value for an existing API key.

    Parameters
    ----------
    key_resource_name : str
        The resource name (path) of the API key.
    gcp_project : str
        GCP project ID where the key exists.

    Returns
    -------
    tuple[bool, str | None, str | None]
        Tuple of (success, api_key_value, error_message).
    """
    try:
        cmd = [
            "gcloud",
            "services",
            "api-keys",
            "get-key-string",
            key_resource_name,
            "--project",
            gcp_project,
            "--format",
            "value(keyString)",
        ]

        # Retry up to 3 times with delays to handle eventual consistency
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=True, timeout=30
                )
                api_key = result.stdout.strip()

                if api_key:
                    return True, api_key, None

                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
                else:
                    error_msg = e.stderr if e.stderr else str(e)
                    return False, None, f"gcloud command failed: {error_msg}"

        return False, None, "Failed to retrieve key string after retries"

    except subprocess.TimeoutExpired:
        return False, None, "Command timed out"
    except Exception as e:
        return False, None, f"Unexpected error: {e}"


def generate_keys_for_teams(  # noqa: PLR0912, PLR0915
    db: firestore.Client,
    bootcamp_name: str,
    gcp_project: str,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[int, int, list[dict]]:
    """
    Generate Gemini API keys for all teams.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    bootcamp_name : str
        Name of the bootcamp for key naming.
    gcp_project : str
        GCP project ID for creating keys.
    dry_run : bool, optional
        If True, only log what would be done without making changes.
    force : bool, optional
        If True, create new keys even if team already has one.

    Returns
    -------
    tuple[int, int, list[dict]]
        Tuple of (successful_count, failed_count, results_list).
    """
    teams = get_all_teams(db)

    if not teams:
        console.print("[yellow]No teams found in Firestore[/yellow]")
        return 0, 0, []

    success_count = 0
    failed_count = 0
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Generating API keys for teams...", total=len(teams)
        )

        for team in teams:
            team_name = team["team_name"]
            team_id = team["id"]
            result = {"team": team_name, "status": "pending", "message": ""}

            # Check if team already has an API key
            if not force and "openai_api_key" in team and team["openai_api_key"]:
                console.print(
                    f"  [dim]• {team_name}: Already has API key (skipping)[/dim]"
                )
                result["status"] = "skipped"
                result["message"] = "Already has API key"
                success_count += 1
                results.append(result)
                progress.update(task, advance=1)
                continue

            # Format the key name
            key_name = format_api_key_name(bootcamp_name, team_name, "gemini")

            # Check if key already exists in GCP
            existing_key_resource = None
            if not dry_run:
                existing_key_resource = check_if_key_exists(key_name, gcp_project)

            if existing_key_resource:
                # Key exists in GCP but not in Firestore - retrieve and sync it
                console.print(
                    f"  [yellow]• {team_name}: Key '{key_name}' exists in GCP, "
                    f"syncing to Firestore[/yellow]"
                )
                success, api_key, error = retrieve_existing_key(
                    existing_key_resource, gcp_project
                )

                if not success or not api_key:
                    console.print(
                        f"  [red]✗ {team_name}: Failed to retrieve existing key[/red]"
                    )
                    if error:
                        console.print(f"    [dim]{error}[/dim]")
                    result["status"] = "failed"
                    result["message"] = error or "Failed to retrieve existing key"
                    failed_count += 1
                    results.append(result)
                    progress.update(task, advance=1)
                    continue
            else:
                # Create the API key
                success, api_key, error = create_api_key(key_name, gcp_project, dry_run)

                if not success or not api_key:
                    console.print(
                        f"  [red]✗ {team_name}: Failed to create API key[/red]"
                    )
                    if error:
                        console.print(f"    [dim]{error}[/dim]")
                    result["status"] = "failed"
                    result["message"] = error or "Unknown error"
                    failed_count += 1
                    results.append(result)
                    progress.update(task, advance=1)
                    continue

            # Update Firestore with the key (either new or existing)
            action_verb = "sync" if existing_key_resource else "create"
            if dry_run:
                console.print(
                    f"  [blue]• {team_name}: Would {action_verb} key '{key_name}'[/blue]"
                )
                result["status"] = "dry_run"
                result["message"] = f"Would {action_verb} key: {key_name}"
            else:
                try:
                    team_ref = db.collection(COLLECTION_TEAMS).document(team_id)
                    team_ref.update(
                        {
                            "openai_api_key": api_key,
                            "openai_api_key_name": key_name,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                    action_past = "Synced" if existing_key_resource else "Created"
                    console.print(
                        f"  [green]✓ {team_name}: {action_past} '{key_name}'[/green]"
                    )
                    result["status"] = "success"
                    result["message"] = f"{action_past} key: {key_name}"
                except Exception as e:
                    console.print(
                        f"  [red]✗ {team_name}: Failed to update Firestore[/red]"
                    )
                    console.print(f"    [dim]{e}[/dim]")
                    result["status"] = "failed"
                    result["message"] = f"Firestore update failed: {e}"
                    failed_count += 1
                    results.append(result)
                    progress.update(task, advance=1)
                    continue

            success_count += 1
            results.append(result)
            progress.update(task, advance=1)

    return success_count, failed_count, results


def display_results_table(results: list[dict]) -> None:
    """
    Display results in a formatted table.

    Parameters
    ----------
    results : list[dict]
        List of result dictionaries.
    """
    table = Table(
        title="Key Generation Results", show_header=True, header_style="bold cyan"
    )
    table.add_column("Team", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for result in results:
        status_icon = {
            "success": "[green]✓ Success[/green]",
            "skipped": "[dim]• Skipped[/dim]",
            "failed": "[red]✗ Failed[/red]",
            "dry_run": "[blue]• Dry Run[/blue]",
        }.get(result["status"], "[dim]Unknown[/dim]")

        table.add_row(result["team"], status_icon, result["message"])

    console.print()
    console.print(table)
    console.print()


def main() -> int:
    """
    Generate Gemini API keys for teams.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Generate Gemini API keys for each team in Firestore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "bootcamp_name",
        type=str,
        help="Name of the bootcamp (used in API key naming: {bootcamp-name}-{team-name})",
    )
    parser.add_argument(
        "--gcp-project",
        type=str,
        required=True,
        help="GCP project ID where API keys should be created",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create new keys even if teams already have keys",
    )

    args = parser.parse_args()

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Gemini API Key Generator[/bold cyan]\n"
            "Create Google Cloud API keys for team-based Gemini access",
            border_style="cyan",
        )
    )

    # Validate bootcamp name format
    if not args.bootcamp_name.replace("-", "").replace("_", "").isalnum():
        console.print(
            "[red]✗ Bootcamp name must be alphanumeric with hyphens/underscores only[/red]"
        )
        return 1

    # Check gcloud authentication
    console.print("\n[cyan]Checking gcloud authentication...[/cyan]")
    is_authed, account = check_gcloud_auth()
    if not is_authed:
        console.print("[red]✗ Not authenticated with gcloud[/red]")
        console.print("  Please run: [bold]gcloud auth login[/bold]")
        return 1
    console.print(f"[green]✓ Authenticated as:[/green] {account}\n")

    if args.dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo API keys will be created or updated",
                border_style="yellow",
            )
        )

    # Initialize Firestore client
    try:
        console.print("[cyan]Connecting to Firestore...[/cyan]")
        db = get_firestore_client()
        console.print("[green]✓ Connected to Firestore[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return 1

    # Display configuration
    config_table = Table(show_header=False, box=None)
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="white")
    config_table.add_row("Bootcamp", args.bootcamp_name)
    config_table.add_row("GCP Project", args.gcp_project)
    config_table.add_row("Force Update", "Yes" if args.force else "No")
    console.print(config_table)
    console.print()

    # Generate keys for teams
    console.print("[bold]Generating API Keys[/bold]\n")
    success_count, failed_count, results = generate_keys_for_teams(
        db, args.bootcamp_name, args.gcp_project, dry_run=args.dry_run, force=args.force
    )

    # Display results table
    if results:
        display_results_table(results)

    # Final summary
    if args.dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Would process: {success_count} teams\n"
                f"Would fail: {failed_count} teams\n\n"
                "[dim]No changes were made[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    elif failed_count == 0:
        console.print(
            Panel.fit(
                "[green]ALL KEYS GENERATED SUCCESSFULLY[/green]\n"
                f"Successful: {success_count}\n"
                f"Failed: {failed_count}",
                border_style="green",
                title="✓ Success",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[yellow]COMPLETED WITH FAILURES[/yellow]\n"
                f"Successful: {success_count}\n"
                f"Failed: {failed_count}\n\n"
                "[dim]Review the errors above and retry failed teams[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
