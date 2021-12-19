import pandas as pd
import typing
import pydantic
import pkg_resources
import yaml
import uuid
from lxml import etree
import subprocess
import os
import pathlib
import sys
import math

import logging

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: 401

PandasDataFrame = typing.TypeVar('pd.core.dataframe')

AR3SIMU_LOCAL_CONFIG_FILENAME = os.path.join(str(pathlib.Path.home()),
                                             ".ar3simu.conf")
# Utility functions
# -----------------


def find_directory(dirname=None, of_file=None, root='.'):
    for path, dirs, files in os.walk(root):
        if not(dirname is None) and (dirname in dirs):
            return os.path.join(path, dirname)
        elif not(of_file is None) and (of_file in files):
            return path

    return None


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


class SimIndicator(pydantic.BaseModel):
    id: str = pydantic.Field(None, description="Indicator unique id")
    name: str = pydantic.Field(None, description="Indicator short name")
    description: str = pydantic.Field(
        None, description="Indicator description")
    unit: str = pydantic.Field(None, description="Indicator unit")
    tags: typing.List[str] = pydantic.Field(
        [], description="List of tags to provide indicator metadata")


class STOIndicator(SimIndicator):
    observer: str = pydantic.Field(None, description="AR3 observer name")
    block: str = pydantic.Field(None, description="AR3 observer block name")
    type: str = pydantic.Field(None, description="Indicator type")
    measure: str = pydantic.Field(None, description="Measure")
    value: str = pydantic.Field(
        None, description="Indicator value to monitor (for categorical indicator)")
    stats: list = pydantic.Field([], description="Stats to be computed")
    data: PandasDataFrame = pydantic.Field(
        None, description="Indicator estimates")

    @pydantic.root_validator()
    def cls_validator(cls, obj):
        if obj.get('id') is None:
            obj['id'] = str(uuid.uuid4())

        if obj.get('name') is None:
            obj['name'] = f"{obj.get('observer', '')}__{obj.get('measure', '')}"

        if obj.get('description') is None:
            obj['description'] = obj['name']

        if obj.get('type') == "Boolean":
            if obj.get('value') in [True, False, "true", "false", "True", "False"]:
                obj['value'] = str(obj.get('value')).lower()
            else:
                obj['value'] = "true"
        else:
            obj['value'] = ''

        return obj


class STOMetaData(pydantic.BaseModel):
    main_block: str = pydantic.Field(
        None, description="Name of model main block")
    source_file: str = pydantic.Field(None, description="Source file path")
    tool_version: str = pydantic.Field(None, description="Simulator version")
    compiler_version: str = pydantic.Field(
        None, description="AR3 compiler version")

    @classmethod
    def from_raw_lines(cls, raw_lines):

        cls_specs = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split("\t")
            key = line_split[0].strip()
            if key == "Meta-Data":
                start = i + 1
                break

        for i, line in enumerate(raw_lines[start:]):

            line_split = line.split("\t")

            key = line_split[0].strip()
            if len(line_split) <= 1:
                break
            value = line_split[1].strip()

            if key == "Source file":
                cls_specs["source_file"] = value
            elif key == "Main block":
                cls_specs["main_block"] = value
            elif key == "Tool version":
                cls_specs["tool_version"] = value
            elif key == "Compiler version":
                cls_specs["compiler_version"] = value

        obj = cls(**cls_specs)

        return obj


class STOSimulationParam(pydantic.BaseModel):
    nb_runs: int = pydantic.Field(
        100, description="Number of simulations")
    seed: int = pydantic.Field(1234, description="Simulator seed")
    result_filename: str = pydantic.Field(
        "result.csv", description="Result filename")
    schedule_name: str = pydantic.Field(
        "Date", description="Result filename")
    schedule_unit: str = pydantic.Field(
        None, description="Result filename")
    schedule_from: float = pydantic.Field(...,
                                          description="Simulation schedule origin")
    schedule_to: float = pydantic.Field(...,
                                        description="Simulation schedule end")
    schedule_step: float = pydantic.Field(...,
                                          description="Simulation schedule step")


