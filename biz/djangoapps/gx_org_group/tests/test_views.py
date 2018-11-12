from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from student.tests.factories import UserFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.gx_org_group.models import Group, Right, Parent, Child
from biz.djangoapps.gx_org_group.tests.factories import GroupUtil, GroupFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_member.models import Member

class OrgGroupListViewTest(BizContractTestBase):
    """
    Test Class for gx_org_group
    """
    def setUp(self):
        super(BizContractTestBase, self).setUp()
        self.user_gacco_staff = UserFactory(username='gacco_staff', is_staff=True, is_superuser=True)
        self.user_tac_aggregator = UserFactory(username='tac_aggregator')
        self.user_a_director = UserFactory(username='a_director')
        self.user_manager1 = UserFactory(username='manager1')
        self.user_manager2 = UserFactory(username='manager2')

        self.org_a = self._create_organization(org_name='org_a', org_code='a', creator_org=self.gacco_organization)

        self.manager_platformer = ManagerFactory.create(org=self.gacco_organization, user=self.user_gacco_staff,
                                                        permissions=[self.platformer_permission])
        self.manager_manager1 = ManagerFactory.create(org=self.gacco_organization, user=self.user_manager1,
                                                      permissions=[self.manager_permission])
        self.manager_manager2 = ManagerFactory.create(org=self.gacco_organization, user=self.user_manager2,
                                                      permissions=[self.manager_permission])

    def _index_view(self):
        """
        Returns URL of group list as index
        :return:
        """
        return reverse('biz:group:group_list')

    def _delete_group(self):
        """
        Returns URL of delete group
        :return:
        """
        return reverse('biz:group:delete_group')

    def _upload_csv(self):
        """
        Returns URL of file upload API
        :return:
        """
        return reverse('biz:group:upload_csv')

    def _download_csv(self):
        """
        Returns URL of group list download API
        :return:
        """
        return reverse('biz:group:download_csv')

    def _detail_view(self, selected_group_id):
        """
        Returns URL of detail of group known access right settings
        :param selected_group_id:
        :return:
        """
        return reverse('biz:group:detail', kwargs={'selected_group_id': selected_group_id})

    def _accessible_user_list(self):
        """
        Returns URL of accessible user list API
        :return:
        """
        return reverse('biz:group:accessible_user_list')

    def _accessible_parent_list(self):
        """
        Returns URL of parent group accessible user list API
        :return:
        """
        return reverse('biz:group:accessible_parent_list')

    def _grant_right(self):
        """
        Returns URL of access right grant API
        :return:
        """
        return reverse('biz:group:grant_right')

    @property
    def _csv_header(self):
        return "\t".join([
            'Organization Group Code',
            'Organization Group Name',
            'Parent Organization Code',
            'Parent Organization Name',
            'notes'
        ]) + '\r\n'

    @property
    def _csv_data_first(self):
        csv_data = "G01\tG1\t\t\t\r\n" \
                   "G01-01\tG1-1\tG01\tG1\t\r\n" \
                   "G01-01-01\tG1-1-1\tG01-01\tG1-1\t\r\n" \
                   "G01-01-02\tG1-1-2\tG01-01\tG1-1\t\r\n" \
                   "G01-02\tG1-2\tG01\tG1\t\r\n" \
                   "G02\tG2\t\t\t\r\n" \
                   "G02-01\tG2-1\tG02\tG2\t\r\n" \
                   "G02-01-01\tG2-1-1\tG02-01\tG2-1\t\r\n" \
                   "G02-01-02\tG2-1-2\tG02-01\tG2-1\t\r\n" \
                   "G02-02\tG2-2\tG02\tG2\t\r\n"
        return csv_data

    @property
    def _csv_data_cir_err_master(self):
        csv_data = "1000\tgroup1\t\t\t\r\n" \
                   "1000aaa\tgroup3\t1000\tgroup1\t\r\n" \
                   "1001\tgroup4\t\t\t\r\n" \
                   "1002\tgroup3\t1000\tgroup1\t\r\n" \
                   "1003\tgroup3\t1000\tgroup1\t\r\n" \
                   "1005\tgroup5\t\t\t\r\n" \
                   "1006\tgroup6\t\t\t\r\n" \
                   "1007\tgroup7\t1009\tgroup9\t\r\n" \
                   "1008\tgroup8\t\t\t\r\n" \
                   "1009\tgroup9\t\t\t\r\n" \
                   "aaaaaaaaabbbbbbbbbcc\tgroup3\t1000\tgroup1\t\r\n"
        return csv_data

    @property
    def _csv_data_cir_err_tran(self):
        csv_data = "1000\tgroup6\t1000\t\t\r\n"
        return csv_data

    def _test_upload_cir_err_master(self):
        csv_header = self._csv_header
        csv_data = self._csv_data_cir_err_master
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(200, response.status_code)

    def _test_upload_first(self):
        csv_header = self._csv_header
        csv_data = self._csv_data_first
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(200, response.status_code)
        self._test_group('G01', 'G1', '', '', '', 0, [],['G01-01', 'G01-02', 'G01-01-01', 'G01-01-02'])
        self._test_group('G01-01', 'G1-1', 'G01', 'G1', '', 1, ['G01'], ['G01-01-01', 'G01-01-02'])
        self._test_group('G01-01-01', 'G1-1-1', 'G01-01', 'G1-1', '', 2, ['G01', 'G01-01'], [])
        self._test_group('G01-01-02', 'G1-1-2', 'G01-01', 'G1-1', '', 2, ['G01', 'G01-01'], [])
        self._test_group('G01-02', 'G1-2', 'G01', 'G1', '', 1, ['G01'], [])
        self._test_group('G02', 'G2',  '', '', '', 0, [], ['G02-01', 'G02-02', 'G02-01-01', 'G02-01-02'])
        self._test_group('G02-01', 'G2-1', 'G02', 'G2', '', 1, ['G02'], ['G02-01-01', 'G02-01-02'])
        self._test_group('G02-01-01', 'G2-1-1', 'G02-01', 'G2-1', '', 2, ['G02', 'G02-01'], [])
        self._test_group('G02-01-02', 'G2-1-2', 'G02-01', 'G2-1', '', 2, ['G02', 'G02-01'], [])
        self._test_group('G02-02', 'G2-2', 'G02', 'G2', '', 1, ['G02'],[])

    def _test_upload_second(self):
        csv_header = self._csv_header
        csv_data = "G02\tG02underG1\tG01\tG1\tmoved to under G1\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(200, response.status_code)
        self._test_group('G02', 'G02underG1', 'G01', 'G1', 'moved to under G1', 1, ['G01'], ['G02-01', 'G02-02', 'G02-01-01', 'G02-01-02'])

    def _test_upload_third(self):
        csv_header = self._csv_header
        csv_data = "G03\tG3\tG01\tG1\tconnect to under G1\r\n" \
                   "G03-01\tG3-1\tG03\tG3\t\r\n" \
                   "G03-01-01\tG3-1-1\tG03-01\tG3-1\t\r\n" \
                   "G03-01-02\tG3-1-2\tG03-01\tG3-1\t\r\n" \
                   "G03-02\tG3-2\tG03\tG3\t\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(200, response.status_code)
        self._test_group('G03', 'G3', 'G01', 'G1', 'connect to under G1', 1, ['G01'], ['G03-01', 'G03-02', 'G03-01-01', 'G03-01-02'])
        self._test_group('G03-01', 'G3-1', 'G03', 'G3', '', 2, ['G01', 'G03'], ['G03-01-01', 'G03-01-02'])
        self._test_group('G03-01-01', 'G3-1-1', 'G03-01', 'G3-1', '', 3, ['G01', 'G03', 'G03-01'], [])
        self._test_group('G03-01-02', 'G3-1-2', 'G03-01', 'G3-1', '', 3, ['G01', 'G03', 'G03-01'], [])
        self._test_group('G03-02', 'G3-2', 'G03', 'G3', '', 2, ['G01', 'G03'], [])

    def _test_group(self, group_code, group_name, parent_code, parent_name, notes, level_no, parents_codes, children_codes):
        group = Group.objects.get(group_code=group_code)
        self.assertEqual(group_name, group.group_name) # Checking Group Name
        self.assertEqual(notes, group.notes) # Checking Note
        self.assertEqual(level_no, group.level_no) # Checking Level

        if parent_code == '':
            self.assertEqual(0, group.parent_id) # Checking Parent Id is not set
        else:
            parent = Group.objects.get(id=group.parent_id)
            self.assertEqual(parent_code, parent.group_code) # Checking Parent Code
            self.assertEqual(parent_name, parent.group_name) # Checking Parent Name

        self._test_parents_data(group, parents_codes) # Checking Parent Table
        self._test_children_data(group, children_codes) # Checking Children Table

    def _test_parents_data(self, group, parents_codes):
        parents_data = Parent.objects.get(group_id=group.id)
        if len(parents_codes) > 0:
            groups = [Group.objects.get(id=int(group_id)) for group_id in self._split(parents_data.path)]
            groups_codes = set([group.group_code for group in groups])
            self.assertEqual(groups_codes, set(parents_codes)) # Checking Parent Codes
        else:
            self.assertEqual('', parents_data.path) # Checking Path is not set

    def _test_children_data(self, group, children_codes):
        children_data = Child.objects.get(group_id=group.id)
        if len(children_codes) > 0:
            groups = [Group.objects.get(id=int(group_id)) for group_id in self._split(children_data.list)]
            groups_codes = set([group.group_code for group in groups])
            self.assertEqual(groups_codes, set(children_codes)) # Checking Codes is not set
        else:
            self.assertEqual('', children_data.list)  # Checking List is not set

    def _split(self, string):
        return [int(group_id) for group_id in string.split(',')]

    def _test_grant_right(self, group_id, username):
        """
        Tests grant access right API
        :return:
        """

        # add a grant user
        user_str = username
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': group_id, 'action': 'allow', 'grant_user_str': user_str})
        self.assertEqual(200, response.status_code)

    def test_index(self):
        """
        Tests group list page
        :return:
        """
        self.setup_user()
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._index_view())
        self.assertEqual(200, response.status_code)

    def test_index_exist_data(self):
        """
        Tests group list tree data
        :return:
        """
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.get(group_code="G01").id
        child_group_id = Group.objects.get(group_code="G01-01").id

        # test index
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            path = self._index_view()
            response = self.client.get(path)

        self.assertEqual(200, response.status_code)
        self.assertEqual(parent_group_id, 9)
        self.assertEqual(child_group_id, 3)

        self._test_grant_right(parent_group_id, self.manager_manager1.user.username)
        parent_group = Group.objects.get(group_code="G01")
        right = Right.objects.filter(group_id=parent_group_id)
        active_user = UserFactory.create()
        self._create_member(
            org=self.org_a, group=parent_group, user=active_user,
            code="code_1", is_active=True, is_delete=False
        )
        member = Member.objects.filter(group_id=parent_group_id)
        group = Group.objects.all()
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            path = self._index_view()
            response = self.client.get(path)
        self.assertEqual(200, response.status_code)
        self.assertEqual(group.count(), 10)
        self.assertEqual(right.count(), 1)
        self.assertEqual(member.count(), 1)

    def _create_member(
            self, org, group, user, code, is_active, is_delete,
            org1='', org2='', org3='', org4='', org5='', org6='', org7='', org8='', org9='', org10='',
            item1='', item2='', item3='', item4='', item5='', item6='', item7='', item8='', item9='', item10=''):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=user,
            creator_org=org,
            updated_by=user,
            updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            org1=org1, org2=org2, org3=org3, org4=org4, org5=org5, org6=org6, org7=org7, org8=org8, org9=org9,
            org10=org10,
            item1=item1, item2=item2, item3=item3, item4=item4, item5=item5, item6=item6, item7=item7, item8=item8,
            item9=item9, item10=item10
        )

    def test_group_delete(self):
        self.setup_user()
        self._test_upload_first()

        # exist manager
        group = Group.objects.all()
        group_id = Group.objects.filter(group_code="G01-01-01").first().id
        self._test_grant_right(group_id, self.manager_manager1.user.username)
        right = Right.objects.filter(group_id=group_id)

        self.assertEqual(group.count(), 10)
        self.assertEqual(right.count(), 1)

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            self._index_view()
            response = self.client.post(self._delete_group(),
                                        {'num': group_id, 'belong': 1, 'grouping': [str(group_id)], 'group_name': 'G1-1-1'})
        group = Group.objects.all()
        right = Right.objects.filter(group_id=group_id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(group.count(), 9)
        self.assertEqual(right.count(), 0)

        # exist member
        group_id_child1 = Group.objects.filter(group_code="G02-01-01").first().id
        group_id_child2 = Group.objects.filter(group_code="G02-01-02").first().id
        group_id = Group.objects.filter(group_code="G02-01").first().id
        current_group = Group.objects.get(group_code="G02-01-01")

        active_user = UserFactory.create()
        self._create_member(
            org=self.org_a, group=current_group, user=active_user,
            code="code_1", is_active=True, is_delete=False
        )
        member = Member.objects.all()
        self.assertEqual(member.count(), 1)

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            self._index_view()
            response = self.client.post(self._delete_group(),
                                        {'num': group_id, 'belong': 1, 'grouping': [str(group_id) + ',' + str(group_id_child1) + ',' + str(group_id_child2)], 'group_name': 'G2-1'})
        member = Member.objects.filter(group_id=group_id)
        group = Group.objects.all()

        self.assertEqual(200, response.status_code)
        self.assertEqual(member.count(), 0)
        self.assertEqual(group.count(), 6)

        # exist member and manager
        group_id = Group.objects.filter(group_code="G02").first().id
        self._test_grant_right(group_id, self.manager_manager1.user.username)
        right = Right.objects.filter(group_id=group_id)
        active_user = UserFactory.create()
        current_group = Group.objects.get(group_code="G02")
        self._create_member(
            org=self.org_a, group=current_group, user=active_user,
            code="code_2", is_active=True, is_delete=False
        )
        member = Member.objects.filter(group_id=group_id)

        self.assertEqual(right.count(), 1)
        self.assertEqual(member.count(), 1)

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            self._index_view()
            response = self.client.post(self._delete_group(),
                                        {'num': group_id, 'belong': 1, 'grouping': [str(group_id)], 'group_name': 'G2'})
        group = Group.objects.all()
        member = Member.objects.filter(group_id=group_id)
        right = Right.objects.filter(group_id=group_id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(group.count(), 5)
        self.assertEqual(member.count(), 0)
        self.assertEqual(right.count(), 0)

        # Not exist member and manager
        group_id = Group.objects.filter(group_code="G01-01-02").first().id
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            self._index_view()
            response = self.client.post(self._delete_group(),
                                        {'num': group_id, 'belong': 0, 'grouping': [str(group_id)], 'group_name': 'G1-1-2'})
        self.assertEqual(200, response.status_code)
        self.assertEqual(group.count(), 4)

    def test_fail_group_delete(self):
        # Not id
        self.setup_user()
        self._test_upload_first()
        group = Group.objects.all()
        self.assertEqual(group.count(), 10)

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            self._index_view()
            response = self.client.post(self._delete_group(),
                                        {'num': 10, 'belong': 1, 'grouping': ['abc'], 'group_name': 'G1'})
        self.assertEqual(400, response.status_code)
        group = Group.objects.all()
        self.assertEqual(group.count(), 10)

    def test_upload_fail(self):
        """
        Tests upload group list API fail
        :return:
        """
        # init
        csv_header = self._csv_header
        self.setup_user()

        # test auth error
        csv_content = ""
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # test unicode error
        csv_content = self._csv_header
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # invalid header format (_exception_001)
        csv_content = "group_code\tgroup_name\txxx_parent_code\tparent_name\tnotes\r\n".encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # wrong number of columns (_exception_002)
        csv_data = "G01-01\tG1-1\tG01\t\t\t\t\tG1\t\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # invalid parent code (_exception_003)
        csv_data = "G01-01\tG1-1\tXXX\tG1\t\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # duplicated group code (_exception_004)
        csv_data = "G01-01\tG1-1\t\t\t\r\n" + "G01-01\tG1-1\t\t\t\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # circular ref (_exception_011) (1) (Parent Code in import file)
        csv_data = "G02-02\tG2-2\tG02-02\tG2-2\tcircular ref1\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # circular ref (_exception_011) (2) (Parent Code in Group model)
        self._test_upload_cir_err_master()  # load master data
        csv_data = self._csv_data_cir_err_tran
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

        # max length over  (_exception_021)
        csv_data = "ABCDEFGHIJ12345678901\tMAX_CODE\t\t\tgroup code error\r\n"
        csv_content = (csv_header + csv_data).encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(400, response.status_code)

    def test_upload_success(self):
        """
        Test upload group list API success
        :return:
        """
        # prepare
        csv_header = self._csv_header
        self.setup_user()

        # import empty
        csv_content = csv_header.encode('UTF-16')
        upload_file = SimpleUploadedFile("org_group.csv", csv_content)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._upload_csv(), {'organization': '', 'org_group_csv': upload_file})
        self.assertEqual(200, response.status_code)

        # test upload data
        self._test_upload_first()
        self._test_upload_second()
        self._test_upload_third()

    def test_download_csv(self):
        """
        Test download group list API
        :return:
        """
        self.setup_user()
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._download_csv())
        self.assertEqual(200, response.status_code)

    def test_detail(self):
        # init
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.filter(group_code="G01").first().id
        child_group_id = Group.objects.filter(group_code="G01-01").first().id

        self._test_grant_right(parent_group_id, self.manager_manager1.user.username)

        # test detail
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            path = self._detail_view(child_group_id)
            response = self.client.get(path)
        self.assertEqual(200, response.status_code)

    def test_accessible_user_list(self):
        """
        Test accessible user list page
        :return:
        """
        # init
        self.setup_user()
        self._test_upload_first()
        group_id = Group.objects.filter(group_code="G01").first().id

        # add a access right for manager
        self._test_grant_right(group_id, self.manager_manager1.user.username)

        # test accessible user list
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._accessible_user_list(), {'group_id': group_id})
        self.assertEqual(200, response.status_code)

    def test_accessible_parent_list(self):
        """
        Tests accessible parent group user list page
        :return:
        """
        # init
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.filter(group_code="G01").first().id
        child_group_id = Group.objects.filter(group_code="G01-01").first().id
        self._test_grant_right(parent_group_id, self.manager_manager1.user.username)

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._accessible_parent_list(), {'group_id': child_group_id})
        self.assertEqual(200, response.status_code)

    def test_grant_right_fail(self):
        """
        Tests grant access right API
        :return:
        """
        # init
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.filter(group_code="G01").first().id
        child_group_id = Group.objects.filter(group_code="G01-01").first().id
        grandson_group_id = Group.objects.filter(group_code="G01-01-01").first().id

        # unknown username (_exception_002)
        user_str = 'unknown username'
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': parent_group_id, 'action': 'allow', 'grant_user_str': user_str})
        self.assertEqual(200, response.status_code)

        # unknown email (_exception_001)
        user_str = 'unknown_username@example.com'
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': parent_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # user is not belonging to manager (_exception_003)
        user_str = 'test'
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': parent_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # a manager but does not have access right (_exception_004)
        user_str = self.manager_platformer.user.username
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': parent_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # *PREPARE* add a access right for manager
        self._test_grant_right(parent_group_id, self.manager_manager1.user.username)

        # *TEST* duplicated manager (_exception_007)
        user_str = self.manager_manager1.user.username
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': parent_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # *TEST* exists in parent group (_exception_005)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': child_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # *PREPARE* add a access right into grandson
        user_str = self.manager_manager2.user.username
        self._test_grant_right(grandson_group_id, user_str)

        # *TEST* exists in child group (_exception_006)
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': child_group_id, 'action': 'allow', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

    def test_grant_right_success(self):
        """
        Tests grant access right API
        :return:
        """

        # init
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.filter(group_code="G01").first().id

        # add a access right for manager
        self._test_grant_right(parent_group_id, self.manager_manager1.user.username)

    def test_revoke_right(self):
        """
        Tests revoke access right API
        :return:
        """
        # init
        self.setup_user()
        self._test_upload_first()
        parent_group_id = Group.objects.filter(group_code="G01").first().id
        group_id = parent_group_id

        # add a access right for manager
        grant_username = self.manager_manager1.user.username
        self._test_grant_right(group_id, grant_username)

        # unknown username
        user_str = 'unknown'
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': group_id, 'action': 'revoke', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # known username
        user_str = 'test'
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': group_id, 'action': 'revoke', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

        # revoke success
        user_str = grant_username
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._grant_right(),
                                        {'group_id': group_id, 'action': 'revoke', 'grant_user_str':  user_str})
        self.assertEqual(200, response.status_code)

    def test_models(self):
        """
        test model unicode string for Django Admin
        :return:
        """
        # init
        self.setup_user()
        gu = GroupUtil(self.org_a, self.user_a_director)
        gu.import_data()

        # test unicode name
        group = Group.objects.get(group_code="G01")
        self.assertEqual(u"G1", unicode(group))

        # test unicode name
        parent = Parent.objects.get(group=group)
        self.assertEqual(u"G1", unicode(parent))

        # test unicode name
        child = Child.objects.get(group=group)
        self.assertEqual(u"G1", unicode(child))

        # test unicode name
        self._test_grant_right(group.id, self.manager_manager1.user.username)
        r = Right.objects.get(group=group)
        self.assertEqual(unicode(self.manager_manager1.user.email), unicode(r))

        # test grant right
        gu.grant_right(group, self.manager_manager1.user)
