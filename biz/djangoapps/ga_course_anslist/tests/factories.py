import csv
import copy

CONST_TEST_FILE = "biz/djangoapps/ga_course_anslist/tests/test_data.tsv"


def get_data_csv():
    test_lst = []

    with open(CONST_TEST_FILE) as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            test_lst.append(row)

    header = copy.deepcopy(test_lst[0])
    del test_lst[0]
    test_dct_lst = []
    dct = {}
    for row in test_lst:
        for key, val in zip(header, row):
            dct.update({key : val})

        test_dct_lst.append(copy.deepcopy(dct))
        dct.clear()

    return test_dct_lst


