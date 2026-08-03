import configparser
from collections import OrderedDict
import json
from importlib import resources

from src.constant import DOW2_MATERIALS

RESOURCE_ROOT = resources.files("src.resources")
DEFAULT_PATTERN_RESOURCE = RESOURCE_ROOT.joinpath("default_pattern.ini")
ARMY_PATTERN_PATH = RESOURCE_ROOT.joinpath("army_pattern.json")

config = configparser.ConfigParser()
config.read_string(DEFAULT_PATTERN_RESOURCE.read_text(encoding="utf-8"))
color_key = [
    "primary_colour_name",
    "secondary_colour_name",
    "tint_colour_name",
    "extra_colour_name",
]

army_color_pattern = {}


def rgb_to_hex(rgb):
    return "#" + "%02x%02x%02x" % rgb


def get_pattern_dict():
    default_pattern_dict = {}
    for army_name, pattern in config.items():
        team_color = []
        if army_name == "DEFAULT":
            continue
        for key in color_key:
            color_name = pattern.get(key)
            team_color.append(
                DOW2_MATERIALS.get(color_name).get("team_colour")
            )
        default_pattern_dict[army_name] = team_color
    return default_pattern_dict


def dump_default_pattern():
    default_pattern_dict = get_pattern_dict()
    for k, v in default_pattern_dict.items():
        default_pattern_dict[k] = {
            key: rgb_to_hex(value) for (key, value) in zip(color_key, v)
        }

    with ARMY_PATTERN_PATH.open("w", encoding="utf-8") as fp:
        json.dump(default_pattern_dict, fp, indent=2, ensure_ascii=False)


def save(name: str, colors: list):
    # TODO: allow pattern overwrite
    if army_color_pattern.get(str) is not None:
        raise ValueError
    pattern_dict = {k: v for (k, v) in zip(color_key, colors)}
    army_color_pattern[name] = pattern_dict
    with ARMY_PATTERN_PATH.open("w", encoding="utf-8") as fp:
        json.dump(army_color_pattern, fp, indent=2, ensure_ascii=False)


def delete(name: str):
    army_color_pattern.pop(name)
    with ARMY_PATTERN_PATH.open("w", encoding="utf-8") as fp:
        json.dump(army_color_pattern, fp, indent=2, ensure_ascii=False)


# TODO: check if file is empty
if not ARMY_PATTERN_PATH.is_file():
    dump_default_pattern()

with ARMY_PATTERN_PATH.open("r", encoding="utf-8") as fp:
    army_color_pattern = json.load(fp, object_pairs_hook=OrderedDict)
