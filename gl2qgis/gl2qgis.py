# -*- coding: utf-8 -*-
"""
/***************************************************************************
 gl2qgis library

 Helps parse a GL style for vector tiles implementation in QGIS.
                              -------------------
        begin                : 2020-05-20
        copyright            : (C) 2020 by MapTiler AG.
        author               : MapTiler Team
        credits              : Martin Dobias and his GL style parser (MIT)
 ***************************************************************************/
"""

import json
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from qgis.core import *

PX_TO_MM = 0.26  # TODO: some good conversion ratio


def parse_color(json_color):
    """
    Parse color in one of these supported formats:
      - #fff or #ffffff
      - hsl(30, 19%, 90%) or hsla(30, 19%, 90%, 0.4)
      - rgb(10, 20, 30) or rgba(10, 20, 30, 0.5)
    """
    if json_color[0] == '#':
        return QColor(json_color)
    elif json_color.startswith('hsla'):
        x = json_color[5:-1]
        lst = x.split(',')
        assert len(lst) == 4 and lst[1].endswith('%') and lst[2].endswith('%')
        hue = int(lst[0])
        sat = float(lst[1][:-1]) / 100. * 255
        lig = float(lst[2][:-1]) / 100. * 255
        alpha = float(lst[3]) * 255
        # print(hue,sat,lig,alpha)
        return QColor.fromHsl(hue, sat, lig, alpha)
    elif json_color.startswith('hsl'):
        x = json_color[4:-1]
        lst = x.split(',')
        assert len(lst) == 3 and lst[1].endswith('%') and lst[2].endswith('%')
        hue = int(lst[0])
        sat = float(lst[1][:-1]) / 100. * 255
        lig = float(lst[2][:-1]) / 100. * 255
        # print(hue,sat,lig)
        return QColor.fromHsl(hue, sat, lig)
    elif json_color.startswith('rgba'):
        x = json_color[5:-1]
        lst = x.split(',')
        assert len(lst) == 4
        return QColor(int(lst[0]), int(lst[1]), int(lst[2]), float(lst[3]) * 255)
    elif json_color.startswith('rgb'):
        x = json_color[4:-1]
        lst = x.split(',')
        assert len(lst) == 3
        return QColor(int(lst[0]), int(lst[1]), int(lst[2]))
    else:
        raise ValueError("unknown color syntax", json_color)


def parse_line_cap(json_line_cap):
    """ Return value from Qt.PenCapStyle enum from JSON value """
    if json_line_cap == "round":
        return Qt.RoundCap
    if json_line_cap == "square":
        return Qt.SquareCap
    return Qt.FlatCap   # "butt" is default


def parse_line_join(json_line_join):
    """ Return value from Qt.PenJoinStyle enum from JSON value """
    if json_line_join == "bevel":
        return Qt.BevelJoin
    if json_line_join == "round":
        return Qt.RoundJoin
    return Qt.MiterJoin  # "miter" is default


def parse_key(json_key):
    if json_key == '$type':
        return "_geom_type"
    return '"{}"'.format(json_key)  # TODO: better escaping


def parse_value(json_value):
    if isinstance(json_value, list):
        return parse_expression(json_value)
    elif isinstance(json_value, str):
        return "'{}'".format(json_value)  # TODO: better escaping
    elif isinstance(json_value, int):
        return str(json_value)
    else:
        print(type(json_value), isinstance(json_value, list), json_value)
        return "?"


def parse_expression(json_expr):
    """ Parses expression into QGIS expression string """
    op = json_expr[0]
    is_literal_value = isinstance(json_expr[-1], (int, float))
    if op == 'all':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "({})".format(") AND (".join(lst))
    elif op == 'any':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "({})".format(") OR (".join(lst))
    elif op == 'none':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "NOT ({})".format(") AND NOT (".join(lst))
    elif op in ("==", "!=", ">=", ">", "<=", "<"):
        # use IS and NOT IS instead of = and != because they can deal with NULL values
        if op == "==":
            if is_literal_value:
                op = "="
            else:
                op = "IS"
        elif op == "!=":
            if is_literal_value:
                op = "!="
            else:
                op = "NOT IS"
        return "{} {} {}".format(parse_key(json_expr[1]), op, parse_value(json_expr[2]))
    elif op == 'has':
        return parse_key(json_expr[1]) + " IS NOT NULL"
    elif op == '!has':
        return parse_key(json_expr[1]) + " IS NULL"
    elif op == 'in' or op == '!in':
        key = parse_key(json_expr[1])
        lst = [parse_value(v) for v in json_expr[2:]]
        if op == 'in':
            return "{} IN ({})".format(key, ", ".join(lst))
        else:  # not in
            return "({} IS NULL OR {} NOT IN ({}))".format(key, key, ", ".join(lst))

    raise ValueError(json_expr)


