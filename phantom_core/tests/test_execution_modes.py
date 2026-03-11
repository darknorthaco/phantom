"""
Comprehensive pytest test suite for Phantom execution mode switching.

Covers:
  1. ExecutionMode enum (controller_api) — values, string construction, invalid mode
  2. _set_execution_mode() — all transitions, previous_mode, audit log, same-mode no-op
  3. REST API endpoints — GET /mode, POST /mode, POST /system/execution-mode
  4. LightweightLLMTaskMaster.set_execution_mode() — propagation, ValueError, record fields
  5. TaskMasterPipeline.update_mode() — system_mode and mode_gate.system_mode updated

All tests are unit-level; no live controller is required.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — mirror the pattern used by other tests in this directory
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "phantom_core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "llm_taskmaster"))


# ===========================================================================
# 1. ExecutionMode enum (controller_api)
# ===========================================================================


class TestControllerApiExecutionModeEnum:
    """Tests for the ExecutionMode(str, Enum) defined in controller_api."""

    @pytest.fixture(autouse=True)
    def _import_enum(self):
        from controller_api import ExecutionMode

        self.ExecutionMode = ExecutionMode

    def test_all_three_modes_exist(self):
        """AUTO, HYBRID, and MANUAL members must exist."""
        assert hasattr(self.ExecutionMode, "AUTO")
        assert hasattr(self.ExecutionMode, "HYBRID")
        assert hasattr(self.ExecutionMode, "MANUAL")

    def test_auto_value(self):
        """AUTO mode value must be the string 'AUTO'."""
        assert self.ExecutionMode.AUTO.value == "AUTO"

    def test_hybrid_value(self):
        """HYBRID mode value must be the string 'HYBRID'."""
        assert self.ExecutionMode.HYBRID.value == "HYBRID"

    def test_manual_value(self):
        """MANUAL mode value must be the string 'MANUAL'."""
        assert self.ExecutionMode.MANUAL.value == "MANUAL"

    def test_construct_from_string(self):
        """ExecutionMode can be constructed from its string value."""
        assert self.ExecutionMode("AUTO") is self.ExecutionMode.AUTO
        assert self.ExecutionMode("HYBRID") is self.ExecutionMode.HYBRID
        assert self.ExecutionMode("MANUAL") is self.ExecutionMode.MANUAL

    def test_invalid_string_raises_value_error(self):
        """Constructing ExecutionMode from an unknown string raises ValueError."""
        with pytest.raises(ValueError):
            self.ExecutionMode("BOGUS")


# ===========================================================================
# 2. _set_execution_mode() — core switching function
# ===========================================================================


class TestSetExecutionMode:
    """Tests for the _set_execution_mode() helper in controller_api."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import controller_api as ca

        self.ca = ca
        self.ExecutionMode = ca.ExecutionMode
        # Reset global state before every test
        ca.execution_mode = ca.ExecutionMode.AUTO
        ca.mode_audit_log.clear()

    def _call(self, mode, session_id="sess-1", source="test"):
        return self.ca._set_execution_mode(mode, session_id, source)

    # --- Transition matrix (all 6 ordered pairs) ---

    def test_auto_to_hybrid(self):
        """AUTO → HYBRID transition updates mode and returns correct dict."""
        result = self._call(self.ExecutionMode.HYBRID)
        assert result["previous_mode"] == "AUTO"
        assert result["mode"] == "HYBRID"
        assert self.ca.execution_mode is self.ExecutionMode.HYBRID

    def test_auto_to_manual(self):
        """AUTO → MANUAL transition updates mode and returns correct dict."""
        result = self._call(self.ExecutionMode.MANUAL)
        assert result["previous_mode"] == "AUTO"
        assert result["mode"] == "MANUAL"

    def test_hybrid_to_auto(self):
        """HYBRID → AUTO transition."""
        self.ca.execution_mode = self.ExecutionMode.HYBRID
        result = self._call(self.ExecutionMode.AUTO)
        assert result["previous_mode"] == "HYBRID"
        assert result["mode"] == "AUTO"

    def test_hybrid_to_manual(self):
        """HYBRID → MANUAL transition."""
        self.ca.execution_mode = self.ExecutionMode.HYBRID
        result = self._call(self.ExecutionMode.MANUAL)
        assert result["previous_mode"] == "HYBRID"
        assert result["mode"] == "MANUAL"

    def test_manual_to_auto(self):
        """MANUAL → AUTO transition."""
        self.ca.execution_mode = self.ExecutionMode.MANUAL
        result = self._call(self.ExecutionMode.AUTO)
        assert result["previous_mode"] == "MANUAL"
        assert result["mode"] == "AUTO"

    def test_manual_to_hybrid(self):
        """MANUAL → HYBRID transition."""
        self.ca.execution_mode = self.ExecutionMode.MANUAL
        result = self._call(self.ExecutionMode.HYBRID)
        assert result["previous_mode"] == "MANUAL"
        assert result["mode"] == "HYBRID"

    # --- Return-value shape ---

    def test_returns_status_mode_set(self):
        """Response always includes status='mode_set'."""
        result = self._call(self.ExecutionMode.HYBRID)
        assert result["status"] == "mode_set"

    def test_returns_session_id(self):
        """Response echoes back the session_id that was passed in."""
        result = self._call(self.ExecutionMode.HYBRID, session_id="my-session")
        assert result["session_id"] == "my-session"

    def test_returns_source(self):
        """Response echoes back the source that was passed in."""
        result = self._call(self.ExecutionMode.HYBRID, source="socket")
        assert result["source"] == "socket"

    # --- Audit log ---

    def test_audit_entry_recorded_on_switch(self):
        """Every mode switch appends exactly one audit entry."""
        self._call(self.ExecutionMode.HYBRID)
        assert len(self.ca.mode_audit_log) == 1
        entry = self.ca.mode_audit_log[0]
        assert entry["event_type"] == "mode_changed"

    def test_audit_entry_contains_modes(self):
        """Audit entry payload contains both previous and new mode."""
        self._call(self.ExecutionMode.MANUAL)
        entry = self.ca.mode_audit_log[0]
        assert entry["payload"]["previous_mode"] == "AUTO"
        assert entry["payload"]["mode"] == "MANUAL"

    def test_multiple_switches_create_multiple_audit_entries(self):
        """Each call creates its own audit entry."""
        self._call(self.ExecutionMode.HYBRID)
        self._call(self.ExecutionMode.MANUAL)
        assert len(self.ca.mode_audit_log) == 2

    # --- Same-mode no-op behaviour ---

    def test_same_mode_switch_returns_identical_previous_and_current(self):
        """Switching to the current mode returns previous_mode == mode."""
        result = self._call(self.ExecutionMode.AUTO)
        assert result["previous_mode"] == result["mode"] == "AUTO"

    def test_same_mode_still_records_audit_entry(self):
        """Even a no-op switch is audited for traceability."""
        self._call(self.ExecutionMode.AUTO)
        assert len(self.ca.mode_audit_log) == 1

    # --- Invalid mode ---

    def test_invalid_string_raises_value_error(self):
        """Passing an unknown mode string must raise ValueError."""
        with pytest.raises(ValueError):
            self._call("SUPER_AUTO")


