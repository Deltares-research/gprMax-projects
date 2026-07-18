"""Extract minimal polygon coordinates from geometry HDF5 files.

Extracts boundaries for each material, identifies disconnected regions, simplifies
using Douglas-Peucker algorithm, and generates QC plots.

Run from repository root:
    python wheels/scripts/extract_polygons.py <h5_file> <material_file>

Example:
    python wheels/scripts/extract_polygons.py wheel_geometry.h5 ../materials/base_sand_material_001.txt
    python wheels/scripts/extract_polygons.py wheels_watertable_geometry.h5 ../materials/split_sand_material_001.txt
"""

from pathlib import Path
import sys
import numpy as np
from netCDF4 import Dataset
from scipy.ndimage import label
from scipy.signal import savgol_filter
from scipy.interpolate import splprep, splev, UnivariateSpline
import matplotlib.pyplot as plt

# --- Configuration ---
SIMPLIFICATION_TOLERANCE = 0.5
SMOOTH_MAX_DEVIATION_M = 0.25
SMOOTH_TARGET_POINTS_MIN = 12
SMOOTH_TARGET_POINTS_MAX = 30
SMOOTH_MOVING_AVG_WINDOW = 9
PROFILE_SMOOTH_WINDOW_MAX = 51
SHARED_INTERFACE_TOL_CELLS = 1e-9
FLAT_SLOPE_THRESHOLD = 0.015
FLAT_MIN_RUN = 120
FLAT_FIT_BLEND = 0.9

# Original palette from traced image (RGB, 0-255)
MATERIAL_COLORS = {
    0: (255, 240, 160),    # pale_yellow_top - unsaturated sand
    1: (207, 229, 245),    # light_blue - sandy clay
    2: (154, 100, 58),     # brown - peat
    3: (146, 170, 163),    # grey_green - silty sandy clay
    4: (200, 220, 220),    # saturated sand (yellow + blue blend)
}

# --- Paths ---
repo = Path(__file__).resolve().parents[2]
geom_dir = repo / "wheels" / "geometries"

