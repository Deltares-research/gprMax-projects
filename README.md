# gprMax-projects

`gprMax-projects` is a dedicated repository for managing gprMax modelling studies without mixing project-specific files into the upstream `gprMax` source tree.

## Repository split

- The upstream `gprMax` source code lives in a separate repository at `../gprMax`
- This repository contains only modelling projects, shared utilities, and project templates
- Keeping the repositories separate means the upstream `gprMax` checkout stays clean and can be updated with `git pull`

## Shared Pixi environment

All projects in this repository use a single Pixi environment defined in the repository root `pyproject.toml`.
The Pixi configuration is embedded directly in `pyproject.toml`; there is no separate `pixi.toml` file.

The workspace is configured for:

- `linux-64`
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

- `pixi run build` - build the sibling `../gprMax` source into a wheel
- `pixi run install` - install `../gprMax` in editable mode
- `pixi run setup` - run both the build and install tasks
- `pixi run wheels_geom` - generate the wheels geometry scaffold
- `pixi run wheels_run` - run the wheels model with `python -m gprMax`
- `pixi run wheels` - generate geometry and then run the wheels model
- `pixi run shell` - open a Pixi shell
