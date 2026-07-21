# gprMax-projects

This repository runs gprMax models with one command and stores outputs in `wheels/outputs`.

Project license: MIT (see `LICENSE`).

## Acknowledgement

This workflow uses gprMax; many thanks to the gprMax contributors.
If you publish results, please cite: Warren, C., Giannopoulos, A., & Giannakis, I. (2016), *Computer Physics Communications*, https://doi.org/10.1016/j.cpc.2016.08.020.
gprMax is licensed separately under GNU GPL v3+; see `THIRD_PARTY_NOTICES.md`.

## First-time setup (Windows)

1. Install Pixi: https://pixi.sh/latest/
2. Clone this repository.
3. Clone `gprMax` as a sibling folder named `gprMax`.

The Pixi environment in this repository expects `../gprMax` to exist.

## First run (guaranteed quick test)

From the repository root:

```
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

```
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

```
pixi run plot -- wheels/outputs/start_test_1ascan__m001__a1.out Ez
```

Plot the newest output automatically:

```
$latest = Get-ChildItem wheels/outputs/*.out | Sort-Object LastWriteTime -Descending | Select-Object -First 1
pixi run plot -- $latest.FullName Ez
```

Plot a single trace (A-scan) with QC metrics:

```
pixi run plot-trace -- wheels/outputs/start_test_1ascan__m001__a1.out Ez --search-start-ns 200 --search-span-ns 100 --reflection-window-ns 65 --direct-end-ns 65 --normalize-processed
```

This plots the raw trace in black and the AGC version in blue on a twin-y-axis figure. The script searches within `[search-start-ns, search-start-ns + search-span-ns]` for the first prominent envelope peak, builds a fixed reflection window around it, draws red boxes for the direct and reflection windows, annotates RMS values, and saves a Markdown report with the metric table next to the `.out` file.

Important interpretation limits for reflection-strength reports:

- Treat reported reflection-strength values as screening metrics, not definitive truth.
- Perform plot-level quality control for every individual trace before accepting any reported metric.
- The method assumes an isolated reflector in the chosen window.
- If reflectors are close together, multiple interfaces can fall inside the same calculation window and bias the metric.
- Example: in the wheels model near 180 m, the water table and the sand-clay interface are close enough that both can contribute within one reflection window.

Batch-process a set of single-trace outputs, save one `600 dpi` PNG per file, and write a combined Markdown summary:

```
pixi run plot-trace -- --batch "wheels/outputs/*.out" Ez --search-start-ns 200 --search-span-ns 100 --reflection-window-ns 65 --direct-end-ns 65
```

In batch mode, PNG QC plots are saved next to each `.out` file and a combined summary Markdown file is written in the same folder.

Keep only relevant `.out` files in the target outputs folder (or place completed sets in subfolders) before running batch processing.

## Convert a result (DT1/RD3/DZT/IPRB)

```
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

```
pixi run wheels
```

or

```
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

## Visualise in ParaView

ParaView is a free, open-source tool for 3-D visualisation of VTK files produced by gprMax.

**Download:** https://www.paraview.org/download/ (pick the latest stable Windows installer)

### Install the `gprMax_info` macro (one-time)

This macro splits the geometry view into labelled per-material layers.

1. Open ParaView.
2. Go to **Macros → Import new macro…**
3. Navigate to `<parent folder>/gprMax/tools/Paraview macros/gprMax_info.py` and open it.
4. The `gprMax_info` button will now appear permanently in the toolbar.

### View the geometry `.vti`

The geometry VTI is written by the `#geometry_view` command. Enable it in your TOML by ensuring `geometry_view_mode` is set (it defaults to `n` for the normal per-cell view).

1. **File → Open** → select the geometry `.vti` file (written in `wheels/models/`).
2. Click **Apply** in the Properties panel — you will see the model outline. If the geometry does not look right, set the view direction to **+Z** and rotate **90 degrees** twice; that shows the geometry as intended.
3. Click the **`gprMax_info`** macro button in the toolbar.
   All materials appear as separate **Threshold** items in the Pipeline Browser.
4. Toggle material visibility with the eye icon. Set colour/opacity in the Properties panel.

### View snapshots as an animation

Snapshots are only written when `wave_field = true` in your run TOML. For each run, gprMax writes them into a per-run folder such as `wheels/models/_start_test_1ascan__m001__a1__snaps/`, with files named `snapshot1.vti`, `snapshot2.vti`, …

1. **File → Open** → navigate to the run's `__snaps` folder and make sure **Group Files** is enabled in the top-right of the Open dialog. In ParaView this is the **two dots** file-series button.
2. Select the grouped snapshot series entry if ParaView shows one. If it only shows individual files, selecting **`snapshot1.vti`** should load the full series when **Group Files** is enabled.
   If selecting `snapshot1.vti` opens only one file, the **Group Files** toggle is off. Selecting all snapshot files manually will open them as separate readers, not as one animation series.
3. Click **Apply**.
4. In the **Properties** panel under **Display**, use the **Coloring** combo box to choose **E-field** or **H-field**, then pick a component (**Magnitude**, **X**, **Y**, or **Z**).
5. Set **Representation** to **Surface**.
6. Press **Play** in the VCR toolbar to animate through time steps.
7. Open **View → Animation View** to control playback speed and loop range.
8. Use the **Color Map Editor** (the coloured bar icon in the toolbar) to adjust the colour scale.

### Show geometry behind the wavefield

To see how the wavefield relates to the model geometry, load both the geometry `.vti` and the snapshot series in the same ParaView view.

1. Open the geometry `.vti` and the snapshot series, then click **Apply** for both readers.
2. In the **Pipeline Browser**, keep both items visible with the eye icon.
3. Select the geometry object and set **Representation** to **Surface** or **Wireframe**.
4. Reduce the geometry **Opacity** to about **0.1-0.3** so it stays in the background.
5. Select the snapshot series and keep its **Opacity** higher, typically **0.6-1.0**.
6. If the geometry hides too much of the field, try **Wireframe** for the geometry or lower its opacity further.

### Export a movie from ParaView

Once the snapshot series is playing correctly, you can save it as a movie file.

1. Set up the view exactly how you want it to appear in the movie.
2. Use **File → Save Animation**.
3. Choose an output filename and format such as **AVI**. On Windows, **MP4** may also be available.
4. In the **Save Animation Options** dialog, set:
   - **Frame Rate** for playback speed, for example **10-20 fps**.
   - **Frame Window** if you only want part of the time series.
   - **Image Resolution** if you want a larger output than the current view.
5. Click **OK** and ParaView will render all frames and write the movie.

If you want maximum control or smaller file sizes, save the animation as a PNG image sequence first, then convert it to video later with another tool. For a quick result inside ParaView, AVI is the simplest option.
