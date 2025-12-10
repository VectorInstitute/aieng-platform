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
from datetime import UTC, datetime
from typing import Any

import requests


try:
    from google.cloud import firestore, storage
except ImportError:
    print("Error: google-cloud-storage or google-cloud-firestore not installed.")
    print("Run: pip install google-cloud-storage google-cloud-firestore")
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
        print(f"Error running command {' '.join(cmd)}: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from command {' '.join(cmd)}: {e}")
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
        print("Error: CODER_TOKEN or CODER_SESSION_TOKEN environment variable not set")
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
        print(f"Warning: Failed to fetch builds for workspace {workspace_id}: {e}")
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
        print(f"Warning: Error calculating build usage hours: {e}")
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
        print(f"Warning: Failed to fetch user activity insights: {e}")
        try:
            error_details = response.json() if response else {}
            print(f"Error details: {error_details}")
        except Exception:
            pass
        return {}


def get_team_mappings() -> dict[str, str]:
    """Get team mappings from Firestore.

    Returns
    -------
    dict[str, str]
        Mapping of github_handle (lowercase) -> team_name
    """
    print("Fetching team mappings from Firestore...")

    project_id = "coderd"
    database_id = "onboarding"

    db = firestore.Client(project=project_id, database=database_id)

    mappings = {}
    participants = db.collection("participants").stream()

    for doc in participants:
        data = doc.to_dict()
        if data:
            github_handle = doc.id.lower()
            team_name = data.get("team_name", "Unassigned")
            mappings[github_handle] = team_name

    print(f"✓ Loaded {len(mappings)} participant team mappings")
    return mappings


