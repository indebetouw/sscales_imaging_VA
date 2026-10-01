#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
    quarantine_target_product.sh --target TARGET --product PRODUCT --firststage {A|P|D} [options]

Required:
  --target TARGET          Target name (e.g. ngc5236_6)
  --product PRODUCT        Product name (e.g. 13co21)
    --firststage STAGE       First stage to quarantine from: A, P, or D

Options:
  --config CONFIG          Config name prefix to match (default: 12m+7m)
  --repo-root PATH         Repo root containing NRAO/master_key_sscales.txt
  --quarantine-root PATH   Quarantine base directory
                           (default: $HOME/phangs_quarantine)
  --preview-only           Print matches only, do not move files
  --yes                    Skip confirmation prompt
  --help                   Show this help

What it does:
    1) Finds matching files/dirs produced from the requested stage onward.
         A => assembled imaging + postprocess + derived
         P => postprocess + derived
         D => derived only
  2) Moves matches into a timestamped quarantine folder (reversible), unless --preview-only.
EOF
}

TARGET=""
PRODUCT=""
FIRSTSTAGE=""
CONFIG="12m+7m"
YES=false
PREVIEW_ONLY=false

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QUARANTINE_ROOT="${HOME}/phangs_quarantine"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --product)
            PRODUCT="$2"
            shift 2
            ;;
        --firststage)
            FIRSTSTAGE="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --repo-root)
            REPO_ROOT="$2"
            shift 2
            ;;
        --quarantine-root)
            QUARANTINE_ROOT="$2"
            shift 2
            ;;
        --preview-only)
            PREVIEW_ONLY=true
            shift
            ;;
        --yes)
            YES=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$TARGET" || -z "$PRODUCT" || -z "$FIRSTSTAGE" ]]; then
    echo "ERROR: --target, --product, and --firststage are required." >&2
    usage
    exit 2
fi

case "$FIRSTSTAGE" in
    A|P|D)
        ;;
    *)
        echo "ERROR: --firststage must be one of: A, P, D" >&2
        usage
        exit 2
        ;;
esac

MASTER_KEY="$REPO_ROOT/NRAO/master_key_sscales.txt"
DIR_KEY="$REPO_ROOT/NRAO/dir_key.txt"

if [[ ! -f "$MASTER_KEY" ]]; then
    echo "ERROR: Missing master key: $MASTER_KEY" >&2
    exit 1
fi

IMAGING_ROOT="$(awk '$1=="imaging_root"{print $2; exit}' "$MASTER_KEY")"
POST_ROOT="$(awk '$1=="postprocess_root"{print $2; exit}' "$MASTER_KEY")"
DER_ROOT="$(awk '$1=="derived_root"{print $2; exit}' "$MASTER_KEY")"

if [[ -z "$IMAGING_ROOT" || -z "$POST_ROOT" || -z "$DER_ROOT" ]]; then
    echo "ERROR: Could not read imaging_root, postprocess_root, and/or derived_root from $MASTER_KEY" >&2
    exit 1
fi

TARGET_DIR=""
if [[ -f "$DIR_KEY" ]]; then
    TARGET_DIR="$(awk -v t="$TARGET" '$1==t && $1 !~ /^#/ {print $2; exit}' "$DIR_KEY")"
fi
if [[ -z "$TARGET_DIR" ]]; then
    TARGET_DIR="$TARGET"
fi

IMG_DIR="${IMAGING_ROOT%/}/$TARGET_DIR"
POST_DIR="${POST_ROOT%/}/$TARGET_DIR"
DER_DIR="${DER_ROOT%/}/$TARGET_DIR"
PATTERN="${TARGET}_${CONFIG}_${PRODUCT}*"
ASSEMBLED_PATTERN="${TARGET}_${CONFIG}_${PRODUCT}*.image*"

echo "Target: $TARGET"
echo "Product: $PRODUCT"
echo "First stage: $FIRSTSTAGE"
echo "Config: $CONFIG"
echo "Target directory key: $TARGET_DIR"
echo "Imaging directory: $IMG_DIR"
echo "Postprocess directory: $POST_DIR"
echo "Derived directory: $DER_DIR"
echo "Match pattern: $PATTERN"
echo

