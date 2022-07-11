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
import requests
import enum
import re
import os

from PyQt5.QtCore import Qt
from qgis.PyQt.Qt import QPointF, QSize, QSizeF, QFont, QFontDatabase, QColor, QImage, QRegularExpression
from qgis.core import *
from .. import utils
from itertools import repeat
from pathlib import Path


class PropertyType(enum.Enum):
    Color = 1
    Line = 2
    Opacity = 3
    Text = 4
    Numeric = 5
    Point = 6


def parse_layers(source_name: str, style_json_data: dict, context: QgsMapBoxGlStyleConversionContext):
    """ Parse list of layers from JSON and return QgsVectorTileBasicRenderer + QgsVectorTileBasicLabeling in a tuple """

    # Sprites
    if style_json_data.get('sprite'):
        sprite_json_dict, sprite_img = get_sprites_from_style_json(style_json_data)
        context.setSprites(sprite_img, sprite_json_dict)

    # Parse layers
    renderer_styles = []
    labeling_styles = []
    layers = style_json_data.get("layers")
    source_layers = []
    map_id = style_json_data.get("id")
    for layer in layers:
        if "source" not in layer or layer["source"] != source_name:
            continue
        source_layers.append(layer)

    for json_layer in source_layers:
        layer_type = json_layer['type']
        if layer_type == 'background':
            continue
        style_id = json_layer['id']
        context.setLayerId(style_id)
        layer_name = json_layer.get('source-layer')
        min_zoom = int(json_layer['minzoom']) if 'minzoom' in json_layer else -1
        max_zoom = int(json_layer['maxzoom']) if 'maxzoom' in json_layer else -1

        enabled = True
        json_layout = json_layer.get("layout")
        if json_layout:
            layer_visibility = json_layout.get("visibility")
            if layer_visibility == "none":
                enabled = False
                continue

        filter_expr = ''
        if 'filter' in json_layer:
            filter_expr = parse_expression(json_layer['filter'], context)

        has_renderer_style = False
        has_labeling_style = False
        try:
            if layer_type == 'fill':
                has_renderer_style, renderer_style = parse_fill_layer(json_layer, context)
            elif layer_type == 'line':
                has_renderer_style, renderer_style = parse_line_layer(json_layer, context)
            elif layer_type == 'symbol':
                has_renderer_style, renderer_style, has_labeling_style, labeling_style = parse_symbol_layer(json_layer, map_id, context)
            elif layer_type == "fill-extrusion":
                continue
            else:
                context.pushWarning(f"{layer_type}: Skipping unknown layer type.")
                continue
        except (AttributeError, TypeError, BaseException) as e:
            context.pushWarning(f"{context.layerId()}: Could not convert expressions in layer style definition, "
                                f"check Python console for details.")
            print(e)

        if has_renderer_style:
            renderer_style.setStyleName(style_id)
            renderer_style.setLayerName(layer_name)
            renderer_style.setFilterExpression(filter_expr)
            renderer_style.setMinZoomLevel(min_zoom)
            renderer_style.setMaxZoomLevel(max_zoom)
            renderer_style.setEnabled(enabled)
            renderer_styles.append(renderer_style)

        if has_labeling_style:
            labeling_style.setStyleName(style_id)
            labeling_style.setLayerName(layer_name)
            labeling_style.setFilterExpression(filter_expr)
            labeling_style.setMinZoomLevel(min_zoom)
            labeling_style.setMaxZoomLevel(max_zoom)
            labeling_style.setEnabled(enabled)
            labeling_styles.append(labeling_style)

    renderer = QgsVectorTileBasicRenderer()
    renderer.setStyles(renderer_styles)

    labeling = QgsVectorTileBasicLabeling()
    labeling.setStyles(labeling_styles)

    return renderer, labeling, context.warnings()


def parse_fill_layer(json_layer, context):
    json_paint = json_layer.get('paint')
    if json_paint is None:
        context.pushWarning(f"{json_layer.get('id')}: Layer has no paint property, skipping.")
        return False, None

    dd_properties = QgsPropertyCollection()
    dd_raster_properties = QgsPropertyCollection()

    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
    fill_symbol = symbol.symbolLayer(0)
    symbol.setOutputUnit(context.targetUnit())
    fill_symbol.setOutputUnit(context.targetUnit())

    # Fill color
    fill_color = None
    if 'fill-color' in json_paint:
        json_fill_color = json_paint['fill-color']
        if isinstance(json_fill_color, dict):
            # Use data defined property
            fill_color = "dd_props"
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_interpolate_color_by_zoom(json_fill_color, context))
        elif isinstance(json_fill_color, list):
            # Use data defined property
            fill_color = "dd_props"
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_value_list(json_fill_color, PropertyType.Color, context, 1, 255))
        elif isinstance(json_fill_color, str):
            # Use simple string color
            fill_color = parse_color(json_fill_color, context)
            fill_symbol.setFillColor(fill_color)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported fill-color type ({type(json_fill_color).__name__})")

    # Fill outline color
    fill_outline_color = None
    if 'fill-outline-color' in json_paint:
        json_fill_outline_color = json_paint.get('fill-outline-color')
        if isinstance(json_fill_outline_color, dict):
            fill_outline_color = "dd_props"
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      parse_interpolate_color_by_zoom(json_fill_outline_color, context))
        elif isinstance(json_fill_outline_color, list):
            fill_outline_color = "dd_props"
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      parse_value_list(json_fill_outline_color, PropertyType.Color,
                                                       context, 1, 255, fill_outline_color))
        elif isinstance(json_fill_outline_color, str):
            fill_outline_color = parse_color(json_fill_outline_color, context)
            fill_symbol.setStrokeColor(fill_outline_color)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported fill-outline-color type ({type(json_fill_outline_color).__name__}).")

    # Fill opacity
    fill_opacity = None
    raster_opacity = None

    json_fill_opacity = json_paint.get('fill-opacity')
    if json_fill_opacity:
        if isinstance(json_fill_opacity, (float, int)):
            fill_opacity = float(json_fill_opacity)
            raster_opacity = fill_opacity
        elif isinstance(json_fill_opacity, dict) \
                and (dd_properties.isActive(QgsSymbolLayer.PropertyFillColor)\
                or dd_properties.isActive(QgsSymbolLayer.PropertyStrokeColor)):
            # opacity already defined in fill color
            fill_opacity = None
        elif isinstance(json_fill_opacity, dict):
            fill_opacity = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_interpolate_opacity_by_zoom(json_fill_opacity,
                                                                        fill_color.alpha() if fill_color else 255))
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      parse_interpolate_opacity_by_zoom(json_fill_opacity,
                                                                        fill_outline_color.alpha() if fill_outline_color else 255))
            dd_raster_properties.setProperty(QgsSymbolLayer.PropertyOpacity,
                                             parse_interpolate_by_zoom(json_fill_opacity, context, 100))
        elif isinstance(json_fill_opacity, list) and dd_properties.isActive(QgsSymbolLayer.PropertyFillColor):
            # opacity already defined in fill color
            fill_opacity = None
        elif isinstance(json_fill_opacity, list):
            fill_opacity = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_value_list(json_fill_opacity, PropertyType.Opacity, context, 1,
                                                       fill_color.alpha() if fill_color else 255))
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      parse_value_list(json_fill_opacity, PropertyType.Opacity, context, 1,
                                                       fill_outline_color.alpha() if fill_outline_color else 255))
            dd_raster_properties.setProperty(QgsSymbolLayer.PropertyOpacity,
                                             parse_value_list(json_fill_opacity, PropertyType.Numeric, context, 100, 255))
        else:
            fill_opacity = None
            context.pushWarning(f"{context.layerId()}: Skipping unsupported fill-opacity type ({type(json_fill_opacity).__name__})")

    # Fill-translate
    json_fill_translate = json_paint.get("fill-translate")
    fill_translate = QPointF()
    if json_fill_translate:
        if isinstance(json_fill_translate, dict):
            dd_properties.setProperty(QgsSymbolLayer.PropertyOffset,
                                      parse_interpolate_point_by_zoom(json_fill_translate, context, context.pixelSizeConversionFactor()))
        elif isinstance(json_fill_translate, list):
            fill_translate = QPointF(json_fill_translate[0] * context.pixelSizeConversionFactor(),
                                     json_fill_translate[1] * context.pixelSizeConversionFactor())
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported fill-translate type ({type(json_fill_translate).__name__})")

    if not fill_translate.isNull():
        fill_symbol.setOffset(fill_translate)
    fill_symbol.setOffsetUnit(context.targetUnit())

    # Fill-pattern
    json_fill_patern = json_paint.get("fill-pattern")
    if json_fill_patern:
        # fill-pattern can be String or Object
        # String: {"fill-pattern": "dash-t"}
        # Object: {"fill-pattern":{"stops":[[11,"wetland8"],[12,"wetland16"]]}}

        core_converter = QgsMapBoxGlStyleConverter()
        sprite_size = QSize()
        sprite_property = ""
        sprite_size_property = ""
        sprite = core_converter.retrieveSpriteAsBase64(json_fill_patern, context, sprite_size, sprite_property, sprite_size_property)

        if sprite:
            # when fill-pattern exists, set and insert QgsRasterFillSymbolLayer
            raster_fill = QgsRasterFillSymbolLayer()
            raster_fill.setImageFilePath(sprite)
            raster_fill.setWidth(sprite_size.width())
            raster_fill.setWidthUnit(context.targetUnit())
            raster_fill.setCoordinateMode(QgsRasterFillSymbolLayer.Viewport)
            fill_color = None

            if raster_opacity:
                raster_fill.setOpacity(raster_opacity)
            if sprite_property:
                dd_raster_properties.setProperty(QgsSymbolLayer.PropertyFile,
                                                 QgsProperty.fromExpression(sprite_property))
                dd_raster_properties.setProperty(QgsSymbolLayer.PropertyWidth,
                                                 QgsProperty.fromExpression(sprite_size_property))

            raster_fill.setDataDefinedProperties(dd_raster_properties)
            symbol.appendSymbolLayer(raster_fill)
        else:
            fill_color = None
            fill_outline_color = None

    fill_symbol.setDataDefinedProperties(dd_properties)

    if fill_opacity:
        symbol.setOpacity(fill_opacity)

    if fill_outline_color == "dd_props":
        fill_symbol.setStrokeStyle(Qt.PenStyle(Qt.SolidLine))
    elif fill_outline_color:
        fill_symbol.setStrokeColor(fill_outline_color)
    elif fill_outline_color is None:
        fill_symbol.setStrokeStyle(Qt.PenStyle(Qt.NoPen))

    if  fill_color == "dd_props":
        fill_symbol.setBrushStyle(Qt.BrushStyle(Qt.SolidPattern))
    elif fill_color:
        fill_symbol.setFillColor(fill_color)
    elif fill_color is None:
        fill_symbol.setBrushStyle(Qt.BrushStyle(Qt.NoBrush))


    style = QgsVectorTileBasicRendererStyle()
    style.setGeometryType(QgsWkbTypes.PolygonGeometry)
    style.setSymbol(symbol)

    return True, style


