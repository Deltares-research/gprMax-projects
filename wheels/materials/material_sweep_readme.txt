Split-sand gprMax material sweep: 33-scenario sensitivity set plus separate best estimate

Purpose:
Assess detectability of the base of the sand body for a split-sand model consisting of an upper unsaturated/partly saturated fine strongly silty sand and a lower fully saturated fine strongly silty sand, with clay and peat units beneath.

Required HDF5 ID mapping:
ID 0 = zand_fijn_sterk_siltig_unsaturated
ID 1 = zand_fijn_sterk_siltig_saturated
ID 2 = klei_zwak_tot_sterk_zandig
ID 3 = veen_plaatselijk_kleiig
ID 4 = klei_zwak_tot_sterk_zandig_en_siltig

Files:
- material_sweep_001.txt to material_sweep_032.txt: all low/high edge cases from the 2^5 factorial sensitivity sweep.
- material_sweep_033.txt: centre/reference case from the low-centre-high parameter table.
- material_best_estimate.txt: separate recommended most-realistic model.
- material_sweep_index.csv: index of all sweep files plus the best-estimate file.
- material_parameter_ranges.csv: compact table of low, centre, high and best-estimate parameters.

Parameter ranges used for the sweep:
ID 0: eps_r 8 / 12 / 18, sigma 0.001 / 0.005 / 0.020 S/m
ID 1: eps_r 18 / 25 / 32, sigma 0.030 / 0.080 / 0.150 S/m
ID 2: eps_r 20 / 30 / 40, sigma 0.050 / 0.150 / 0.350 S/m
ID 3: eps_r 50 / 65 / 80, sigma 0.050 / 0.150 / 0.350 S/m
ID 4: eps_r 24 / 35 / 45, sigma 0.080 / 0.250 / 0.600 S/m

Best-estimate model:
ID 0: eps_r 12, sigma 0.010 S/m
ID 1: eps_r 25, sigma 0.080 S/m
ID 2: eps_r 30, sigma 0.150 S/m
ID 3: eps_r 65, sigma 0.150 S/m
ID 4: eps_r 35, sigma 0.250 S/m

Rationale:
The 33-scenario sweep is intended as a full sensitivity envelope: 32 low/high combinations plus one centre/reference file. The separate best-estimate file is not the mathematical centre of the sweep. It is the recommended most-realistic model based on the interpretation that the upper sand is not dune sand, but fine, strongly silty, likely moist and influenced by capillary water. Therefore ID0 sigma is set to 0.010 S/m in the best-estimate model rather than 0.005 S/m.

Use in gprMax:
#include_file: material_sweep_033.txt
or
#include_file: material_best_estimate.txt

Notes:
- mu_r is fixed at 1 and magnetic loss at 0 for all materials.
- Reflection coefficients in the index are approximate normal-incidence magnitudes based only on relative permittivity. They are provided for quick triage and are not full lossy gprMax amplitudes.
