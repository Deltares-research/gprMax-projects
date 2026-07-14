from pathlib import Path


def figure_path(filename: str, root: str | Path = "figures") -> Path:
    return Path(root) / filename
