#!/usr/bin/env python3
"""
Aggregate Coder analytics from all historical GCS snapshots.

This script:
1. Reads every snapshot from gs://coder-analytics-snapshots/snapshots/
2. Builds a deduplicated workspace registry (all workspaces ever seen)
3. Computes team, platform, template, and daily engagement metrics
4. Writes a single analytics_aggregate.json to GCS

The dashboard reads analytics_aggregate.json directly — no metric
computation is done in TypeScript.

Run after collect.py (or standalone) to refresh the aggregate.
"""

import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud.storage import Bucket
from google.cloud.storage import Client as StorageClient
from rich.console import Console


console = Console()

BUCKET_NAME = "coder-analytics-snapshots"
AGGREGATE_FILE = "analytics_aggregate.json"
EXCLUDED_TEAMS = {"facilitators", "Unassigned"}
ACTIVE_DAYS = 7
INACTIVE_DAYS = 30


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------


def get_bucket() -> Bucket:
    """Return the GCS bucket used for analytics snapshots."""
    client = StorageClient()
    return client.bucket(BUCKET_NAME)


def list_snapshot_names(bucket: Bucket) -> list[str]:
    """Return all snapshot blob names sorted chronologically."""
    blobs = bucket.list_blobs(prefix="snapshots/")
    return sorted(b.name for b in blobs if b.name.endswith(".json"))


def download_snapshot(bucket: Bucket, blob_name: str) -> dict[str, Any] | None:
    """Download and parse a single snapshot blob; return None on failure."""
    try:
        content = bucket.blob(blob_name).download_as_text()
        return json.loads(content)
    except Exception as e:
        console.print(f"  [yellow]⚠ Skipping {blob_name}: {e}[/yellow]")
        return None


def download_all_snapshots(
    bucket: Bucket, blob_names: list[str], max_workers: int = 20
) -> list[dict[str, Any]]:
    """Download all snapshots in parallel, return in chronological order."""
    console.print(
        f"[cyan]Downloading {len(blob_names)} snapshots ({max_workers} parallel)...[/cyan]"
    )
    results: dict[str, dict[str, Any] | None] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(download_snapshot, bucket, name): name for name in blob_names
        }
        for done, future in enumerate(as_completed(futures), start=1):
            name = futures[future]
            results[name] = future.result()
            if done % 50 == 0:
                console.print(f"  [dim]{done}/{len(blob_names)} downloaded...[/dim]")

    # Return in chronological order (sorted by blob name = sorted by timestamp)
    ordered: list[dict[str, Any]] = []
    for name in blob_names:
        snapshot = results.get(name)
        if snapshot is not None:
            ordered.append(snapshot)
    return ordered


# ---------------------------------------------------------------------------
# Workspace registry
# ---------------------------------------------------------------------------


