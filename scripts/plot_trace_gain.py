import argparse
import glob
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks, hilbert


VALID_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz", "Ix", "Iy", "Iz")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot a raw A-scan together with an AGC-processed version and save reflection-strength metrics."
    )
    parser.add_argument("input_file", nargs="?", type=Path, help="Path to a gprMax .out file")
    parser.add_argument("component", nargs="?", choices=VALID_COMPONENTS, default="Ez", help="Receiver component to plot (default: Ez)")
    parser.add_argument("--rx", type=int, default=1, help="Receiver number to read (default: 1)")
    parser.add_argument(
        "--trace-index",
        type=int,
        default=1,
        help="Trace index for merged outputs with multiple A-scans (1-based, default: 1)",
    )
    parser.add_argument(
        "--direct-end-ns",
        type=float,
        default=65.0,
        help="End time of the direct-wave window in ns (default: 65.0)",
    )
    parser.add_argument(
        "--search-start-ns",
        type=float,
        default=180.0,
        help="Start time in ns after which the reflection search begins (default: 180.0)",
    )
    parser.add_argument(
        "--search-span-ns",
        type=float,
        default=100.0,
        help="Length of the reflection search interval in ns after search-start-ns (default: 100.0)",
    )
    parser.add_argument(
        "--reflection-window-ns",
        type=float,
        default=65.0,
        help="Width of the reflection-analysis window in ns (default: 65.0)",
    )
    parser.add_argument(
        "--agc-window-ns",
        type=float,
        default=20.0,
        help="AGC window length in nanoseconds for the running RMS envelope (default: 20.0)",
    )
    parser.add_argument(
        "--agc-floor",
        type=float,
        default=1e-12,
        help="Lower bound on the AGC envelope to avoid division by zero (default: 1e-12)",
    )
    parser.add_argument(
        "--normalize-processed",
        action="store_true",
        help="Normalize the AGC trace to the raw peak amplitude for easier visual comparison",
    )
    parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Optional markdown report path. Defaults to a file next to the output trace.",
    )
    parser.add_argument(
        "--batch",
        type=str,
        default=None,
        help="Batch glob pattern for multiple .out files, e.g. wheels/outputs/*.out",
    )
    parser.add_argument(
        "--save-png",
        action="store_true",
        help="Save the QC plot as a PNG instead of only showing it interactively",
    )
    parser.add_argument(
        "--png-dpi",
        type=int,
        default=600,
        help="DPI for saved PNG QC plots (default: 600)",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Optional path for the combined markdown summary in batch mode.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    batch_mode = args.batch is not None
    if not batch_mode and args.input_file is None:
        raise ValueError("Provide either input_file for single mode or --batch for batch mode")


def is_batch_mode(args: argparse.Namespace) -> bool:
    return args.batch is not None


def parse_batch_selector(selector: str) -> str:
    glob_pattern = selector.strip()
    if not glob_pattern:
        raise ValueError("--batch must include a non-empty glob pattern")
    if "::" in glob_pattern:
        raise ValueError("Prefix filters were removed; use a curated folder plus a glob pattern")
    return glob_pattern


def read_trace(input_file: Path, rx: int, component: str, trace_index: int) -> tuple[np.ndarray, float]:
    dataset_path = f"/rxs/rx{rx}/{component}"

    with h5py.File(input_file, "r") as f:
        if dataset_path not in f:
            raise KeyError(f"Dataset not found: {dataset_path}")

        data = np.asarray(f[dataset_path], dtype=np.float64)
        dt_s = float(f.attrs["dt"])

    if data.ndim == 1:
        return data, dt_s

    if data.ndim != 2:
        raise ValueError(f"Expected 1D or 2D receiver data, got shape {data.shape}")

    column_index = trace_index - 1
    if column_index < 0 or column_index >= data.shape[1]:
        raise IndexError(f"trace-index must be between 1 and {data.shape[1]}")

    return data[:, column_index], dt_s


def build_time_ns(trace: np.ndarray, dt_s: float) -> np.ndarray:
    time_ns = np.arange(trace.size, dtype=np.float64) * dt_s * 1e9
    return time_ns

def apply_agc(trace: np.ndarray, dt_s: float, window_ns: float, agc_floor: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if window_ns <= 0.0:
        raise ValueError("agc-window-ns must be > 0")

    time_ns = build_time_ns(trace, dt_s)
    dt_ns = dt_s * 1e9
    window_samples = max(1, int(round(window_ns / dt_ns)))
    if window_samples % 2 == 0:
        window_samples += 1

    kernel = np.ones(window_samples, dtype=np.float64) / window_samples
    rms = np.sqrt(np.convolve(trace * trace, kernel, mode="same"))
    rms = np.maximum(rms, agc_floor)
    return trace / rms, time_ns, rms


def scale_like_raw(raw: np.ndarray, processed: np.ndarray) -> np.ndarray:
    raw_peak = float(np.max(np.abs(raw)))
    processed_peak = float(np.max(np.abs(processed)))
    if raw_peak == 0.0 or processed_peak == 0.0:
        return processed
    return processed * (raw_peak / processed_peak)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def peak_abs(x: np.ndarray) -> float:
    return float(np.max(np.abs(x)))


def build_window_mask(time_ns: np.ndarray, start_ns: float, end_ns: float) -> np.ndarray:
    if end_ns <= start_ns:
        raise ValueError("window end must be greater than start")
    return (time_ns >= start_ns) & (time_ns <= end_ns)


def find_reflection_window(
    processed_trace: np.ndarray,
    time_ns: np.ndarray,
    search_start_ns: float,
    search_span_ns: float,
    window_ns: float,
) -> tuple[float, float, float]:
    if search_span_ns <= 0.0:
        raise ValueError("search-span-ns must be > 0")

    search_end_ns = search_start_ns + search_span_ns
    search_mask = (time_ns >= search_start_ns) & (time_ns <= search_end_ns)
    if not np.any(search_mask):
        raise ValueError("search interval does not overlap the trace")

    envelope = np.abs(hilbert(processed_trace))
    search_indices = np.where(search_mask)[0]
    search_envelope = envelope[search_mask]
    prominence = 0.1 * float(np.max(search_envelope))
    peak_offsets, _ = find_peaks(search_envelope, prominence=prominence)

    if peak_offsets.size > 0:
        peak_index = search_indices[int(peak_offsets[0])]
    else:
        peak_index = search_indices[int(np.argmax(search_envelope))]

    center_ns = float(time_ns[peak_index])
    half_window = window_ns / 2.0
    start_ns = max(float(time_ns[0]), center_ns - half_window)
    end_ns = min(float(time_ns[-1]), center_ns + half_window)
    return start_ns, end_ns, center_ns


def window_metrics(trace: np.ndarray, time_ns: np.ndarray, start_ns: float, end_ns: float) -> dict[str, float]:
    mask = build_window_mask(time_ns, start_ns, end_ns)
    window = trace[mask]
    env = np.abs(hilbert(window))
    return {
        "start_ns": float(start_ns),
        "end_ns": float(end_ns),
        "duration_ns": float(end_ns - start_ns),
        "mean": float(np.mean(window)),
        "rms": rms(window),
        "peak_abs": peak_abs(window),
        "env_peak": float(np.max(env)),
        "env_rms": rms(env),
    }


def choose_report_path(input_file: Path, component: str, report_file: Path | None) -> Path:
    if report_file is not None:
        return report_file
    return input_file.with_name(f"{input_file.stem}_{component}_reflection_report.md")


def choose_png_path(input_file: Path, component: str) -> Path:
    return input_file.with_name(f"{input_file.stem}_{component}_qc.png")


def choose_summary_path(input_files: list[Path], component: str, summary_file: Path | None) -> Path:
    if summary_file is not None:
        return summary_file
    common_parent = Path(input_files[0]).parent if input_files else Path.cwd()
    return common_parent / f"trace_qc_summary_{component}.md"


def build_report_text(
    input_file: Path,
    component: str,
    rx: int,
    trace_index: int,
    settings: dict[str, float],
    raw_direct: dict[str, float],
    raw_reflection: dict[str, float],
    processed_direct: dict[str, float],
    processed_reflection: dict[str, float],
) -> str:
    processed_rms_db = 20.0 * np.log10(max(processed_reflection["rms"], 1e-30) / max(processed_direct["rms"], 1e-30))
    processed_peak_db = 20.0 * np.log10(max(processed_reflection["peak_abs"], 1e-30) / max(processed_direct["peak_abs"], 1e-30))
    processed_env_peak_db = 20.0 * np.log10(max(processed_reflection["env_peak"], 1e-30) / max(processed_direct["env_peak"], 1e-30))
    processed_env_rms_db = 20.0 * np.log10(max(processed_reflection["env_rms"], 1e-30) / max(processed_direct["env_rms"], 1e-30))
    raw_rms_db = 20.0 * np.log10(max(raw_reflection["rms"], 1e-30) / max(raw_direct["rms"], 1e-30))
    raw_peak_db = 20.0 * np.log10(max(raw_reflection["peak_abs"], 1e-30) / max(raw_direct["peak_abs"], 1e-30))

    lines = [
        f"# Reflection Strength Report",
        "",
        f"- Output file: `{input_file}`",
        f"- Component: `{component}`",
        f"- Receiver: `{rx}`",
        f"- Trace index: `{trace_index}`",
        "",
        "## Settings",
        "",
        "| Setting | Value |",
        "|---|---:|",
        f"| Direct window end (ns) | {settings['direct_end_ns']:.3f} |",
        f"| Reflection search start (ns) | {settings['search_start_ns']:.3f} |",
        f"| Reflection search span (ns) | {settings['search_span_ns']:.3f} |",
        f"| Reflection window length (ns) | {settings['reflection_window_ns']:.3f} |",
        f"| AGC window (ns) | {settings['agc_window_ns']:.3f} |",
        "",
        "## Metrics",
        "",
        "| Signal | Domain | Start ns | End ns | Mean | RMS | Peak abs | Envelope peak | Envelope RMS | RMS vs direct dB | Peak vs direct dB | Env peak vs direct dB | Env RMS vs direct dB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| Direct | Raw | {raw_direct['start_ns']:.3f} | {raw_direct['end_ns']:.3f} | {raw_direct['mean']:.6e} | {raw_direct['rms']:.6e} | {raw_direct['peak_abs']:.6e} | {raw_direct['env_peak']:.6e} | {raw_direct['env_rms']:.6e} | 0.000 | 0.000 | 0.000 | 0.000 |",
        f"| Reflection | Raw | {raw_reflection['start_ns']:.3f} | {raw_reflection['end_ns']:.3f} | {raw_reflection['mean']:.6e} | {raw_reflection['rms']:.6e} | {raw_reflection['peak_abs']:.6e} | {raw_reflection['env_peak']:.6e} | {raw_reflection['env_rms']:.6e} | {raw_rms_db:.3f} | {raw_peak_db:.3f} | {20.0 * np.log10(max(raw_reflection['env_peak'], 1e-30) / max(raw_direct['env_peak'], 1e-30)):.3f} | {20.0 * np.log10(max(raw_reflection['env_rms'], 1e-30) / max(raw_direct['env_rms'], 1e-30)):.3f} |",
        f"| Direct | Raw for AGC/metric | {processed_direct['start_ns']:.3f} | {processed_direct['end_ns']:.3f} | {processed_direct['mean']:.6e} | {processed_direct['rms']:.6e} | {processed_direct['peak_abs']:.6e} | {processed_direct['env_peak']:.6e} | {processed_direct['env_rms']:.6e} | 0.000 | 0.000 | 0.000 | 0.000 |",
        f"| Reflection | Raw for AGC/metric | {processed_reflection['start_ns']:.3f} | {processed_reflection['end_ns']:.3f} | {processed_reflection['mean']:.6e} | {processed_reflection['rms']:.6e} | {processed_reflection['peak_abs']:.6e} | {processed_reflection['env_peak']:.6e} | {processed_reflection['env_rms']:.6e} | {processed_rms_db:.3f} | {processed_peak_db:.3f} | {processed_env_peak_db:.3f} | {processed_env_rms_db:.3f} |",
        "",
        "## Recommended Reporting Metric",
        "",
        f"Use the raw-trace RMS reflection-to-direct ratio: **{processed_rms_db:.3f} dB**.",
    ]
    return "\n".join(lines) + "\n"


def plot_trace(
    processed_trace: np.ndarray,
    agc_trace: np.ndarray,
    time_ns: np.ndarray,
    input_file: Path,
    component: str,
    rx: int,
    trace_index: int,
    direct_metrics: dict[str, float],
    reflection_metrics: dict[str, float],
    reflection_rms_db: float,
) -> plt.Figure:
    fig, ax_left = plt.subplots(num=f"{input_file.name} {component}", figsize=(14, 5), facecolor="w", edgecolor="w")
    ax_right = ax_left.twinx()

    filtered_line = ax_left.plot(time_ns, processed_trace, color="black", lw=1.2, label="Raw trace")
    processed_line = ax_right.plot(time_ns, agc_trace, color="tab:blue", lw=1.2, label="AGC of raw trace")

    ax_left.set_title("Raw and AGC A-scan with direct/reflection windows")
    ax_left.set_xlabel("Time [ns]")
    ax_left.set_ylabel(f"Raw {component}")
    ax_right.set_ylabel(f"AGC {component}")
    ax_left.grid(which="both", axis="both", linestyle="-.")

    y0, y1 = ax_left.get_ylim()
    height = y1 - y0
    for metrics, label in ((direct_metrics, "Direct"), (reflection_metrics, "Reflection")):
        rect = plt.Rectangle(
            (metrics["start_ns"], y0),
            metrics["duration_ns"],
            height,
            fill=False,
            edgecolor="red",
            linewidth=1.8,
        )
        ax_left.add_patch(rect)
        if label == "Direct":
            text = f"{label}\nRMS={metrics['rms']:.3e}"
            ax_left.text(metrics["start_ns"] + 1.0, y1 - 0.08 * height, text, color="red", va="top", ha="left")
        else:
            text = f"{label}\nRMS={metrics['rms']:.3e}\n{reflection_rms_db:.1f} dB"
            ax_left.text(metrics["start_ns"] + 1.0, y1 - 0.28 * height, text, color="red", va="top", ha="left")

    lines = filtered_line + processed_line
    labels = [line.get_label() for line in lines]
    ax_left.legend(lines, labels, loc="upper right")

    fig.suptitle(f"{input_file.name} | rx{rx} | {component} | trace {trace_index}")
    fig.tight_layout()
    return fig


def summarize_metrics_row(
    input_file: Path,
    component: str,
    direct_metrics: dict[str, float],
    reflection_metrics: dict[str, float],
    reflection_rms_db: float,
    search_start_ns: float,
    search_span_ns: float,
) -> dict[str, float | str]:
    return {
        "file": str(input_file),
        "component": component,
        "search_start_ns": search_start_ns,
        "search_span_ns": search_span_ns,
        "direct_start_ns": direct_metrics["start_ns"],
        "direct_end_ns": direct_metrics["end_ns"],
        "reflection_start_ns": reflection_metrics["start_ns"],
        "reflection_end_ns": reflection_metrics["end_ns"],
        "direct_rms": direct_metrics["rms"],
        "reflection_rms": reflection_metrics["rms"],
        "reflection_peak": reflection_metrics["peak_abs"],
        "reflection_env_peak": reflection_metrics["env_peak"],
        "reflection_rms_db": reflection_rms_db,
    }


def build_summary_text(rows: list[dict[str, float | str]], component: str) -> str:
    lines = [
        "# Trace QC Summary",
        "",
        f"Component: `{component}`",
        "",
        "| File | Direct ns | Reflection ns | Direct RMS | Reflection RMS | Reflection peak | Reflection env peak | Recommended dB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        direct_label = f"{row['direct_start_ns']:.3f}-{row['direct_end_ns']:.3f}"
        reflection_label = f"{row['reflection_start_ns']:.3f}-{row['reflection_end_ns']:.3f}"
        lines.append(
            f"| {row['file']} | {direct_label} | {reflection_label} | {row['direct_rms']:.6e} | {row['reflection_rms']:.6e} | {row['reflection_peak']:.6e} | {row['reflection_env_peak']:.6e} | {row['reflection_rms_db']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


def resolve_input_files(args: argparse.Namespace) -> list[Path]:
    if args.batch is not None:
        batch_glob = parse_batch_selector(args.batch)
        files = sorted(Path(p) for p in glob.glob(batch_glob))
    else:
        files = [args.input_file] if args.input_file is not None else []

    files = [path for path in files if path is not None]
    if not files:
        raise ValueError("No input .out files matched the requested inputs")
    return files


def run_analysis_for_file(input_file: Path, args: argparse.Namespace) -> tuple[str, dict[str, float | str], plt.Figure]:
    raw, dt_s = read_trace(input_file, args.rx, args.component, args.trace_index)
    time_ns = build_time_ns(raw, dt_s)
    reflection_start_ns, reflection_end_ns, _ = find_reflection_window(
        raw,
        time_ns,
        args.search_start_ns,
        args.search_span_ns,
        args.reflection_window_ns,
    )
    direct_start_ns = 0.0
    direct_end_ns = args.direct_end_ns

    raw_direct = window_metrics(raw, time_ns, direct_start_ns, direct_end_ns)
    raw_reflection = window_metrics(raw, time_ns, reflection_start_ns, reflection_end_ns)
    processed_direct = window_metrics(raw, time_ns, direct_start_ns, direct_end_ns)
    processed_reflection = window_metrics(raw, time_ns, reflection_start_ns, reflection_end_ns)

    agc_trace, _time_ns, _envelope = apply_agc(raw, dt_s, args.agc_window_ns, args.agc_floor)
    if args.normalize_processed:
        agc_trace = scale_like_raw(raw, agc_trace)

    report_text = build_report_text(
        input_file,
        args.component,
        args.rx,
        args.trace_index,
        {
            "direct_end_ns": args.direct_end_ns,
            "search_start_ns": args.search_start_ns,
            "search_span_ns": args.search_span_ns,
            "reflection_window_ns": args.reflection_window_ns,
            "agc_window_ns": args.agc_window_ns,
        },
        raw_direct,
        raw_reflection,
        processed_direct,
        processed_reflection,
    )

    reflection_rms_db = 20.0 * np.log10(max(processed_reflection["rms"], 1e-30) / max(processed_direct["rms"], 1e-30))
    figure = plot_trace(
        raw,
        agc_trace,
        time_ns,
        input_file,
        args.component,
        args.rx,
        args.trace_index,
        processed_direct,
        processed_reflection,
        reflection_rms_db,
    )
    summary_row = summarize_metrics_row(
        input_file,
        args.component,
        processed_direct,
        processed_reflection,
        reflection_rms_db,
        args.search_start_ns,
        args.search_span_ns,
    )
    return report_text, summary_row, figure


def main() -> None:
    args = parse_args()
    validate_args(args)
    input_files = resolve_input_files(args)
    summary_rows: list[dict[str, float | str]] = []

    for input_file in input_files:
        report_text, summary_row, figure = run_analysis_for_file(input_file, args)
        summary_rows.append(summary_row)

        report_path = choose_report_path(input_file, args.component, args.report_file if len(input_files) == 1 else None)
        report_path.write_text(report_text, encoding="utf-8")
        print(report_text)

        if args.save_png or is_batch_mode(args):
            png_path = choose_png_path(input_file, args.component)
            figure.savefig(png_path, dpi=args.png_dpi, bbox_inches="tight")

        if not is_batch_mode(args):
            plt.show()
        else:
            plt.close(figure)

    if is_batch_mode(args):
        summary_path = choose_summary_path(input_files, args.component, args.summary_file)
        summary_text = build_summary_text(summary_rows, args.component)
        summary_path.write_text(summary_text, encoding="utf-8")
        print(summary_text)


if __name__ == "__main__":
    main()