# --- Material File Parsing ---
def parse_material_file(material_file_path):
    """Extract material ID to name mapping from material file.
    
    Looks for lines like:
        ID 0: zand_fijn_sterk_siltig -- description
    """
    material_names = {}
    
    try:
        with open(material_file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ID "):
                    # Parse "ID 0: material_name -- description"
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        id_part = parts[0].strip()  # "ID 0"
                        name_part = parts[1].strip()  # "material_name -- description"
                        
                        # Extract ID number
                        try:
                            mat_id = int(id_part.split()[-1])
                            # Extract material name (before " --" if it exists)
                            mat_name = name_part.split("--")[0].strip()
                            if mat_name:
                                material_names[mat_id] = mat_name
                        except (ValueError, IndexError):
                            pass
    except FileNotFoundError:
        print(f"⚠️  Material file not found: {material_file_path}")
    
    return material_names

# --- Douglas-Peucker Simplification ---
def rdp_simplify(points, epsilon):
    """Ramer-Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points
    
    dmax = 0.0
    index = 0
    start = points[0]
    end = points[-1]
    
    for i in range(1, len(points) - 1):
        d = point_to_line_distance(points[i], start, end)
        if d > dmax:
            index = i
            dmax = d
    
    if dmax > epsilon:
        rec1 = rdp_simplify(points[:index+1], epsilon)
        rec2 = rdp_simplify(points[index:], epsilon)
        return np.vstack((rec1[:-1], rec2))
    else:
        return np.array([start, end])

def point_to_line_distance(point, line_start, line_end):
    """Perpendicular distance from point to line."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    denom = np.sqrt((y2 - y1)**2 + (x2 - x1)**2)
    return num / denom if denom > 0 else 0.0

def simplify_closed_polygon(points_closed, epsilon):
    """Apply RDP to a closed polygon by simplifying its open ring then re-closing."""
    pts = np.asarray(points_closed, dtype=float)
    if len(pts) < 4:
        return pts

    if np.allclose(pts[0], pts[-1]):
        ring = pts[:-1]
    else:
        ring = pts

    if len(ring) < 3:
        return pts

    simplified = rdp_simplify(ring, epsilon)
    # Prevent degenerate polygons after aggressive simplification.
    if len(simplified) < 3:
        simplified = ring

    if not np.allclose(simplified[0], simplified[-1]):
        simplified = np.vstack([simplified, simplified[0]])

    return simplified

def resample_closed_ring(points_open, target_n):
    """Uniform arc-length resampling on a closed ring of open points."""
    pts = np.asarray(points_open, dtype=float)
    n = len(pts)
    if n < 3 or target_n < 3:
        return pts

    periodic = np.vstack([pts, pts[0]])
    seg = np.diff(periodic, axis=0)
    seglen = np.sqrt((seg**2).sum(axis=1))
    s = np.concatenate(([0.0], np.cumsum(seglen)))
    total = s[-1]
    if total == 0:
        return pts

    u = s / total
    u_new = np.linspace(0.0, 1.0, target_n, endpoint=False)
    x_new = np.interp(u_new, u, periodic[:, 0])
    y_new = np.interp(u_new, u, periodic[:, 1])
    return np.column_stack([x_new, y_new])

def circular_moving_average(points_open, window):
    """Circular moving average smoothing on open ring points."""
    pts = np.asarray(points_open, dtype=float)
    n = len(pts)
    if n < 3:
        return pts
    w = max(3, int(window))
    if w % 2 == 0:
        w += 1
    w = min(w, n if n % 2 == 1 else n - 1)
    if w < 3:
        return pts

    pad = w // 2
    ext = np.vstack([pts[-pad:], pts, pts[:pad]])
    kernel = np.ones(w, dtype=float) / w
    xs = np.convolve(ext[:, 0], kernel, mode="valid")
    ys = np.convolve(ext[:, 1], kernel, mode="valid")
    return np.column_stack([xs, ys])

def smooth_polygon_constrained(points_closed):
    """Smooth polygon boundaries while limiting geometric drift and point count."""
    pts = np.asarray(points_closed, dtype=float)
    if len(pts) < 6:
        return pts

    if np.allclose(pts[0], pts[-1]):
        ring = pts[:-1]
    else:
        ring = pts
    if len(ring) < 4:
        return pts

    # Densify first so smoothing affects shape smoothly instead of creating kinks.
    dense_n = int(np.clip(len(ring) * 6, 60, 400))
    dense = resample_closed_ring(ring, dense_n)

    # Smooth with circular moving average.
    smooth = circular_moving_average(dense, SMOOTH_MOVING_AVG_WINDOW)

    # Constrain displacement from original dense boundary.
    delta = smooth - dense
    dist = np.sqrt((delta**2).sum(axis=1))
    scale = np.ones_like(dist)
    over = dist > SMOOTH_MAX_DEVIATION_M
    scale[over] = SMOOTH_MAX_DEVIATION_M / dist[over]
    constrained = dense + delta * scale[:, None]

    # Fit periodic spline, then sample to target budget.
    target_n = int(np.clip(len(ring), SMOOTH_TARGET_POINTS_MIN, SMOOTH_TARGET_POINTS_MAX))
    try:
        tck, _ = splprep([constrained[:, 0], constrained[:, 1]], s=0.0, per=1, k=min(3, len(constrained)-1))
        u_new = np.linspace(0.0, 1.0, target_n, endpoint=False)
        x_new, y_new = splev(u_new, tck)
        out = np.column_stack([x_new, y_new])
    except Exception:
        out = resample_closed_ring(constrained, target_n)

    if not np.allclose(out[0], out[-1]):
        out = np.vstack([out, out[0]])
    return out

def _smooth_profile(y_values):
    """1D smoothing for interface profiles with robust small-sample handling."""
    y = np.asarray(y_values, dtype=float)
    n = len(y)
    if n < 5:
        return y

    x = np.arange(n, dtype=float)

    # First pass: smooth spline suppresses local staircase jumps while retaining
    # broad curvature (e.g., valley/basin shapes).
    try:
        s_main = max(1e-6, 0.35 * n)
        ys = UnivariateSpline(x, y, s=s_main, k=min(3, n - 1))(x)
    except Exception:
        ys = y.copy()

    # Second pass: light Savitzky-Golay cleanup for residual local kinks.
    win = min(PROFILE_SMOOTH_WINDOW_MAX, n if n % 2 == 1 else n - 1)
    win = max(7, win)
    if win >= n:
        win = n - 1 if (n - 1) % 2 == 1 else n - 2
    if win >= 5:
        ys = savgol_filter(ys, window_length=win, polyorder=2, mode="interp")

    # Final pass: straighten long near-horizontal segments to remove local jumps.
    ys = _flatten_near_horizontal_segments(ys)
    return ys

def _flatten_near_horizontal_segments(y_values):
    """Line-fit long, near-horizontal runs to suppress staircase artifacts."""
    y = np.asarray(y_values, dtype=float).copy()
    n = len(y)
    if n < FLAT_MIN_RUN:
        return y

    x = np.arange(n, dtype=float)
    slope = np.gradient(y)
    flat = np.abs(slope) <= FLAT_SLOPE_THRESHOLD

    i = 0
    while i < n:
        if not flat[i]:
            i += 1
            continue
        j = i
        while j < n and flat[j]:
            j += 1

        if (j - i) >= FLAT_MIN_RUN:
            xs = x[i:j]
            ys = y[i:j]
            a, b = np.polyfit(xs, ys, 1)
            y_fit = a * xs + b
            y[i:j] = (1.0 - FLAT_FIT_BLEND) * ys + FLAT_FIT_BLEND * y_fit

        i = j

    return y

def _find_shared_boundary_groups(boundaries):
    """Group boundaries that share the exact same raw interface samples."""
    keys = list(boundaries.keys())
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(keys)):
        k1 = keys[i]
        c1 = boundaries[k1]["cols"]
        y1 = boundaries[k1]["y_raw"]
        for j in range(i + 1, len(keys)):
            k2 = keys[j]
            c2 = boundaries[k2]["cols"]
            y2 = boundaries[k2]["y_raw"]

            common, i1, i2 = np.intersect1d(c1, c2, return_indices=True)
            if len(common) < 3:
                continue
            if np.allclose(y1[i1], y2[i2], atol=1e-9):
                union(k1, k2)

    groups = {}
    for k in keys:
        r = find(k)
        groups.setdefault(r, []).append(k)
    return list(groups.values())

