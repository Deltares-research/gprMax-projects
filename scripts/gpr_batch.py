import argparse
import subprocess
import sys
from pathlib import Path
import shutil


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input_file")
    p.add_argument("mode", nargs="?", default="1")
    args = p.parse_args()

    input_file = Path(args.input_file).resolve()
    stem = input_file.with_suffix("")
    is_geometry = args.mode.lower() == "geometry"
    runs = 1 if is_geometry else int(args.mode)
    jobs = runs + 1
    outputs = input_file.parent.parent / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    mpiexec = Path(sys.executable).resolve().parent / "Library" / "bin" / "mpiexec.exe"

    cmd = [sys.executable, "-m", "gprMax", args.input_file, "-n", str(runs)]
    if is_geometry:
        cmd.append("--geometry-only")
    elif runs > 1:
        mpi_cmd = ["-m", "gprMax", args.input_file, "-n", str(runs), "-mpi", str(jobs)]
        if mpiexec.exists():
            cmd = [str(mpiexec), "-n", "1", sys.executable, *mpi_cmd]
        else:
            cmd = [sys.executable, *mpi_cmd]
    run(cmd)

    if is_geometry:
        target = outputs / f"{stem.name}.vti"
        for candidate in (Path("geom.vti"), input_file.parent / "geom.vti"):
            if candidate.exists():
                if target.exists():
                    target.unlink()
                shutil.move(str(candidate), str(target))
                break
        return

    merge_cmd = [sys.executable, "-m", "tools.outputfiles_merge", str(stem), "--remove-files"]
    run(merge_cmd)

    merged = stem.parent / f"{stem.name}_merged.out"
    if merged.exists():
        shutil.move(str(merged), str(outputs / merged.name))

    for leftover in stem.parent.glob(f"{stem.name}*.out"):
        if leftover.exists() and not leftover.name.endswith("_merged.out"):
            leftover.unlink()


if __name__ == "__main__":
    main()
