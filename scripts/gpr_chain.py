import argparse
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import psutil


def run(cmd: list[str], env: dict | None = None) -> int:
    return subprocess.run(cmd, capture_output=False, env=env).returncode


def die(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{i:03d}{path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def load_run_config(path: Path) -> dict:
    if not path.exists():
        die(f"Run config not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        die(f"Invalid run config format: {path}")
    return data


def load_rows_from_toml(settings: dict) -> list[dict[str, str]]:
    material_files = settings.get("material_files")
    if material_files is not None:
        if not isinstance(material_files, list) or not material_files:
            die("material_files must be a non-empty list")
        try:
            geometry_file = str(settings["geometry_file"]).strip()
            ascans = str(settings["ascans"]).strip()
        except KeyError as e:
            die(f"Missing key {e!s} for compact material sweep mode")

        material_dir = str(settings.get("material_dir", "")).strip()
        rows: list[dict[str, str]] = []
        for i, raw in enumerate(material_files, 1):
            material_file = str(raw).strip()
            if not material_file:
                die(f"Empty material file entry at index {i}")
            # Join with material_dir only for bare filenames.
            if material_dir and "/" not in material_file and "\\" not in material_file:
                material_file = f"{material_dir.rstrip('/\\')}/{material_file}"
            rows.append(
                {
                    "geometry_file": geometry_file,
                    "material_file": material_file,
                    "ascans": ascans,
                }
            )
        return rows

    models = settings.get("models")
    if not isinstance(models, list) or not models:
        die("Run config must include either material_files or at least one [[models]] entry")

    rows: list[dict[str, str]] = []
    for i, model in enumerate(models, 1):
        if not isinstance(model, dict):
            die(f"Invalid model entry at index {i}")
        try:
            geometry_file = str(model["geometry_file"]).strip()
            material_file = str(model["material_file"]).strip()
            ascans = str(model["ascans"]).strip()
        except KeyError as e:
            die(f"Missing key {e!s} in [[models]] entry {i}")
        rows.append(
            {
                "geometry_file": geometry_file,
                "material_file": material_file,
                "ascans": ascans,
            }
        )
    return rows


def run_batch(input_file: Path, runs: int, gpu: bool) -> int:
    stem = input_file.with_suffix("")
    outputs = input_file.parent.parent / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    physical_cores = psutil.cpu_count(logical=False) or 1
    mpi_tasks = max(2, physical_cores + 1)
    env = {**os.environ, "OMP_NUM_THREADS": "1"}

    if gpu and runs > 1:
        for i in range(1, runs + 1):
            code = run(
                [
                    sys.executable,
                    "-m",
                    "gprMax",
                    str(input_file),
                    "-n",
                    str(runs),
                    "-task",
                    str(i),
                    "-gpu",
                ],
                env=env,
            )
            if code != 0:
                return code
    elif runs > 1:
        code = run(
            [
                "mpiexec",
                "-n",
                str(mpi_tasks),
                sys.executable,
                "-m",
                "gprMax",
                str(input_file),
                "-n",
                str(runs),
                "--mpi-no-spawn",
            ],
            env=env,
        )
        if code != 0:
            return code
    else:
        cmd = [sys.executable, "-m", "gprMax", str(input_file), "-n", str(runs)]
        if gpu:
            cmd.append("-gpu")
        code = run(cmd, env=env)
        if code != 0:
            return code

    if run([sys.executable, "-m", "tools.outputfiles_merge", str(stem), "--remove-files"], env=env) != 0:
        return 1

    merged = stem.parent / f"{stem.name}_merged.out"
    if merged.exists():
        shutil.move(str(merged), str(unique_destination(outputs / merged.name)))

    for leftover in stem.parent.glob(f"{stem.name}*.out"):
        if leftover.exists() and not leftover.name.endswith("_merged.out"):
            leftover.unlink()

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Run sequential gprMax model chain")
    p.add_argument("--run-config", default="wheels/models/run_config.toml")
    p.add_argument("--gpu", action="store_true")
    args = p.parse_args()

    settings = load_run_config(Path(args.run_config))

    gpu_enabled = args.gpu or bool(settings.get("gpu", False))

    repo = Path(__file__).resolve().parent.parent
    template_value = settings.get("template", "wheels/models/wheels-chain.in")
    template_path = repo / template_value
    if not template_path.exists():
        die(f"Template not found: {template_path}")

    template = template_path.read_text(encoding="utf-8")

    rows = load_rows_from_toml(settings)

    print(f"=== Chain: {len(rows)} model(s) ===\n")

    results: list[tuple[str, str]] = []
    start_time = time.time()

    for i, row in enumerate(rows, 1):
        geom_file = row["geometry_file"].strip()
        mat_file = row["material_file"].strip()
        ascans = row["ascans"].strip()
        mat_base = Path(mat_file).stem

        content = template.replace("{GEOMETRY_FILE}", geom_file)
        content = content.replace("{MATERIAL_FILE}", mat_file)
        content = content.replace("{MATERIAL_BASE}", mat_base)

        temp_in = repo / "wheels" / "models" / f"_chain_temp_{i:03d}_.in"
        temp_in.write_text(content, encoding="utf-8")

        print(f"[{i}/{len(rows)}] Running: {mat_file} ({ascans} A-scans)")
        print(f"      Input: {temp_in.name}")

        exit_code = run_batch(temp_in, int(ascans), gpu_enabled)
        if exit_code == 0:
            status = "OK"
            results.append((mat_file, "OK"))
        else:
            status = "FAILED"
            results.append((mat_file, "FAILED"))
        print(f"      {status}\n")

        if temp_in.exists():
            temp_in.unlink()

    elapsed = time.time() - start_time
    passed = sum(1 for _, state in results if state == "OK")
    failed = len(results) - passed

    print(f"\n=== Chain Complete ===")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")

    if failed > 0:
        print(f"\nFailed models:")
        for mat, state in results:
            if state == "FAILED":
                print(f"  - {mat}")


if __name__ == "__main__":
    main()
