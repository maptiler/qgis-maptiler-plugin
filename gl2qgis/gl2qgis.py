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
import enum
import json
import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from qgis.core import *
from qgis.gui import *

# SCREEN SETTING
screen = QgsApplication.primaryScreen()
PX_RATIO = 1
RENDER_UNIT = QgsUnitTypes.RenderPixels


def parse_color(json_color: str):
    """
    Parse color in one of these supported formats:
      - #fff or #ffffff
      - hsl(30, 19%, 90%) or hsla(30, 19%, 90%, 0.4)
      - rgb(10, 20, 30) or rgba(10, 20, 30, 0.5)
    """
    if not isinstance(json_color, str):
        print(f"Could not parse non-string color {json_color}, skipping.")
        return QColor(0,0,0,0)
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
    if isinstance(json_key, list):
        try:
            return json_key[1]
        # e.g. len(json_key) == 1
        except IndexError:
            return json_key[0]
    
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
    if op == 'all':
        lst = [parse_value(v) for v in json_expr[1:]]
        if None in lst:
            print(f"Skipping unsupported expression {json_expr}")
            return
        return "({})".format(") AND (".join(lst))
    elif op == 'any':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "({})".format(") OR (".join(lst))
    elif op == 'none':
        lst = [parse_value(v) for v in json_expr[1:]]
        return "NOT ({})".format(") AND NOT (".join(lst))
    elif op == '!':
        # ! inverts next expression meaning
        contra_json_expr = json_expr[1]
        contra_json_expr[0] = op + contra_json_expr[0]
        # ['!', ['has', 'level']] -> ['!has', 'level']
        return parse_key(contra_json_expr)
    elif op in ("==", "!=", ">=", ">", "<=", "<"):
        # use IS and NOT IS instead of = and != because they can deal with NULL values
        if op == "==":
            op = "IS"
        elif op == "!=":
            op = "IS NOT"
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
    elif op == 'get':
        return parse_key(json_expr[1][1])
    elif op == 'match':
        attr = json_expr[1][1]
        case_str = "CASE "
        for i in range(2, len(json_expr)-2):
            if isinstance(json_expr[i], (list, tuple)):
                attr_value = tuple(json_expr[i])
                when_str = f"WHEN ({attr} IN {attr_value}) "
            elif isinstance(json_expr[i], (str, float, int)):
                attr_value = json_expr[i]
                when_str = f"WHEN ({attr}='{attr_value}') "
            then_str= f"THEN {json_expr[i+1]}"
            case_str = f"{case_str} {when_str} {then_str}"
            i += 2
        case_str = f"{case_str} ELSE {json_expr[-1]}"
        return case_str
    else:
        print(f"Skipping {json_expr}")
        return
    raise ValueError(json_expr)


def parse_json(json_str):
    json_data = json.loads(json_str)
    json_layers = json_data['layers']
    return parse_layers(json_layers)


def parse_opacity(json_opacity: dict) -> float:
    # TODO fix parsing opacity
    base = json_opacity['base'] if 'base' in json_opacity else 1
    stops = json_opacity['stops']
    opacity = float((stops[0][1] + stops[1][1]) / 2)

    return opacity


class PropertyType(enum.Enum):
    Color = 1
    Line = 2
    Opacity = 3
    Text = 4


def parse_interpolate_list_by_zoom(json_obj: list, prop_type: PropertyType, multiplier: float = 1):
    """
    Interpolates list that starts with interpolate function.
    """
    # TODO improve method
    if json_obj[0] != "interpolate":
        return None
    if json_obj[1][0] == "linear":
        base = 1
    elif json_obj[1][0] == "exponential":
        base = json_obj[1][1]
    elif json_obj[1][0] == "cubic-bezier":
        print(f"QGIS does not support cubic-bezier interpolation, linear used instead.")
        base = 1
    else:
        print(f"Skipping not implemented interpolation method {json_obj[1][0]}")
        return None
    if json_obj[2] != ["zoom"]:
        print(f"Skipping not implemented interpolation input {json_obj[2]}")
        return None
    # Convert stops into list of lists
    list_stops_values = json_obj[3:]
    it = iter(list_stops_values)
    stops = list(zip(it, it))
    d = {"base": base, "stops": stops}
    if prop_type == PropertyType.Color:
        expr = parse_interpolate_color_by_zoom(d)
    elif prop_type == PropertyType.Line or prop_type == PropertyType.Text:
        expr = parse_interpolate_by_zoom(d, multiplier)
    elif prop_type == PropertyType.Opacity:
        expr = parse_interpolate_opacity_by_zoom(d)

    return expr


