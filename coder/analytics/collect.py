#!/usr/bin/env python3
"""
Collect Coder workspace and template analytics and upload to Google Cloud Storage.

This script:
1. Fetches workspace data using the Coder CLI
2. Fetches template data using the Coder CLI
3. Creates a JSON snapshot with timestamp
4. Uploads the snapshot to GCS bucket
5. Updates the 'latest.json' file in the bucket
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import requests
from rich.console import Console


# Global console instance for rich output
console = Console()


try:
    from google.cloud import firestore, storage  # type: ignore[attr-defined]
except ImportError:
    console.print(
        "[red]Error: google-cloud-storage or google-cloud-firestore not installed.[/red]"
    )
    console.print("Run: pip install google-cloud-storage google-cloud-firestore")
    sys.exit(1)


def run_command(cmd: list[str]) -> Any:
    """Run a shell command and return JSON output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Error running command {' '.join(cmd)}:[/red] {e}")
        console.print(f"[red]stderr:[/red] {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(
            f"[red]✗ Error parsing JSON from command {' '.join(cmd)}:[/red] {e}"
        )
        sys.exit(1)


def get_coder_api_config() -> tuple[str, str]:
    """Get Coder API URL and session token from environment.

    Returns
    -------
    tuple[str, str]
        Tuple of (api_url, session_token)
    """
    # Get API URL from environment or use default
    api_url = os.getenv("CODER_URL", "https://platform.vectorinstitute.ai")

    # Get token from environment (try CODER_TOKEN or CODER_SESSION_TOKEN)
    session_token = os.getenv("CODER_TOKEN") or os.getenv("CODER_SESSION_TOKEN")
    if not session_token:
        console.print(
            "[red]✗ Error: CODER_TOKEN or CODER_SESSION_TOKEN environment variable not set[/red]"
        )
        sys.exit(1)

    return api_url, session_token


def fetch_workspace_builds(
    workspace_id: str, api_url: str, session_token: str
) -> list[dict[str, Any]]:
    """Fetch all builds for a workspace using the Coder API.

    Parameters
    ----------
    workspace_id : str
        The UUID of the workspace
    api_url : str
        The Coder API base URL
    session_token : str
        The Coder session token for authentication

    Returns
    -------
    list[dict[str, Any]]
        List of build objects for this workspace
    """
    url = f"{api_url}/api/v2/workspaces/{workspace_id}/builds"
    headers = {"Coder-Session-Token": session_token}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        console.print(
            f"[yellow]⚠ Warning: Failed to fetch builds for workspace {workspace_id}:[/yellow] {e}"
        )
        return []


def calculate_build_usage_hours(build: dict[str, Any]) -> float:
    """Calculate usage hours for a single build based on agent connection times.

    Parameters
    ----------
    build : dict[str, Any]
        A build object containing resources and agents

    Returns
    -------
    float
        Usage hours for this build (0 if no valid connection data)
    """
    try:
        resources = build.get("resources", [])
        earliest_connection = None
        latest_connection = None

        for resource in resources:
            agents = resource.get("agents", [])
            for agent in agents:
                first_connected = agent.get("first_connected_at")
                last_connected = agent.get("last_connected_at")

                if first_connected:
                    first_dt = datetime.fromisoformat(
                        first_connected.replace("Z", "+00:00")
                    )
                    if earliest_connection is None or first_dt < earliest_connection:
                        earliest_connection = first_dt

                if last_connected:
                    last_dt = datetime.fromisoformat(
                        last_connected.replace("Z", "+00:00")
                    )
                    if latest_connection is None or last_dt > latest_connection:
                        latest_connection = last_dt

        # Calculate hours between first and last connection
        if earliest_connection and latest_connection:
            delta = latest_connection - earliest_connection
            return delta.total_seconds() / 3600.0

        return 0.0
    except Exception as e:
        console.print(
            f"[yellow]⚠ Warning: Error calculating build usage hours:[/yellow] {e}"
        )
        return 0.0


