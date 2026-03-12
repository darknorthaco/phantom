# Regression Sweep — Phase 4 / Phase 6 Compatibility Fixes

**Date:** 2025-03-11  
**Objective:** Fix tests expecting `WorkerDiscoveryAdapter._backend` and scan for similar regressions.

---

## Changes Applied

### 1. installer/backend_interface/worker_discovery_adapter.py

**Fix:** Restore backward-compatible `_backend` alias for tests.

```diff
     def __init__(self):
         self._udp_client = InstallerDiscoveryClient()
         self._legacy = WorkerDiscovery()
+        # Backward-compatible alias for tests that expect _backend (get_local_network, check_worker_port)
+        self._backend = self._legacy
```

**Rationale:** Tests in `test_wizard_backend.py` patch `self.adapter._backend` for `get_local_network` and `check_worker_port`. Both delegate to `_legacy`, so `_backend = _legacy` restores compatibility without changing runtime behavior.

---

### 2. phantom_core/tests/test_wizard_backend.py

**Fix:** Update `test_discover_comprehensive_delegates` and `test_discover_manual_delegates` to mock the new UDP discovery path instead of the removed legacy delegation.

```diff
     def test_discover_comprehensive_delegates(self):
-        with patch.object(
-            self.adapter._backend,
-            "discover_workers_comprehensive",
+        """discover_comprehensive() uses UDP discovery; mock _udp_client.discover."""
+        with patch.object(
+            self.adapter._udp_client,
+            "discover",
             return_value=[],
         ) as mock:
             result = self.adapter.discover_comprehensive()
             mock.assert_called_once()
             self.assertEqual(result, [])

     def test_discover_manual_delegates(self):
-        with patch.object(
-            self.adapter._backend,
-            "discover_workers_manual",
+        """discover_manual() uses UDP discovery; mock _udp_client.discover."""
+        with patch.object(
+            self.adapter._udp_client,
+            "discover",
             return_value=[],
         ) as mock:
             result = self.adapter.discover_manual()
             mock.assert_called_once()
             self.assertEqual(result, [])
```

**Rationale:** Phase 4 replaced `discover_workers_comprehensive` / `discover_workers_manual` delegation with UDP discovery via `_udp_client.discover()`. Tests now mock the actual code path without changing core logic.

---

## Repo-Wide Scan Results

| Category | Finding | Action |
|----------|---------|--------|
| `_backend` | `test_wizard_backend.py` only | Fixed — alias restored |
| `_adapter` | No test references | None |
| `_controller` | `test_integration`, `test_security_defaults` — method names, not attributes | None |
| Linux/Windows worker paths | No tests reference `linux_worker.main` or `windows_worker.main` | None |
| Old discovery paths | Discovery tests updated to UDP path | Fixed |
| Old manifest format | `test_manifest_signing.py` — tests schema, not discovery adapter | None |
| Silent failures | Phase 5/6 deployer changes — no tests assert silent Ok() | None |

---

## Test Verification

```
$ python -m unittest phantom_core.tests.test_wizard_backend.TestWorkerDiscoveryAdapter -v
test_check_worker_port_delegates_to_backend ... ok
test_discover_comprehensive_delegates ... ok
test_discover_manual_delegates ... ok
test_enrich_adds_display_fields ... ok
test_enrich_unknown_gpu ... ok
test_get_local_network_delegates_to_backend ... ok
test_is_suitable_task_master_high_vram ... ok
test_is_suitable_task_master_low_vram ... ok
test_is_suitable_task_master_unknown_vram ... ok
test_task_master_message_insufficient ... ok
test_task_master_message_sufficient ... ok
test_task_master_message_unknown_vram ... ok
----------------------------------------------------------------------
Ran 12 tests in 0.087s
OK
```

---

## Summary

- **2 files modified**
- **No core logic changed**
- **No diagnostics or integrity enforcement weakened**
- **WorkerDiscoveryAdapter tests:** 12/12 pass

**Ready for commit. Pausing per request.**
