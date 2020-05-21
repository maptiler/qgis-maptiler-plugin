import sys
sys.path.append("/home/adam/dev/qgis_plugin/qgis-maptiler-plugin/mapboxGL2qgis")
import converter
import json


def convert():
    json_path = "/home/adam/dev/qgis_plugin/qgis-maptiler-plugin/mapboxGL2qgis/data/klokantech_basic.json"
    with open(json_path) as json_file:
        layers = converter.generate_styles(json_file.read())
    renderer, labeling = converter.write_styles(layers=layers)
    print("Done!")
    print(renderer, labeling)
    # create_icons(style=style_json, output_directory=output_directory)
    return renderer, labeling


if __name__ in ["__main__", "__console__"]:
    convert()