def build_workspace_registry(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build a deduplicated registry of every workspace ever seen.

    Iterates snapshots chronologically so later snapshots overwrite earlier
    ones for the same workspace_id, preserving the most up-to-date values.
    """
    registry: dict[str, dict[str, Any]] = {}

    for snapshot in snapshots:
        ts = snapshot.get("timestamp", "")
        for ws in snapshot.get("workspaces", []):
            ws_id = ws.get("id")
            if not ws_id:
                continue

            last_used = ws.get("last_used_at") or ws.get("created_at", "")

            existing = registry.get(ws_id)
            if existing and existing["snapshot_timestamp"] >= ts:
                # We already have an equal or newer snapshot for this workspace
                continue

            # Prefer team_name from snapshot; fall back to existing if present
            team_name = ws.get("team_name") or (existing or {}).get(
                "team_name", "Unassigned"
            )

            registry[ws_id] = {
                "id": ws_id,
                "owner_name": ws.get("owner_name", ""),
                "team_name": team_name,
                "template_name": ws.get("template_name", ""),
                "template_display_name": ws.get("template_display_name", ""),
                "template_id": ws.get("template_id", ""),
                "created_at": ws.get("created_at", ""),
                "last_used_at": last_used,
                "total_usage_hours": ws.get("total_usage_hours", 0.0) or 0.0,
                "active_hours": ws.get("active_hours", 0.0) or 0.0,
                "owner_first_name": ws.get("owner_first_name"),
                "owner_last_name": ws.get("owner_last_name"),
                "snapshot_timestamp": ts,
            }

    return registry


def enrich_registry_from_accumulated(
    registry: dict[str, dict[str, Any]],
    accumulated_usage: dict[str, Any],
) -> None:
    """Ensure every workspace_id in accumulated_usage appears in the registry.

    Adds minimal stub entries for workspaces deleted before snapshot collection
    began, so that team counts remain correct.
    """
    for record in accumulated_usage.values():
        owner = record.get("owner_name", "")
        team = record.get("team_name", "Unassigned")
        template_name = record.get("template_name", "")
        for ws_id in record.get("workspace_ids", []):
            if ws_id not in registry:
                registry[ws_id] = {
                    "id": ws_id,
                    "owner_name": owner,
                    "team_name": team,
                    "template_name": template_name,
                    "template_display_name": template_name,
                    "template_id": "",
                    "created_at": record.get("first_seen", ""),
                    # Deleted workspaces have no last_used_at; use last_updated
                    # from accumulated_usage as a conservative proxy
                    "last_used_at": record.get(
                        "last_updated", record.get("first_seen", "")
                    ),
                    "total_usage_hours": 0.0,
                    "active_hours": 0.0,
                    "owner_first_name": None,
                    "owner_last_name": None,
                    "snapshot_timestamp": "",
                }


# ---------------------------------------------------------------------------
# Activity helpers
# ---------------------------------------------------------------------------


def days_since(timestamp: str, now: datetime) -> int:
    """Return the number of days between a UTC timestamp and now (0 if future)."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return max(0, (now - dt).days)
    except Exception:
        return 9999


def activity_status(last_used_at: str, now: datetime) -> str:
    """Classify a workspace as active, inactive, or stale based on last use."""
    d = days_since(last_used_at, now)
    if d <= ACTIVE_DAYS:
        return "active"
    if d <= INACTIVE_DAYS:
        return "inactive"
    return "stale"


def _build_members(
    workspaces: list[dict[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    """Build a sorted member list from a team's workspaces."""
    member_map: dict[str, dict] = {}
    for ws in workspaces:
        owner = ws["owner_name"]
        existing = member_map.get(owner)
        if not existing or ws["last_used_at"] > existing["last_used_at"]:
            member_map[owner] = ws

    members = []
    for owner, ws in member_map.items():
        fn, ln = ws.get("owner_first_name"), ws.get("owner_last_name")
        name = f"{fn} {ln}" if fn and ln else owner
        members.append(
            {
                "github_handle": owner,
                "name": name,
                "workspace_count": sum(
                    1 for w in workspaces if w["owner_name"] == owner
                ),
                "last_active": ws["last_used_at"],
                "activity_status": activity_status(ws["last_used_at"], now),
            }
        )
    members.sort(key=lambda m: str(m["last_active"]), reverse=True)
    return members


# ---------------------------------------------------------------------------
# Metric calculators
# ---------------------------------------------------------------------------


def compute_team_metrics(
    registry: dict[str, dict[str, Any]],
    accumulated_usage: dict[str, Any],
    accumulated_daily_engagement: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    """Compute per-team metrics for all teams ever seen across all snapshots."""
    # Group workspace registry entries by team
    team_ws: dict[str, list[dict]] = defaultdict(list)
    for ws in registry.values():
        team = ws["team_name"]
        if team not in EXCLUDED_TEAMS:
            team_ws[team].append(ws)

    # Ensure teams that only appear in accumulated_usage are included
    for record in accumulated_usage.values():
        team = record.get("team_name", "Unassigned")
        if team not in EXCLUDED_TEAMS and team not in team_ws:
            team_ws[team] = []

    # Precompute per-team data from accumulated_usage
    acc_by_team: dict[str, dict] = defaultdict(
        lambda: {
            "total_active_hours": 0.0,
            "total_workspace_hours": 0.0,
            "workspace_ids": set(),
        }
    )
    for record in accumulated_usage.values():
        team = record.get("team_name", "Unassigned")
        if team in EXCLUDED_TEAMS:
            continue
        acc_by_team[team]["total_active_hours"] += record.get("total_active_hours", 0.0)
        acc_by_team[team]["total_workspace_hours"] += record.get(
            "total_workspace_hours", 0.0
        )
        acc_by_team[team]["workspace_ids"].update(record.get("workspace_ids", []))

    # Compute active dates from daily engagement (last 7 days)
    cutoff = (now - timedelta(days=ACTIVE_DAYS)).strftime("%Y-%m-%d")

    result = []
    for team_name, workspaces in team_ws.items():
        # All workspace IDs ever for this team
        all_ws_ids = {ws["id"] for ws in workspaces} | acc_by_team[team_name][
            "workspace_ids"
        ]

        # Member map: owner_name -> most recently active workspace
        # Active users (last 7 days) from workspace registry
        members = _build_members(workspaces, now)
        active_users = {
            m["github_handle"] for m in members if m["activity_status"] == "active"
        }

        # Active days: unique dates in last 7 days where a team member appears
        team_owners_lower = {ws["owner_name"].lower() for ws in workspaces}
        active_dates: set[str] = set()
        for date_str, data in accumulated_daily_engagement.items():
            if date_str >= cutoff and team_owners_lower & set(
                data.get("unique_users", [])
            ):
                active_dates.add(date_str)

        # Hours — prefer accumulated_usage, fall back to registry sum
        total_active_hours = acc_by_team[team_name]["total_active_hours"]
        total_workspace_hours = acc_by_team[team_name]["total_workspace_hours"]
        if total_workspace_hours == 0:
            total_workspace_hours = sum(
                ws.get("total_usage_hours", 0.0) for ws in workspaces
            )

        avg_ws_hours = total_workspace_hours / len(all_ws_ids) if all_ws_ids else 0.0

        # Template distribution (current workspaces only)
        template_dist: dict[str, int] = defaultdict(int)
        for ws in workspaces:
            template_dist[ws["template_display_name"]] += 1

        result.append(
            {
                "team_name": team_name,
                "total_workspaces": len(all_ws_ids),
                "unique_active_users": len(active_users),
                "total_workspace_hours": round(total_workspace_hours),
                "total_active_hours": round(total_active_hours),
                "avg_workspace_hours": round(avg_ws_hours * 10) / 10,
                "active_days": len(active_dates),
                "template_distribution": dict(template_dist),
                "members": members,
            }
        )

    result.sort(key=lambda t: t["team_name"])
    return result


def compute_platform_metrics(
    registry: dict[str, dict[str, Any]],
    accumulated_usage: dict[str, Any],
    team_metrics: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Compute platform-wide aggregate metrics."""
    # All workspace IDs ever (registry + accumulated_usage)
    all_ws_ids: set[str] = set(registry.keys())
    for record in accumulated_usage.values():
        all_ws_ids.update(record.get("workspace_ids", []))

    non_excluded = [
        ws for ws in registry.values() if ws["team_name"] not in EXCLUDED_TEAMS
    ]
    active_ws = sum(
        1 for ws in non_excluded if activity_status(ws["last_used_at"], now) == "active"
    )
    inactive_ws = sum(
        1
        for ws in non_excluded
        if activity_status(ws["last_used_at"], now) == "inactive"
    )
    stale_ws = sum(
        1 for ws in non_excluded if activity_status(ws["last_used_at"], now) == "stale"
    )

    all_users = {ws["owner_name"] for ws in non_excluded}
    templates_seen: set[str] = {
        ws["template_name"] for ws in non_excluded if ws["template_name"]
    }

    template_counts: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "display_name": ""}
    )
    for ws in non_excluded:
        t = ws["template_name"]
        if t:
            template_counts[t]["count"] += 1
            template_counts[t]["display_name"] = ws["template_display_name"]

    most_popular = (
        max(template_counts.items(), key=lambda x: x[1]["count"])
        if template_counts
        else None
    )

    days_since_active_vals = [
        days_since(ws["last_used_at"], now) for ws in non_excluded
    ]
    avg_days = (
        round(sum(days_since_active_vals) / len(days_since_active_vals), 1)
        if days_since_active_vals
        else 0.0
    )

    return {
        "total_workspaces": len(all_ws_ids),
        "total_users": len(all_users),
        "total_teams": len(team_metrics),
        "active_workspaces": active_ws,
        "inactive_workspaces": inactive_ws,
        "stale_workspaces": stale_ws,
        "total_templates": len(templates_seen),
        "most_popular_template": {
            "name": most_popular[0],
            "display_name": most_popular[1]["display_name"],
            "count": most_popular[1]["count"],
        }
        if most_popular
        else None,
        "healthy_rate": 0.0,
        "avg_days_since_active": avg_days,
    }


def compute_template_metrics(
    registry: dict[str, dict[str, Any]],
    templates: list[dict[str, Any]],
    accumulated_usage: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    """Compute per-template metrics combining registry and accumulated usage."""
    # Group registry workspaces by template_id
    by_template_id: dict[str, list[dict]] = defaultdict(list)
    for ws in registry.values():
        if ws["template_id"] and ws["team_name"] not in EXCLUDED_TEAMS:
            by_template_id[ws["template_id"]].append(ws)

    result = []
    for template in templates:
        t_id = template["id"]
        t_name = template["name"]
        workspaces = by_template_id.get(t_id, [])

        active_ws = [
            ws
            for ws in workspaces
            if activity_status(ws["last_used_at"], now) == "active"
        ]
        active_users = {ws["owner_name"] for ws in active_ws}

        # All-time workspace IDs for this template (excluding facilitators/Unassigned)
        all_ws_ids: set[str] = {ws["id"] for ws in workspaces}
        for record in accumulated_usage.values():
            if (
                record.get("template_name") == t_name
                and record.get("team_name", "Unassigned") not in EXCLUDED_TEAMS
            ):
                all_ws_ids.update(record.get("workspace_ids", []))

        total_active_hours = sum(
            r.get("total_active_hours", 0.0)
            for r in accumulated_usage.values()
            if r.get("template_name") == t_name
            and r.get("team_name", "Unassigned") not in EXCLUDED_TEAMS
        )
        total_workspace_hours = sum(
            r.get("total_workspace_hours", 0.0)
            for r in accumulated_usage.values()
            if r.get("template_name") == t_name
            and r.get("team_name", "Unassigned") not in EXCLUDED_TEAMS
        )
        if total_workspace_hours == 0:
            total_workspace_hours = sum(
                ws.get("total_usage_hours", 0.0) for ws in workspaces
            )

        avg_ws_hours = total_workspace_hours / len(all_ws_ids) if all_ws_ids else 0.0

        team_dist: dict[str, int] = defaultdict(int)
        for ws in workspaces:
            team_dist[ws["team_name"]] += 1

        result.append(
            {
                "template_id": t_id,
                "template_name": t_name,
                "template_display_name": template.get("display_name", t_name),
                "total_workspaces": len(all_ws_ids),
                "active_workspaces": len(active_ws),
                "unique_active_users": len(active_users),
                "total_workspace_hours": round(total_workspace_hours),
                "total_active_hours": round(total_active_hours),
                "avg_workspace_hours": round(avg_ws_hours * 10) / 10,
                "team_distribution": dict(team_dist),
            }
        )

    return result


def compute_daily_engagement(
    accumulated_daily_engagement: dict[str, Any],
    days: int = 90,
) -> list[dict[str, Any]]:
    """Return daily engagement entries for the last N days, sorted by date."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    result = [
        {
            "date": date_str,
            "unique_users": len(data.get("unique_users", [])),
            "active_workspaces": len(data.get("active_workspaces", [])),
        }
        for date_str, data in accumulated_daily_engagement.items()
        if date_str >= cutoff
    ]
    result.sort(key=lambda x: str(x["date"]))
    return result


def compute_workspace_metrics(
    registry: dict[str, dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Compute workspace-level metrics for the detail table."""
    result = []
    for ws in registry.values():
        if ws["team_name"] in EXCLUDED_TEAMS:
            continue
        last_used = ws["last_used_at"]
        created = ws["created_at"]
        dsa = days_since(last_used, now)
        dsc = days_since(created, now)

        name = ws["owner_name"]
        fn, ln = ws.get("owner_first_name"), ws.get("owner_last_name")
        if fn and ln:
            name = f"{fn} {ln}"

        result.append(
            {
                "workspace_id": ws["id"],
                "workspace_name": ws.get("name") or f"{ws['owner_name']}/workspace",
                "owner_github_handle": ws["owner_name"],
                "owner_name": name,
                "team_name": ws["team_name"],
                "template_id": ws["template_id"],
                "template_name": ws["template_name"],
                "template_display_name": ws["template_display_name"],
                "current_status": "unknown",
                "health_status": "unknown",
                "created_at": created,
                "last_active": last_used,
                "last_build_at": created,
                "days_since_created": dsc,
                "days_since_active": dsa,
                "workspace_hours": ws.get("total_usage_hours", 0.0),
                "active_hours": ws.get("active_hours", 0.0),
                "total_builds": 0,
                "last_build_status": "unknown",
                "activity_status": activity_status(last_used, now),
                "recent_active_dates": [],
            }
        )

    result.sort(key=lambda w: w["last_active"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _print_summary(
    team_metrics: list[dict[str, Any]],
    platform_metrics: dict[str, Any],
    daily_engagement: list[dict[str, Any]],
) -> None:
    """Print the final aggregation summary to the console."""
    console.print("[bold green]" + "=" * 60 + "[/bold green]")
    console.print("[bold green]✓ Aggregation complete![/bold green]")
    console.print("[bold green]" + "=" * 60 + "[/bold green]")
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  [cyan]Teams:[/cyan] {len(team_metrics)}")
    console.print(
        f"  [cyan]Total workspaces (all-time):[/cyan]"
        f" {platform_metrics['total_workspaces']}"
    )
    console.print(
        f"  [cyan]Active workspaces (last 7d):[/cyan]"
        f" {platform_metrics['active_workspaces']}"
    )
    console.print(f"  [cyan]Total users:[/cyan] {platform_metrics['total_users']}")
    console.print(f"  [cyan]Engagement days tracked:[/cyan] {len(daily_engagement)}")


def main() -> None:
    """Aggregate all GCS snapshots and write analytics_aggregate.json."""
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]Coder Analytics Aggregation Script[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    bucket = get_bucket()

    # 1. List and download all snapshots
    snapshot_names = list_snapshot_names(bucket)
    console.print(f"[green]✓[/green] Found {len(snapshot_names)} snapshots")

    snapshots = download_all_snapshots(bucket, snapshot_names)
    console.print(f"[green]✓[/green] Downloaded {len(snapshots)} snapshots\n")

    if not snapshots:
        console.print("[red]✗ No snapshots downloaded. Exiting.[/red]")
        sys.exit(1)

    # 2. Use the latest snapshot for accumulated data and templates
    latest = snapshots[-1]
    accumulated_usage: dict[str, Any] = latest.get("accumulated_usage") or {}
    accumulated_daily_engagement: dict[str, Any] = (
        latest.get("accumulated_daily_engagement") or {}
    )
    templates: list[dict[str, Any]] = latest.get("templates") or []

    console.print(f"[green]✓[/green] Latest snapshot: {latest.get('timestamp')}")
    console.print(f"  [dim]Accumulated usage records:[/dim] {len(accumulated_usage)}")
    console.print(
        f"  [dim]Daily engagement records:[/dim] {len(accumulated_daily_engagement)}"
    )
    console.print(f"  [dim]Templates:[/dim] {len(templates)}\n")

    # 3. Build workspace registry from all snapshots
    console.print("[cyan]Building workspace registry from all snapshots...[/cyan]")
    registry = build_workspace_registry(snapshots)
    console.print(
        f"[green]✓[/green] Registry: {len(registry)} unique workspaces from snapshots"
    )

    # Fill in stubs for workspaces in accumulated_usage not seen in any snapshot
    enrich_registry_from_accumulated(registry, accumulated_usage)
    console.print(
        f"[green]✓[/green] Registry after enrichment: {len(registry)} workspaces\n"
    )

    # 4. Compute all metrics
    now = datetime.now(timezone.utc)

    console.print("[cyan]Computing team metrics...[/cyan]")
    team_metrics = compute_team_metrics(
        registry, accumulated_usage, accumulated_daily_engagement, now
    )
    console.print(f"[green]✓[/green] {len(team_metrics)} teams")

    console.print("[cyan]Computing platform metrics...[/cyan]")
    platform_metrics = compute_platform_metrics(
        registry, accumulated_usage, team_metrics, now
    )
    console.print(
        f"[green]✓[/green] {platform_metrics['total_workspaces']} total workspaces, "
        f"{platform_metrics['total_teams']} teams, "
        f"{platform_metrics['total_users']} users"
    )

    console.print("[cyan]Computing template metrics...[/cyan]")
    template_metrics = compute_template_metrics(
        registry, templates, accumulated_usage, now
    )
    console.print(f"[green]✓[/green] {len(template_metrics)} templates")

    console.print("[cyan]Computing daily engagement...[/cyan]")
    daily_engagement = compute_daily_engagement(accumulated_daily_engagement)
    console.print(f"[green]✓[/green] {len(daily_engagement)} days of engagement data")

    console.print("[cyan]Computing workspace metrics...[/cyan]")
    workspace_metrics = compute_workspace_metrics(registry, now)
    console.print(f"[green]✓[/green] {len(workspace_metrics)} workspace metrics\n")

    # 5. Build aggregate and upload
    aggregate = {
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "platform_metrics": platform_metrics,
        "team_metrics": team_metrics,
        "workspace_metrics": workspace_metrics,
        "template_metrics": template_metrics,
        "daily_engagement": daily_engagement,
    }

    console.print(f"[cyan]Uploading {AGGREGATE_FILE} to gs://{BUCKET_NAME}/...[/cyan]")
    blob = bucket.blob(AGGREGATE_FILE)
    blob.upload_from_string(
        json.dumps(aggregate, indent=2), content_type="application/json"
    )
    console.print(f"[green]✓[/green] Uploaded gs://{BUCKET_NAME}/{AGGREGATE_FILE}\n")

    _print_summary(team_metrics, platform_metrics, daily_engagement)


if __name__ == "__main__":
    main()
