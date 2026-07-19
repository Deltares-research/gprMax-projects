import argparse
import os
import re
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


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "run"


def load_run_config(path: Path) -> dict:
    if not path.exists():
        die(f"Run config not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        die(f"Invalid run config format: {path}")
    return data


def resolve_template_path(template_value: str, repo_root: Path, config_path: Path) -> Path:
    t = Path(template_value)
    candidates = [t] if t.is_absolute() else [repo_root / t, config_path.parent / t]
    for c in candidates:
        if c.exists():
            return c
    die(f"Template not found: {template_value}")


def render_template(template: str, row: dict[str, str], settings: dict) -> str:
    mat_file = row["material_file"].strip()
    freq_mhz = float(settings.get("freq_mhz", 100.0))
    # gprMax expects Hz, keep output readable as e6 from MHz input.
    freq_hz_expr = f"{freq_mhz:g}e6"

    # Preferred user-facing unit in TOML is ns; fallback supports legacy seconds key.
    if "time_window_ns" in settings:
        time_window_ns = float(settings["time_window_ns"])
    else:
        time_window_ns = float(settings.get("time_window", 3.0e-7)) * 1e9
    time_window_s_expr = f"{time_window_ns:g}e-9"

    geometry_view_enabled = bool(settings.get("geometry_view", False))
    geometry_view_mode = str(settings.get("geometry_view_mode", "n")).lower().strip()
    if geometry_view_mode not in {"n", "f"}:
        die("geometry_view_mode must be either 'n' or 'f'")
    geometry_view_line = (
        f"geometry_view: 0 0 0 50 6.0 0.01 0.01 0.01 geom {geometry_view_mode}"
        if geometry_view_enabled
        else "geometry_view disabled"
    )

    values: dict[str, str] = {
        "GEOMETRY_FILE": row["geometry_file"].strip(),
        "MATERIAL_FILE": mat_file,
        "MATERIAL_BASE": Path(mat_file).stem,
        "FREQ_MHZ": f"{freq_mhz:g}",
        "FREQ_HZ": freq_hz_expr,
        "TIME_WINDOW_S": time_window_s_expr,
        "X_SRC": str(settings.get("x_src", 1.0)),
        "Y_SRC": str(settings.get("y_src", 1.0)),
        "Z_SRC": str(settings.get("z_src", 0.0)),
        "RX_OFFSET": str(settings.get("rx_offset", 1.0)),
        "STEP": str(settings.get("step", 1.0)),
        "WAVE_FIELD": "True" if bool(settings.get("wave_field", False)) else "False",
        "DT_SNAP_NS": str(settings.get("dt_snap_ns", 2)),
        "SNAPSHOT_COUNT": str(settings.get("snapshot_count", 24)),
        "GEOMETRY_VIEW_LINE": geometry_view_line,
    }

    content = template
    for k, v in values.items():
        content = content.replace(f"{{{k}}}", v)
    return content


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


def run_batch(input_file: Path, runs: int, gpu: bool, output_basename: str) -> int:
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
        target = unique_destination(outputs / f"{output_basename}.out")
        shutil.move(str(merged), str(target))

    for leftover in stem.parent.glob(f"{stem.name}*.out"):
        if leftover.exists() and not leftover.name.endswith("_merged.out"):
            leftover.unlink()

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Run sequential gprMax model chain")
    p.add_argument(
        "--config",
        "--run-config",
        dest="config",
        default="wheels/models/start_test_1ascan.toml",
        help="Path to run config TOML (alias: --run-config)",
    )
    p.add_argument("--gpu", action="store_true")
    args = p.parse_args()

    run_config_path = Path(args.config)
    settings = load_run_config(run_config_path)
    run_name = sanitize_name(str(settings.get("output_prefix", run_config_path.stem)))

    gpu_enabled = args.gpu or bool(settings.get("gpu", False))

    repo = Path(__file__).resolve().parent.parent
    template_value = settings.get("template", "wheels/models/wheels.in")
    template_path = resolve_template_path(str(template_value), repo, run_config_path)

    template = template_path.read_text(encoding="utf-8")

    rows = load_rows_from_toml(settings)

    print(f"=== Chain: {len(rows)} model(s) ===\n")

    results: list[tuple[str, str]] = []
    start_time = time.time()

    for i, row in enumerate(rows, 1):
        ascans = row["ascans"].strip()
        mat_file = row["material_file"].strip()
        out_base = sanitize_name(f"{run_name}__m{i:03d}__a{ascans}")

        content = render_template(template, row, settings)

        temp_in = repo / "wheels" / "models" / f"_{out_base}_.in"
        temp_in.write_text(content, encoding="utf-8")

        print(f"[{i}/{len(rows)}] Running: {mat_file} ({ascans} A-scans)")
        print(f"      Input: {temp_in.name}")

        exit_code = run_batch(temp_in, int(ascans), gpu_enabled, out_base)
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