IMG_MATCHES=()
POST_MATCHES=()
DER_MATCHES=()

if [[ "$FIRSTSTAGE" == "A" ]]; then
    mapfile -t IMG_MATCHES < <(find "$IMG_DIR" -maxdepth 1 -mindepth 1 \
        \( -name "${TARGET}_${CONFIG}_${PRODUCT}.image" \
        -o -name "${TARGET}_${CONFIG}_${PRODUCT}.joint.cube.image" \
        -o -name "${TARGET}_${CONFIG}_${PRODUCT}_singlescale.image" \
        -o -name "${TARGET}_${CONFIG}_${PRODUCT}_singlescale.joint.cube.image" \
        -o -name "${TARGET}_${CONFIG}_${PRODUCT}_multiscale.image" \
        -o -name "${TARGET}_${CONFIG}_${PRODUCT}_multiscale.joint.cube.image" \) \
        -print 2>/dev/null | sort || true)
fi

if [[ "$FIRSTSTAGE" == "A" || "$FIRSTSTAGE" == "P" ]]; then
    mapfile -t POST_MATCHES < <(find "$POST_DIR" -maxdepth 1 -mindepth 1 -name "$PATTERN" -print 2>/dev/null | sort || true)
fi

mapfile -t DER_MATCHES < <(find "$DER_DIR" -maxdepth 1 -mindepth 1 -name "$PATTERN" -print 2>/dev/null | sort || true)

echo "Preview imaging matches (${#IMG_MATCHES[@]}):"
if [[ ${#IMG_MATCHES[@]} -eq 0 ]]; then
    echo "  (none)"
else
    printf '  %s\n' "${IMG_MATCHES[@]}"
fi
echo

echo "Preview postprocess matches (${#POST_MATCHES[@]}):"
if [[ ${#POST_MATCHES[@]} -eq 0 ]]; then
    echo "  (none)"
else
    printf '  %s\n' "${POST_MATCHES[@]}"
fi
echo

echo "Preview derived matches (${#DER_MATCHES[@]}):"
if [[ ${#DER_MATCHES[@]} -eq 0 ]]; then
    echo "  (none)"
else
    printf '  %s\n' "${DER_MATCHES[@]}"
fi
echo

TOTAL=$(( ${#IMG_MATCHES[@]} + ${#POST_MATCHES[@]} + ${#DER_MATCHES[@]} ))
if [[ "$PREVIEW_ONLY" == true ]]; then
    echo "Preview only requested. No files moved."
    exit 0
fi

if [[ $TOTAL -eq 0 ]]; then
    echo "No matching files found. Nothing to move."
    exit 0
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
QUAR_DIR="${QUARANTINE_ROOT%/}/${TARGET}_${PRODUCT}_${STAMP}"
QUAR_IMG="$QUAR_DIR/imaging"
QUAR_POST="$QUAR_DIR/post"
QUAR_DER="$QUAR_DIR/derived"

mkdir -p "$QUAR_IMG" "$QUAR_POST" "$QUAR_DER"

if [[ "$YES" != true ]]; then
    read -r -p "Move $TOTAL entries into quarantine at '$QUAR_DIR'? [y/N] " RESP
    case "$RESP" in
        y|Y|yes|YES)
            ;;
        *)
            echo "Cancelled."
            exit 0
            ;;
    esac
fi

for f in "${IMG_MATCHES[@]}"; do
    mv -v "$f" "$QUAR_IMG/"
done

for f in "${POST_MATCHES[@]}"; do
    mv -v "$f" "$QUAR_POST/"
done

for f in "${DER_MATCHES[@]}"; do
    mv -v "$f" "$QUAR_DER/"
done

echo
echo "Done. Quarantined files at: $QUAR_DIR"
echo "Restore example: mv '$QUAR_IMG'/* '$IMG_DIR'/"
echo "Restore example: mv '$QUAR_POST'/* '$POST_DIR'/"
echo "Restore example: mv '$QUAR_DER'/* '$DER_DIR'/"
