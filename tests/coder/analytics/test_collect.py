"""Unit tests for Coder analytics collection script."""

from coder.analytics.collect import (
    calculate_accumulated_usage,
    calculate_build_usage_hours,
    calculate_workspace_total_usage,
    merge_participant_data,
)


class TestCalculateBuildUsageHours:
    """Tests for calculate_build_usage_hours function."""

    def test_returns_zero_for_build_without_resources(self) -> None:
        """Test that a build with no resources returns 0 hours."""
        build = {"resources": []}
        assert calculate_build_usage_hours(build) == 0.0

    def test_returns_zero_for_build_without_agents(self) -> None:
        """Test that a build with resources but no agents returns 0 hours."""
        build = {"resources": [{"agents": []}]}
        assert calculate_build_usage_hours(build) == 0.0

    def test_returns_zero_for_agent_without_connection_times(self) -> None:
        """Test that an agent without connection times returns 0 hours."""
        build = {
            "resources": [
                {"agents": [{"first_connected_at": None, "last_connected_at": None}]}
            ]
        }
        assert calculate_build_usage_hours(build) == 0.0

    def test_calculates_hours_for_single_agent(self) -> None:
        """Test calculation for a single agent with connection times."""
        # 2 hour difference
        build = {
            "resources": [
                {
                    "agents": [
                        {
                            "first_connected_at": "2024-01-01T10:00:00Z",
                            "last_connected_at": "2024-01-01T12:00:00Z",
                        }
                    ]
                }
            ]
        }
        assert calculate_build_usage_hours(build) == 2.0

    def test_calculates_hours_across_multiple_agents(self) -> None:
        """Test calculation across multiple agents (earliest to latest)."""
        # Agent 1: 10:00 - 11:00
        # Agent 2: 09:00 - 13:00
        # Total: 09:00 - 13:00 = 4 hours
        build = {
            "resources": [
                {
                    "agents": [
                        {
                            "first_connected_at": "2024-01-01T10:00:00Z",
                            "last_connected_at": "2024-01-01T11:00:00Z",
                        },
                        {
                            "first_connected_at": "2024-01-01T09:00:00Z",
                            "last_connected_at": "2024-01-01T13:00:00Z",
                        },
                    ]
                }
            ]
        }
        assert calculate_build_usage_hours(build) == 4.0

    def test_handles_partial_connection_data(self) -> None:
        """Test handling when only some agents have connection data."""
        build = {
            "resources": [
                {
                    "agents": [
                        {
                            "first_connected_at": "2024-01-01T10:00:00Z",
                            "last_connected_at": "2024-01-01T12:00:00Z",
                        },
                        {"first_connected_at": None, "last_connected_at": None},
                    ]
                }
            ]
        }
        assert calculate_build_usage_hours(build) == 2.0


class TestCalculateWorkspaceTotalUsage:
    """Tests for calculate_workspace_total_usage function."""

    def test_returns_zero_for_empty_builds_list(self) -> None:
        """Test that an empty builds list returns 0 hours."""
        assert calculate_workspace_total_usage([]) == 0.0

    def test_sums_hours_across_multiple_builds(self) -> None:
        """Test summing hours across multiple builds."""
        builds = [
            {
                "resources": [
                    {
                        "agents": [
                            {
                                "first_connected_at": "2024-01-01T10:00:00Z",
                                "last_connected_at": "2024-01-01T12:00:00Z",
                            }
                        ]
                    }
                ]
            },
            {
                "resources": [
                    {
                        "agents": [
                            {
                                "first_connected_at": "2024-01-02T10:00:00Z",
                                "last_connected_at": "2024-01-02T13:00:00Z",
                            }
                        ]
                    }
                ]
            },
        ]
        # Build 1: 2 hours, Build 2: 3 hours, Total: 5 hours
        assert calculate_workspace_total_usage(builds) == 5.0


