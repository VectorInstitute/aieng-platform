"""Unit tests for admin offboard_users module."""

import json
import subprocess
from contextlib import ExitStack
from typing import Any
from unittest.mock import Mock, patch

import pytest

from aieng_platform_onboard.admin.offboard_users import (
    delete_coder_user,
    display_stale_users_table,
    fetch_coder_users,
    fetch_github_org_members,
    fetch_user_workspaces,
    find_stale_coder_users,
    offboard_user,
    offboard_users,
    offboard_users_from_org,
    suspend_coder_user,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_coder_user(
    username: str,
    login_type: str = "github",
    status: str = "active",
    roles: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Return a minimal Coder user record."""
    return {
        "id": f"id-{username}",
        "username": username,
        "email": f"{username}@example.com",
        "login_type": login_type,
        "status": status,
        "created_at": "2025-11-01T00:00:00Z",
        "updated_at": "2025-11-01T00:00:00Z",
        "last_seen_at": "2025-11-01T00:00:00Z",
        "roles": roles or [],
        "organization_ids": [],
    }


def _make_workspace(owner: str, name: str) -> dict[str, Any]:
    """Return a minimal Coder workspace record."""
    return {
        "id": f"ws-{owner}-{name}",
        "name": name,
        "owner_name": owner,
        "template_name": "bootcamp",
        "created_at": "2025-11-01T00:00:00Z",
        "latest_build": {"status": "running"},
    }


# ---------------------------------------------------------------------------
# fetch_github_org_members
# ---------------------------------------------------------------------------


class TestFetchGithubOrgMembers:
    """Tests for fetch_github_org_members."""

    def test_returns_lowercase_login_set(self) -> None:
        """Logins are normalised to lowercase."""
        members = [{"login": "Alice"}, {"login": "BOB"}, {"login": "carol"}]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout=json.dumps(members), stderr=""
            )
            result = fetch_github_org_members("my-org")

        assert result == {"alice", "bob", "carol"}
        mock_run.assert_called_once_with(
            ["gh", "api", "/orgs/my-org/members", "--paginate"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_empty_org_returns_empty_set(self) -> None:
        """An org with no members returns an empty set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="[]", stderr="")
            result = fetch_github_org_members("empty-org")

        assert result == set()

    def test_gh_cli_not_found_raises(self) -> None:
        """Missing gh CLI raises RuntimeError."""
        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(RuntimeError, match="gh CLI not found"),
        ):
            fetch_github_org_members("my-org")

    def test_api_failure_raises(self) -> None:
        """Non-zero gh exit raises RuntimeError."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "gh", stderr="not found"),
            ),
            pytest.raises(RuntimeError, match="Failed to fetch GitHub org members"),
        ):
            fetch_github_org_members("my-org")

    def test_invalid_json_raises(self) -> None:
        """Malformed JSON response raises RuntimeError."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="not-json", stderr="")
            with pytest.raises(RuntimeError, match="Could not parse"):
                fetch_github_org_members("my-org")


# ---------------------------------------------------------------------------
# fetch_coder_users
# ---------------------------------------------------------------------------