def fetch_workspaces(
    team_mappings: dict[str, str], api_url: str, session_token: str
) -> list[dict[str, Any]]:
    """Fetch workspaces using Coder CLI and enrich with build data.

    Parameters
    ----------
    team_mappings : dict[str, str]
        Mapping of github_handle -> team_name
    api_url : str
        Coder API base URL
    session_token : str
        Coder session token for API authentication

    Returns
    -------
    list[dict[str, Any]]
        List of workspace objects with builds, usage hours, and active hours
    """
    print("Fetching workspaces from Coder...")
    workspaces = run_command(["coder", "list", "-a", "-o", "json"])

    # Teams to exclude from analytics
    excluded_teams = ["facilitators", "Unassigned"]

    original_count = len(workspaces)

    # Filter out workspaces owned by users in excluded teams
    filtered_workspaces = []
    for ws in workspaces:
        owner_name = ws.get("owner_name", "").lower()
        team_name = team_mappings.get(owner_name, "Unassigned")

        if team_name not in excluded_teams:
            filtered_workspaces.append(ws)

    filtered_count = original_count - len(filtered_workspaces)
    if filtered_count > 0:
        print(
            f"✓ Filtered out {filtered_count} workspaces from excluded teams: {', '.join(excluded_teams)}"
        )

    print(f"✓ Fetched {len(filtered_workspaces)} workspaces")

    # Fetch user activity insights (active hours)
    # Use a wide time range to capture all activity
    # Find earliest workspace creation date
    print("Fetching user activity insights...")
    earliest_created = min(
        (
            datetime.fromisoformat(ws.get("created_at", "").replace("Z", "+00:00"))
            for ws in filtered_workspaces
            if ws.get("created_at")
        ),
        default=datetime.now(UTC),
    )
    # Normalize to midnight (00:00:00) as required by the API
    start_time = earliest_created.replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Normalize end time to the start of the current hour (required by API)
    now = datetime.now(UTC)
    end_time = now.replace(minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    activity_map = fetch_user_activity_insights(
        api_url, session_token, start_time, end_time
    )
    print(f"✓ Fetched activity data for {len(activity_map)} users")

    # Enrich workspaces with full build history and usage hours
    print("Enriching workspaces with build history and active hours...")
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

        # Progress indicator
        if i % 10 == 0:
            print(f"  Processed {i}/{len(filtered_workspaces)} workspaces...")

    print(
        f"✓ Enriched {len(filtered_workspaces)} workspaces with build history and active hours"
    )
    return filtered_workspaces


def fetch_templates() -> list[dict[str, Any]]:
    """Fetch all templates using Coder CLI."""
    print("Fetching templates from Coder...")
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

    print(f"✓ Fetched {len(templates)} templates")
    return templates


def create_snapshot(
    workspaces: list[dict[str, Any]], templates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a snapshot object with timestamp."""
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    snapshot = {
        "timestamp": timestamp,
        "workspaces": workspaces,
        "templates": templates,
    }

    print(f"✓ Created snapshot at {timestamp}")
    return snapshot


def ensure_bucket_exists(bucket_name: str) -> storage.Bucket:
    """Ensure the GCS bucket exists, create if it doesn't."""
    client = storage.Client()

    try:
        bucket = client.get_bucket(bucket_name)
        print(f"✓ Bucket '{bucket_name}' exists")
        return bucket
    except Exception:
        print(f"Bucket '{bucket_name}' doesn't exist, creating...")
        bucket = client.create_bucket(bucket_name)

        # Set lifecycle policy to delete objects older than 90 days
        lifecycle_rule = {"action": {"type": "Delete"}, "condition": {"age": 90}}
        bucket.lifecycle_rules = [lifecycle_rule]
        bucket.patch()

        print(f"✓ Created bucket '{bucket_name}' with 90-day lifecycle policy")
        return bucket


def upload_to_gcs(snapshot: dict[str, Any], bucket_name: str) -> None:
    """Upload snapshot to GCS bucket."""
    print(f"Uploading snapshot to gs://{bucket_name}/...")

    # Ensure bucket exists
    bucket = ensure_bucket_exists(bucket_name)

    # Convert snapshot to JSON
    snapshot_json = json.dumps(snapshot, indent=2)

    # Upload with timestamp filename
    timestamp = snapshot["timestamp"].replace(":", "-").replace(".", "-")
    timestamp_filename = f"snapshots/{timestamp}.json"

    blob = bucket.blob(timestamp_filename)
    blob.upload_from_string(snapshot_json, content_type="application/json")
    print(f"✓ Uploaded to {timestamp_filename}")

    # Update latest.json
    latest_blob = bucket.blob("latest.json")
    latest_blob.upload_from_string(snapshot_json, content_type="application/json")
    print("✓ Updated latest.json")

    print("\n✓ Successfully uploaded snapshot to GCS")


def save_local_copy(
    snapshot: dict[str, Any], output_path: str = "coder_snapshot.json"
) -> None:
    """Save a local copy of the snapshot for debugging."""
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"✓ Saved local copy to {output_path}")


def main() -> None:
    """Execute the main workflow."""
    print("=" * 60)
    print("Coder Analytics Collection Script")
    print("=" * 60)
    print()

    # Configuration
    bucket_name = "coder-analytics-snapshots"
    save_local = "--local" in sys.argv

    # Get Coder API configuration
    api_url, session_token = get_coder_api_config()
    print(f"✓ Using Coder API: {api_url}")

    # Fetch team mappings first
    team_mappings = get_team_mappings()

    # Fetch data (with filtering and build enrichment)
    workspaces = fetch_workspaces(team_mappings, api_url, session_token)
    templates = fetch_templates()

    # Create snapshot
    snapshot = create_snapshot(workspaces, templates)

    # Save local copy if requested
    if save_local:
        save_local_copy(snapshot)

    # Upload to GCS
    upload_to_gcs(snapshot, bucket_name)

    print()
    print("=" * 60)
    print("✓ Collection complete!")
    print("=" * 60)

    # Print summary
    print("\nSummary:")
    print(f"  Workspaces: {len(workspaces)}")
    print(f"  Templates: {len(templates)}")
    print(f"  Timestamp: {snapshot['timestamp']}")
    print(f"  Bucket: gs://{bucket_name}/")


if __name__ == "__main__":
    main()