def parse_paint(json_paint):
    # TODO implement!
    return Qt.white


def parse_opacity(json_opacity):
    # TODO fix parsing opacity
    base = json_opacity['base'] if 'base' in json_opacity else 1
    stops = json_opacity['stops']
    opacity = float((stops[0][1] + stops[1][1]) / 2)

    return opacity


def parse_fill_layer(json_layer):
    try:
        json_paint = json_layer['paint']
    except KeyError as e:
        print(
            f'Style layer {json_layer["id"]} has not paint property, skipping...')
        return
    dd_properties = {}
    # Fill color
    if 'fill-color' not in json_paint:
        print("skipping fill without fill-color", json_paint)
        return
    else:
        json_fill_color = json_paint['fill-color']
        if not isinstance(json_fill_color, str):
            # TODO implement color of type dict
            fill_color = parse_paint(json_fill_color)
            fill_color = Qt.white
        else:
            fill_color = parse_color(json_fill_color)

    # Fill outline color
    if 'fill-outline-color' not in json_paint:
        fill_outline_color = fill_color
    else:
        json_fill_outline_color = json_paint['fill-outline-color']
        if isinstance(json_fill_outline_color, str):
            fill_outline_color = parse_color(json_fill_outline_color)
        else:
            fill_outline_color = parse_paint(json_fill_outline_color)
            fill_outline_color = Qt.white

    # Fill opacity
    if 'fill-opacity' not in json_paint:
        fill_opacity = 1.0
    else:
        json_fill_opacity = json_paint['fill-opacity']
        if isinstance(json_fill_opacity, (float, int)):
            fill_opacity = float(json_fill_opacity)
        elif isinstance(json_fill_opacity, dict):
            fill_opacity = None
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_opacity_by_zoom(json_fill_opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = parse_interpolate_opacity_by_zoom(json_fill_opacity)
        else:
            print(f"Could not parse opacity: {json_fill_opacity}")

    # TODO: fill-translate

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
    fill_symbol = sym.symbolLayer(0)
    fill_symbol.setColor(fill_color)
    fill_symbol.setStrokeColor(fill_outline_color)
    for dd_key, dd_expression in dd_properties.items():
        fill_symbol.setDataDefinedProperty(dd_key, QgsProperty.fromExpression(dd_expression))
    if fill_opacity:
        sym.setOpacity(fill_opacity)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.PolygonGeometry)
    st.setSymbol(sym)
    return st


def parse_interpolate_by_zoom(json_obj, multiplier=1):
    base = json_obj['base'] if 'base' in json_obj else 1
    stops = json_obj['stops']  # TODO: use intermediate stops
    if base == 1:
        scale_expr = "scale_linear(@zoom_level, {}, {}, {}, {})".format(
            stops[0][0], stops[-1][0], stops[0][1], stops[-1][1])
    else:
        scale_expr = "scale_exp(@zoom_level, {}, {}, {}, {}, {})".format(
            stops[0][0], stops[-1][0], stops[0][1], stops[-1][1], base)
    return scale_expr + " * {}".format(multiplier)


def parse_interpolate_opacity_by_zoom(json_obj):
    base = json_obj['base'] if 'base' in json_obj else 1
    stops = json_obj['stops']  # TODO: use intermediate stops
    if base == 1:
        scale_expr = f"set_color_part(@symbol_color, 'alpha', scale_linear(@zoom_level, " \
                     f"{stops[0][0]}, {stops[-1][0]}, {stops[0][1]*255}, {stops[-1][1]*255}))"
    else:
        scale_expr = f"set_color_part(@symbol_color, 'alpha', scale_exp(@zoom_level, " \
                     f"{stops[0][0]}, {stops[-1][0]}, {stops[0][1]*255}, {stops[-1][1]*255}, {base}))"
    return scale_expr


