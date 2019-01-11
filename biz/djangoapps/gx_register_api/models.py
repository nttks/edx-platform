from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_organization.models import Organization

# Create your models here.
class APIContractMailBase(models.Model):
    """
    Abstract base class for mail settings for contract
    """
    class Meta:
        app_label = 'gx_register_api'
        abstract = True
        unique_together = ('contract', 'mail_type')
        ordering = ['id']

    MAIL_TYPE = ()
    MAIL_PARAMS = {}

    contract = models.ForeignKey(Contract, default=None, null=True, blank=True)
    mail_type = models.CharField(max_length=255)
    mail_subject = models.CharField(max_length=128)
    mail_body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __init__(self, *args, **kwargs):
        self._meta.get_field('mail_type')._choices = self.MAIL_TYPE
        super(APIContractMailBase, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return u'{}:{}'.format(
            _("Default Template") if self.contract is None else self.contract.contract_name,
            self.mail_type_name,
        )

    @property
    def mail_type_name(self):
        return dict(self.MAIL_TYPE).get(self.mail_type, '')

    @property
    def mail_params(self):
        return {p[0]: p[1] for p in self.MAIL_PARAMS[self.mail_type]}

    @classmethod
    def is_mail_type(cls, mail_type):
        return mail_type in dict(cls.MAIL_TYPE).keys()


class APIContractMail(APIContractMailBase):

    API_MAIL_TYPE_REGISTER_NEW_USER = 'RNU'
    MAIL_TYPE = (
        (API_MAIL_TYPE_REGISTER_NEW_USER, _("For New User")),
    )

    MAIL_PARAM_USERNAME = ('username', _("Replaced with the user name"))
    MAIL_PARAM_LINK_URL1 = ('link_url1', _("Replaced with the URL code for login"))
    MAIL_PARAM_LINK_URL2 = ('link_url2', _("Replaced with the URL code for login"))
    MAIL_PARAM_FULLNAME = ('fullname', _("Replaced with the full name"))
    MAIL_PARAM_EMAIL_ADDRESS = ('email_address', _("Replaced with the user e-mail address"))
    MAIL_PARAM_CONTRACT_NAME = ('contract_name', _(""))
    MAIL_PARAM_COURSE_NAME = ('course_name', _("Replaced with the course name"))
    MAIL_PARAMS = {
        API_MAIL_TYPE_REGISTER_NEW_USER: [
            MAIL_PARAM_USERNAME,
            MAIL_PARAM_FULLNAME,
            MAIL_PARAM_EMAIL_ADDRESS,
            MAIL_PARAM_LINK_URL1,
            MAIL_PARAM_LINK_URL2,
            MAIL_PARAM_CONTRACT_NAME,
            MAIL_PARAM_COURSE_NAME,
        ],


    }

    @classmethod
    def get_register_mail(cls, contract):
        return cls.objects.filter(contract=contract, mail_type=cls.API_MAIL_TYPE_REGISTER_NEW_USER).first()

    @classmethod
    def register_replace_dict(cls, user, fullname, link_url1, link_url2, contract_name, course_name):
        """
        Conversion function to display in the mail body.
        :param user: User.username
        :param fullname: UserProfile.name
        :param link_url1: request.POST['link_url1']
        :param link_url2: request.POST['link_url2']
        :param contract_name: Contract.contract_name
        :param course_name: CourseOverView.display_name
        :return:
        """
        replace_dict = {
            cls.MAIL_PARAM_USERNAME[0]: user.username.encode('utf-8'),
            cls.MAIL_PARAM_FULLNAME[0]: fullname.encode('utf-8'),
            cls.MAIL_PARAM_EMAIL_ADDRESS[0]: user.email.encode('utf-8'),
            cls.MAIL_PARAM_LINK_URL1[0]: link_url1.encode('utf-8'),
            cls.MAIL_PARAM_LINK_URL2[0]: link_url2.encode('utf-8'),
            cls.MAIL_PARAM_CONTRACT_NAME[0]: contract_name.encode('utf-8'),
            cls.MAIL_PARAM_COURSE_NAME[0]: course_name.encode('utf-8'),
        }
        return replace_dict


class APIGatewayKey(models.Model):
    class Meta:
        app_label = 'gx_register_api'
        unique_together = ('api_key', 'org_id')
    def __unicode__(self):
        return self.org_id.org_name + ' : ' + self.api_key

    api_key = models.CharField(max_length=255)
    org_id = models.ForeignKey(Organization)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)