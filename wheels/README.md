# Wheels gprMax project

This folder contains the first `gprmax-projects` model setup for the Dutch `wielen` / levee-breach geometry.

## Folder roles

- `models/` contains the gprMax `.in` file and material file.
- `geometries/` contains generated HDF5 geometry and material-ID mapping files.
- `scripts/` contains Python scripts used to regenerate geometry or process results.
- `data/` contains source interpretation inputs, such as the traced PNG.
- `outputs/` is for gprMax outputs from `pixi run wheels ...` and is ignored by Git.
- `figures/` contains previews and figures for checking/reporting.

## Current generated files

- `models/wheels.in`
- `models/materials.txt`
- `geometries/wheel_geometry.h5`
- `geometries/wheel_material_id_mapping.csv`
- `figures/wheel_geometry_preview.png`
- `data/traced_section_boundaries_flat_surface_v2.png`

The values in `models/materials.txt` are placeholders. Edit the electromagnetic properties before running a scientific simulation.

## Runs

- `pixi run wheels`
- `pixi run wheels -- 49`
- `pixi run wheels -- geometry`

## View outputs

- Plot merged B-scan: `pixi run python -m tools.plot_Bscan wheels/outputs/wheels_merged.out Ez`
- Change component as needed: `Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`

## DT1 export

- Python converter script: `scripts/outputfile_converter.py`
- Pixi task entrypoint: `pixi run convert -- ...`

Examples:

- DT1: `pixi run convert -- wheels/outputs/wheels_merged.out --format dt1`
- RD3: `pixi run convert -- wheels/outputs/wheels_merged.out --format rd3`
- DZT: `pixi run convert -- wheels/outputs/wheels_merged.out --format dzt`
- IPRB: `pixi run convert -- wheels/outputs/wheels_merged.out --format iprb`

Pixi argument separator:

- Keep `--` after `pixi run convert` so arguments are passed to the converter script (not parsed by Pixi).

Notes:

- The converter always exports all three components: `Ex`, `Ey`, `Ez`.
- Default behavior mirrors MATLAB script: transpose receiver matrix, resample to 1024 samples, then scale to 16-bit.
- Output names include component suffix, e.g. `wheels_merged_ex.dt1`, `wheels_merged_ey.dt1`, `wheels_merged_ez.dt1`.
- Fixed metadata defaults in script: centre frequency `250 MHz`, antenna separation `0.5 m`, trace interval `0.1 m`.
