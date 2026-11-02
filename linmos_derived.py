import os
import sys

# Locate the master key.
# This follows the same local import pattern used by the linmos runner.
sdir = '/lustre/cv/users/rindebet/local/github/sscales_imaging_VA/'
key_file = sdir + 'master_key_sscales.txt'
sys.path.append(os.path.expanduser(sdir))
sys.path.append(os.path.expanduser('/home/casa/contrib/bitbucket/AIV/analysis_scripts/'))

from phangsPipeline import handlerDerived as der
from phangsPipeline import handlerKeys as kh
from phangsPipeline import phangsLogger as pl

pl.setup_logger(level='DEBUG', logfile=None)

TARGET = 'ngc5236'
PRODUCT = 'c18o21'
CONFIG = '12m+7m+tp'
RUN_DERIVED = True


def run_derived_only(key_handler, target, product, config, run_derived=True):
    """Run only the derived-product pipeline for a target/product/config pair."""
    derived_handler = der.DerivedHandler(key_handler=key_handler)
    derived_handler.set_targets(only=[target])
    derived_handler.set_interf_configs(only=[config])
    derived_handler.set_feather_configs(only=[config])
    derived_handler.set_line_products(only=[product])
    derived_handler.set_no_cont_products(True)

    if not run_derived:
        return

    do_vfield = (product == 'co21')

    # Pass 1: core derived products (round 1, plus round 2 where applicable).
    # For non-CO products, skip secondary moments to avoid routing flat moments
    # through the secondary-moment path.
    derived_handler.loop_derive_products(
        do_convolve=True,
        do_noise=True,
        do_strictmask=True,
        do_broadmask=True,
        do_moments=True,
        do_secondary=do_vfield,
        do_vfield=do_vfield,
        do_shuffling=False,
        do_flatmask=False,
        do_flatmaps=False,
        make_directories=True,
        overwrite=True,
    )

    # Pass 2: flat products (round 3 / flatmask + flatmaps).
    derived_handler.loop_derive_products(
        do_convolve=False,
        do_noise=False,
        do_strictmask=False,
        do_broadmask=False,
        do_moments=False,
        do_secondary=False,
        do_vfield=False,
        do_shuffling=False,
        do_flatmask=True,
        do_flatmaps=True,
        make_directories=True,
        overwrite=True,
    )
 

def main():
    key_handler = kh.KeyHandler(master_key=key_file)

    print(f'Running derived-only helper for target={TARGET}, product={PRODUCT}, config={CONFIG}')
    run_derived_only(
        key_handler=key_handler,
        target=TARGET,
        product=PRODUCT,
        config=CONFIG,
        run_derived=RUN_DERIVED,
    )


if __name__ == '__main__':
    main()
