from factory.django import DjangoModelFactory
from biz.djangoapps.gx_org_group.models import Group, Right
from biz.djangoapps.gx_org_group.builders import OrgTsv


class GroupFactory(DjangoModelFactory):
    class Meta(object):
        model = Group


class RightFactory(DjangoModelFactory):
    class Meta(object):
        model = Right


class GroupUtil:
    """
    Org Group Utility
    """
    def __init__(self, org, user):
        self.org = org
        self.user = user

    @property
    def _csv_header(self):
        return [
            'Organization Group Code',
            'Organization Group Name',
            'Parent Organization Code',
            'Parent Organization Name',
            'notes'
        ]

    @property
    def _csv_data1(self):
        csv_data = [
            self._csv_header,
            ["G01", "G1", "", "",""],
            ["G01-01", "G1-1", "G01", "G1",""],
            ["G01-01-01", "G1-1-1", "G01-01", "G1-1",""],
            ["G01-01-02", "G1-1-2", "G01-01", "G1-1",""],
            ["G01-02", "G1-2", "G01", "G1",""],
            ["G02", "G2", "", "",""],
            ["G02-01", "G2-1", "G02", "G2",""],
            ["G02-01-01", "G2-1-1", "G02", "G2-1",""],
            ["G02-01-02", "G2-1-2", "G02", "G2-1",""],
            ["G02-02", "G2-2", "G02", "G2",""],
        ]
        return csv_data

    def import_data(self, csv_data=None):
        """
        import csv string list into Group model
        :param csv_data: list (includes header)
        :return:
        """
        if csv_data is None:
            csv_data = self._csv_data1
        org_tsv = OrgTsv(self.org, self.user)
        ret = org_tsv.import_data(csv_data)
        return ret

    def grant_right(self, group, user):
        """
        grant manager user to the group
        :param group:
        :param user:
        :return:
        """
        RightFactory.create(org=self.org, group=group, user=user, created_by=user, creator_org=self.org)