class STOMissionResult(pydantic.BaseModel):
    nb_executions: int = pydantic.Field(
        None, description="Number of simulations")
    seed: int = pydantic.Field(None, description="Simulator seed")
    mission_time: float = pydantic.Field(None, description="Mission time")
    date_start: str = pydantic.Field(None, description="Simulation date start")
    date_end: str = pydantic.Field(None, description="Simulation date end")
    event_fired_stats: dict = pydantic.Field({},
                                             description="Simulation date end")

    @classmethod
    def from_raw_lines(cls, raw_lines):

        cls_specs = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split("\t")
            key = line_split[0].strip()
            if key == "Mission":
                start = i + 1
                break

        indic_def_lines = raw_lines[start:]
        for i, line in enumerate(indic_def_lines):

            line_split = line.split("\t")

            key = line_split[0].strip()
            if len(line_split) <= 1:
                break
            value = line_split[1].strip()

            if key == "Number of executions":
                cls_specs["nb_executions"] = value
            elif key == "Seed":
                cls_specs["seed"] = int(value)
            elif key == "Mission time":
                cls_specs["mission_time"] = float(value)
            elif key == "Started":
                cls_specs["date_start"] = value
            elif key == "Completed":
                cls_specs["date_end"] = value
            elif key == "Number of events fired per execution":
                event_fire_stats_str = indic_def_lines[i+2].split("\t")

                cls_specs["event_fired_stats"] = dict(
                    mean=float(event_fire_stats_str[0]),
                    min=float(event_fire_stats_str[1]),
                    max=float(event_fire_stats_str[2]))

        obj = cls(**cls_specs)

        return obj


class STOStudyResults(pydantic.BaseModel):

    meta_data: STOMetaData = pydantic.Field(
        STOMetaData(), description="Study meta-line")

    mission: STOMissionResult = pydantic.Field(
        STOMissionResult(), description="Performance fitting parametters")

    indicators: typing.Dict[str, STOIndicator] = pydantic.Field(
        {}, description="Dictionary of simulation indicators")

    @classmethod
    def from_result_csv(cls, filename, **kwrds):

        with open(filename, 'r',
                  encoding="utf-8") as file:

            file_lines = file.readlines()

        obj = cls.from_raw_lines(file_lines)
        # obj = cls(**{**study_specs, **kwrds})

        # obj.load_data()
        # obj.build_models_perf()

        return obj

    @classmethod
    def from_raw_lines(cls, raw_lines):

        cls_specs = {}

        cls_specs["meta_data"] = STOMetaData.from_raw_lines(raw_lines)
        cls_specs["mission"] = STOMissionResult.from_raw_lines(raw_lines)
        cls_specs["indicators"] = cls.indicators_from_raw_lines(raw_lines)

        # Update indicator block information
        for indic_id, indic in cls_specs["indicators"].items():
            if not(cls_specs["meta_data"].main_block is None):
                indic.block = cls_specs["meta_data"].main_block

        obj = cls(**cls_specs)

        return obj

    @classmethod
    def indicators_from_raw_lines(cls, raw_lines):

        indics_dict = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split("\t")
            key = line_split[0].strip()
            if key == "Indicators":
                start = i + 2
                break

        indic_def_lines = raw_lines[start:]
        for i, line in enumerate(indic_def_lines):

            line_split = line.split("\t")

            if len(line_split) <= 1:
                start = i + 1
                break

            indic_id = line_split[0].strip()
            observer = line_split[1].strip()
            # TODO: TO BE IMPROVED BUT NEED MORE TETS
            # value = line_split[2].strip()
            # measure = line_split[3].strip()
            indics_dict[indic_id] = \
                STOIndicator(
                    id=indic_id,
                    name=indic_id,
                    observer=observer)
            # value=value,
            # type="Boolean" if value in ["true", "false"] else "Real",
            # measure=measure)

        indic_id = None
        indic_data_lines = indic_def_lines[start:]
        for i, line in enumerate(indic_data_lines):

            line_split = line.strip().split("\t")

            if line_split[0] == "Indicator":
                indic_id = line_split[1]
                indics_dict[indic_id].data = []

            elif is_float(line_split[0]) and not(indic_id is None):

                data_cur = dict(
                    date=float(line_split[0]),
                    sample_size=int(line_split[1]),
                    mean=float(line_split[2])
                    if len(line_split) >= 3 else float("NaN"),
                    std=float(line_split[3])
                    if len(line_split) >= 4 else float("NaN")
                )
                # Compute IC95%
                if "std" in data_cur.keys():
                    data_cur["ic95"] = 1.96*data_cur["std"] / \
                        math.sqrt(data_cur["sample_size"])

                indics_dict[indic_id].data.append(data_cur)

            # indics_dict[indic_id]
        for indic_id in indics_dict:
            indics_dict[indic_id].data = \
                pd.DataFrame(indics_dict[indic_id].data)

        return indics_dict

    def to_excel(self, filename):

        writer = pd.ExcelWriter(filename, engine='xlsxwriter')

        for indic_id, indic in self.indicators.items():
            indic.data.to_excel(writer,
                                sheet_name=indic_id,
                                index=False)

        writer.save()


