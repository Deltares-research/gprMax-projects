Split-sand gprMax material sensitivity set, 17 runs

Purpose:
Detectability of the base of the sand body after splitting the original top sand into an upper unsaturated/partly saturated sand and a lower fully saturated sand.

Required HDF5 ID mapping:
ID 0 = zand_boven_onverzadigd_deels_verzadigd
ID 1 = zand_onder_verzadigd_fijn_sterk_siltig
ID 2 = klei_zwak_tot_sterk_zandig
ID 3 = veen_plaatselijk_kleiig
ID 4 = klei_zwak_tot_sterk_zandig_en_siltig

Design:
- 12 one-factor screening cases.
- 1 centre case: split_sand_material_013.txt.
- 4 combined interpretive cases: best, worst, low-contrast targets, high-loss case.
- Total: 17 runs.

Use:
#include_file: split_sand_material_013.txt
or swap any split_sand_material_XXX.txt file in your batch script.

Notes:
- The lower sand is always saturated in all runs.
- The upper sand ranges from unsaturated/drier to strongly moist/nearly saturated.
- Clay and peat ranges follow the previous 4-material strategy.
- The index CSV includes approximate normal-incidence reflection coefficients based only on relative permittivity. These are quick triage numbers, not full lossy gprMax amplitudes.
