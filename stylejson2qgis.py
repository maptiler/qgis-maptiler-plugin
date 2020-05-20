import json


def parse_style_json(json_fp):
    with open(json_fp) as json_file:
        json_data = json.load(json_file)

    return json_data


if __name__ == "__console__":
    parse_style_json("/home/adam/dev/qgis_plugin/styles/Basic.json")
