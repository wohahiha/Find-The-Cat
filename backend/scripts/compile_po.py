"""
简易 PO → MO 编译脚本

用途：在缺少 GNU gettext 的环境下，编译 locale/zh_Hans/LC_MESSAGES/django.po (或 djangojs.po) 到 .mo

使用：
python scripts/compile_po.py locale/zh_Hans/LC_MESSAGES/django.po
"""

from __future__ import annotations

import sys
import struct
from pathlib import Path


def compile_po(po_path: Path) -> Path:
    mo_path = po_path.with_suffix(".mo")
    entries: list[tuple[str, str | None]] = []
    msgid: str | None = None
    msgstr: str | None = None

    for line in po_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("msgid "):
            if msgid is not None:
                entries.append((msgid, msgstr))
            msgid = line[6:].strip().strip('"')
            msgstr = None
        elif line.startswith("msgstr "):
            msgstr = line[7:].strip().strip('"')
        elif line.startswith('"') and msgstr is not None:
            msgstr += line.strip().strip('"')
        elif line.startswith('"') and msgid is not None and msgstr is None:
            msgid += line.strip().strip('"')
    if msgid is not None:
        entries.append((msgid, msgstr))

    ids = b""
    strs = b""
    offsets = []
    for mid, mstr in entries:
        mid_b = mid.encode("utf-8") if mid is not None else b""
        mstr_b = (mstr or "").encode("utf-8")
        offsets.append((len(mid_b), len(mstr_b), len(ids), len(strs)))
        ids += mid_b + b"\0"
        strs += mstr_b + b"\0"

    keystart = 7 * 4 + 16 * len(entries)
    valuestart = keystart + len(ids)

    out = []
    out.append(struct.pack("I", 0x950412de))  # magic
    out.append(struct.pack("I", 0))  # version
    out.append(struct.pack("I", len(entries)))  # number of entries
    out.append(struct.pack("I", 7 * 4))  # start of key index
    out.append(struct.pack("I", 7 * 4 + 8 * len(entries)))  # start of value index
    out.append(struct.pack("I", 0))  # size/hash
    out.append(struct.pack("I", 0))  # hash offset

    for length, _, offset, _ in offsets:
        out.append(struct.pack("II", length, keystart + offset))
    for _, length, _, offset in offsets:
        out.append(struct.pack("II", length, valuestart + offset))
    out.append(ids)
    out.append(strs)
    mo_path.write_bytes(b"".join(out))
    return mo_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/compile_po.py <path/to/file.po>")
        sys.exit(1)
    path = Path(sys.argv[1]).resolve()
    result = compile_po(path)
    print(f"Wrote: {result}")