def calculate_workspace_total_usage(builds: list[dict[str, Any]]) -> float:
    """Calculate total usage hours across all builds for a workspace.

    Parameters
    ----------
    builds : list[dict[str, Any]]
        List of build objects for a workspace

    Returns
    -------
    float
        Total usage hours summed across all builds
    """
    total_hours = 0.0
    for build in builds:
        total_hours += calculate_build_usage_hours(build)
    return total_hours


def fetch_user_activity_insights(
    api_url: str, session_token: str, start_time: str, end_time: str
) -> dict[str, float]:
    """Fetch user activity insights from Coder API.

    Parameters
    ----------
    api_url : str
        The Coder API base URL
    session_token : str
        The Coder session token for authentication
    start_time : str
        Start time in ISO 8601 format (e.g., "2025-11-01T00:00:00Z")
    end_time : str
        End time in ISO 8601 format (e.g., "2025-12-10T00:00:00Z")

    Returns
    -------
    dict[str, float]
        Mapping of username (lowercase) -> active_hours
    """
    url = f"{api_url}/api/v2/insights/user-activity"
    headers = {"Coder-Session-Token": session_token}
    params = {"start_time": start_time, "end_time": end_time}

    response = None
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Create mapping of username -> active hours
        activity_map = {}
        users = data.get("report", {}).get("users", [])
        for user in users:
            username = user.get("username", "").lower()
            seconds = user.get("seconds", 0)
            hours = round(seconds / 3600.0, 2)
            activity_map[username] = hours

        return activity_map
    except requests.RequestException as e:
        console.print(
            f"[yellow]⚠ Warning: Failed to fetch user activity insights:[/yellow] {e}"
        )
        try:
            error_details = response.json() if response else {}
            console.print(f"[yellow]Error details:[/yellow] {error_details}")
        except Exception:
            pass
        return {}


