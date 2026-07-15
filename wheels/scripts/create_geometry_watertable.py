"""Generate wheels_watertable_geometry.h5 with water table subdivision.

This script loads wheel_geometry.h5 and subdivides the top yellow layer (orig ID 0)
into two materials:
  - ID 0: sand_saturated (0-3m depth, or to interface if shallower)
  - ID 1: yellow_dry (below water table)
  
Other materials are renumbered:
  - ID 2: light_blue (was 1)
  - ID 3: brown (was 2)
  - ID 4: grey_green (was 3)

The water table follows the yellow/light_blue interface where it's < 3m.

Run from repository root:
    python wheels/scripts/create_geometry_watertable.py
"""

from pathlib import Path
from netCDF4 import Dataset
import numpy as np

repo = Path(__file__).resolve().parents[2]
in_h5 = repo / "wheels" / "geometries" / "wheel_geometry.h5"
out_h5 = repo / "wheels" / "geometries" / "wheels_watertable_geometry.h5"
out_mat = repo / "wheels" / "models" / "materials_watertable.txt"

# Load original geometry
fin = Dataset(in_h5, "r")
orig_data = fin.variables["data"][:]
dx_dy_dz = fin.getncattr("dx_dy_dz")
fin.close()

nx, ny, nz = orig_data.shape
dy = dx_dy_dz[1]  # depth resolution in meters
water_table_depth_m = 3.0  # meters

# Create output array
data = orig_data.copy()

# For each x-column, find water table boundary
for ix in range(nx):
    column = orig_data[ix, :, 0]
    
    # Find boundary between orig ID 0 (yellow) and ID 1 (light_blue) from top
    interface_y_idx = None
    for iy in range(ny - 1):
        if column[iy] == 0 and column[iy + 1] == 1:
            interface_y_idx = iy + 1  # Index where interface occurs
            break
    
    # Determine water table depth for this column
    if interface_y_idx is not None:
        interface_depth_m = interface_y_idx * dy
        water_table_y_idx = min(interface_y_idx, int(round(water_table_depth_m / dy)))
    else:
        water_table_y_idx = int(round(water_table_depth_m / dy))
    
    # Remap materials in this column
    for iy in range(ny):
        orig_id = orig_data[ix, iy, 0]
        
        if orig_id == 0:  # Yellow layer
            if iy < water_table_y_idx:
                data[ix, iy, 0] = 0  # sand_saturated
            else:
                data[ix, iy, 0] = 1  # yellow_dry
        elif orig_id == 1:
            data[ix, iy, 0] = 2  # light_blue
        elif orig_id == 2:
            data[ix, iy, 0] = 3  # brown
        elif orig_id == 3:
            data[ix, iy, 0] = 4  # grey_green

# Write HDF5 file
out_h5.parent.mkdir(parents=True, exist_ok=True)
root = Dataset(out_h5, "w", format="NETCDF4")
root.createDimension("x", nx)
root.createDimension("y", ny)
root.createDimension("z", nz)
var = root.createVariable("data", "i2", ("x", "y", "z"), zlib=True, complevel=4)
var[:] = data
root.setncattr("dx_dy_dz", dx_dy_dz)
root.setncattr("note", "2D x-depth section with water table; depth stored as gprMax y dimension; z is one invariant cell.")
root.close()

# Write materials file
mat_names = ["sand_saturated", "yellow_dry", "light_blue", "brown", "grey_green"]
with open(out_mat, "w") as f:
    f.write("## gprMax material file for wheels/models/wheels_watertable.in\n")
    f.write("## IMPORTANT: eps_r, conductivity, mu_r, magnetic_loss are placeholders. Edit before scientific use.\n")
    f.write("## The order must match wheels_watertable_geometry.h5 /data integer IDs: 0, 1, 2, 3, 4.\n")
    for name in mat_names:
        f.write("#material: 1.0 0.0 1.0 0.0 " + name + "\n")

print(f"Wrote {out_h5}")
print(f"Wrote {out_mat}")