def parse_line_layer(json_layer: dict, context: QgsMapBoxGlStyleConversionContext):
    json_paint = json_layer.get('paint')
    if json_paint is None:
        context.pushWarning(f"{json_layer.get('id')}: Layer has no paint property, skipping.")
        return False, None

    if "line-pattern" in json_paint:
        context.pushWarning(f"{context.layerId()}: Skipping unsupported line-pattern property.")
        return False, None

    # Default
    symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
    line_symbol = symbol.symbolLayer(0)
    symbol.setOutputUnit(context.targetUnit())
    line_symbol.setOutputUnit(context.targetUnit())
    dd_properties = QgsPropertyCollection()

    # Line color
    line_color = None
    json_line_color = json_paint.get("line-color")
    if json_line_color:
        if isinstance(json_line_color, dict):
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_interpolate_color_by_zoom(json_line_color, context))
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      dd_properties.property(QgsSymbolLayer.PropertyFillColor))
        elif isinstance(json_line_color, list):
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_value_list(json_line_color, PropertyType.Color, context, 1, 255))
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      dd_properties.property(QgsSymbolLayer.PropertyFillColor))
        elif isinstance(json_line_color, str):
            line_color = parse_color(json_line_color, context)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported line-color type ({type(json_line_color).__name__}).")
    else:
        # Default to #000000
        line_color = QColor(0, 0, 0)

    # Line width
    line_width = line_symbol.width()
    line_width_property = None
    json_line_width = json_paint.get("line-width")
    if json_line_width:
        if isinstance(json_line_width, (float, int)):
            line_width = float(json_line_width * context.pixelSizeConversionFactor())
        elif isinstance(json_line_width, dict):
            line_width = None
            line_width_property = parse_interpolate_by_zoom(json_line_width, context,
                                                            context.pixelSizeConversionFactor())
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeWidth, line_width_property)
        elif isinstance(json_line_width, list):
            line_width_property = parse_value_list(json_line_width, PropertyType.Numeric, context,
                                                       context.pixelSizeConversionFactor(), 255)
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeWidth, line_width_property)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported fill-width type ({type(json_line_width).__name__}).")

    # Line offset
    line_offset = 0.0
    json_line_offset = json_paint.get("line-offset")
    if json_line_offset:
        if isinstance(json_line_offset, (int, float)):
            line_offset = - float(json_line_offset) * context.pixelSizeConversionFactor()
        elif isinstance(json_line_offset, dict):
            line_offset = None
            line_width = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyOffset,
                                      parse_interpolate_by_zoom(json_line_offset, context,
                                                                context.pixelSizeConversionFactor() * -1))
        elif isinstance(json_line_offset, list):
            line_offset = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyOffset,
                                      parse_value_list(json_line_offset, PropertyType.Numeric, context,
                                                       context.pixelSizeConversionFactor() * -1, 255))
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported line-offset type ({type(json_line_offset).__name__}).")

    # Line opacity
    line_opacity = None
    json_line_opacity = json_paint.get('line-opacity')
    if json_line_opacity:
        if isinstance(json_line_opacity, (float, int)):
            line_opacity = float(json_line_opacity)
        elif isinstance(json_line_opacity, dict) and dd_properties.isActive(QgsSymbolLayer.PropertyStrokeColor):
            # opacity already defined in stroke color
            line_opacity = None
        elif isinstance(json_line_opacity, dict):
            line_opacity = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyStrokeColor,
                                      parse_interpolate_opacity_by_zoom(json_line_opacity, line_color.alpha() if line_color else 255))
        elif isinstance(json_line_opacity, list) and dd_properties.isActive(QgsSymbolLayer.PropertyStrokeColor):
            # opacity already defined in stroke color
            line_opacity = None
        elif isinstance(json_line_opacity, list):
            line_opacity = None
            dd_properties.setProperty(QgsSymbolLayer.PropertyFillColor,
                                      parse_value_list(json_line_opacity, PropertyType.Opacity, context, 1,
                                                       line_color.alpha() if line_color else 255))
        else:
            line_opacity = None
            context.pushWarning(
                f"{context.layerId()}: Skipping unsupported line-opacity type ({type(json_line_opacity).__name__}).")

    # Line dash
    dash_vector = None
    json_dasharray = json_paint.get("line-dasharray")
    if json_dasharray:
        if isinstance(json_dasharray, dict):
            stops = json_dasharray.get("stops")
            if line_width_property:
                expr = f"array_to_string(" \
                       f"array_foreach({parse_array_stops(stops, 1)}," \
                       f"@element * coalesce(" \
                       f"({line_width_property.asExpression()}), " \
                       f"{line_symbol.width()} * {context.pixelSizeConversionFactor()})), ';')"
            else:
                expr = f"array_to_string({parse_array_stops(stops, 1)}, ';')"
            dd_properties.setProperty(QgsSymbolLayer.PropertyCustomDash, QgsProperty.fromExpression(expr))
            dash_source = stops[-1][1]
            if line_width:
                dash_vector = [i * line_width for i in dash_source]
            else:
                dash_vector = dash_source
        elif isinstance(json_dasharray, list):
            if line_width_property:
                expr = f"array_to_string(" \
                       f"array_foreach(array({','.join(map(str,json_dasharray))})," \
                       f"@element * coalesce(" \
                       f"({line_width_property.asExpression()}), " \
                       f"{line_symbol.width()} * {context.pixelSizeConversionFactor()})), ';')"
                dd_properties.setProperty(QgsSymbolLayer.PropertyCustomDash, QgsProperty.fromExpression(expr))
            if line_width:
                dash_vector = [i * line_width for i in json_dasharray]
            else:
                dash_vector = json_dasharray

        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported line-dasharray type"
                                f" ({type(json_dasharray).__name__}).")

    # Layout
    pen_cap_style = Qt.FlatCap
    pen_join_style = Qt.MiterJoin

    json_layout = json_layer.get("layout")
    if json_layout:
        if 'line-cap' in json_layout:
            pen_cap_style = parse_cap_style(json_layout.get("line-cap"))
        if 'line-join' in json_layout:
            pen_join_style = parse_join_style(json_layout.get("line-join"))

    line_symbol.setPenCapStyle(pen_cap_style)
    line_symbol.setPenJoinStyle(pen_join_style)
    line_symbol.setDataDefinedProperties(dd_properties)
    if line_offset:
        line_symbol.setOffset(line_offset)
    line_symbol.setOffsetUnit(context.targetUnit())

    if dash_vector:
        line_symbol.setCustomDashVector(dash_vector)
        line_symbol.setUseCustomDashPattern(True)
        line_symbol.setStrokeColor(QColor("transparent"))
    if line_color:
        line_symbol.setColor(line_color)
    if line_opacity:
        symbol.setOpacity(line_opacity)
    if line_width:
        line_symbol.setWidth(line_width)

    style = QgsVectorTileBasicRendererStyle()
    style.setGeometryType(QgsWkbTypes.LineGeometry)
    style.setSymbol(symbol)

    return True, style


