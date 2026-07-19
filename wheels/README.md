# Wheels project

This folder contains model inputs, material parameter files, geometry, and outputs for the wheels gprMax runs.

## Folder overview

- `models/` run configs (`.toml`) and the shared input template (`wheels.in`)
- `materials/` material definition files used by runs
- `geometries/` geometry HDF5 files
- `outputs/` generated `.out` files
- `scripts/` helper scripts for geometry and data tasks

## First successful run

From the repository root:

```powershell
pixi run wheels
```

Default run config:

- `wheels/models/start_test_1ascan.toml`

This is a quick sanity run designed to finish fast.

## Available run configs

- `wheels/models/start_test_1ascan.toml`
- `wheels/models/3models_197ascans.toml`
- `wheels/models/material_sweep_1ascan.toml`

Run a specific config:

```powershell
pixi run wheels -- --config wheels/models/3models_197ascans.toml
pixi run wheels -- --config wheels/models/material_sweep_1ascan.toml
```

## Output files

Outputs are written to `wheels/outputs`.

Filename pattern:

- `<output_prefix>__mNNN__aASCANS.out`

## Plot

```powershell
pixi run plot -- wheels/outputs/start_test_1ascan__m001__a1.out Ez
```

Valid components: `Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`.

## Convert

```powershell
pixi run convert -- wheels/outputs/start_test_1ascan__m001__a1.out --format dt1
```

Formats: `dt1`, `rd3`, `dzt`, `iprb`.

## GPU (CUDA)

To run on NVIDIA GPU:

1. Install NVIDIA driver.
2. Install CUDA Toolkit (https://developer.nvidia.com/cuda-downloads).
3. Set `gpu = true` in the run TOML.

Then run:

```powershell
pixi run wheels
```

Check terminal output for:

- `GPU(s) detected: ...`
- `GPU solving using: ...`

If these lines do not appear, the run is on CPU.
