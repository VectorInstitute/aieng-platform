"""Offboard Coder users who are no longer members of the GitHub org.

This module identifies Coder users authenticated via GitHub whose accounts no
longer exist in the specified GitHub organization, then cleans them up by:

1. Deleting (or orphaning) their Coder workspaces
2. Suspending or deleting their Coder user account
3. Removing them from the Firestore onboarding database

Usage
-----
    onboard admin offboard-users --org VectorInstitute [--dry-run] [--suspend]
        [--skip-workspaces] [--skip-firestore] [--orphan] [--no-auto-orphan]
"""

import json
import subprocess
from typing import Any

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aieng_platform_onboard.admin.delete_participants import delete_participants
from aieng_platform_onboard.admin.delete_workspaces import (
    delete_workspace_cli,
    run_coder_command,
)
from aieng_platform_onboard.admin.utils import (
    console,
    get_firestore_client,
    normalize_github_handle,
)


# Coder role name that identifies deployment owners – always skipped
_CODER_OWNER_ROLE = "owner"


def fetch_github_org_members(org: str) -> set[str]:
    """
    Return the set of lowercase GitHub usernames that are members of *org*.

    Uses the ``gh`` CLI which must be installed and authenticated.

    Parameters
    ----------
    org : str
        GitHub organization slug (e.g. ``"VectorInstitute"``).

    Returns
    -------
    set[str]
        Lowercase login names of every current org member.

    Raises
    ------
    RuntimeError
        If the ``gh`` CLI is unavailable or the API call fails.
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"/orgs/{org}/members", "--paginate"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "gh CLI not found. Install it and authenticate with `gh auth login`."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Failed to fetch GitHub org members for '{org}': {e.stderr}"
        ) from e

    try:
        members: list[dict[str, Any]] = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse GitHub API response: {e}") from e

    return {m["login"].lower() for m in members}


def fetch_coder_users() -> list[dict[str, Any]]:
    """
    Return all Coder user records as a list of dicts.

    Returns
    -------
    list[dict[str, Any]]
        Raw Coder user objects from ``coder users list --output json``.

    Raises
    ------
    RuntimeError
        If the Coder CLI call fails or the output cannot be parsed.
    """
    try:
        result = run_coder_command(["users", "list", "--output", "json"])
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Coder user data: {e}") from e


def find_stale_coder_users(
    coder_users: list[dict[str, Any]],
    org_members: set[str],
) -> list[dict[str, Any]]:
    """
    Return Coder users authenticated via GitHub who are no longer org members.

    Coder owner accounts are always excluded – they are platform administrators
    who exist independently of bootcamp cohort membership.

    Parameters
    ----------
    coder_users : list[dict[str, Any]]
        Full list of Coder user records.
    org_members : set[str]
        Lowercase GitHub logins of current org members.

    Returns
    -------
    list[dict[str, Any]]
        Coder user records that should be offboarded.
    """
    stale = []
    for user in coder_users:
        # Only consider users who authenticated via GitHub
        if user.get("login_type") != "github":
            continue

        # Never offboard Coder owners
        roles = [r.get("name") for r in user.get("roles", [])]
        if _CODER_OWNER_ROLE in roles:
            continue

        username_lower = user["username"].lower()
        if username_lower not in org_members:
            stale.append(user)

    return stale


def suspend_coder_user(username: str, dry_run: bool = False) -> bool:
    """
    Suspend a Coder user account (prevents login, preserves data).

    Parameters
    ----------
    username : str
        Coder username to suspend.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    bool
        True if the operation succeeded, False otherwise.
    """
    if dry_run:
        console.print(f"  [blue]Would suspend[/blue] Coder user '{username}'")
        return True

    try:
        result = run_coder_command(["users", "suspend", username], check=False)
        if result.returncode == 0:
            console.print(f"  [green]✓[/green] Suspended Coder user '{username}'")
            return True
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        console.print(
            f"  [red]✗[/red] Failed to suspend '{username}': {error_msg}"
        )
        return False
    except RuntimeError as e:
        console.print(f"  [red]✗[/red] Failed to suspend '{username}': {e}")
        return False


def delete_coder_user(username: str, dry_run: bool = False) -> bool:
    """
    Permanently delete a Coder user account.

    Parameters
    ----------
    username : str
        Coder username to delete.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    bool
        True if the operation succeeded, False otherwise.
    """
    if dry_run:
        console.print(f"  [blue]Would delete[/blue] Coder user '{username}'")
        return True

    try:
        result = run_coder_command(
            ["users", "delete", username], check=False
        )
        if result.returncode == 0:
            console.print(f"  [green]✓[/green] Deleted Coder user '{username}'")
            return True
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        console.print(
            f"  [red]✗[/red] Failed to delete '{username}': {error_msg}"
        )
        return False
    except RuntimeError as e:
        console.print(f"  [red]✗[/red] Failed to delete '{username}': {e}")
        return False


def fetch_user_workspaces(username: str) -> list[dict[str, Any]]:
    """
    Return all workspaces owned by *username*.

    Parameters
    ----------
    username : str
        Coder username.

    Returns
    -------
    list[dict[str, Any]]
        Workspace records owned by the user. Empty list if none or on error.
    """
    try:
        result = run_coder_command(
            ["list", "--all-users", "--output", "json", "--search", f"owner:{username}"],
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        workspaces: list[dict[str, Any]] = json.loads(result.stdout)
        # Filter to only this user's workspaces (the search filter may not be exact)
        return [w for w in workspaces if w.get("owner_name") == username]
    except (json.JSONDecodeError, RuntimeError):
        return []


def offboard_user(
    user: dict[str, Any],
    suspend: bool = False,
    skip_workspaces: bool = False,
    skip_firestore: bool = False,
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> bool:
    """
    Offboard a single Coder user completely.

    Steps (each is skipped if the relevant ``skip_*`` flag is set):

    1. Delete all Coder workspaces owned by the user.
    2. Suspend or delete the Coder user account.
    3. Remove the user from the Firestore onboarding database.

    Parameters
    ----------
    user : dict[str, Any]
        Coder user record (from ``fetch_coder_users``).
    suspend : bool, optional
        If True, suspend the Coder account instead of deleting it.
    skip_workspaces : bool, optional
        If True, skip workspace deletion.
    skip_firestore : bool, optional
        If True, skip Firestore cleanup.
    orphan : bool, optional
        Passed through to workspace deletion – skips Terraform destroy.
    auto_orphan_on_failure : bool, optional
        Passed through to workspace deletion.
    dry_run : bool, optional
        If True, only log what would be done.

    Returns
    -------
    bool
        True if all steps succeeded, False if any step failed.
    """
    username = user["username"]
    success = True

    # Step 1: workspaces
    if not skip_workspaces:
        workspaces = fetch_user_workspaces(username)
        if workspaces:
            console.print(
                f"  [dim]Found {len(workspaces)} workspace(s) for '{username}'[/dim]"
            )
            for ws in workspaces:
                ws_name = ws.get("name", "")
                ok = delete_workspace_cli(
                    owner_name=username,
                    workspace_name=ws_name,
                    orphan=orphan,
                    auto_orphan_on_failure=auto_orphan_on_failure,
                    dry_run=dry_run,
                )
                if not ok:
                    success = False

    # Step 2: Coder account
    if suspend:
        ok = suspend_coder_user(username, dry_run=dry_run)
    else:
        ok = delete_coder_user(username, dry_run=dry_run)
    if not ok:
        success = False

    # Step 3: Firestore
    if not skip_firestore:
        try:
            if dry_run:
                console.print(
                    f"  [blue]Would remove[/blue] '{username}' from Firestore"
                )
            else:
                db = get_firestore_client()
                handle = normalize_github_handle(username)
                delete_participants(
                    db,
                    [handle],
                    delete_empty_teams=True,
                    dry_run=False,
                )
        except Exception as e:
            console.print(
                f"  [yellow]⚠[/yellow] Firestore cleanup failed for '{username}': {e}"
            )
            success = False

    return success


def display_stale_users_table(
    stale_users: list[dict[str, Any]], org: str
) -> None:
    """
    Display a summary table of Coder users to be offboarded.

    Parameters
    ----------
    stale_users : list[dict[str, Any]]
        Coder user records that are stale.
    org : str
        GitHub org name, used in the table title.
    """
    table = Table(
        title=f"Coder Users Not in GitHub Org '{org}'",
        show_header=True,
        header_style="bold red",
    )
    table.add_column("Username", style="yellow")
    table.add_column("Email", style="dim")
    table.add_column("Status", style="dim")
    table.add_column("Created At", style="dim")
    table.add_column("Last Seen", style="dim")

    for user in sorted(stale_users, key=lambda u: u.get("created_at", "")):
        created = user.get("created_at", "")[:10]
        last_seen = user.get("last_seen_at", "")[:10]
        table.add_row(
            user["username"],
            user.get("email", ""),
            user.get("status", ""),
            created,
            last_seen,
        )

    console.print()
    console.print(table)
    console.print()


def offboard_users(
    stale_users: list[dict[str, Any]],
    suspend: bool = False,
    skip_workspaces: bool = False,
    skip_firestore: bool = False,
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Offboard a list of stale Coder users.

    Parameters
    ----------
    stale_users : list[dict[str, Any]]
        Coder user records to offboard.
    suspend : bool, optional
        Suspend Coder accounts instead of deleting them.
    skip_workspaces : bool, optional
        Skip workspace deletion.
    skip_firestore : bool, optional
        Skip Firestore cleanup.
    orphan : bool, optional
        Orphan GCP resources instead of destroying via Terraform.
    auto_orphan_on_failure : bool, optional
        Retry workspace deletion with --orphan on Terraform failure.
    dry_run : bool, optional
        Log actions without making changes.

    Returns
    -------
    tuple[int, int]
        Tuple of (success_count, failed_count).
    """
    success_count = 0
    failed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Offboarding users...", total=len(stale_users)
        )

        for user in stale_users:
            console.print(f"\n[bold]Offboarding:[/bold] {user['username']}")
            ok = offboard_user(
                user,
                suspend=suspend,
                skip_workspaces=skip_workspaces,
                skip_firestore=skip_firestore,
                orphan=orphan,
                auto_orphan_on_failure=auto_orphan_on_failure,
                dry_run=dry_run,
            )
            if ok:
                success_count += 1
            else:
                failed_count += 1

            progress.update(task, advance=1)

    return success_count, failed_count


