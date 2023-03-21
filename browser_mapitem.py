import os
import json
import requests
import webbrowser

from qgis.core import *
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton
from qgis.gui import QgsMessageViewer
from qgis.utils import iface
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

from .gl2qgis import converter

from .configure_dialog import ConfigureDialog
from .edit_connection_dialog import EditConnectionDialog
from .settings_manager import SettingsManager
from . import utils

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")
DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
BG_VECTOR_PATH = os.path.join(DATA_PATH, "background.geojson")
TERRAIN_COLOR_RAMP_PATH = os.path.join(DATA_PATH, "terrain-color-ramp.txt")
OCEAN_COLOR_RAMP_PATH = os.path.join(DATA_PATH, "ocean-color-ramp.txt")
SPRITES_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "gl2qgis", "sprites")


class MapDataItem(QgsDataItem):
    def __init__(self, parent, name, dataset, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom,
                             parent, name, "/MapTiler/maps/" + name)

        icon_path = os.path.join(IMGS_PATH, "icon_maps_light.svg")
        if utils.is_in_darkmode():
            icon_path = os.path.join(IMGS_PATH, "icon_maps_dark.svg")
        self.setIcon(QIcon(icon_path))

        self.populate()  # set to treat Item as not-folder-like

        self._parent = parent
        self._name = name
        self._dataset = dataset
        self._editable = editable

    def handleDoubleClick(self):
        smanager = SettingsManager()
        prefervector = int(smanager.get_setting('prefervector'))

        if 'custom' in self._dataset:
            self._add_custom_to_canvas()
        elif utils.is_qgs_vectortile_api_enable() and prefervector and 'vector' in self._dataset:
            self._add_vector_to_canvas()
        elif 'raster-dem' in self._dataset:
            self._add_raster_dem_to_canvas()
        elif 'terrain-group' in self._dataset:
            self._add_terrain_group_to_canvas()
        else:
            self._add_raster_to_canvas()
        return True

    def actions(self, parent):
        actions = []

        # user custom map
        if 'custom' in self._dataset:
            add_custom_action = QAction(QIcon(), 'Add Layer', parent)
            add_custom_action.triggered.connect(
                lambda: self._add_custom_to_canvas())
            actions.append(add_custom_action)

            edit_action = QAction(QIcon(), 'Edit', parent)
            edit_action.triggered.connect(self._edit)
            actions.append(edit_action)

            delete_action = QAction(QIcon(), 'Delete', parent)
            delete_action.triggered.connect(self._delete)
            actions.append(delete_action)

        # Terrain-RGB
        elif 'raster-dem' in self._dataset:
            add_raster_dem_action = QAction(QIcon(), 'Add Layer', parent)
            add_raster_dem_action.triggered.connect(
                lambda: self._add_raster_dem_to_canvas())
            actions.append(add_raster_dem_action)

            remove_action = QAction(QIcon(), 'Remove', parent)
            remove_action.triggered.connect(self._remove)
            actions.append(remove_action)

        # MapTiler map
        else:
            add_raster_action = QAction(QIcon(), 'Add as Raster', parent)
            add_raster_action.triggered.connect(
                lambda: self._add_raster_to_canvas())
            actions.append(add_raster_action)

            # QGIS version 3.13 or more
            if utils.is_qgs_vectortile_api_enable():
                add_vector_action = QAction(QIcon(), 'Add as Vector', parent)
                add_vector_action.triggered.connect(
                    lambda: self._add_vector_to_canvas())
                actions.append(add_vector_action)

            remove_action = QAction(QIcon(), 'Remove', parent)
            remove_action.triggered.connect(self._remove)
            actions.append(remove_action)

            if 'customize_url' in self._dataset:
                separator = QAction(QIcon(), '', parent)
                separator.setSeparator(True)
                actions.append(separator)

                open_customize_url_action = QAction(QIcon(), 'Customize in Cloud ↗', parent)
                open_customize_url_action.triggered.connect(self._open_customize_url)
                actions.append(open_customize_url_action)

        return actions

    def _are_credentials_valid(self):
        # credentials validation
        if not utils.validate_credentials():
            QMessageBox.warning(None, 'Access Error', '\nAccess error occurred. \nPlease Confirm your Credentials.')
            return False
        return True

    def _is_vector_json(self, json_url: str) -> bool:
        url_endpoint = json_url.split("?")[0]
        if url_endpoint.endswith(".json"):
            style_json_data = converter.get_style_json(json_url)
            if "sources" in style_json_data and "layers" in style_json_data:
                return True
        # tiles.json
        else:
            json_data = json.loads(requests.get(json_url).text)
            data_format = json_data['format']
            return data_format == 'pbf'

    def _add_raster_to_canvas(self, data_key='raster'):
        """add raster layer from tiles.json"""
        if not self._are_credentials_valid() and data_key == 'raster':
            self._openConfigureDialog()
            return

        try:
            tile_json_url = self._dataset[data_key]
            tile_json_data = utils.qgis_request_json(tile_json_url)

            layer_zxy_url = tile_json_data.get("tiles")[0]
            if layer_zxy_url.startswith("https://api.maptiler.com/maps"):
                smanager = SettingsManager()
                auth_cfg_id = smanager.get_setting('auth_cfg_id')
                layer_zxy_url = f"{layer_zxy_url.split('?')[0]}?usage={{usage}}"
                if ".png" in layer_zxy_url:
                    url_split = layer_zxy_url.split(".png")
                    uri = f"type=xyz&url={url_split[0]}@2x.png{url_split[1]}&authcfg={auth_cfg_id}"
                elif ".jpg" in layer_zxy_url:
                    url_split = layer_zxy_url.split(".jpg")
                    uri = f"type=xyz&url={url_split[0]}@2x.jpg{url_split[1]}&authcfg={auth_cfg_id}"
                elif ".webp" in layer_zxy_url:
                    url_split = layer_zxy_url.split(".webp")
                    uri = f"type=xyz&url={url_split[0]}@2x.webp{url_split[1]}&authcfg={auth_cfg_id}"
            elif layer_zxy_url.startswith("https://api.maptiler.com/tiles"):
                smanager = SettingsManager()
                auth_cfg_id = smanager.get_setting('auth_cfg_id')
                layer_zxy_url = f"{layer_zxy_url.split('?')[0]}?usage={{usage}}"
                uri = f"type=xyz&url={layer_zxy_url}&authcfg={auth_cfg_id}"
            else:
                uri = f"type=xyz&url={layer_zxy_url}"
            zmax = tile_json_data.get("maxzoom")
            if zmax:
                uri = f"{uri}&zmax={zmax}"
            raster = QgsRasterLayer(uri, self._name, "wms")

            # change resampler to bilinear
            qml_str = self._qml_of(raster)
            bilinear_qml = self._change_resampler_to_bilinear(qml_str)
            ls = QgsMapLayerStyle(bilinear_qml)
            ls.writeToLayer(raster)

            # add Copyright
            attribution_text = tile_json_data.get("attribution")
            raster.setAttribution(attribution_text)

            # add rlayer to project
            proj = QgsProject().instance()
            proj.addMapLayer(raster, False)
            root = proj.layerTreeRoot()
            root.addLayer(raster)
        except utils.MapTilerApiException as e:
            self._display_exception(e)


    def _add_raster_dem_to_canvas(self, data_key='raster-dem'):
        """add raster layer from tiles.json"""
        if not self._are_credentials_valid() and data_key == 'raster-dem':
            self._openConfigureDialog()
            return

        try:
            tile_json_url = self._dataset[data_key]
            tile_json_data = utils.qgis_request_json(tile_json_url)
            layer_zxy_url = tile_json_data.get("tiles")[0]
            if layer_zxy_url.startswith("https://api.maptiler.com/tiles/terrain-rgb") or layer_zxy_url.startswith("https://api.maptiler.com/tiles/ocean-rgb"):
                smanager = SettingsManager()
                auth_cfg_id = smanager.get_setting('auth_cfg_id')
                intprt = "maptilerterrain"
                layer_zxy_url = f"{layer_zxy_url.split('?')[0]}?usage={{usage}}"
                uri = f"type=xyz&url={layer_zxy_url}&authcfg={auth_cfg_id}&interpretation={intprt}"
            else:
                uri = f"type=xyz&url={layer_zxy_url}"
            zmax = tile_json_data.get("maxzoom")
            if zmax:
                uri = f"{uri}&zmax={zmax}"
            raster_dem = QgsRasterLayer(uri, self._name, "wms")

            # Color ramp
            if layer_zxy_url.startswith("https://api.maptiler.com/tiles/terrain-rgb"):
                min_ramp_value, max_ramp_value, color_ramp = utils.load_color_ramp_from_file(TERRAIN_COLOR_RAMP_PATH)
            elif layer_zxy_url.startswith("https://api.maptiler.com/tiles/ocean-rgb"):
                min_ramp_value, max_ramp_value, color_ramp = utils.load_color_ramp_from_file(OCEAN_COLOR_RAMP_PATH)
            fnc = QgsColorRampShader(min_ramp_value, max_ramp_value)
            fnc.setColorRampType(QgsColorRampShader.Interpolated)
            fnc.setClassificationMode(QgsColorRampShader.Continuous)
            fnc.setColorRampItemList(color_ramp)
            lgnd = QgsColorRampLegendNodeSettings()
            lgnd.setUseContinuousLegend(True)
            lgnd.setOrientation(1)
            fnc.setLegendSettings(lgnd)
            # Shader
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fnc)

            # Renderer
            renderer = QgsSingleBandPseudoColorRenderer(raster_dem.dataProvider(), 1, shader)
            raster_dem.setRenderer(renderer)

            resampleFilter = raster_dem.resampleFilter()
            resampleFilter.setZoomedInResampler(QgsBilinearRasterResampler())
            resampleFilter.setZoomedOutResampler(QgsBilinearRasterResampler())

            # add Copyright
            attribution_text = tile_json_data.get("attribution")
            raster_dem.setAttribution(attribution_text)

            # add rlayer to project
            proj = QgsProject().instance()
            proj.addMapLayer(raster_dem, False)
            root = proj.layerTreeRoot()
            root.addLayer(raster_dem)
            dem_layer = root.findLayer(raster_dem)
            dem_layer.setExpanded(False)
        except utils.MapTilerApiException as e:
            self._display_exception(e)


    def _add_terrain_group_to_canvas(self, data_key='terrain-group'):
        """add raster layer from tiles.json"""
        if not self._are_credentials_valid() and data_key == 'terrain-group':
            self._openConfigureDialog()
            return

        try:
            root = QgsProject().instance().layerTreeRoot()
            node_map = root.addGroup(self._name)
            node_map.setExpanded(True)

            sources = converter.get_sources_dict_from_terrain_group(self._dataset[data_key])
            for source_name, source_data in sources.items():
                layer_zxy_url = source_data.get('zxy_url')
                smanager = SettingsManager()
                auth_cfg_id = smanager.get_setting('auth_cfg_id')
                intprt = "maptilerterrain"
                layer_zxy_url = f"{layer_zxy_url.split('?')[0]}?usage={{usage}}"
                uri = f"type=xyz&url={layer_zxy_url}&authcfg={auth_cfg_id}&interpretation={intprt}"
                zmax = source_data.get("maxzoom")
                if zmax:
                    uri = f"{uri}&zmax={zmax}"
                raster_dem = QgsRasterLayer(uri, source_name, "wms")

                # Color ramp
                if layer_zxy_url.startswith("https://api.maptiler.com/tiles/terrain-rgb"):
                    min_ramp_value, max_ramp_value, color_ramp = utils.load_color_ramp_from_file(
                        TERRAIN_COLOR_RAMP_PATH)
                elif layer_zxy_url.startswith("https://api.maptiler.com/tiles/ocean-rgb"):
                    min_ramp_value, max_ramp_value, color_ramp = utils.load_color_ramp_from_file(OCEAN_COLOR_RAMP_PATH)
                fnc = QgsColorRampShader(min_ramp_value, max_ramp_value)
                fnc.setColorRampType(QgsColorRampShader.Interpolated)
                fnc.setClassificationMode(QgsColorRampShader.Continuous)
                fnc.setColorRampItemList(color_ramp)
                lgnd = QgsColorRampLegendNodeSettings()
                lgnd.setUseContinuousLegend(True)
                lgnd.setOrientation(1)
                fnc.setLegendSettings(lgnd)
                # Shader
                shader = QgsRasterShader()
                shader.setRasterShaderFunction(fnc)

                # Renderer
                renderer = QgsSingleBandPseudoColorRenderer(raster_dem.dataProvider(), raster_dem.type(), shader)
                raster_dem.setRenderer(renderer)

                resampleFilter = raster_dem.resampleFilter()
                resampleFilter.setZoomedInResampler(QgsBilinearRasterResampler())
                resampleFilter.setZoomedOutResampler(QgsBilinearRasterResampler())

                # add Copyright
                attribution_text = source_data.get("attribution")
                raster_dem.setAttribution(attribution_text)
                QgsProject.instance().addMapLayer(raster_dem, False)
                node_map.insertLayer(-1, raster_dem)
                layerNode = node_map.findLayer(raster_dem.id())
                layerNode.setExpanded(False)

        except utils.MapTilerApiException as e:
            self._display_exception(e)


    def _add_vector_to_canvas(self, data_key='vector'):
        if data_key == "vector":
            if not self._are_credentials_valid():
                self._openConfigureDialog()
                return

        try:
            attribution_text = self._get_attribution_text(data_key)
            json_url = self._dataset[data_key]
            style_json_data = {}
            style_json_data = converter.get_style_json(json_url)

            root = QgsProject().instance().layerTreeRoot()
            node_map = root.addGroup(self._name)
            node_map.setExpanded(False)

            if style_json_data:
                self._add_vtlayer_from_style_json(style_json_data, node_map, attribution_text)
            else:
                # when tiles.json for vector tile
                tile_json_data = utils.qgis_request_json(json_url)
                self._add_vtlayer_from_tile_json(tile_json_data, node_map, attribution_text)
        except utils.MapTilerApiException as e:
            self._display_exception(e)


    def _add_vtlayer_from_style_json(self,
                                     style_json_data: dict,
                                     target_node: QgsLayerTreeGroup,
                                     attribution_text: str):
        proj = QgsProject().instance()
        smanager =  SettingsManager()
        os.makedirs(SPRITES_PATH, exist_ok=True)
        converter.write_sprite_imgs_from_style_json(style_json_data, SPRITES_PATH)
        auth_cfg_id = smanager.get_setting('auth_cfg_id')

        # Context
        context = QgsMapBoxGlStyleConversionContext()
        context.setTargetUnit(QgsUnitTypes.RenderMillimeters)
        context.setPixelSizeConversionFactor(0.264583)  # 25.4 / 96.0
        # context.setTargetUnit(QgsUnitTypes.RenderPixels)
        # context.setPixelSizeConversionFactor(1)

        # Add other layers from sources
        sources = converter.get_sources_dict_from_style_json(style_json_data)
        ordered_sources = {k: v for k, v in sorted(sources.items(), key=lambda item: item[1]["order"])}
        for source_id, source_data in ordered_sources.items():
            name = source_data.get("name")
            zxy_url = source_data.get("zxy_url")
            if zxy_url.startswith("https://api.maptiler.com"):
                smanager = SettingsManager()
                auth_cfg_id = smanager.get_setting('auth_cfg_id')
                zxy_url = f"{zxy_url.split('?')[0]}?usage={{usage}}"
                uri = f"type=xyz&url={zxy_url}&authcfg={auth_cfg_id}"
            else:
                uri = f"type=xyz&url={zxy_url}"

            zmax = source_data.get("maxzoom")
            if zmax:
                uri = f"{uri}&zmax={zmax}"

            if source_data["type"] == "vector":
                vector = QgsVectorTileLayer(uri, name)
                renderer, labeling, candidate_warnings = converter.convert(source_id, style_json_data, context)
                vector.setLabeling(labeling)
                vector.setRenderer(renderer)
                vector.setAttribution(attribution_text)
                proj.addMapLayer(vector, False)
                target_node.insertLayer(source_data["order"], vector)
            elif source_data["type"] == "raster-dem":
                if source_data.get("name") == "Terrain RGB" and "https://api.maptiler.com/tiles/terrain-rgb" in zxy_url:
                    if utils.is_qgs_early_resampling_enabled():
                        intprt = "maptilerterrain"
                        uri = f"{uri}&interpretation={intprt}"
                        raster = QgsRasterLayer(uri, name, "wms")
                        raster.setResamplingStage(Qgis.RasterResamplingStage.Provider)
                        raster.dataProvider().setZoomedInResamplingMethod(QgsRasterDataProvider.ResamplingMethod.Cubic)
                        raster.dataProvider().setZoomedOutResamplingMethod(QgsRasterDataProvider.ResamplingMethod.Cubic)
                        renderer=QgsHillshadeRenderer(raster.pipe().at(0), 1, 315, 45)
                        renderer.setOpacity(0.2)
                        renderer.setMultiDirectional(True)
                        raster.pipe().set(renderer)
                    else:
                        uri = f"zmin=0&zmax=12&type=xyz" \
                              f"&url={zxy_url.replace('terrain-rgb', 'hillshades')}" \
                              f"&authcfg={auth_cfg_id}"
                        raster = QgsRasterLayer(uri, "hillshades", "wms")
                        renderer = raster.renderer().clone()
                        renderer.setOpacity(0.2)
                        raster.setRenderer(renderer)
                else:
                    raster = QgsRasterLayer(uri, name, "wms")
                    raster.setAttribution(attribution_text)
                proj.addMapLayer(raster, False)
                target_node.insertLayer(source_data["order"], raster)
            elif source_data["type"] == "raster":
                rlayers = converter.get_source_layers_by(source_id, style_json_data)
                for rlayer_json in rlayers:
                    layer_id = rlayer_json.get("id", "NO_NAME")
                    raster = QgsRasterLayer(uri, layer_id, "wms")
                    renderer = raster.renderer()
                    styled_renderer, styled_resampler = converter.get_raster_renderer_resampler(
                        renderer, rlayer_json)
                    # raster.setRenderer(styled_renderer)
                    if styled_renderer is not None:
                        raster.setRenderer(styled_renderer)
                    if styled_resampler == "bilinear" or styled_renderer is None:
                        # change resampler to bilinear
                        qml_str = self._qml_of(raster)
                        bilinear_qml = self._change_resampler_to_bilinear(
                            qml_str)
                        ls = QgsMapLayerStyle(bilinear_qml)
                        ls.writeToLayer(raster)
                    raster.setAttribution(attribution_text)
                    proj.addMapLayer(raster, False)
                    target_node.insertLayer(source_data["order"], raster)

        # Print conversion warnings
        if bool(candidate_warnings):
            warnings = list()
            # Remove duplicates
            candidate_warnings = list(set(candidate_warnings))
            for candidate in candidate_warnings:
                # Removed known warnings
                if "sprite ''" in candidate or "sprite ' '" in candidate:
                    continue
                if candidate.startswith("highway-shield") and "method concat" in candidate:
                    continue
                warnings.append(candidate)
            # Print warnings during conversion
            if bool(warnings):
                widget = iface.messageBar().createMessage("Vector tiles:",
                                                          f"Style {style_json_data.get('name')} "
                                                          f"could not be completely converted")
                button = QPushButton(widget)
                button.setText("Details")

                def show_warnings():
                    warnings_dlg = QgsMessageViewer()
                    warnings_dlg.setTitle("Vector Tiles")
                    html_text = "<p>The following warnings were generated while converting the vector tile style:</p><ul>"
                    for cw in warnings:
                        # Skip known issues

                        html_text += f"<li>{cw}</li>"
                    html_text += "</ul>"
                    warnings_dlg.setMessage(html_text, 1)
                    warnings_dlg.showMessage()

                button.pressed.connect(show_warnings)
                widget.layout().addWidget(button)
                iface.messageBar().pushWidget(widget, Qgis.Warning)

        # Add background layer as last if exists
        bg_renderer = converter.get_bg_renderer(style_json_data)
        if bg_renderer:
            bg_vector = QgsVectorLayer(BG_VECTOR_PATH, "background", "ogr")
            bg_vector.setRenderer(bg_renderer)
            bg_vector.setAttribution(attribution_text)
            proj.addMapLayer(bg_vector, False)
            target_node.insertLayer(-1, bg_vector)

    def _add_vtlayer_from_tile_json(self,
                                    tile_json_data: dict,
                                    target_node: QgsLayerTreeGroup,
                                    attribution_text: str):
        uri = f"type=xyz&url={tile_json_data.get('tiles')[0]}"

        vector = QgsVectorTileLayer(uri, self._name)
        vector.setAttribution(attribution_text)
        QgsProject.instance().addMapLayer(vector, False)
        target_node.insertLayer(-1, vector)

    def _get_attribution_text(self, data_key) -> str:
        attribution_text = ""
        # MapTiler style.json doesn't always have attribution text
        # Get text from tiles.json
        if data_key == 'vector':
            tile_json_url = self._dataset['raster']
            tile_json_data = utils.qgis_request_json(tile_json_url)
            attribution_text = tile_json_data.get("attribution")

        elif data_key == 'custom':
            custom_json_url = self._dataset['custom']
            custom_json_data = utils.qgis_request_json(custom_json_url)

            url_endpoint = custom_json_url.split("?")[0]
            if url_endpoint.endswith("style.json"):
                sources = custom_json_data.get("sources")
                maptiler_attribution = sources.get("maptiler_attribution")
                if maptiler_attribution:
                    attribution = maptiler_attribution.get("attribution", "")
                    attribution_text = str(attribution)
                else:
                    src_attr_set = set()
                    for source_name, source_data in sources.items():
                        tiles_json_url = source_data.get("url")
                        if tiles_json_url is not None:
                            tiles_json_data = utils.qgis_request_json(tiles_json_url)
                            src_attr_set.add(tiles_json_data.get("attribution"))
                    attribution_text = "".join(src_attr_set)
            else:
                attribution_text = custom_json_data.get("attribution", "")

        return attribution_text

    def _add_custom_to_canvas(self):
        json_url = self._dataset['custom']

        try:
            if "https://api.maptiler.com" in json_url:
                if not self._are_credentials_valid():
                    self._openConfigureDialog()
                    return

            if self._is_vector_json(json_url):
                if utils.is_qgs_vectortile_api_enable():
                    self._add_vector_to_canvas(data_key='custom')
                else:
                    widget = iface.messageBar().createMessage(f"'{self.name()} Layer Loading Error',"
                                                              f"'This map\'s JSON is for Vector Tile. Vector Tile feature is not available on this QGIS version.'")
                    iface.messageBar().pushWidget(widget, Qgis.Warning)
            else:
                self._add_raster_to_canvas(data_key='custom')
        except utils.MapTilerApiException as e:
            self._display_exception(e)

    def _display_exception(self, e):
        print(e.message)
        if e.content:
            print(e.content)
            msg = f"Access denied: {e.content}"
            detail_msg = f"{e.message}\n{e.content}"
        else:
            msg = f"Access denied: Check details"
            detail_msg = f"{e.message}"
        widget = iface.messageBar().createMessage(f"{self.name()}", msg)
        button = QPushButton(widget)
        button.setText("Details")

        def show_warnings():
            details_dlg = QgsMessageViewer()
            details_dlg.setTitle("MapTiler API Access denied")

            details_dlg.setMessage(detail_msg, 0)
            details_dlg.showMessage()

        button.pressed.connect(show_warnings)
        widget.layout().addWidget(button)
        iface.messageBar().pushWidget(widget, Qgis.Warning)

    def _edit(self):
        edit_dialog = EditConnectionDialog(self._name)
        edit_dialog.exec_()
        # to reload item's info, once delete item
        self._parent.deleteChildItem(self)
        self._parent.refreshConnections()

    def _delete(self):
        smanager = SettingsManager()
        custommaps = smanager.get_setting('custommaps')
        del custommaps[self._name]
        smanager.store_setting('custommaps', custommaps)
        self.refreshConnections()

    def _remove(self):
        smanager = SettingsManager()
        selectedmaps = smanager.get_setting('selectedmaps')
        selectedmaps.remove(self._name)
        smanager.store_setting('selectedmaps', selectedmaps)
        self.refreshConnections()

    def _open_customize_url(self):
        customize_url = self._dataset.get("customize_url")
        webbrowser.open(customize_url)

    def _openConfigureDialog(self):
        configure_dialog = ConfigureDialog()
        configure_dialog.exec_()
        self.refreshConnections()

    def _qml_of(self, layer: QgsMapLayer):
        ls = QgsMapLayerStyle()
        ls.readFromLayer(layer)
        return ls.xmlData()

    def _change_resampler_to_bilinear(self, qml_str):
        default_resampler_xmltext = '<rasterresampler'
        bilinear_resampler_xmltext = '<rasterresampler zoomedInResampler="bilinear"'
        replaced = qml_str.replace(
            default_resampler_xmltext, bilinear_resampler_xmltext)
        return replaced
