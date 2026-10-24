"""
Print the Nuitka options pointing to the Tcl/Tk script libraries.
Tcl/Tk 9 in uv's standalone Python keep them zipped inside their DLLs, where Nuitka does not look:
extract them to the given folder. Prints nothing when the libraries are regular folders.
"""

import sys
import zipfile
from pathlib import Path

LIBRARIES = {"tcl_library": "--tcl-library-dir", "tk_library": "--tk-library-dir"}


def main(output: Path):
    options = []
    for dll in sorted(Path(sys.base_prefix, "DLLs").glob("tcl*.dll")):
        if not zipfile.is_zipfile(dll):
            continue
        with zipfile.ZipFile(dll) as archive:
            for name, option in LIBRARIES.items():
                members = [member for member in archive.namelist() if member.startswith(f"{name}/")]
                if members:
                    archive.extractall(output, members)
                    # Quoted and with forward slashes: the output is pasted into a shell command
                    options.append(f'{option}="{(output / name).as_posix()}"')
    print(" ".join(options))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
