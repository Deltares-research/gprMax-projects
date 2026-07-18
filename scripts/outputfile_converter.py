import argparse
import math
import struct
from datetime import datetime
from pathlib import Path

import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator


DEFAULT_CENTRE_FREQ_MHZ = 250.0
DEFAULT_ANT_SEP_M = 0.5
DEFAULT_TRACE_INTERVAL_M = 0.1
DEFAULT_RESAMPLE_SAMPLES = None  # None = no resampling, keep original samples


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert merged gprMax .out to RD3, DZT, DT1, or IPRB for Ex/Ey/Ez."
    )
    p.add_argument("input_file", type=Path, help="Path to merged gprMax .out file")
    p.add_argument("--format", dest="fmt", choices=["rd3", "dzt", "dt1", "iprb"], required=True)
    return p.parse_args()


def read_data(input_file: Path, component: str, transpose: bool) -> tuple[np.ndarray, float]:
    component = component.capitalize()
    dataset_path = f"/rxs/rx1/{component}"

    with h5py.File(input_file, "r") as f:
        if dataset_path not in f:
            # Check if file is essentially empty
            if len(f.keys()) == 0:
                raise ValueError(f"File {input_file.name} is empty or corrupted (no datasets found)")
            raise KeyError(f"Dataset not found: {dataset_path}. Available groups: {list(f.keys())}")
        data = np.asarray(f[dataset_path], dtype=np.float64)
        dt_s = float(f.attrs["dt"])

    if data.ndim == 1:
        data = data[:, None]
    if transpose:
        data = data.T

    if data.ndim != 2:
        raise ValueError("Receiver data must be a 2D array after orientation")

    return data, dt_s


def resample_data(data: np.ndarray, target_samples: int | None) -> np.ndarray:
    if target_samples is None:
        return data
    if target_samples <= 0:
        raise ValueError("resample-samples must be > 0")
    n_samples = data.shape[0]
    if n_samples == target_samples:
        return data

    x_old = np.arange(n_samples, dtype=np.float64)
    x_new = np.linspace(0.0, n_samples - 1, target_samples)
    pchip = PchipInterpolator(x_old, data, axis=0)
    return pchip(x_new)


def scale_to_int16(data: np.ndarray) -> np.ndarray:
    max_abs = float(np.max(np.abs(data)))
    if max_abs == 0.0:
        return np.zeros_like(data, dtype=np.int16)

    scaled = data * (32767.5 / max_abs)
    scaled = np.clip(np.rint(scaled), -32768, 32767)
    return scaled.astype(np.int16)


