##############################################################################
# Load routines, initialize handlers
##############################################################################

import os
import sys

from astropy.io import fits
from casatasks import casalog

# Initialize mpicasa lazily so skipped chunks can exit cleanly without
# triggering MPI abnormal-termination handling.
_mpi_initialized = False


def init_mpi_if_needed():
    global _mpi_initialized
    if _mpi_initialized:
        return

    import casampi.private.start_mpi  # noqa: F401
    from casampi.MPIEnvironment import MPIEnvironment

    # TODO hook up the logger correctly
    print("MPI server rank list: {}".format(MPIEnvironment.mpi_server_rank_list()))
    _mpi_initialized = True

casalog.showconsole(True)  

# Use boolean flags to set the steps to be performed when the pipeline
# is called. See descriptions below (but only edit here).

print("Starting run_chunk.py")

# Locate the master key
sdir = '/lustre/cv/users/rindebet/local/github/sscales_imaging_VA/'
key_file = sdir+'master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
sys.path.append(os.path.expanduser("/home/casa/contrib/bitbucket/AIV/analysis_scripts/"))
chunksize = 40
stage_overwrite = False


# Pass the target name from the cmd line

if len(sys.argv) != 6:
    # raise ValueError('SLURM processing requires exactly 3 command line arguments: target, stagestring, job_array_id')

    target= 'ngc5236_3'  # default for testing
    stagestring = 'D'  
    chunk_num = 0  # default for testing
    config = "12m+7m"
    product = "13co21"

else:
    target = sys.argv[-5]
    config = sys.argv[-4]
    product = sys.argv[-3]
    stagestring = sys.argv[-2]
    try: 
        chunk_num = int(sys.argv[-1])
    except ValueError:
        chunk_num = -1


imaging_method = "sdintimaging"

do_staging = False
do_imaging = False
do_assemble = False
do_postprocess = False
do_derived = False

from phangsPipeline import handlerKeys as kh
this_kh = kh.KeyHandler(master_key=key_file)

if 'S' in stagestring:
    do_staging = True
    print('Adding STAGING step to this processing run')
    from phangsPipeline import handlerVis as uvh
    this_uvh = uvh.VisHandler(key_handler=this_kh)
    this_uvh.set_targets(only=[target])
    this_uvh.set_interf_configs(only=[config])
    this_uvh.set_line_products(only=[product])
    this_uvh.set_no_cont_products(True)


if 'I' in stagestring:
    do_imaging = True
    print('Adding IMAGING step to this processing run')
    from phangsPipeline import handlerImaging as imh
    from phangsPipeline.handlerImagingChunked import ImagingChunkedHandler
    this_imh = imh.ImagingHandler(key_handler=this_kh)
    this_imh.set_targets(only=[target])
    this_imh.set_interf_configs(only=[config])
    this_imh.set_no_cont_products(True)
    this_imh.set_line_products(only=[product])

if 'A' in stagestring:
    do_assemble = True
    print('Adding ASSEMBLY step to this processing run')
    from phangsPipeline import handlerImaging as imh
    from phangsPipeline.handlerImagingChunked import ImagingChunkedHandler
    this_imh = imh.ImagingHandler(key_handler=this_kh)


if 'P' in stagestring:
    do_postprocess = True
    print('Adding POSTPROCESS step to this processing run')
    from phangsPipeline import handlerPostprocess as pph
    this_pph = pph.PostProcessHandler(key_handler=this_kh)
    this_pph.set_targets(only=[target])
    this_pph.set_interf_configs(only=[config])
    this_pph.set_feather_configs(only=[config])
    this_pph.set_line_products(only=[product])
    this_pph.set_no_cont_products(True)

if 'D' in stagestring:
    do_derived = True
    print('Adding DERIVED step to this processing run')


if target.endswith('.py'):
    raise ValueError('No target set at command line')

from phangsPipeline import phangsLogger as pl
pl.setup_logger(level='DEBUG', logfile=None)

# Imports

# sys.path.insert(1, )

from phangsPipeline import handlerDerived as der