def parse_symbol_layer(json_layer: dict, map_id: str, context: QgsMapBoxGlStyleConversionContext):
    has_labeling = False
    has_renderer = False
    core_converter = QgsMapBoxGlStyleConverter()

    json_layout = json_layer.get("layout")
    if not json_layout:
        context.pushWarning(f"{json_layer.get('id')}: Layer has no layout property, skipping.")
        return has_renderer, None, has_labeling, None

    if "text-field" not in json_layout:
        has_renderer, renderer_style = core_converter.parseSymbolLayerAsRenderer(json_layer, context)
        return has_renderer, renderer_style, has_labeling, None

    json_paint = json_layer.get("paint")
    if json_paint is None:
        context.pushWarning(f"{json_layer.get('id')}: Layer has no paint property, skipping.")
        return has_renderer, None, has_labeling, None

    dd_label_properties = QgsPropertyCollection()

    text_size = 16 * context.pixelSizeConversionFactor()
    text_size_property = QgsProperty()
    json_text_size = json_layout.get("text-size")
    if json_text_size:
        if isinstance(json_text_size, (float, int)):
            text_size = json_text_size * context.pixelSizeConversionFactor()
        elif isinstance(json_text_size, dict):
            text_size_property = parse_interpolate_by_zoom(json_text_size, context, context.pixelSizeConversionFactor())
        elif isinstance(json_text_size, list):
            text_size_property = parse_value_list(json_text_size, PropertyType.Numeric, context,
                                                  context.pixelSizeConversionFactor(), 255)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-size type ({type(json_text_size).__name__}).")
            return has_renderer, None, has_labeling, None

    if text_size_property:
        dd_label_properties.setProperty(QgsPalLayerSettings.Size, text_size_property)

    # a rough average of ems to character count conversion for a variety of fonts
    EM_TO_CHARS = 2.0

    # Text max width
    json_text_max_width = json_layout.get("text-max-width")
    text_max_width = None
    if json_text_max_width:
        if isinstance(json_text_max_width, (int, float)):
            text_max_width = json_text_max_width * EM_TO_CHARS
        elif isinstance(json_text_max_width, dict):
            dd_label_properties.setProperty(QgsPalLayerSettings.AutoWrapLength,
                                            parse_interpolate_by_zoom(json_text_max_width, context, EM_TO_CHARS))
        elif isinstance(json_text_max_width, list):
            dd_label_properties.setProperty(QgsPalLayerSettings.AutoWrapLength,
                                            parse_value_list(json_text_max_width, PropertyType.Numeric, context,
                                                             EM_TO_CHARS, 255))
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-max-width type ({type(json_text_max_width).__name__}).")
    else:
        text_max_width = 10 * EM_TO_CHARS

    # Text letter spacing
    text_letter_spacing = None
    json_text_letter_spacing = json_layout.get("text-letter-spacing")
    if json_text_letter_spacing:
        if isinstance(json_text_letter_spacing, (int, float)):
            text_letter_spacing = float(json_text_letter_spacing)
        elif isinstance(json_text_letter_spacing, dict):
            dd_label_properties.setProperty(QgsPalLayerSettings.FontLetterSpacing,
                                            parse_interpolate_by_zoom(json_text_letter_spacing, context, 1))
        elif isinstance(json_text_letter_spacing, list):
            dd_label_properties.setProperty(QgsPalLayerSettings.FontLetterSpacing,
                                            parse_value_list(json_text_letter_spacing, PropertyType.Numeric, context,
                                                             1, 255))
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-letter-spacing type ({type(json_text_letter_spacing).__name__}).")

    # Text font
    text_font = QFont()

    def check_font_dbs(font_name, font_style):
        if QgsFontUtils.fontFamilyOnSystem(font_name):
            if font_style == " " or font_style is None:
                return font_name, None
            elif QgsFontUtils.fontFamilyHasStyle(font_name, font_style):
                return font_name, font_style
        elif font_name in QFontDatabase().families():
            if font_style == " ":
                return font_name, None
            elif font_style in QFontDatabase().styles(font_name):
                return f"{font_name} {font_style}", None
        return None, None

    def split_font_family(font_name):
        text_font_parts = font_name.split(" ")
        for i in range(len(text_font_parts)):
            candidate_font_name = " ".join(text_font_parts[:i+1])
            candidate_font_style = " ".join(text_font_parts[i+1:])
            # Check as-is
            found_name, found_style = check_font_dbs(candidate_font_name, candidate_font_style)
            if found_name:
                return True, found_name, found_style
            # Remove gaps after "Extra" or "Semi"
            if "Extra " in candidate_font_style:
                candidate_font_style = candidate_font_style.replace("Extra ", "Extra")
            if "Semi " in candidate_font_style:
                candidate_font_style = candidate_font_style.replace("Semi ", "Semi")
            if "Semibold" in candidate_font_style:
                candidate_font_style = candidate_font_style.replace("Semibold", "SemiBold")
            # Check again with no gaps
            found_name, found_style = check_font_dbs(candidate_font_name, candidate_font_style)
            if found_name:
                return True, found_name, found_style
        return False, None, None


    json_text_font = json_layout.get("text-font")
    font_name = None
    if json_text_font:
        if not isinstance(json_text_font, (str, list, dict)):
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-font type {type(json_text_font)}")
        else:
            split_ok = False
            if isinstance(json_text_font, list):
                for font_name in json_text_font:
                    split_ok, font_family, font_style = split_font_family(font_name)
                    if split_ok:
                        break
                if not split_ok:
                    context.pushWarning(f"{context.layerId()}: None of fonts in {json_text_font} is available on "
                                    f"your system. Default font will be used.")
            elif isinstance(json_text_font, str):
                split_ok, font_family, font_style = split_font_family(json_text_font)
                if not split_ok:
                    context.pushWarning(f"{context.layerId()}: Referenced font {json_text_font} is not available on your "
                                        f"system. Default font will be used.")
            elif isinstance(json_text_font, dict):
                family_case_string = "CASE "
                style_case_string = "CASE "
                stops = json_text_font.get("stops")
                error = False
                for i in range(len(stops)-1):
                    # Bottom zoom and value
                    bz = stops[i][0]
                    bv = stops[i][1] if isinstance(stops[i][1], str) else stops[i][1][0]
                    if isinstance(bz, list):
                        context.pushWarning(f"{context.layerId()}: Expressions in interpolation function are not "
                                            f"supported, skipping")
                        error = True

                    # Top zoom
                    tz = stops[i+1][0]
                    if isinstance(tz, list):
                        context.pushWarning(f"{context.layerId()}: Expressions in interpolation function are not "
                                            f"supported, skipping")
                        error = True
                    split_ok, font_family, font_style = split_font_family(bv)
                    if split_ok:
                        family_case_string += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} " \
                                              f"THEN {QgsExpression.quotedValue(font_family)} "
                        style_case_string += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {bz} " \
                                             f"THEN {QgsExpression.quotedValue(font_style)} "
                    else:
                        context.pushWarning(f"{context.layerId()}: Referenced font {bv} is not available on your "
                                            f"system. Default font will be used.")
                if error:
                    return False, None, False, None
                bv = stops[-1][1] if isinstance(stops[-1][1], str) else stops[-1][1][0]
                split_ok, font_family, font_style = split_font_family(bv)
                if split_ok:
                    family_case_string += f"ELSE {QgsExpression.quotedValue(font_family)} END"
                    style_case_string += f"ElSE {QgsExpression.quotedValue(font_style)} END"
                    dd_label_properties.setProperty(QgsPalLayerSettings.Family,
                                                    QgsProperty.fromExpression(family_case_string))
                    dd_label_properties.setProperty(QgsPalLayerSettings.FontStyle,
                                                    QgsProperty.fromExpression(style_case_string))
                else:
                    context.pushWarning(f"{context.layerId()}: Referenced font {bv} is not available on your system. "
                                        f"Default font will be used.")
            if split_ok:
                text_font = QFont(font_family)
                if font_style:
                    text_font.setStyleName(font_style)

    # Text color
    text_color = None
    json_text_color = json_paint.get('text-color')
    if json_text_color:
        if isinstance(json_text_color, dict):
            dd_label_properties.setProperty(QgsPalLayerSettings.Color,
                                            parse_interpolate_color_by_zoom(json_text_color, context))
        elif isinstance(json_text_color, list):
            dd_label_properties.setProperty(QgsPalLayerSettings.Color,
                                            parse_value_list(json_text_color, PropertyType.Color, context, 1, 255))
        elif isinstance(json_text_color, str):
            text_color = parse_color(json_text_color, context)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-color type ({type(json_text_color).__name__}).")
    else:
        # Default to #000000
        text_color = QColor(0, 0, 0)

    # Buffer color
    buffer_color = None
    json_text_halo_color = json_paint.get('text-halo-color')
    if json_text_halo_color:
        if isinstance(json_text_halo_color, dict):
            dd_label_properties.setProperty(QgsPalLayerSettings.BufferColor,
                                            parse_interpolate_color_by_zoom(json_text_halo_color, context))
        elif isinstance(json_text_halo_color, list):
            dd_label_properties.setProperty(QgsPalLayerSettings.BufferColor,
                                            parse_value_list(json_text_halo_color, PropertyType.Color, context, 1, 255))
        elif isinstance(json_text_halo_color, str):
            buffer_color = parse_color(json_text_halo_color, context)
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-halo-color type ({json_text_halo_color}).")

    # Buffer size
    # the pixel based text buffers appear larger when rendered on the web - so automatically scale
    # them up when converting to a QGIS style
    # (this number is based on trial-and-error comparisons only!)

    BUFFER_SIZE_SCALE = 2.0
    json_text_halo_width = json_paint.get('text-halo-width')
    buffer_size = 0
    if json_text_halo_width:
        if isinstance(json_text_halo_width, (float, int)):
            buffer_size = json_text_halo_width * context.pixelSizeConversionFactor() * BUFFER_SIZE_SCALE
        elif isinstance(json_text_halo_width, dict):
            buffer_size = 1
            dd_label_properties.setProperty(QgsPalLayerSettings.BufferSize,
                                            parse_interpolate_by_zoom(json_text_halo_width, context,
                                                                      context.pixelSizeConversionFactor() * BUFFER_SIZE_SCALE))
        elif isinstance(json_text_halo_width, list):
            buffer_size = 1
            dd_label_properties.setProperty(QgsPalLayerSettings.BufferSize,
                                            parse_value_list(json_text_halo_width, PropertyType.Numeric, context,
                                                             context.pixelSizeConversionFactor() * BUFFER_SIZE_SCALE,
                                                             255))
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-halo-width type ({type(json_text_halo_width).__name__}).")

    # Halo blur size
    halo_blur_size = 0
    json_text_halo_blur = json_paint.get("text-halo-blur")
    if json_text_halo_blur:
        if isinstance(json_text_halo_blur, (int, float)):
            halo_blur_size = json_text_halo_blur * context.pixelSizeConversionFactor()

    format = QgsTextFormat()
    format.setSizeUnit(context.targetUnit())
    if text_color:
        format.setColor(text_color)
    if text_size:
        format.setSize(text_size)
    if text_font:
        format.setFont(text_font)
    if text_letter_spacing:
        f = format.font()
        f.setLetterSpacing(QFont.AbsoluteSpacing, text_letter_spacing)
        format.setFont(f)
    if buffer_size and buffer_color and buffer_color.alpha() > 0:
        format.buffer().setEnabled(True)
        format.buffer().setSize(buffer_size)
        format.buffer().setSizeUnit(context.targetUnit())
        format.buffer().setColor(buffer_color)
        if halo_blur_size:
            stack = QgsEffectStack()
            blur = QgsBlurEffect()
            blur.setEnabled(True)
            blur.setBlurUnit(context.targetUnit())
            blur.setBlurLevel(halo_blur_size)
            blur.setBlurMethod(QgsBlurEffect.StackBlur)
            stack.appendEffect(blur)
            stack.setEnabled(True)
            format.buffer().setPaintEffect(stack)

    label_settings = QgsPalLayerSettings()
    if text_max_width:
        label_settings.autoWrapLength = int(text_max_width)

    json_text_field = json_layout.get("text-field")
    if json_text_field:
        if isinstance(json_text_field, str):
            field_name, field_is_expression = process_label_field(json_text_field)
            label_settings.fieldName = field_name
            label_settings.isExpression = field_is_expression
        elif isinstance(json_text_field, list):
            if len(json_text_field) > 2 and json_text_field[0] == "format":
                # e.g.
                # "text-field": ["format",
                #                "foo", { "font-scale": 1.2 },
                #                "bar", { "font-scale": 0.8 }
                # ]
                parts = []
                for i in range(len(json_text_field)):
                    is_expression = False
                    part, is_expression = process_label_field(json_text_field[i])
                    if not is_expression:
                        parts.append(QgsExpression.quotedColumnRef(part))
                    else:
                        parts.append(part)
                    i += 1
                label_settings.fieldName = f"concat({','.join(parts)})"
                label_settings.isExpression = True
            else:
                # e.g.
                # "text-field": ["to-string", ["get", "name"]]
                label_settings.fieldName = parse_expression(json_text_field, context)
                label_settings.isExpression = True
        elif isinstance(json_text_field, dict):
            label_settings.fieldName = parse_field_name_dict(json_text_field, context)
            label_settings.isExpression = True
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-field type ({type(json_text_field).__name__}).")

    # Text transform
    text_transform = json_layout.get("text-transform")
    if text_transform:
        if text_transform == "uppercase":
            label_settings.fieldName = f"upper({label_settings.fieldName if label_settings.isExpression else QgsExpression.quotedColumnRef(label_settings.fieldName)})"
        elif text_transform == "lowercase":
            label_settings.fieldName = f"lower({label_settings.fieldName if label_settings.isExpression else QgsExpression.quotedColumnRef(label_settings.fieldName)})"
        label_settings.isExpression = True

    # Placement
    label_settings.placement = QgsPalLayerSettings.OverPoint
    geometry_type = QgsWkbTypes.PointGeometry
    symbol_placement = json_layout.get("symbol-placement")
    text_offset = None
    if symbol_placement == "line" or ("line" in str(symbol_placement)):
            label_settings.placement = QgsPalLayerSettings.Curved
            label_settings.lineSettings().setPlacementFlags(QgsLabeling.OnLine)
            geometry_type = QgsWkbTypes.LineGeometry

            text_rotation_alignment = json_layout.get("text-rotation-alignment")
            if text_rotation_alignment:
                if text_rotation_alignment == "viewport":
                    label_settings.placement = QgsPalLayerSettings.Horizontal

            if label_settings.placement == QgsPalLayerSettings.Curved:
                json_text_offset = json_layout.get("text-offset")
                text_offset_property = None
                if json_text_offset:
                    if isinstance(json_text_offset, dict):
                        text_offset_property = parse_interpolate_point_by_zoom(json_text_offset, context,
                                                                               text_size if not text_size_property else 1.0)
                        if not text_size_property:
                            dd_label_properties.setProperty(QgsPalLayerSettings.LabelDistance,
                                                            f"abs(array_get({text_offset_property},1))-{text_size}")
                        else:
                            dd_label_properties.setProperty(QgsPalLayerSettings.LabelDistance,
                                                            f"with_variable('text_size',{text_size_property.asExpression()},abs(array_get({text_offset_property.asExpression()},1))*@text_size-@text_size)")
                        dd_label_properties.setProperty(QgsPalLayerSettings.LinePlacementOptions,
                                                        f"if(array_get({text_offset_property},1)>0,'BL','AL')")
                    elif isinstance(json_text_offset, list):
                        text_offset = QPointF(json_text_offset[0] * text_size, json_text_offset[1] * text_size)
                    else:
                        context.pushWarning(f"{context.layerId()}: Skipping unsupported text-offset type ({type(json_text_offset).__name__})")

                    if text_offset:
                        label_settings.distUnits = context.targetUnit()
                        label_settings.dist = abs(text_offset.y()) - text_size
                        label_settings.lineSettings().setPlacementFlags(QgsLabeling.BelowLine if text_offset.y() > 0.0 else QgsLabeling.AboveLine)
                        if text_size_property and not text_offset_property:
                            dd_label_properties.setProperty(QgsPalLayerSettings.LabelDistance,
                                                            f"with_variable('text_size',{text_size_property.asExpression()},{abs(text_offset.y()/text_size)}*@text_size-@text_size)")

                if text_offset:
                    label_settings.distUnits = context.targetUnit()
                    label_settings.dist = abs(text_offset.y()) - text_size
                    label_settings.lineSettings().setPlacementFlags(QgsLabeling.BelowLine if text_offset.y() > 0.0 else QgsLabeling.AboveLine)
                    if text_offset and not text_offset_property:
                        dd_label_properties.setProperty(QgsPalLayerSettings.LabelDistance,
                                                        f"with_variable('text_size',{abs(text_offset.y()/text_size)},{text_size_property.asExpression()}*@text_size-@text_size)")
                if not text_offset:
                    label_settings.lineSettings().setPlacementFlags(QgsLabeling.OnLine)

    json_text_justify = json_layout.get("text-justify")

    if json_text_justify:
        if isinstance(json_text_justify, str):
            text_align = json_text_justify
            if text_align == "left":
                label_settings.multilineAlign = QgsPalLayerSettings.MultiLeft
            elif text_align == "right":
                label_settings.multilineAlign = QgsPalLayerSettings.MultiRight
            elif text_align == "center":
                label_settings.multilineAlign = QgsPalLayerSettings.MultiCenter
            elif text_align == "follow":
                label_settings.multilineAlign = QgsPalLayerSettings.MultiFollowPlacement
        else:
            context.pushWarning(f"{context.layerId()}: Skipping unsupported text-justify type ({type(json_text_justify).__name__}).")
    else:
        label_settings.multilineAlign = QgsPalLayerSettings.MultiCenter

    if label_settings.placement == QgsPalLayerSettings.OverPoint:
        # Default
        text_anchor = "center"
        json_text_anchor = json_layout.get("text-anchor")
        if json_text_anchor:
            if isinstance(json_text_anchor, str):
                text_anchor = json_text_anchor
            elif isinstance(json_text_anchor, dict):
                stops = json_text_anchor.get("stops")
                text_anchor = stops[-1][-1]
            else:
                context.pushWarning(f"{context.layerId()}: Skipping unsupported text-anchor type ({type(json_text_anchor).__name__})")

            if text_anchor == "center":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantOver
            elif text_anchor == "left":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantRight
            elif text_anchor == "right":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantLeft
            elif text_anchor == "top":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantBelow
            elif text_anchor == "bottom":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantOver
            elif text_anchor == "top-left":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantBelowRight
            elif text_anchor == "top-right":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantBelowLeft
            elif text_anchor == "bottom-left":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantRight
            elif text_anchor == "bottom-right":
                label_settings.quadOffset = QgsPalLayerSettings.QuadrantLeft

        json_text_offset = json_layout.get("text-offset")
        if json_text_offset:
            if isinstance(json_text_offset, dict):
                dd_label_properties.setProperty(QgsPalLayerSettings.OffsetXY,
                                                parse_interpolate_point_by_zoom(json_text_offset, context, text_size))
            elif isinstance(json_text_offset, list):
                if json_text_offset[0] == "literal":
                    text_offset = QPointF(json_text_offset[1][0] * text_size, json_text_offset[1][1] * text_size)
                else:
                    text_offset = QPointF(json_text_offset[0] * text_size, json_text_offset[1] * text_size)
            else:
                context.pushWarning(f"{context.layerId()}: Skipping unsupported text-offset type ({type(json_text_offset).__name__})")

            if text_offset:
                label_settings.offsetUnits = context.targetUnit()
                label_settings.xOffset = text_offset.x()
                label_settings.yOffset = text_offset.y()

    if text_size:
        label_settings.priority = int(min(text_size / (context.pixelSizeConversionFactor() * 3), 10.0))

    # highway-shields
    json_icon_image = json_layout.get("icon-image")
    if json_icon_image and label_settings.placement in (QgsPalLayerSettings.Horizontal, QgsPalLayerSettings.Curved) \
            and json_layer.get("id").startswith("highway-shield"):
        backgroundSettings = QgsTextBackgroundSettings()
        backgroundSettings.setEnabled(True)
        backgroundSettings.setType(QgsTextBackgroundSettings.ShapeSVG)
        dd_label_properties.setProperty(QgsPalLayerSettings.ShapeSVGFile,
                                        parse_svg_path(json_icon_image, map_id, context))
        backgroundSettings.setSizeType(0)  # buffer
        backgroundSettings.setSizeUnit(context.targetUnit())
        backgroundSettings.setSize(QSizeF(1, 1))
        format.setBackground(backgroundSettings)
        label_settings.priority = 0

    label_settings.setFormat(format)
    label_settings.obstacleSettings().setFactor(0.1)
    label_settings.setDataDefinedProperties(dd_label_properties)

    labeling_style = QgsVectorTileBasicLabelingStyle()
    labeling_style.setGeometryType(geometry_type)
    labeling_style.setLabelSettings(label_settings)

    has_labeling_style = True

    # renderer_style, has_renderer_style = parse_symbol_layer_as_renderer(json_layer, context)
    # Use QgsMapBoxGlStyleConverter.parseSymbolLayerAsRenderer
    has_renderer_style, renderer_style = core_converter.parseSymbolLayerAsRenderer(json_layer, context)

    return has_renderer_style, renderer_style, has_labeling_style, labeling_style


