from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Type


class LayerType(Enum):
    BACKGROUND = 0
    FILL = 1
    LINE = 2
    SYMBOL = 3
    RASTER = 4
    CIRCLE = 5
    FILL_EXTRUSION = 6
    HEATMAP = 7
    HILLSHADE = 8


class LineCap(Enum):
    BUTT = 0
    ROUND = 1
    SQUARE = 2


class LineJoin(Enum):
    BEVEL = 0
    ROUND = 1
    MITER = 2


class Visibility(Enum):
    NONE = 0
    VISIBLE = 1


class StyleGL(object):
    def __init__(self, style_dict):
        self.__dict__ = style_dict


class BaseLayerGL(metaclass=ABCMeta):
    def __init__(self, layer_name, layer_data):
        self.source_layer = layer_name
        self.data = layer_data

    def styles2Styles(self):
        list_of_style_dicts = self.data.get("styles")
        list_of_styles = []
        for style_dict in list_of_style_dicts:
            style = StyleGL(style_dict)
            list_of_styles.append(style)

        return list_of_styles


class BackgroundLayerGL(BaseLayerGL):
    layerType = LayerType.BACKGROUND

    def __init__(self, id):
        super().__init__(id, None, None)
        self._visibility = None
        self._background_pattern = None
        self._background_opacity = None
        self._background_color = None


class FillLayerGL(BaseLayerGL):
    layerType = LayerType.FILL

    def __init__(self, layer_name, layer_data):
        super().__init__(layer_name, layer_data)
        self.styles = self.styles2Styles()

    def get_styles(self):
        return self.styles


class LineLayerGL(BaseLayerGL):
    layerType = LayerType.LINE

    def __init__(self, id, source, source_layer):
        super().__init__(id, source, source_layer)
        self.line_blur = None
        self.line_cap: LineCap
        self.line_color = None
        self.line_dasharray = None
        self.line_gap_width = None
        self.line_gradient = None
        self.line_join: LineJoin
        self.line_miter_limit = None
        self.line_offset = None
        self.line_opacity = None
        self.line_pattern = None
        self.line_round_limit = None
        self.line_sort_key = None
        self.line_translate = None
        self.line_translate_anchor = None
        self.line_width = None
        self.visibility: Visibility


class SymbolLayerGL(BaseLayerGL):
    layerType = LayerType.SYMBOL

    def __init__(self, id, source, source_layer):
        super().__init__(id, source, source_layer)
        self.icon_allow_overlap = None
        self.icon_anchor = None
        self.icon_color = None
        self.icon_halo_blur = None
        self.icon_halo_color = None
        self.icon_halo_width = None
        self.icon_ignore_placement = None
        self.icon_image = None
        self.icon_keep_upright = None
        self.icon_offset = None
        self.icon_opacity = None
        self.icon_optional = None
        self.icon_padding = None
        self.icon_pitch_alignment = None
        self.icon_rotate = None
        self.icon_rotation_alignment = None
        self.icon_size = None
        self.icon_text_fit = None
        self.icon_text_fit_padding = None
        self.icon_translate = None
        self.icon_translate_anchor = None
        self.symbol_avoid_edges = None
        self.symbol_placement = None
        self.symbol_sort_key = None
        self.symbol_spacing = None
        self.symbol_z_order = None
        self.text_allow_overlap = None
        self.text_anchor = None
        self.text_color = None
        self.text_field = None
        self.text_font = None
        self.text_halo_blur = None
        self.text_halo_color = None
        self.text_halo_width = None
        self.text_ignore_placement = None
        self.text_justify = None
        self.text_keep_upright = None
        self.text_letter_spacing = None
        self.text_line_height = None
        self.text_max_angle = None
        self.text_max_width = None
        self.text_offset = None
        self.text_opacity = None
        self.text_optional = None
        self.text_padding = None
        self.text_pitch_alignment = None
        self.text_radial_offset = None
        self.text_rotate = None
        self.text_rotation_alignment = None
        self.text_size = None
        self.text_transform = None
        self.text_translate = None
        self.text_translate_anchor = None
        self.text_variable_anchor = None
        self.text_writing_mode = None
        self.visibility: Visibility


def layer2Layer(layer_name: str, layer_data: dict):
    layer_type = layer_data.get("type")
    if layer_type == "fill":
        layerGL = FillLayerGL(layer_name, layer_data)

    print("Done")
    return layerGL

def dokopirotva():
    json_paint = json_layer['paint']

    if 'fill-color' not in json_paint:
        print("skipping fill without fill-color", json_paint)
        return

    json_fill_color = json_paint['fill-color']
    if not isinstance(json_fill_color, str):
        print("skipping non-string color", json_fill_color)
        return

    fill_color = parse_color(json_fill_color)

    fill_outline_color = fill_color

    if 'fill-outline-color' in json_paint:
        json_fill_outline_color = json_paint['fill-outline-color']
        if isinstance(json_fill_outline_color, str):
            fill_outline_color = parse_color(json_fill_outline_color)
        else:
            print("skipping non-string color", json_fill_outline_color)

    fill_opacity = 1.0
    if 'fill-opacity' in json_paint:
        json_fill_opacity = json_paint['fill-opacity']
        if isinstance(json_fill_opacity, (float, int)):
            fill_opacity = float(json_fill_opacity)
        else:
            print("skipping non-float opacity", json_fill_opacity)

    # TODO: fill-translate

    sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PolygonGeometry)
    fill_symbol = sym.symbolLayer(0)
    fill_symbol.setColor(fill_color)
    fill_symbol.setStrokeColor(fill_outline_color)
    sym.setOpacity(fill_opacity)

    st = QgsVectorTileBasicRendererStyle()
    st.setGeometryType(QgsWkbTypes.PolygonGeometry)
    st.setSymbol(sym)
    return st
