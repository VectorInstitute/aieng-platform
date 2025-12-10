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
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any


try:
    from google.cloud import storage
except ImportError:
    print(
        "Error: google-cloud-storage not installed. Run: pip install google-cloud-storage"
    )
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


def fetch_workspaces() -> list[dict[str, Any]]:
    """Fetch all workspaces using Coder CLI."""
    print("Fetching workspaces from Coder...")
    workspaces = run_command(["coder", "list", "-a", "-o", "json"])
    print(f"✓ Fetched {len(workspaces)} workspaces")
    return workspaces


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

    # Fetch data
    workspaces = fetch_workspaces()
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