def parse_interpolate_color_by_zoom(json_fill_color, context):
    base = json_fill_color['base'] if 'base' in json_fill_color else 1
    stops = json_fill_color['stops']
    # Bottom color
    case_str = f"CASE "

    if len(stops) == 0:
        return QgsProperty()

    for i in range(0, len(stops) - 1):
        bz = stops[i][0]
        tz = stops[i+1][0]
        bottom_color = parse_color(stops[i][1], context)
        top_color = parse_color(stops[i+1][1], context)

        bc_hue, bc_sat, bc_light, bc_alpha = get_color_as_hsla_components(bottom_color)
        tc_hue, tc_sat, tc_light, tc_alpha = get_color_as_hsla_components(top_color)

        case_str += f"WHEN @vector_tile_zoom >= {bz} AND @vector_tile_zoom < {tz} THEN color_hsla(" \
                    f"{interpolate_expression(bz, tz, bc_hue, tc_hue, base)}, " \
                    f"{interpolate_expression(bz, tz, bc_sat, tc_sat, base)}, " \
                    f"{interpolate_expression(bz, tz, bc_light, tc_light, base)}, " \
                    f"{interpolate_expression(bz, tz, bc_alpha, tc_alpha, base)}) "

    # Top color
    tz = stops[-1][0]
    top_color = parse_color(stops[-1][1], context)
    tc_hue, tc_sat, tc_light, tc_alpha = get_color_as_hsla_components(top_color)
    case_str += f"WHEN @vector_tile_zoom >= {tz} THEN color_hsla({tc_hue}, {tc_sat}, {tc_light}, {tc_alpha}) " \
                f"ELSE color_hsla({tc_hue}, {tc_sat}, {tc_light}, {tc_alpha}) END"

    return QgsProperty.fromExpression(case_str)


