#!/usr/bin/env python3
"""
Setup teams in Firestore from CSV file.

This script reads a CSV file containing team names and creates
team documents in Firestore.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import firestore
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from utils import (
    COLLECTION_TEAMS,
    console,
    get_firestore_client,
    validate_team_name,
)


def read_teams_from_csv(csv_path: Path) -> tuple[list[str], list[str]]:
    """
    Read team names from CSV file.

    Parameters
    ----------
    csv_path : Path
        Path to the CSV file.

    Returns
    -------
    tuple[list[str], list[str]]
        Tuple of (team_names, errors).
    """
    if not csv_path.exists():
        return [], [f"CSV file not found: {csv_path}"]

    team_names = []
    errors = []

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [name.lower() for name in reader.fieldnames]

            for row_num, csv_row in enumerate(reader, start=2):
                row = {k.lower(): v for k, v in csv_row.items()}

                if "team_name" not in row and "team-name" not in row:
                    errors.append(
                        f"Row {row_num}: Missing 'team_name' or 'team-name' column"
                    )
                    continue

                team_name = row.get("team_name") or row.get("team-name", "")
                team_name = team_name.strip()

                if not team_name:
                    errors.append(f"Row {row_num}: team_name cannot be empty")
                    continue

                if not validate_team_name(team_name):
                    errors.append(f"Row {row_num}: Invalid team_name '{team_name}'")
                    continue

                team_names.append(team_name)

    except Exception as e:
        errors.append(f"Error reading CSV file: {e}")
        return [], errors

    # Check for duplicates
    duplicates = [name for name in team_names if team_names.count(name) > 1]
    if duplicates:
        unique_duplicates = list(set(duplicates))
        errors.append(f"Duplicate team names found: {unique_duplicates}")
        return [], errors

    return team_names, errors


def create_or_update_teams(
    db: firestore.Client, team_names: list[str], dry_run: bool = False
) -> tuple[int, int, int]:
    """
    Create or update team documents in Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    team_names : list[str]
        List of team names to create.
    dry_run : bool, optional
        If True, only log what would be done without making changes.

    Returns
    -------
    tuple[int, int, int]
        Tuple of (created_count, updated_count, skipped_count).
    """
    created_count = 0
    updated_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing teams...", total=len(team_names))

        for team_name in team_names:
            try:
                team_ref = db.collection(COLLECTION_TEAMS).document(team_name)
                team_doc = team_ref.get()

                if team_doc.exists:
                    # Team already exists - update timestamp
                    if dry_run:
                        console.print(
                            f"  [blue]Would update[/blue] team '{team_name}' (already exists)"
                        )
                    else:
                        team_ref.update({"updated_at": datetime.now(timezone.utc)})
                        console.print(f"  [yellow]○[/yellow] Updated '{team_name}'")
                    updated_count += 1
                else:
                    # Create new team
                    team_doc = {
                        "team_name": team_name,
                        "participants": [],
                        "created_at": datetime.now(timezone.utc),
                    }

                    if dry_run:
                        console.print(f"  [blue]Would create[/blue] team '{team_name}'")
                    else:
                        team_ref.set(team_doc)
                        console.print(f"  [green]✓[/green] Created '{team_name}'")
                    created_count += 1

            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to process '{team_name}': {e}")
                skipped_count += 1

            progress.update(task, advance=1)

    return created_count, updated_count, skipped_count


def display_summary_table(team_names: list[str]) -> None:
    """
    Display a summary table of teams.

    Parameters
    ----------
    team_names : list[str]
        List of team names.
    """
    table = Table(title="Teams to Setup", show_header=True, header_style="bold cyan")
    table.add_column("Team Name", style="yellow")

    for team_name in team_names:
        table.add_row(team_name)

    console.print()
    console.print(table)
    console.print()


def main() -> int:
    """
    Set up teams from CSV.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Setup teams in Firestore from CSV file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV File Format:
  team_name
  example-team
  awesome-team

Examples:
  # Create teams from CSV
  python scripts/admin/setup_teams.py teams.csv

  # Dry run to validate
  python scripts/admin/setup_teams.py teams.csv --dry-run
        """,
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to CSV file with column: team_name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be done without making changes",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv_file)

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Team Setup[/bold cyan]\nCreate teams from CSV in Firestore",
            border_style="cyan",
        )
    )

    if args.dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo changes will be made to Firestore",
                border_style="yellow",
            )
        )

    # Step 1: Read CSV file
    console.print("\n[bold]Step 1: Read CSV File[/bold]")
    console.print(f"[cyan]Reading from:[/cyan] {csv_path}")

    team_names, errors = read_teams_from_csv(csv_path)

    if errors:
        console.print("\n[red bold]✗ CSV Validation Errors:[/red bold]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
        return 1

    if not team_names:
        console.print("[yellow]No valid team names found in CSV[/yellow]")
        return 1

    console.print(f"[green]✓ Found {len(team_names)} teams in CSV[/green]")

    # Display summary
    display_summary_table(team_names)

    # Step 2: Initialize Firestore client
    console.print("[bold]Step 2: Connect to Firestore[/bold]")
    try:
        console.print("[cyan]Connecting to Firestore...[/cyan]")
        db = get_firestore_client()
        console.print("[green]✓ Connected to Firestore[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return 1

    # Step 3: Create or update teams
    console.print("[bold]Step 3: Create Teams[/bold]")
    created_count, updated_count, skipped_count = create_or_update_teams(
        db, team_names, dry_run=args.dry_run
    )
    console.print(
        f"\n[green]✓ Processed {len(team_names)} teams[/green]\n"
        f"  Created: {created_count}\n"
        f"  Updated: {updated_count}\n"
        f"  Failed: {skipped_count}\n"
    )

    # Final summary
    if args.dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Would create: {created_count} teams\n"
                f"Would update: {updated_count} teams\n"
                f"Would fail: {skipped_count} teams\n\n"
                "[dim]No changes were made to Firestore[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    elif skipped_count > 0:
        console.print(
            Panel.fit(
                "[yellow]SETUP COMPLETED WITH ERRORS[/yellow]\n"
                f"Created: {created_count}\n"
                f"Updated: {updated_count}\n"
                f"Failed: {skipped_count}",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1
    else:
        console.print(
            Panel.fit(
                "[green]SETUP COMPLETE[/green]\n"
                f"Teams created: {created_count}\n"
                f"Teams updated: {updated_count}",
                border_style="green",
                title="✓ Success",
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