def get_latest_snapshot(bucket_name: str) -> dict[str, Any] | None:
    """Get the most recent snapshot from GCS.

    Parameters
    ----------
    bucket_name : str
        Name of the GCS bucket containing snapshots

    Returns
    -------
    dict[str, Any] | None
        The previous snapshot data, or None if not found
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # List all snapshots and get the most recent one
        blobs = list(bucket.list_blobs(prefix="snapshots/"))

        if not blobs:
            return None

        # Sort by name (which includes timestamp) to get most recent
        snapshot_blobs = [b for b in blobs if b.name.endswith(".json")]
        if not snapshot_blobs:
            return None

        # Get the most recent snapshot (last in sorted order)
        snapshot_blobs.sort(key=lambda b: b.name)
        latest_blob = snapshot_blobs[-1]

        console.print(f"  [dim]Using previous snapshot: {latest_blob.name}[/dim]")

        content = latest_blob.download_as_text()
        return json.loads(content)
    except Exception as e:
        console.print(
            f"  [yellow]⚠ Warning: Could not load previous snapshot:[/yellow] {e}"
        )
        return None


def get_historical_participant_data(bucket_name: str) -> dict[str, dict[str, Any]]:
    """Get historical participant data from the previous snapshot.

    Parameters
    ----------
    bucket_name : str
        Name of the GCS bucket containing snapshots

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of github_handle (lowercase) -> {
            'team_name': str,
            'first_name': str | None,
            'last_name': str | None
        }
    """
    console.print(
        "[cyan]Fetching historical participant data from previous snapshot...[/cyan]"
    )

    snapshot = get_latest_snapshot(bucket_name)
    if not snapshot:
        console.print("  [yellow]No previous snapshots found[/yellow]")
        return {}

    historical_data = {}
    for workspace in snapshot.get("workspaces", []):
        owner_name = workspace.get("owner_name", "").lower()
        team_name = workspace.get("team_name")
        first_name = workspace.get("owner_first_name")
        last_name = workspace.get("owner_last_name")

        # Only store if we have actual data (not null/None)
        if team_name:
            historical_data[owner_name] = {
                "team_name": team_name,
                "first_name": first_name,
                "last_name": last_name,
            }

    console.print(
        f"[green]✓[/green] Loaded historical data for {len(historical_data)} participants"
    )
    return historical_data


def get_historical_accumulated_usage(
    bucket_name: str,
) -> dict[str, dict[str, Any]]:
    """Get historical accumulated usage data from the previous snapshot.

    Parameters
    ----------
    bucket_name : str
        Name of the GCS bucket containing snapshots

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of user_template key -> {
            'owner_name': str,
            'template_name': str,
            'team_name': str,
            'total_accumulated_hours': float,
            'last_updated': str,
            'first_seen': str
        }
    """
    console.print(
        "[cyan]Fetching historical accumulated usage from previous snapshot...[/cyan]"
    )

    snapshot = get_latest_snapshot(bucket_name)
    if not snapshot:
        console.print("  [yellow]No previous snapshots found[/yellow]")
        return {}

    accumulated_usage = snapshot.get("accumulated_usage", {})

    console.print(
        f"[green]✓[/green] Loaded {len(accumulated_usage)} accumulated usage records"
    )
    return accumulated_usage


def get_historical_workspace_snapshots(
    bucket_name: str,
) -> dict[str, dict[str, Any]]:
    """Get workspace usage snapshots from the previous collection.

    Parameters
    ----------
    bucket_name : str
        Name of the GCS bucket containing snapshots

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of workspace_id -> {
            'active_hours': float,
            'owner_name': str,
            'template_name': str
        }
    """
    console.print(
        "[cyan]Fetching historical workspace snapshots from previous snapshot...[/cyan]"
    )

    snapshot = get_latest_snapshot(bucket_name)
    if not snapshot:
        console.print("  [yellow]No previous snapshots found[/yellow]")
        return {}

    workspace_snapshots = snapshot.get("workspace_usage_snapshot", {})

    console.print(
        f"[green]✓[/green] Loaded {len(workspace_snapshots)} workspace usage snapshots"
    )
    return workspace_snapshots


def get_participant_mappings() -> dict[str, dict[str, Any]]:
    """Get current participant data from Firestore.

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of github_handle (lowercase) -> {
            'team_name': str,
            'first_name': str | None,
            'last_name': str | None
        }
    """
    console.print("[cyan]Fetching current participant data from Firestore...[/cyan]")

    project_id = "coderd"
    database_id = "onboarding"

    db = firestore.Client(project=project_id, database=database_id)

    mappings = {}
    participants = db.collection("participants").stream()

    for doc in participants:
        data = doc.to_dict()
        if data:
            github_handle = doc.id.lower()
            mappings[github_handle] = {
                "team_name": data.get("team_name", "Unassigned"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
            }

    console.print(
        f"[green]✓[/green] Loaded {len(mappings)} current participant mappings"
    )
    return mappings


def merge_participant_data(
    historical_data: dict[str, dict[str, Any]], current_data: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Merge historical and current participant data, preserving history.

    Historical data takes precedence to preserve team assignments even after
    participants are removed from Firestore.

    Parameters
    ----------
    historical_data : dict[str, dict[str, Any]]
        Historical participant data from previous snapshot
    current_data : dict[str, dict[str, Any]]
        Current participant data from Firestore

    Returns
    -------
    dict[str, dict[str, Any]]
        Merged participant data with historical preservation
    """
    console.print("[cyan]Merging historical and current participant data...[/cyan]")

    # Start with historical data (preserves deleted participants)
    merged = historical_data.copy()

    # Update with current data (adds new participants, updates existing)
    for handle, data in current_data.items():
        merged[handle] = data

    console.print(f"[green]✓[/green] Merged data: {len(merged)} total participants")
    console.print(
        f"  [dim]Historical only (deleted):[/dim] {len(set(historical_data.keys()) - set(current_data.keys()))}"
    )
    console.print(f"  [dim]Current (active):[/dim] {len(current_data)}")

    return merged


