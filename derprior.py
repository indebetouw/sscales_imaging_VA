import os

import sys

from astropy.io import fits
from casatasks import casalog

# initialize mpicasa
import casampi.private.start_mpi
from casampi.MPIEnvironment import MPIEnvironment
# TODO hook up the logger correctly
print("MPI server rank list: {}".format(MPIEnvironment.mpi_server_rank_list()))

casalog.showconsole(True)  

# Use boolean flags to set the steps to be performed when the pipeline
# is called. See descriptions below (but only edit here).

# Locate the master key
sdir = '/lustre/cv/users/rindebet/local/github/phangs_imaging_scripts/'
key_file = sdir+'NRAO/master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
sys.path.append(os.path.expanduser("/home/casa/contrib/bitbucket/AIV/analysis_scripts/"))
stage_overwrite = False


# Pass runtime arguments from the cmd line.
# Required: <target> <config> <product> <stagestring>
# Optional: <prior_product_for_broadmask> (default: co21)

args = sys.argv[1:]
if len(args) not in (5, 6):
    target = 'ngc5236_5'  
    stagestring = 'S'
    config = "12m+7m"
    product = "c18o21"
    prior_product = "13co21"
else:
    target = args[0]
    config = args[1]
    product = args[2]
    stagestring = args[3]

    prior_product = "co21"
    if len(args) == 6:
        prior_product = args[5]

from phangsPipeline import phangsLogger as pl
pl.setup_logger(level='DEBUG', logfile=None)

import shutil

from phangsPipeline import handlerDerived as der
from phangsPipeline import handlerKeys as kh
from phangsPipeline import utilsFilenames


# Minimal derived pass for a non-CO product using an existing prior broad mask.
this_kh = kh.KeyHandler(master_key=key_file)
this_der = der.DerivedHandler(key_handler=this_kh)

this_der.set_interf_configs(only=[config])
this_der.set_feather_configs(only=[config])
this_der.set_line_products(only=[product])
this_der.set_targets(only=[target])
this_der.set_no_cont_products(True)

derived_dir = this_kh.get_derived_dir_for_target(target=target, changeto=False)

prior_broadmask = utilsFilenames.get_cube_filename(
    target=target,
    config=config,
    product=prior_product,
    ext='_broadmask',
    casa=False,
)

line_broadmask = utilsFilenames.get_cube_filename(
    target=target,
    config=config,
    product=product,
    ext='_broadmask',
    casa=False,
)

prior_broadmask_path = os.path.join(derived_dir, prior_broadmask)
line_broadmask_path = os.path.join(derived_dir, line_broadmask)

if not os.path.isfile(prior_broadmask_path):
    raise FileNotFoundError(
        f"Missing prior broad mask for {prior_product}: {prior_broadmask_path}. "
        f"Run derived for {prior_product} first."
    )

if prior_broadmask_path != line_broadmask_path:
    if stage_overwrite or (not os.path.isfile(line_broadmask_path)):
        shutil.copy2(prior_broadmask_path, line_broadmask_path)

# Generate into a separate filename namespace so prior-based products do not
# overwrite products generated with a different mask strategy.
prior_ext = f"_prior_{prior_product}"
print(f"Using prior product '{prior_product}' with output suffix '{prior_ext}'.")

tagged_line_broadmask = utilsFilenames.get_cube_filename(
    target=target,
    config=config,
    product=product,
    ext=f"{prior_ext}_broadmask",
    casa=False,
)
tagged_line_broadmask_path = os.path.join(derived_dir, tagged_line_broadmask)

if line_broadmask_path != tagged_line_broadmask_path:
    if stage_overwrite or (not os.path.isfile(tagged_line_broadmask_path)):
        shutil.copy2(line_broadmask_path, tagged_line_broadmask_path)

# Generate only the configured moment products (including tpeak products)
# for the selected non-CO line using the copied broad mask.
this_der.loop_derive_products(
    do_convolve=False,
    do_noise=False,
    do_strictmask=False,
    do_broadmask=False,
    do_moments=True,
    do_secondary=False,
    extra_ext=prior_ext,
)
