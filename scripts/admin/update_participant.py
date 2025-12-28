#!/usr/bin/env python3
"""Update a participant's github_handle in Firestore."""

import sys
from datetime import datetime, timezone

from utils import COLLECTION_PARTICIPANTS, console, get_firestore_client


def main() -> int:
    old_handle = "sfoustina"
    new_handle = "foustinas"

    console.print("[cyan]Connecting to Firestore...[/cyan]")
    db = get_firestore_client()
    console.print("[green]✓ Connected[/green]\n")

    # Get the old document
    console.print(f"[cyan]Fetching document for '{old_handle}'...[/cyan]")
    old_doc_ref = db.collection(COLLECTION_PARTICIPANTS).document(old_handle)
    old_doc = old_doc_ref.get()

    if not old_doc.exists:
        console.print(f"[red]✗ Document '{old_handle}' not found[/red]")
        return 1

    console.print("[green]✓ Found document[/green]")
    old_data = old_doc.to_dict()
    console.print(f"[dim]Current data: {old_data}[/dim]\n")

    # Create new document with updated handle
    console.print(f"[cyan]Creating new document for '{new_handle}'...[/cyan]")
    new_data = old_data.copy()
    new_data["github_handle"] = new_handle
    new_data["updated_at"] = datetime.now(timezone.utc)

    new_doc_ref = db.collection(COLLECTION_PARTICIPANTS).document(new_handle)
    new_doc_ref.set(new_data)
    console.print("[green]✓ Created new document[/green]\n")

    # Update team's participants list if needed
    if "team_name" in old_data:
        team_name = old_data["team_name"]
        console.print(f"[cyan]Updating team '{team_name}' participants list...[/cyan]")

        team_ref = db.collection("teams").document(team_name)
        team_doc = team_ref.get()

        if team_doc.exists:
            team_data = team_doc.to_dict()
            participants = team_data.get("participants", [])

            if old_handle in participants:
                participants.remove(old_handle)
                participants.append(new_handle)
                team_ref.update(
                    {
                        "participants": participants,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                console.print("[green]✓ Updated team participants list[/green]\n")

    # Delete old document
    console.print(f"[cyan]Deleting old document '{old_handle}'...[/cyan]")
    old_doc_ref.delete()
    console.print("[green]✓ Deleted old document[/green]\n")

    console.print(
        f"[green bold]✓ Successfully updated '{old_handle}' to '{new_handle}'[/green bold]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
