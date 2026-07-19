# gprMax-projects

This repository runs gprMax models with one command and stores outputs in `wheels/outputs`.

## First-time setup (Windows)

1. Install Pixi: https://pixi.sh/latest/
2. Clone this repository.
3. Clone `gprMax` as a sibling folder named `gprMax`.

Expected folder layout:

```text
<parent folder>/
  gprMax/
  gprMax-projects/
```

The Pixi environment in this repository expects `../gprMax` to exist.

## First run (guaranteed quick test)

From the repository root:

```powershell
pixi run wheels
```

This runs the default starter config:

- `wheels/models/start_test_1ascan.toml`

You should see a successful summary ending with:

- `Passed: 1/1`

## Main run configs

- `wheels/models/start_test_1ascan.toml` - fastest sanity check (default)
- `wheels/models/3models_197ascans.toml` - 3-material scenario, 197 A-scans
- `wheels/models/material_sweep_1ascan.toml` - full material sweep, 1 A-scan each

Run a specific config:

```powershell
pixi run wheels -- --config wheels/models/3models_197ascans.toml
pixi run wheels -- --config wheels/models/material_sweep_1ascan.toml
```

## Where results are written

Final `.out` files are moved to:

- `wheels/outputs`

Names follow this pattern:

- `<output_prefix>__mNNN__aASCANS.out`

Example:

- `start_test_1ascan__m001__a1.out`

If a file with the same name already exists, a suffix is added automatically (`_001`, `_002`, ...).

## Plot a result

Plot any output file and choose a field component (`Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`):

```powershell
pixi run plot -- wheels/outputs/start_test_1ascan__m001__a1.out Ez
```

Plot the newest output automatically:

```powershell
$latest = Get-ChildItem wheels/outputs/*.out | Sort-Object LastWriteTime -Descending | Select-Object -First 1
pixi run plot -- $latest.FullName Ez
```

## Convert a result (DT1/RD3/DZT/IPRB)

```powershell
pixi run convert -- wheels/outputs/start_test_1ascan__m001__a1.out --format dt1
```

Supported formats:

- `dt1`
- `rd3`
- `dzt`
- `iprb`

## GPU usage (optional)

GPU runs use NVIDIA CUDA through gprMax.

### CUDA requirements

1. NVIDIA GPU with CUDA support.
2. Recent NVIDIA driver installed.
3. CUDA Toolkit installed (from https://developer.nvidia.com/cuda-downloads).

Recommended Windows install path:

- `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X`

If needed, set the environment variable:

- `CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X`

Restart terminal/VS Code after driver/toolkit changes.

### Enable GPU in a run config

Set `gpu = true` in the TOML you want to run, then run normally:

```powershell
pixi run wheels
```

or

```powershell
pixi run wheels -- --config wheels/models/3models_197ascans.toml
```

### Confirm GPU is actually used

In terminal output, look for lines like:

- `GPU(s) detected: ...`
- `GPU solving using: ...`

If those lines are missing, the run used CPU.

### Common GPU issues

1. `TOMLDecodeError` after editing config:
  - Use lowercase booleans only: `true` / `false`.
2. CUDA not detected:
  - Reinstall/update NVIDIA driver.
  - Verify CUDA Toolkit installation.
  - Reopen terminal/VS Code.
3. GPU run slower than expected:
  - Very small models may not benefit from GPU.
  - Test with larger A-scan counts.