def calculate_accumulated_usage(
    current_workspaces: list[dict[str, Any]],
    historical_accumulated: dict[str, dict[str, Any]],
    historical_workspace_snapshots: dict[str, dict[str, Any]],
    participant_mappings: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Calculate accumulated active hours, preserving history.

    Preserves history even for deleted workspaces. Tracks active hours (from
    Insights API) which represent time with active app connections.

    Parameters
    ----------
    current_workspaces : list[dict[str, Any]]
        List of current workspace objects with active_hours (from Insights API)
    historical_accumulated : dict[str, dict[str, Any]]
        Historical accumulated usage from previous snapshot
    historical_workspace_snapshots : dict[str, dict[str, Any]]
        Workspace usage from previous snapshot (for delta calculation)
    participant_mappings : dict[str, dict[str, Any]]
        Current participant team mappings

    Returns
    -------
    tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]
        (accumulated_usage, workspace_usage_snapshot)
    """
    console.print(
        "[cyan]Calculating accumulated active hours with historical preservation...[/cyan]"
    )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Start with historical accumulated usage (preserves deleted workspaces)
    accumulated_usage = {k: v.copy() for k, v in historical_accumulated.items()}

    # Build new workspace snapshot
    workspace_usage_snapshot = {}

    # Track per-user active hours (Insights API returns per-user, not per-workspace)
    user_active_hours: dict[str, float] = {}
    for workspace in current_workspaces:
        owner_name = workspace.get("owner_name", "").lower()
        active_hours = workspace.get("active_hours", 0.0)
        # Take max since active_hours is per-user (same across all their workspaces)
        user_active_hours[owner_name] = max(
            user_active_hours.get(owner_name, 0.0), active_hours
        )

    # Build workspace snapshot and track user-template combinations
    user_template_workspaces = {}  # Track workspaces per user-template
    for workspace in current_workspaces:
        workspace_id = workspace.get("id")
        owner_name = workspace.get("owner_name", "").lower()
        template_name = workspace.get("template_name", "")
        current_active = user_active_hours.get(owner_name, 0.0)

        if not workspace_id or not owner_name or not template_name:
            continue

        # Update workspace snapshot for next collection
        workspace_usage_snapshot[workspace_id] = {
            "active_hours": current_active,
            "owner_name": owner_name,
            "template_name": template_name,
        }

        # Track workspaces per user-template for delta calculation
        key = f"{owner_name}_{template_name}"
        if key not in user_template_workspaces:
            user_template_workspaces[key] = {
                "owner_name": owner_name,
                "template_name": template_name,
                "current_active": current_active,
                "workspace_ids": [],
            }
        user_template_workspaces[key]["workspace_ids"].append(workspace_id)

    # Now calculate deltas per user-template combination (not per workspace)
    for key, data in user_template_workspaces.items():
        owner_name = data["owner_name"]
        template_name = data["template_name"]
        current_active = data["current_active"]
        workspace_ids = data["workspace_ids"]

        # Get previous active hours for this user from any of their workspaces
        # (they all have the same per-user value)
        previous_active = 0.0
        for ws_id in workspace_ids:
            if ws_id in historical_workspace_snapshots:
                previous_active = historical_workspace_snapshots[ws_id].get(
                    "active_hours", 0.0
                )
                break  # All workspaces have same per-user value

        # Calculate delta (new active hours since last snapshot)
        delta = max(0.0, current_active - previous_active)

        # Get team name (current mapping takes precedence, then historical)
        participant_data = participant_mappings.get(owner_name, {})
        team_name = participant_data.get("team_name")
        if not team_name and key in accumulated_usage:
            # Preserve historical team assignment
            team_name = accumulated_usage[key].get("team_name", "Unassigned")
        if not team_name:
            team_name = "Unassigned"

        # Update accumulated usage (once per user-template combination)
        if key in accumulated_usage:
            # Existing record: add delta to accumulated total
            accumulated_usage[key]["total_active_hours"] += delta
            accumulated_usage[key]["last_updated"] = now
            # Update team name (in case it changed)
            accumulated_usage[key]["team_name"] = team_name
            # Add new workspace IDs to the list
            existing_ws_ids = set(accumulated_usage[key].get("workspace_ids", []))
            for ws_id in workspace_ids:
                existing_ws_ids.add(ws_id)
            accumulated_usage[key]["workspace_ids"] = list(existing_ws_ids)
        else:
            # New record: start accumulating
            accumulated_usage[key] = {
                "owner_name": owner_name,
                "template_name": template_name,
                "team_name": team_name,
                "total_active_hours": current_active,
                "workspace_ids": workspace_ids,
                "last_updated": now,
                "first_seen": now,
            }

    console.print(
        f"[green]✓[/green] Calculated accumulated active hours for {len(accumulated_usage)} user-template combinations"
    )
    console.print(
        f"  [dim]Current workspace snapshots:[/dim] {len(workspace_usage_snapshot)}"
    )
    console.print(
        f"  [dim]Historical records preserved:[/dim] {len(accumulated_usage) - len(workspace_usage_snapshot)}"
    )

    return accumulated_usage, workspace_usage_snapshot


def fetch_workspaces(
    participant_mappings: dict[str, dict[str, Any]], api_url: str, session_token: str
) -> list[dict[str, Any]]:
    """Fetch workspaces using Coder CLI and enrich with build data.

    Parameters
    ----------
    participant_mappings : dict[str, dict[str, Any]]
        Mapping of github_handle -> participant data (team_name, first_name, last_name)
    api_url : str
        Coder API base URL
    session_token : str
        Coder session token for API authentication

    Returns
    -------
    list[dict[str, Any]]
        List of workspace objects with builds, usage hours, active hours, and team data
    """
    console.print("[cyan]Fetching workspaces from Coder...[/cyan]")
    workspaces = run_command(["coder", "list", "-a", "-o", "json"])

    # Teams to exclude from analytics
    # Historical team data is preserved from previous snapshots
    # "Unassigned" only appears for new users not in any historical snapshot
    # or Firestore
    excluded_teams = ["facilitators", "Unassigned"]

    original_count = len(workspaces)

    # Filter out workspaces owned by users in excluded teams
    filtered_workspaces = []
    for ws in workspaces:
        owner_name = ws.get("owner_name", "").lower()
        participant_data = participant_mappings.get(owner_name, {})
        team_name = participant_data.get("team_name", "Unassigned")

        if team_name not in excluded_teams:
            filtered_workspaces.append(ws)

    filtered_count = original_count - len(filtered_workspaces)
    if filtered_count > 0:
        console.print(
            f"[green]✓[/green] Filtered out {filtered_count} workspaces from excluded teams: {', '.join(excluded_teams)}"
        )

    console.print(f"[green]✓[/green] Fetched {len(filtered_workspaces)} workspaces")

    # Fetch user activity insights (active hours)
    # Use a wide time range to capture all activity
    # Find earliest workspace creation date
    console.print("[cyan]Fetching user activity insights...[/cyan]")
    earliest_created = min(
        (
            datetime.fromisoformat(ws.get("created_at", "").replace("Z", "+00:00"))
            for ws in filtered_workspaces
            if ws.get("created_at")
        ),
        default=datetime.now(timezone.utc),
    )
    # Normalize to midnight (00:00:00) as required by the API
    start_time = earliest_created.replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Normalize end time to the start of the current hour (required by API)
    now = datetime.now(timezone.utc)
    end_time = now.replace(minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    activity_map = fetch_user_activity_insights(
        api_url, session_token, start_time, end_time
    )
    console.print(
        f"[green]✓[/green] Fetched activity data for {len(activity_map)} users"
    )

    # Enrich workspaces with full build history and usage hours
    console.print(
        "[cyan]Enriching workspaces with build history and active hours...[/cyan]"
    )
    for i, workspace in enumerate(filtered_workspaces, 1):
        workspace_id = workspace.get("id")
        if workspace_id:
            # Fetch all builds for this workspace
            builds = fetch_workspace_builds(workspace_id, api_url, session_token)
            workspace["all_builds"] = builds

            # Calculate total usage hours across all builds
            total_usage_hours = calculate_workspace_total_usage(builds)
            workspace["total_usage_hours"] = round(total_usage_hours, 2)

        # Add active hours from activity insights
        # NOTE: active_hours is per-USER (not per-workspace) and includes
        # ALL TIME activity. Users with multiple workspaces will have the
        # same value on each workspace. The frontend aggregation logic
        # handles this correctly by counting each user once.
        owner_name = workspace.get("owner_name", "").lower()
        workspace["active_hours"] = activity_map.get(owner_name, 0.0)

        # Enrich with participant data (team and name)
        # This ensures all data needed for dashboard is in the snapshot
        participant_data = participant_mappings.get(owner_name, {})
        workspace["team_name"] = participant_data.get("team_name", "Unassigned")
        workspace["owner_first_name"] = participant_data.get("first_name")
        workspace["owner_last_name"] = participant_data.get("last_name")

        # Progress indicator
        if i % 10 == 0:
            console.print(
                f"  [dim]Processed {i}/{len(filtered_workspaces)} workspaces...[/dim]"
            )

    console.print(
        f"[green]✓[/green] Enriched {len(filtered_workspaces)} workspaces with build history and active hours"
    )
    return filtered_workspaces


def fetch_templates() -> list[dict[str, Any]]:
    """Fetch all templates using Coder CLI."""
    console.print("[cyan]Fetching templates from Coder...[/cyan]")
    templates_raw = run_command(["coder", "templates", "list", "-o", "json"])

    # Unwrap the "Template" object from each item
    templates = []
    for item in templates_raw:
        if "Template" in item:
            templates.append(item["Template"])
        else:
            templates.append(item)

    # Filter out kubernetes-gpu template
    templates = [t for t in templates if t.get("name") != "kubernetes-gpu"]

    console.print(f"[green]✓[/green] Fetched {len(templates)} templates")
    return templates


def create_snapshot(
    workspaces: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    accumulated_usage: dict[str, dict[str, Any]],
    workspace_usage_snapshot: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Create a snapshot object with timestamp and accumulated usage data."""
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    snapshot = {
        "timestamp": timestamp,
        "workspaces": workspaces,
        "templates": templates,
        "accumulated_usage": accumulated_usage,
        "workspace_usage_snapshot": workspace_usage_snapshot,
    }

    console.print(f"[green]✓[/green] Created snapshot at {timestamp}")
    console.print(f"  [dim]Accumulated usage records:[/dim] {len(accumulated_usage)}")
    console.print(f"  [dim]Workspace snapshots:[/dim] {len(workspace_usage_snapshot)}")
    return snapshot


