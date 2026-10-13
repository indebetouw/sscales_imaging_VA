import os
import sys

from casatasks import casalog

# initialize mpicasa
import casampi.private.start_mpi
from casampi.MPIEnvironment import MPIEnvironment

sys.path.append(os.path.expanduser("/home/casa/contrib/bitbucket/AIV/analysis_scripts/"))

# TODO hook up the logger correctly
print("MPI server rank list: {}".format(MPIEnvironment.mpi_server_rank_list()))

casalog.showconsole(True)

# Locate the master key
sdir = '/lustre/cv/users/rindebet/local/github/sscales_imaging_VA/'
key_file = sdir + 'master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
sys.path.append(os.path.expanduser('/home/casa/contrib/bitbucket/AIV/analysis_scripts/'))
sys.path.append('/lustre/cv/users/rindebet/local/github/phangs_imaging_scripts')

from phangsPipeline import handlerKeys as kh
from phangsPipeline import handlerPostprocess as pp
from phangsPipeline import phangsLogger as pl

pl.setup_logger(level='DEBUG', logfile=None)

TARGET = 'ngc5236'
PRODUCT = 'co21'
CONFIG = '12m+7m+tp'
POSTPROCESS_CONFIG = '12m+7m+tp'
CONVOLVE_METHOD = 'convolve_uv'


def main():
    this_kh = kh.KeyHandler(master_key=key_file)

    if not this_kh.is_target_linmos(TARGET):
        raise ValueError(
            f'{TARGET} is not defined as a linear mosaic target in {key_file}. '
            'Add it to linearmosaic_definitions.txt and define the corresponding part targets.'
        )

    parts = this_kh.get_parts_for_linmos(TARGET)
    if not parts:
        raise RuntimeError(f'No parts found for linmos target {TARGET}.')

    print(f'Linear mosaic target: {TARGET}')
    print(f'Line product: {PRODUCT}')
    print(f'Config: {CONFIG}')
    print(f'Using parts: {", ".join(parts)}')

    postprocess_handler = pp.PostProcessHandler(key_handler=this_kh)
    postprocess_handler.set_targets(only=[TARGET])
    postprocess_handler.set_interf_configs(only=[CONFIG])
    postprocess_handler.set_feather_configs(only=[POSTPROCESS_CONFIG])
    postprocess_handler.set_line_products(only=[PRODUCT])
    postprocess_handler.set_no_cont_products(True)

    # This is the PHANGS linear-mosaic recipe: it loops over the part tiles in
    # the linmos key, convolves them to a common resolution, aligns them to a
    # common grid, creates weight cubes, and mosaics them together.
    postprocess_handler.recipe_mosaic_one_target(
        target=TARGET,
        product=PRODUCT,
        config=CONFIG,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        convolve_method=CONVOLVE_METHOD,
        copy_weights=False,
        check_files=True,
    )

    # Continue through the normal postprocess cleanup path so the final fitted
    # product is written with the expected pbcorr_trimmed_k naming.
    postprocess_handler.task_compress(
        target=TARGET,
        product=PRODUCT,
        config=CONFIG,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )
    postprocess_handler.task_convert_units(
        target=TARGET,
        product=PRODUCT,
        config=CONFIG,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )
    postprocess_handler.task_export_to_fits(
        target=TARGET,
        product=PRODUCT,
        config=CONFIG,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )

    final_cube = os.path.join(
        this_kh.get_postprocess_dir_for_target(target=TARGET, changeto=False),
        f'{TARGET}_{POSTPROCESS_CONFIG}_{PRODUCT}_pbcorr_trimmed_k.fits',
    )
    print(f'Created linear-mosaic product: {final_cube}')


if __name__ == '__main__':
    main()