def parse_interpolate_by_zoom(json_obj: dict, context: QgsMapBoxGlStyleConversionContext,
                              multiplier: float):
    base = json_obj.get('base') if json_obj.get('base') else 1
    stops = json_obj.get("stops")

    scale_expression = parse_stops(base, stops, multiplier, context)

    if isinstance(scale_expression, (int, float)):
        return scale_expression
    else:
        return QgsProperty.fromExpression(scale_expression)


def parse_interpolate_opacity_by_zoom(json_obj: dict, max_opacity: int):
    base = json_obj.get("base") if json_obj.get("base") else 1
    stops = json_obj.get("stops")

    if len(stops) == 0:
        return QgsProperty()
    if len(stops) <= 2:
        scale_exp = f"set_color_part(@symbol_color, 'alpha', " \
                    f"{interpolate_expression(stops[0][0], stops[-1][0],stops[0][1] * max_opacity, stops[-1][1] * max_opacity, base)})"
    else:
        scale_exp = parse_opacity_stops(base, stops, max_opacity)

    return QgsProperty.fromExpression(scale_exp)


def parse_opacity_stops(base: (int, float), stops: list, max_opacity: int):
    case_str = f"CASE WHEN @vector_tile_zoom < {stops[0][0]} THEN set_color_part(@symbol_color, 'alpha', " \
               f"{stops[0][1]*max_opacity})"

    for i in range(len(stops) - 1):
        case_str += f" WHEN @vector_tile_zoom >= {stops[i][0]} AND @vector_tile_zoom < {stops[i + 1][0]} " \
                    f"THEN set_color_part(@symbol_color, 'alpha', " \
                    f"{interpolate_expression(stops[i][0], stops[i+1][0], stops[i][1] * max_opacity, stops[i+1][1], max_opacity, base)})"
    case_str += f" WHEN @vector_tile_zoom >= {stops[-1][0]}" \
               f" THEN set_color_part(@symbol_color, 'alpha', {stops[-1][1] * 255.0}) END"
    return case_str