def ensure_bucket_exists(bucket_name: str) -> storage.Bucket:
    """Ensure the GCS bucket exists, create if it doesn't."""
    client = storage.Client()

    try:
        bucket = client.get_bucket(bucket_name)
        console.print(f"[green]✓[/green] Bucket '{bucket_name}' exists")
        return bucket
    except Exception:
        console.print(f"[cyan]Bucket '{bucket_name}' doesn't exist, creating...[/cyan]")
        bucket = client.create_bucket(bucket_name)

        # Set lifecycle policy to delete objects older than 90 days
        lifecycle_rule = {"action": {"type": "Delete"}, "condition": {"age": 90}}
        bucket.lifecycle_rules = [lifecycle_rule]
        bucket.patch()

        console.print(
            f"[green]✓[/green] Created bucket '{bucket_name}' with 90-day lifecycle policy"
        )
        return bucket


def upload_to_gcs(snapshot: dict[str, Any], bucket_name: str) -> None:
    """Upload snapshot to GCS bucket."""
    console.print(f"[cyan]Uploading snapshot to gs://{bucket_name}/...[/cyan]")

    # Ensure bucket exists
    bucket = ensure_bucket_exists(bucket_name)

    # Convert snapshot to JSON
    snapshot_json = json.dumps(snapshot, indent=2)

    # Upload with timestamp filename
    timestamp = snapshot["timestamp"].replace(":", "-").replace(".", "-")
    timestamp_filename = f"snapshots/{timestamp}.json"

    blob = bucket.blob(timestamp_filename)
    blob.upload_from_string(snapshot_json, content_type="application/json")
    console.print(f"[green]✓[/green] Uploaded to {timestamp_filename}")

    # Update latest.json
    latest_blob = bucket.blob("latest.json")
    latest_blob.upload_from_string(snapshot_json, content_type="application/json")
    console.print("[green]✓[/green] Updated latest.json")

    console.print("\n[green]✓ Successfully uploaded snapshot to GCS[/green]")


