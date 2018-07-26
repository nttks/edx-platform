# -*- coding:UTF-8 -*-
import copy
import logging
from collections import OrderedDict
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils.translation import ugettext as _
from biz.djangoapps.gx_org_group.models import Group, Parent, Child

log = logging.getLogger(__name__)


class OrgTsv:
    """
    Tsv helper class for gx_org_group
    """
    _exception_001 = _('invalid header or file type')  # error case 'a'
    _exception_002 = _(': incorrect the number of columns')  # error case 'b'
    _exception_003 = _(': unknown parent_code=')  # error case 'c'
    _exception_004 = _(': duplicated code: group_code=')  # error case 'd'
    _exception_011 = _(': circular referenced parent_code=')  # error case 'e'
    _exception_021 = _('{line:6} : maximum length over : '
                       + 'column name = {col_name} , maximum length = {max_len} , input length = {input_len}')

    def __init__(self, org, op_user):
        """
        Constructor for OrgTsv
        :param org:  from biz.djangoapps.ga_organization.models import Organization
        :param op_user: from django.contrib.auth.models import User
        """
        self.org = org
        self.op_user = op_user
        self.column_list = OrderedDict([
            ('group_code', _("Organization Group Code")),
            ('group_name', _("Organization Group Name")),
            ('parent_code', _("Parent Organization Code")),
            ('parent_name', _("Parent Organization Name")),
            ('notes', _("notes"))
        ])
        self.code_id_matrix = {}
        self.id_code_matrix = {}
        self.master_data = {}
        self.tran_data = {}
        self.tran_parent_code = {}
        self.tran_group_code_id = {}
        self.parent_dict = {}
        self.child_dict = {}

    def load_master_data(self):
        """
        Loads organization group data from database table
        :return:
        """
        group_data = Group.objects.filter(org_id=self.org).values('id', 'parent_id', 'group_code', 'group_name')
        hash_code_id = {}
        hash_id_code = {}
        hash_master = {}
        for group in group_data:
            hash_code_id[group['group_code']] = group['id']
            hash_id_code[group['id']] = group['group_code']
            hash_master[group['id']] = group
        self.code_id_matrix = hash_code_id
        self.id_code_matrix = hash_id_code
        self.master_data = hash_master

    def import_tran_data(self, p_lines):
        """
        Imports transaction data from upload file ( in memories )
        Stores : self.tran_data[group_code] = { 'line_no': #, 'group_code': <code>, ... ,'notes': <notes> }
        :param p_lines:
        :return:
        """
        # make max length dict
        max_dict = {}
        opts = Group._meta  # inner member access
        column_key_list = self.column_list.keys()
        for key in column_key_list:
            if key in ['parent_code', 'parent_name']:
                continue
            max_dict[key] = opts.get_field(key).max_length
        max_dict['parent_code'] = max_dict['group_code']
        # copy lines
        lines = copy.copy(p_lines)
        header = lines.pop(0)
        if header != self.column_list.values():
            raise ValueError(self._exception_001)
        self.tran_data = {}
        line_no = 2
        error_list = []
        dup_list = {}
        for line in lines:
            record = {'line_no': line_no}
            line_no += 1
            # check the number of TSV columns
            if len(line) != len(column_key_list):
                error_list.append('%6d' % record['line_no'] + self._exception_002)
                continue
            # copy TSV columns into record items
            for i in range(len(column_key_list)):
                key = column_key_list[i]
                value = line[i]
                record[key] = value
                # check maximum length
                if key in max_dict.keys() and max_dict[key] < len(value):
                    error_message = self._exception_021.format(line=record['line_no'], col_name=self.column_list[key],
                                                               max_len=max_dict[key], input_len=len(value))
                    error_list.append(error_message)
            group_code = record['group_code']
            # check the duplicated group code
            if group_code in self.tran_data.keys():
                error_list.append('%6d' % record['line_no'] + self._exception_004 + group_code)
                if group_code not in dup_list:
                    dup_list[group_code] = 0
                dup_list[group_code] += 1
                continue
            # assign record into trans_data
            self.tran_data[group_code] = record
        # copy root cause duplicated group code into error message list
        if dup_list:
            for dup_code in dup_list.keys():
                record = self.tran_data[dup_code]
                error_list.append('%6d' % record['line_no'] + self._exception_004 + dup_code)
        # raise value error if error_list other than zero
        if error_list:
            raise ValueError(error_list)
        return len(lines)

    def create_code_id_matrix_for_tran_data(self):
        """
        Creates group_code id matrix for transaction data
        :return:
        """
        tran_group_code = {}
        for tran in self.tran_data.values():
            group_code = tran['group_code']
            tran_group_code[group_code] = self.get_id(group_code)
        self.tran_group_code_id = tran_group_code
        return len(tran_group_code)

    def validate_parent_code(self):
        """
        Confirms existence of parent code in transaction data
        :return: the number of resolved parent code
        """
        error_messages = []
        for tran in self.tran_data.values():
            parent_code = tran['parent_code']
            line_no = tran['line_no']
            if parent_code and self.get_id(parent_code) < 0:
                if parent_code not in self.tran_group_code_id:
                    error_messages.append('%6d' % line_no + self._exception_003 + parent_code)
        if len(error_messages) > 0:
            raise ValueError(error_messages)
        return len(self.tran_data)

    def merge_trans_data(self):
        """
        Merges transaction data to master data
        :return:
        """
        for e in self.tran_data.values():
            tran_group_code = e['group_code']
            tran_group_name = e['group_name']
            tran_notes = e['notes']
            tran_gid = self.get_id(tran_group_code)
            if tran_gid < 0:  # create
                master = Group.objects.create(
                    parent_id=-1, level_no=-1,
                    group_code=tran_group_code, group_name=tran_group_name,
                    notes=tran_notes, org=self.org, created_by=self.op_user
                )
                self.code_id_matrix[tran_group_code] = master.id
                self.id_code_matrix[master.id] = tran_group_code
            else:  # update
                update_flag = 0
                tran_parent_id = self.get_id(e['parent_code'])
                master = Group.objects.get(pk=tran_gid)
                if master.group_name != tran_group_name:
                    update_flag = 1
                    master.group_name = tran_group_name
                if master.notes != tran_notes:
                    update_flag = 1
                    master.notes = tran_notes
                if master.parent_id != tran_parent_id:
                    update_flag = 1
                    master.parent_id = tran_parent_id
                    master.level_no = -1
                if update_flag != 0:
                    master.save()

    def adopt_stray_children(self):
        """
        Resolves unknown parent_id in transaction data
        :return:
        """
        stray_children = Group.objects.filter(org=self.org).filter(parent_id__lt=0)
        for child in stray_children:
            child_group_code = child.group_code
            tran_parent_code = self.tran_data[child_group_code]['parent_code']
            if tran_parent_code:
                tran_parent_id = self.get_id(tran_parent_code)
                child.parent_id = tran_parent_id
                child.save()
            else:
                child.parent_id = 0
                child.level_no = 0
                child.save()

    def make_parent_data(self):
        """
        Makes parent path for Parent model, set the level_no into Group model
        :return:
        """
        for group in Group.objects.filter(org=self.org):
            str_path = ''
            try:
                parent = Parent.objects.get(group=group)
            except ObjectDoesNotExist:
                parent = Parent.objects.create(org=self.org, group=group, path=str_path)
            parent.path = str_path
            parent.save()
        children = Group.objects.filter(org=self.org).order_by('id')
        for child in children:
            parent_id = child.parent_id
            level_no = 0
            parents_path = []
            if parent_id > 0:
                parents_path.append(parent_id)
                parents_path = self._get_parents(parent_id, parents_path)
                if parents_path[0] < 0:
                    # circular ref error
                    circular_id = abs(parents_path[0])
                    group_code = child.group_code
                    err_parent_code = self.id_code_matrix[circular_id]
                    line_no = self._get_circular_line_no(group_code, err_parent_code)
                    raise ValueError('%6d' % line_no + self._exception_011 + err_parent_code)
                level_no = len(parents_path)
            child.level_no = level_no
            child.save()
            path = []
            for v in reversed(parents_path):
                path.append(v)
            path_str = ','.join([str(x) for x in path])
            parent_list = Parent.objects.filter(group=child)
            if parent_list:
                for parent in parent_list:
                    parent.path = path_str
                    parent.save()

    def _get_circular_line_no(self, group_code, err_parent_code):
        """
        Returns line_no of circular reference error
        :param group_code:
        :param err_parent_code:
        :return:
        """
        line_no = 0
        try:
            line_no = self.tran_data[group_code]['line_no']
            log.warning('found circular reference data by group_code='+group_code)
        except KeyError:
            for key in self.tran_data.keys():
                if self.tran_data[key]['parent_code'] == err_parent_code:
                    line_no = self.tran_data[key]['line_no']
                    log.warning('found circular reference data by parent_code=' + err_parent_code )
                    return line_no
        return line_no

    def _get_parents(self, current_id, parents):
        """
        Gets parent id list recursively
        :param current_id:
        :param parents:
        :return:
        """
        parent = Group.objects.get(id=current_id)
        grand_id = parent.parent_id
        if grand_id > 0 and parents and grand_id == parents[0]:
            parents[0] = -1 * grand_id
            return parents
        if grand_id > 0:
            parents.append(grand_id)
            self._get_parents(grand_id, parents)
        return parents

    def make_child_data(self):
        """
        Makes children id data, and sets to Child model
        :return:
        """
        for current in Group.objects.filter(org=self.org):
            current_id = current.id
            children = []
            children = self.get_children(current_id, children)
            children_str = ','.join([str(c) for c in children])
            child_records = Child.objects.filter(group=current)
            if child_records:
                for record in child_records:
                    record.list = children_str
                    record.save()
            else:
                Child.objects.create(org=self.org, group=current, list=children_str)

    def get_children(self, gid, children):
        """
        Gets child id list recursively
        :param gid:
        :param children:
        :return:
        """
        for child in Group.objects.filter(org=self.org).filter(parent_id=gid):
            child_id = child.id
            children.append(child_id)
            self.get_children(child_id, children)
        return children

    def get_id(self, group_code):
        """
        Gets group id from group_code
        :param group_code:
        :return:
        """
        if group_code and self.code_id_matrix.has_key(group_code):
            return self.code_id_matrix[group_code]
        return -1

    @transaction.atomic
    def import_data(self, lines):
        """
        Imports from TSV data and recreates organization structure data
        :param lines:
        :return:
        """
        log.info('import data -- start')
        log.info('load transaction data from TSV file buffer')
        ret = self.import_tran_data(lines)
        if ret == 0:  # there are no data to import
            return ret
        log.info('load master data from db')
        self.load_master_data()  # for merging transaction data
        log.info('create code id matrix for transaction data')
        self.create_code_id_matrix_for_tran_data()
        log.info('validate parent code')
        self.validate_parent_code()
        log.info('merge transaction data to master')
        self.merge_trans_data()
        log.info('adopt stray children')
        self.adopt_stray_children()
        log.info('make parent data for rapid access')
        self.make_parent_data()
        log.info('make child data for rapid access')
        self.make_child_data()
        log.info('import data -- completed')
        return ret
