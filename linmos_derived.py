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
PRODUCT = 'co21'
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
