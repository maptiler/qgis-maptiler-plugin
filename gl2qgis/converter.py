# -*- coding: utf-8 -*-
"""
/***************************************************************************
 gl2qgis library

 Helps parse a GL style for vector tiles implementation in QGIS.
                              -------------------
        begin                : 2020-05-20
        copyright            : (C) 2020 by MapTiler AG.
        author               : MapTiler Team
 ***************************************************************************/
"""

import json
import requests
import io
import os

from .gl2qgis import parse_layers, parse_background
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsMapBoxGlStyleConversionContext
from .. import utils


def get_sources_dict_from_style_json(style_json_data: dict) -> dict:
    # Get order of sources
    # TODO solve case when sources order is mixed like this:
    # Layer 1: Source 1
    # Layer 2: Source 2
    # Layer 3: Source 1
    layers = style_json_data.get("layers")
    source_order = []
    for layer in layers:
        if "source" not in layer:
            continue
        layer_source = layer.get("source")
        if layer_source not in source_order:
            source_order.append(layer.get("source"))
    source_order.reverse()

    layer_sources = style_json_data.get("sources")
    source_zxy_dict = {}
    for source_id, source_data in layer_sources.items():
        # For sources that are not used in layers
        if source_id not in source_order:
            continue
        layer_zxy_url = ""
        min_zoom = None
        max_zoom = None
        tile_json_url = None
        if "url" in source_data:
            tile_json_url = source_data.get("url")
        if tile_json_url:
            tile_json_data = utils.qgis_request_json(tile_json_url)
            if "tiles" in tile_json_data:
                layer_zxy_url = tile_json_data.get("tiles")[0]
            if "minzoom" in tile_json_data:
                min_zoom = tile_json_data.get("minzoom")
            if "maxzoom" in tile_json_data:
                max_zoom = tile_json_data.get("maxzoom")
            if "name" in tile_json_data:
                if not tile_json_data.get("name") or tile_json_data.get("name").isspace():
                    source_name = source_id
                else:
                    source_name = tile_json_data.get("name")
            else:
                source_name = source_id
        # style.json can have no tiles.json
        else:
            if source_data.get("tiles") is None:
                continue
            layer_zxy_url = source_data.get("tiles")[0]
            source_name = source_id

        source_type = source_data.get("type")
        source_zxy_dict[source_id] = {
            "name": source_name, "zxy_url": layer_zxy_url,
            "type": source_type, "order": source_order.index(source_id),
            "maxzoom": max_zoom, "minzoom": min_zoom
        }

    return source_zxy_dict


def get_sources_dict_from_terrain_group(group_sources: list) -> dict:
    source_zxy_dict = {}
    for tile_json_url in group_sources:
        layer_zxy_url = ""
        min_zoom = None
        max_zoom = None
        attribution = None

        tile_json_data = utils.qgis_request_json(tile_json_url)
        if "tiles" in tile_json_data:
            layer_zxy_url = tile_json_data.get("tiles")[0]
        if "minzoom" in tile_json_data:
            min_zoom = tile_json_data.get("minzoom")
        if "maxzoom" in tile_json_data:
            max_zoom = tile_json_data.get("maxzoom")
        if "attribution" in tile_json_data:
            attribution = tile_json_data.get("attribution")
        if "name" in tile_json_data:
            source_name = tile_json_data.get("name")

        source_zxy_dict[source_name] = {
            "name": source_name, "zxy_url": layer_zxy_url,
            "type": 'raster-dem', "attribution": attribution,
            "maxzoom": max_zoom, "minzoom": min_zoom
        }

    return source_zxy_dict


def get_style_json(style_json_url: str) -> dict:
    url_endpoint = style_json_url.split("?")[0]
    if url_endpoint.endswith(".json"):
        style_json_data = utils.qgis_request_json(style_json_url)
        return style_json_data
    elif url_endpoint.endswith(".pbf"):
        print(f"Url to tiles, not to style supplied: {style_json_url}")
        return None
    else:
        raise Exception(f"Invalid url: {style_json_url}")


def convert(source_name: str, style_json_data: dict, context: QgsMapBoxGlStyleConversionContext):
    renderer, labeling, warnings = parse_layers(source_name, style_json_data, context)
    return renderer, labeling, warnings


def get_bg_renderer(style_json_data: dict):
    layers = style_json_data.get("layers")
    renderer = None
    for layer in layers:
        if layer["id"] == "background":
            renderer = parse_background(layer)
    return renderer


def get_source_layers_by(source_name: str, style_json_data: dict):
    layers = style_json_data.get("layers")
    source_layers = []
    for layer in layers:
        if "source" not in layer or layer["source"] != source_name:
            continue
        source_layers.append(layer)
    return source_layers


def get_raster_renderer_resampler(renderer, layer_json: dict):
    paint = layer_json.get("paint")
    if paint is None:
        return None, None

    #not fully converted:only opacity, resampling
    gl_style = {
        "brightness_max": paint.get("raster-brightness-max"),
        "brightness_min": paint.get("raster-brightness-min"),
        "contrast": paint.get("raster-contrast"),
        "fade_duration": paint.get("raster-fade-duration"),
        "hue_rotate": paint.get("raster-hue-rotate"),
        "opacity": paint.get("raster-opacity"),
        "resampling": paint.get("raster-resampling"),
        "saturation": paint.get("raster-saturation")
    }

    styled_renderer = renderer.clone()
    styled_resampler = "bilinear"  # as default
    for key, value in gl_style.items():
        if value is None:
            continue

        if key == "opacity":
            parsed_opacity = 1.0
            if not isinstance(value, (str, float, int)):
                
                if isinstance(value, (dict)):
                    #e.g. {'stops': [[1, 0.2], [13, 0.1], [16, 0]]}
                    stops = value.get("stops")
                    minzoom_opacity = stops[0][1]
                    maxzoom_opacity = stops[-1][1]
                    parsed_opacity = (minzoom_opacity + maxzoom_opacity) / 2
                else:
                    #list
                    parsed_opacity = 1.0
                    print(f"Could not parse raster opacity {value}, setting 1.0.")
            else:
                parsed_opacity = float(value)
            styled_renderer.setOpacity(parsed_opacity)

        if key == "resampling":
            styled_resampler = value

    return styled_renderer, styled_resampler


def write_sprite_imgs_from_style_json(style_json_data: dict, output_path: str):
    sprite_url = style_json_data.get("sprite")
    if sprite_url is None:
        return {}
    try:
        from PIL import Image
        sprite_json_dict = json.loads(requests.get(sprite_url + '.json').text)
        sprite_img = Image.open(io.BytesIO(requests.get(sprite_url + '.png').content))
        sprite_imgs_dict = {}

        for key, value in sprite_json_dict.items():
            left = int(value["x"])
            top = int(value["y"])
            right = left + int(value["width"])
            bottom = top + int(value["height"])
            cropped = sprite_img.crop((left, top, right, bottom))
            sprite_imgs_dict[key] = cropped

        for key, value in sprite_imgs_dict.items():
            value.save(os.path.join(output_path, key + ".png"))
    except ImportError:
        import_error_message = "You do not have PIL/Pillow library installed on your system. "\
                "Sprites will not be supported.\n"\
                "MacOS users: To install Pillow library, run following code in terminal:\n"\
                "/Applications/QGIS.app/Contents/MacOS/bin/pip3 install pillow -U"
        QMessageBox.warning(None, 'Missing PIL/Pillow library', import_error_message)
