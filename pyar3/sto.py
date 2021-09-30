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
    stats: list = pydantic.Field([], description="Stats to be computed")
    data: PandasDataFrame = pydantic.Field(
        None, description="Indicator estimates")


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


class STOSimulatorParam(pydantic.BaseModel):
    nb_executions: int = pydantic.Field(
        None, description="Number of simulations")
    seed: int = pydantic.Field(None, description="Simulator seed")


class STOMission(pydantic.BaseModel):
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

    mission: STOMission = pydantic.Field(
        STOMission(), description="Performance fitting parametters")

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
        cls_specs["mission"] = STOMission.from_raw_lines(raw_lines)
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

    mission: STOMission = pydantic.Field(
        None, description="Mission parameters")

    simu_params: STOSimulatorParam = pydantic.Field(
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

        for indic in self.indicators:

            if not(indic.observer in observers.keys()):
                # ipdb.set_trace()
                observers[indic.observer] = etree.SubElement(
                    idf_root, "calculation")
                observers[indic.observer].set('observer', indic.observer)

            indic_name = f"{indic.observer}_{indic.measure}"

            # observers[indic.observer].append(
        # items = ET.SubElement(data, 'items')
        # item1 = ET.SubElement(items, 'item')
        # item2 = ET.SubElement(items, 'item')
        # item1.set('name','item1')
        # item2.set('name','item2')
        # item1.text = 'item1abc'
        # item2.text = 'item2abc'

        idf_tree = etree.ElementTree(idf_root)

        # with open(filename, "w") as idf_file:
        idf_tree.write(filename, pretty_print=True)

# XML IDF examples
# <?xml version="1.0" encoding="UTF-8" standalone="no"?>
# <ar3ccp>
#    <calculation observer="obs_Source_flow_out">
#       <indicator name="src_avl_has_value" type="has-value" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#       <indicator name="src_avl_had_value" type="had-value" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#       <indicator name="src_avl_sojourn_time" type="sojourn-time" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#    </calculation>
#    <calculation observer="obs_Target_flow_in">
#       <indicator name="target_avl_has_value" type="has-value" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#       <indicator name="target_avl_had_value" type="had-value" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#       <indicator name="target_avl_sojourn_time" type="sojourn-time" value="true">
#          <mean/>
#          <standard-deviation/>
#          <confidence-range/>
#       </indicator>
#    </calculation>
# </ar3ccp>