# ===========================================================================
# 3. REST API endpoints
# ===========================================================================


class TestModeRestEndpoints:
    """Tests for the mode REST endpoints in controller_api using TestClient."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import controller_api as ca
        from starlette.testclient import TestClient

        ca.execution_mode = ca.ExecutionMode.AUTO
        ca.mode_audit_log.clear()
        self.client = TestClient(ca.app, raise_server_exceptions=True)
        self.ca = ca

    # --- GET /mode ---

    def test_get_mode_returns_200(self):
        """GET /mode returns HTTP 200."""
        resp = self.client.get("/mode")
        assert resp.status_code == 200

    def test_get_mode_contains_mode_field(self):
        """GET /mode response body includes a 'mode' key."""
        resp = self.client.get("/mode")
        assert "mode" in resp.json()

    def test_get_mode_returns_current_mode(self):
        """GET /mode returns the currently active mode."""
        resp = self.client.get("/mode")
        assert resp.json()["mode"] == "AUTO"

    def test_get_mode_contains_schemas(self):
        """GET /mode response body includes a 'schemas' key with all three modes."""
        resp = self.client.get("/mode")
        schemas = resp.json().get("schemas", {})
        assert "AUTO" in schemas
        assert "HYBRID" in schemas
        assert "MANUAL" in schemas

    # --- POST /mode ---

    def test_post_mode_changes_mode(self):
        """POST /mode with a valid mode switches the active mode."""
        resp = self.client.post("/mode", json={"mode": "HYBRID"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "HYBRID"

    def test_post_mode_returns_previous_mode(self):
        """POST /mode response includes the mode that was active before the switch."""
        resp = self.client.post("/mode", json={"mode": "MANUAL"})
        assert resp.json()["previous_mode"] == "AUTO"

    def test_post_mode_updates_global_state(self):
        """POST /mode actually updates the in-process global execution_mode."""
        self.client.post("/mode", json={"mode": "HYBRID"})
        assert self.ca.execution_mode is self.ca.ExecutionMode.HYBRID

    def test_post_mode_with_session_id(self):
        """POST /mode accepts an optional session_id and echoes it back."""
        resp = self.client.post("/mode", json={"mode": "MANUAL", "session_id": "s-123"})
        assert resp.json()["session_id"] == "s-123"

    def test_post_mode_invalid_returns_422(self):
        """POST /mode with an unrecognised mode string returns HTTP 422."""
        resp = self.client.post("/mode", json={"mode": "TURBO"})
        assert resp.status_code == 422

    def test_post_mode_missing_mode_returns_422(self):
        """POST /mode with an empty body returns HTTP 422."""
        resp = self.client.post("/mode", json={})
        assert resp.status_code == 422

    # --- POST /system/execution-mode ---

    def test_post_system_mode_valid(self):
        """POST /system/execution-mode with a valid mode returns 200."""
        resp = self.client.post(
            "/system/execution-mode",
            json={"mode": "hybrid", "changed_by": "operator", "reason": "testing"},
        )
        assert resp.status_code == 200

    def test_post_system_mode_response_contains_new_mode(self):
        """POST /system/execution-mode response body contains new_mode."""
        resp = self.client.post(
            "/system/execution-mode",
            json={"mode": "manual", "changed_by": "op", "reason": "test"},
        )
        assert resp.json()["new_mode"] == "manual"

    def test_post_system_mode_response_contains_previous_mode(self):
        """POST /system/execution-mode response body contains previous_mode."""
        resp = self.client.post(
            "/system/execution-mode",
            json={"mode": "hybrid", "changed_by": "op", "reason": "test"},
        )
        assert "previous_mode" in resp.json()

    def test_post_system_mode_invalid_returns_400(self):
        """POST /system/execution-mode with an invalid mode returns HTTP 400."""
        resp = self.client.post(
            "/system/execution-mode",
            json={"mode": "turbo", "changed_by": "op", "reason": "test"},
        )
        assert resp.status_code == 400

    def test_post_system_mode_all_valid_values(self):
        """POST /system/execution-mode accepts 'auto', 'hybrid', and 'manual'."""
        for mode in ("auto", "hybrid", "manual"):
            resp = self.client.post(
                "/system/execution-mode",
                json={"mode": mode, "changed_by": "op", "reason": "test"},
            )
            assert resp.status_code == 200, f"Expected 200 for mode={mode}"


# ===========================================================================
# 4. LightweightLLMTaskMaster.set_execution_mode()
# ===========================================================================


class TestLightweightLLMTaskMasterModeSwitch:
    """Tests for LightweightLLMTaskMaster.set_execution_mode()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        import os
        import lightweight_llm_setup as lls
        from lightweight_llm_setup import LightweightLLMTaskMaster, ExecutionMode

        # Remove any lingering env var so the task master starts in the default AUTO mode
        os.environ.pop("PHANTOM_EXECUTION_MODE", None)

        self.lls = lls
        self.LightweightLLMTaskMaster = LightweightLLMTaskMaster
        self.ExecutionMode = ExecutionMode
        self.tm = LightweightLLMTaskMaster()

    def test_initial_mode_is_auto(self):
        """Task master defaults to AUTO mode on creation."""
        assert self.tm.execution_mode == self.ExecutionMode.AUTO

    def test_set_mode_updates_execution_mode(self):
        """set_execution_mode() updates self.execution_mode."""
        self.tm.set_execution_mode("hybrid")
        assert self.tm.execution_mode == self.ExecutionMode.HYBRID

    def test_set_mode_all_transitions(self):
        """All valid mode transitions work correctly."""
        for target in ("auto", "hybrid", "manual"):
            self.tm.set_execution_mode(target)
            assert self.tm.execution_mode.value == target

    def test_invalid_mode_raises_value_error(self):
        """set_execution_mode() with an invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid execution mode"):
            self.tm.set_execution_mode("turbo")

    def test_invalid_mode_does_not_change_current_mode(self):
        """After a failed set_execution_mode(), the mode is unchanged."""
        original = self.tm.execution_mode
        with pytest.raises(ValueError):
            self.tm.set_execution_mode("invalid_mode")
        assert self.tm.execution_mode == original

    def test_change_record_contains_previous_mode(self):
        """Returned change record includes 'previous_mode' field."""
        record = self.tm.set_execution_mode("hybrid")
        assert "previous_mode" in record
        assert record["previous_mode"] == "auto"

    def test_change_record_contains_new_mode(self):
        """Returned change record includes 'new_mode' field."""
        record = self.tm.set_execution_mode("manual")
        assert "new_mode" in record
        assert record["new_mode"] == "manual"

    def test_change_record_contains_timestamp(self):
        """Returned change record includes an ISO-format 'timestamp' field."""
        record = self.tm.set_execution_mode("hybrid")
        assert "timestamp" in record
        # Basic ISO format check: contains 'T' separator
        assert "T" in record["timestamp"]

    def test_change_record_contains_changed_by(self):
        """Returned change record echoes back the 'changed_by' argument."""
        record = self.tm.set_execution_mode("hybrid", changed_by="operator-1")
        assert record["changed_by"] == "operator-1"

    def test_change_record_contains_reason(self):
        """Returned change record echoes back the 'reason' argument."""
        record = self.tm.set_execution_mode("manual", reason="debugging session")
        assert record["reason"] == "debugging session"

    def test_propagates_to_pipeline_when_active(self):
        """If a pipeline is active, set_execution_mode() calls pipeline.update_mode()."""
        mock_pipeline = MagicMock()
        self.tm.pipeline = mock_pipeline

        with patch.object(self.lls, "PIPELINE_AVAILABLE", True):
            self.tm.set_execution_mode("manual")

        mock_pipeline.update_mode.assert_called_once()

    def test_does_not_call_pipeline_when_pipeline_is_none(self):
        """If pipeline is None, set_execution_mode() must not raise."""
        self.tm.pipeline = None
        # Should complete without error
        record = self.tm.set_execution_mode("hybrid")
        assert record["new_mode"] == "hybrid"


# ===========================================================================
# 5. TaskMasterPipeline.update_mode()
# ===========================================================================


class TestTaskMasterPipelineUpdateMode:
    """Tests for TaskMasterPipeline.update_mode()."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from pipeline import TaskMasterPipeline, ExecutionMode

        self.TaskMasterPipeline = TaskMasterPipeline
        self.ExecutionMode = ExecutionMode
        self.pipeline = TaskMasterPipeline({}, ExecutionMode.AUTO)

    def test_initial_system_mode_is_auto(self):
        """Pipeline starts with AUTO system mode."""
        assert self.pipeline.system_mode == self.ExecutionMode.AUTO

    def test_update_mode_sets_system_mode(self):
        """update_mode() sets self.system_mode to the new mode."""
        self.pipeline.update_mode(self.ExecutionMode.HYBRID)
        assert self.pipeline.system_mode == self.ExecutionMode.HYBRID

    def test_update_mode_sets_mode_gate_system_mode(self):
        """update_mode() also updates self.mode_gate.system_mode."""
        self.pipeline.update_mode(self.ExecutionMode.MANUAL)
        assert self.pipeline.mode_gate.system_mode == self.ExecutionMode.MANUAL

    def test_update_mode_all_transitions(self):
        """All three mode values can be set via update_mode()."""
        for mode in (
            self.ExecutionMode.AUTO,
            self.ExecutionMode.HYBRID,
            self.ExecutionMode.MANUAL,
        ):
            self.pipeline.update_mode(mode)
            assert self.pipeline.system_mode == mode
            assert self.pipeline.mode_gate.system_mode == mode

    def test_update_mode_pipeline_and_gate_stay_in_sync(self):
        """system_mode and mode_gate.system_mode are always identical after update."""
        self.pipeline.update_mode(self.ExecutionMode.HYBRID)
        assert self.pipeline.system_mode == self.pipeline.mode_gate.system_mode

        self.pipeline.update_mode(self.ExecutionMode.MANUAL)
        assert self.pipeline.system_mode == self.pipeline.mode_gate.system_mode