def _smooth_shared_boundaries(boundaries):
    """Smooth shared interfaces once so adjacent polygons overlap perfectly."""
    groups = _find_shared_boundary_groups(boundaries)
    assigned = set()

    for members in groups:
        if len(members) == 1:
            continue

        # Build one canonical profile for the shared interface.
        cols_union = np.unique(np.concatenate([boundaries[m]["cols"] for m in members]))
        y_vals = np.zeros_like(cols_union, dtype=float)
        n_vals = np.zeros_like(cols_union, dtype=float)

        col_to_idx = {int(c): i for i, c in enumerate(cols_union)}
        for m in members:
            cols_m = boundaries[m]["cols"]
            y_m = boundaries[m]["y_raw"]
            for c, y in zip(cols_m, y_m):
                idx = col_to_idx[int(c)]
                y_vals[idx] += y
                n_vals[idx] += 1.0

        y_mean = y_vals / np.maximum(n_vals, 1.0)
        y_smooth = _smooth_profile(y_mean)

        # Assign identical smoothed interface values to each member on their own x-support.
        for m in members:
            cols_m = boundaries[m]["cols"]
            boundaries[m]["y_smooth"] = np.interp(cols_m, cols_union, y_smooth)
            assigned.add(m)

    # Non-shared boundaries are smoothed individually.
    for k, b in boundaries.items():
        if k in assigned:
            continue
        boundaries[k]["y_smooth"] = _smooth_profile(b["y_raw"])

# --- Geometry Extraction ---
def load_geometry(h5_path):
    """Load geometry from HDF5 file. Returns (nx, ny, data, dx, dy, dz)."""
    root = Dataset(h5_path, "r")
    data = root["data"][:, :, 0].astype(np.int16)
    root.close()
    
    # Data is stored as [x, y] in the HDF5
    # HDF5 shape 10000x500 @ 0.02m = 200m x 10m (matches gprMax model resolution)
    nx, ny = data.shape
    
    # Use cell spacing that matches the gprMax model (0.02m)
    dx = dy = 0.02
    dz = 0.02
    
    return nx, ny, data, dx, dy, dz

