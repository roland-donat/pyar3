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
import colored

import logging

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: 401

PandasDataFrame = typing.TypeVar('pd.core.dataframe')

AR3SIMU_LOCAL_CONFIG_FILENAME = os.path.join(str(pathlib.Path.home()),
                                             ".ar3simu.conf")
# Utility functions
# -----------------


def find_directory(dirname=None, of_file=None, root='.', smart_search=True):
    dir_list = []
    for path, dirs, files in os.walk(root):
        if not(dirname is None) and (dirname in dirs):
            dir_list.append(os.path.join(path, dirname))
            break
        elif not(of_file is None) and (of_file in files):
            dir_list.append(path)
            break

    # ipdb.set_trace()
    if (len(dir_list) == 0) or not(smart_search):
        return dir_list

    path_smart = str(pathlib.Path(dir_list[0]).parent)

    for path, dirs, files in os.walk(path_smart):
        if not(dirname is None) and (dirname in dirs):
            dir_list.append(os.path.join(path, dirname))
        elif not(of_file is None) and (of_file in files):
            dir_list.append(path)

    return set(dir_list)


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

    def has_tag(self, tag):
        return any([tag == t for t in self.tags])

    def get_tag_value(self, tag_name, defaut=None):
        if tag_name[-1] != ":":
            tag_name += ":"

        tag_sel = [t for t in self.tags if t.startswith(tag_name)]
        if len(tag_sel) == 0:
            return None
        else:
            return tag_sel[0].replace(tag_name, "")


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
            obj['value'] = 'non applicable'

        return obj


