import os
import re
import shutil
import sys
from glob import glob

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

from phangsPipeline import handlerDerived as der
from phangsPipeline import handlerKeys as kh
from phangsPipeline import handlerPostprocess as pp
from phangsPipeline import phangsLogger as pl
from phangsPipeline.scMosaicRoutines import (
    common_grid_for_mosaic,
    common_res_for_mosaic,
    generate_weight_file,
    mosaic_aligned_data,
)

pl.setup_logger(level='DEBUG', logfile=None)


TARGET = 'ngc5236'
PRODUCT = 'co21'

# Optional override. Set to None to infer from part filenames.
CONFIG_OVERRIDE = None

CONVOLVE_METHOD = 'convolve_uv'
RUN_DERIVED = True
RECALCULATE = False


def discover_post_parts(target, post_root):
    """Find postprocess part directories for a target (e.g., ngc5236_1)."""

    prefix = f'{target}_'
    parts = []

    for entry in sorted(os.listdir(post_root)):
        if not entry.startswith(prefix):
            continue
        if not os.path.isdir(os.path.join(post_root, entry)):
            continue
        parts.append(entry)

    return parts


def infer_config(post_root, parts, product):
    """Infer config from files like <part>_<config>_<product>_pbcorr_round.image.fits."""

    part_configs = []
    for part in parts:
        part_dir = os.path.join(post_root, part)
        pattern = os.path.join(part_dir, f'{part}_*_{product}_pbcorr_round.image.fits')
        matches = [os.path.basename(m) for m in glob(pattern)]
        if len(matches) == 0:
            print(f'No pbcorr_round FITS found for part {part} and product {product} in {part_dir}')
            continue

        configs_this_part = set()
        for name in matches:
            pattern_re = rf'^{re.escape(part)}_(.+)_{re.escape(product)}_pbcorr_round\.image\.fits$'
            match = re.match(pattern_re, name)
            if match:
                configs_this_part.add(match.group(1))

        if len(configs_this_part) != 1:
            raise RuntimeError(
                f'Could not uniquely infer config for {part}. Candidates: {sorted(configs_this_part)}'
            )

        part_configs.append(next(iter(configs_this_part)))

    unique_configs = sorted(set(part_configs))
    if len(unique_configs) != 1:
        raise RuntimeError(
            f'Parts do not share one unique config for {product}: {unique_configs}'
        )

    return unique_configs[0]


def cube_name(part, config, product, tag=None, ext='image'):
    base = f'{part}_{config}_{product}'
    if tag:
        base += f'_{tag}'
    return f'{base}.{ext}.fits'


