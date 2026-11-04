"""Extract guest IDs from Proxmox backup tasks without guessing group jobs."""

from __future__ import annotations

import re
from typing import Any


def extract_backup_vmid(task: dict[str, Any]) -> str:
    """Return VMID for a guest-specific task, else 'unknown'.

    Proxmox node task data may include a numeric ``id`` and/or a VZDump UPID
    of the form ``UPID:<node>:<pid>:<pstart>:<start>:vzdump:<vmid>:<user>:``.
    Group-wide tasks sometimes have no VMID or use 0; do not infer coverage.
    """
    for key in ("vmid", "id"):
        candidate = task.get(key)
        if candidate is not None:
            value = str(candidate).strip()
            if value.isascii() and value.isdigit() and int(value) > 0:
                return str(int(value))

    upid = str(task.get("upid") or "")
    parts = upid.split(":")
    if len(parts) >= 8 and parts[0] == "UPID" and parts[5] == "vzdump":
        worker_id = parts[6]
        if worker_id.isascii() and worker_id.isdigit() and int(worker_id) > 0:
            return str(int(worker_id))

    # Retain compatibility with unconventional task IDs containing vm/ or ct/.
    match = re.search(r"(?:^|[/:])(?:vm|ct)/(\d+)(?=$|[/:])", upid)
    if match and int(match.group(1)) > 0:
        return str(int(match.group(1)))
    return "unknown"
