#!/usr/bin/env python3
"""
Setup global/shared keys in Firestore.

This script stores shared API keys and configuration (Embedding, Weaviate,
Langfuse host) in the Firestore global_keys collection. These keys are shared
across all participants.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from google.cloud import firestore  # type: ignore[attr-defined]
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from utils import (
    COLLECTION_GLOBAL_KEYS,
    GLOBAL_KEYS_DOC_ID,
    console,
    get_firestore_client,
    mask_sensitive_value,
)


# Required global keys
REQUIRED_KEYS = {
    "EMBEDDING_API_KEY": "API key for the embedding service",
    "EMBEDDING_BASE_URL": "Base URL for the embedding service",
    "WEAVIATE_API_KEY": "API key for Weaviate",
    "WEAVIATE_HTTP_HOST": "Weaviate HTTP host",
    "WEAVIATE_GRPC_HOST": "Weaviate gRPC host",
    "WEAVIATE_HTTP_PORT": "Weaviate HTTP port",
    "WEAVIATE_GRPC_PORT": "Weaviate gRPC port",
    "WEAVIATE_HTTP_SECURE": "Weaviate HTTP secure (true/false)",
    "WEAVIATE_GRPC_SECURE": "Weaviate gRPC secure (true/false)",
    "LANGFUSE_HOST": "Langfuse host URL (shared across all teams)",
    "WEB_SEARCH_BASE_URL": "Base URL for the web search service",
}


def load_keys_from_env(env_file: Path) -> dict[str, str]:
    """
    Load global keys from a .env file.

    Parameters
    ----------
    env_file : Path
        Path to the .env file.

    Returns
    -------
    dict[str, str]
        Dictionary of key-value pairs from the .env file.

    Raises
    ------
    FileNotFoundError
        If the environment file does not exist.
    """
    if not env_file.exists():
        raise FileNotFoundError(f"Environment file not found: {env_file}")

    console.print(f"[cyan]Loading keys from:[/cyan] {env_file}")
    env_values = dotenv_values(env_file)

    # Filter to only include required keys
    return {
        key: value
        for key, value in env_values.items()
        if key in REQUIRED_KEYS and value is not None
    }


def validate_keys(keys: dict[str, str]) -> tuple[bool, list[str]]:
    """
    Validate that all required keys are present and non-empty.

    Parameters
    ----------
    keys : dict[str, str]
        Dictionary of keys to validate.

    Returns
    -------
    tuple[bool, list[str]]
        Tuple of (is_valid, list of missing/empty keys).
    """
    missing_keys = []

    for key in REQUIRED_KEYS:
        if key not in keys or not keys[key]:
            missing_keys.append(key)

    is_valid = len(missing_keys) == 0
    return is_valid, missing_keys


def prompt_for_keys() -> dict[str, str]:
    """
    Interactively prompt user for global keys.

    Returns
    -------
    dict[str, str]
        Dictionary of keys entered by user.
    """
    console.print(
        Panel(
            "[yellow]Interactive Mode[/yellow]\n"
            "Please provide the following global configuration values.\n"
            "These will be shared across all bootcamp participants.",
            border_style="yellow",
        )
    )

    keys = {}

    for key, description in REQUIRED_KEYS.items():
        while True:
            value = Prompt.ask(f"\n[cyan]{key}[/cyan]\n[dim]{description}[/dim]")
            if value.strip():
                keys[key] = value.strip()
                break
            console.print("[red]Value cannot be empty, please try again[/red]")

    return keys


def get_existing_global_keys(db: firestore.Client) -> dict[str, str] | None:
    """
    Retrieve existing global keys from Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.

    Returns
    -------
    dict[str, str] | None
        Existing global keys or None if not found.
    """
    doc_ref = db.collection(COLLECTION_GLOBAL_KEYS).document(GLOBAL_KEYS_DOC_ID)
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    return None


def display_keys_table(keys: dict[str, str], title: str = "Global Keys") -> None:
    """
    Display keys in a formatted table.

    Parameters
    ----------
    keys : dict[str, str]
        Dictionary of keys to display.
    title : str, optional
        Table title, by default "Global Keys".
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Key", style="yellow")
    table.add_column("Value", style="green")
    table.add_column("Description", style="dim")

    for key, description in REQUIRED_KEYS.items():
        value = keys.get(key, "NOT SET")

        # Mask sensitive values
        if value != "NOT SET":
            display_value = mask_sensitive_value(value)
        else:
            display_value = "[red]NOT SET[/red]"

        table.add_row(key, display_value, description)

    console.print()
    console.print(table)
    console.print()