class TestMergeParticipantData:
    """Tests for merge_participant_data function."""

    def test_preserves_historical_data_for_deleted_participants(self) -> None:
        """Test that historical data is preserved even when participants are removed."""
        historical_data = {
            "user1": {
                "team_name": "team-a",
                "first_name": "John",
                "last_name": "Doe",
            },
            "user2": {
                "team_name": "team-b",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        }
        current_data = {
            "user1": {
                "team_name": "team-a",
                "first_name": "John",
                "last_name": "Doe",
            },
            # user2 removed
        }

        merged = merge_participant_data(historical_data, current_data)

        assert len(merged) == 2
        assert "user2" in merged
        assert merged["user2"]["team_name"] == "team-b"

    def test_current_data_overwrites_historical(self) -> None:
        """Test that current data takes precedence over historical."""
        historical_data = {
            "user1": {
                "team_name": "old-team",
                "first_name": "John",
                "last_name": "Doe",
            }
        }
        current_data = {
            "user1": {
                "team_name": "new-team",
                "first_name": "John",
                "last_name": "Doe",
            }
        }

        merged = merge_participant_data(historical_data, current_data)

        assert merged["user1"]["team_name"] == "new-team"

    def test_adds_new_participants_from_current(self) -> None:
        """Test that new participants in current data are added."""
        historical_data = {
            "user1": {
                "team_name": "team-a",
                "first_name": "John",
                "last_name": "Doe",
            }
        }
        current_data = {
            "user1": {
                "team_name": "team-a",
                "first_name": "John",
                "last_name": "Doe",
            },
            "user2": {
                "team_name": "team-b",
                "first_name": "Jane",
                "last_name": "Smith",
            },
        }

        merged = merge_participant_data(historical_data, current_data)

        assert len(merged) == 2
        assert "user2" in merged
        assert merged["user2"]["team_name"] == "team-b"


class TestCalculateAccumulatedUsage:
    """Tests for calculate_accumulated_usage function."""

    def test_creates_new_record_for_new_workspace(self) -> None:
        """Test creating a new accumulated usage record for a new workspace."""
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 10.0,
            }
        ]
        historical_accumulated = {}
        historical_workspace_snapshots = {}
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        assert key in accumulated
        assert accumulated[key]["total_active_hours"] == 10.0
        assert accumulated[key]["team_name"] == "team-a"
        assert "ws-1" in snapshots
        assert snapshots["ws-1"]["active_hours"] == 10.0

    def test_adds_delta_to_existing_record(self) -> None:
        """Test that only the delta is added to existing accumulated hours."""
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 15.0,  # Was 10, now 15
            }
        ]
        historical_accumulated = {
            "user1_python-dev": {
                "owner_name": "user1",
                "template_name": "python-dev",
                "team_name": "team-a",
                "total_active_hours": 10.0,
                "last_updated": "2024-01-01T00:00:00Z",
                "first_seen": "2024-01-01T00:00:00Z",
            }
        }
        historical_workspace_snapshots = {
            "ws-1": {
                "active_hours": 10.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            }
        }
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Should be 10 (previous) + 5 (delta) = 15
        assert accumulated[key]["total_active_hours"] == 15.0
        assert snapshots["ws-1"]["active_hours"] == 15.0

    def test_preserves_deleted_workspace_hours(self) -> None:
        """Test that hours from deleted workspaces are preserved."""
        # Current workspaces only has ws-2, ws-1 was deleted
        current_workspaces = [
            {
                "id": "ws-2",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 5.0,
            }
        ]
        # Historical has both workspaces' accumulated hours
        historical_accumulated = {
            "user1_python-dev": {
                "owner_name": "user1",
                "template_name": "python-dev",
                "team_name": "team-a",
                "total_active_hours": 20.0,  # From ws-1 (15h) and ws-2 (5h)
                "last_updated": "2024-01-01T00:00:00Z",
                "first_seen": "2024-01-01T00:00:00Z",
            }
        }
        historical_workspace_snapshots = {
            "ws-1": {
                "active_hours": 15.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            },
            "ws-2": {
                "active_hours": 5.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            },
        }
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Should still have 20h (ws-1's 15h is preserved, ws-2 has no new delta)
        assert accumulated[key]["total_active_hours"] == 20.0
        # Only ws-2 should be in snapshots now
        assert "ws-2" in snapshots
        assert "ws-1" not in snapshots

    def test_handles_multiple_templates_per_user(self) -> None:
        """Test accumulation across multiple templates for same user.

        Note: active_hours from Insights API is per-user, so both templates
        get the same value (max across all workspaces).
        """
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 10.0,  # Per-user value
            },
            {
                "id": "ws-2",
                "owner_name": "user1",
                "template_name": "nodejs-dev",
                "active_hours": 10.0,  # Same per-user value
            },
        ]
        historical_accumulated = {}
        historical_workspace_snapshots = {}
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        assert "user1_python-dev" in accumulated
        assert "user1_nodejs-dev" in accumulated
        # Both should have the same per-user active hours (10.0)
        assert accumulated["user1_python-dev"]["total_active_hours"] == 10.0
        assert accumulated["user1_nodejs-dev"]["total_active_hours"] == 10.0

    def test_prevents_negative_delta(self) -> None:
        """Test that negative deltas (hours going backwards) are treated as 0."""
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 5.0,  # Somehow decreased from 10
            }
        ]
        historical_accumulated = {
            "user1_python-dev": {
                "owner_name": "user1",
                "template_name": "python-dev",
                "team_name": "team-a",
                "total_active_hours": 10.0,
                "last_updated": "2024-01-01T00:00:00Z",
                "first_seen": "2024-01-01T00:00:00Z",
            }
        }
        historical_workspace_snapshots = {
            "ws-1": {
                "active_hours": 10.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            }
        }
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Should remain 10.0 (delta = max(0, 5 - 10) = 0)
        assert accumulated[key]["total_active_hours"] == 10.0

    def test_handles_team_name_changes(self) -> None:
        """Test that team name updates are reflected in accumulated usage."""
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 15.0,
            }
        ]
        historical_accumulated = {
            "user1_python-dev": {
                "owner_name": "user1",
                "template_name": "python-dev",
                "team_name": "old-team",
                "total_active_hours": 10.0,
                "last_updated": "2024-01-01T00:00:00Z",
                "first_seen": "2024-01-01T00:00:00Z",
            }
        }
        historical_workspace_snapshots = {
            "ws-1": {
                "active_hours": 10.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            }
        }
        participant_mappings = {"user1": {"team_name": "new-team"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Team name should be updated to new-team
        assert accumulated[key]["team_name"] == "new-team"
        # Hours should still accumulate correctly
        assert accumulated[key]["total_active_hours"] == 15.0

    def test_preserves_historical_team_for_deleted_participant(self) -> None:
        """Test team name preservation when participant deleted from Firestore."""
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 15.0,
            }
        ]
        historical_accumulated = {
            "user1_python-dev": {
                "owner_name": "user1",
                "template_name": "python-dev",
                "team_name": "team-a",
                "total_active_hours": 10.0,
                "last_updated": "2024-01-01T00:00:00Z",
                "first_seen": "2024-01-01T00:00:00Z",
            }
        }
        historical_workspace_snapshots = {
            "ws-1": {
                "active_hours": 10.0,
                "owner_name": "user1",
                "template_name": "python-dev",
            }
        }
        participant_mappings = {}  # User1 deleted from Firestore

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Team name should be preserved from historical data
        assert accumulated[key]["team_name"] == "team-a"
        # Hours should still accumulate
        assert accumulated[key]["total_active_hours"] == 15.0

    def test_handles_multiple_workspaces_same_user_template(self) -> None:
        """Test accumulation when user has multiple workspaces from same template.

        Note: active_hours from Insights API is per-user (same across all workspaces),
        so we take the max value, not sum.
        """
        current_workspaces = [
            {
                "id": "ws-1",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 10.0,  # Per-user value from Insights API
            },
            {
                "id": "ws-2",
                "owner_name": "user1",
                "template_name": "python-dev",
                "active_hours": 10.0,  # Same per-user value
            },
        ]
        historical_accumulated = {}
        historical_workspace_snapshots = {}
        participant_mappings = {"user1": {"team_name": "team-a"}}

        accumulated, snapshots = calculate_accumulated_usage(
            current_workspaces,
            historical_accumulated,
            historical_workspace_snapshots,
            participant_mappings,
        )

        key = "user1_python-dev"
        # Should be 10 (max of user's active_hours, not sum)
        assert accumulated[key]["total_active_hours"] == 10.0
        assert len(snapshots) == 2
