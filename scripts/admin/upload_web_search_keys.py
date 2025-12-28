#!/usr/bin/env python3
"""
Upload Web Search API keys for teams.

This script reads a CSV file containing Web Search API keys for each team and updates
the team documents in Firestore with these keys.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from utils import (
    COLLECTION_TEAMS,
    console,
    get_firestore_client,
    mask_sensitive_value,
)


def validate_csv_row(  # noqa: PLR0911
    row: dict[str, str], row_num: int
) -> tuple[bool, str]:
    """
    Validate a single CSV row.

    Parameters
    ----------
    row : dict[str, str]
        CSV row as a dictionary.
    row_num : int
        Row number for error reporting.

    Returns
    -------
    tuple[bool, str | None]
        Tuple of (is_valid, error_message).
    """
    required_fields = ["team-name", "web_search_api_key"]

    # Check for missing fields
    missing_fields = [field for field in required_fields if field not in row]
    if missing_fields:
        return False, f"Row {row_num}: Missing fields: {', '.join(missing_fields)}"

    # Check for empty values
    team_name = row["team-name"].strip()
    api_key = row["web_search_api_key"].strip()

    if not team_name:
        return False, f"Row {row_num}: team-name cannot be empty"

    if not api_key:
        return False, f"Row {row_num}: web_search_api_key cannot be empty"

    return True, ""


def read_web_search_keys_csv(csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """
    Read and validate Web Search API keys from CSV file.

    Parameters
    ----------
    csv_path : Path
        Path to the CSV file.

    Returns
    -------
    tuple[list[dict[str, str]], list[str]]
        Tuple of (valid_rows, errors).
    """
    if not csv_path.exists():
        return [], [f"CSV file not found: {csv_path}"]

    valid_rows = []
    errors = []

    try:
        with open(csv_path, "r") as f:
            # Convert to lowercase for case-insensitive matching
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [name.lower() for name in reader.fieldnames]

            for row_num, row_data in enumerate(
                reader, start=2
            ):  # Start at 2 (header is 1)
                # Normalize keys to lowercase
                row = {k.lower(): v for k, v in row_data.items()}

                is_valid, error = validate_csv_row(row, row_num)
                if not is_valid:
                    errors.append(error if error else "Unknown validation error")
                    continue

                valid_rows.append(
                    {
                        "team_name": row["team-name"].strip(),
                        "web_search_api_key": row["web_search_api_key"].strip(),
                    }
                )

    except Exception as e:
        errors.append(f"Error reading CSV file: {e}")
        return [], errors

    return valid_rows, errors


def update_team_web_search_key(
    db: Any,
    team_name: str,
    api_key: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Update Web Search API key for a team in Firestore.

    Parameters
    ----------
    db : Any
        Firestore client instance.
    team_name : str
        Name of the team.
    api_key : str
        Web Search API key.
    dry_run : bool, optional
        If True, only simulate the operation.

    Returns
    -------
    tuple[bool, str]
        Tuple of (success, message).
    """
    if dry_run:
        return True, "Dry run - no changes made"

    try:
        team_ref = db.collection(COLLECTION_TEAMS).document(team_name)
        team_doc = team_ref.get()

        if not team_doc.exists:
            return False, f"Team '{team_name}' not found in Firestore"

        # Update team document with Web Search API key
        team_ref.update(
            {
                "web_search_api_key": api_key,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return True, "Updated successfully"

    except Exception as e:
        return False, str(e)


def upload_web_search_keys(
    db: Any,
    teams_data: list[dict[str, str]],
    dry_run: bool = False,
) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Upload Web Search API keys for all teams.

    Parameters
    ----------
    db : Any
        Firestore client instance.
    teams_data : list[dict[str, str]]
        List of team data dictionaries.
    dry_run : bool, optional
        If True, only simulate operations.

    Returns
    -------
    tuple[int, int, list[dict[str, Any]]]
        Tuple of (success_count, failed_count, results).
    """
    success_count = 0
    failed_count = 0
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Uploading Web Search API keys...", total=len(teams_data)
        )

        for team in teams_data:
            team_name = team["team_name"]
            api_key = team["web_search_api_key"]

            result = {
                "team_name": team_name,
                "status": "pending",
                "message": "",
            }

            # Update team with Web Search API key
            success, message = update_team_web_search_key(
                db, team_name, api_key, dry_run
            )

            if success:
                if dry_run:
                    console.print(
                        f"  [blue]• {team_name}: Would update Web Search API key[/blue]"
                    )
                    result["status"] = "dry_run"
                else:
                    console.print(f"  [green]✓ {team_name}: {message}[/green]")
                    result["status"] = "success"
                success_count += 1
            else:
                console.print(f"  [red]✗ {team_name}: {message}[/red]")
                result["status"] = "failed"
                failed_count += 1

            result["message"] = message
            results.append(result)
            progress.update(task, advance=1)

    return success_count, failed_count, results


def display_results_table(results: list[dict[str, Any]]) -> None:
    """
    Display results in a formatted table.

    Parameters
    ----------
    results : list[dict[str, Any]]
        List of result dictionaries.
    """
    table = Table(
        title="Web Search API Keys Upload Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Team", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for result in results:
        status_icon = {
            "success": "[green]✓ Success[/green]",
            "failed": "[red]✗ Failed[/red]",
            "dry_run": "[blue]• Dry Run[/blue]",
        }.get(result["status"], "[dim]Unknown[/dim]")

        table.add_row(
            result["team_name"],
            status_icon,
            result["message"],
        )

    console.print()
    console.print(table)
    console.print()


def main() -> int:
    """
    Upload Web Search API keys for teams from CSV.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Upload Web Search API keys for teams from CSV file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
CSV File Format:
  team-name,WEB_SEARCH_API_KEY
  example-team,api-key-here
  awesome-team,another-key

Examples:
  # Upload Web Search API keys
  python scripts/admin/upload_web_search_keys.py web_search_keys.csv

  # Dry run to validate CSV
  python scripts/admin/upload_web_search_keys.py web_search_keys.csv --dry-run
        """,
    )
    parser.add_argument(
        "csv_file",
        type=str,
        help="Path to CSV file containing team Web Search API keys",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()
    csv_path = Path(args.csv_file)

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Web Search API Keys Uploader[/bold cyan]\n"
            "Update team Web Search API keys in Firestore",
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

    # Step 1: Read and validate CSV
    console.print("\n[bold]Step 1: Read CSV File[/bold]")
    console.print(f"[cyan]Reading from:[/cyan] {csv_path}")

    teams_data, errors = read_web_search_keys_csv(csv_path)

    if errors:
        console.print("\n[red bold]✗ CSV Validation Errors:[/red bold]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
        return 1

    if not teams_data:
        console.print("[yellow]No valid team data found in CSV[/yellow]")
        return 1

    console.print(f"[green]✓ Found {len(teams_data)} teams in CSV[/green]\n")

    # Display preview table
    preview_table = Table(show_header=True, header_style="bold cyan")
    preview_table.add_column("Team", style="yellow")
    preview_table.add_column("API Key", style="dim")

    for team in teams_data:
        preview_table.add_row(
            team["team_name"],
            mask_sensitive_value(team["web_search_api_key"], 12),
        )

    console.print(preview_table)
    console.print()

    # Step 2: Connect to Firestore
    console.print("[bold]Step 2: Connect to Firestore[/bold]")
    try:
        db = get_firestore_client()
        console.print("[green]✓ Connected to Firestore[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Firestore:[/red] {e}")
        return 1

    # Step 3: Upload keys
    console.print("[bold]Step 3: Upload Web Search API Keys[/bold]\n")
    success_count, failed_count, results = upload_web_search_keys(
        db, teams_data, dry_run=args.dry_run
    )

    # Display results
    if results:
        display_results_table(results)

    # Final summary
    if args.dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Would update: {success_count} teams\n"
                f"Would fail: {failed_count} teams\n\n"
                "[dim]No changes were made[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    elif failed_count == 0:
        console.print(
            Panel.fit(
                "[green]ALL KEYS UPLOADED SUCCESSFULLY[/green]\n"
                f"Successful: {success_count}\n"
                f"Failed: {failed_count}\n\n"
                "[dim]All teams updated with Web Search API keys[/dim]",
                border_style="green",
                title="✓ Success",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[yellow]COMPLETED WITH FAILURES[/yellow]\n"
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
