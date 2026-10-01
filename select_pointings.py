import numpy as np
import matplotlib
matplotlib.use('TkAgg')

from astropy.coordinates import Angle
import astropy.units as u
from matplotlib.path import Path
from matplotlib.widgets import PolygonSelector


class SelectFromCollection:
    """
    Select indices from a matplotlib collection using `PolygonSelector`.

    Selected indices are saved in the `ind` attribute. This tool fades out the
    points that are not part of the selection (i.e., reduces their alpha
    values). If your collection has alpha < 1, this tool will permanently
    alter the alpha values.

    Note that this tool selects collection objects based on their *origins*
    (i.e., `offsets`).

    Parameters
    ----------
    ax : `~matplotlib.axes.Axes`
        Axes to interact with.
    collection : `matplotlib.collections.Collection` subclass
        Collection you want to select from.
    alpha_other : 0 <= float <= 1
        To highlight a selection, this tool sets all selected points to an
        alpha value of 1 and non-selected points to *alpha_other*.
    """

    def __init__(self, ax, collection, alpha_other=0.3):
        self.canvas = ax.figure.canvas
        self.collection = collection
        self.alpha_other = alpha_other

        self.xys = collection.get_offsets()
        self.Npts = len(self.xys)

        # Ensure that we have separate colors for each object
        self.fc = collection.get_facecolors()
        if len(self.fc) == 0:
            raise ValueError('Collection must have a facecolor')
        elif len(self.fc) == 1:
            self.fc = np.tile(self.fc, (self.Npts, 1))

        self.poly = PolygonSelector(ax, self.onselect, draw_bounding_box=True)
        self.ind = []

    def onselect(self, verts):
        path = Path(verts)
        self.ind = np.nonzero(path.contains_points(self.xys))[0]
        self.fc[:, -1] = self.alpha_other
        self.fc[self.ind, -1] = 1
        self.collection.set_facecolors(self.fc)
        self.canvas.draw_idle()

    def disconnect(self):
        self.poly.disconnect_events()
        self.fc[:, -1] = 1
        self.collection.set_facecolors(self.fc)
        self.canvas.draw_idle()


if __name__ == '__main__':
    import matplotlib.pyplot as pl
    import sys,os
    sys.path.append("/home/casa/contrib/bitbucket/AIV/analysis_scripts/")
    import analysisUtils as aU

    pl.clf()
    print(os.getcwd())
    myms="/lustre/cv/users/rindebet/galaxies/m83/targms/uid___A002_X13128dc_X1194c_targets.ms/"
    myms="/lustre/cv/users/rindebet/galaxies/m83/targms/uid___A002_X133b089_X6951_targets.ms/"
    myms="/lustre/cv/users/rindebet/galaxies/m83/targms/uid___A002_X1314bf3_X268e_targets.ms"
    aU.plotmosaic(myms,coord="absolute")

    ax = pl.gca()
    text_labels = None
    if ax.collections:
        pts = ax.collections[-1]
    elif ax.texts:
        text_objects = ax.texts
        text_labels = np.asarray([txt.get_text() for txt in text_objects])
        positions = [txt.get_position() for txt in text_objects]
        x = np.asarray([pos[0] for pos in positions])
        y = np.asarray([pos[1] for pos in positions])
        pts = ax.scatter(x, y, s=50, marker='o', c='blue',
                         edgecolors='black', linestyle='None')
    elif ax.lines:
        line = ax.lines[-1]
        x = np.asarray(line.get_xdata())
        y = np.asarray(line.get_ydata())
        marker = line.get_marker()
        size = (line.get_markersize() or 5) ** 2
        facecolor = line.get_markerfacecolor()
        edgecolor = line.get_markeredgecolor()
        pts = ax.scatter(x, y, s=size, marker=marker, c=facecolor,
                         edgecolors=edgecolor, linestyle='None', zorder=line.get_zorder() + 1)
    else:
        raise RuntimeError('No plotted collection, text labels, or line symbols available for selection')

    selector = SelectFromCollection(ax, pts)

    print("Select points in the figure by enclosing them within a polygon.")
    print("Press the 'esc' key to start a new polygon.")
    print("Try holding the 'shift' key to move all of the vertices.")
    print("Try holding the 'ctrl' key to move a single vertex.")

    pl.ioff()
    pl.show()

    selector.disconnect()

    # After figure is closed print the coordinates of the selected points
    print('\nSelected points:')
    print(selector.xys[selector.ind])
    mean_ra = np.mean(selector.xys[selector.ind, 0])
    mean_dec = np.mean(selector.xys[selector.ind, 1])
    print(Angle(mean_ra * u.deg).to_string(sep='hms', precision=2, pad=True))
    print(Angle(mean_dec * u.deg).to_string(sep='dms', precision=2, pad=True))

    # If text labels were available, print the corresponding labels
    if text_labels is not None:
        print('\nCorresponding text labels:')
        print(text_labels[selector.ind])