def parse_interpolate_point_by_zoom(json_obj: dict, context: QgsMapBoxGlStyleConversionContext, multiplier: float):
    base = json_obj.get("base") if json_obj.get("base") else 1
    stops = json_obj.get("stops")

    if len(stops) == 0:
        return QgsProperty()

    if len(stops) <= 2:
        scale_expr = f"array(" \
                     f"{interpolate_expression(stops[0][0], stops[-1][0], stops[0][1][0], stops[-1][1][0], base, multiplier)}, " \
                     f"{interpolate_expression(stops[0][0], stops[-1][0], stops[0][1][1], stops[-1][1][1], base, multiplier)})"
        scale_expr = parse_point_stops(base, stops, context, multiplier)

    else:
        scale_expr = parse_point_stops(base, stops, context, multiplier)

    return QgsProperty.fromExpression(scale_expr)


def parse_interpolate_string_by_zoom(json_dict: dict, context: QgsMapBoxGlStyleConversionContext, conversion_map):
    stops = json_dict.get("stops")
    if not stops:
        return QgsProperty()
    scale_expression = parse_string_stops(stops, context, conversion_map)
    return QgsProperty.fromExpression(scale_expression)


def parse_point_stops(base: float, stops: list, context: QgsMapBoxGlStyleConversionContext, multiplier: (int, float)):
    case_str = "CASE "
    for i in range(len(stops)-1):
        bz = stops[i][0]
        bv = stops[i][-1]
        if not isinstance(bv, list):
            context.pushWarning(f"{context.layerId()}: Skipping unsupported offset interpolation type ({type(bz).__name__}).")
            return

        tz = stops[i+1][0]
        tv = stops[i+1][-1]
        if not isinstance(tv, list):
            context.pushWarning(f"{context.layerId()}: Skipping unsupported offset interpolation type ({type(bz).__name__}).")
            return
    case_str += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} " \
                f"THEN array(" \
                f"{interpolate_expression(bz, tz, bv[0], tv[0], base, multiplier)}, " \
                f"{interpolate_expression(bz, tz, bv[1], tv[1], base, multiplier)}) "
    case_str += "END"
    return case_str


def parse_stops(base: (int, float), stops: list, multiplier: (int, float), context: QgsMapBoxGlStyleConversionContext):
    case_str = "CASE "
    # First zoom/value
    fz = stops[0][0]
    fv = stops[0][1]
    if isinstance(fv, list):
        fv = parse_expression(fv, context)
    case_str += f"WHEN @vector_tile_zoom <= {fz} " \
                f"THEN {fv} * {multiplier} "
    for i in range(len(stops)-1):
        bz = stops[i][0]
        bv = stops[i][1]
        if isinstance(bv, list):
            bv = parse_expression(bv, context)
        tz = stops[i + 1][0]
        tv = stops[i + 1][1]
        if isinstance(tv, list):
            tv = parse_expression(tv, context)

        case_str += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} " \
                    f"THEN {interpolate_expression(bz, tz, bv, tv, base, multiplier)} "

    z = stops[-1][0]
    v = stops[-1][1]
    if isinstance(v, list):
        v = parse_expression(v, context)
    case_str += f"WHEN @vector_tile_zoom > {z} THEN {v} * {multiplier} END"
    return case_str


def parse_discrete(json_list: list, context: QgsMapBoxGlStyleConversionContext):
    attr = parse_expression(json_list[1], context)

    if not attr:
        context.pushWarning(f"{context.layerId()}: Could not interpret step expression.")
        return

    case_str = "CASE "
    for i in range(2, len(json_list)-1, 2):
        # WHEN value
        when_value = json_list[i]
        # THEN value
        then_value = json_list[i+1]
        # IN operator for list
        if isinstance(when_value, list):
            match_str_lst = [QgsExpression.quotedValue(wv) for wv in when_value]
            case_str += f"WHEN {attr} IN ({','.join(match_str_lst)}) THEN {then_value} "
        # EQUAL operator for single key
        elif isinstance(when_value, str):
            case_str += f"WHEN {attr}={QgsExpression.quotedValue(when_value)} THEN {then_value} "

    else_value = json_list[-1]
    case_str += f"ELSE {else_value} END"
    return case_str


def parse_concat(json_list: list, context: QgsMapBoxGlStyleConversionContext):
    concat_items = list(map(parse_expression, json_list[1:], repeat(context)))
    concat_str = f"concat({','.join(concat_items)})"
    return concat_str


def parse_case(json_list: list, context: QgsMapBoxGlStyleConversionContext):
    case_str = "CASE "
    for i in range(1, len(json_list) - 1, 2):
        # WHEN value
        when_value = json_list[i]
        # THEN value
        then_value = json_list[i + 1]
        if isinstance(when_value, list):
            when_expr = parse_expression(when_value, context)
            case_str += f"WHEN {when_expr} THEN {then_value} "
        # EQUAL operator for single key
        elif isinstance(when_value, str):
            case_str += f"WHEN {QgsExpression.quotedValue(when_value)} THEN {then_value} "
    else_value = json_list[-1]
    case_str += f"ELSE {else_value} END"
    return case_str


def parse_array_stops(stops: list, multiplier: (int, float)):
    if len(stops) < 2:
        return
    case_str = "CASE "
    for i in range(len(stops)-1):
        bz = stops[i][0]
        bv = stops[i][1]
        bl = []
        for v in bv:
            bl.append(str(float(v) * multiplier))
        tz = stops[i+1][0]

        case_str += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} THEN array({','.join(bl)}) "

    lz = stops[-1][0]
    lv = stops[-1][1]
    ll = []
    for v in lv:
        ll.append(str(float(v) * multiplier))
    case_str += f"WHEN @vector_tile_zoom > {lz} THEN array({','.join(ll)}) "
    case_str += f"END"
    return case_str


def process_label_field(string: str):
    # Convert field name
    # {field_name} is permitted in string -- if multiple fields are present, convert them to an expression
    # but if single field is covered in {}, return it directly
    string = string.strip()
    single_field_rx = QRegularExpression("^{([^}]+)}$")
    match = single_field_rx.match(string)
    if match.hasMatch():
        is_expression = True
        return QgsExpression.quotedColumnRef(match.captured(1)), is_expression
    multi_field_rx = "(?={[^}]+})"
    parts = re.split(multi_field_rx, string)
    if len(parts) > 1:
        is_expression = True
        res = []
        for part in parts:
            if not part:
                continue
            elif "}" in part:
                # part will start at a {field} reference
                split = part.split("}")
                res.append(QgsExpression.quotedColumnRef(split[0][1:]))
                if split[1]:
                    res.append(QgsExpression.quotedValue(split[1]))
            else:
                res.append(QgsExpression.quotedValue(part))
        return f"concat({','.join(res)})", is_expression
    else:
        is_expression = False
    return QgsExpression.quotedColumnRef(string), is_expression


