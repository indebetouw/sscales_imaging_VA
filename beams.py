import glob
import os

import matplotlib.pyplot as pl
import numpy as np
from astropy.io import fits

pl.ion()


def _find_image_files(line):
    search_root = "/lustre/cv/users/rindebet/galaxies/array_reduction/post/"
    matches = sorted(glob.glob(os.path.join(search_root, "ngc5236_*", "*"+line+".image.fits")))

    seen = set()
    unique = []
    for path in matches:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def gethead_beam_arrays2(files=None,line="_co21"):
    """Read the beam record from the second FITS extension for each file and take
    the median BMAJ/BMIN/BPA value for that file."""
    if files is None:
        files = _find_image_files(line)

    if not files:
        return {
            "bmaj": np.array([], dtype=float),
            "bmin": np.array([], dtype=float),
            "bpa": np.array([], dtype=float),
            "files": [],
        }

    bmaj = []
    bmin = []
    bpa = []

    for path in files:
        with fits.open(path) as hdul:
            if len(hdul) < 2:
                raise ValueError(f"{path} does not contain a second FITS extension with beam metadata.")

            table = hdul[1].data
            if table is None or not hasattr(table, "dtype") or "BMAJ" not in table.dtype.names:
                raise ValueError(f"{path} second extension does not contain BMAJ/BMIN/BPA columns.")

            bmaj.append(np.median(table["BMAJ"]))
            bmin.append(np.median(table["BMIN"]))
            bpa.append(np.median(table["BPA"]))

    return {
        "bmaj": np.array(bmaj, dtype=float),
        "bmin": np.array(bmin, dtype=float),
        "bpa": np.array(bpa, dtype=float),
        "files": files,
    }


if __name__ == "__main__":
    tt = np.arange(21) / 10 * np.pi
    st = np.sin(tt)
    ct = np.cos(tt)

    pl.clf()
    lines=["_co21","13co21","c18o21"]

    data=[]
    for iline,line in enumerate(lines):
        data.append(gethead_beam_arrays2(line=line))

        # pl.hist(data[-1]["bmaj"], bins=10, histtype='step', label=f"{line}")
        # pl.subplot(2,2,iline+1)
        # for i, path in enumerate(data["files"]):
        #     fname = path.split('/')[-1]
        #     print(f"{i}: {fname}: {data['bmaj'][i]:.6f}, {data['bmin'][i]:.6f}, {data['bpa'][i]:.3f}")
        #     x0 = ct * data['bmaj'][i]
        #     y0 = st * data['bmin'][i]
        #     x = x0 * np.cos(data['bpa'][i] * np.pi / 180) - y0 * np.sin(data['bpa'][i] * np.pi / 180)
        #     y = x0 * np.sin(data['bpa'][i] * np.pi / 180) + y0 * np.cos(data['bpa'][i] * np.pi / 180)
        #     pl.plot(x, y, label=f"{i}: {fname.split('_')[1]}")
        # pl.gca().set_aspect('equal', adjustable='box')
        # pl.gca().set_xticklabels([])
        # pl.title(line)
        # pl.legend(prop={'size': 6})

    # pl.subplots_adjust(hspace=0.1,left=0.1,right=0.95,bottom=0.1,top=0.95)

    pl.plot(data[0]["bmaj"], data[0]["bmin"], "o", label=lines[0][1:])
    pl.plot(data[1]["bmaj"], data[1]["bmin"], "o", label=lines[1])
    pl.plot(data[2]["bmaj"], data[2]["bmin"], "o", label=lines[2])
    pl.legend(prop={'size': 10})
    pl.gca().set_aspect('equal', adjustable='box')
    pl.xlabel("BMAJ [arcsec]")
    pl.ylabel("BMIN [arcsec]")

    pl.savefig("beams.png")
    print("done")


