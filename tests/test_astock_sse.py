"""SSE / EventBus tests — at least 2 tests.

Tests verify:
1. EventBus publish/poll/peek/clear work correctly
2. SSE route structure (blueprint registration, response type)
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_API = _REPO / "tradingagents" / "astock" / "api"
_PKG_PARENT_EXEC = "tradingagents.astock.execution"
_PKG_PARENT_API = "tradingagents.astock.api"


def _load_submodule(rel_name: str, path_root: Path, pkg_parent: str):
    """Load a module without polluting sys.modules with fake packages."""
    import importlib

    fname = rel_name + ".py"
    full_name = f"{pkg_parent}.{rel_name}"
    path = str(path_root / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", pkg_parent):
        mod = sys.modules.get(parent)
        if mod is not None and hasattr(mod, "__path__") and not getattr(mod, "__path__", []):
            del sys.modules[parent]
        if parent not in sys.modules:
            try:
                importlib.import_module(parent)
            except ImportError:
                pass
    exec_pkg = sys.modules.get(pkg_parent)
    if exec_pkg:
        exec_pkg.__path__ = [str(path_root)]
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg_parent
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load modules
# Use importlib for package submodules (infrastructure.event_bus)
import importlib
_eb = importlib.import_module("tradingagents.astock.execution.infrastructure.event_bus")
_sse = _load_submodule("routes_sse", _API, _PKG_PARENT_API)

EventBus = _eb.EventBus


class TestEventBus(unittest.TestCase):
    """Test the in-process EventBus."""

    def setUp(self):
        EventBus.clear()

    def tearDown(self):
        EventBus.clear()

    def test_publish_and_poll(self):
        """Published events can be polled in FIFO order."""
        EventBus.publish({"type": "test", "value": 1})
        EventBus.publish({"type": "test", "value": 2})
        self.assertEqual(EventBus.size(), 2)

        e1 = EventBus.poll()
        self.assertEqual(e1["value"], 1)
        e2 = EventBus.poll()
        self.assertEqual(e2["value"], 2)
        self.assertIsNone(EventBus.poll())  # Empty

    def test_peek_all_returns_copy(self):
        """peek_all returns all events without removing them."""
        EventBus.publish({"type": "alpha"})
        EventBus.publish({"type": "beta"})
        all_events = EventBus.peek_all()
        self.assertEqual(len(all_events), 2)
        # Buffer should still have events
        self.assertEqual(EventBus.size(), 2)
        # peek_all returns a copy
        all_events.append({"type": "gamma"})
        self.assertEqual(EventBus.size(), 2)

    def test_clear(self):
        """clear removes all buffered events."""
        EventBus.publish({"type": "test"})
        EventBus.publish({"type": "test"})
        self.assertEqual(EventBus.size(), 2)
        EventBus.clear()
        self.assertEqual(EventBus.size(), 0)
        self.assertIsNone(EventBus.poll())

    def test_to_json_list(self):
        """to_json_list returns valid JSON array string."""
        EventBus.publish({"type": "a", "val": 1})
        EventBus.publish({"type": "b", "val": 2})
        json_str = EventBus.to_json_list()
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 2)

    def test_ring_buffer_max_size(self):
        """EventBus caps buffer at MAX_EVENTS."""
        for i in range(EventBus.MAX_EVENTS + 100):
            EventBus.publish({"i": i})
        self.assertLessEqual(EventBus.size(), EventBus.MAX_EVENTS)


class TestSseBlueprint(unittest.TestCase):
    """Test SSE blueprint structure."""

    def test_blueprint_created(self):
        """routes_sse has a valid blueprint with expected routes."""
        bp = _sse.bp
        self.assertIsNotNone(bp)
        # Check the blueprint name
        self.assertEqual(bp.name, "sse")

    def test_sse_route_returns_response(self):
        """paper_progress_sse endpoint can be created."""
        # Create a minimal Flask app to test the route
        try:
            from flask import Flask

            app = Flask(__name__)
            app.config["ASTOCK_REQUIRE_AUTH"] = False
            app.register_blueprint(_sse.bp, url_prefix="/api/v1")
            with app.test_client() as client:
                # Use streamed=True to get a streaming response
                resp = client.get("/api/v1/sse/paper-progress")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.mimetype, "text/event-stream")
                # Read first 200 bytes from the streaming response
                # (the generator yields data: {...}\n\n or a heartbeat)
                first_chunk = b""
                for chunk in resp.response:
                    first_chunk += chunk
                    if len(first_chunk) >= 200:
                        break
                self.assertIn(b"data: ", first_chunk)
        except Exception as e:
            self.fail(f"SSE route test failed: {e}")

    def test_events_endpoint(self):
        """GET /sse/events returns buffered events."""
        EventBus.clear()
        EventBus.publish({"type": "test_event"})
        try:
            from flask import Flask

            app = Flask(__name__)
            app.config["ASTOCK_REQUIRE_AUTH"] = False
            app.register_blueprint(_sse.bp, url_prefix="/api/v1")
            with app.test_client() as client:
                resp = client.get("/api/v1/sse/events")
                self.assertEqual(resp.status_code, 200)
                data = json.loads(resp.data.decode("utf-8"))["data"]["events"]
                self.assertIsInstance(data, list)
                self.assertGreaterEqual(len(data), 1)
        except Exception as e:
            self.fail(f"Events endpoint test failed: {e}")


class TestTaskRunWrapping(unittest.TestCase):
    """Validate that raw events are wrapped with TaskRun fields."""

    def setUp(self):
        from tradingagents.astock.api.routes_sse import _to_task_run
        self._to_task_run = _to_task_run

    def test_cycle_start_has_task_run_fields(self):
        e = self._to_task_run({"type": "cycle_start", "cycle": 1,
                               "timestamp": "2026-06-25T12:00:00"})
        self.assertEqual(e["task_type"], "research")
        self.assertEqual(e["status"], "running")
        self.assertIn("task_id", e)
        self.assertIn("progress", e)
        self.assertIsNone(e["finished_at"])

    def test_error_has_failure_fields(self):
        e = self._to_task_run({"type": "error", "message": "fail",
                               "timestamp": "2026-06-25T12:00:00"})
        self.assertEqual(e["status"], "failed")
        self.assertIsNotNone(e["error"])
        self.assertEqual(e["error"]["message"], "fail")
        self.assertIsNotNone(e["finished_at"])

    def test_idle_has_idle_status(self):
        e = self._to_task_run({"type": "idle", "timestamp": 12345.0})
        self.assertEqual(e["status"], "idle")
        self.assertEqual(e["task_type"], "data_refresh")

    def test_unknown_event_preserved(self):
        e = self._to_task_run({"type": "my_event", "custom": 42})
        self.assertEqual(e["custom"], 42)
        self.assertIn("task_id", e)
        self.assertIn("status", e)

    def test_events_endpoint_returns_task_run_fields(self):
        from flask import Flask
        from tradingagents.astock.api import routes_sse as _sse

        EventBus.clear()
        EventBus.publish({"type": "cycle_start", "cycle": 99})
        EventBus.publish({"type": "error", "message": "oops"})

        app = Flask(__name__)
        app.config["ASTOCK_REQUIRE_AUTH"] = False
        app.register_blueprint(_sse.bp, url_prefix="/api/v1")
        with app.test_client() as client:
            resp = client.get("/api/v1/sse/events")
            data = json.loads(resp.data.decode("utf-8"))["data"]["events"]
            self.assertEqual(len(data), 2)
            for entry in data:
                self.assertIn("task_id", entry)
                self.assertIn("task_type", entry)
                self.assertIn("status", entry)
                self.assertIn("progress", entry)
            # Second event should be failed
            self.assertEqual(data[1]["status"], "failed")
            self.assertEqual(data[1]["error"]["message"], "oops")


if __name__ == "__main__":
    unittest.main()
