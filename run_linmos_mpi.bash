#!/bin/bash
# Submit with:
# sbatch --account=rindebet --time=72:00:00 --job-name=linmos_mpi --chdir=/lustre/cv/users/rindebet/galaxies/array_reduction/work --output=/lustre/cv/users/rindebet/galaxies/array_reduction/work/%x_%A.out --error=/lustre/cv/users/rindebet/galaxies/array_reduction/work/%x_%A.err --ntasks=8 --mem=250G --cpus-per-task=1 --partition=plwg,batch2 /lustre/cv/users/rindebet/local/github/sscales_imaging_VA/run_linmos_mpi.bash

set -euo pipefail

script_dir="/lustre/cv/users/rindebet/local/github/sscales_imaging_VA"
job_workdir="/lustre/cv/users/rindebet/galaxies/array_reduction/work"

mkdir -p "$job_workdir"

. /users/rindebet/miniforge3/etc/profile.d/conda.sh
conda activate phclean

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export TMPDIR="$job_workdir"

cd "$script_dir"

mpirun --mca btl_vader_single_copy_mechanism none \
    -x OMP_NUM_THREADS -x OPENBLAS_NUM_THREADS -x TMPDIR \
    -n 8 \
    python "$script_dir/linmos.py"
