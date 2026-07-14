# gprMax-projects

`gprMax-projects` is a dedicated repository for managing gprMax modelling studies without mixing project-specific files into the upstream `gprMax` source tree.

## Repository split

- The upstream `gprMax` source code lives in a separate repository at `../gprMax`
- This repository contains modelling projects and shared runner scripts
- Keeping the repositories separate means the upstream `gprMax` checkout stays clean and can be updated with `git pull`

## Shared Pixi environment

All projects in this repository use a single Pixi environment defined in the repository root `pyproject.toml`.
The Pixi configuration is embedded directly in `pyproject.toml`; there is no separate `pixi.toml` file.

The workspace is configured for:

- `win-64`

and uses the `conda-forge` channel.

## Local editable gprMax dependency

The Pixi environment includes `gprMax` as an editable local PyPI dependency pointing to `../gprMax`.
That keeps the modelling workspace decoupled from the upstream source checkout while still allowing local development against the sibling repository.

## Projects

The first modelling project in this repository is `wheels`.
It includes folders for models, generated geometries, scripts, outputs, and figures.

## Pixi tasks

Common tasks are defined in `pyproject.toml`:

- `pixi run wheels` - run one scan, merge outputs, remove per-scan files
- `pixi run wheels -- 49` - run 49 scans with MPI (`jobs = 50`), merge outputs, remove per-scan files
- `pixi run wheels -- geometry` - geometry-only run
- `pixi run convert -- any/path/to/file.out --format dt1` - export Ex/Ey/Ez to DT1/HD
- `pixi run plot -- any/path/to/file.out Ez` - plot B-scan for a field component (`Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`)

Notes:

- Keep `--` after task names when passing arguments.
- For plotting, use a field component (for example `Ez`), not `--format dt1`.
