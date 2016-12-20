
from django.conf.urls import patterns, url

from ga_shoppingcart.forms import PersonalInfoModelForm
from ga_shoppingcart.views import InputPersonalInfoFormPreview


urlpatterns = patterns('ga_shoppingcart.views',  # nopep8
    url('^notify$', 'notify', name='notify'),
    url(r'^input_personal_info/(?P<order_id>.+)$',
        InputPersonalInfoFormPreview(PersonalInfoModelForm), name='input_personal_info'),
)
