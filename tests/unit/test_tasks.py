"""Unit tests for task polling helpers."""

from __future__ import annotations

from typing import Any

import pytest

from sylve_cli.client import SylveError
from sylve_cli.tasks import (
    wait_for_backup_event,
    wait_for_lifecycle_task,
    wait_for_replication_event,
)


class FakeClient:
    """Minimal client returning queued responses in order."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.calls = 0

    def get(self, path: str, **_kwargs: Any) -> dict[str, Any]:
        """Return the next canned response."""
        self.calls += 1
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0] if self._responses else {}


def test_wait_for_lifecycle_task_success() -> None:
    client = FakeClient(
        [
            {"id": 1, "status": "queued"},
            {"id": 1, "status": "completed", "guestType": "vm", "guestId": 101},
        ]
    )
    result = wait_for_lifecycle_task(client, 1, poll_interval=0, quiet=True)
    assert result["status"] == "completed"
    assert client.calls == 2


def test_wait_for_lifecycle_task_failure() -> None:
    client = FakeClient([{"id": 1, "status": "failed", "error": "boom"}])
    with pytest.raises(SylveError, match="boom"):
        wait_for_lifecycle_task(client, 1, poll_interval=0, quiet=True)


def test_wait_for_lifecycle_task_timeout() -> None:
    client = FakeClient([{"id": 1, "status": "running"}])
    with pytest.raises(SylveError, match="Timed out"):
        wait_for_lifecycle_task(client, 1, timeout=0.01, poll_interval=0.001, quiet=True)


def test_wait_for_replication_event_success() -> None:
    client = FakeClient(
        [
            {"event": {"status": "running"}, "progressPercent": 50},
            {"event": {"status": "completed"}, "progressPercent": 100},
        ]
    )
    event = wait_for_replication_event(client, 7, poll_interval=0)
    assert event["status"] == "completed"


def test_wait_for_replication_event_failure() -> None:
    client = FakeClient([{"event": {"status": "failed", "error": "replication broke"}}])
    with pytest.raises(SylveError, match="replication broke"):
        wait_for_replication_event(client, 7, poll_interval=0)


def test_wait_for_backup_event_success_and_failure() -> None:
    client = FakeClient(
        [
            {"event": {"status": "running"}, "progressPercent": 25, "phase": "send"},
            {"event": {"status": "completed"}, "progressPercent": 100},
        ]
    )
    event = wait_for_backup_event(client, 8, poll_interval=0)
    assert event["status"] == "completed"

    failing = FakeClient([{"event": {"status": "failed"}, "progressPercent": 0}])
    with pytest.raises(SylveError, match="failed"):
        wait_for_backup_event(failing, 8, poll_interval=0)
