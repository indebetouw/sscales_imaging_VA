#!/bin/bash
#SBATCH --account=rindebet
#SBATCH --time=72:00:00
#SBATCH --job-name=phangs_chunk
#SBATCH --chdir=/lustre/cv/users/rindebet/galaxies/array_reduction/work
#SBATCH --output=/lustre/cv/users/rindebet/galaxies/array_reduction/work/%x_%A_%a.out
#SBATCH --error=/lustre/cv/users/rindebet/galaxies/array_reduction/work/%x_%A_%a.err
#SBATCH --ntasks=4      # number of MPI processes
#SBATCH --mem=126G      # memory; default unit is megabytes; was 32G/core
#SBATCH --cpus-per-task=1
#SBATCH --mail-user=rindebet@nrao.edu
#SBATCH --mail-type=ALL
#SBATCH --partition=plwg_low 

# plwg,batch2

job_workdir='/lustre/cv/users/rindebet/galaxies/array_reduction/work'
script_dir="$(cd "$(dirname "$0")" && pwd)"
dry_run_submit=false
dry_run_counter=0

# competed stages will be skipped if the final postprocessed product already exists. 
# if you want to rerun starting from a specific stage, set first_stage_to_rerun to S, I, A, P, or D.
# subsequent stages will all be rerun. 
# Optional command-line form: run_chunked.bash <target> <product> --rerun=S
first_stage_to_rerun=""  # S, I, A, P, D

stages=("S" "I" "A" "P" "D")
declare -A stage_rank=()
for stage_index in "${!stages[@]}"; do
    stage_rank["${stages[$stage_index]}"]="$stage_index"
done

submit_sbatch() {
    local __outvar="$1"
    shift

    if [[ "$dry_run_submit" == true ]]; then
        echo "DRY RUN: sbatch $*"
        dry_run_counter=$((dry_run_counter + 1))
        printf -v "$__outvar" "DRYRUN_%03d" "$dry_run_counter"
    else
        local __id
        __id=$(sbatch --chdir="$job_workdir" --output="$job_workdir/%x_%A_%a.out" --error="$job_workdir/%x_%A_%a.err" "$@")
        printf -v "$__outvar" "%s" "$__id"
    fi
}

assembled_products_exist() {
    local target_name="$1"
    local product_name="$2"
    local config_name="12m+7m"
    local master_key="${script_dir}/master_key_sscales.txt"
    local dir_key="${script_dir}/dir_key.txt"
    local imaging_root
    local target_dir
    local imaging_dir
    local cube_root
    local root_tag
    local p_tclean
    local p_sdint

    if [[ ! -f "$master_key" ]]; then
        return 1
    fi

    imaging_root=$(awk '$1=="imaging_root" {print $2; exit}' "$master_key")
    if [[ -z "$imaging_root" ]]; then
        return 1
    fi

    if [[ -f "$dir_key" ]]; then
        target_dir=$(awk -v tgt="$target_name" '$1==tgt && $1 !~ /^#/ {print $2; exit}' "$dir_key")
    fi
    if [[ -z "$target_dir" ]]; then
        target_dir="$target_name"
    fi

    imaging_dir="${imaging_root%/}/${target_dir}"
    cube_root="${target_name}_${config_name}_${product_name}"

    # Only require final assembled cube products. The "dirty" cube is
    # diagnostic/intermediate for many runs and may not be preserved.
    for root_tag in "" "_singlescale" "_multiscale"; do
        p_tclean="${imaging_dir}/${cube_root}${root_tag}.image"
        p_sdint="${imaging_dir}/${cube_root}${root_tag}.joint.cube.image"
        if [[ -d "$p_tclean" || -d "$p_sdint" ]]; then
            :
        else
            echo "Missing assembled product path: $p_tclean or $p_sdint" >&2
            return 1
        fi
    done

    return 0
}

