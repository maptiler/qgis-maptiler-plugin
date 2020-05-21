from abc import ABCMeta, abstractmethod
from enum import Enum


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
