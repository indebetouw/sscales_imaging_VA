import os
import sys

from casatasks import casalog

# initialize mpicasa
import casampi.private.start_mpi
from casampi.MPIEnvironment import MPIEnvironment

# TODO hook up the logger correctly
print("MPI server rank list: {}".format(MPIEnvironment.mpi_server_rank_list()))

casalog.showconsole(True)

# Locate the master key
sdir = '/lustre/cv/users/rindebet/local/github/phangs_imaging_scripts/'
key_file = sdir + 'NRAO/master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
sys.path.append(os.path.expanduser('/home/casa/contrib/bitbucket/AIV/analysis_scripts/'))

from phangsPipeline import handlerDerived as der
from phangsPipeline import handlerKeys as kh
from phangsPipeline import handlerPostprocess as pp
from phangsPipeline import phangsLogger as pl

pl.setup_logger(level='DEBUG', logfile=None)


TARGET = 'ngc5236'
CONFIG = '12m+7m'
PRODUCT = '13co21'


def discover_linmos_parts(target, imaging_root):
	"""Find on-disk mosaic parts for a target."""

	prefix = f'{target}_'
	parts = []

	for entry in sorted(os.listdir(imaging_root)):
		if not entry.startswith(prefix):
			continue
		if not os.path.isdir(os.path.join(imaging_root, entry)):
			continue
		parts.append(entry)

	return parts


def register_linmos_target(this_kh, target, parts):
	"""Register a linear-mosaic target in-memory for this run."""

	this_kh._linmos_dict = {target: parts}
	this_kh._mosaic_assign_dict = {part: target for part in parts}


def main():
	this_kh = kh.KeyHandler(master_key=key_file)

	imaging_root = this_kh.get_imaging_dir_for_target(target=TARGET, changeto=False)
	derived_root = this_kh.get_derived_dir_for_target(target=TARGET, changeto=False)

	if not os.path.isdir(imaging_root):
		raise FileNotFoundError(f'Missing imaging directory: {imaging_root}')
	if not os.path.isdir(derived_root):
		os.makedirs(derived_root, exist_ok=True)

	mosaic_parts = discover_linmos_parts(TARGET, "/".join(imaging_root.split("/")[:-2]))
	if len(mosaic_parts) == 0:
		raise RuntimeError(
			f'No ngc5236_* mosaic parts found under {imaging_root}'
		)

	register_linmos_target(this_kh, TARGET, mosaic_parts)

	print(f'Linear mosaic target: {TARGET}')
	print(f'Line product: {PRODUCT}')
	print(f'Using parts: {", ".join(mosaic_parts)}')
	print(f'Derived output directory: {derived_root}')

	postprocess_handler = pp.PostProcessHandler(key_handler=this_kh)
	postprocess_handler.set_targets(only=[TARGET])
	postprocess_handler.set_interf_configs(only=[CONFIG])
	postprocess_handler.set_feather_configs(only=[CONFIG])
	postprocess_handler.set_line_products(only=[PRODUCT])
	postprocess_handler.set_no_cont_products(True)

	postprocess_handler.loop_postprocess(
		do_prep=False,
		do_feather=False,
		do_mosaic=True,
		do_cleanup=False,
		imaging_method='sdintimaging',
		postprocessing_method='casa',
		convolve_method='convolve_fft',
	)

	derived_handler = der.DerivedHandler(key_handler=this_kh)
	derived_handler.set_targets(only=[TARGET])
	derived_handler.set_interf_configs(only=[CONFIG])
	derived_handler.set_feather_configs(only=[CONFIG])
	derived_handler.set_line_products(only=[PRODUCT])
	derived_handler.set_no_cont_products(True)

	derived_handler.loop_derive_products(
		do_convolve=True,
		do_noise=True,
		do_strictmask=True,
		do_broadmask=True,
		do_moments=True,
		do_secondary=True,
		do_vfield=False,
		do_shuffling=False,
		do_flatmask=False,
		do_flatmaps=False,
		make_directories=True,
		overwrite=True,
	)


if __name__ == '__main__':
	main()