def extract_polygons(geom_data, dx, dy, tolerance):
    """Extract and simplify polygons for each material.
    
    Returns dict: {material_id: [(polygon_id, simplified_points), ...]}
    geom_data shape: (nx, ny) indexed as [x_index, y_index]
    Transpose to [y_index, x_index] for find_contours (image convention).
    """
    results = {}
    nx, ny = geom_data.shape

    # Build all connected components first (across all materials), then enforce
    # shared interfaces globally so neighboring polygons overlap perfectly.
    components = []
    for mat_id in np.unique(geom_data):
        if mat_id < 0:
            continue

        mask_t = (geom_data == mat_id).T.astype(np.uint8)  # [y, x]
        labeled, num_regions = label(mask_t)

        for region_id in range(1, num_regions + 1):
            region_mask = (labeled == region_id)
            cols = np.where(region_mask.any(axis=0))[0]
            if len(cols) < 2:
                continue

            y_top = np.zeros(len(cols), dtype=float)
            y_bot = np.zeros(len(cols), dtype=float)
            for i, c in enumerate(cols):
                ys = np.where(region_mask[:, c])[0]
                # Interface coordinates at cell edges, not centers.
                y_top[i] = ys.min() - 0.5
                y_bot[i] = ys.max() + 0.5

            y_top = np.clip(y_top, 0.0, ny)
            y_bot = np.clip(y_bot, 0.0, ny)

            components.append({
                "mat_id": int(mat_id),
                "poly_id": int(region_id - 1),
                "cols": cols.astype(int),
                "top_raw": y_top,
                "bot_raw": y_bot,
                "top_locked": np.zeros(len(cols), dtype=bool),
                "bot_locked": np.zeros(len(cols), dtype=bool),
                "top_lock_vals": np.zeros(len(cols), dtype=float),
                "bot_lock_vals": np.zeros(len(cols), dtype=float),
            })

    # Lock shared interfaces to identical values between adjacent materials.
    for i in range(len(components)):
        ci = components[i]
        for j in range(i + 1, len(components)):
            cj = components[j]

            common_cols = np.intersect1d(ci["cols"], cj["cols"])
            if len(common_cols) < 3:
                continue

            ibot = np.interp(common_cols, ci["cols"], ci["bot_raw"])
            itop = np.interp(common_cols, ci["cols"], ci["top_raw"])
            jbot = np.interp(common_cols, cj["cols"], cj["bot_raw"])
            jtop = np.interp(common_cols, cj["cols"], cj["top_raw"])

            # Detect which boundary pair is the shared interface.
            d_ibot_jtop = np.mean(np.abs(ibot - jtop))
            d_itop_jbot = np.mean(np.abs(itop - jbot))

            if d_ibot_jtop <= SHARED_INTERFACE_TOL_CELLS:
                shared = _smooth_profile(0.5 * (ibot + jtop))
                ci_idx = np.nonzero(np.isin(ci["cols"], common_cols))[0]
                cj_idx = np.nonzero(np.isin(cj["cols"], common_cols))[0]
                ci["bot_locked"][ci_idx] = True
                cj["top_locked"][cj_idx] = True
                ci["bot_lock_vals"][ci_idx] = shared
                cj["top_lock_vals"][cj_idx] = shared
            elif d_itop_jbot <= SHARED_INTERFACE_TOL_CELLS:
                shared = _smooth_profile(0.5 * (itop + jbot))
                ci_idx = np.nonzero(np.isin(ci["cols"], common_cols))[0]
                cj_idx = np.nonzero(np.isin(cj["cols"], common_cols))[0]
                ci["top_locked"][ci_idx] = True
                cj["bot_locked"][cj_idx] = True
                ci["top_lock_vals"][ci_idx] = shared
                cj["bot_lock_vals"][cj_idx] = shared

    # Finalize each polygon: smooth free parts, keep locked shared parts identical.
    for comp in components:
        cols = comp["cols"]
        y_top = _smooth_profile(comp["top_raw"])
        y_bot = _smooth_profile(comp["bot_raw"])

        top_locked = comp["top_locked"]
        bot_locked = comp["bot_locked"]
        y_top[top_locked] = comp["top_lock_vals"][top_locked]
        y_bot[bot_locked] = comp["bot_lock_vals"][bot_locked]

        top = np.column_stack([cols * dx, y_top * dy])
        bot = np.column_stack([cols[::-1] * dx, y_bot[::-1] * dy])
        poly = np.vstack([top, bot])

        if not np.allclose(poly[0], poly[-1]):
            poly = np.vstack([poly, poly[0]])

        results.setdefault(comp["mat_id"], []).append((comp["poly_id"], poly))

    return results

# --- Output ---
def save_polygons_csv(polygons_dict, output_path, material_names, dx, dy):
    """Save polygons to CSV: material_name, polygon_id, point_order, x, y"""
    with open(output_path, "w") as f:
        f.write("material_name,polygon_id,point_order,x,y\n")
        
        for mat_id in sorted(polygons_dict.keys()):
            mat_name = material_names.get(mat_id, f"material_{mat_id}")
            
            for poly_id, points in polygons_dict[mat_id]:
                for order, (x, y) in enumerate(points):
                    f.write(f"{mat_name},{poly_id},{order},{x:.3f},{y:.3f}\n")

