"""Regenerate wheels/geometries/wheel_geometry.h5 from wheels/data/traced_section_boundaries_flat_surface_v2.png.

This script is generated from the original Copilot extraction workflow.
It expects to be run from the repository root:

    python wheels/scripts/create_geometry.py

The exported HDF5 uses:
    /data, int16, shape = (2000, 100, 1)
    dx_dy_dz = (0.1, 0.1, 0.1)

Depth is represented by the gprMax y coordinate. The z direction is one invariant cell.
"""

from pathlib import Path
from PIL import Image
import numpy as np
from netCDF4 import Dataset
from scipy.ndimage import median_filter
import pandas as pd

repo = Path(__file__).resolve().parents[2]
src_img = repo / "wheels" / "data" / "traced_section_boundaries_flat_surface_v2.png"
out_h5 = repo / "wheels" / "geometries" / "wheel_geometry.h5"
out_csv = repo / "wheels" / "geometries" / "wheel_material_id_mapping.csv"
out_mat = repo / "wheels" / "models" / "materials.txt"

img = Image.open(src_img).convert("RGB")
arr = np.array(img)

x0_px = 134.0
x200_px = 1609.0
y0_px = 67.0
y10_px = 451.0

xmin, xmax = 0.0, 200.0
zmin, zmax = 0.0, 10.0
dx = dy = dz = 0.1
nx = int(round((xmax-xmin)/dx))
ny = int(round((zmax-zmin)/dy))
nz = 1

xc = xmin + (np.arange(nx)+0.5)*dx
zc = zmin + (np.arange(ny)+0.5)*dy
px = x0_px + (xc-xmin)/(xmax-xmin)*(x200_px-x0_px)
py = y0_px + (zc-zmin)/(zmax-zmin)*(y10_px-y0_px)

palette = np.array([
    [255,240,160],
    [207,229,245],
    [154,100, 58],
    [146,170,163],
], dtype=np.float32)
mat_names = ["pale_yellow_top", "light_blue", "brown", "grey_green"]

geom2d = np.empty((nx, ny), dtype=np.int16)
py_round = np.clip(np.rint(py).astype(int), 0, arr.shape[0]-1)
r = 3
for ix, px_i in enumerate(px):
    pxi = int(round(px_i))
    pxi = max(0, min(arr.shape[1]-1, pxi))
    for iy, pyi in enumerate(py_round):
        xlo = max(0, pxi-r); xhi = min(arr.shape[1], pxi+r+1)
        ylo = max(0, pyi-r); yhi = min(arr.shape[0], pyi+r+1)
        colours = arr[ylo:yhi, xlo:xhi, :].reshape(-1, 3).astype(np.float32)
        valid = ~((colours.max(axis=1) < 40) | (colours.min(axis=1) > 245))
        if valid.sum() >= 5:
            colours = colours[valid]
        d2 = ((colours[:,None,:] - palette[None,:,:])**2).sum(axis=2)
        labels = np.argmin(d2, axis=1)
        geom2d[ix, iy] = np.bincount(labels, minlength=len(palette)).argmax()

geom2d = median_filter(geom2d, size=(3, 3)).astype(np.int16)
data = geom2d[:, :, None]

out_h5.parent.mkdir(parents=True, exist_ok=True)
root = Dataset(out_h5, "w", format="NETCDF4")
root.createDimension("x", nx)
root.createDimension("y", ny)
root.createDimension("z", nz)
var = root.createVariable("data", "i2", ("x", "y", "z"), zlib=True, complevel=4)
var[:] = data
root.setncattr("dx_dy_dz", np.array([dx, dy, dz], dtype="f8"))
root.setncattr("source_image", src_img.name)
root.setncattr("physical_extent_x_m", np.array([xmin, xmax], dtype="f8"))
root.setncattr("physical_extent_depth_m", np.array([zmin, zmax], dtype="f8"))
root.setncattr("note", "2D x-depth section; depth stored as gprMax y dimension; z is one invariant cell.")
root.close()

pd.DataFrame({
    "material_id_in_h5": range(len(mat_names)),
    "material_name_in_materials_txt": mat_names,
    "rgb_from_source_png": [",".join(map(str, map(int, c))) for c in palette],
    "note": ["physical properties not assigned"]*len(mat_names),
}).to_csv(out_csv, index=False)

with open(out_mat, "w") as f:
    f.write("## gprMax material file for wheels/models/wheels.in\n")
    f.write("## IMPORTANT: eps_r, conductivity, mu_r, magnetic_loss are placeholders. Edit before scientific use.\n")
    f.write("## The order must match wheel_geometry.h5 /data integer IDs: 0, 1, 2, 3.\n")
    for name in mat_names:
        f.write("#material: 1.0 0.0 1.0 0.0 " + name + "\n")

print(f"Wrote {out_h5}")
print(f"Wrote {out_csv}")
print(f"Wrote {out_mat}")
