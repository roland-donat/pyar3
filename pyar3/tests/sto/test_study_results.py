import pytest
import os
import pkg_resources
import pathlib
import pyar3

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb

DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
EXPECTED_PATH = os.path.join(os.path.dirname(__file__), "expected")
pathlib.Path(DATA_PATH).mkdir(parents=True, exist_ok=True)
pathlib.Path(EXPECTED_PATH).mkdir(parents=True, exist_ok=True)


def test_study_results_load():

    study_res_filename = os.path.join(DATA_PATH,
                                      "results_test_sys_1.csv")

    study_res = pyar3.STOStudyResults.from_result_csv(study_res_filename)

    ipdb.set_trace()

    assert True
