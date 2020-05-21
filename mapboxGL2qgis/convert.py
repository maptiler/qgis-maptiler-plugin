import converter
import json


def convert():
    json_path = "/home/adam/dev/qgis_plugin/qgis-maptiler-plugin/mapboxGL2qgis/data/klokantech_basic_short.json"
    with open(json_path) as json_file:
        layers = converter.generate_styles(json_file.read())

    with open("/home/adam/dev/qgis_plugin/qgis-maptiler-plugin/mapboxGL2qgis/data/basic_dumped_tmp.json", 'w') as fp:
        json.dump(layers, fp)
    renderer, labeling = converter.write_styles(layers=layers)
    # create_icons(style=style_json, output_directory=output_directory)


if __name__ == "__main__":
    convert()