def parse_string_stops(stops, context, conversion_map):
    case_str = "CASE "
    for i in range(len(stops)-1):
        # Bottom zoom and value
        bz = stops[i][0]
        bv = stops[i][1]

        if isinstance(bz, list):
            context.pushWarning(f"{context.layerId()}: Expressions in interplation function are not supported, skipping.")
            return

        # Top zoom
        tz = stops[i+1][0]
        if isinstance(tz, list):
            context.pushWarning(f"{context.layerId()}: Expressions in interplation function are not supported, skipping.")
            return

        case_str += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} " \
                    f"THEN {QgsExpression.quotedValue(conversion_map[bv][bv])} "
    case_str += f"ELSE {QgsExpression.quotedValue(conversion_map[stops[-1][1]][stops[-1][1]])} END"

    return case_str


def parse_value_list(json_list: list, property_type: PropertyType, context: QgsMapBoxGlStyleConversionContext,
                     multiplier: float, max_opacity: int):
    method = json_list[0]
    if method == "interpolate":
        return parse_interpolate_list_by_zoom(json_list, property_type, context, multiplier, max_opacity)
    elif method == "match":
        return parse_match_list(json_list, property_type, context, multiplier, max_opacity)
    else:
        context.pushWarning(f"{context.layerId()}: Could not interpret value list with method {method}")
        return QgsProperty()


def parse_match_list(json_list: list, property_type: PropertyType, context: QgsMapBoxGlStyleConversionContext,
                     multiplier: float, max_opacity: int):
    attr = parse_expression(json_list[1], context)

    if not attr:
        context.pushWarning(f"{context.layerId()}: Could not interpret match list.")
        return QgsProperty()

    case_str = "CASE "
    for i in range(2, len(json_list)-1, 2):
        # THEN value
        then_value = json_list[i+1]
        if property_type == PropertyType.Color:
            color = parse_color(then_value, context)
            then_value_str = QgsExpression.quotedString(color.name(QColor.HexArgb))
        elif property_type == PropertyType.Numeric:
            then_value_str = str(then_value * multiplier)
        elif property_type == PropertyType.Opacity:
            then_value_str = str(then_value * max_opacity)
        elif property_type == PropertyType.Point:
            then_value_str = f"array({then_value[0] * multiplier},{then_value[0] * multiplier})"
        # WHEN value
        when_value = json_list[i]
        # IN operator for list
        if isinstance(when_value, list):
            match_str_lst = [QgsExpression.quotedValue(wv) for wv in when_value]
            case_str += f"WHEN {attr} IN ({','.join(match_str_lst)}) THEN {then_value_str} "
        # EQUAL operator for single key
        elif isinstance(when_value, (str, int, float)):
            case_str += f"WHEN {attr}={QgsExpression.quotedValue(when_value)} THEN {then_value_str} "

    if property_type == PropertyType.Color:
        color = parse_color(json_list[-1], context)
        else_value = QgsExpression.quotedString(color.name(QColor.HexArgb))
    elif property_type == PropertyType.Numeric:
        v = json_list[-1] * multiplier
        else_value = str(v)
    elif property_type == PropertyType.Opacity:
        v = json_list[-1] * max_opacity
        else_value = str(v)
    elif property_type == PropertyType.Point:
        else_value = f"array(" \
                     f"{json_list[-1][0] * multiplier}," \
                     f"{json_list[-1][0] * multiplier})"
    case_str += f"ELSE {else_value} END"
    return QgsProperty.fromExpression(case_str)


def parse_interpolate_list_by_zoom(json_list: list, type: PropertyType, context: QgsMapBoxGlStyleConversionContext,
                                   multiplier: float, max_opacity: int):
    if json_list[0] != "interpolate":
        context.pushWarning(f"{context.layerId()}: Could not interpret value list.")
        return QgsProperty()

    technique = json_list[1][0]

    if technique == "linear":
        base = 1
    elif technique == "exponential":
        base = json_list[1][1]
    elif technique == "cubic-bezier":
        context.pushWarning(f"{context.layerId()}: Cubic-bezier interpolation is not supported, linear used instead.")
        base = 1
    else:
        context.pushWarning(f"{context.layerId()}: Skipping not implemented interpolation method {technique}")
        return QgsProperty()

    if json_list[2][0] != "zoom":
        context.pushWarning(f"{context.layerId()}: Skipping not implemented interpolation input {json_list[2]}")
        return QgsProperty()

    # Convert stops into list of lists
    list_stops_values = json_list[3:]
    it = iter(list_stops_values)
    stops = list(zip(it, it))
    props = {"base": base, "stops": stops}

    if type == PropertyType.Color:
        return parse_interpolate_color_by_zoom(props, context)
    elif type == PropertyType.Numeric:
        return parse_interpolate_by_zoom(props, context, multiplier)
    elif type == PropertyType.Opacity:
        return parse_interpolate_opacity_by_zoom(props, max_opacity)
    elif type == PropertyType.Point:
        return parse_interpolate_point_by_zoom(props, context, multiplier)

    return QgsProperty()


def parse_color(json_color: str, context: QgsMapBoxGlStyleConversionContext):
    if not isinstance(json_color, str):
        context.pushWarning(f"{context.layerId()}: Could not parse non-string color {json_color}, skipping.")
        return None
    return QgsSymbolLayerUtils.parseColor(json_color)


def get_color_as_hsla_components(qcolor: QColor):
    """
    Takes QColor object and returns HSLA components in required format for QGIS color_hsla() function.
    hue: an integer value from 0 to 360,
    saturation: an integer value from 0 to 100,
    lightness: an integer value from 0 to 100,
    alpha: an integer value from 0 (completely transparent) to 255 (opaque).
    """
    hue = int(max(0, qcolor.hslHue()))
    sat = int(qcolor.hslSaturation() / 255.0 * 100)
    lightness = int(qcolor.lightness() / 255 * 100)
    alpha = int(qcolor.alpha())
    return hue, sat, lightness, alpha


def interpolate_expression(zoom_min: float, zoom_max: float, value_min: float, value_max: float, base: float, multiplier: float=1):
    if isinstance(value_min, (int, float)) and isinstance(value_max, (int, float)) and qgsDoubleNear(value_min, value_max):
        return value_min * multiplier

    if base == 1:
        expression = f"scale_linear(@vector_tile_zoom,{zoom_min},{zoom_max},{value_min},{value_max})"
    else:
        expression = f"{value_min} + ({value_max} - {value_min}) * " \
                     f"({base}^(@vector_tile_zoom-{zoom_min})-1)/({base}^({zoom_max}-{zoom_min})-1)"

    if multiplier != 1:
        return f"({expression}) * {multiplier}"
    else:
        return expression


def parse_cap_style(style: str):
    if style == "round":
        return Qt.RoundCap
    elif style == "square":
        return Qt.SquareCap
    else:
        # default
        return Qt.FlatCap


def parse_join_style(style: str):
    if style == "bevel":
        return Qt.BevelJoin
    elif style == "round":
        return Qt.RoundJoin
    else:
        # default
        return Qt.MiterJoin


