import casatools
from casatasks import *
import numpy as np
import os
import matplotlib.pyplot as pl
pl.ion()

tb=casatools.table()

vis="/lustre/cv/users/rindebet/galaxies/array_reduction/ngc5236/ngc5236_5_12m+7m_co21.ms"

tb.open(vis)
uvw=tb.getcol("UVW")  # in meters
fld=tb.getcol("FIELD_ID")
obsID=tb.getcol("OBSERVATION_ID")
tb.done()



imsize=[2880,2560]

maxu=np.maximum(np.absolute(uvw[0].max()),np.absolute(uvw[0].min()))
maxv=np.maximum(np.absolute(uvw[1].max()),np.absolute(uvw[1].min()))

pl.clf()

# Prepare common bin edges and radial binning (shared for all fields)
nx, ny = imsize
xedges = np.linspace(-maxu, maxu, nx + 1)
yedges = np.linspace(-maxv, maxv, ny + 1)
xcenters = 0.5 * (xedges[:-1] + xedges[1:])
ycenters = 0.5 * (yedges[:-1] + yedges[1:])

# Build meshgrid matching histogram2d output shape (x bins first)
xx, yy = np.meshgrid(xcenters, ycenters, indexing='ij')
r = np.sqrt(xx**2 + yy**2)
r_flat = r.ravel(order='C')

dr = np.mean(np.diff(xcenters))
rbins = np.arange(0.0, r_flat.max() + 2.0 * dr, dr)
ridx = np.digitize(r_flat, rbins) - 1
mask_r = (ridx >= 0) & (ridx < len(rbins) - 1)

radii_full = 0.5 * (rbins[:-1] + rbins[1:])

cache_name = f"uvdist_imsize_{nx}x{ny}.npz"
if os.path.exists(cache_name):
	print(f"Loading cached uvdist data from {cache_name}")
	data = np.load(cache_name, allow_pickle=True)
	fields_list = data["fields_list"].tolist()
	# Ensure loaded arrays have the expected dtypes
	radial_means = [np.asarray(arr, dtype=float) for arr in data["radial_means"]]
	radial_valids = [np.asarray(arr, dtype=bool) for arr in data["radial_valids"]]
	radial_maxes = [np.asarray(arr, dtype=float) for arr in data["radial_maxes"]]
	# total_radial_sum is stored per-obsID (first axis) — require obs_list
	total_radial_sum = np.asarray(data["total_radial_sum"], dtype=float)
	obs_list = data["obs_list"].tolist()
	radial_count = data["radial_count"]
	radii_full = data["radii_full"]
else:
	# Loop over fields, compute 2D histogram and azimuthal average for each
	fields = np.unique(fld)
	radial_means = []
	radial_valids = []
	radial_maxes = []
	fields_list = []
	radial_count = np.bincount(ridx[mask_r], minlength=len(rbins) - 1)
	# Track total radial sums independently for each OBSERVATION_ID
	obs_list = np.unique(obsID)
	total_radial_sum = np.zeros((len(obs_list), len(rbins) - 1), dtype=float)
	for f in fields:
		print(f)
		sel = (fld == f)
		if not np.any(sel):
			continue
		# 2D histogram of UV coordinates for this field
		h, _, _ = np.histogram2d(uvw[0][sel], uvw[1][sel], bins=[xedges, yedges])
		h_flat = h.ravel(order='C')

		# Sum counts in radial bins (per-field)
		radial_sum = np.bincount(ridx[mask_r], weights=h_flat[mask_r], minlength=len(rbins) - 1)
		valid = radial_count > 0
		radial_mean_full = np.zeros(len(rbins) - 1, dtype=float)
		radial_mean_full[valid] = radial_sum[valid] / radial_count[valid]

		# Maximum bin count at each radius
		radial_max_full = np.zeros(len(rbins) - 1, dtype=float)
		for ridx_i, count in zip(ridx[mask_r], h_flat[mask_r]):
			if count > radial_max_full[ridx_i]:
				radial_max_full[ridx_i] = count

		radial_means.append(radial_mean_full)
		radial_valids.append(valid)
		radial_maxes.append(radial_max_full)
		fields_list.append(f)

	# Now compute per-obsID total radial sums (summing all samples belonging to each obsID)
	for i, o in enumerate(obs_list):
		sel_obs = (obsID == o)
		if not np.any(sel_obs):
			continue
		h_obs, _, _ = np.histogram2d(uvw[0][sel_obs], uvw[1][sel_obs], bins=[xedges, yedges])
		h_flat_obs = h_obs.ravel(order='C')
		radial_sum_obs = np.bincount(ridx[mask_r], weights=h_flat_obs[mask_r], minlength=len(rbins) - 1)
		total_radial_sum[i, :] = radial_sum_obs

	np.savez_compressed(
		cache_name,
		fields_list=np.array(fields_list, dtype=object),
		radial_means=np.array(radial_means, dtype=object),
		radial_valids=np.array(radial_valids, dtype=object),
		radial_maxes=np.array(radial_maxes, dtype=object),
		total_radial_sum=total_radial_sum,
		obs_list=np.array(obs_list, dtype=object),
		radial_count=radial_count,
		radii_full=radii_full,
	)

# Plot all azimuthally averaged profiles at the end
pl.figure(1)
pl.subplot(211)
for f, mean, valid in zip(fields_list, radial_means, radial_valids):
	pl.plot(radii_full[valid], mean[valid], label=str(int(f)))
pl.xlabel('Radius [m]')
pl.ylabel('Azimuthal average of UV histogram')
pl.title('Azimuthal average of UV histogram (per field)')
#pl.legend(title='FIELD_ID',prop={'size': 6})
pl.grid(True)
pl.subplot(212)
for f, rmax, valid in zip(fields_list, radial_maxes, radial_valids):
	pl.plot(radii_full[valid], rmax[valid], label=str(int(f)))
pl.xlabel('Radius [m]')
pl.ylabel('Azimuthal maximum of UV histogram')
pl.title('Azimuthal maximum of UV histogram (per field)')
#pl.legend(title='FIELD_ID',prop={'size': 6})
pl.grid(True)

pl.savefig("m83_5_radial_uv_histogram_perfield.png", dpi=300)

pl.figure(2)
pl.clf()

# Plot radial means for grouped OBSERVATION_ID sets
valid_all = radial_count > 0
obs_groups = {
    '0-4': [0, 1, 2, 3, 4],
    '4+6': [4, 6],
    '7+8': [7, 8],
}
def smooth_profile(profile, window=11):
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(profile, kernel, mode='same')

for label, group_ids in obs_groups.items():
    mask = np.isin(obs_list, group_ids)
    if not np.any(mask):
        continue
    group_sum = total_radial_sum[mask].sum(axis=0)
    radial_mean_group = np.zeros(len(rbins) - 1, dtype=float)
    radial_mean_group[valid_all] = group_sum[valid_all] / radial_count[valid_all]
    radial_mean_group = smooth_profile(radial_mean_group, window=11)
    pl.plot(radii_full[valid_all], radial_mean_group[valid_all]/radial_mean_group[valid_all].sum(), label=label)

pl.xlabel('Radius [m]')
pl.ylabel('Azimuthal average of UV histogram')
pl.title('Azimuthal average of UV histogram (grouped OBSERVATION_IDs)')
pl.xscale("log")
pl.xlim(8,1e3)
pl.ylim(0,0.02)
pl.grid(True)
pl.legend()
pl.savefig("m83_5_radial_uv_histogram_obsID_groups.png", dpi=300)

import pdb
pdb.set_trace()