postprocessed_products_exist() {
    local target_name="$1"
    local product_name="$2"
    local config_name="12m+7m+tp"
    local master_key="${script_dir}/master_key_sscales.txt"
    local dir_key="${script_dir}/dir_key.txt"
    local postprocess_root
    local target_dir
    local postprocess_dir
    local cube_root
    local cube_path

    if [[ ! -f "$master_key" ]]; then
        return 1
    fi

    postprocess_root=$(awk '$1=="postprocess_root" {print $2; exit}' "$master_key")
    if [[ -z "$postprocess_root" ]]; then
        return 1
    fi

    if [[ -f "$dir_key" ]]; then
        target_dir=$(awk -v tgt="$target_name" '$1==tgt && $1 !~ /^#/ {print $2; exit}' "$dir_key")
    fi
    if [[ -z "$target_dir" ]]; then
        target_dir="$target_name"
    fi

    postprocess_dir="${postprocess_root%/}/${target_dir}"
    cube_root="${target_name}_${config_name}_${product_name}"
    cube_path="${postprocess_dir}/${cube_root}_pbcorr_trimmed_k.fits"

    if [[ -f "$cube_path" ]]; then
        return 0
    fi

    echo "Missing postprocessed product: $cube_path" >&2
    return 1
}

derived_products_exist() {
    local target_name="$1"
    local product_name="$2"
    local master_key="${script_dir}/master_key_sscales.txt"
    local dir_key="${script_dir}/dir_key.txt"
    local derived_root
    local target_dir
    local derived_dir
    local derived_files

    if [[ ! -f "$master_key" ]]; then
        return 1
    fi

    derived_root=$(awk '$1=="derived_root" {print $2; exit}' "$master_key")
    if [[ -z "$derived_root" ]]; then
        return 1
    fi

    if [[ -f "$dir_key" ]]; then
        target_dir=$(awk -v tgt="$target_name" '$1==tgt && $1 !~ /^#/ {print $2; exit}' "$dir_key")
    fi
    if [[ -z "$target_dir" ]]; then
        target_dir="$target_name"
    fi

    derived_dir="${derived_root%/}/${target_dir}"

    shopt -s nullglob
    derived_files=("${derived_dir}/${target_name}_"*"_${product_name}_"*.fits)
    shopt -u nullglob

    if (( ${#derived_files[@]} > 0 )); then
        return 0
    fi

    return 1
}

staged_ms_exists() {
    local target_name="$1"
    local product_name="$2"
    local config_name="12m+7m"
    local master_key="${script_dir}/master_key_sscales.txt"
    local dir_key="${script_dir}/dir_key.txt"
    local imaging_root
    local target_dir
    local staging_dir
    local ms_path

    if [[ ! -f "$master_key" ]]; then
        return 1
    fi

    imaging_root=$(awk '$1=="imaging_root" {print $2; exit}' "$master_key")
    if [[ -z "$imaging_root" ]]; then
        return 1
    fi

    if [[ -f "$dir_key" ]]; then
        target_dir=$(awk -v tgt="$target_name" '$1==tgt && $1 !~ /^#/ {print $2; exit}' "$dir_key")
    fi
    if [[ -z "$target_dir" ]]; then
        target_dir="$target_name"
    fi

    staging_dir="${imaging_root%/}/${target_dir}"
    ms_path="${staging_dir}/${target_name}_${config_name}_${product_name}.ms"

    if [[ -d "$ms_path" ]]; then
        return 0
    fi

    echo "Missing staged MS path: $ms_path" >&2
    return 1
}

all_required_chunk_products_exist() {
    local target_name="$1"
    local product_name="$2"
    local config_name="12m+7m"
    local chunksize=40
    local master_key="${script_dir}/master_key_sscales.txt"
    local dir_key="${script_dir}/dir_key.txt"
    local imaging_root
    local target_dir
    local imaging_dir
    local cube_root
    local ms_path
    local nchan
    local nchunks
    local chunk_idx
    local chan_start
    local chan_end
    local chunk_root
    local chunk_tclean
    local chunk_sdint
    local tclean_exists
    local sdint_exists

    if [[ ! -f "$master_key" ]]; then
        return 1
    fi

    imaging_root=$(awk '$1=="imaging_root" {print $2; exit}' "$master_key")
    if [[ -z "$imaging_root" ]]; then
        return 1
    fi

    if [[ -f "$dir_key" ]]; then
        target_dir=$(awk -v tgt="$target_name" '$1==tgt && $1 !~ /^#/ {print $2; exit}' "$dir_key")
    fi
    if [[ -z "$target_dir" ]]; then
        target_dir="$target_name"
    fi

    imaging_dir="${imaging_root%/}/${target_dir}"
    cube_root="${target_name}_${config_name}_${product_name}"
    ms_path="${imaging_dir}/${cube_root}.ms"

    if [[ ! -d "$ms_path" ]]; then
        echo "Missing staged MS path for chunk guard: $ms_path" >&2
        return 1
    fi

    nchan=$(/users/rindebet/miniforge3/envs/phclean/bin/python - "$ms_path" <<'PY'
import sys

ms_path = sys.argv[1]
try:
    from casatools import msmetadata
    msmd = msmetadata()
    msmd.open(ms_path)
    nchan = int(msmd.nchan(0))
    msmd.close()
    print(nchan)
except Exception:
    print("")
PY
)

    if ! [[ "$nchan" =~ ^[0-9]+$ ]]; then
        echo "Unable to determine nchan from staged MS for chunk guard: $ms_path" >&2
        return 1
    fi

    nchunks=$(( (nchan + chunksize - 1) / chunksize ))

    if [[ "$dry_run_submit" == true ]]; then
        echo "Dry-run chunk guard: target=${target_name} product=${product_name} nchan=${nchan} chunksize=${chunksize} nchunks=${nchunks}"
    fi

    for ((chunk_idx=0; chunk_idx<nchunks; chunk_idx++)); do
        chan_start=$((chunk_idx * chunksize))
        chan_end=$((chan_start + chunksize - 1))
        if ((chan_end >= nchan)); then
            chan_end=$((nchan - 1))
        fi

        chunk_root="${imaging_dir}/${cube_root}_chan${chan_start}_${chan_end}"
        chunk_tclean="${chunk_root}.image"
        chunk_sdint="${chunk_root}.joint.cube.image"

        tclean_exists=false
        sdint_exists=false
        if [[ -d "$chunk_tclean" ]]; then
            tclean_exists=true
        fi
        if [[ -d "$chunk_sdint" ]]; then
            sdint_exists=true
        fi

        if [[ "$dry_run_submit" == true ]]; then
            echo "Dry-run chunk check: idx=${chunk_idx} range=${chan_start}-${chan_end} tclean_exists=${tclean_exists} sdint_exists=${sdint_exists}"
            echo "  tclean_path=${chunk_tclean}"
            echo "  sdint_path=${chunk_sdint}"
        fi

        if [[ "$tclean_exists" == true || "$sdint_exists" == true ]]; then
            :
        else
            if (( chan_start >= 200 && chan_end <= 203 )); then
                echo "Skipping known missing chunk range ${chan_start}-${chan_end}: $chunk_tclean or $chunk_sdint" >&2
                continue
            fi
            echo "Missing chunk image path: $chunk_tclean or $chunk_sdint" >&2
            return 1
        fi
    done

    return 0
}





# ==========================
# Read target/product from CLI and submit with dynamic job naming when run
# outside of an allocated Slurm job.
if [[ -z "${SLURM_JOB_ID:-}" ]]; then
	if [[ $# -lt 2 ]]; then
        echo "Usage: $0 <target> <product> [--rerun=<stage>] [sbatch options] [--dry-run-submit]"
        echo "Example: $0 ngc5236_5 13co21 --array=0-5 --rerun=I --dry-run-submit"
        exit 1
	fi
	target_cli="$1"
	product_cli="$2"
	job_tag="${target_cli}_${product_cli}"
	shift 2
    sbatch_opts=()
    for arg in "$@"; do
        if [[ "$arg" == "--dry-run-submit" ]] || [[ "$arg" == "--dry" ]]; then
            dry_run_submit=true
        elif [[ "$arg" == --rerun=* ]]; then
            first_stage_to_rerun="${arg#--rerun=}"
        elif [[ "$arg" == rerun=* ]]; then
            first_stage_to_rerun="${arg#rerun=}"
        else
            sbatch_opts+=("$arg")
        fi
    done
    if [[ "$dry_run_submit" == true ]]; then
        echo "Dry-run submit mode enabled; no jobs will be submitted."
    fi

    if [[ -n "${first_stage_to_rerun}" ]] && [[ ! " ${stages[*]} " =~ " ${first_stage_to_rerun} " ]]; then
        echo "Invalid first_stage_to_rerun value: ${first_stage_to_rerun}. Must be one of: ${stages[*]}"
        exit 1
    fi
    
    if { [[ -z "${first_stage_to_rerun}" ]] || (( stage_rank["${first_stage_to_rerun}"] > stage_rank["S"] )); } && \
       staged_ms_exists "${target_cli}" "${product_cli}"; then
        echo "Staged MS already exists for ${job_tag}; skipping S submission."
        STAGE_ID=""
    else
        export stagestring='S'
        submit_sbatch STAGE_ID --parsable --ntasks=1 --job-name="${job_tag}_stage" "$0" "${target_cli}" "${product_cli}"
        echo "Submitted Stage job '${job_tag}_stage' ${STAGE_ID}"
    fi

    if { [[ -z "${first_stage_to_rerun}" ]] || (( stage_rank["${first_stage_to_rerun}"] > stage_rank["I"] )); } && \
       all_required_chunk_products_exist "${target_cli}" "${product_cli}"; then
        echo "All required chunk products already exist for ${job_tag}; skipping I submission."
        IMAGE_ID=""
    else
        export stagestring='I'
        if [[ -n "${STAGE_ID}" ]]; then
            submit_sbatch IMAGE_ID --parsable --dependency=afterok:${STAGE_ID} "${sbatch_opts[@]}" --job-name="${job_tag}" "$0" "${target_cli}" "${product_cli}"
        else
            submit_sbatch IMAGE_ID --parsable "${sbatch_opts[@]}" --job-name="${job_tag}" "$0" "${target_cli}" "${product_cli}"
        fi
        echo "Submitted Imaging job '${job_tag}' ${IMAGE_ID}"
    fi

    if { [[ -z "${first_stage_to_rerun}" ]] || (( stage_rank["${first_stage_to_rerun}"] > stage_rank["A"] )); } && \
       assembled_products_exist "${target_cli}" "${product_cli}"; then
        echo "All required assembled products already exist for ${job_tag}; skipping A submission."
        ASSEMBLY_ID=""
    else
        export stagestring='A'
        if [[ -n "${IMAGE_ID}" ]]; then
            submit_sbatch ASSEMBLY_ID --parsable --dependency=afterok:${IMAGE_ID} --ntasks=1 --job-name="${job_tag}_assemble" "$0" "${target_cli}" "${product_cli}"
        else
            submit_sbatch ASSEMBLY_ID --parsable --ntasks=1 --job-name="${job_tag}_assemble" "$0" "${target_cli}" "${product_cli}"
        fi
        echo "Submitted Assembly job '${job_tag}' ${ASSEMBLY_ID}"
    fi

    if { [[ -z "${first_stage_to_rerun}" ]] || (( stage_rank["${first_stage_to_rerun}"] > stage_rank["P"] )); } && \
       postprocessed_products_exist "${target_cli}" "${product_cli}"; then
        echo "All required postprocessed products already exist for ${job_tag}; skipping P submission."
        POST_ID=""
    else
        export stagestring='P'
        if [[ -n "${ASSEMBLY_ID}" ]]; then
            submit_sbatch POST_ID --parsable --dependency=afterok:${ASSEMBLY_ID} --ntasks=1 --job-name="${job_tag}_post" "$0" "${target_cli}" "${product_cli}"
        else
            submit_sbatch POST_ID --parsable --ntasks=1 --job-name="${job_tag}_post" "$0" "${target_cli}" "${product_cli}"
        fi
        echo "Submitted Postprocess job '${job_tag}' ${POST_ID}"
    fi

    if { [[ -z "${first_stage_to_rerun}" ]] || (( stage_rank["${first_stage_to_rerun}"] > stage_rank["D"] )); } && \
       derived_products_exist "${target_cli}" "${product_cli}"; then
        echo "All required derived products already exist for ${job_tag}; skipping D submission."
        DERIVED_ID=""
    else
        export stagestring='D'
        if [[ -n "${POST_ID}" ]]; then
            submit_sbatch DERIVED_ID --parsable --dependency=afterok:${POST_ID} --time=24:00:00 --ntasks=8 --mem=250G --job-name="${job_tag}_derived" "$0" "${target_cli}" "${product_cli}"
        else
            submit_sbatch DERIVED_ID --parsable --time=24:00:00 --ntasks=8 --mem=250G --job-name="${job_tag}_derived" "$0" "${target_cli}" "${product_cli}"
        fi
        echo "Submitted Derived job '${job_tag}' ${DERIVED_ID}"
    fi

	exit $?
fi

# Edit these lines to point to correct directory and galaxy name
export code_dir='/lustre/cv/users/rindebet/local/github/sscales_imaging_VA/'
# export casadir='/lustre/cv/users/rindebet/casa/casa-6.7.5-10-pipeline-2026.1.1.7-py3.12.el8/'
# Target and product are read from command line as:
#   run_chunked.bash <target> <product>
# Example target: m83_5
export target="$1"
export config="12m+7m"
export product="$2"

# call this file with
# run_chunked.bash m83_5 13co21 --array=0-5


#### you shouldn't need to edit below this line
# srun bash
#ls -l /idia/software/containers/casa-modular-v6.6.4.sif
#module load casa/6.6.4
# do this in the CASA installation before starting this script
# pip install spectral-cube, uvcombine

if [ -z ${SLURM_ARRAY_TASK_ID+x} ]; then export SLURM_ARRAY_TASK_ID=-1; fi
echo "Job array ID is set to '$SLURM_ARRAY_TASK_ID'"

# how to pass arguments to the -c command of casa
#${casadir}/bin/casa --log2term --logfile casa_{$SLURM_ARRAY_TASK_ID}.log -c "${code_dir}/run_chunk.py $target $stagestring $SLURM_ARRAY_TASK_ID"
. /users/rindebet/miniforge3/etc/profile.d/conda.sh
conda activate phclean
echo "Using conda environment: $(which python)"
# Normalize any accidental whitespace so stage selection is exact.
stage_mode="${stagestring:-}"
stage_mode="${stage_mode//[[:space:]]/}"

echo "calling ${code_dir}/run_chunk.py $target $config $product $stagestring $SLURM_ARRAY_TASK_ID"

if [[ "$stage_mode" == "I" ]]; then
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TMPDIR="$job_workdir" mpirun --mca btl_vader_single_copy_mechanism none -x OMP_NUM_THREADS -x OPENBLAS_NUM_THREADS -x TMPDIR -n 4 python ${code_dir}/run_chunk.py $target $config $product $stagestring $SLURM_ARRAY_TASK_ID
elif [[ "$stage_mode" == "D" ]]; then
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TMPDIR="$job_workdir" mpirun --mca btl_vader_single_copy_mechanism none -x OMP_NUM_THREADS -x OPENBLAS_NUM_THREADS -x TMPDIR -n 8 python ${code_dir}/run_chunk.py $target $config $product $stagestring $SLURM_ARRAY_TASK_ID
else
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TMPDIR="$job_workdir" python ${code_dir}/run_chunk.py $target $config $product $stagestring $SLURM_ARRAY_TASK_ID    
fi