class STOStudy(pydantic.BaseModel):

    name: str = pydantic.Field(
        None, description="Name of the study")

    description: str = pydantic.Field(
        None, description="Study description")

    main_block: str = pydantic.Field(
        None, description="Study main block name")

    indicators: typing.List[STOIndicator] = pydantic.Field(
        [], description="List of indicators")

    simu_params: STOSimulationParam = pydantic.Field(
        None, description="Simulator parametters")

    @classmethod
    def from_yaml(cls, yaml_filename, **kwrds):

        with open(yaml_filename, 'r',
                  encoding="utf-8") as yaml_file:
            try:
                study_specs = yaml.load(yaml_file,
                                        Loader=yaml.FullLoader)
            except yaml.YAMLError as exc:
                logging.error(exc)

        obj = cls(**{**study_specs, **kwrds})

        return obj

    def get_indicator_from_id(self, id):
        for indic in self.indicators:
            if indic.id == id:
                return indic
        return None

    def to_idf(self, filename):

        idf_root = etree.Element('ar3ccp')

        observers = {}
        for indic in self.indicators:

            if not(indic.observer in observers.keys()):
                # ipdb.set_trace()
                observers[indic.observer] = \
                    etree.SubElement(idf_root, "calculation")
                observers[indic.observer].set('observer', indic.observer)

            indic_elt = \
                etree.SubElement(observers[indic.observer],
                                 "indicator")
            indic_elt.set('name', indic.id)
            indic_elt.set('type', indic.measure)
            indic_elt.set('value', indic.value)

            for stat in indic.stats:
                # stat_elt can have attribute for more complex stat (ex: distribution)
                stat_elt = \
                    etree.SubElement(indic_elt, stat)

        idf_tree = etree.ElementTree(idf_root)

        # Header required ? # <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        idf_tree.write(filename,
                       pretty_print=True,
                       xml_declaration=True,
                       encoding="utf-8")

    def to_mdf(self, filename, result_filename=None):

        if not(result_filename is None):
            self.simu_params.result_filename = result_filename

        mdf_root = etree.Element('ar3ccp')

        simu_elt = etree.SubElement(mdf_root, "simulation")
        simu_elt.set('seed', str(self.simu_params.seed))
        simu_elt.set('number-of-runs', str(self.simu_params.nb_runs))
        simu_elt.set('results-csv', str(self.simu_params.result_filename))

        mission_time = self.simu_params.schedule_to

        schedule_elt = etree.SubElement(simu_elt, "schedule")
        schedule_elt.set('mission-time', str(mission_time))

        range_elt = etree.SubElement(schedule_elt, "range")
        range_elt.set('step', str(self.simu_params.schedule_step))
        range_elt.set('from', str(self.simu_params.schedule_from))
        range_elt.set('to', str(self.simu_params.schedule_to))

        mdf_tree = etree.ElementTree(mdf_root)

        # Header required ?
        # <?xml version="1.0" ?>
        # <!DOCTYPE ar3ccp>
        mdf_tree.write(filename,
                       pretty_print=True,
                       xml_declaration=True,
                       encoding="utf-8")

    def get_stosim_config(self, logging=None):
        local_config_filename = AR3SIMU_LOCAL_CONFIG_FILENAME
        local_config_file = pathlib.Path(local_config_filename)

        if not(local_config_file.is_file()):
            ar3simu_bin_dir = \
                find_directory(of_file="gtsstocmp.sh",
                               root=str(pathlib.Path.home()))

            if not(ar3simu_bin_dir is None):
                if not(logging is None):
                    logging.info(
                        f"AR3 simulator binary found at {ar3simu_bin_dir}")
                    logging.info(
                        f"Configuration saved in file {local_config_filename}")

                with open(local_config_filename, 'w', encoding="utf-8") \
                        as yaml_file:
                    try:
                        ar3_config = yaml.dump(
                            {"ar3bin_folder": ar3simu_bin_dir},
                            yaml_file)

                    except yaml.YAMLError as exc:
                        print(exc)
                        logging.error(exc)
            else:
                if not(logging is None):
                    logging.error(
                        f"Configuration file {local_config_filename} not found, "
                        f"please create it specifying the ar3config_folder attribute")

                sys.exit(1)

        with open(AR3SIMU_LOCAL_CONFIG_FILENAME, 'r', encoding="utf-8") as yaml_file:
            try:
                stosim_local_config = yaml.load(yaml_file,
                                                Loader=yaml.FullLoader)

            except yaml.YAMLError as exc:
                if not(logging is None):
                    logging.error(exc)

        return stosim_local_config

    def run_simu(self, path=".", logging=None):

        stosim_local_config = self.get_stosim_config(logging=logging)

        study_alt_filename = os.path.join(
            path, f"{self.main_block}.alt")

        study_idf_filename = os.path.join(
            path, f"{self.main_block}.idf")

        study_mdf_filename = os.path.join(
            path, f"{self.main_block}.mdf")

        study_result_filename = os.path.join(
            path, f"{self.main_block}.csv")

        self.simu_params.result_filename = study_result_filename
        self.to_idf(study_idf_filename)
        self.to_mdf(study_mdf_filename)

        # study_alt_filename = app_bknd.blocks[app_bknd.study.main_block]\
        #                              .filename\
        #                              .replace(app_bknd.project_folder, "")\
        #                              .strip(os.path.sep)

        args = ['ar3simu',
                '-v',
                '-p',
                '-a', stosim_local_config.get("ar3bin_folder", "."),
                '-s', self.main_block,
                '-l', study_alt_filename,
                '-i', study_idf_filename,
                '-m', study_mdf_filename,
                #            "-o", csvFilePath,
                "-r"]

        logging.info(" ".join(args))
        currentProcess = subprocess.Popen(args, cwd=".",
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)

        returnCode = currentProcess.poll()

        while returnCode is None:
            returnCode = currentProcess.poll()
            print(currentProcess.stdout.readline())
            out = currentProcess.stdout.readline().decode("utf-8")
            sys.stdout.write(out)

        returnCode = currentProcess.poll()

        study_res = None
        if returnCode == 0:
            study_res = \
                STOStudyResults.from_result_csv(
                    study_result_filename)

            for indic in self.indicators:
                indic.data = study_res.indicators[indic.id].data.copy()
            # out.write(app_bknd.study_res)
            logging.info("Simulation completed")

        else:
            logging.info("Simulation failed")

        return study_res