def plot_qc(geom_data, polygons_dict, dx, dy, output_path, material_names, title=""):
    """Generate QC plot: heatmap with original colors + legend.
    
    geom_data shape: (nx, ny) indexed as [x, y].
    For display, transpose to [y, x] to match image convention.
    """
    fig, ax = plt.subplots(figsize=(14, 5))
    
    # Transpose for proper image display: [y, x]
    geom_display = geom_data.T
    nx, ny = geom_data.shape
    
    # Create custom colormap from material colors (normalized 0-1)
    cmap_colors = []
    for mat_id in range(max(MATERIAL_COLORS.keys()) + 1):
        if mat_id in MATERIAL_COLORS:
            rgb = tuple(c / 255.0 for c in MATERIAL_COLORS[mat_id])
            cmap_colors.append(rgb)
        else:
            cmap_colors.append((0.5, 0.5, 0.5))  # fallback gray
    
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(cmap_colors)
    
    # Extent: [left, right, bottom, top] = [xmin, xmax, ymin, ymax]
    extent = [0, nx * dx, ny * dy, 0]
    ax.imshow(geom_display, extent=extent, cmap=cmap, alpha=1.0, origin="upper", vmin=0, vmax=max(MATERIAL_COLORS.keys()))

    # Optional overlay to QC exported boundaries against the filled materials.
    for mat_id in sorted(polygons_dict.keys()):
        for _, points in polygons_dict[mat_id]:
            ax.plot(points[:, 0], points[:, 1], color="black", linewidth=0.6, alpha=0.55)
    
    # Create legend with color patches
    from matplotlib.patches import Patch
    legend_elements = []
    for mat_id in sorted(polygons_dict.keys()):
        mat_name = material_names.get(mat_id, f"material_{mat_id}")
        if mat_id in MATERIAL_COLORS:
            rgb = tuple(c / 255.0 for c in MATERIAL_COLORS[mat_id])
        else:
            rgb = (0.5, 0.5, 0.5)
        legend_elements.append(Patch(facecolor=rgb, label=mat_name))
    
    ax.legend(handles=legend_elements, loc="upper left", fontsize=10, framealpha=0.95)
    
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Polygon Extraction QC - {title}")
    ax.grid(True, alpha=0.3)
    ax.set_aspect("auto")
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"  QC plot saved: {output_path}")
    plt.close()

# --- Main ---
def main():
    if len(sys.argv) != 3:
        print("Usage: python extract_polygons.py <h5_file> <material_file>")
        print()
        print("Examples:")
        print("  python extract_polygons.py wheel_geometry.h5 ../materials/base_sand_material_001.txt")
        print("  python extract_polygons.py wheels_watertable_geometry.h5 ../materials/split_sand_material_001.txt")
        sys.exit(1)
    
    h5_file = sys.argv[1]
    material_file = sys.argv[2]
    
    h5_path = geom_dir / h5_file
    material_path = geom_dir.parent / "materials" / material_file if not Path(material_file).is_absolute() else Path(material_file)
    
    if not h5_path.exists():
        print(f"❌ HDF5 file not found: {h5_path}")
        sys.exit(1)
    
    print(f"\n📂 Processing: {h5_file}")
    
    # Parse material names
    material_names = parse_material_file(material_path)
    print(f"   Parsed {len(material_names)} materials from {material_path.name}")
    
    # Load geometry
    nx, ny, geom_data, dx, dy, dz = load_geometry(h5_path)
    print(f"   Grid size: {nx} × {ny} cells ({nx*dx:.1f}m × {ny*dy:.1f}m)")
    
    # Extract polygons
    polygons = extract_polygons(geom_data, dx, dy, SIMPLIFICATION_TOLERANCE)
    
    # Count polygons
    total_polys = sum(len(plist) for plist in polygons.values())
    print(f"   Materials: {len(polygons)}")
    print(f"   Total regions: {total_polys}")
    
    for mat_id, plist in sorted(polygons.items()):
        mat_name = material_names.get(mat_id, f"material_{mat_id}")
        print(f"     {mat_name}: {len(plist)} region(s)")
    
    # Save CSV
    csv_path = geom_dir / f"{h5_file.replace('.h5', '')}_polygons.csv"
    save_polygons_csv(polygons, csv_path, material_names, dx, dy)
    print(f"  ✓ CSV saved: {csv_path}")
    
    # Generate QC plot
    plot_path = geom_dir / f"{h5_file.replace('.h5', '')}_polygons_qc.png"
    plot_qc(geom_data, polygons, dx, dy, plot_path, material_names, title=h5_file)

if __name__ == "__main__":
    main()
