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


def test_study_load():

    study_filename = os.path.join(DATA_PATH,
                                  "study_1.yaml")

    study = pyar3.STOStudy.from_yaml(study_filename)

    idf_filename = os.path.join(EXPECTED_PATH,
                                "study_1.idf")
    study.to_idf(idf_filename)
    print(study)

    assert True