# Initialize the various handler objects. First initialize the
# KeyHandler, which reads the master key and the files linked in the
# master key. Then feed this keyHandler, which has all the project
# data, into the other handlers (VisHandler, ImagingHandler,
# PostProcessHandler), which run the actual pipeline using the project
# definitions from the KeyHandler.


# Make any missing directories

this_kh.make_missing_directories(imaging=True, derived=True, postprocess=True, release=True)

##############################################################################
# Set up what we do this run
##############################################################################


# Set the configs (arrays), spectral products (lines), and targets to
# consider.

# Set the targets. Called with only () it will use all targets. The
# only= , just= , start= , stop= criteria allow one to build a smaller
# list. 

# Set the configs. Set both interf_configs and feather_configs just to
# determine which cubes will be processed. The only effect in this
# derive product calculation is to determine which cubes get fed into
# the calculation.

# Set the line products. Similarly, this just determines which cubes
# are fed in. Right now there's no derived product pipeline focused on
# continuum maps.

# ASIDE: In PHANGS-ALMA we ran a cheap parallelization by running
# several scripts with different start and stop values in parallel. If
# you are running a big batch of jobs you might consider scripting
# something similar.

# Note here that we need to set the targets, configs, and lines for
# *all three* relevant handlers - the VisHandler (uvh), ImagingHandler
# (imh), and PostprocessHandler (pph). The settings below will stage
# combined 12m+7m data sets (including staging C18O and continuum),
# image the CO 2-1 line from these, and then postprocess the CO 2-1
# cubes.







##############################################################################
# Run staging
##############################################################################

# "Stage" the visibility data. This involves copying the original
# calibrated measurement set, continuum subtracting (if requested),
# extraction of requested lines and continuum data, regridding and
# concatenation into a single measurement set. The overwrite=True flag
# is needed to ensure that previous runs can be overwritten.

if do_staging:
    this_uvh.loop_stage_uvdata(do_copy=True, do_contsub=True,
                               do_extract_line=False, do_extract_cont=False,
                               do_remove_staging=False, overwrite=stage_overwrite,
                               intent='*TARGET*')

    this_uvh.loop_stage_uvdata(do_copy=False, do_contsub=False,
                               do_extract_line=True, do_extract_cont=False,
                               do_remove_staging=False, overwrite=stage_overwrite)

    this_uvh.loop_stage_uvdata(do_copy=False, do_contsub=False,
                               do_extract_line=False, do_extract_cont=True,
                               do_remove_staging=False, overwrite=stage_overwrite)

#    this_uvh.loop_stage_uvdata(do_copy=False, do_contsub=False,
#                               do_extract_line=False, do_extract_cont=False,
#                               do_remove_staging=True, overwrite=True)

##############################################################################
# Step through imaging
##############################################################################

# Image the concatenated, regridded visibility data. The full loop
# involves applying any user-supplied clean mask, multiscale imaging,
# mask generation for the single scale clean, and single scale
# clean. The individual parts can be turned on or off with flags to
# the imaging loop call but this call does everything.

if do_imaging:
    this_imh = ImagingChunkedHandler(target, config, product, this_kh,
                                    chunksize=chunksize, imaging_method=imaging_method)
    if chunk_num >= this_imh.nchunks:
        raise ValueError(f"Chunk number {chunk_num} is greater than the number of chunks {this_imh.nchunks}")

    # Guard against re-imaging by checking for chunk products in the
    # permanent imaging directory (not this run's temp dir).
    guard_imh = ImagingChunkedHandler(target, config, product, this_kh,
                                      chunksize=chunksize, imaging_method=imaging_method,
                                      make_temp_dir=False)
    chunk_image_root = guard_imh.chunk_params[chunk_num]['full_imagename']
    if imaging_method == "sdintimaging":
        expected_chunk_image = f"{chunk_image_root}.joint.cube.image"
    elif imaging_method == "tclean":
        expected_chunk_image = f"{chunk_image_root}.image"
    else:
        raise ValueError(f"Unsupported imaging_method for skip guard: {imaging_method}")

    if os.path.exists(expected_chunk_image):
        existing_image = expected_chunk_image
        print(f"Chunk {chunk_num} already imaged: {existing_image}")
        print("Skipping imaging for this chunk.")
    else:
        init_mpi_if_needed()
        print(f"Chunk {chunk_num} of {this_imh.nchunks}")
        this_imh.run_imaging(do_all=True, chunk_num=chunk_num)

