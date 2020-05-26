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
from .gl2qgis import parse_layers, parse_background


def get_sources_dict_from_style_json(style_json_data: dict) -> dict:
    layer_sources = style_json_data.get("sources")
    source_zxy_dict = {}
    for source_name, source_data in layer_sources.items():
        tile_json_url = source_data.get("url")
        source_type = source_data.get("type")
        tile_json_data = json.loads(requests.get(tile_json_url).text)
        layer_zxy_url = tile_json_data.get("tiles")[0]
        source_zxy_dict[source_name] = {"name": source_name, "zxy_url": layer_zxy_url, "type": source_type}

    return source_zxy_dict


def get_style_json(style_json_url: str) -> dict:
    url_endpoint = style_json_url.split("?")[0]
    if url_endpoint.endswith("style.json"):
        style_json_data = json.loads(requests.get(style_json_url).text)
        return style_json_data
    elif url_endpoint.endswith(".pbf"):
        print(f"Url to tiles, not to style supplied: {style_json_url}")
        return None
    else:
        raise Exception(f"Invalid url: {style_json_url}")


def get_renderer_labeling(source_name: str, style_json_data: dict):
    layers = style_json_data.get("layers")
    source_layers = []
    for layer in layers:
        if "source" not in layer or layer["source"] != source_name:
            continue
        source_layers.append(layer)

    renderer, labeling = parse_layers(source_layers)
    return renderer, labeling


def get_bg_renderer(style_json_data: dict):
    layers = style_json_data.get("layers")
    renderer = None
    for layer in layers:
        if layer["id"] == "background":
            renderer = parse_background(layer)
    if not renderer:
        print("No background layer in style.json.")
    return renderer