def store_global_keys(
    db: firestore.Client, keys: dict[str, str], dry_run: bool = False
) -> bool:
    """
    Store global keys in Firestore.

    Parameters
    ----------
    db : firestore.Client
        Firestore client instance.
    keys : dict[str, str]
        Dictionary of keys to store.
    dry_run : bool, optional
        If True, only log what would be done without making changes.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    # Check if keys already exist
    existing_keys = get_existing_global_keys(db)

    if existing_keys:
        console.print(
            "[yellow]Global keys already exist in Firestore - will update[/yellow]"
        )

    # Prepare document data
    doc_data: dict[str, Any] = keys.copy()
    doc_data["updated_at"] = datetime.now(timezone.utc)

    if not existing_keys:
        doc_data["created_at"] = datetime.now(timezone.utc)

    if dry_run:
        console.print(
            Panel(
                "[blue]DRY RUN[/blue]\nWould store the following keys to Firestore",
                border_style="blue",
            )
        )
        display_keys_table(keys, "Keys to be stored")
        return True

    try:
        doc_ref = db.collection(COLLECTION_GLOBAL_KEYS).document(GLOBAL_KEYS_DOC_ID)
        doc_ref.set(doc_data)
        console.print("[green]✓ Successfully stored global keys in Firestore[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Failed to store keys in Firestore:[/red] {e}")
        return False


def main() -> int:  # noqa: PLR0912
    """
    Set up global keys in Firestore.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Setup global/shared keys in Firestore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env-file",
        type=str,
        help="Path to .env file containing global keys (if not provided, will prompt interactively)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--show-existing",
        action="store_true",
        help="Show existing global keys and exit",
    )

    args = parser.parse_args()

    # Print header
    console.print(
        Panel.fit(
            "[bold cyan]Global Keys Setup[/bold cyan]\n"
            "Configure shared API keys and configuration for all participants",
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

    # If --show-existing, display and exit
    if args.show_existing:
        existing_keys = get_existing_global_keys(db)
        if existing_keys:
            display_keys_table(existing_keys, "Existing Global Keys")
        else:
            console.print("[yellow]No global keys found in Firestore[/yellow]")
        return 0

    # Load keys from .env file or interactive input
    if args.env_file:
        try:
            env_path = Path(args.env_file)
            keys = load_keys_from_env(env_path)
            console.print(f"[green]✓ Loaded {len(keys)} keys from file[/green]\n")
        except Exception as e:
            console.print(f"[red]✗ Failed to load keys from .env file:[/red] {e}")
            return 1
    else:
        keys = prompt_for_keys()

    # Validate keys
    console.print("\n[cyan]Validating keys...[/cyan]")
    is_valid, missing_keys = validate_keys(keys)

    if not is_valid:
        console.print("[red]✗ Validation failed! Missing or empty keys:[/red]")
        for key in missing_keys:
            console.print(f"  [red]•[/red] {key}: {REQUIRED_KEYS[key]}")
        return 1

    console.print("[green]✓ All required keys present![/green]")

    # Display keys to be stored
    display_keys_table(keys, "Keys to Store")

    if args.dry_run:
        console.print(
            Panel(
                "[yellow]DRY RUN MODE[/yellow]\nNo changes will be made to Firestore",
                border_style="yellow",
            )
        )

    # Store keys in Firestore
    console.print("[cyan]Storing global keys in Firestore...[/cyan]")
    success = store_global_keys(db, keys, dry_run=args.dry_run)

    if not success:
        return 1

    # Final summary
    if args.dry_run:
        console.print(
            Panel.fit(
                "[yellow]DRY RUN COMPLETE[/yellow]\n"
                f"{len(keys)} keys validated\n\n"
                "[dim]No changes were made to Firestore[/dim]",
                border_style="yellow",
                title="Summary",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[green]GLOBAL KEYS SETUP COMPLETE[/green]\n"
                f"Stored {len(keys)} keys in Firestore\n"
                f"Document: {COLLECTION_GLOBAL_KEYS}/{GLOBAL_KEYS_DOC_ID}",
                border_style="green",
                title="✓ Success",
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