def parse_interpolate_by_zoom(json_obj, multiplier=1):
    base = json_obj['base'] if 'base' in json_obj else 1
    stops = json_obj['stops']
    if len(stops) <= 2:
        if base == 1:
            scale_expr = f"scale_linear(@zoom_level, {stops[0][0]}, {stops[-1][0]}, " \
                         f"{stops[0][1]}, {stops[-1][1]}) " \
                         f"* {multiplier}"
        else:
            scale_expr = f"{interpolate_exp(stops[0][0], stops[-1][0], stops[0][1], stops[-1][1], base)} " \
                         f"* {multiplier}"
    else:
        scale_expr = parse_stops(base, stops, multiplier)
    return scale_expr


def parse_stops(base: (int, float), stops: list, multiplier: (int, float)) -> str:
    # Bottom zoom and value
    case_str = f"CASE "
    if base == 1:
        # base = 1 -> scale_linear
        for i in range(len(stops)-1):
            # Bottom zoom and value
            bz = stops[i][0]
            bv = stops[i][1]
            if isinstance(bv, list):
                parsed_expr = parse_expression(bv)
                if not isinstance(bv, (int, float)):
                    print(f"QGIS does not support expressions in interpolation function, skipping. Expression: {bv}")
                    return
                else:
                    bv = parsed_expr
            # Top zoom and value
            tz = stops[i+1][0]
            tv = stops[i+1][1]
            if isinstance(tv, list):
                parsed_expr = parse_expression(tv)
                if not isinstance(tv, (int, float)):
                    print(f"QGIS does not support expressions in interpolation function, skipping. Expression: {tv}")
                    return
                else:
                    tv = parsed_expr
            interval_str = f"WHEN @zoom_level > {bz} AND @zoom_level <= {tz} " \
                           f"THEN scale_linear(@zoom_level, {bz}, {tz}, {bv}, {tv}) " \
                           f"* {multiplier} "
            case_str = case_str + f"{interval_str}"
    else:
        # base != 1 -> scale_exp
        for i in range(len(stops)-1):
            # Bottom zoom and value
            bz = stops[i][0]
            bv = stops[i][1]
            if isinstance(bv, list):
                parsed_expr = parse_expression(bv)
                if not isinstance(bv, (int, float)):
                    print(f"QGIS does not support expressions in interpolation function, skipping. Expression: {bv}")
                    return
                else:
                    bv = parsed_expr
            # Top zoom and value
            tz = stops[i + 1][0]
            tv = stops[i + 1][1]
            if isinstance(tv, list):
                parsed_expr = parse_expression(tv)
                if not isinstance(tv, (int, float)):
                    print(f"QGIS does not support expressions in interpolation function, skipping. Expression: {tv}")
                    return
                else:
                    tv = parsed_expr
            interval_str = f"WHEN @zoom_level > {bz} AND @zoom_level <= {tz} " \
                           f"THEN {interpolate_exp(bz, tz, bv, tv, base)} " \
                           f"* {multiplier} "
            case_str = case_str + f"{interval_str} "
    case_str = case_str + f"END"
    return case_str


def parse_interpolate_opacity_by_zoom(json_obj):
    """
    Interpolates opacity with either scale_linear() or scale_exp() (depending on base value).
    For json_obj with intermediate stops it uses parse_opacity_stops() function.
    It uses QGIS set_color_part() function to set alpha component of color.
    """
    base = json_obj['base'] if 'base' in json_obj else 1
    stops = json_obj['stops']
    if len(stops) <= 2:
        if base == 1:
            scale_expr = f"set_color_part(@symbol_color, 'alpha', scale_linear(@zoom_level, " \
                         f"{stops[0][0]}, {stops[-1][0]}, {stops[0][1]*255}, {stops[-1][1]*255}))"
        else:
            scale_expr = f"set_color_part(@symbol_color, 'alpha', " \
                         f"{interpolate_exp(stops[0][0], stops[-1][0], stops[0][1]*255, stops[-1][1]*255, base)})"
    else:
        scale_expr = parse_opacity_stops(base, stops)
    return scale_expr


