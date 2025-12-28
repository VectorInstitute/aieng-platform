#!/usr/bin/env python3
"""
Verify Firestore setup for bootcamp onboarding.

This script validates the Firestore database setup by checking:
- Global keys are present and complete
- Teams exist with required fields and API keys
- Participants exist and reference valid teams
- No orphaned data or inconsistencies
"""

import argparse
import sys
from typing import Any

from google.cloud import firestore  # type: ignore[attr-defined]
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from utils import (
    COLLECTION_GLOBAL_KEYS,
    COLLECTION_PARTICIPANTS,
    COLLECTION_TEAMS,
    GLOBAL_KEYS_DOC_ID,
    console,
    get_firestore_client,
)


class VerificationReport:
    """Container for verification results."""

    def __init__(self) -> None:
        """Initialize verification report."""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []
        self.teams_count: int = 0
        self.participants_count: int = 0
        self.teams_with_keys: int = 0
        self.teams_without_keys: int = 0
        self.onboarded_participants: int = 0

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def add_info(self, message: str) -> None:
        """Add an info message."""
        self.info.append(message)

    def is_valid(self) -> bool:
        """Check if setup is valid (no errors)."""
        return len(self.errors) == 0

    def print_statistics(self) -> None:
        """Print statistics in a table."""
        table = Table(title="Statistics", show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Teams", str(self.teams_count))
        table.add_row("Participants", str(self.participants_count))
        table.add_row(
            "Teams with API keys",
            f"{self.teams_with_keys}/{self.teams_count}",
        )
        table.add_row(
            "Onboarded participants",
            f"{self.onboarded_participants}/{self.participants_count}",
        )

        console.print()
        console.print(table)
        console.print()

    def print_issues(self) -> None:
        """Print warnings and errors as a tree."""
        if not self.warnings and not self.errors:
            console.print("[green]✓ No issues found[/green]\n")
            return

        tree = Tree("[bold]Issues Found[/bold]")

        if self.errors:
            errors_branch = tree.add(
                f"[red bold]Errors ({len(self.errors)})[/red bold]"
            )
            for error in self.errors:
                errors_branch.add(f"[red]✗ {error}[/red]")

        if self.warnings:
            warnings_branch = tree.add(
                f"[yellow bold]Warnings ({len(self.warnings)})[/yellow bold]"
            )
            for warning in self.warnings:
                warnings_branch.add(f"[yellow]⚠  {warning}[/yellow]")

        console.print()
        console.print(tree)
        console.print()

    def print_report(self) -> None:
        """Print the complete verification report."""
        console.print()
        console.print(
            Panel.fit(
                "[bold cyan]Verification Report[/bold cyan]",
                border_style="cyan",
            )
        )

        # Statistics
        self.print_statistics()

        # Issues
        self.print_issues()

        # Final verdict
        if self.is_valid():
            console.print(
                Panel.fit(
                    "[green bold]✓ VERIFICATION PASSED[/green bold]\n"
                    "Firestore setup is valid and ready for use",
                    border_style="green",
                    title="Success",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[red bold]✗ VERIFICATION FAILED[/red bold]\n"
                    f"Found {len(self.errors)} error(s) and {len(self.warnings)} warning(s)\n\n"
                    "[dim]Please fix the errors above before proceeding[/dim]",
                    border_style="red",
                    title="Failed",
                )
            )


def verify_global_keys(db: firestore.Client, report: VerificationReport) -> None:
    """
    Verify global keys are present and complete.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    report : VerificationReport
        Report object to add findings to.
    """
    console.print("[cyan]Checking global keys...[/cyan]")

    doc_ref = db.collection(COLLECTION_GLOBAL_KEYS).document(GLOBAL_KEYS_DOC_ID)
    doc = doc_ref.get()

    if not doc.exists:
        report.add_error("Global keys document does not exist")
        console.print("  [red]✗ Global keys document not found[/red]")
        return

    keys = doc.to_dict()

    required_keys = [
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "WEAVIATE_API_KEY",
        "WEAVIATE_HTTP_HOST",
        "WEAVIATE_GRPC_HOST",
        "WEAVIATE_HTTP_PORT",
        "WEAVIATE_GRPC_PORT",
        "WEAVIATE_HTTP_SECURE",
        "WEAVIATE_GRPC_SECURE",
        "LANGFUSE_HOST",
    ]

    missing = []
    for key in required_keys:
        if key not in keys or not keys[key]:
            report.add_error(f"Global key missing or empty: {key}")
            missing.append(key)

    if missing:
        console.print(f"  [red]✗ Missing {len(missing)} required keys[/red]")
    else:
        report.add_info("All global keys are present")
        console.print("  [green]✓ All required keys present[/green]")


def verify_teams(
    db: firestore.Client, report: VerificationReport
) -> dict[str, dict[str, Any]]:
    """
    Verify teams collection.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    report : VerificationReport
        Report object to add findings to.

    Returns
    -------
    dict[str, dict[str, Any]]
        Dictionary mapping team names to team data.
    """
    console.print("[cyan]Checking teams...[/cyan]")

    teams_ref = db.collection(COLLECTION_TEAMS)
    teams = {}

    for doc in teams_ref.stream():
        team_data = doc.to_dict()
        team_name = team_data.get("team_name") if team_data else None

        if not team_name:
            report.add_error(f"Team document {doc.id} missing 'team_name' field")
            continue

        teams[team_name] = team_data
        report.teams_count += 1

        # Check required fields
        required_fields = ["team_name", "participants", "created_at"]
        for field in required_fields:
            if field not in team_data:
                report.add_error(f"Team '{team_name}' missing required field: {field}")

        # Check if team has API key
        if "openai_api_key" in team_data and team_data["openai_api_key"]:
            report.teams_with_keys += 1
        else:
            report.teams_without_keys += 1
            report.add_warning(f"Team '{team_name}' does not have an API key")

        # Check participants field
        if "participants" in team_data:
            if not isinstance(team_data["participants"], list):
                report.add_error(f"Team '{team_name}' participants field is not a list")
            elif len(team_data["participants"]) == 0:
                report.add_warning(f"Team '{team_name}' has no participants")

    if report.teams_count == 0:
        report.add_error("No teams found in Firestore")
        console.print("  [red]✗ No teams found[/red]")
    else:
        report.add_info(f"Found {report.teams_count} teams")
        console.print(f"  [green]✓ Found {report.teams_count} teams[/green]")

    return teams


def verify_participants(  # noqa: PLR0912
    db: firestore.Client, teams: dict[str, dict[str, Any]], report: VerificationReport
) -> None:
    """
    Verify participants collection.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    teams : dict[str, dict[str, Any]]
        Dictionary of valid teams.
    report : VerificationReport
        Report object to add findings to.
    """
    console.print("[cyan]Checking participants...[/cyan]")

    participants_ref = db.collection(COLLECTION_PARTICIPANTS)
    team_participant_counts: dict[str, int] = dict.fromkeys(teams, 0)

    for doc in participants_ref.stream():
        participant_data = doc.to_dict()
        github_handle = (
            participant_data.get("github_handle") if participant_data else None
        )
        team_name = participant_data.get("team_name") if participant_data else None

        if not github_handle:
            report.add_error(
                f"Participant document {doc.id} missing 'github_handle' field"
            )
            continue

        report.participants_count += 1

        # Check required fields
        required_fields = ["github_handle", "team_name", "onboarded", "created_at"]
        for field in required_fields:
            if participant_data and field not in participant_data:
                report.add_error(
                    f"Participant '{github_handle}' missing required field: {field}"
                )

        # Check if team exists
        if team_name not in teams:
            report.add_error(
                f"Participant '{github_handle}' references non-existent team: {team_name}"
            )
        else:
            team_participant_counts[team_name] += 1

        # Check if participant is in team's participants list
        if team_name in teams:
            team_participants = teams[team_name].get("participants", [])
            if github_handle not in team_participants:
                report.add_warning(
                    f"Participant '{github_handle}' not in team '{team_name}' participants list"
                )

        # Count onboarded participants
        if participant_data and participant_data.get("onboarded", False):
            report.onboarded_participants += 1

    # Check for teams with participants in their list but no participant documents
    for team_name, team_data in teams.items():
        team_participants = team_data.get("participants", [])
        actual_count = team_participant_counts.get(team_name, 0)

        if len(team_participants) != actual_count:
            report.add_warning(
                f"Team '{team_name}' has {len(team_participants)} participants in list "
                f"but {actual_count} participant documents"
            )

    if report.participants_count == 0:
        report.add_warning("No participants found in Firestore")
        console.print("  [yellow]⚠  No participants found[/yellow]")
    else:
        report.add_info(f"Found {report.participants_count} participants")
        console.print(
            f"  [green]✓ Found {report.participants_count} participants[/green]"
        )


def display_team_summary(teams: dict[str, dict[str, Any]]) -> None:
    """
    Display a summary table of teams.

    Parameters
    ----------
    teams : dict[str, dict[str, Any]]
        Dictionary of team data.
    """
    if not teams:
        return

    table = Table(title="Team Summary", show_header=True, header_style="bold cyan")
    table.add_column("Team Name", style="yellow")
    table.add_column("Participants", justify="right", style="green")
    table.add_column("Has API Key", justify="center")

    for team_name, team_data in sorted(teams.items()):
        participant_count = len(team_data.get("participants", []))
        has_key = "✓" if team_data.get("openai_api_key") else "✗"
        key_style = "green" if team_data.get("openai_api_key") else "red"

        table.add_row(
            team_name, str(participant_count), f"[{key_style}]{has_key}[/{key_style}]"
        )

    console.print()
    console.print(table)
    console.print()


def main() -> int:
    """
    Verify Firestore setup for bootcamp onboarding.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Verify Firestore setup for bootcamp onboarding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    parser.add_argument(
        "--show-teams",
        action="store_true",
        help="Show detailed team summary",
    )

    args = parser.parse_args()

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Firestore Setup Verification[/bold cyan]\n"
            "Validate bootcamp onboarding database configuration",
            border_style="cyan",
        )
    )

    # Initialize Firestore client
    try:
        console.print("\n[cyan]Connecting to Firestore...[/cyan]")
        db = get_firestore_client()
        console.print("[green]✓ Connected to Firestore[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return 1

    # Create report
    report = VerificationReport()

    console.print("[bold]Running Verification Checks[/bold]\n")

    # Run verifications
    verify_global_keys(db, report)
    teams = verify_teams(db, report)
    verify_participants(db, teams, report)

    # Show team summary if requested
    if args.show_teams and teams:
        display_team_summary(teams)

    # Print report
    report.print_report()

    # Determine exit code
    if not report.is_valid():
        return 1

    if args.strict and report.warnings:
        console.print(
            Panel(
                "[yellow]STRICT MODE: Treating warnings as errors[/yellow]",
                border_style="yellow",
            )
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
