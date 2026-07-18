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

- `pixi run wheels` - run batch chain defined in `wheels/models/run_config.toml`
- `pixi run convert -- any/path/to/file.out --format dt1` - export Ex/Ey/Ez to DT1/HD
- `pixi run plot -- any/path/to/file.out Ez` - plot B-scan for a field component (`Ex`, `Ey`, `Ez`, `Hx`, `Hy`, `Hz`)

Notes:

- Keep `--` after task names when passing arguments.
- For plotting, use a field component (for example `Ez`), not `--format dt1`.

## GPU Acceleration (Optional)

To accelerate simulations with NVIDIA GPU:

1. **Install CUDA Toolkit** — Download from [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
   - Select your OS and architecture
   - During installation, select only: CUDA Toolkit + NVIDIA Drivers
   - Note the installation path (default: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X`)

2. **Set CUDA_PATH environment variable** (Windows)
   - System Properties → Environment Variables
   - Add new variable: `CUDA_PATH = C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\vXX.X`
   - Restart your terminal/IDE

3. **Run with GPU** — Set `gpu = true` in `wheels/models/run_config.toml`, then run:
   ```powershell
   pixi run wheels
   ```

GPU acceleration can significantly reduce runtime depending on model size and hardware.

## Field Components Explained

GPRMax outputs six electromagnetic field components:

**Electric Field (E-field):**
- `Ex`, `Ey`, `Ez` — Electric field in x, y, z directions (units: V/m)

**Magnetic Field (H-field):**
- `Hx`, `Hy`, `Hz` — Magnetic field in x, y, z directions (units: A/m)

**For a vertical Hertzian dipole** (z-polarized, as in your models):
- **Ez is strong** — The dipole orientation directly radiates in the z-direction
- **Hy is strong** — Magnetic field perpendicular to the electric dipole, follows right-hand rule
- Ex, Ey, Hx, Hz are typically much weaker

This is standard electromagnetic theory: a vertical antenna primarily radiates vertical electric field with orthogonal magnetic field. Your models correctly show **Ez and Hy** as the dominant components, which is expected behavior.