def parse_line_layer(json_layer):
    try:
        json_paint = json_layer['paint']
    except KeyError as e:
        print(
            f'Style layer {json_layer["id"]} has not paint property, skipping...')
        return

    if 'line-color' not in json_paint:
        print("skipping line without line-color", json_paint)
        return

    dd_properties = {}

    json_line_color = json_paint['line-color']
    if not isinstance(json_line_color, str):
        print("skipping non-string color", json_line_color)
        return

    line_color = parse_color(json_line_color)

    line_width = 0
    if 'line-width' in json_paint:
        json_line_width = json_paint['line-width']
        if isinstance(json_line_width, (float, int)):
            line_width = float(json_line_width)
        elif isinstance(json_line_width, dict):
            dd_properties[QgsSymbolLayer.PropertyStrokeWidth] = parse_interpolate_by_zoom(
                json_line_width, PX_TO_MM)
        else:
            print("skipping non-float line-width", json_line_width)

    line_opacity = 1
    if 'line-opacity' in json_paint:
        json_line_opacity = json_paint['line-opacity']
        if isinstance(json_line_opacity, (float, int)):
            line_opacity = float(json_line_opacity)
        elif isinstance(json_line_opacity, dict):
            fill_opacity = None
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_opacity_by_zoom(json_line_opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = parse_interpolate_opacity_by_zoom(json_line_opacity)
        else:
            print("skipping non-float line-opacity",
                  json_line_opacity, type(json_line_opacity))

    dash_vector = None
    if 'line-dasharray' in json_paint:
        json_dasharray = json_paint['line-dasharray']
        if isinstance(json_dasharray, list):
            dash_vector = list(map(float, json_dasharray))
        if isinstance(json_dasharray, dict):
            print("skipping dasharray in dict", json_dasharray)

    pen_cap_style = Qt.FlatCap
    pen_join_style = Qt.MiterJoin
    if 'layout' in json_layer:
        json_layout = json_layer['layout']
        if 'line-cap' in json_layout:
            pen_cap_style = parse_line_cap(json_layout['line-cap'])
        if 'line-join' in json_layout:
            pen_join_style = parse_line_join(json_layout['line-join'])

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
    line_symbol = sym.symbolLayer(0)
    line_symbol.setColor(line_color)
    line_symbol.setWidth(line_width * PX_TO_MM)
    line_symbol.setPenCapStyle(pen_cap_style)
    line_symbol.setPenJoinStyle(pen_join_style)
    if dash_vector is not None:
        line_symbol.setCustomDashVector(dash_vector)
        line_symbol.setUseCustomDashPattern(True)
    for dd_key, dd_expression in dd_properties.items():
        line_symbol.setDataDefinedProperty(
            dd_key, QgsProperty.fromExpression(dd_expression))
    if line_opacity:
        sym.setOpacity(line_opacity)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.LineGeometry)
    st.setSymbol(sym)
    return st


def parse_symbol_layer(json_layer):
    try:
        json_paint = json_layer['paint']
    except KeyError as e:
        print(
            f'Style layer {json_layer["id"]} has not paint property, skipping...')
        return
    try:
        json_layout = json_layer['layout']
    except KeyError as e:
        print(
            f'Style layer {json_layer["id"]} has not layout property, skipping...')
        return

    dd_properties = {}

    TEXT_SIZE_MULTIPLIER = 1  # *2 because of high-res screen?

    text_size = 16
    if 'text-size' in json_layout:
        json_text_size = json_layout['text-size']
        if isinstance(json_text_size, (float, int)):
            text_size = json_text_size
        elif isinstance(json_text_size, dict):
            dd_properties[QgsPalLayerSettings.Size] = parse_interpolate_by_zoom(
                json_text_size, TEXT_SIZE_MULTIPLIER)
        else:
            print("skipping non-float text-size", json_text_size)

    # TODO: text-font

    text_color = Qt.black
    if 'text-color' in json_paint:
        json_text_color = json_paint['text-color']
        if isinstance(json_text_color, str):
            text_color = parse_color(json_text_color)
        else:
            print("skipping non-string text-color", json_text_color)

    buffer_color = QColor(0, 0, 0, 0)
    if 'text-halo-color' in json_paint:
        json_text_halo_color = json_paint['text-halo-color']
        if isinstance(json_text_halo_color, str):
            buffer_color = parse_color(json_text_halo_color)
        else:
            print("skipping non-string text-halo-color", json_text_halo_color)

    buffer_size = 0
    if 'text-halo-width' in json_paint:
        json_text_halo_width = json_paint['text-halo-width']
        if isinstance(json_text_halo_width, (float, int)):
            buffer_size = json_text_halo_width
        else:
            print("skipping non-float text-halo-width", json_text_halo_width)

    format = QgsTextFormat()
    format.setColor(text_color)
    format.setSize(text_size * TEXT_SIZE_MULTIPLIER)
    format.setSizeUnit(QgsUnitTypes.RenderPixels)
    # format.setFont(font)

    if buffer_size > 0:
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(buffer_size * PX_TO_MM * TEXT_SIZE_MULTIPLIER)
        buffer_settings.setColor(buffer_color)
        format.setBuffer(buffer_settings)

    label_settings = QgsPalLayerSettings()
    label_settings.fieldName = '"name:latin"'  # TODO: parse field name
    label_settings.isExpression = True
    label_settings.placement = QgsPalLayerSettings.OverPoint
    label_settings.priority = min(text_size/3., 10.)
    label_settings.setFormat(format)

    if dd_properties:
        for dd_key, dd_expression in dd_properties.items():
            prop_collection = QgsPropertyCollection()
            prop_collection.setProperty(
                dd_key, QgsProperty.fromExpression(dd_expression))
        label_settings.setDataDefinedProperties(prop_collection)

    lb = QgsVectorTileBasicLabelingStyle()
    lb.setGeometryType(QgsWkbTypes.PointGeometry)
    lb.setLabelSettings(label_settings)
    return lb


