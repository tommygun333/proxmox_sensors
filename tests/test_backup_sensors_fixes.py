"""Dependency-free regression tests for Proxmox backup timestamps and VMID parsing."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parents[1] / "custom_components/proxmox_sensors"
HELPER = ROOT / "logic/backup_task_identity.py"
PBS = ROOT / "sensor/pbs.py"
NODE = ROOT / "sensor/node.py"

spec = importlib.util.spec_from_file_location("backup_task_identity_under_test", HELPER)
assert spec and spec.loader
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class TestBackupVmid(unittest.TestCase):
    def test_numeric_task_id_for_pbs_vm(self):
        self.assertEqual(helper.extract_backup_vmid({"id": "112"}), "112")

    def test_upid_worker_id(self):
        self.assertEqual(helper.extract_backup_vmid({
            "upid": "UPID:proxmox:00006D7A:000991A1:6919F670:vzdump:106:root@pam:"
        }), "106")

    def test_numeric_vmid_from_parsed_task(self):
        self.assertEqual(helper.extract_backup_vmid({"vmid": "112", "id": "backup"}), "112")

    def test_unknown_group_job_is_not_misidentified(self):
        for item in ({"id": 0, "upid": "UPID:proxmox:aaa:bbb:ccc:vzdump:0:root@pam:"},
                     {"upid": "UPID:proxmox:aaa:bbb:ccc:vzdump::root@pam:"},
                     {"id": "backup", "upid": ""}):
            self.assertEqual(helper.extract_backup_vmid(item), "unknown")

    def test_legacy_task_path(self):
        self.assertEqual(helper.extract_backup_vmid({"upid": "job/ct/106:backup"}), "106")

    def test_recent_task_publishes_debug_identifiers(self):
        source = NODE.read_text(encoding="utf-8")
        self.assertIn('"id": task.get("id"),', source)
        self.assertIn('"upid": task.get("upid"),', source)


class TestBackupTime(unittest.TestCase):
    @staticmethod
    def formatter():
        """Compile only the real production helper; no HA import needed."""
        module = ast.parse(PBS.read_text(encoding="utf-8"))
        fn = next(n for n in module.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_format_utc_timestamp")
        date_util = SimpleNamespace(
            utc_from_timestamp=lambda v: datetime.fromtimestamp(v, timezone.utc),
            as_local=lambda v: v.astimezone(ZoneInfo("Europe/Bratislava")),
        )
        scope = {"dt_util": date_util}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                     str(PBS), "exec"), scope)
        return scope["_format_utc_timestamp"]

    def test_cet_winter(self):
        value = datetime(2026, 11, 4, 2, 10, 50, tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.formatter()(value), "04/11/2026 03:10:50")

    def test_cest_summer(self):
        value = datetime(2026, 7, 4, 2, 10, 50, tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.formatter()(value), "04/07/2026 04:10:50")

    def test_machine_readable_epoch_attribute(self):
        self.assertIn('"last_backups_per_resource_epoch"', PBS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