def plot_outputs(data: np.ndarray, samp_int_ns: float, trac_int_m: float, title: str) -> None:
    pmin = float(np.min(data))
    pmax = float(np.max(data))

    n_samples, n_traces = data.shape
    x = np.arange(n_traces, dtype=np.float64) * trac_int_m
    t = (np.arange(1, n_samples + 1, dtype=np.float64)) * samp_int_ns

    plt.figure("Bscan")
    plt.title(title)
    plt.xlabel("Distance (m)")
    plt.ylabel("Time (ns)")
    plt.imshow(
        data,
        cmap="bone",
        vmin=pmin,
        vmax=pmax,
        aspect="auto",
        extent=[x[0] if n_traces else 0, x[-1] if n_traces else 0, t[-1], t[0]],
    )

    m = 1 << math.ceil(math.log2(n_samples))
    amp = np.fft.fft(data, n=m, axis=0)
    amp = (np.abs(amp[: m // 2, :]) / m) * 2.0
    amp = np.mean(amp, axis=1)

    samp_freq_mhz = (1.0 / samp_int_ns) * 1e3
    freq = samp_freq_mhz * np.arange(m // 2) / m

    plt.figure("Frequency Spectrum")
    plt.title(title)
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Amplitude")
    plt.fill_between(freq, amp, color="black")
    plt.tight_layout()
    plt.show()


def write_rd3_rad(base: Path, data_i16: np.ndarray, hdr: dict[str, float | int | str]) -> None:
    rad_path = base.with_suffix(".rad")
    rd3_path = base.with_suffix(".rd3")

    lines = [
        f"SAMPLES:{hdr['num_samp']}",
        f"FREQUENCY:{hdr['samp_freq']:.6f}",
        "FREQUENCY STEPS:1",
        "SIGNAL POSITION:0.000000",
        "RAW SIGNAL POSITION:0",
        "DISTANCE FLAG:1",
        "TIME FLAG:0",
        "PROGRAM FLAG:0",
        "EXTERNAL FLAG:0",
        "TIME INTERVAL:0.000000",
        f"DISTANCE INTERVAL:{hdr['trac_int']:.6f}",
        "OPERATOR:Unknown",
        "CUSTOMER:Unknown",
        "SITE:gprMax",
        f"ANTENNAS:{hdr['antenna']}",
        "ANTENNA ORIENTATION:NOT VALID FIELD",
        f"ANTENNA SEPARATION:{hdr['ant_sep']:.6f}",
        "COMMENT:----",
        f"TIMEWINDOW:{hdr['time_window']:.6f}",
        "STACKS:1",
        "STACK EXPONENT:0",
        "STACKING TIME:0.000000",
        f"LAST TRACE:{hdr['num_trac']}",
        f"STOP POSITION:{(hdr['num_trac'] * hdr['trac_int']):.6f}",
        "SYSTEM CALIBRATION:0.000000",
        "START POSITION:0.000000",
        "SHORT FLAG:1",
        "INTERMEDIATE FLAG:0",
        "LONG FLAG:0",
        "PREPROCESSING:0",
        "HIGH:0",
        "LOW:0",
        "FIXED INCREMENT:0.000000",
        "FIXED MOVES UP:0",
        "FIXED MOVES DOWN:1",
        "FIXED POSITION:0.000000",
        "WHEEL CALIBRATION:0.000000",
        "POSITIVE DIRECTION:1",
    ]

    rad_path.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
    with open(rd3_path, "wb") as f:
        f.write(np.asfortranarray(data_i16).tobytes(order="F"))


def _pack_dos_time(dt: datetime) -> int:
    sec2 = int(dt.second // 2)
    return (dt.hour << 11) | (dt.minute << 5) | sec2


def _pack_dos_date(dt: datetime) -> int:
    year = max(0, dt.year - 1980)
    return (year << 9) | (dt.month << 5) | dt.day


def write_dzt(base: Path, data_i16: np.ndarray, hdr: dict[str, float | int | str]) -> None:
    dzt_path = base.with_suffix(".dzt")

    num_samp = int(hdr["num_samp"])
    num_trac = int(hdr["num_trac"])
    trac_int = float(hdr["trac_int"])
    time_window = float(hdr["time_window"])

    antenna = str(hdr["antenna"])[:14].ljust(14)
    raw_name = base.stem[:12].ljust(12)

    c = 299792458.0
    dielectric = 8.0
    v = (c / math.sqrt(dielectric)) * 1e-9
    range_depth = v * (time_window / 2.0)

    now = datetime.now()
    create_time = 0
    create_date = 0
    mod_time = _pack_dos_time(now)
    mod_date = _pack_dos_date(now)

    with open(dzt_path, "wb") as f:
        f.write(struct.pack("<H", 255))
        f.write(struct.pack("<H", 1024))
        f.write(struct.pack("<H", num_samp))
        f.write(struct.pack("<H", 16))
        f.write(struct.pack("<H", 32768))
        f.write(struct.pack("<f", 0.0))
        f.write(struct.pack("<f", 1.0 / trac_int))
        f.write(struct.pack("<f", 0.0))
        f.write(struct.pack("<f", 0.0))
        f.write(struct.pack("<f", time_window))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", create_time))
        f.write(struct.pack("<H", create_date))
        f.write(struct.pack("<H", mod_time))
        f.write(struct.pack("<H", mod_date))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<f", dielectric))
        f.write(struct.pack("<f", 0.0))
        f.write(struct.pack("<f", range_depth))
        f.write(bytes(31))
        f.write(struct.pack("<B", 0))
        f.write(antenna.encode("ascii", "ignore"))
        f.write(struct.pack("<H", 0))
        f.write(raw_name.encode("ascii", "ignore"))
        f.write(struct.pack("<H", 0))
        f.write(struct.pack("<H", 0))
        f.write(bytes(896))

        f.seek(1024)
        data_u16 = (data_i16.astype(np.int32) + 2**15).astype(np.uint16)
        f.write(np.asfortranarray(data_u16).tobytes(order="F"))


def write_dt1_hd(base: Path, data_i16: np.ndarray, hdr: dict[str, float | int | str]) -> None:
    hd_path = base.with_suffix(".hd")
    dt1_path = base.with_suffix(".dt1")

    n_samples = int(hdr["num_samp"])
    n_traces = int(hdr["num_trac"])
    trac_int = float(hdr["trac_int"])
    time_window = float(hdr["time_window"])

    now = datetime.now()
    date_txt = f"{now.year}-{now.month}-{now.day}"

    hd_lines = [
        "1234",
        f"Data Collected with {hdr['antenna']}",
        date_txt,
        f"NUMBER OF TRACES   = {n_traces}",
        f"NUMBER OF PTS/TRC  = {n_samples}",
        "TIMEZERO AT POINT  = 0",
        f"TOTAL TIME WINDOW  = {time_window:.6f}",
        "STARTING POSITION  = 0.000000",
        f"FINAL POSITION     = {(n_traces - 1) * trac_int:.6f}",
        f"STEP SIZE USED     = {trac_int:.6f}",
        "POSITION UNITS     = m",
        f"NOMINAL FREQUENCY  = {float(hdr['centre_freq']):.6f}",
        f"ANTENNA SEPARATION = {float(hdr['ant_sep']):.6f}",
        "PULSER VOLTAGE (V) = 0.000000",
        "NUMBER OF STACKS   = 1",
        "SURVEY MODE        = Reflection",
    ]
    hd_path.write_text("\r\n".join(hd_lines) + "\r\n", encoding="ascii")

    samp_int = float(hdr["samp_int"])
    
    with open(dt1_path, "wb") as f:
        for i in range(n_traces):
            pos = i * trac_int
            header = bytearray()
            header.extend(struct.pack("<f", float(i + 1)))           # Trace number
            header.extend(struct.pack("<f", float(pos)))             # Position
            header.extend(struct.pack("<f", float(n_samples)))       # Number of samples
            header.extend(struct.pack("<f", 0.0))                    # Time zero
            header.extend(struct.pack("<f", samp_int))               # Sample interval (ns)
            header.extend(struct.pack("<f", 2.0))                    # Gains applied
            header.extend(struct.pack("<f", float(time_window)))     # Time window
            header.extend(struct.pack("<f", 1.0))                    # Number of stacks
            header.extend(struct.pack("<d", 0.0))                    # Position 1 (x)
            header.extend(struct.pack("<d", float(pos)))             # Position 2 (y)
            header.extend(struct.pack("<d", 0.0))                    # Position 3 (z)
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(struct.pack("<f", 0.0))
            header.extend(bytes(28))
            f.write(header)
            f.write(np.asarray(data_i16[:, i], dtype="<i2").tobytes())


def write_iprb_iprh(base: Path, data_i16: np.ndarray, hdr: dict[str, float | int | str]) -> None:
    iprh_path = base.with_suffix(".iprh")
    iprb_path = base.with_suffix(".iprb")

    now = datetime.now()
    date_txt = f"{now.year}-{now.month}-{now.day}"

    lines = [
        "HEADER VERSION: 20",
        "DATA VERSION: 16",
        f"DATE: {date_txt}",
        "START TIME: 00:00:00",
        "STOP TIME: 00:00:00",
        f"ANTENNA: {float(hdr['centre_freq'])} MHz",
        f"ANTENNA SEPARATION: {float(hdr['ant_sep']):.6f}",
        f"SAMPLES: {int(hdr['num_samp'])}",
        "SIGNAL POSITION: 0.000000",
        "CLIPPED SAMPLES: 0",
        "RUNS: 0",
        "MAX STACKS: 1",
        "AUTOSTACKS: 1",
        f"FREQUENCY: {float(hdr['samp_freq']):.6f}",
        f"TIMEWINDOW: {float(hdr['time_window']):.6f}",
        f"LAST TRACE: {int(hdr['num_trac'])}",
        "TRIG SOURCE: wheel",
        "TIME INTERVAL: 0.000000",
        f"DISTANCE INTERVAL: {float(hdr['trac_int']):.6f}",
        f"USER DISTANCE INTERVAL: {float(hdr['trac_int']):.6f}",
        f"STOP POSITION: {(float(hdr['num_trac']) * float(hdr['trac_int'])):.6f}",
        "WHEEL NAME: Cart",
        "WHEEL CALIBRATION: 0.000000",
        "ZERO LEVEL: 0",
        "SOIL VELOCITY: 100",
        "PREPROCESSING: Unknown Preprocessing",
        "OPERATOR COMMENT: ----",
        "ANTENNA F/W: ----",
        "ANTENNA H/W: ----",
        "ANTENNA FPGA: ----",
        "ANTENNA SERIAL: ----",
        "SOFTWARE VERSION: ----",
        "POSITIONING: 0",
        "CHANNELS: 1",
        "CHANNEL CONFIGURATION: 1",
        "CH_X_OFFSET: 0.000000",
        "CH_Y_OFFSET: 0.000000",
        "MEASUREMENT DIRECTION: 1",
        "RELATIVE DIRECTION: 0",
        "RELATIVE DISTANCE: 0.000000",
        "RELATIVE START: 0.000000",
    ]

    iprh_path.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
    with open(iprb_path, "wb") as f:
        f.write(np.asfortranarray(data_i16).tobytes(order="F"))


def get_available_components(input_file: Path) -> list[str]:
    """Discover which field components are available in the HDF5 file."""
    available = []
    try:
        with h5py.File(input_file, "r") as f:
            if "/rxs/rx1" in f:
                rx1_group = f["/rxs/rx1"]
                for component in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
                    if component in rx1_group:
                        available.append(component)
    except Exception:
        pass
    return available


def main() -> None:
    args = parse_args()

    # Discover available components
    available_components = get_available_components(args.input_file)
    if not available_components:
        print("Error: No field components found in file", file=__import__("sys").stderr)
        return

    fmt = args.fmt.lower()
    
    for component in available_components:
        try:
            # DT1 format needs original orientation (n_samples, n_traces), others need transpose
            transpose = (fmt != "dt1")
            data, dt_s = read_data(args.input_file, component, transpose=transpose)
        except ValueError as e:
            print(f"Error: {e}", file=__import__("sys").stderr)
            return
        except KeyError as e:
            print(f"Warning: Skipping {component} - {e}", file=__import__("sys").stderr)
            continue
            
        original_num_samp = data.shape[0]
        data = resample_data(data, DEFAULT_RESAMPLE_SAMPLES)

        num_samp, num_trac = data.shape
        # Keep total time window from original dt and original sample count.
        time_window_ns = original_num_samp * dt_s * 1e9
        samp_int_ns = time_window_ns / (num_samp - 1) if num_samp > 1 else time_window_ns
        samp_freq_mhz = (1.0 / samp_int_ns) * 1e3
        data_i16 = scale_to_int16(data)

        base = args.input_file.with_suffix("").with_name(
            f"{args.input_file.with_suffix('').name}_{component.lower()}"
        )
        hdr = {
            "num_samp": num_samp,
            "num_trac": num_trac,
            "time_window": time_window_ns,
            "samp_int": samp_int_ns,
            "samp_freq": samp_freq_mhz,
            "centre_freq": DEFAULT_CENTRE_FREQ_MHZ,
            "ant_sep": DEFAULT_ANT_SEP_M,
            "trac_int": DEFAULT_TRACE_INTERVAL_M,
            "antenna": f"gprMax {DEFAULT_CENTRE_FREQ_MHZ}MHz",
        }

        if fmt == "rd3":
            write_rd3_rad(base, data_i16, hdr)
        elif fmt == "dzt":
            write_dzt(base, data_i16, hdr)
        elif fmt == "dt1":
            write_dt1_hd(base, data_i16, hdr)
        elif fmt == "iprb":
            write_iprb_iprh(base, data_i16, hdr)
        else:
            raise ValueError(f"Unsupported format: {args.fmt}")

        print(f"Wrote {fmt.upper()} export: {base}")


if __name__ == "__main__":
    main()