def offboard_users_from_org(  # noqa: PLR0911
    org: str,
    suspend: bool = False,
    skip_workspaces: bool = False,
    skip_firestore: bool = False,
    orphan: bool = False,
    auto_orphan_on_failure: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Offboard all Coder users who are no longer members of a GitHub org.

    Parameters
    ----------
    org : str
        GitHub organization slug (e.g. ``"VectorInstitute"``).
    suspend : bool, optional
        Suspend Coder accounts instead of deleting them (safer, reversible).
    skip_workspaces : bool, optional
        Skip workspace deletion step.
    skip_firestore : bool, optional
        Skip Firestore cleanup step.
    orphan : bool, optional
        Delete workspaces without running Terraform destroy.
    auto_orphan_on_failure : bool, optional
        Automatically retry workspace deletion with --orphan on Terraform failure.
    dry_run : bool, optional
        Validate and show what would be done without making any changes.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    account_action = "suspend" if suspend else "delete"

    console.print(
        Panel.fit(
            "[bold red]Offboard Coder Users[/bold red]\n"
            f"Remove users no longer in GitHub org '{org}'",
            border_style="red",
        )
    )

    # Verify Coder CLI
    console.print("\n[cyan]Verifying Coder CLI...[/cyan]")
    try:
        result = run_coder_command(["version"], check=False)
        if result.returncode != 0:
            console.print(
                f"[red]✗[/red] Coder CLI not working: {result.stderr}"
            )
            return 1
        console.print(f"[green]✓[/green] Coder CLI: {result.stdout.strip()}")
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        return 1

    # Fetch GitHub org members
    console.print(f"\n[cyan]Fetching members of GitHub org '{org}'...[/cyan]")
    try:
        org_members = fetch_github_org_members(org)
        console.print(f"[green]✓[/green] Found {len(org_members)} org members")
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        return 1

    # Fetch Coder users
    console.print("\n[cyan]Fetching Coder users...[/cyan]")
    try:
        coder_users = fetch_coder_users()
        console.print(f"[green]✓[/green] Found {len(coder_users)} Coder users")
    except RuntimeError as e:
        console.print(f"[red]✗[/red] {e}")
        return 1

    # Identify stale users
    stale_users = find_stale_coder_users(coder_users, org_members)

    if not stale_users:
        console.print(
            f"\n[green]✓ All Coder users are current members of '{org}'.[/green] "
            "Nothing to offboard."
        )
        return 0

    console.print(
        f"\n[yellow]Found {len(stale_users)} Coder user(s) not in org '{org}'[/yellow]"
    )
    display_stale_users_table(stale_users, org)

    # Show what will happen
    steps = []
    if not skip_workspaces:
        orphan_note = " (orphan mode)" if orphan else ""
        steps.append(f"Delete Coder workspaces{orphan_note}")
    steps.append(f"{account_action.capitalize()} Coder account")
    if not skip_firestore:
        steps.append("Remove from Firestore onboarding database")

    console.print("[bold]Steps per user:[/bold]")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i}. {step}")
    console.print()

    # Confirm or skip if dry-run
    if not dry_run and not _confirm_offboard(len(stale_users), account_action):
        console.print("\n[yellow]Offboarding cancelled.[/yellow]")
        return 0

    if dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo changes will be made",
                border_style="yellow",
            )
        )

    # Process
    console.print("[bold]Offboarding Users[/bold]")
    success_count, failed_count = offboard_users(
        stale_users,
        suspend=suspend,
        skip_workspaces=skip_workspaces,
        skip_firestore=skip_firestore,
        orphan=orphan,
        auto_orphan_on_failure=auto_orphan_on_failure,
        dry_run=dry_run,
    )

    console.print(
        f"\n[green]✓ Processed {success_count + failed_count} user(s)[/green]\n"
        f"  Successful: {success_count}\n"
        f"  Failed: {failed_count}\n"
    )

    # Final summary
    if dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"Users that would be offboarded: {success_count}\n\n"
                "[dim]No changes were made[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
        return 0

    if failed_count > 0:
        console.print(
            Panel.fit(
                "[yellow]OFFBOARDING COMPLETED WITH ERRORS[/yellow]\n"
                f"Users offboarded: {success_count}\n"
                f"Users failed: {failed_count}\n\n"
                "[dim]Check errors above for details[/dim]",
                border_style="yellow",
                title="⚠ Partial Success",
            )
        )
        return 1

    console.print(
        Panel.fit(
            f"[green]OFFBOARDING COMPLETE[/green]\nUsers offboarded: {success_count}",
            border_style="green",
            title="✓ Success",
        )
    )
    return 0


def _confirm_offboard(user_count: int, account_action: str) -> bool:
    """Prompt user for offboarding confirmation."""
    console.print(
        Panel(
            f"[bold red]⚠ WARNING ⚠[/bold red]\n\n"
            f"You are about to offboard {user_count} Coder user(s).\n"
            f"Their Coder accounts will be [bold]{account_action}d[/bold] "
            "and workspaces deleted.\n\n"
            "[yellow]This action is difficult to reverse![/yellow]\n\n"
            "Type 'OFFBOARD' (in capital letters) to confirm:",
            border_style="red",
            title="⚠ Confirmation Required",
        )
    )
    confirmation = input().strip()
    if confirmation == "OFFBOARD":
        console.print()
        return True
    return False
