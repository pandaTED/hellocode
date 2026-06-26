"""Build script for compiling HelloCode with Nuitka."""

import subprocess
import sys
import os
from pathlib import Path


def build():
    """Build hellocode executable with Nuitka."""
    project_root = Path(__file__).parent

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--output-dir=dist",
        "--output-filename=hellocode.exe" if os.name == "nt" else "hellocode",
        "--include-package=hellocode",
        "--include-package-data=hellocode",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=test",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=ruff",
        "--nofollow-import-to=mypy",
        "--nofollow-import-to=black",
        "--nofollow-import-to=isort",
        "--nofollow-import-to=flake8",
        "--nofollow-import-to=pylint",
        "--nofollow-import-to=IPython",
        "--nofollow-import-to=notebook",
        "--nofollow-import-to=jupyter",
        "--nofollow-import-to=numpy",
        "--nofollow-import-to=pandas",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=PIL",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=tensorflow",
        "--nofollow-import-to=torch",
        "--nofollow-import-to=sklearn",
        "--python-flag=-m",
        "hellocode",
    ]

    print("Building HelloCode with Nuitka...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        print("-" * 60)
        print("Build successful!")
        print(f"Executable location: {project_root / 'dist'}")
    else:
        print("-" * 60)
        print(f"Build failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    build()
