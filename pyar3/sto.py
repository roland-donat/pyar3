import pandas as pd
import typing
import pydantic
import pkg_resources
import yaml
from lxml import etree

import logging

installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: 401

PandasDataFrame = typing.TypeVar('pd.core.dataframe')


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


class SimIndicator(pydantic.BaseModel):
    name: str = pydantic.Field(None, description="Indicator name")


class STOIndicator(SimIndicator):
    observer: str = pydantic.Field(None, description="AR3 observer name")
    type: str = pydantic.Field(None, description="Indicator type")
    measure: str = pydantic.Field(None, description="Measure")
    value: str = pydantic.Field(
        None, description="Indicator value to monitor (for categorical indicator)")
    stats: list = pydantic.Field([], description="Stats to be computed")
    data: PandasDataFrame = pydantic.Field(
        None, description="Indicator estimates")

    @pydantic.root_validator()
    def cls_validator(cls, obj):
        if obj.get('name') is None:
            obj['name'] = f"{obj.get('observer', '')}__{obj.get('measure', '')}"

        if obj.get('type') == "Boolean":
            if not(obj.get('value') in ["true", "false"]):
                obj['value'] = "true"

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

            indic_name = line_split[0].strip()
            indics_dict[indic_name] = \
                STOIndicator(name=indic_name,
                             observer=line_split[1].strip())

        indic_name = None
        indic_data_lines = indic_def_lines[start:]
        for i, line in enumerate(indic_data_lines):

            line_split = line.strip().split("\t")

            if line_split[0] == "Indicator":
                indic_name = line_split[1]
                indics_dict[indic_name].data = []

            elif is_float(line_split[0]) and not(indic_name is None):

                data_cur = dict(
                    date=float(line_split[0]),
                    sample_size=int(line_split[1]),
                    mean=float(line_split[2])
                    if len(line_split) >= 3 else float("NaN"),
                    std=float(line_split[3])
                    if len(line_split) >= 4 else float("NaN")
                )

                indics_dict[indic_name].data.append(data_cur)

            # indics_dict[indic_name]
        for indic_name in indics_dict:
            indics_dict[indic_name].data = \
                pd.DataFrame(indics_dict[indic_name].data)

        return indics_dict

    def to_excel(self, filename):

        writer = pd.ExcelWriter(filename, engine='xlsxwriter')

        for indic_name, indic in self.indicators.items():
            indic.data.to_excel(writer,
                                sheet_name=indic_name,
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

    def to_idf(self, filename):

        idf_root = etree.Element('ar3ccp')

        observers = {}
        print(self)
        for indic in self.indicators:

            if not(indic.observer in observers.keys()):
                # ipdb.set_trace()
                observers[indic.observer] = \
                    etree.SubElement(idf_root, "calculation")
                observers[indic.observer].set('observer', indic.observer)

            indic_elt = \
                etree.SubElement(observers[indic.observer],
                                 "indicator")
            indic_elt.set('name', indic.name)
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
