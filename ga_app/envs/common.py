"""
Settings for Biz
"""
import matplotlib as mpl
import matplotlib.font_manager as font_manager

from lms.envs.common import INSTALLED_APPS

"""
Install Apps
"""
INSTALLED_APPS += (
    'ga_app.djangoapps.ga_diagnosis',
)

"""
Matplotlib
"""
prop = font_manager.FontProperties(fname='/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf')
mpl.rcParams['font.family'] = prop.get_name()
mpl.rcParams['backend'] = 'agg'
