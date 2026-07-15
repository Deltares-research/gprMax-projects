"""Run a chain of gprMax models sequentially from a config file.

Configuration is read from wheels/models/chain_config.csv with columns:
  geometry_file, material_file, ascans

For each row, the template wheels/models/wheels-chain.in is instantiated,
run via gpr_batch.py, and output merged into the outputs/ directory.

Usage:
    python scripts/gpr_chain.py [config_file]

Default config: wheels/models/chain_config.csv
"""

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path


def run(cmd: list[str]) -> int:
    """Run command, return exit code (0 on success)."""
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def main() -> None:
    p = argparse.ArgumentParser(description="Run sequential gprMax model chain")
    p.add_argument("--config", default="wheels/models/chain_config.csv",
                   help="Path to chain config CSV (default: wheels/models/chain_config.csv)")
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    repo = Path(__file__).resolve().parent.parent
    template_path = repo / "wheels" / "models" / "wheels-chain.in"
    
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        sys.exit(1)

    # Read template
    with open(template_path) as f:
        template = f.read()

    # Read config
    rows = []
    with open(config_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"ERROR: No rows in config {config_path}")
        sys.exit(1)

    print(f"=== Chain: {len(rows)} model(s) ===\n")

    results = []
    start_time = time.time()

    for i, row in enumerate(rows, 1):
        geom_file = row["geometry_file"].strip()
        mat_file = row["material_file"].strip()
        ascans = row["ascans"].strip()
        
        # Extract basename for title and output naming
        mat_base = Path(mat_file).stem
        
        # Substitute placeholders
        content = template.replace("{GEOMETRY_FILE}", geom_file)
        content = content.replace("{MATERIAL_FILE}", mat_file)
        content = content.replace("{MATERIAL_BASE}", mat_base)
        
        # Create temp .in file
        temp_in = repo / "wheels" / "models" / f"_chain_temp_{i:03d}.in"
        with open(temp_in, "w") as f:
            f.write(content)
        
        print(f"[{i}/{len(rows)}] Running: {mat_file} ({ascans} A-scans)")
        print(f"      Input: {temp_in.name}")
        
        # Run via gpr_batch.py
        cmd = [sys.executable, "scripts/gpr_batch.py", str(temp_in), ascans]
        exit_code = run(cmd)
        
        if exit_code == 0:
            status = "✓ OK"
            results.append((mat_file, "OK"))
        else:
            status = "✗ FAILED"
            results.append((mat_file, "FAILED"))
        
        print(f"      {status}\n")
        
        # Clean up temp file
        if temp_in.exists():
            temp_in.unlink()

    # Summary
    elapsed = time.time() - start_time
    passed = sum(1 for _, s in results if s == "OK")
    failed = len(results) - passed
    
    print(f"\n=== Chain Complete ===")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print(f"\nFailed models:")
        for mat, status in results:
            if status == "FAILED":
                print(f"  - {mat}")


if __name__ == "__main__":
    main()
