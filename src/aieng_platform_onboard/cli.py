#!/usr/bin/env python3
"""
Participant onboarding CLI.

This module provides the command-line interface for bootcamp participant
onboarding, authenticating participants, fetching their team's API keys
from Firestore, creating a .env file, running integration tests, and marking
them as onboarded.
"""

import argparse
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.table import Table

from aieng_platform_onboard.utils import (
    check_onboarded_status,
    console,
    create_env_file,
    fetch_token_from_service,
    get_all_participants_with_status,
    get_github_user,
    get_global_keys,
    get_participant_data,
    get_team_data,
    initialize_firestore_admin,
    initialize_firestore_with_token,
    update_onboarded_status,
    validate_env_file,
)


def get_version() -> str:
    """
    Get the installed version of the package.

    Returns
    -------
    str
        Version string from package metadata.
    """
    try:
        return version("aieng-platform-onboard")
    except Exception:
        return "unknown"


def run_integration_test(test_script: Path) -> tuple[bool, str]:
    """
    Execute integration test script to verify API keys.

    Parameters
    ----------
    test_script : Path
        Path to the test script.

    Returns
    -------
    tuple[bool, str]
        Tuple of (success, output/error).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr if result.stderr else result.stdout

    except subprocess.TimeoutExpired:
        return False, "Test timed out after 60 seconds"
    except Exception as e:
        return False, str(e)


def _authenticate_and_connect(
    bootcamp_name: str,
    gcp_project: str,
    firebase_api_key: str | None,
) -> tuple[str, Any] | tuple[None, None]:
    """
    Authenticate participant and connect to Firestore.

    Parameters
    ----------
    bootcamp_name : str
        Name of the bootcamp.
    gcp_project : str
        GCP project ID.
    firebase_api_key : str | None
        Firebase Web API key.

    Returns
    -------
    tuple[str, any] | tuple[None, None]
        Tuple of (github_user, firestore_client) or (None, None) on failure.
    """
    # Step 1: Get GitHub username
    console.print("\n[bold]Step 1: Identify Participant[/bold]")
    github_user = get_github_user()

    if not github_user:
        console.print(
            "[red]✗ Could not determine GitHub username[/red]\n"
            "  Please set the GITHUB_USER environment variable"
        )
        return None, None

    console.print(f"[green]✓ GitHub User:[/green] {github_user}\n")

    # Step 2: Fetch authentication token
    console.print("[bold]Step 2: Fetch Authentication Token[/bold]")
    console.print("[cyan]Fetching fresh token from service...[/cyan]")
    success, token, error = fetch_token_from_service(github_user)

    if not success or not token:
        console.print(
            f"[red]✗ Failed to fetch authentication token:[/red]\n"
            f"  {error}\n\n"
            "[yellow]Possible reasons:[/yellow]\n"
            "  • Token service not deployed or misconfigured\n"
            "  • Missing permissions\n"
            "  • Participant not found in Firestore\n\n"
            "[dim]Contact bootcamp admin for assistance[/dim]"
        )
        return None, None

    console.print("[green]✓ Authentication token retrieved[/green]\n")

    # Step 3: Connect to Firestore
    console.print("[bold]Step 3: Connect to Firestore[/bold]")
    console.print("[cyan]Initializing secure Firestore connection...[/cyan]")

    try:
        db = initialize_firestore_with_token(
            token,
            gcp_project,
            "onboarding",
            firebase_api_key=firebase_api_key,
        )
        console.print("[green]✓ Connected to Firestore[/green]\n")
        return github_user, db
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return None, None


def _fetch_participant_and_team_data(
    db: Any, github_user: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | tuple[None, None, None]:
    """
    Fetch participant, team, and global configuration data.

    Parameters
    ----------
    db : any
        Firestore client instance.
    github_user : str
        GitHub username.

    Returns
    -------
    tuple[dict, dict, dict] | tuple[None, None, None]
        Tuple of (participant_data, team_data, global_keys) or (None, None, None).
    """
    # Step 4: Fetch participant data
    console.print("[bold]Step 4: Fetch Your Profile[/bold]")
    console.print("[cyan]Reading participant data...[/cyan]")

    participant_data = get_participant_data(db, github_user)

    if not participant_data:
        console.print(
            f"[red]✗ Participant profile not found for '{github_user}'[/red]\n"
            "[dim]Contact bootcamp admin to add you to the participant list[/dim]"
        )
        return None, None, None

    team_name = participant_data.get("team_name")
    if not team_name:
        console.print("[red]✗ No team assigned to your profile[/red]")
        return None, None, None

    console.print("[green]✓ Profile found[/green]")
    console.print(f"  Team: [yellow]{team_name}[/yellow]\n")

    # Step 5: Fetch team data (includes API keys)
    console.print("[bold]Step 5: Fetch Team API Keys[/bold]")
    console.print(f"[cyan]Reading team data for '{team_name}'...[/cyan]")

    team_data = get_team_data(db, team_name)

    if not team_data:
        console.print(
            f"[red]✗ Team data not found for '{team_name}'[/red]\n"
            "[dim]Contact bootcamp admin[/dim]"
        )
        return None, None, None

    # Check if team has required keys
    missing_keys = []
    if not team_data.get("openai_api_key"):
        missing_keys.append("OPENAI_API_KEY (Gemini)")

    if missing_keys:
        console.print(
            "[yellow]⚠ Warning: Team is missing some API keys:[/yellow]\n"
            f"  {', '.join(missing_keys)}\n"
            "[dim]Onboarding will continue, but some features may not work[/dim]\n"
        )

    console.print("[green]✓ Team API keys retrieved[/green]\n")

    # Step 6: Fetch global shared keys
    console.print("[bold]Step 6: Fetch Global Configuration[/bold]")
    console.print("[cyan]Reading shared keys...[/cyan]")

    global_keys = get_global_keys(db)

    if not global_keys:
        console.print(
            "[red]✗ Global keys not found[/red]\n[dim]Contact bootcamp admin[/dim]"
        )
        return None, None, None

    console.print("[green]✓ Global configuration retrieved[/green]\n")

    return participant_data, team_data, global_keys


def _setup_environment(
    output_dir: str, team_data: dict[str, Any], global_keys: dict[str, Any]
) -> Path | None:
    """
    Create .env file with API keys and configuration.

    Parameters
    ----------
    output_dir : str
        Directory where .env file should be created.
    team_data : dict[str, any]
        Team data containing API keys.
    global_keys : dict[str, any]
        Global configuration keys.

    Returns
    -------
    Path | None
        Path to created .env file or None on failure.
    """
    console.print("[bold]Step 7: Create Environment File[/bold]")
    output_path = Path(output_dir) / ".env"
    console.print(f"[cyan]Creating .env file at: {output_path}[/cyan]")

    if output_path.exists():
        console.print(
            "[yellow]⚠ .env file already exists, will be overwritten[/yellow]"
        )

    success_create = create_env_file(output_path, team_data, global_keys)

    if not success_create:
        console.print("[red]✗ Failed to create .env file[/red]")
        return None

    console.print("[green]✓ .env file created successfully[/green]\n")
    return output_path


def display_onboarding_status_report(gcp_project: str) -> int:
    """
    Display onboarding status report for all participants.

    This function is for admin use only and requires proper GCP service
    account credentials. It fetches all participants from Firestore and
    displays their onboarding status in a table.

    Parameters
    ----------
    gcp_project : str
        GCP project ID.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    console.print(
        Panel.fit(
            "[bold cyan]Onboarding Status Report[/bold cyan]\n"
            "Admin view of all participant onboarding status",
            border_style="cyan",
        )
    )

    # Initialize Firestore with admin credentials
    console.print("\n[cyan]Connecting to Firestore with admin credentials...[/cyan]")
    try:
        db = initialize_firestore_admin(project_id=gcp_project)
        console.print("[green]✓ Connected to Firestore[/green]\n")
    except Exception as e:
        console.print(
            f"[red]✗ Failed to connect to Firestore:[/red]\n"
            f"  {e}\n\n"
            "[yellow]This command requires admin (service account) credentials.[/yellow]\n"
            "[dim]Ensure you are authenticated with proper GCP permissions:[/dim]\n"
            "  gcloud auth application-default login\n"
            "  [dim]or have GOOGLE_APPLICATION_CREDENTIALS set[/dim]"
        )
        return 1

    # Fetch all participants
    console.print("[cyan]Fetching participant data...[/cyan]")
    try:
        participants = get_all_participants_with_status(db)
        console.print(f"[green]✓ Found {len(participants)} participants[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch participant data:[/red] {e}")
        return 1

    if not participants:
        console.print(
            Panel.fit(
                "[yellow]No participants found in Firestore[/yellow]\n\n"
                "[dim]Use admin scripts to add participants first[/dim]",
                border_style="yellow",
            )
        )
        return 0

    # Create and display status table
    table = Table(
        title="Participant Onboarding Status",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("GitHub Handle", style="yellow", no_wrap=True)
    table.add_column("Team Name", style="blue")
    table.add_column("Status", justify="center")

    # Count onboarded vs total
    onboarded_count = 0

    for participant in participants:
        github_handle = participant["github_handle"]
        team_name = participant["team_name"]
        is_onboarded = participant["onboarded"]

        if is_onboarded:
            onboarded_count += 1
            status = "[green]✓ Onboarded[/green]"
        else:
            status = "[red]✗ Not Onboarded[/red]"

        table.add_row(github_handle, team_name, status)

    console.print(table)
    console.print()

    # Display summary
    total_count = len(participants)
    not_onboarded_count = total_count - onboarded_count
    percentage = (onboarded_count / total_count * 100) if total_count > 0 else 0

    summary_text = (
        f"[bold]Onboarding Summary[/bold]\n\n"
        f"Total Participants: [cyan]{total_count}[/cyan]\n"
        f"Onboarded: [green]{onboarded_count}[/green]\n"
        f"Not Onboarded: [red]{not_onboarded_count}[/red]\n"
        f"Completion Rate: [yellow]{percentage:.1f}%[/yellow]"
    )

    console.print(
        Panel.fit(
            summary_text,
            border_style="cyan",
            title="Summary",
        )
    )

    return 0


def _run_tests_and_finalize(
    db: Any, github_user: str, skip_test: bool, test_script: str
) -> bool:
    """
    Run integration tests and update onboarded status.

    Parameters
    ----------
    db : any
        Firestore client instance.
    github_user : str
        GitHub username.
    skip_test : bool
        Whether to skip integration tests.
    test_script : str
        Path to the integration test script.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    # Step 8: Run integration test
    if not skip_test:
        console.print("[bold]Step 8: Run Integration Test[/bold]")
        console.print("[cyan]Testing API keys...[/cyan]")

        test_script_path = Path(test_script)

        if not test_script_path.exists():
            console.print(
                f"[red]✗ Test script not found at: {test_script_path}[/red]\n"
            )
            return False
        success_test, output = run_integration_test(test_script_path)

        if success_test:
            console.print("[green]✓ All API keys tested successfully[/green]\n")
        else:
            console.print(
                "[red]✗ Integration test failed:[/red]\n"
                f"[dim]{output}[/dim]\n\n"
                "[yellow]Your .env file was created, but some keys may not work.[/yellow]\n"
                "[dim]Contact bootcamp admin if you need assistance[/dim]\n"
            )
            return False
    else:
        console.print("[dim]Integration test skipped[/dim]\n")

    # Step 9: Update onboarded status
    console.print("[bold]Step 9: Mark as Onboarded[/bold]")
    console.print("[cyan]Updating your status...[/cyan]")

    success_update, error_update = update_onboarded_status(db, github_user)

    if not success_update:
        console.print(
            f"[yellow]⚠ Failed to update onboarded status:[/yellow] {error_update}\n"
            "[dim]Your .env file is ready to use, but status was not updated[/dim]\n"
        )
    else:
        console.print("[green]✓ Marked as onboarded[/green]\n")

    return True


def main() -> int:  # noqa: PLR0911
    """
    Onboard bootcamp participants with team-specific API keys.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Bootcamp participant onboarding script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
        help="Show version number and exit",
    )
    parser.add_argument(
        "--bootcamp-name",
        type=str,
        help="Name of the bootcamp (e.g., fall-2025)",
    )
    parser.add_argument(
        "--gcp-project",
        type=str,
        default="coderd",
        help="GCP project ID (default: coderd)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory where .env file should be created (default: current directory)",
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Skip integration test",
    )
    parser.add_argument(
        "--test-script",
        type=str,
        help="Path to integration test script",
    )
    parser.add_argument(
        "--firebase-api-key",
        type=str,
        help="Firebase Web API key for token exchange (or set FIREBASE_WEB_API_KEY env var)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-onboarding even if already onboarded",
    )
    parser.add_argument(
        "--admin-status-report",
        action="store_true",
        help="Display onboarding status for all participants (admin only, requires service account credentials)",
    )

    args = parser.parse_args()

    # Handle admin status report (early return)
    if args.admin_status_report:
        return display_onboarding_status_report(args.gcp_project)

    # Validate required arguments for normal onboarding flow
    if not args.bootcamp_name:
        parser.error("--bootcamp-name is required for participant onboarding")
    if not args.test_script:
        parser.error("--test-script is required for participant onboarding")

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Bootcamp Participant Onboarding[/bold cyan]\n"
            "Setup your environment with team-specific API keys",
            border_style="cyan",
        )
    )

    # Check if .env file already exists and is complete
    output_path = Path(args.output_dir) / ".env"
    if output_path.exists():
        console.print("\n[bold]Checking existing .env file...[/bold]")
        is_complete, missing = validate_env_file(output_path)

        if is_complete:
            console.print(
                "[green]✓ .env file is already complete with all required keys[/green]\n"
                f"[dim]Location: {output_path}[/dim]\n"
            )
            console.print(
                Panel.fit(
                    "[green bold]✓ ALREADY ONBOARDED[/green bold]\n\n"
                    "Your environment is already set up. No action needed.\n\n"
                    "[dim]To re-onboard, delete the .env file and run again.[/dim]",
                    border_style="green",
                    title="Success",
                )
            )
            return 0
        console.print(
            f"[yellow]⚠ .env file exists but is incomplete[/yellow]\n"
            f"[dim]Missing keys: {', '.join(missing)}[/dim]\n"
            "[cyan]Continuing with onboarding to regenerate .env file...[/cyan]\n"
        )

    # Authenticate and connect
    github_user, db = _authenticate_and_connect(
        args.bootcamp_name, args.gcp_project, args.firebase_api_key
    )
    if not github_user or not db:
        return 1

    # Check if already onboarded in Firestore
    console.print("[bold]Checking onboarded status...[/bold]")
    success_check, is_onboarded = check_onboarded_status(db, github_user)

    skip_onboarding = (
        success_check and is_onboarded and not args.force and output_path.exists()
    )
    if skip_onboarding:
        console.print(
            "[green]✓ You are already marked as onboarded in Firestore[/green]\n"
            "[yellow]Use --force to re-onboard anyway[/yellow]\n"
        )
        return 0

    if success_check and is_onboarded and not args.force:
        console.print(
            "[green]✓ You are already marked as onboarded in Firestore[/green]\n"
            "[cyan]But .env file is missing, continuing to create it...[/cyan]\n"
        )

    # Fetch data
    participant_data, team_data, global_keys = _fetch_participant_and_team_data(
        db, github_user
    )
    if not participant_data or not team_data or not global_keys:
        return 1

    # Setup environment
    env_output_path = _setup_environment(args.output_dir, team_data, global_keys)
    if not env_output_path:
        return 1
    output_path = env_output_path

    # Run tests and finalize
    if not _run_tests_and_finalize(db, github_user, args.skip_test, args.test_script):
        return 1

    # Final summary
    console.print(
        Panel.fit(
            "[green bold]✓ ONBOARDING COMPLETE[/green bold]\n\n"
            f"Your .env file is ready at: [cyan]{output_path}[/cyan]\n\n"
            "[bold]Next steps:[/bold]\n"
            "1. Source the environment file:\n"
            f"   [cyan]source {output_path}[/cyan]\n"
            "2. Start building!\n\n"
            "[dim]If you encounter any issues, contact your bootcamp admin[/dim]",
            border_style="green",
            title="Success",
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