class TestFetchCoderUsers:
    """Tests for fetch_coder_users."""

    def test_returns_list_of_users(self) -> None:
        """Parses Coder user JSON correctly."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout=json.dumps(users))
            result = fetch_coder_users()

        assert len(result) == 2
        assert result[0]["username"] == "alice"
        mock_run.assert_called_once_with(["users", "list", "--output", "json"])

    def test_empty_list(self) -> None:
        """Handles empty Coder user list."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout="[]")
            assert fetch_coder_users() == []

    def test_invalid_json_raises(self) -> None:
        """Invalid JSON raises RuntimeError."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(stdout="bad json")
            with pytest.raises(RuntimeError, match="Failed to parse Coder user data"):
                fetch_coder_users()

    def test_command_failure_propagates(self) -> None:
        """RuntimeError from run_coder_command propagates."""
        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.run_coder_command",
                side_effect=RuntimeError("CLI error"),
            ),
            pytest.raises(RuntimeError),
        ):
            fetch_coder_users()


# ---------------------------------------------------------------------------
# find_stale_coder_users
# ---------------------------------------------------------------------------


class TestFindStaleCoderUsers:
    """Tests for find_stale_coder_users."""

    def test_identifies_users_not_in_org(self) -> None:
        """Users whose username is absent from org_members are returned."""
        users = [
            _make_coder_user("alice"),
            _make_coder_user("bob"),
            _make_coder_user("carol"),
        ]
        org_members = {"alice", "carol"}

        result = find_stale_coder_users(users, org_members)

        assert len(result) == 1
        assert result[0]["username"] == "bob"

    def test_case_insensitive_comparison(self) -> None:
        """Username matching is case-insensitive."""
        users = [_make_coder_user("Alice"), _make_coder_user("BOB")]
        org_members = {"alice"}  # lowercase

        result = find_stale_coder_users(users, org_members)

        assert len(result) == 1
        assert result[0]["username"] == "BOB"

    def test_skips_non_github_login_type(self) -> None:
        """Users authenticated via password/OIDC are always skipped."""
        users = [
            _make_coder_user("alice", login_type="password"),
            _make_coder_user("bob", login_type="oidc"),
        ]
        # Neither is in the org
        result = find_stale_coder_users(users, set())

        assert result == []

    def test_skips_coder_owner_accounts(self) -> None:
        """Coder deployment owners are never offboarded."""
        owner = _make_coder_user("admin", roles=[{"name": "owner"}])
        regular = _make_coder_user("regular")
        org_members: set[str] = set()  # neither is in the org

        result = find_stale_coder_users([owner, regular], org_members)

        assert len(result) == 1
        assert result[0]["username"] == "regular"

    def test_all_users_in_org(self) -> None:
        """Returns empty list when every user is still in the org."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]
        org_members = {"alice", "bob"}

        assert find_stale_coder_users(users, org_members) == []

    def test_empty_user_list(self) -> None:
        """Empty Coder user list returns empty result."""
        assert find_stale_coder_users([], {"alice"}) == []

    def test_empty_org_flags_all_github_users(self) -> None:
        """An empty org means every GitHub-authenticated user is stale."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]

        result = find_stale_coder_users(users, set())

        assert len(result) == 2

    def test_mixed_login_types_and_roles(self) -> None:
        """Complex scenario with multiple login types and an owner."""
        users = [
            _make_coder_user("alice"),  # stale (not in org)
            _make_coder_user("bob"),  # in org – should be kept
            _make_coder_user("charlie", login_type="password"),  # skip: non-github
            _make_coder_user("dave", roles=[{"name": "owner"}]),  # skip: owner
        ]
        org_members = {"bob"}

        result = find_stale_coder_users(users, org_members)

        assert len(result) == 1
        assert result[0]["username"] == "alice"


# ---------------------------------------------------------------------------
# suspend_coder_user
# ---------------------------------------------------------------------------


class TestSuspendCoderUser:
    """Tests for suspend_coder_user."""

    def test_success(self) -> None:
        """Successful suspension returns True."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            assert suspend_coder_user("alice") is True
        mock_run.assert_called_once_with(["users", "suspend", "alice"], check=False)

    def test_dry_run_skips_command(self) -> None:
        """Dry run returns True without calling Coder."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            assert suspend_coder_user("alice", dry_run=True) is True
        mock_run.assert_not_called()

    def test_nonzero_exit_returns_false(self) -> None:
        """Non-zero Coder exit returns False."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="not found")
            assert suspend_coder_user("alice") is False

    def test_runtime_error_returns_false(self) -> None:
        """RuntimeError from CLI returns False."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command",
            side_effect=RuntimeError("CLI broken"),
        ):
            assert suspend_coder_user("alice") is False


# ---------------------------------------------------------------------------
# delete_coder_user
# ---------------------------------------------------------------------------


class TestDeleteCoderUser:
    """Tests for delete_coder_user."""

    def test_success(self) -> None:
        """Successful deletion returns True."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            assert delete_coder_user("bob") is True
        mock_run.assert_called_once_with(["users", "delete", "bob"], check=False)

    def test_dry_run_skips_command(self) -> None:
        """Dry run returns True without calling Coder."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            assert delete_coder_user("bob", dry_run=True) is True
        mock_run.assert_not_called()

    def test_nonzero_exit_returns_false(self) -> None:
        """Non-zero Coder exit returns False."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
            assert delete_coder_user("bob") is False

    def test_runtime_error_returns_false(self) -> None:
        """RuntimeError from CLI returns False."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command",
            side_effect=RuntimeError("CLI broken"),
        ):
            assert delete_coder_user("bob") is False


# ---------------------------------------------------------------------------
# fetch_user_workspaces
# ---------------------------------------------------------------------------


class TestFetchUserWorkspaces:
    """Tests for fetch_user_workspaces."""

    def test_returns_workspaces_for_user(self) -> None:
        """Returns only workspaces owned by the requested user."""
        workspaces = [
            _make_workspace("alice", "ws1"),
            _make_workspace("alice", "ws2"),
            _make_workspace("bob", "ws3"),  # different owner – should be filtered out
        ]
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(
                returncode=0, stdout=json.dumps(workspaces), stderr=""
            )
            result = fetch_user_workspaces("alice")

        assert len(result) == 2
        assert all(w["owner_name"] == "alice" for w in result)

    def test_returns_empty_list_when_none(self) -> None:
        """Empty workspace list returns empty result."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="[]", stderr="")
            assert fetch_user_workspaces("alice") == []

    def test_returns_empty_list_on_nonzero_exit(self) -> None:
        """Non-zero CLI exit (e.g. no workspaces) returns empty list."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
            assert fetch_user_workspaces("alice") == []

    def test_returns_empty_list_on_invalid_json(self) -> None:
        """Invalid JSON returns empty list instead of raising."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command"
        ) as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="bad json", stderr="")
            assert fetch_user_workspaces("alice") == []

    def test_returns_empty_list_on_runtime_error(self) -> None:
        """RuntimeError from CLI returns empty list."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command",
            side_effect=RuntimeError("CLI broken"),
        ):
            assert fetch_user_workspaces("alice") == []


# ---------------------------------------------------------------------------
# offboard_user
# ---------------------------------------------------------------------------


class TestOffboardUser:
    """Tests for offboard_user (single user)."""

    def _make_user(self, username: str = "alice") -> dict[str, Any]:
        return _make_coder_user(username)

    def test_full_offboard_dry_run(self) -> None:
        """Dry run reports all three steps without executing them."""
        user = self._make_user()
        workspaces = [_make_workspace("alice", "ws1")]

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=workspaces,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_workspace_cli",
                return_value=True,
            ) as mock_ws,
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ) as mock_del,
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client"
            ) as mock_fs,
        ):
            result = offboard_user(user, dry_run=True)

        assert result is True
        mock_ws.assert_called_once_with(
            owner_name="alice",
            workspace_name="ws1",
            orphan=False,
            auto_orphan_on_failure=True,
            dry_run=True,
        )
        mock_del.assert_called_once_with("alice", dry_run=True)
        # Firestore client should NOT be initialised in dry run
        mock_fs.assert_not_called()

    def test_suspend_instead_of_delete(self) -> None:
        """suspend=True calls suspend_coder_user instead of delete_coder_user."""
        user = self._make_user()

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=[],
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.suspend_coder_user",
                return_value=True,
            ) as mock_suspend,
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user"
            ) as mock_delete,
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            offboard_user(user, suspend=True, dry_run=True)

        mock_suspend.assert_called_once_with("alice", dry_run=True)
        mock_delete.assert_not_called()

    def test_skip_workspaces(self) -> None:
        """skip_workspaces=True bypasses workspace deletion."""
        user = self._make_user()

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces"
            ) as mock_fetch,
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            offboard_user(user, skip_workspaces=True, dry_run=True)

        mock_fetch.assert_not_called()

    def test_skip_firestore(self) -> None:
        """skip_firestore=True bypasses Firestore cleanup."""
        user = self._make_user()

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=[],
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client"
            ) as mock_fs,
        ):
            result = offboard_user(user, skip_firestore=True, dry_run=True)

        assert result is True
        mock_fs.assert_not_called()

    def test_workspace_deletion_failure_propagates(self) -> None:
        """Failed workspace deletion causes offboard_user to return False."""
        user = self._make_user()
        workspaces = [_make_workspace("alice", "ws1")]

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=workspaces,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_workspace_cli",
                return_value=False,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            result = offboard_user(user)

        assert result is False

    def test_coder_account_deletion_failure_propagates(self) -> None:
        """Failed Coder account deletion causes offboard_user to return False."""
        user = self._make_user()

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=[],
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=False,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            result = offboard_user(user)

        assert result is False

    def test_firestore_exception_propagates_as_false(self) -> None:
        """Firestore error counts as a failure but doesn't raise."""
        user = self._make_user()

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=[],
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                side_effect=Exception("Firestore down"),
            ),
        ):
            result = offboard_user(user)

        assert result is False

    def test_orphan_flag_passed_to_workspace_deletion(self) -> None:
        """orphan=True is forwarded to delete_workspace_cli."""
        user = self._make_user()
        workspaces = [_make_workspace("alice", "ws1")]

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=workspaces,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_workspace_cli",
                return_value=True,
            ) as mock_ws,
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            offboard_user(user, orphan=True)

        _, kwargs = mock_ws.call_args
        assert kwargs["orphan"] is True

    def test_multiple_workspaces_all_deleted(self) -> None:
        """All workspaces for a user are deleted."""
        user = self._make_user()
        workspaces = [
            _make_workspace("alice", "ws1"),
            _make_workspace("alice", "ws2"),
            _make_workspace("alice", "ws3"),
        ]

        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_user_workspaces",
                return_value=workspaces,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_workspace_cli",
                return_value=True,
            ) as mock_ws,
            patch(
                "aieng_platform_onboard.admin.offboard_users.delete_coder_user",
                return_value=True,
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.get_firestore_client",
                return_value=Mock(),
            ),
            patch("aieng_platform_onboard.admin.offboard_users.delete_participants"),
        ):
            result = offboard_user(user)

        assert result is True
        assert mock_ws.call_count == 3