if do_assemble:
    this_imh = ImagingChunkedHandler(target, config, product, this_kh,
                                     chunksize=chunksize,
                                     imaging_method=imaging_method,
                                     make_temp_dir=False,
                                     )
    
    # When running per chunk, combining into final cubes is a separate call
    this_imh.task_complete_gather_into_cubes(
        root_name='all',
    )

##############################################################################
# Step through postprocessing
##############################################################################

# Postprocess the data in CASA after imaging. This involves primary
# beam correction, linear mosaicking, feathering, conversion to Kelvin
# units, and some downsampling to save space.

# do_uvcombine

if do_postprocess:
    this_pph.loop_postprocess(do_prep=True, do_feather=False,
                              do_mosaic=True, do_cleanup=True,
                              imaging_method=imaging_method,
                              postprocessing_method="spectralcube")

    pph_fname_dict = this_pph._fname_dict(
        target=target,
        config=config,
        product=product,
        imaging_method=imaging_method,
    )
    intermediate_fits = os.path.join(
        this_kh.get_postprocess_dir_for_target(target),
        pph_fname_dict["pbcorr_trimmed_k"] + ".fits",
    )
    if os.path.exists(intermediate_fits):
        os.remove(intermediate_fits)

if do_derived:
    import astropy
    import spectral_cube

    this_der = der.DerivedHandler(key_handler=this_kh)
    feather_config = this_kh.get_feather_config_for_interf_config(config)
    if feather_config is not None:
        this_der.set_no_interf_configs(True)
        this_der.set_feather_configs(only=[feather_config])
    else:
        this_der.set_no_feather_configs(True)
        this_der.set_interf_configs(only=[config])
    this_der.set_line_products(only=[product])
    this_der.set_targets(only=[target])
    this_der.set_no_cont_products(True)
    
    do_convolve = True
    do_noise = True
    do_strictmask = True
    do_broadmask = True
    do_moments = True
    do_secondary = False

    if do_convolve:
        this_der.loop_derive_products(do_convolve=True, do_noise=False,
                                    do_strictmask=False, do_broadmask=False,
                                    do_moments=False, do_secondary=False) # postprocessing_method="spectralcube" ?

    # Estimate the noise from the signal-free regions of the data to
    # produce a three-dimensional noise model for each cube.

    if do_noise:
        this_der.loop_derive_products(do_convolve=False, do_noise=True,
                                    do_strictmask=False, do_broadmask=False,
                                    do_moments=False, do_secondary=False)

    # Construct "strict masks" for each cube at each resolution.

    if do_strictmask:
        this_der.loop_derive_products(do_convolve=False, do_noise=False,
                                    do_strictmask=True, do_broadmask=False,
                                    do_moments=False, do_secondary=False)

    # Combine the strict masks across all linked resolutions to form
    # "broad masks" that have high completeness.

    if do_broadmask:
        this_der.loop_derive_products(do_convolve=False, do_noise=False,
                                    do_strictmask=False, do_broadmask=True,
                                    do_moments=False, do_secondary=False)

    # Apply the masks and use the cubes and noise models to produce moment
    # maps with associated uncertainty.

    if do_moments:
        this_der.loop_derive_products(do_convolve=False, do_noise=False,
                                    do_strictmask=False, do_broadmask=False,
                                    do_moments=True, do_secondary=False)

    # Run a second round of moment calculations. This enables claculation
    # of moments that depend on other, earlier moment map calculations

    if do_secondary:
        this_der.loop_derive_products(do_convolve=False, do_noise=False,
                                    do_strictmask=False, do_broadmask=False,
                                    do_moments=False, do_secondary=True)

        

