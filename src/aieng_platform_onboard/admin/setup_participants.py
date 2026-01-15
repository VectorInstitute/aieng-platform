"""Setup participants and teams in Firestore from CSV file."""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import firestore  # type: ignore[attr-defined]
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
    validate_email,
    validate_github_handle,
    validate_team_name,
)


def validate_csv_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate CSV data structure and content.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing participant data.

    Returns
    -------
    tuple[bool, list[str]]
        Tuple of (is_valid, list of error messages).
    """
    errors = []

    # Check required columns
    required_columns = {"github_handle", "team_name"}
    optional_columns = {"email", "first_name", "last_name"}
    all_columns = required_columns | optional_columns

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
        return False, errors

    extra_columns = set(df.columns) - all_columns
    if extra_columns:
        console.print(
            f"[yellow]Warning:[/yellow] Extra columns will be ignored: {extra_columns}"
        )

    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # +2 because of 0-indexing and header row

        # Validate github_handle
        if pd.isna(row["github_handle"]) or not row["github_handle"]:
            errors.append(f"Row {row_num}: Missing github_handle")
        elif not validate_github_handle(str(row["github_handle"])):
            errors.append(
                f"Row {row_num}: Invalid github_handle '{row['github_handle']}'"
            )

        # Validate team_name
        if pd.isna(row["team_name"]) or not row["team_name"]:
            errors.append(f"Row {row_num}: Missing team_name")
        elif not validate_team_name(str(row["team_name"])):
            errors.append(f"Row {row_num}: Invalid team_name '{row['team_name']}'")

        # Validate email if present
        if (
            "email" in row
            and pd.notna(row["email"])
            and row["email"]
            and not validate_email(str(row["email"]))
        ):
            errors.append(f"Row {row_num}: Invalid email '{row['email']}'")

    # Check for duplicate github_handles
    duplicate_handles = df[df.duplicated(subset=["github_handle"], keep=False)]
    if not duplicate_handles.empty:
        dupes = duplicate_handles["github_handle"].unique().tolist()
        errors.append(f"Duplicate github_handles found: {dupes}")

    is_valid = len(errors) == 0
    return is_valid, errors


def group_participants_by_team(df: pd.DataFrame) -> dict[str, list[dict]]:
    """
    Group participants by their team.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing participant data.

    Returns
    -------
    dict[str, list[dict]]
        Dictionary mapping team names to lists of participant records.
    """
    teams: dict[str, list[dict]] = defaultdict(list)

    for _, row in df.iterrows():
        team_name = str(row["team_name"]).strip()
        participant = {
            # Normalize GitHub handle for case-insensitive matching
            "github_handle": normalize_github_handle(str(row["github_handle"]).strip()),
            "email": (
                str(row["email"]).strip()
                if "email" in row and pd.notna(row["email"])
                else ""
            ),
            "first_name": (
                str(row["first_name"]).strip()
                if "first_name" in row and pd.notna(row["first_name"])
                else ""
            ),
            "last_name": (
                str(row["last_name"]).strip()
                if "last_name" in row and pd.notna(row["last_name"])
                else ""
            ),
        }
        teams[team_name].append(participant)

    return dict(teams)


def create_or_update_teams(
    db: firestore.Client, teams_data: dict[str, list[dict]], dry_run: bool = False
) -> dict[str, str]:
    """
    Create or update team documents in Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    teams_data : dict[str, list[dict]]
        Dictionary mapping team names to participant lists.
    dry_run : bool, optional
        If True, only log what would be done without making changes.

    Returns
    -------
    dict[str, str]
        Dictionary mapping team names to their document IDs.
    """
    team_ids = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing teams...", total=len(teams_data))

        for team_name, participants in teams_data.items():
            # GitHub handles are already normalized in group_participants_by_team
            participant_handles = [p["github_handle"] for p in participants]

            # Check if team already exists
            existing_team = get_team_by_name(db, team_name)

            if existing_team:
                if dry_run:
                    console.print(
                        f"  [blue]Would update[/blue] team '{team_name}' "
                        f"({len(participant_handles)} participants)"
                    )
                else:
                    team_ref = db.collection(COLLECTION_TEAMS).document(
                        existing_team["id"]
                    )
                    team_ref.update(
                        {
                            "participants": participant_handles,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                    console.print(f"  [green]✓[/green] Updated team '{team_name}'")
                team_ids[team_name] = existing_team["id"]
            else:
                team_doc = {
                    "team_name": team_name,
                    "participants": participant_handles,
                    "created_at": datetime.now(timezone.utc),
                }

                if dry_run:
                    console.print(
                        f"  [blue]Would create[/blue] team '{team_name}' "
                        f"({len(participant_handles)} participants)"
                    )
                    team_ids[team_name] = f"dry-run-{team_name}"
                else:
                    team_ref = db.collection(COLLECTION_TEAMS).document(team_name)
                    team_ref.set(team_doc)
                    console.print(f"  [green]✓[/green] Created team '{team_name}'")
                    team_ids[team_name] = team_name

            progress.update(task, advance=1)

    return team_ids


def create_or_update_participants(  # noqa: PLR0912, PLR0915
    db: firestore.Client, teams_data: dict[str, list[dict]], dry_run: bool = False
) -> tuple[int, int]:
    """
    Create or update participant documents in Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    teams_data : dict[str, list[dict]]
        Dictionary mapping team names to participant lists.
    dry_run : bool, optional
        If True, only log what would be done without making changes.

    Returns
    -------
    tuple[int, int]
        Tuple of (successful_count, failed_count).
    """
    success_count = 0
    failed_count = 0
    total_participants = sum(len(participants) for participants in teams_data.values())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Processing participants...", total=total_participants
        )

        for team_name, participants in teams_data.items():
            # Check if team exists in Firestore
            team_exists = False
            try:
                team_ref = db.collection(COLLECTION_TEAMS).document(team_name)
                team_doc = team_ref.get()
                team_exists = team_doc.exists
            except Exception as e:
                console.print(
                    f"  [red]✗ Failed to check if team '{team_name}' exists:[/red] {e}"
                )

            if not team_exists:
                console.print(
                    f"  [red]✗ Team '{team_name}' not found in Firestore[/red]\n"
                    f"    [yellow]Skipping {len(participants)} participant(s) for this team[/yellow]\n"
                    f"    [dim]Team creation may have failed - check errors above[/dim]"
                )
                failed_count += len(participants)
                progress.update(task, advance=len(participants))
                continue

            for participant in participants:
                # GitHub handle is already normalized in group_participants_by_team
                github_handle = participant["github_handle"]
                email = participant["email"]
                first_name = participant.get("first_name", "")
                last_name = participant.get("last_name", "")

                # Check if participant already exists
                existing_participant = get_participant_by_handle(db, github_handle)

                if existing_participant:
                    if dry_run:
                        console.print(
                            f"  [blue]Would update[/blue] '{github_handle}' → {team_name}"
                        )
                    else:
                        participant_ref = db.collection(
                            COLLECTION_PARTICIPANTS
                        ).document(github_handle)
                        update_data = {
                            "team_name": team_name,
                            "updated_at": datetime.now(timezone.utc),
                        }
                        if email:
                            update_data["email"] = email
                        if first_name:
                            update_data["first_name"] = first_name
                        if last_name:
                            update_data["last_name"] = last_name
                        participant_ref.update(update_data)
                        console.print(f"  [green]✓[/green] Updated '{github_handle}'")
                else:
                    participant_doc = {
                        "github_handle": github_handle,
                        "team_name": team_name,
                        "onboarded": False,
                        "created_at": datetime.now(timezone.utc),
                    }
                    if email:
                        participant_doc["email"] = email
                    if first_name:
                        participant_doc["first_name"] = first_name
                    if last_name:
                        participant_doc["last_name"] = last_name

                    if dry_run:
                        console.print(
                            f"  [blue]Would create[/blue] '{github_handle}' → {team_name}"
                        )
                    else:
                        participant_ref = db.collection(
                            COLLECTION_PARTICIPANTS
                        ).document(github_handle)
                        participant_ref.set(participant_doc)
                        console.print(f"  [green]✓[/green] Created '{github_handle}'")

                success_count += 1
                progress.update(task, advance=1)

    return success_count, failed_count


def display_summary_table(teams_data: dict[str, list[dict]]) -> None:
    """
    Display a summary table of teams and participants.

    Parameters
    ----------
    teams_data : dict[str, list[dict]]
        Dictionary mapping team names to participant lists.
    """
    table = Table(title="Setup Summary", show_header=True, header_style="bold cyan")
    table.add_column("Team Name", style="yellow")
    table.add_column("Participants", justify="right", style="green")
    table.add_column("Members", style="dim")

    for team_name, participants in sorted(teams_data.items()):
        members = ", ".join(p["github_handle"] for p in participants[:3])
        if len(participants) > 3:
            members += f" ... (+{len(participants) - 3} more)"
        table.add_row(team_name, str(len(participants)), members)

    console.print()
    console.print(table)
    console.print()


def setup_participants_from_csv(csv_file: str, dry_run: bool = False) -> int:
    """
    Set up participants and teams from CSV file.

    Parameters
    ----------
    csv_file : str
        Path to CSV file with participant data.
    dry_run : bool, optional
        If True, validate and show what would be done without making changes.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Bootcamp Participant Setup[/bold cyan]\n"
            "Load participants and teams from CSV into Firestore",
            border_style="cyan",
        )
    )

    # Check if CSV file exists
    csv_path = Path(csv_file)
    if not csv_path.exists():
        console.print(f"[red]✗[/red] CSV file not found: {csv_file}")
        return 1

    # Read CSV file
    try:
        console.print(f"\n[cyan]Reading CSV file:[/cyan] {csv_file}")
        df = pd.read_csv(csv_path)
        console.print(f"[green]✓[/green] Found {len(df)} rows in CSV\n")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read CSV file: {e}")
        return 1

    # Validate CSV data
    console.print("[cyan]Validating CSV data...[/cyan]")
    is_valid, errors = validate_csv_data(df)

    if not is_valid:
        console.print("[red]✗ CSV validation failed:[/red]")
        for error in errors:
            console.print(f"  [red]•[/red] {error}")
        return 1

    console.print("[green]✓ CSV validation passed![/green]\n")

    # Group participants by team
    teams_data = group_participants_by_team(df)

    # Display summary
    display_summary_table(teams_data)

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

    # Create or update teams
    console.print("[bold]Processing Teams[/bold]")
    team_ids = create_or_update_teams(db, teams_data, dry_run=dry_run)
    console.print(f"[green]✓ Processed {len(team_ids)} teams[/green]\n")

    # Create or update participants
    console.print("[bold]Processing Participants[/bold]")
    success_count, failed_count = create_or_update_participants(
        db, teams_data, dry_run=dry_run
    )
    console.print(
        f"[green]✓ Processed {success_count + failed_count} participants[/green]\n"
        f"  Successful: {success_count}\n"
        f"  Failed: {failed_count}\n"
    )

    # Final summary
    if dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Teams: {len(team_ids)}\n"
                f"Participants (successful): {success_count}\n"
                f"Participants (failed): {failed_count}\n\n"
                "[dim]No changes were made to Firestore[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    elif failed_count > 0:
        console.print(
            Panel.fit(
                "[yellow]SETUP COMPLETED WITH ERRORS[/yellow]\n"
                f"Teams created/updated: {len(team_ids)}\n"
                f"Participants successful: {success_count}\n"
                f"Participants failed: {failed_count}\n\n"
                "[dim]Review errors above for details on failed operations[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1
    else:
        console.print(
            Panel.fit(
                "[green]SETUP COMPLETE[/green]\n"
                f"Teams created/updated: {len(team_ids)}\n"
                f"Participants created/updated: {success_count}",
                border_style="green",
                title="✓ Success",
            )
        )

    return 0
