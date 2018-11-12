import logging
from django.conf import settings

from django.db import models
from biz.djangoapps.ga_organization.models import Organization

log = logging.getLogger("edx.cms")

class OrgUsernameRule(models.Model):
    """
    OrgUsernameRule model
    """
    prefix = models.CharField(max_length=255, unique=True)
    org = models.ForeignKey(Organization)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, null=True, db_index=True, blank=True)

    class Meta:
        app_label = 'gx_username_rule'

    def __unicode__(self):
        return self.prefix

    @classmethod
    def exists_org_prefix(cls, str, org=0):
        """
        except Exception OperationError:
        Because we are running the test with lms,
        we do not need to run the test with cms
        :param str:
        :param org:
        :return Bool:
        True == pass
        False == error
        """
        try:
            str = str.lower()
            # a = 1 + 'a'
            if cls.objects.filter(org=org).exists():
                if str.startswith(tuple([r.prefix.lower() for r in cls.objects.filter(org=org)])):
                    return True
                else:
                    return False
            if cls.objects.exclude(org=org).exists():
                if str.startswith(tuple([r.prefix.lower() for r in cls.objects.exclude(org=org)])):
                    return False
                else:
                    return True
            return True
        except Exception as e:
            if settings.ROOT_URLCONF == 'cms.urls':
                logging.exception(e)
                return True
            else:
                raise e