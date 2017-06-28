import base64
from io import BytesIO

import numpy as np
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.projections import register_projection
from matplotlib.projections.polar import PolarAxes
from matplotlib.spines import Spine

from django.conf import settings


def radar_factory(num_vars):
    """Create a radar chart with `num_vars` axes.

    This function creates a RadarAxes projection and registers it.

    Parameters
    ----------
    num_vars : int
        Number of variables for radar chart.
    """
    # calculate evenly-spaced axis angles
    theta = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)
    # rotate theta such that the first axis is at the top
    theta += np.pi / 2

    class RadarAxes(PolarAxes):

        name = 'radar'

        def plot(self, *args, **kwargs):
            """Override plot so that line is closed by default"""
            lines = super(RadarAxes, self).plot(*args, **kwargs)
            for line in lines:
                if '--' != kwargs.get('linestyle'):
                    line.set_linewidth(2.0)
                self._close_line(line)

        @staticmethod
        def _close_line(line):
            x, y = line.get_data()
            if x[0] != x[-1]:
                x = np.concatenate((x, [x[0]]))
                y = np.concatenate((y, [y[0]]))
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels, fontsize=16)

        def _gen_axes_spines(self):
            # The following is a hack to get the spines (i.e. the axes frame)
            # to draw correctly for a polygon frame.

            # spine_type must be 'left', 'right', 'top', 'bottom', or `circle`.
            spine_type = 'circle'
            verts = unit_poly_verts(theta)
            # close off polygon by repeating first vertex
            verts.append(verts[0])
            path = Path(verts)

            spine = Spine(self, spine_type, path)
            spine.set_transform(self.transAxes)
            return {'polar': spine}

    register_projection(RadarAxes)
    return theta


def unit_poly_verts(theta):
    """Return vertices of polygon for subplot axes.

    This polygon is circumscribed by a unit circle centered at (0.5, 0.5)
    """
    x0, y0, r = [0.5] * 3
    verts = [(r * np.cos(t) + x0, r * np.sin(t) + y0) for t in theta]
    return verts


def prepare_radar_chart(theta, ax):
    for d in [[0, 0, 0, 0, 0],
              [5, 5, 5, 5, 5],
              [10, 10, 10, 10, 10],
              [15, 15, 15, 15, 15],
              [20, 20, 20, 20, 20],
              [25, 25, 25, 25, 25]]:
        ax.plot(theta, d, color='#58595B', linestyle='--')


def get_radar_chart(data):
    theta = radar_factory(5)
    spoke_labels = data.pop(0)

    fig, ax = plt.subplots(figsize=(8, 8), nrows=1, ncols=1, subplot_kw=dict(projection='radar'))

    prepare_radar_chart(theta, ax)

    colors = ['b', 'r']
    case_data = data[0]
    ax.set_rgrids([5, 10, 15, 20, 25], angle=90)
    for tmp_data, color in zip(case_data, colors):
        # reverse tmp_data[1] ~ tmp_data[4]
        # Please see the following example for chart order.
        # 1st:tmp_data[0]
        # 2nd:tmp_data[4]
        # 3rd:tmp_data[3]
        # 4th:tmp_data[2]
        # 5th:tmp_data[1]
        d = [tmp_data[0]] + tmp_data[1:5][::-1]
        ax.plot(theta, d, color=color)

    # labels setup
    ax.set_varlabels(spoke_labels)

    ax.grid('off')
    ax.patch.set_alpha(0.0)
    fig.patch.set_alpha(0.0)
    figfile = BytesIO()
    plt.savefig(figfile, format='png')
    figfile.seek(0)

    return figfile.getvalue()


def get_radar_chart_with_base64(data):
    value = get_radar_chart(data)
    return base64.b64encode(value)
