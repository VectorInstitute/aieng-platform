"""Delete participants from Firestore onboarding database."""

from pathlib import Path

import pandas as pd
from google.cloud import firestore
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aieng_platform_onboard.admin.utils import (
    COLLECTION_PARTICIPANTS,
    COLLECTION_TEAMS,
    console,
    get_firestore_client,
    get_participant_by_handle,
    get_team_by_name,
    normalize_github_handle,
    validate_github_handle,
)


def validate_csv_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate CSV data structure and content.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing github_handles to delete.

    Returns
    -------
    tuple[bool, list[str]]
        Tuple of (is_valid, list of error messages).
    """
    errors = []

    # Check required columns
    if "github_handle" not in df.columns:
        errors.append("Missing required column: 'github_handle'")
        return False, errors

    # Validate each row
    for idx in range(len(df)):
        row = df.iloc[idx]
        row_num = idx + 2  # +2 because of 0-indexing and header row

        # Validate github_handle
        if pd.isna(row["github_handle"]) or not row["github_handle"]:
            errors.append(f"Row {row_num}: Missing github_handle")
        elif not validate_github_handle(str(row["github_handle"])):
            errors.append(
                f"Row {row_num}: Invalid github_handle '{row['github_handle']}'"
            )

    # Check for duplicate github_handles
    duplicate_handles = df[df.duplicated(subset=["github_handle"], keep=False)]
    if not duplicate_handles.empty:
        dupes = duplicate_handles["github_handle"].unique().tolist()
        errors.append(f"Duplicate github_handles found: {dupes}")

    is_valid = len(errors) == 0
    return is_valid, errors


def delete_participant_from_team(
    db: firestore.Client,
    github_handle: str,
    team_name: str,
    dry_run: bool = False,
) -> tuple[bool, bool]:
    """
    Remove participant from team's participants array.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handle : str
        Normalized GitHub handle to remove.
    team_name : str
        Name of the team.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    tuple[bool, bool]
        Tuple of (success, team_is_empty_after_removal).
    """
    try:
        team = get_team_by_name(db, team_name)
        if not team:
            console.print(
                f"    [yellow]⚠[/yellow] Team '{team_name}' not found in Firestore"
            )
            return True, False

        # Get current participants
        current_participants = team.get("participants", [])

        # Remove the github_handle
        if github_handle in current_participants:
            updated_participants = [
                h for h in current_participants if h != github_handle
            ]

            if dry_run:
                console.print(
                    f"    [blue]Would remove[/blue] '{github_handle}' from team '{team_name}'"
                )
            else:
                team_ref = db.collection(COLLECTION_TEAMS).document(team["id"])
                team_ref.update({"participants": updated_participants})
                console.print(
                    f"    [green]✓[/green] Removed '{github_handle}' from team '{team_name}'"
                )

            # Check if team is now empty
            team_is_empty = len(updated_participants) == 0
            return True, team_is_empty
        console.print(
            f"    [yellow]⚠[/yellow] '{github_handle}' not in team '{team_name}' participants list"
        )
        return True, False

    except Exception as e:
        console.print(f"    [red]✗[/red] Failed to remove from team '{team_name}': {e}")
        return False, False


def delete_empty_team(
    db: firestore.Client, team_name: str, dry_run: bool = False
) -> bool:
    """
    Delete a team that has no participants.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    team_name : str
        Name of the team to delete.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    try:
        team = get_team_by_name(db, team_name)
        if not team:
            return True

        if dry_run:
            console.print(f"    [blue]Would delete[/blue] empty team '{team_name}'")
        else:
            team_ref = db.collection(COLLECTION_TEAMS).document(team["id"])
            team_ref.delete()
            console.print(f"    [green]✓[/green] Deleted empty team '{team_name}'")

        return True

    except Exception as e:
        console.print(f"    [red]✗[/red] Failed to delete team '{team_name}': {e}")
        return False