class STOMetaData(pydantic.BaseModel):
    main_block: str = pydantic.Field(
        None, description="Name of model main block")
    source_file: str = pydantic.Field(None, description="Source file path")
    tool_version: str = pydantic.Field(None, description="Simulator version")
    compiler_version: str = pydantic.Field(
        None, description="AR3 compiler version")

    @classmethod
    def from_raw_lines(cls, raw_lines, sep="\t"):

        cls_specs = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split(sep)
            key = line_split[0].strip()
            if key == "Meta-Data":
                start = i + 1
                break

        for i, line in enumerate(raw_lines[start:]):

            line_split = line.split(sep)

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
    schedule_from: float = pydantic.Field(None,
                                          description="Simulation schedule origin")
    schedule_to: float = pydantic.Field(...,
                                        description="Simulation schedule end")
    schedule_step: float = pydantic.Field(None,
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
    def from_raw_lines(cls, raw_lines, sep="\t"):

        cls_specs = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split(sep)
            key = line_split[0].strip()
            if key == "Mission":
                start = i + 1
                break

        indic_def_lines = raw_lines[start:]
        for i, line in enumerate(indic_def_lines):

            line_split = line.split(sep)

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
                event_fire_stats_str = indic_def_lines[i+2].split(sep)

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

    @staticmethod
    def get_simu_csv_result_sep(raw_lines):
        if ";" in raw_lines[1]:
            return ";"
        else:
            return "\t"

    @classmethod
    def from_result_csv(cls, filename, **kwrds):

        with open(filename, 'r',
                  encoding="utf-8") as file:

            file_lines = file.readlines()

        simu_csv_sep = cls.get_simu_csv_result_sep(file_lines)

        obj = cls.from_raw_lines(file_lines, sep=simu_csv_sep)
        # obj = cls(**{**study_specs, **kwrds})

        # obj.load_data()
        # obj.build_models_perf()

        return obj

    @classmethod
    def from_raw_lines(cls, raw_lines, sep="\t"):

        cls_specs = {}

        cls_specs["meta_data"] = STOMetaData.from_raw_lines(raw_lines,
                                                            sep=sep)
        cls_specs["mission"] = STOMissionResult.from_raw_lines(raw_lines,
                                                               sep=sep)
        cls_specs["indicators"] = cls.indicators_from_raw_lines(raw_lines,
                                                                sep=sep)

        # Update indicator block information
        for indic_id, indic in cls_specs["indicators"].items():
            if not(cls_specs["meta_data"].main_block is None):
                indic.block = cls_specs["meta_data"].main_block

        obj = cls(**cls_specs)

        return obj

    @classmethod
    def indicators_from_raw_lines(cls, raw_lines, sep="\t"):

        indics_dict = {}

        start = len(raw_lines)
        for i, line in enumerate(raw_lines):
            line_split = line.split(sep)
            key = line_split[0].strip()
            if key == "Indicators":
                start = i + 2
                break

        indic_def_lines = raw_lines[start:]
        for i, line in enumerate(indic_def_lines):

            line_split = line.split(sep)

            if len(line_split) <= 1:
                start = i + 1
                break

            indic_id = line_split[0].strip()
            observer = line_split[1].strip()
            # TODO: TO BE IMPROVED BUT NEED MORE TESTS
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

            line_split = line.strip().split(sep)

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

        if self.simu_params.schedule_step:
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

    def get_gtsstocmp_version(self, gtsstocmp_path, logging=None):

        cmd_args = [os.path.join(gtsstocmp_path, 'gtsstocmp'),
                    '--version']

        currentProcess = subprocess.Popen(cmd_args,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)

        while currentProcess.poll() is None:
            pass

        returnCode = currentProcess.poll()

        version = \
            currentProcess.communicate()[0].decode("utf-8")\
                                           .split()[1] \
            if returnCode == 0 \
            else None

        return version

    def get_stosim_config(self,
                          update_bin_path=False,
                          bin_path_search=str(pathlib.Path.home()),
                          logging=None):
        local_config_filename = AR3SIMU_LOCAL_CONFIG_FILENAME
        local_config_file = pathlib.Path(local_config_filename)

        # ipdb.set_trace()

        if not(local_config_file.is_file()) or update_bin_path:
            ar3simu_bin_dir_list = \
                find_directory(of_file="gtsstocmp.sh",
                               root=bin_path_search)

            ar3simu_bin_listdict = []
            if len(ar3simu_bin_dir_list) >= 1:

                for ar3simu_bin_dir in ar3simu_bin_dir_list:

                    gtssto_version = self.get_gtsstocmp_version(
                        ar3simu_bin_dir,
                        logging=logging)

                    if gtssto_version is None:
                        continue
                    else:
                        if not(logging is None):
                            logging.info(
                                f"AR3 simulator binary found at "
                                f"{ar3simu_bin_dir} [version {gtssto_version}]"
                            )
                        ar3simu_bin_listdict.append(
                            dict(path=ar3simu_bin_dir,
                                 version=gtssto_version))

            if len(ar3simu_bin_listdict) >= 1:

                with open(local_config_filename, 'w', encoding="utf-8") \
                        as yaml_file:
                    try:
                        yaml.dump(
                            {"ar3bin_folders": ar3simu_bin_listdict},
                            yaml_file)
                        logging.info(
                            f"Configuration saved in file {local_config_filename}")

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

    def run_simu(self, path=".",
                 gtssto_version=None,
                 update_bin_path=False,
                 bin_path_search=None,
                 logging=None):

        if bin_path_search is None:
            bin_path_search = str(pathlib.Path.home())

        stosim_local_config = \
            self.get_stosim_config(update_bin_path=update_bin_path,
                                   bin_path_search=bin_path_search,
                                   logging=logging)

        ar3bin_folder_list = stosim_local_config.get("ar3bin_folders", [])

        ar3bin_version_path_dict = \
            {val["version"]: val["path"]
             for val in ar3bin_folder_list}
        if gtssto_version is None:
            # ipdb.set_trace()
            ar3bin_path = list(ar3bin_version_path_dict.values())[-1]
            gtssto_version = \
                self.get_gtsstocmp_version(
                    ar3bin_path,
                    logging=logging)
        else:
            ar3bin_path = ar3bin_version_path_dict.get(gtssto_version)
            if ar3bin_path is None:
                error_msg = colored.stylize(
                    f"Simulator version {gtssto_version} not found",
                    colored.fg("red") + colored.attr("bold"))
                raise ValueError(error_msg)

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

        log_msg = colored.stylize(
            f"Start simulation process [version {gtssto_version}]",
            colored.fg("blue") + colored.attr("bold"))
        logging.info(log_msg)

        args = ['ar3simu',
                '-v',
                '-p',
                '-a', ar3bin_path,
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
            log_msg = colored.stylize(
                "Simulation completed",
                colored.fg("green") + colored.attr("bold"))
            logging.info(log_msg)

        else:
            log_msg = colored.stylize(
                "Simulation failed",
                colored.fg("red") + colored.attr("bold"))
            logging.info(log_msg)

        return study_res
