
from django.conf.urls import patterns, url


urlpatterns = patterns('ga_shoppingcart.views',  # nopep8
    url('^notify$', 'notify', name='notify'),
)
