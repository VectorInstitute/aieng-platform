"""Admin CLI dispatcher for aieng-platform-onboard."""

import argparse
import sys

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

    args = parser.parse_args()

    # Route to appropriate command handler
    if args.command == "setup-participants":
        return setup_participants_from_csv(args.csv_file, dry_run=args.dry_run)

    # Should never reach here due to required=True
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
