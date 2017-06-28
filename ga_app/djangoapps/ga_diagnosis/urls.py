"""
URLconf for ga_diagnosis views
"""
from django.conf.urls import patterns, url

from ga_app.djangoapps.ga_diagnosis.views import (BlockA1, BlockA2, BlockA3, BlockB1, BlockB2, IndexView, PreResult)

urlpatterns = patterns(
    'ga_app.djangoapps.ga_diagnosis.views',

    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^block_a1/$', BlockA1.as_view(), name='block_a1'),
    url(r'^block_a2/$', BlockA2.as_view(), name='block_a2'),
    url(r'^block_a3/$', BlockA3.as_view(), name='block_a3'),
    url(r'^block_b1/$', BlockB1.as_view(), name='block_b1'),
    url(r'^block_b2/$', BlockB2.as_view(), name='block_b2'),
    url(r'^pre_result_a/$', PreResult.as_view(), name='pre_result_a'),
    url(r'^pre_result_b/$', PreResult.as_view(), name='pre_result_b'),
    url(r'^result/$', 'result', name='result'),
    url(r'^get_pdf_status/$', 'get_pdf_status', name='get_pdf_status'),
)