def parse_layers(json_layers):
    """ Parse list of layers from JSON and return QgsVectorTileBasicRenderer + QgsVectorTileBasicLabeling in a tuple """
    renderer_styles = []
    labeling_styles = []

    for json_layer in json_layers:
        layer_type = json_layer['type']
        if layer_type == 'background':
            continue   # TODO: parse background color
        style_id = json_layer['id']
        layer_name = json_layer['source-layer']
        min_zoom = json_layer['minzoom'] if 'minzoom' in json_layer else -1
        max_zoom = json_layer['maxzoom'] if 'maxzoom' in json_layer else -1

        if 'visibility' in json_layer and json_layer['visibility'] == 'none':
            enabled = False
        else:
            enabled = True

        filter_expr = ''
        if 'filter' in json_layer:
            # TODO fix expressions
            filter_expr = parse_expression(json_layer['filter'])
            # TODO fix water styling
            if style_id == "water":
                filter_expr = "TRUE"

        st, lb = None, None
        if layer_type == 'fill':
            st = parse_fill_layer(json_layer)
        elif layer_type == 'line':
            st = parse_line_layer(json_layer)
        elif layer_type == 'symbol':
            lb = parse_symbol_layer(json_layer)
        else:
            print("skipping unknown layer type", layer_type)
            continue

        if st:
            st.setStyleName(style_id)
            st.setLayerName(layer_name)
            st.setFilterExpression(filter_expr)
            st.setMinZoomLevel(min_zoom)
            st.setMaxZoomLevel(max_zoom)
            st.setEnabled(enabled)
            renderer_styles.append(st)

        if lb:
            lb.setStyleName(style_id)
            lb.setLayerName(layer_name)
            lb.setFilterExpression(filter_expr)
            lb.setMinZoomLevel(min_zoom)
            lb.setMaxZoomLevel(max_zoom)
            lb.setEnabled(enabled)
            labeling_styles.append(lb)

    renderer = QgsVectorTileBasicRenderer()
    renderer.setStyles(renderer_styles)

    labeling = QgsVectorTileBasicLabeling()
    labeling.setStyles(labeling_styles)

    return renderer, labeling


def parse_json(json_str):
    json_data = json.loads(json_str)
    json_layers = json_data['layers']
    return parse_layers(json_layers)


def parse_background(bg_layer_data: dict):
    json_paint = bg_layer_data.get("paint")
    renderer = None
    if "background-color" in json_paint:
        json_background_color = json_paint.get("background-color")
        if not isinstance(json_background_color, str):
            # TODO implement color of type dict
            bg_color = parse_paint(json_background_color)
        else:
            bg_color = parse_color(json_background_color)
        sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
        sym.setColor(bg_color)
        sym.symbolLayer(0).setStrokeColor(QColor("transparent"))
        if "background-opacity" in json_paint:
            json_background_opacity = json_paint.get("background-opacity")
            bg_opacity = parse_opacity(json_background_opacity)
            sym.setOpacity(bg_opacity)
        renderer = QgsSingleSymbolRenderer(sym)
    return renderer