def save_local_copy(
    snapshot: dict[str, Any], output_path: str = "coder_snapshot.json"
) -> None:
    """Save a local copy of the snapshot for debugging."""
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    console.print(f"[green]✓[/green] Saved local copy to {output_path}")


def main() -> None:
    """Execute the main workflow."""
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]Coder Analytics Collection Script[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print()

    # Configuration
    bucket_name = "coder-analytics-snapshots"
    save_local = "--local" in sys.argv

    # Get Coder API configuration
    api_url, session_token = get_coder_api_config()
    console.print(f"[green]✓[/green] Using Coder API: {api_url}")

    # Fetch participant data from multiple sources and merge
    # Historical data preserves team assignments for deleted participants
    historical_data = get_historical_participant_data(bucket_name)
    current_data = get_participant_mappings()
    participant_mappings = merge_participant_data(historical_data, current_data)

    # Fetch historical accumulated usage data
    historical_accumulated = get_historical_accumulated_usage(bucket_name)
    historical_workspace_snapshots = get_historical_workspace_snapshots(bucket_name)

    # Fetch data (with filtering and build enrichment)
    workspaces = fetch_workspaces(participant_mappings, api_url, session_token)
    templates = fetch_templates()

    # Calculate accumulated usage with historical preservation
    accumulated_usage, workspace_usage_snapshot = calculate_accumulated_usage(
        workspaces,
        historical_accumulated,
        historical_workspace_snapshots,
        participant_mappings,
    )

    # Create snapshot with accumulated usage data
    snapshot = create_snapshot(
        workspaces, templates, accumulated_usage, workspace_usage_snapshot
    )

    # Save local copy if requested
    if save_local:
        save_local_copy(snapshot)

    # Upload to GCS
    upload_to_gcs(snapshot, bucket_name)

    console.print()
    console.print("[bold green]" + "=" * 60 + "[/bold green]")
    console.print("[bold green]✓ Collection complete![/bold green]")
    console.print("[bold green]" + "=" * 60 + "[/bold green]")

    # Print summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  [cyan]Workspaces:[/cyan] {len(workspaces)}")
    console.print(f"  [cyan]Templates:[/cyan] {len(templates)}")
    console.print(f"  [cyan]Accumulated Usage Records:[/cyan] {len(accumulated_usage)}")
    console.print(f"  [cyan]Timestamp:[/cyan] {snapshot['timestamp']}")
    console.print(f"  [cyan]Bucket:[/cyan] gs://{bucket_name}/")


if __name__ == "__main__":
    main()