def parse_opacity_stops(base: (int, float), stops: list) -> str:
    """
    Takes values from stops and uses either scale_linear() or scale_exp() functions
    to interpolate alpha component of color.
    """
    case_str = f"CASE WHEN @zoom_level < {stops[0][0]} THEN set_color_part(@symbol_color, 'alpha', {stops[0][1]*255})"
    if base == 1:
        # base = 1 -> scale_linear
        for i in range(len(stops)-1):
            interval_str = f" WHEN @zoom_level >= {stops[i][0]} AND @zoom_level < {stops[i+1][0]} " \
                           f"THEN set_color_part(@symbol_color, 'alpha', " \
                           f"scale_linear(@zoom_level, {stops[i][0]}, {stops[i+1][0]}, " \
                           f"{stops[i][1]*255}, {stops[i+1][1]*255})) "
            case_str = case_str + f"{interval_str}"
    else:
        # base != 1 -> scale_expr
        for i in range(len(stops)-1):
            interval_str = f" WHEN @zoom_level >= {stops[i][0]} AND @zoom_level < {stops[i+1][0]} " \
                           f"THEN set_color_part(@symbol_color, 'alpha', " \
                           f"{interpolate_exp(stops[i][0], stops[i+1][0], stops[i][1]*255, stops[i+1][1]*255, base)}"
            case_str = case_str + f"{interval_str} "
    case_str = case_str + f"WHEN @zoom_level >= {stops[-1][0]} " \
                          f"THEN set_color_part(@symbol_color, 'alpha', {stops[-1][1]}) END"
    return case_str


def interpolate_exp(zoom_min, zoom_max, value_min, value_max, base):
    return f"{value_min} + {value_max - value_min} * " \
           f"({base}^(@zoom_level-{zoom_min})-1)/({base}^({zoom_max}-{zoom_min})-1)"


def get_color_as_hsla_components(qcolor):
    """
    Takes QColor object and returns HSLA components in required format for QGIS color_hsla() function.
    hue: an integer value from 0 to 360,
    saturation: an integer value from 0 to 100,
    lightness: an integer value from 0 to 100,
    alpha: an integer value from 0 (completely transparent) to 255 (opaque).
    """
    hue = qcolor.hslHue()
    if hue < 0:
        hue = 0
    sat = int((qcolor.hslSaturation() / 255) * 100)
    lightness = int((qcolor.lightness() / 255) * 100)
    alpha = qcolor.alpha()
    return hue, sat, lightness, alpha


def parse_interpolate_color_by_zoom(json_obj):
    base = json_obj['base'] if 'base' in json_obj else 1
    stops = json_obj['stops']
    # Bottom color
    case_str = f"CASE "

    # Base = 1 -> scale_linear()
    if base == 1:
        for i in range(len(stops)-1):
            # Step bottom zoom
            bz = stops[i][0]
            # Step top zoom
            tz = stops[i+1][0]
            bottom_color = parse_color(stops[i][1])
            top_color = parse_color(stops[i+1][1])
            bc_hue, bc_sat, bc_light, bc_alpha = get_color_as_hsla_components(bottom_color)
            tc_hue, tc_sat, tc_light, tc_alpha = get_color_as_hsla_components(top_color)

            when_str = f"WHEN @zoom_level >= {bz} AND @zoom_level < {tz} THEN color_hsla(" \
                       f"scale_linear(@zoom_level, {bz}, {tz}, {bc_hue}, {tc_hue}), " \
                       f"scale_linear(@zoom_level, {bz}, {tz}, {bc_sat}, {tc_sat}), " \
                       f"scale_linear(@zoom_level, {bz}, {tz}, {bc_light}, {tc_light}), " \
                       f"scale_linear(@zoom_level, {bz}, {tz}, {bc_alpha}, {tc_alpha})) "
            case_str = case_str + when_str
    # Base != 1 -> scale_exp()
    else:
        for i in range(len(stops) - 1):
            # Step bottom zoom
            bz = stops[i][0]
            # Step top zoom
            tz = stops[i + 1][0]
            bottom_color = parse_color(stops[i][1])
            top_color = parse_color(stops[i + 1][1])
            bc_hue, bc_sat, bc_light, bc_alpha = get_color_as_hsla_components(bottom_color)
            tc_hue, tc_sat, tc_light, tc_alpha = get_color_as_hsla_components(top_color)

            when_str = f"WHEN @zoom_level >= {bz} AND @zoom_level < {tz} THEN color_hsla(" \
                       f"{interpolate_exp(bz, tz, bc_hue, tc_hue, base)}, " \
                       f"{interpolate_exp(bz, tz, bc_sat, tc_sat, base)}, " \
                       f"{interpolate_exp(bz, tz, bc_light, tc_light, base)}, " \
                       f"{interpolate_exp(bz, tz, bc_alpha, tc_alpha, base)}) "
            case_str = case_str + when_str
    # Top color
    tz = stops[-1][0]
    top_color = parse_color(stops[-1][1])
    tc_hue, tc_sat, tc_light, tc_alpha = get_color_as_hsla_components(top_color)
    end_string = f"WHEN @zoom_level >= {tz} THEN color_hsla({tc_hue}, {tc_sat}, {tc_light}, {tc_alpha}) " \
                 f"ELSE color_hsla({tc_hue}, {tc_sat}, {tc_light}, {tc_alpha}) END"
    case_str = case_str + end_string

    return case_str


