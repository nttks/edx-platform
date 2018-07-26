from factory.django import DjangoModelFactory

from biz.djangoapps.gx_member.models import Member, MemberTaskHistory, MemberRegisterTaskTarget


class MemberFactory(DjangoModelFactory):
    """Factory for the Member model"""

    class Meta(object):
        model = Member


class MemberTaskHistoryFactory(DjangoModelFactory):
    """Factory for the MemberTaskHistory model"""

    class Meta(object):
        model = MemberTaskHistory


class MemberRegisterTaskTargetFactory(DjangoModelFactory):
    """Factory for the MemberRegisterTaskTarget model"""

    class Meta(object):
        model = MemberRegisterTaskTarget

