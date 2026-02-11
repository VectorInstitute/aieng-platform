"""Admin CLI dispatcher for aieng-platform-onboard."""

import argparse
import sys

from aieng_platform_onboard.admin.create_gemini_keys import (
    create_gemini_keys_for_teams,
)
from aieng_platform_onboard.admin.delete_participants import (
    delete_participants_from_csv,
)
from aieng_platform_onboard.admin.delete_workspaces import (
    delete_workspaces_before_date,
)
from aieng_platform_onboard.admin.setup_participants import (
    setup_participants_from_csv,
)


def main() -> int:
    """
    Admin CLI entry point for admin commands.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        prog="onboard admin",
        description="Admin commands for managing bootcamp participants and teams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Admin command to run",
        required=True,
    )

    # setup-participants subcommand
    setup_participants_parser = subparsers.add_parser(
        "setup-participants",
        help="Setup participants and teams from CSV file",
        description="Load participants and teams from CSV into Firestore",
    )
    setup_participants_parser.add_argument(
        "csv_file",
        type=str,
        help="Path to CSV file with columns: github_handle, team_name, email (optional), first_name (optional), last_name (optional)",
    )
    setup_participants_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be done without making changes",
    )

    # delete-participants subcommand
    delete_participants_parser = subparsers.add_parser(
        "delete-participants",
        help="Delete participants from Firestore database",
        description="Remove participants and optionally empty teams from Firestore",
    )
    delete_participants_parser.add_argument(
        "csv_file",
        type=str,
        help="Path to CSV file with column: github_handle",
    )
    delete_participants_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be done without making changes",
    )
    delete_participants_parser.add_argument(
        "--keep-empty-teams",
        action="store_true",
        help="Keep teams even if they become empty after removing participants",
    )

    # delete-workspaces subcommand
    delete_workspaces_parser = subparsers.add_parser(
        "delete-workspaces",
        help="Delete Coder workspaces created before a specified date",
        description="Remove Coder workspaces and associated GCP resources (VMs, disks)",
    )
    delete_workspaces_parser.add_argument(
        "--before",
        type=str,
        required=True,
        help="Delete workspaces created before this date (YYYY-MM-DD format)",
    )
    delete_workspaces_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes",
    )
    delete_workspaces_parser.add_argument(
        "--orphan",
        action="store_true",
        help="Delete workspaces without removing GCP resources (use for broken workspaces)",
    )
    delete_workspaces_parser.add_argument(
        "--no-auto-orphan",
        action="store_true",
        help="Disable automatic retry with --orphan when Terraform fails",
    )

    # create-gemini-keys subcommand
    create_gemini_keys_parser = subparsers.add_parser(
        "create-gemini-keys",
        help="Create Gemini API keys for teams",
        description="Automatically create and configure Gemini API keys for teams in GCP",
    )
    create_gemini_keys_parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="GCP project ID where API keys will be created",
    )
    create_gemini_keys_parser.add_argument(
        "--bootcamp",
        type=str,
        required=True,
        help="Bootcamp name to use in API key naming (e.g., 'agent-bootcamp')",
    )
    create_gemini_keys_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be done without making changes",
    )
    create_gemini_keys_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation of created keys against Gemini API",
    )
    create_gemini_keys_parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Recreate API keys for teams that already have them",
    )
    create_gemini_keys_parser.add_argument(
        "--teams",
        type=str,
        help="Comma-separated list of specific team names to process",
    )

    args = parser.parse_args()

    # Route to appropriate command handler
    if args.command == "setup-participants":
        return setup_participants_from_csv(args.csv_file, dry_run=args.dry_run)
    if args.command == "delete-participants":
        return delete_participants_from_csv(
            args.csv_file,
            delete_empty_teams=not args.keep_empty_teams,
            dry_run=args.dry_run,
        )
    if args.command == "delete-workspaces":
        return delete_workspaces_before_date(
            before_date=args.before,
            orphan=args.orphan,
            auto_orphan_on_failure=not args.no_auto_orphan,
            dry_run=args.dry_run,
        )
    if args.command == "create-gemini-keys":
        # Parse teams list if provided
        team_names = None
        if args.teams:
            team_names = [t.strip() for t in args.teams.split(",")]

        return create_gemini_keys_for_teams(
            project_id=args.project,
            bootcamp_name=args.bootcamp,
            dry_run=args.dry_run,
            skip_validation=args.skip_validation,
            overwrite_existing=args.overwrite_existing,
            team_names=team_names,
        )

    # Should never reach here due to required=True
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
