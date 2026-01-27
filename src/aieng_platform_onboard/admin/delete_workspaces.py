"""Delete Coder workspaces and associated GCP resources created before a specified date.

This module provides functionality to delete Coder workspaces using the Coder CLI.
When a workspace is deleted, Coder triggers Terraform destroy to clean up associated
GCP resources (VMs, persistent disks).

Usage:
    onboard admin delete-workspaces --before 2025-01-01 [--dry-run] [--orphan]
"""

import json
import subprocess
from datetime import datetime, timezone
from typing import Any

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aieng_platform_onboard.admin.utils import console


def run_coder_command(
    args: list[str], check: bool = True
) -> subprocess.CompletedProcess:
    """
    Run a Coder CLI command.

    Parameters
    ----------
    args : list[str]
        Arguments to pass to the coder command.
    check : bool, optional
        If True, raise CalledProcessError on non-zero exit code.

    Returns
    -------
    subprocess.CompletedProcess
        The completed process result.

    Raises
    ------
    RuntimeError
        If the coder CLI is not available or command fails.
    """
    cmd = ["coder"] + args
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Coder CLI not found. Please install it and ensure it's in your PATH. "
            "See: https://coder.com/docs/install"
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Coder command failed: {e.stderr}") from e


def fetch_all_workspaces() -> list[dict[str, Any]]:
    """
    Fetch all workspaces from Coder using the CLI.

    Returns
    -------
    list[dict[str, Any]]
        List of workspace objects.

    Raises
    ------
    RuntimeError
        If fetching workspaces fails.
    """
    try:
        result = run_coder_command(["list", "-a", "-o", "json"])
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse workspace data: {e}") from e


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string in YYYY-MM-DD format.

    Parameters
    ----------
    date_str : str
        Date string in YYYY-MM-DD format.

    Returns
    -------
    datetime
        Parsed datetime object with UTC timezone (at start of day).

    Raises
    ------
    ValueError
        If date string is invalid.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Use YYYY-MM-DD.") from e


def parse_workspace_created_at(created_at: str) -> datetime:
    """
    Parse workspace created_at timestamp.

    Parameters
    ----------
    created_at : str
        ISO 8601 timestamp from Coder API.

    Returns
    -------
    datetime
        Parsed datetime object.
    """
    return datetime.fromisoformat(created_at.replace("Z", "+00:00"))


def filter_workspaces_by_date(
    workspaces: list[dict[str, Any]],
    before_date: datetime,
) -> list[dict[str, Any]]:
    """
    Filter workspaces created before a specified date.

    Parameters
    ----------
    workspaces : list[dict[str, Any]]
        List of workspace objects.
    before_date : datetime
        Only include workspaces created before this date.

    Returns
    -------
    list[dict[str, Any]]
        Filtered list of workspaces.
    """
    filtered = []
    for workspace in workspaces:
        created_at_str = workspace.get("created_at")
        if not created_at_str:
            continue

        created_at = parse_workspace_created_at(created_at_str)
        if created_at < before_date:
            filtered.append(workspace)

    return filtered


