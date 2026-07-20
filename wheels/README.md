# Wheels project

This folder contains model inputs, material parameter files, geometry, and outputs for the wheels gprMax runs.

## Acknowledgement

This workflow uses gprMax; many thanks to the gprMax contributors.
If you publish results, please cite: Warren, C., Giannopoulos, A., & Giannakis, I. (2016), *Computer Physics Communications*, https://doi.org/10.1016/j.cpc.2016.08.020.
gprMax is licensed separately under GNU GPL v3+; see `../THIRD_PARTY_NOTICES.md`.

## Folder overview

- `models/` run configs (`.toml`) and the shared input template (`wheels.in`)
- `materials/` material definition files used by runs
- `geometries/` geometry HDF5 files
- `outputs/` generated `.out` files
- `scripts/` helper scripts for geometry and data tasks

## First successful run

From the repository root:

```
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

```
pixi run wheels -- --config wheels/models/3models_197ascans.toml
pixi run wheels -- --config wheels/models/material_sweep_1ascan.toml
```

## Output files

Outputs are written to `wheels/outputs`.

Filename pattern:

- `<output_prefix>__mNNN__aASCANS.out`

## Plot

```
pixi run plot -- wheels/outputs/start_test_1ascan__m001__a1.out Ez
```

Valid components: `Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`.

## Plot a single trace

```
pixi run plot-trace -- wheels/outputs/start_test_1ascan__m001__a1.out Ez --search-start-ns 200 --search-span-ns 100 --reflection-window-ns 65 --direct-end-ns 65 --normalize-processed
```

This plots the raw trace and its AGC version on one figure with twin y-axes, adds red direct/reflection boxes, and saves a Markdown metric report. The reflection window is centered on the first prominent envelope peak found within the bounded search interval. Use `--trace-index` for merged outputs with multiple A-scans.

For multiple single-trace outputs at once:

```
pixi run plot-trace -- --batch "wheels/outputs/*.out" Ez --search-start-ns 200 --search-span-ns 100 --reflection-window-ns 65 --direct-end-ns 65
```

This saves one `600 dpi` PNG QC plot per `.out` file and a combined Markdown summary in the outputs folder.

Keep only relevant `.out` files in this folder when running batch mode; move completed sets into subfolders as needed.

## Convert

```
pixi run convert -- wheels/outputs/start_test_1ascan__m001__a1.out --format dt1
```

Formats: `dt1`, `rd3`, `dzt`, `iprb`.

## GPU (CUDA)

To run on NVIDIA GPU:

1. Install NVIDIA driver.
2. Install CUDA Toolkit (https://developer.nvidia.com/cuda-downloads).
3. Set `gpu = true` in the run TOML.

Then run:

```
pixi run wheels
```

Check terminal output for:

- `GPU(s) detected: ...`
- `GPU solving using: ...`

If these lines do not appear, the run is on CPU.