def parse_fill_layer(json_layer, style_name):
    try:
        json_paint = json_layer['paint']
    except KeyError as e:
        print(
            f'Style layer {json_layer["id"]} has not paint property, skipping...')
        return
    dd_properties = {}

    # Fill color
    fill_color = None
    if 'fill-color' in json_paint:
        json_fill_color = json_paint['fill-color']
        if isinstance(json_fill_color, dict):
            # Use data defined property
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_color_by_zoom(json_fill_color)
        elif isinstance(json_fill_color, list):
            # Use data defined property
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_list_by_zoom(
                json_fill_color, PropertyType.Color)
        elif isinstance(json_fill_color, str):
            # Use simple string color
            fill_color = parse_color(json_fill_color)
        else:
            print(f"Skipping non-implemented color expression {json_fill_color}")

    # Fill outline color
    if 'fill-outline-color' not in json_paint:
        # Use fill_color simple string if available
        if fill_color:
            fill_outline_color = fill_color
        # Use fill color data defined property
        else:
            fill_outline_color = None
            if QgsSymbolLayer.PropertyFillColor in dd_properties:
                dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
    else:
        json_fill_outline_color = json_paint['fill-outline-color']
        if isinstance(json_fill_outline_color, str):
            fill_outline_color = parse_color(json_fill_outline_color)
        elif isinstance(json_fill_outline_color, dict):
            fill_outline_color = None
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = parse_interpolate_color_by_zoom(json_fill_outline_color)
        elif isinstance(json_fill_outline_color, list):
            fill_outline_color = None
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = parse_interpolate_list_by_zoom(
                json_fill_outline_color, PropertyType.Color)
        else:
            fill_outline_color = None
            print(f"Skipping non-implemented color expression {json_fill_outline_color}")

    # Fill opacity
    fill_opacity = None
    if 'fill-opacity' in json_paint:
        json_fill_opacity = json_paint['fill-opacity']
        if isinstance(json_fill_opacity, (float, int)):
            fill_opacity = float(json_fill_opacity)
        elif isinstance(json_fill_opacity, (dict, list)) and QgsSymbolLayer.PropertyFillColor in dd_properties:
            print(f"Could not set opacity of layer {json_layer['id']}, "
                  f"opacity already defined in: {json_fill_color}")
        elif isinstance(json_fill_opacity, dict):
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_opacity_by_zoom(json_fill_opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = parse_interpolate_opacity_by_zoom(json_fill_opacity)
        elif isinstance(json_fill_opacity, list):
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_list_by_zoom(
                json_fill_opacity, PropertyType.Opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
        else:
            print(f"Could not parse opacity: {json_fill_opacity}")

    # TODO: fill-translate

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
    fill_symbol = sym.symbolLayer(0)
    # set render units
    sym.setOutputUnit(RENDER_UNIT)
    fill_symbol.setOutputUnit(RENDER_UNIT)

    #get fill-pattern to set sprite
    #sprite imgs will already have been downloaded in converter.py
    fill_pattern = json_paint.get("fill-pattern")

    # fill-pattern can be String or Object
    # String: {"fill-pattern": "dash-t"}
    # Object: {"fill-pattern":{"stops":[[11,"wetland8"],[12,"wetland16"]]}}

    # if Object, simpify into one sprite.
    # TODO: 
    if isinstance(fill_pattern, dict):
        pattern_stops = fill_pattern.get("stops", [None])
        fill_pattern = pattern_stops[-1][-1]
    
    #when fill-pattern exists, set and insert RasterFillSymbolLayer
    if fill_pattern:
        SPRITES_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sprites")
        raster_fill_symbol = QgsRasterFillSymbolLayer(os.path.join(SPRITES_PATH, fill_pattern + ".png"))
        sym.appendSymbolLayer(raster_fill_symbol)

    for dd_key, dd_expression in dd_properties.items():
        fill_symbol.setDataDefinedProperty(dd_key, QgsProperty.fromExpression(dd_expression))
    
    if fill_opacity:
        sym.setOpacity(fill_opacity)
    if fill_outline_color:
        fill_symbol.setStrokeColor(fill_outline_color)
    else:
        transparent_color = parse_color("rgba(0, 0, 0, 0.0)")
        fill_symbol.setStrokeColor(transparent_color)
    if fill_color:
        fill_symbol.setColor(fill_color)
    else:
        transparent_color = parse_color("rgba(0, 0, 0, 0.0)")
        fill_symbol.setColor(transparent_color)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.PolygonGeometry)
    st.setSymbol(sym)
    return st


def parse_line_layer(json_layer, style_name):
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

    line_color = None
    json_line_color = json_paint['line-color']
    if isinstance(json_line_color, dict):
        dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_color_by_zoom(json_line_color)
        dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
    elif isinstance(json_line_color, list):
        dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_list_by_zoom(
            json_line_color, PropertyType.Color)
        dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
    elif isinstance(json_line_color, str):
        line_color = parse_color(json_line_color)
    else:
        print("skipping not implemented line-color expression",
              json_line_color, type(json_line_color))

    line_width = 1
    if 'line-width' in json_paint:
        json_line_width = json_paint['line-width']
        if isinstance(json_line_width, (float, int)):
            line_width = float(json_line_width)
        elif isinstance(json_line_width, dict):
            line_width = None
            dd_properties[QgsSymbolLayer.PropertyStrokeWidth] = parse_interpolate_by_zoom(
                json_line_width, PX_RATIO)
        elif isinstance(json_line_width, list):
            line_width = None
            dd_properties[QgsSymbolLayer.PropertyStrokeWidth] = parse_interpolate_list_by_zoom(
                json_line_width, PropertyType.Line, PX_RATIO)
        else:
            print("skipping not implemented line-width expression",
                  json_line_width, type(json_line_width))


    line_opacity = 1
    if 'line-opacity' in json_paint:
        json_line_opacity = json_paint['line-opacity']
        if isinstance(json_line_opacity, (float, int)):
            line_opacity = float(json_line_opacity)
        elif isinstance(json_line_opacity, (dict, list)) and QgsSymbolLayer.PropertyFillColor in dd_properties:
            print(f"Could not set opacity of layer {json_layer['id']},"
                  f" opacity already defined in: {json_paint['line-color']}")
        elif isinstance(json_line_opacity, dict):
            fill_opacity = None
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_opacity_by_zoom(json_line_opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
        elif isinstance(json_line_opacity, list):
            fill_opacity = None
            dd_properties[QgsSymbolLayer.PropertyFillColor] = parse_interpolate_list_by_zoom(
                json_line_opacity, PropertyType.Opacity)
            dd_properties[QgsSymbolLayer.PropertyStrokeColor] = dd_properties[QgsSymbolLayer.PropertyFillColor]
        else:
            print("skipping not implemented line-opacity expression",
                  json_line_opacity, type(json_line_opacity))

    dash_vector = None
    if 'line-dasharray' in json_paint:
        json_dasharray = json_paint['line-dasharray']
        if isinstance(json_dasharray, list):
            dash_vector = [i * PX_RATIO for i in json_dasharray]
        elif isinstance(json_dasharray, dict):
            # TODO improve parsing (use PropertyCustomDash?)
            dash_vector = [i * PX_RATIO for i in json_dasharray["stops"][-1][1]]
        else:
            print(f"Skipping non implemented dash vector expression: {json_dasharray}")

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
    # set render units
    sym.setOutputUnit(RENDER_UNIT)
    line_symbol.setOutputUnit(RENDER_UNIT)

    line_symbol.setPenCapStyle(pen_cap_style)
    line_symbol.setPenJoinStyle(pen_join_style)

    for dd_key, dd_expression in dd_properties.items():
        line_symbol.setDataDefinedProperty(
            dd_key, QgsProperty.fromExpression(dd_expression))
    if dash_vector:
        line_symbol.setCustomDashVector(dash_vector)
        line_symbol.setUseCustomDashPattern(True)
        line_symbol.setStrokeColor(QColor("transparent"))
    if line_color:
        line_symbol.setColor(line_color)
    if line_width:
        line_symbol.setWidth(line_width * PX_RATIO)
    if line_opacity:
        sym.setOpacity(line_opacity)
    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.LineGeometry)
    st.setSymbol(sym)
    return st


def parse_symbol_layer(json_layer, style_name):
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

    text_size = 16
    if 'text-size' in json_layout:
        json_text_size = json_layout['text-size']
        if isinstance(json_text_size, (float, int)):
            text_size = json_text_size
        elif isinstance(json_text_size, dict):
            text_size = None
            dd_properties[QgsPalLayerSettings.Size] = parse_interpolate_by_zoom(
                json_text_size)
        elif isinstance(json_text_size, list):
            text_size = None
            dd_properties[QgsPalLayerSettings.Size] = parse_interpolate_list_by_zoom(
                json_text_size, PropertyType.Text)
        else:
            print("skipping non-float text-size", json_text_size)

    text_font = None
    if 'text-font' in json_layout:
        json_text_font = json_layout['text-font']
        if not isinstance(json_text_font, (str, list)):
            print(f"Skipping non implemented text-font expression {json_text_font}")
        else:
            if isinstance(json_text_font, str):
                font_name = json_text_font
            elif isinstance(json_text_font, list):
                font_name = json_text_font[0]

            # mapbox GL text-font property includes font style along with family,
            # we have to test to see exactly where this split occurs!
            found = False
            text_font_parts = font_name.split(' ')
            for i in range(1, len(text_font_parts)):
                candidate_font_family= ' '.join(text_font_parts[:-i])
                candidate_font_style = ' '.join(text_font_parts[-i:])
                if QgsFontUtils.fontFamilyHasStyle(candidate_font_family, candidate_font_style):
                    text_font = QFont(candidate_font_family)
                    text_font.setStyleName(candidate_font_style)
                    found = True
                    break

            if not found:
                # fallback -- just pretend text-font string is a font family alone!
                text_font = QFont(font_name)
                if 'bold' in font_name.lower():
                    text_font.setBold(True)
                if 'italic' in font_name.lower():
                    text_font.setItalic(True)

    text_color = Qt.black
    if 'text-color' in json_paint:
        json_text_color = json_paint['text-color']
        if isinstance(json_text_color, str):
            text_color = parse_color(json_text_color)
        elif isinstance(json_text_color, dict):
            text_color = None
            dd_properties[QgsPalLayerSettings.Color] = parse_interpolate_color_by_zoom(json_text_color)
        else:
            print("skipping non-string text-color", json_text_color)

    buffer_color = None
    if 'text-halo-color' in json_paint:
        json_text_halo_color = json_paint['text-halo-color']
        if isinstance(json_text_halo_color, str):
            buffer_color = parse_color(json_text_halo_color)
        else:
            print("skipping non-string text-halo-color", json_text_halo_color)

    buffer_size = 0
    if 'text-halo-width' in json_paint and buffer_color is not None:
        json_text_halo_width = json_paint['text-halo-width']
        if isinstance(json_text_halo_width, (float, int)):
            buffer_size = json_text_halo_width
            # TODO implement blur
            # if 'text-halo-blur' in json_paint:
            #     json_text_halo_blur = json_paint['text-halo-blur']
            #     if isinstance(json_text_halo_blur, (float, int)):
            #         buffer_size = buffer_size - json_text_halo_blur
            #     else:
            #         print("skipping non-float text-halo-blur", json_text_halo_blur)
        else:
            print("skipping non-float text-halo-width", json_text_halo_width)

    format = QgsTextFormat()
    format.setSizeUnit(QgsUnitTypes.RenderPixels)
    if text_color:
        format.setColor(text_color)
    if text_size:
        format.setSize(text_size)
    if text_font:
        format.setFont(text_font)

    if buffer_size > 0:
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(buffer_size * PX_RATIO)
        buffer_settings.setSizeUnit(RENDER_UNIT)
        buffer_settings.setColor(buffer_color)
        format.setBuffer(buffer_settings)

    symbol_placement = 'point'
    if 'symbol-placement' in json_layout:
        #point, line, polygon
        symbol_placement = json_layout['symbol-placement']

    label_settings = QgsPalLayerSettings()
    # TODO: parse field name
    label_settings.fieldName = '"name:latin"'
    if "text-field" in json_layout:
        text_field = json_layout["text-field"]
        if isinstance(text_field, list):
            label_settings.fieldName = f'\"{text_field[1][1]}\"'
        else:
            label_settings.fieldName = str(text_field)

    if label_settings.fieldName == '{_name_global}':
        label_settings.fieldName = '_name_global'
    elif label_settings.fieldName == '{_name_local}':
        label_settings.fieldName = '_name_local'
    elif label_settings.fieldName == '{_name}':
        label_settings.fieldName = '_name'

    label_settings.isExpression = True
    if "text-transform" in json_layout:
        text_transform = json_layout["text-transform"]
        if text_transform == "uppercase":
            label_settings.fieldName = 'upper({})'.format(label_settings.fieldName)
        elif text_transform == "lowercase":
            label_settings.fieldName = 'lower({})'.format(label_settings.fieldName)

    label_settings.placement = QgsPalLayerSettings.OverPoint
    wkb_type = QgsWkbTypes.PointGeometry
    if 'symbol-placement' in json_layout:
        symbol_placement = json_layout['symbol-placement']
        if symbol_placement == 'line':
            label_settings.placement = QgsPalLayerSettings.Curved
            label_settings.placementFlags = 1 #LinePlacementFlags.OnLine
            wkb_type = QgsWkbTypes.LineGeometry
        
    if text_size:
        label_settings.priority = min(text_size/3., 10.)
    else:
        label_settings.priority = 10
    label_settings.setFormat(format)

    if dd_properties:
        for dd_key, dd_expression in dd_properties.items():
            prop_collection = QgsPropertyCollection()
            prop_collection.setProperty(
                dd_key, QgsProperty.fromExpression(dd_expression))
        label_settings.setDataDefinedProperties(prop_collection)

    lb = QgsVectorTileBasicLabelingStyle()
    lb.setGeometryType(wkb_type)
    lb.setLabelSettings(label_settings)
    return lb


def parse_layers(json_layers, style_name):
    """ Parse list of layers from JSON and return QgsVectorTileBasicRenderer + QgsVectorTileBasicLabeling in a tuple """
    renderer_styles = []
    labeling_styles = []

    for json_layer in json_layers:
        layer_type = json_layer['type']
        if layer_type == 'background':
            continue
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
            st = parse_fill_layer(json_layer, style_name)
        elif layer_type == 'line':
            st = parse_line_layer(json_layer, style_name)
        elif layer_type == 'symbol':
            lb = parse_symbol_layer(json_layer, style_name)
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


def parse_background(bg_layer_data: dict):
    json_paint = bg_layer_data.get("paint")
    renderer = None
    if "background-color" in json_paint:
        sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
        # Set no stroke for background layer
        sym.symbolLayer(0).setStrokeColor(QColor("transparent"))
        # Parse fill color
        json_background_color = json_paint.get("background-color")
        if isinstance(json_background_color, dict):
            bg_color_expr = parse_interpolate_color_by_zoom(json_background_color)
            fill_symbol = sym.symbolLayer(0)
            fill_symbol.setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor,
                                               QgsProperty.fromExpression(bg_color_expr))
        elif isinstance(json_background_color, str):
            bg_color = parse_color(json_background_color)
            sym.symbolLayer(0).setColor(bg_color)
        else:
            print(f"Skipping not implemented expression for background color: "
                  f"{json_background_color} , {type(json_background_color)}")
        if "background-opacity" in json_paint:
            json_background_opacity = json_paint.get("background-opacity")
            if isinstance(json_background_opacity, dict):
                bg_opacity = parse_opacity(json_background_opacity)
            elif isinstance(json_background_opacity, (int, float)):
                sym.setOpacity(json_background_opacity)
        renderer = QgsSingleSymbolRenderer(sym)
    return renderer