def delete_workspace_cli(
    owner_name: str,
    workspace_name: str,
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> bool:
    """
    Delete a Coder workspace using the CLI.

    Parameters
    ----------
    owner_name : str
        The owner's username.
    workspace_name : str
        The name of the workspace.
    orphan : bool, optional
        If True, delete workspace without removing GCP resources.
        Use this for workspaces in a broken state.
    auto_orphan_on_failure : bool, optional
        If True and normal deletion fails due to Terraform errors,
        automatically retry with --orphan flag.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    bool
        True if deletion succeeded, False otherwise.
    """
    full_name = f"{owner_name}/{workspace_name}"

    if dry_run:
        orphan_msg = " (orphan mode)" if orphan else ""
        console.print(
            f"  [blue]Would delete[/blue] workspace '{full_name}'{orphan_msg}"
        )
        return True

    try:
        # Build the delete command
        # coder delete <owner>/<workspace> -y [--orphan]
        args = ["delete", full_name, "-y"]
        if orphan:
            args.append("--orphan")

        result = run_coder_command(args, check=False)

        if result.returncode == 0:
            orphan_msg = " (orphaned)" if orphan else ""
            console.print(
                f"  [green]✓[/green] Deleted workspace '{full_name}'{orphan_msg}"
            )
            return True

        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"

        # Check if this is a Terraform error and auto-orphan is enabled
        is_terraform_error = "terraform" in error_msg.lower()
        if is_terraform_error and auto_orphan_on_failure and not orphan:
            console.print(
                f"  [yellow]⚠[/yellow] Terraform failed for '{full_name}', "
                "retrying with --orphan..."
            )
            # Retry with orphan flag
            return delete_workspace_cli(
                owner_name=owner_name,
                workspace_name=workspace_name,
                orphan=True,
                auto_orphan_on_failure=False,  # Don't recurse again
                dry_run=dry_run,
            )

        console.print(f"  [red]✗[/red] Failed to delete '{full_name}': {error_msg}")
        return False

    except RuntimeError as e:
        console.print(f"  [red]✗[/red] Failed to delete '{full_name}': {e}")
        return False


def display_workspace_table(workspaces: list[dict[str, Any]], before_date: str) -> None:
    """
    Display a table of workspaces to be deleted.

    Parameters
    ----------
    workspaces : list[dict[str, Any]]
        List of workspace objects to display.
    before_date : str
        The cutoff date string for display.
    """
    table = Table(
        title=f"Workspaces Created Before {before_date}",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("Owner", style="cyan")
    table.add_column("Workspace", style="yellow")
    table.add_column("Template", style="dim")
    table.add_column("Created At", style="dim")
    table.add_column("Status", style="dim")

    # Sort by created_at
    sorted_workspaces = sorted(
        workspaces, key=lambda w: w.get("created_at", ""), reverse=True
    )

    for workspace in sorted_workspaces[:20]:  # Show first 20
        owner = workspace.get("owner_name", "unknown")
        name = workspace.get("name", "unknown")
        template = workspace.get("template_name", "unknown")
        created_at = workspace.get("created_at", "unknown")
        if created_at != "unknown":
            created_at = created_at[:10]  # Just the date part
        status = workspace.get("latest_build", {}).get("status", "unknown")
        table.add_row(owner, name, template, created_at, status)

    if len(workspaces) > 20:
        table.add_row(
            f"... and {len(workspaces) - 20} more",
            "",
            "",
            "",
            "",
            style="dim",
        )

    console.print()
    console.print(table)
    console.print()


def delete_workspaces(
    workspaces: list[dict[str, Any]],
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Delete multiple Coder workspaces using the CLI.

    Parameters
    ----------
    workspaces : list[dict[str, Any]]
        List of workspace objects to delete.
    orphan : bool, optional
        If True, orphan GCP resources instead of deleting them via Terraform.
    auto_orphan_on_failure : bool, optional
        If True, automatically retry with --orphan when Terraform fails.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    tuple[int, int]
        Tuple of (successful_count, failed_count).
    """
    success_count = 0
    failed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Deleting workspaces...", total=len(workspaces))

        for workspace in workspaces:
            workspace_name = workspace.get("name")
            owner_name = workspace.get("owner_name")

            if not workspace_name or not owner_name:
                console.print(
                    "  [yellow]⚠[/yellow] Skipping workspace with missing name or owner"
                )
                failed_count += 1
                progress.update(task, advance=1)
                continue

            success = delete_workspace_cli(
                owner_name=owner_name,
                workspace_name=workspace_name,
                orphan=orphan,
                auto_orphan_on_failure=auto_orphan_on_failure,
                dry_run=dry_run,
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

            progress.update(task, advance=1)

    return success_count, failed_count


def _validate_and_fetch_workspaces(
    before_date: str,
) -> tuple[int | None, datetime | None, list[dict[str, Any]]]:
    """
    Validate date, verify Coder CLI, and fetch workspaces.

    Parameters
    ----------
    before_date : str
        Date string in YYYY-MM-DD format.

    Returns
    -------
    tuple[int | None, datetime | None, list[dict[str, Any]]]
        Tuple of (error_code, cutoff_date, workspaces).
        If error_code is not None, an error occurred and the function should return it.
    """
    # Parse and validate the date
    try:
        cutoff_date = parse_date(before_date)
        console.print(f"\n[cyan]Cutoff date:[/cyan] {before_date} (UTC)")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        return (1, None, [])

    # Verify Coder CLI is available and authenticated
    console.print("\n[cyan]Verifying Coder CLI...[/cyan]")
    try:
        result = run_coder_command(["version"], check=False)
        if result.returncode != 0:
            console.print(
                f"[red]✗[/red] Coder CLI not working properly: {result.stderr}"
            )
            return (1, None, [])
        console.print(f"[green]✓[/green] Coder CLI: {result.stdout.strip()}")
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        return (1, None, [])

    # Fetch all workspaces
    console.print("\n[cyan]Fetching workspaces from Coder...[/cyan]")
    try:
        all_workspaces = fetch_all_workspaces()
        console.print(f"[green]✓[/green] Found {len(all_workspaces)} total workspaces")
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        return (1, None, [])

    return (None, cutoff_date, all_workspaces)


def delete_workspaces_before_date(
    before_date: str,
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Delete Coder workspaces created before a specified date.

    This function uses the Coder CLI to delete workspaces. By default, Coder
    triggers Terraform destroy to clean up associated GCP resources (VMs, disks).

    Parameters
    ----------
    before_date : str
        Delete workspaces created before this date (YYYY-MM-DD format).
    orphan : bool, optional
        If True, delete workspaces without removing GCP resources via Terraform.
        Use this if Terraform destroy is failing for some workspaces.
    auto_orphan_on_failure : bool, optional
        If True, automatically retry with --orphan when Terraform fails.
        This allows most deletions to succeed even when some have broken state.
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
            "[bold red]Delete Coder Workspaces[/bold red]\n"
            "Remove workspaces and associated GCP resources (VMs, disks)",
            border_style="red",
        )
    )

    # Validate and fetch workspaces
    error_code, cutoff_date, all_workspaces = _validate_and_fetch_workspaces(
        before_date
    )
    if error_code is not None:
        return error_code

    # cutoff_date is guaranteed to be set when error_code is None
    assert cutoff_date is not None

    # Filter workspaces by date
    workspaces_to_delete = filter_workspaces_by_date(all_workspaces, cutoff_date)

    if not workspaces_to_delete:
        console.print(
            f"\n[yellow]No workspaces found created before {before_date}[/yellow]"
        )
        return 0

    console.print(
        f"[green]✓[/green] Found {len(workspaces_to_delete)} workspace(s) "
        f"created before {before_date}"
    )

    # Display summary table
    display_workspace_table(workspaces_to_delete, before_date)

    # Confirm deletion or skip if dry-run
    if not dry_run and not _confirm_deletion(len(workspaces_to_delete), orphan):
        console.print("\n[yellow]Deletion cancelled.[/yellow]")
        return 0

    # Process deletion
    return _process_deletion(
        workspaces_to_delete, orphan, auto_orphan_on_failure, dry_run
    )


def _confirm_deletion(workspace_count: int, orphan: bool) -> bool:
    """Prompt user for deletion confirmation."""
    resource_action = "orphaned (NOT deleted)" if orphan else "DELETED via Terraform"
    console.print(
        Panel(
            f"[bold red]⚠ WARNING ⚠[/bold red]\n\n"
            f"You are about to delete {workspace_count} workspace(s).\n"
            f"Associated GCP resources (VMs, disks) will be {resource_action}.\n\n"
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
    workspaces: list[dict[str, Any]],
    orphan: bool,
    auto_orphan_on_failure: bool,
    dry_run: bool,
) -> int:
    """Process the deletion and return exit code."""
    if dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo workspaces will be deleted",
                border_style="yellow",
            )
        )

    if orphan:
        console.print(
            Panel(
                "[yellow]ORPHAN MODE[/yellow]\n"
                "GCP resources will NOT be deleted via Terraform.\n"
                "You may need to manually clean up VMs and disks.",
                border_style="yellow",
            )
        )
    elif auto_orphan_on_failure:
        console.print(
            "[dim]Auto-orphan enabled: will retry with --orphan if Terraform fails[/dim]"
        )

    # Delete workspaces
    console.print("[bold]Deleting Workspaces[/bold]")
    success_count, failed_count = delete_workspaces(
        workspaces=workspaces,
        orphan=orphan,
        auto_orphan_on_failure=auto_orphan_on_failure,
        dry_run=dry_run,
    )

    console.print(
        f"\n[green]✓ Processed {success_count + failed_count} workspace(s)[/green]\n"
        f"  Successful: {success_count}\n"
        f"  Failed: {failed_count}\n"
    )

    # Final summary
    if dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Workspaces marked for deletion: {success_count}\n"
                f"Workspaces skipped: {failed_count}\n\n"
                "[dim]No workspaces were actually deleted[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
        return 0

    if failed_count > 0:
        console.print(
            Panel.fit(
                "[yellow]DELETION COMPLETED WITH ERRORS[/yellow]\n"
                f"Workspaces deleted: {success_count}\n"
                f"Workspaces failed: {failed_count}\n\n"
                "[dim]Check errors above for details[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1

    console.print(
        Panel.fit(
            f"[green]DELETION COMPLETE[/green]\nWorkspaces deleted: {success_count}",
            border_style="green",
            title="✓ Success",
        )
    )
    return 0