def main():
    this_kh = kh.KeyHandler(master_key=key_file)

    # postprocess_handler = pp.PostProcessHandler(key_handler=this_kh)
    # postprocess_handler.set_targets(only=[TARGET])
    # postprocess_handler.set_interf_configs(only=[config])
    # postprocess_handler.set_feather_configs(only=[config])
    # postprocess_handler.set_line_products(only=[PRODUCT])
    # postprocess_handler.set_no_cont_products(True)

    target_post_dir = this_kh.get_postprocess_dir_for_target(target=TARGET, changeto=False)
    derived_root = this_kh.get_derived_dir_for_target(target=TARGET, changeto=False)
    post_root = os.path.dirname(target_post_dir.rstrip('/'))

    if not os.path.isdir(post_root):
        raise FileNotFoundError(f'Missing postprocess root: {post_root}')

    os.makedirs(target_post_dir, exist_ok=True)
    os.makedirs(derived_root, exist_ok=True)

    parts = discover_post_parts(TARGET, post_root)
    if len(parts) == 0:
        raise RuntimeError(f'No {TARGET}_* part directories found under {post_root}')

    config = CONFIG_OVERRIDE or infer_config(post_root, parts, PRODUCT)

    print(f'Linear mosaic target: {TARGET}')
    print(f'Line product: {PRODUCT}')
    print(f'Config: {config}')
    print(f'Using parts: {", ".join(parts)}')
    print(f'Postprocess root: {post_root}')

    part_dirs = [os.path.join(post_root, part) for part in parts]
    newparts=parts.copy()
    newpart_dirs=part_dirs.copy()

    for part, part_dir in zip(parts, part_dirs):
        pbcorr_round = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='pbcorr_round'))

        if not os.path.exists(pbcorr_round):
            newparts.pop(newparts.index(part))
            newpart_dirs.pop(newpart_dirs.index(part_dir))
    parts=newparts
    part_dirs=newpart_dirs


    in_pbcorr_round = [
        os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='pbcorr_round'))
        for part, part_dir in zip(parts, part_dirs)
    ]
    out_commonres = [
        os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='linmos_commonres'))
        for part, part_dir in zip(parts, part_dirs)
    ]

    # 1) Convolve all parts to common resolution
    # postprocess_handler.task_convolve_parts_for_mosaic(
    #     target=TARGET,
    #     product=PRODUCT,
    #     config=config,
    #     postprocessing_method='spectralcube',
    #     convolve_method=CONVOLVE_METHOD,
    #     in_tag='pbcorr_round',
    #     out_tag='linmos_commonres',
    #     check_files=True,
    # )
    missing_in_commonres = []
    missing_out_commonres = []
    existing_commonres = []

    for part, in_cube, out_cube in zip(parts, in_pbcorr_round, out_commonres):
        if os.path.exists(out_cube):
            existing_commonres.append(part)
        else:
            missing_in_commonres.append(in_cube)
            missing_out_commonres.append(out_cube)

    if RECALCULATE:
        print('RECALCULATE=True: forcing full linmos_commonres recomputation for all parts.')
        common_res_for_mosaic(
            infile_list=in_pbcorr_round,
            outfile_list=out_commonres,
            do_convolve=True,
            convolve_fn=CONVOLVE_METHOD,
            overwrite=True,
        )
    else:
        if len(existing_commonres) > 0:
            print(
                'Reusing existing linmos_commonres for parts: '
                + ', '.join(existing_commonres)
            )

        if len(missing_out_commonres) > 0:
            common_res_for_mosaic(
                infile_list=missing_in_commonres,
                outfile_list=missing_out_commonres,
                do_convolve=True,
                convolve_fn=CONVOLVE_METHOD,
                overwrite=True,
            )
        else:
            print('All linmos_commonres files already exist; skipping common_res_for_mosaic.')

    in_align = []
    out_align = []

    for part, part_dir, commonres in zip(parts, part_dirs, out_commonres):
        pb = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag=None, ext='pb'))
        linmos_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='linmos_aligned'))
        pb_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='pb_aligned'))

        in_align.extend([commonres, pb])
        out_align.extend([linmos_aligned, pb_aligned])

    template_name = os.path.join(
        target_post_dir,
        f'{TARGET}_{config}_{PRODUCT}_linmos_template.fits',
    )

    # 2) Regrid all parts and PBs onto one mosaic grid
    # postprocess_handler.task_align_for_mosaic(
    #     target=TARGET,
    #     product=PRODUCT,
    #     config=config,
    #     postprocessing_method='spectralcube',
    #     in_tags=['linmos_commonres', 'pb'],
    #     out_tags=['linmos_aligned', 'pb_aligned'],
    #     check_files=True,
    # )
    existing_grid = []
    missing_in_align = []
    missing_out_align = []

    for part, part_dir, in_file, out_file in zip(parts, part_dirs, in_align, out_align):
        if os.path.exists(out_file):
            existing_grid.append(part)
        else:
            missing_in_align.append(in_file)
            missing_out_align.append(out_file)

    if RECALCULATE:
        print('RECALCULATE=True: forcing full common-grid recomputation for all parts.')
        common_grid_for_mosaic(
            infile_list=in_align,
            outfile_list=out_align,
            template_name=template_name,
            overwrite=True,
        )
    else:
        if len(existing_grid) > 0:
            print('Reusing existing linmos_aligned/pb_aligned files for parts: ' + ', '.join(existing_grid))

        if len(missing_out_align) > 0:
            common_grid_for_mosaic(
                infile_list=missing_in_align,
                outfile_list=missing_out_align,
                template_name=template_name,
                overwrite=True,
            )
        else:
            print('All common-grid files already exist; skipping common_grid_for_mosaic.')

    aligned_images = []
    weight_images = []

    # 3) Build aligned weight cubes from aligned PBs
    # postprocess_handler.task_make_weights_for_mosaic(
    #     target=TARGET,
    #     product=PRODUCT,
    #     config=config,
    #     imaging_method='sdintimaging',
    #     postprocessing_method='spectralcube',
    #     copy_weights=False,
    #     check_files=True,
    # )
    existing_weight_parts = []
    missing_weight_parts = []

    for part, part_dir in zip(parts, part_dirs):
        aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='linmos_aligned'))
        pb_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='pb_aligned'))
        weight_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='weight_aligned'))

        if os.path.exists(weight_aligned):
            existing_weight_parts.append(part)
            aligned_images.append(aligned)
            weight_images.append(weight_aligned)
            continue

        missing_weight_parts.append((part, aligned, pb_aligned, weight_aligned))

    if RECALCULATE:
        print('RECALCULATE=True: forcing full generate_weight_file recomputation for all parts.')
        for part, part_dir in zip(parts, part_dirs):
            aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='linmos_aligned'))
            pb_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='pb_aligned'))
            weight_aligned = os.path.join(part_dir, cube_name(part, config, PRODUCT, tag='weight_aligned'))

            ok = generate_weight_file(
                image_file=aligned,
                input_file=pb_aligned,
                input_type='pb',
                outfile=weight_aligned,
                scale_by_noise=True,
                already_pbcorr=True,
                overwrite=True,
            )
            if not ok:
                raise RuntimeError(f'Failed generating weight file: {weight_aligned}')

            aligned_images.append(aligned)
            weight_images.append(weight_aligned)
    else:
        if len(existing_weight_parts) > 0:
            print('Reusing existing weight_aligned files for parts: ' + ', '.join(existing_weight_parts))

        for part, aligned, pb_aligned, weight_aligned in missing_weight_parts:
            ok = generate_weight_file(
                image_file=aligned,
                input_file=pb_aligned,
                input_type='pb',
                outfile=weight_aligned,
                scale_by_noise=True,
                already_pbcorr=True,
                overwrite=True,
            )
            if not ok:
                raise RuntimeError(f'Failed generating weight file: {weight_aligned}')

            aligned_images.append(aligned)
            weight_images.append(weight_aligned)

        if len(missing_weight_parts) == 0:
            print('All weight_aligned files already exist; skipping generate_weight_file.')

    mosaic_out = os.path.join(
        target_post_dir,
        cube_name(TARGET, config, PRODUCT, tag='pbcorr_round'),
    )

    # 4) Linear mosaic
    # postprocess_handler.task_linear_mosaic(
    #     target=TARGET,
    #     product=PRODUCT,
    #     config=config,
    #     postprocessing_method='spectralcube',
    #     image_tag='linmos_aligned',
    #     weight_tag='weight_aligned',
    #     out_tag='pbcorr_round',
    #     check_files=True,
    # )
    ok = mosaic_aligned_data(
        infile_list=aligned_images,
        weightfile_list=weight_images,
        template_name=template_name,
        outfile=mosaic_out,
        overwrite=True,
    )
    if not ok:
        raise RuntimeError('mosaic_aligned_data failed')

    print(f'Created mosaic: {mosaic_out}')

    # The derived pipeline expects the postprocess products created by the
    # standard postprocess steps: compress -> convert_jytok -> derived.
    # Do not copy the round-image output directly; run the same postprocess
    # routines that generate pbcorr_trimmed and pbcorr_trimmed_k in the target
    # postprocess directory before the derived pass starts.
    postprocess_handler = pp.PostProcessHandler(key_handler=this_kh)
    postprocess_handler.set_targets(only=[TARGET])
    postprocess_handler.set_interf_configs(only=[config])
    postprocess_handler.set_feather_configs(only=[config])
    postprocess_handler.set_line_products(only=[PRODUCT])
    postprocess_handler.set_no_cont_products(True)

    postprocess_handler.task_compress(
        target=TARGET,
        product=PRODUCT,
        config=config,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )
    postprocess_handler.task_convert_units(
        target=TARGET,
        product=PRODUCT,
        config=config,
        imaging_method='sdintimaging',
        postprocessing_method='spectralcube',
        check_files=False,
    )

    derived_input = os.path.join(
        target_post_dir,
        f'{TARGET}_{config}_{PRODUCT}_pbcorr_trimmed_k.fits',
    )
    if not os.path.exists(derived_input):
        raise FileNotFoundError(
            'Missing postprocess input for derived products after running task_compress/task_convert_units: '
            f'{derived_input}'
        )

    if RUN_DERIVED:
        derived_handler = der.DerivedHandler(key_handler=this_kh)
        derived_handler.set_targets(only=[TARGET])
        derived_handler.set_interf_configs(only=[config])
        derived_handler.set_feather_configs(only=[config])
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
