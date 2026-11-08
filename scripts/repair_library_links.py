"""Resolve dev-package links whose runtime library was already installed on Ubuntu."""

import os
from pathlib import Path

for f in Path("native/usr/lib/x86_64-linux-gnu").iterdir():
    if f.is_symlink() and not f.exists():
        src = Path("/usr/lib/x86_64-linux-gnu") / Path(os.readlink(f)).name
        if src.exists():
            f.unlink()
            f.symlink_to(src)
            print(f, "->", src)