# ---------------------------------------------------------------------------
# offboard_users (batch)
# ---------------------------------------------------------------------------


class TestOffboardUsers:
    """Tests for offboard_users (batch)."""

    def test_all_succeed(self) -> None:
        """All users succeed."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]

        with patch(
            "aieng_platform_onboard.admin.offboard_users.offboard_user",
            return_value=True,
        ) as mock_ob:
            success, failed = offboard_users(users)

        assert success == 2
        assert failed == 0
        assert mock_ob.call_count == 2

    def test_partial_failure(self) -> None:
        """Some failures are tracked correctly."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]

        def side_effect(user: dict, **kwargs: Any) -> bool:
            return user["username"] == "alice"

        with patch(
            "aieng_platform_onboard.admin.offboard_users.offboard_user",
            side_effect=side_effect,
        ):
            success, failed = offboard_users(users)

        assert success == 1
        assert failed == 1

    def test_all_fail(self) -> None:
        """All failures reported."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]

        with patch(
            "aieng_platform_onboard.admin.offboard_users.offboard_user",
            return_value=False,
        ):
            success, failed = offboard_users(users)

        assert success == 0
        assert failed == 2

    def test_empty_list(self) -> None:
        """Empty user list returns zeros."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.offboard_user"
        ) as mock_ob:
            success, failed = offboard_users([])

        assert success == 0
        assert failed == 0
        mock_ob.assert_not_called()

    def test_kwargs_forwarded(self) -> None:
        """All keyword arguments are forwarded to offboard_user."""
        users = [_make_coder_user("alice")]

        with patch(
            "aieng_platform_onboard.admin.offboard_users.offboard_user",
            return_value=True,
        ) as mock_ob:
            offboard_users(
                users,
                suspend=True,
                skip_workspaces=True,
                skip_firestore=True,
                orphan=True,
                auto_orphan_on_failure=False,
                dry_run=True,
            )

        mock_ob.assert_called_once_with(
            users[0],
            suspend=True,
            skip_workspaces=True,
            skip_firestore=True,
            orphan=True,
            auto_orphan_on_failure=False,
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# display_stale_users_table
# ---------------------------------------------------------------------------


class TestDisplayStaleUsersTable:
    """Tests for display_stale_users_table."""

    def test_renders_without_error(self) -> None:
        """Table renders without raising for a normal user list."""
        users = [_make_coder_user("alice"), _make_coder_user("bob")]
        display_stale_users_table(users, "my-org")  # must not raise

    def test_renders_empty_list(self) -> None:
        """Table renders without raising for an empty user list."""
        display_stale_users_table([], "my-org")

    def test_renders_users_with_missing_fields(self) -> None:
        """Table renders even when optional fields are absent."""
        users = [{"username": "alice", "login_type": "github"}]
        display_stale_users_table(users, "my-org")


# ---------------------------------------------------------------------------
# offboard_users_from_org (top-level integration)
# ---------------------------------------------------------------------------


class TestOffboardUsersFromOrg:
    """Tests for offboard_users_from_org."""

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _patch_coder_version_ok(self) -> Mock:
        """Return a mock that succeeds the Coder version check."""
        return Mock(returncode=0, stdout="Coder v2.0.0", stderr="")

    def _base_patches(
        self,
        coder_users: list[dict],
        org_members: set[str],
        stale_users: list[dict] | None = None,
    ):
        """Context manager stack for the common happy-path patches."""
        stack = ExitStack()
        stack.enter_context(
            patch(
                "aieng_platform_onboard.admin.offboard_users.run_coder_command",
                return_value=self._patch_coder_version_ok(),
            )
        )
        stack.enter_context(
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_github_org_members",
                return_value=org_members,
            )
        )
        stack.enter_context(
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_coder_users",
                return_value=coder_users,
            )
        )
        if stale_users is not None:
            stack.enter_context(
                patch(
                    "aieng_platform_onboard.admin.offboard_users.find_stale_coder_users",
                    return_value=stale_users,
                )
            )
        return stack

    # ------------------------------------------------------------------
    # CLI / infrastructure failures
    # ------------------------------------------------------------------

    def test_coder_cli_not_available_returns_1(self) -> None:
        """Returns 1 when the Coder CLI is not available."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command",
            side_effect=RuntimeError("Coder CLI not found"),
        ):
            assert offboard_users_from_org("my-org") == 1

    def test_coder_version_check_fails_returns_1(self) -> None:
        """Returns 1 when the Coder version check exits non-zero."""
        with patch(
            "aieng_platform_onboard.admin.offboard_users.run_coder_command",
            return_value=Mock(returncode=1, stdout="", stderr="bad"),
        ):
            assert offboard_users_from_org("my-org") == 1

    def test_github_org_fetch_failure_returns_1(self) -> None:
        """Returns 1 when the GitHub org member fetch fails."""
        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.run_coder_command",
                return_value=self._patch_coder_version_ok(),
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_github_org_members",
                side_effect=RuntimeError("API error"),
            ),
        ):
            assert offboard_users_from_org("my-org") == 1

    def test_coder_user_fetch_failure_returns_1(self) -> None:
        """Returns 1 when fetching Coder users fails."""
        with (
            patch(
                "aieng_platform_onboard.admin.offboard_users.run_coder_command",
                return_value=self._patch_coder_version_ok(),
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_github_org_members",
                return_value={"alice"},
            ),
            patch(
                "aieng_platform_onboard.admin.offboard_users.fetch_coder_users",
                side_effect=RuntimeError("CLI error"),
            ),
        ):
            assert offboard_users_from_org("my-org") == 1

    # ------------------------------------------------------------------
    # No stale users
    # ------------------------------------------------------------------

    def test_no_stale_users_returns_0(self) -> None:
        """Returns 0 without prompting when there are no stale users."""
        users = [_make_coder_user("alice")]
        with self._base_patches(users, {"alice"}, stale_users=[]) as _:
            assert offboard_users_from_org("my-org") == 0

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------

    def test_dry_run_returns_0_and_does_not_call_offboard(self) -> None:
        """Dry run completes without calling the actual offboard logic."""
        users = [_make_coder_user("alice")]
        stale = [_make_coder_user("alice")]

        with (
            self._base_patches(users, set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users",
                return_value=(1, 0),
            ) as mock_ob,
        ):
            result = offboard_users_from_org("my-org", dry_run=True)

        assert result == 0
        # offboard_users IS called in dry-run (with dry_run=True forwarded)
        mock_ob.assert_called_once()
        _, kwargs = mock_ob.call_args
        assert kwargs["dry_run"] is True

    # ------------------------------------------------------------------
    # Confirmation prompt
    # ------------------------------------------------------------------

    def test_user_cancels_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cancellation at the confirmation prompt returns 0."""
        stale = [_make_coder_user("alice")]
        monkeypatch.setattr("builtins.input", lambda: "NO")

        with (
            self._base_patches([], set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users"
            ) as mock_ob,
        ):
            result = offboard_users_from_org("my-org", dry_run=False)

        assert result == 0
        mock_ob.assert_not_called()

    def test_user_confirms_offboarding(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Correct confirmation triggers offboarding."""
        stale = [_make_coder_user("alice")]
        monkeypatch.setattr("builtins.input", lambda: "OFFBOARD")

        with (
            self._base_patches([], set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users",
                return_value=(1, 0),
            ) as mock_ob,
        ):
            result = offboard_users_from_org("my-org", dry_run=False)

        assert result == 0
        mock_ob.assert_called_once()

    # ------------------------------------------------------------------
    # Success / failure exit codes
    # ------------------------------------------------------------------

    def test_all_succeed_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 0 when all offboardings succeed."""
        stale = [_make_coder_user("alice")]
        monkeypatch.setattr("builtins.input", lambda: "OFFBOARD")

        with (
            self._base_patches([], set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users",
                return_value=(1, 0),
            ),
        ):
            assert offboard_users_from_org("my-org") == 0

    def test_partial_failure_returns_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 1 when at least one offboarding fails."""
        stale = [_make_coder_user("alice"), _make_coder_user("bob")]
        monkeypatch.setattr("builtins.input", lambda: "OFFBOARD")

        with (
            self._base_patches([], set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users",
                return_value=(1, 1),
            ),
        ):
            assert offboard_users_from_org("my-org") == 1

    # ------------------------------------------------------------------
    # Flag forwarding
    # ------------------------------------------------------------------

    def test_flags_forwarded_to_offboard_users(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All option flags are forwarded correctly to offboard_users."""
        stale = [_make_coder_user("alice")]
        monkeypatch.setattr("builtins.input", lambda: "OFFBOARD")

        with (
            self._base_patches([], set(), stale_users=stale),
            patch(
                "aieng_platform_onboard.admin.offboard_users.offboard_users",
                return_value=(1, 0),
            ) as mock_ob,
        ):
            offboard_users_from_org(
                "my-org",
                suspend=True,
                skip_workspaces=True,
                skip_firestore=True,
                orphan=True,
                auto_orphan_on_failure=False,
                dry_run=False,
            )

        _, kwargs = mock_ob.call_args
        assert kwargs["suspend"] is True
        assert kwargs["skip_workspaces"] is True
        assert kwargs["skip_firestore"] is True
        assert kwargs["orphan"] is True
        assert kwargs["auto_orphan_on_failure"] is False
        assert kwargs["dry_run"] is False
