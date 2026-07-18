Base-of-sand gprMax material sensitivity set, 17 runs

Purpose:
Detectability of the base of the sand body, not full geological inversion.
The HDF5 IDs must map in this exact order:
ID 0 = zand_fijn_sterk_siltig
ID 1 = klei_zwak_tot_sterk_zandig
ID 2 = veen_plaatselijk_kleiig
ID 3 = klei_zwak_tot_sterk_zandig_en_siltig

Design:
- 16 two-level edge cases over ID0, ID1, ID2 and ID3.
- 1 centre case: base_sand_material_017.txt.

Why not 81?
This targets reflection-strength and detectability of sand-base interfaces.
For the primary top-of-lower-unit reflection, the key terms are:
- two-way attenuation in the sand above the interface;
- impedance/permittivity contrast at the sand-base interface;
- lossy response of the target medium at the boundary.
Propagation deeper into clay/peat is secondary if you only want the first base-of-sand return.

Use:
#include_file: base_sand_material_017.txt
or swap any base_sand_material_XXX.txt file in your batch script.
