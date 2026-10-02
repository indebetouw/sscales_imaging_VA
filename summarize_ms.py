#!/usr/bin/env python3
"""Regenerate staged combined MS spectral summary table."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
from casatools import msmetadata

# Rest frequencies in Hz for supported products.
REST_FREQ_HZ = {
    "co21": 230.538000e9,
    "13co21": 220.3986842e9,
    "c18o21": 219.5603541e9,
}

C_KMS = 299792.458


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build staged_combined_ms_spectral_summary.tsv from staged combined MS datasets."
    )
    parser.add_argument(
        "--master-key",
        default="master_key_sscales.txt",
        help="Path to master key file (default: master_key_sscales.txt).",
    )
    parser.add_argument(
        "--imaging-root",
        default=None,
        help="Override imaging root (default: parsed from master key).",
    )
    parser.add_argument(
        "--config",
        default="12m+7m",
        help="Combined config token used in MS names (default: 12m+7m).",
    )
    parser.add_argument(
        "--output",
        default="staged_combined_ms_spectral_summary.tsv",
        help="Output TSV path.",
    )
    return parser.parse_args()


def read_imaging_root(master_key: Path) -> str:
    for line in master_key.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) >= 2 and parts[0] == "imaging_root":
            return parts[1]
    raise RuntimeError(f"Could not find imaging_root in {master_key}")


def iter_ms_paths(imaging_root: Path, config: str) -> list[Path]:
    pattern = f"*/*_{config}_*.ms"
    return sorted(p for p in imaging_root.glob(pattern) if p.is_dir())


def parse_target_product(ms_path: Path, config: str) -> tuple[str, str]:
    pattern = re.compile(rf"^(?P<target>.+)_{re.escape(config)}_(?P<product>.+)\.ms$")
    match = pattern.match(ms_path.name)
    if not match:
        raise RuntimeError(f"Unexpected MS name format: {ms_path.name}")
    return match.group("target"), match.group("product")


def summarize_ms(ms_path: Path, rest_hz: float) -> tuple[int, float, float, float, float, float]:
    msmd = msmetadata()
    msmd.open(str(ms_path))
    try:
        nchan = int(msmd.nchan(0))
        freqs_hz = np.asarray(msmd.chanfreqs(0), dtype=float)
    finally:
        msmd.close()

    vel_kms = C_KMS * (1.0 - (freqs_hz / rest_hz))
    v_min = float(np.min(vel_kms))
    v_max = float(np.max(vel_kms))
    v_center = 0.5 * (v_min + v_max)
    chan_width = float(np.median(np.abs(np.diff(vel_kms)))) if nchan > 1 else 0.0
    return nchan, v_center, chan_width, (v_max - v_min), v_min, v_max


def product_sort_key(product: str) -> tuple[int, str]:
    order = {"co21": 0, "13co21": 1, "c18o21": 2}
    return order.get(product, 99), product


def main() -> int:
    args = parse_args()
    master_key = Path(args.master_key)
    if not master_key.exists():
        print(f"Missing master key: {master_key}", file=sys.stderr)
        return 1

    imaging_root = Path(args.imaging_root or read_imaging_root(master_key))
    if not imaging_root.exists():
        print(f"Missing imaging root: {imaging_root}", file=sys.stderr)
        return 1

    ms_paths = iter_ms_paths(imaging_root, args.config)
    if not ms_paths:
        print(f"No combined MS files found under {imaging_root}", file=sys.stderr)
        return 1

    rows = []
    for ms_path in ms_paths:
        target, product = parse_target_product(ms_path, args.config)
        rest_hz = REST_FREQ_HZ.get(product)
        if rest_hz is None:
            print(
                f"Skipping unsupported product without rest frequency mapping: {product} ({ms_path})",
                file=sys.stderr,
            )
            continue

        nchan, v_center, chan_width, v_range, v_min, v_max = summarize_ms(ms_path, rest_hz)
        rows.append(
            {
                "target": target,
                "product": product,
                "nchan": str(nchan),
                "v_center_kms_radio": f"{v_center:.6f}",
                "chan_width_kms": f"{chan_width:.6f}",
                "v_range_kms": f"[{v_min:.6f}, {v_max:.6f}]",
                "v_min_kms": f"{v_min:.6f}",
                "v_max_kms": f"{v_max:.6f}",
                "ms_path": str(ms_path),
            }
        )

    rows.sort(key=lambda r: (r["target"], product_sort_key(r["product"])))

    output = Path(args.output)
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "product",
                "nchan",
                "v_center_kms_radio",
                "chan_width_kms",
                "v_range_kms",
                "v_min_kms",
                "v_max_kms",
                "ms_path",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
