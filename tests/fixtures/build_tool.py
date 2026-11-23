"""Record setup commands and provide their file outputs without downloading/building."""

import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(os.environ["MASKRF_TEST_ROOT"]).resolve()
tool, *arguments = sys.argv[1:]


def local(path):
    path = Path(path).resolve()
    assert path.is_relative_to(ROOT), f"Unexpected write outside test directory: {path}"
    return path


local(Path.cwd())
with Path(os.environ["MASKRF_TEST_CALLS"]).open("a") as log:
    log.write(
        json.dumps({"tool": tool, "arguments": arguments, "cwd": str(Path.cwd())})
        + "\n"
    )

if tool == "git":
    if arguments[0] == "clone":
        source = local(arguments[-1])
        (source / ".git").mkdir(parents=True)
        for component in ("fparser", "CSXCAD", "openEMS"):
            (source / component / "python").mkdir(parents=True)
    else:
        print("d0d2e8dad8a02388f1919bbcdd29a67e9199dd2c")
elif tool == "apt-get":
    archives = local("apt/cache/archives")
    archives.mkdir(parents=True, exist_ok=True)
    (archives / "test.deb").touch()
elif tool == "dpkg-deb":
    prefix = local(arguments[-1])
    (prefix / "usr/lib/x86_64-linux-gnu").mkdir(parents=True, exist_ok=True)
elif tool == "cmake":
    if arguments[0] in ("--build", "--install"):
        build = local(arguments[1])
        prefix = local((build / "install-prefix").read_text())
        if arguments[0] == "--install":
            (prefix / "lib").mkdir(parents=True, exist_ok=True)
            (prefix / "lib" / f"lib{build.name}.so").touch()
    else:
        build = local(arguments[arguments.index("-B") + 1])
        prefix = local(
            next(
                value.split("=", 1)[1]
                for value in arguments
                if value.startswith("-DCMAKE_INSTALL_PREFIX=")
            )
        )
        build.mkdir(parents=True)
        (build / "install-prefix").write_text(str(prefix))
elif tool == "uv":
    if arguments[0] == "venv":
        binary = local(arguments[-1]) / "bin/python"
        binary.parent.mkdir(parents=True)
        binary.touch()
        binary.chmod(0o755)
    elif arguments[0] == "run":
        if "setup.py" in arguments:
            dist = local("dist")
            dist.mkdir(exist_ok=True)
            (dist / f"{Path.cwd().parent.name}-test.whl").touch()
        else:
            index = next(
                i
                for i, argument in enumerate(arguments)
                if argument.endswith("repair_library_links.py")
            )
            sys.argv = arguments[index:]
            runpy.run_path(sys.argv[0], run_name="__main__")
    elif "-r" in arguments:
        assert Path(arguments[arguments.index("-r") + 1]).is_file()
    else:
        for argument in arguments:
            if argument.endswith(".whl"):
                assert local(argument).is_file()
else:
    raise AssertionError(f"Unexpected build command: {tool}")
