import os
import sys
from glob import glob

# Locate the master key
sdir = '/lustre/cv/users/rindebet/local/github/sscales_imaging_VA/'
key_file = sdir + 'master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
# this has to be appended before importing phangsPipeline
sys.path.append(os.path.expanduser('/home/casa/contrib/bitbucket/AIV/analysis_scripts/'))

from phangsPipeline import handlerDerived as der
from phangsPipeline import handlerKeys as kh
from phangsPipeline import phangsLogger as pl
from phangsPipeline import handlerPostprocess as pp


pl.setup_logger(level='DEBUG', logfile=None)


TARGET = 'ngc5236'
PRODUCT = 'co21'

# Optional override. Set to None to infer config from postprocess products.
CONFIG_OVERRIDE = None
RUN_DERIVED = True


def run_postprocess_and_derived(
    key_handler,
    target,
    product,
    config,
    target_post_dir,
    run_derived=True,
):
    """Run postprocess compression/unit conversion and optional derived pass."""

    # The derived pipeline expects the postprocess products created by the
    # standard postprocess steps: compress -> convert_jytok -> derived.
    postprocess_handler = pp.PostProcessHandler(key_handler=key_handler)
    postprocess_handler.set_targets(only=[target])
    postprocess_handler.set_interf_configs(only=[config])
    postprocess_handler.set_feather_configs(only=[config])
    postprocess_handler.set_line_products(only=[product])
    postprocess_handler.set_no_cont_products(True)

    postprocess_handler.task_compress(
        target=target,
        product=product,
        config=config,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )
    postprocess_handler.task_convert_units(
        target=target,
        product=product,
        config=config,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )

    derived_input = os.path.join(
        target_post_dir,
        f'{target}_{config}_{product}_pbcorr_trimmed_k.fits',
    )
    if not os.path.exists(derived_input):
        raise FileNotFoundError(
            'Missing postprocess input for derived products after running task_compress/task_convert_units: '
            f'{derived_input}'
        )

    if run_derived:
        derived_handler = der.DerivedHandler(key_handler=key_handler)
        derived_handler.set_targets(only=[target])
        derived_handler.set_interf_configs(only=[config])
        derived_handler.set_feather_configs(only=[config])
        derived_handler.set_line_products(only=[product])
        derived_handler.set_no_cont_products(True)

        derived_handler.loop_derive_products(
            do_convolve=True,
            do_noise=True,
            do_strictmask=True,
            do_broadmask=True,
            do_moments=True,
            do_secondary=True,
            do_vfield=True,
            do_shuffling=False,
            do_flatmask=True,
            do_flatmaps=True,
            make_directories=True,
            overwrite=True,
        )


def infer_config(target_post_dir, target, product):
    """Infer config from postprocess products in the target postprocess directory."""

    patterns = [
        os.path.join(target_post_dir, f'{target}_*_{product}_pbcorr_trimmed_k.fits'),
        os.path.join(target_post_dir, f'{target}_*_{product}_pbcorr_round.image.fits'),
    ]

    configs = set()
    for pattern in patterns:
        for path in glob(pattern):
            name = os.path.basename(path)
            if name.startswith(f'{target}_') and f'_{product}_' in name:
                config = name[len(target) + 1 : name.index(f'_{product}_')]
                configs.add(config)

    if len(configs) != 1:
        raise RuntimeError(
            f'Could not uniquely infer config for {target}/{product} in {target_post_dir}. '
            f'Candidates: {sorted(configs)}'
        )

    return next(iter(configs))


def main():
    key_handler = kh.KeyHandler(master_key=key_file)
    target_post_dir = key_handler.get_postprocess_dir_for_target(target=TARGET, changeto=False)

    config = CONFIG_OVERRIDE or infer_config(target_post_dir, TARGET, PRODUCT)

    print(f'Running derived helper for target={TARGET}, product={PRODUCT}, config={config}')
    run_postprocess_and_derived(
        key_handler=key_handler,
        target=TARGET,
        product=PRODUCT,
        config=config,
        target_post_dir=target_post_dir,
        run_derived=RUN_DERIVED,
    )


if __name__ == '__main__':
    main()
