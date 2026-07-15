import argparse
import os
import subprocess
import sys
from pathlib import Path
import shutil

import psutil


def run(cmd: list[str], env: dict | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input_file")
    p.add_argument("mode", nargs="?", default="1")
    p.add_argument("--omp-threads", type=int, default=1,
                   help="OpenMP threads per worker (default: 1)")
    args = p.parse_args()

    input_file = Path(args.input_file).resolve()
    stem = input_file.with_suffix("")
    is_geometry = args.mode.lower() == "geometry"
    runs = 1 if is_geometry else int(args.mode)
    outputs = input_file.parent.parent / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    physical_cores = psutil.cpu_count(logical=False) or 1
    omp_threads = args.omp_threads
    workers = max(1, physical_cores // omp_threads)
    mpi_tasks = workers + 1  # 1 master + N workers

    env = {**os.environ, "OMP_NUM_THREADS": str(omp_threads)}

    cmd = [sys.executable, "-m", "gprMax", args.input_file, "-n", str(runs)]
    if is_geometry:
        cmd.append("--geometry-only")
    elif runs > 1:
        # Use mpiexec with --mpi-no-spawn (Windows-friendly, no spawn mechanism)
        cmd = ["mpiexec", "-n", str(mpi_tasks), sys.executable, "-m", "gprMax", 
               args.input_file, "-n", str(runs), "--mpi-no-spawn"]
    run(cmd, env=env)

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
    run(merge_cmd, env=env)

    merged = stem.parent / f"{stem.name}_merged.out"
    if merged.exists():
        shutil.move(str(merged), str(outputs / merged.name))

    for leftover in stem.parent.glob(f"{stem.name}*.out"):
        if leftover.exists() and not leftover.name.endswith("_merged.out"):
            leftover.unlink()


if __name__ == "__main__":
    main()