def parse_expression(json_expr, context):
    """ Parses expression into QGIS expression string """
    if isinstance(json_expr, str):
        return QgsExpression.quotedValue(json_expr)

    op = json_expr[0]

    if op in ('all', "any", "none"):
        lst = [parse_value(v, context) for v in json_expr[1:]]
        if None in lst:
            context.pushWarning(f"{context.layerId}: Skipping unsupported expression.")
            return
        if op == "none":
            operator_string = ") AND NOT ("
            return f"NOT ({operator_string.join(lst)})"
        if op == 'all':
            operator_string = ") AND ("
        elif op == 'any':
            operator_string = ") OR ("
        return f"({operator_string.join(lst)})"
    elif op == '!':
        # ! inverts next expression meaning
        contra_json_expr = json_expr[1]
        contra_json_expr[0] = op + contra_json_expr[0]
        # ['!', ['has', 'level']] -> ['!has', 'level']
        return parse_key(contra_json_expr, context)
    elif op in ("==", "!=", ">=", ">", "<=", "<"):
        # use IS and NOT IS instead of = and != because they can deal with NULL values
        if op == "==":
            op = "IS"
        elif op == "!=":
            op = "IS NOT"
        return f"{parse_key(json_expr[1], context)} {op} {parse_value(json_expr[2], context)}"
    elif op == 'has':
        return parse_key(json_expr[1], context) + " IS NOT NULL"
    elif op == '!has':
        return parse_key(json_expr[1], context) + " IS NULL"
    elif op == 'in' or op == '!in':
        key = parse_key(json_expr[1], context)
        lst = [parse_value(v, context) for v in json_expr[2:]]
        if None in lst:
            context.pushWarning(f"{context.layerId}: Skipping unsupported expression.")
            return
        if op == 'in':
            return f"{key} IN ({', '.join(lst)})"
        else:  # not in
            return f"({key} IS NULL OR {key} NOT IN ({', '.join(lst)}))"
    elif op == 'get':
        if json_expr[1].startswith("name"):
            return parse_key(json_expr[1], context)
        elif json_expr[1] == "class":
            return parse_key(json_expr[1], context)
        else:
            return f"attribute('{json_expr[1]}')"
    elif op == 'match':
        attr = json_expr[1][1]

        if len(json_expr) == 5 and isinstance(json_expr[3], bool) and isinstance(json_expr[4], bool):
            if isinstance(json_expr[2], list):
                lst = map(QgsExpression.quotedValue, json_expr[2])
                if len(json_expr[2]) > 1:
                    return f"{attr} IS NULL OR {QgsExpression.quotedColumnRef(attr)} IN ({', '.join(lst)})"
                else:
                    return QgsExpression.createFieldEqualityExpression(attr, json_expr[2][0])
            elif isinstance(json_expr[2], (str, float, int)):
                return QgsExpression.createFieldEqualityExpression(attr, json_expr[2])
            else:
                context.pushWarning(f"{context.layerId}: Skipping unsupported expression.")
                return
        else:
            case_str = "CASE "
            for i in range(2, len(json_expr)-2, 2):
                if isinstance(json_expr[i], (list, tuple)):
                    lst = list(map(QgsExpression.quotedValue, json_expr[i]))
                    if len(lst) > 1:
                        case_str += f"WHEN {QgsExpression.quotedValue(attr)} IN ({', '.join(lst)}) "
                    else:
                        case_str += f"WHEN {QgsExpression.createFieldEqualityExpression(attr, json_expr[i])} "
                elif isinstance(json_expr[i], (str, float, int)):
                    case_str += f"WHEN ({QgsExpression.createFieldEqualityExpression(attr, json_expr[i])}) "
                case_str += f"THEN {json_expr[i+1]} "
            case_str += f"ELSE {QgsExpression.quotedValue(json_expr[-1])} END"
            return case_str
    elif op == "to-string":
        return f"to_string({parse_expression(json_expr[1], context)})"
    elif op == "step":
        return parse_discrete(json_expr, context)
    elif op == "literal":
        field_name, field_is_expression = process_label_field(json_expr[1])
        return field_name
    elif op == "concat":
        return parse_concat(json_expr, context)
    elif op == "case":
        return parse_case(json_expr, context)
    else:
        context.pushWarning(f"{context.layerId()}: Skipping unsupported expression.")
        return


def parse_value(json_value, context):
    if isinstance(json_value, list):
        return parse_expression(json_value, context)
    elif isinstance(json_value, str):
        return QgsExpression.quotedValue(json_value)
    elif isinstance(json_value, (int, float)):
        return str(json_value)
    else:
        context.pushWarning(f"{context.layerId}: Skipping unsupported expression part: {json_value}")
        return None


def parse_key(json_key, context):
    if json_key == '$type' or json_key == 'geometry-type':
        return "_geom_type"
    elif isinstance(json_key, list):
        if len(json_key) > 1:
            return parse_expression(json_key, context)
        else:
            return parse_key(json_key[0], context)
    return QgsExpression.quotedColumnRef(json_key)


def parse_field_name_dict(json_obj, context):
    stops = json_obj.get("stops")

    if len(stops) == 0:
        return
    else:
        case_str = "CASE "
        for i in range(len(stops)-1):
            bz = stops[i][0]
            bv = stops[i][1]
            if isinstance(bv, list):
                context.pushWarning(
                    f"{context.layerId()}: Expressions in field name are not supported, skipping.")
                return QgsExpression()
            processed_bv, is_expression = process_label_field(bv)
            tz = stops[i + 1][0]
            case_str += f"WHEN @vector_tile_zoom > {bz} AND @vector_tile_zoom <= {tz} " \
                        f"THEN {processed_bv} "

        z = stops[-1][0]
        v = stops[-1][1]
        processed_v, is_expression =  process_label_field(v)
        case_str += f"WHEN @vector_tile_zoom > {z} THEN {processed_v} END"
        return case_str


def parse_svg_path(json_icon_image, map_id, context):
    ICONS_PATH = Path(os.path.dirname(os.path.realpath(__file__)).strip("gl2qgis"), "data", "icons").as_posix()
    if map_id == "openstreetmap":
        return QgsProperty.fromExpression(f"""'{ICONS_PATH}/{json_icon_image}.svg'""")
    if map_id == "bright":
        ICONS_PATH = f"{ICONS_PATH}/bright/"
    if isinstance(json_icon_image, str):
        image_parts = re.split('{|}', json_icon_image)
        concat_expr = f"concat('{ICONS_PATH}/', "
        for p in image_parts:
            if p:
                if not p.startswith("_") and not p.endswith("_"):
                    p=f"attribute('{p}')"
                    concat_expr = f"{concat_expr}{p}, "
                else:
                    concat_expr = f"{concat_expr}'{p}', "
        concat_expr = f"{concat_expr}'.svg')"
        return QgsProperty.fromExpression(concat_expr)
    elif isinstance(json_icon_image, list):
        if json_icon_image[0] == 'concat':
            json_icon_image.insert(1, f"{ICONS_PATH}/")
            json_icon_image.append(".svg")
            concat_expr = parse_concat(json_icon_image, context)
            return QgsProperty.fromExpression(concat_expr)
    else:
        context.pushWarning(f"{context.layerId}: Cannot parse svg icon path.")
        return


def parse_background(bg_layer_data: dict):
    json_paint = bg_layer_data.get("paint")
    renderer = None
    core_converter = QgsMapBoxGlStyleConverter()
    if "background-color" in json_paint:
        sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
        # Set no stroke for background layer
        sym.symbolLayer(0).setStrokeColor(QColor("transparent"))
        # Parse fill color
        json_background_color = json_paint.get("background-color")
        context = QgsMapBoxGlStyleConversionContext()
        if isinstance(json_background_color, dict):
            bg_color_expr = core_converter.parseInterpolateColorByZoom(json_background_color, context)
            fill_symbol = sym.symbolLayer(0)
            fill_symbol.setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor, bg_color_expr[0])
        elif isinstance(json_background_color, str):
            bg_color = core_converter.parseColor(json_background_color, context)
            sym.symbolLayer(0).setColor(bg_color)
        elif isinstance(json_background_color, list):
            bg_color_expr = parse_value_list(json_background_color, PropertyType.Color, context, 1, 255)
            fill_symbol = sym.symbolLayer(0)
            fill_symbol.setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor, bg_color_expr)
        else:
            context.pushWarning(f"Background: Skipping not implemented expression for background color: "
                                f"{json_background_color} , {type(json_background_color)}")
        if "background-opacity" in json_paint:
            json_background_opacity = json_paint.get("background-opacity")
            if isinstance(json_background_opacity, dict):
                bg_opacity = core_converter.parseOpacity(json_background_opacity)
            elif isinstance(json_background_opacity, (int, float)):
                sym.setOpacity(json_background_opacity)
        renderer = QgsSingleSymbolRenderer(sym)
    return renderer


def get_sprites_from_style_json(style_json_data: dict):
    sprite_url = style_json_data.get("sprite")
    if sprite_url is None:
        return None, None

    # sprite_json_dict = json.loads(requests.get(sprite_url + '@2x.json').text)
    sprite_json_dict = utils.qgis_request_json(f"{sprite_url}@2x.json")
    sprite_img = QImage()
    sprite_img.loadFromData(utils.qgis_request_data(f"{sprite_url}@2x.png"))
    return sprite_json_dict, sprite_img