def delete_participants(
    db: firestore.Client,
    github_handles: list[str],
    delete_empty_teams: bool = True,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Delete participants from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    github_handles : list[str]
        List of normalized GitHub handles to delete.
    delete_empty_teams : bool, optional
        If True, delete teams that become empty after removing participants.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    tuple[int, int]
        Tuple of (successful_count, failed_count).
    """
    success_count = 0
    failed_count = 0
    empty_teams = set()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Deleting participants...", total=len(github_handles)
        )

        for github_handle in github_handles:
            try:
                # Check if participant exists
                participant = get_participant_by_handle(db, github_handle)

                if not participant:
                    console.print(
                        f"  [yellow]⚠[/yellow] '{github_handle}' not found in Firestore (already deleted?)"
                    )
                    success_count += 1
                    progress.update(task, advance=1)
                    continue

                team_name = participant.get("team_name")

                # Delete from participant collection
                if dry_run:
                    console.print(
                        f"  [blue]Would delete[/blue] participant '{github_handle}'"
                    )
                else:
                    participant_ref = db.collection(COLLECTION_PARTICIPANTS).document(
                        github_handle
                    )
                    participant_ref.delete()
                    console.print(
                        f"  [green]✓[/green] Deleted participant '{github_handle}'"
                    )

                # Remove from team's participants array
                if team_name:
                    team_success, team_is_empty = delete_participant_from_team(
                        db, github_handle, team_name, dry_run=dry_run
                    )

                    if not team_success:
                        failed_count += 1
                        progress.update(task, advance=1)
                        continue

                    # Track empty teams for later deletion
                    if team_is_empty:
                        empty_teams.add(team_name)

                success_count += 1

            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to delete '{github_handle}': {e}")
                failed_count += 1

            progress.update(task, advance=1)

    # Delete empty teams if requested
    if delete_empty_teams and empty_teams:
        console.print(f"\n[bold]Cleaning up {len(empty_teams)} empty team(s)[/bold]")
        for team_name in empty_teams:
            delete_empty_team(db, team_name, dry_run=dry_run)

    return success_count, failed_count


def display_summary_table(github_handles: list[str]) -> None:
    """
    Display a summary table of participants to delete.

    Parameters
    ----------
    github_handles : list[str]
        List of GitHub handles to delete.
    """
    table = Table(
        title="Participants to Delete", show_header=True, header_style="bold red"
    )
    table.add_column("GitHub Handle", style="yellow")
    table.add_column("Status", style="dim")

    for handle in github_handles[:10]:  # Show first 10
        table.add_row(handle, "Pending deletion")

    if len(github_handles) > 10:
        table.add_row(
            f"... and {len(github_handles) - 10} more",
            "Pending deletion",
            style="dim",
        )

    console.print()
    console.print(table)
    console.print()


def delete_participants_from_csv(
    csv_file: str, delete_empty_teams: bool = True, dry_run: bool = False
) -> int:
    """
    Delete participants from Firestore based on CSV file.

    Parameters
    ----------
    csv_file : str
        Path to CSV file with github_handle column.
    delete_empty_teams : bool, optional
        If True, delete teams that become empty after removing participants.
    dry_run : bool, optional
        If True, validate and show what would be done without making changes.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    exit_code = 0

    # Print header
    console.print(
        Panel.fit(
            "[bold red]Delete Bootcamp Participants[/bold red]\n"
            "Remove participants from Firestore onboarding database",
            border_style="red",
        )
    )

    # Check if CSV file exists
    csv_path = Path(csv_file)
    if not csv_path.exists():
        console.print(f"[red]✗[/red] CSV file not found: {csv_file}")
        exit_code = 1
    # Read CSV file
    elif (df := _read_csv_file(csv_file)) is None or (
        github_handles := _validate_and_normalize_csv(df)
    ) is None:
        exit_code = 1
    # Confirm deletion or skip if dry-run
    elif not dry_run and not _confirm_deletion(github_handles, delete_empty_teams):
        console.print("\n[yellow]Deletion cancelled.[/yellow]")
        exit_code = 0
    # Process deletion
    else:
        exit_code = _process_deletion(github_handles, delete_empty_teams, dry_run)

    return exit_code


def _read_csv_file(csv_file: str) -> pd.DataFrame | None:
    """Read and return CSV file, or None on error."""
    try:
        console.print(f"\n[cyan]Reading CSV file:[/cyan] {csv_file}")
        df = pd.read_csv(csv_file)
        console.print(f"[green]✓[/green] Found {len(df)} participant(s) to delete\n")
        return df
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read CSV file: {e}")
        return None


def _validate_and_normalize_csv(df: pd.DataFrame) -> list[str] | None:
    """Validate CSV data and return normalized handles, or None on error."""
    console.print("[cyan]Validating CSV data...[/cyan]")
    is_valid, errors = validate_csv_data(df)

    if not is_valid:
        console.print("[red]✗ CSV validation failed:[/red]")
        for error in errors:
            console.print(f"  [red]•[/red] {error}")
        return None

    console.print("[green]✓ CSV validation passed![/green]\n")

    # Normalize GitHub handles
    github_handles = [
        normalize_github_handle(str(handle).strip())
        for handle in df["github_handle"]
        if pd.notna(handle)
    ]

    # Display summary
    display_summary_table(github_handles)

    return github_handles


def _confirm_deletion(github_handles: list[str], delete_empty_teams: bool) -> bool:
    """Prompt user for deletion confirmation."""
    console.print(
        Panel(
            f"[bold red]⚠ WARNING ⚠[/bold red]\n\n"
            f"You are about to delete {len(github_handles)} participant(s) from Firestore.\n"
            f"Empty teams will {'be deleted' if delete_empty_teams else 'NOT be deleted'}.\n\n"
            "[yellow]This action cannot be undone![/yellow]\n\n"
            "Type 'DELETE' (in capital letters) to confirm:",
            border_style="red",
            title="⚠ Confirmation Required",
        )
    )
    confirmation = input().strip()
    if confirmation == "DELETE":
        console.print()
        return True
    return False


def _process_deletion(
    github_handles: list[str], delete_empty_teams: bool, dry_run: bool
) -> int:
    """Process the deletion and return exit code."""
    if dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo changes will be made to Firestore",
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

    # Delete participants
    console.print("[bold]Deleting Participants[/bold]")
    success_count, failed_count = delete_participants(
        db, github_handles, delete_empty_teams=delete_empty_teams, dry_run=dry_run
    )
    console.print(
        f"\n[green]✓ Processed {success_count + failed_count} participant(s)[/green]\n"
        f"  Successful: {success_count}\n"
        f"  Failed: {failed_count}\n"
    )

    # Final summary
    if dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Participants marked for deletion: {success_count}\n"
                f"Participants not found: {failed_count}\n\n"
                "[dim]No changes were made to Firestore[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
        return 0

    if failed_count > 0:
        console.print(
            Panel.fit(
                "[yellow]DELETION COMPLETED WITH ERRORS[/yellow]\n"
                f"Participants deleted: {success_count}\n"
                f"Participants failed: {failed_count}\n\n"
                "[dim]Check errors above for details[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1

    console.print(
        Panel.fit(
            f"[green]DELETION COMPLETE[/green]\nParticipants deleted: {success_count}",
            border_style="green",
            title="✓ Success",
        )
    )
    return 0
