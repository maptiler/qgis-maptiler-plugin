import os
import sip
import json
import requests
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import *

from .gl2qgis import converter

from .configue_dialog import ConfigueDialog
from .edit_connection_dialog import EditConnectionDialog
from .settings_manager import SettingsManager
from . import utils

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")
DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
BG_VECTOR_PATH = os.path.join(DATA_PATH, "background.geojson")


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
        elif utils.is_qgs_vectortile_api_enable() and prefervector:
            self._add_vector_to_canvas()
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

        return actions

    def _is_apikey_valid(self):
        # apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')

        if not utils.validate_key(apikey):
            QMessageBox.warning(
                None, 'Access Error', '\nAccess error occurred. \nPlease Confirm your API-key.')
            return False

        return True

    def _is_vector_json(self, json_url: str) -> bool:
        url_endpoint = json_url.split("?")[0]
        if url_endpoint.endswith("style.json"):
            return True
        # tiles.json
        else:
            json_data = json.loads(requests.get(json_url).text)
            data_format = json_data['format']
            return data_format == 'pbf'

    def _add_raster_to_canvas(self, data_key='raster'):
        if not self._is_apikey_valid():
            self._openConfigueDialog()
            return

        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')

        proj = QgsProject().instance()
        tile_json_url = self._dataset[data_key] + apikey
        tile_json_data = json.loads(requests.get(tile_json_url).text)
        layer_zxy_url = tile_json_data.get("tiles")[0]
        if layer_zxy_url.startswith("https://api.maptiler.com/maps"):
            if ".png" in layer_zxy_url:
                url_split = layer_zxy_url.split(".png")
                url = "type=xyz&url=" + url_split[0] + "@2x.png" + url_split[1]
            elif ".jpg" in layer_zxy_url:
                url_split = layer_zxy_url.split(".jpg")
                url = "type=xyz&url=" + url_split[0] + "@2x.jpg" + url_split[1]
            elif ".webp" in layer_zxy_url:
                url_split = layer_zxy_url.split(".webp")
                url = "type=xyz&url=" + \
                    url_split[0] + "@2x.webp" + url_split[1]
        else:
            url = "type=xyz&url=" + layer_zxy_url
        raster = QgsRasterLayer(url, self._name, "wms")

        # change resampler to bilinear
        qml_str = self._qml_of(raster)
        bilinear_qml = self._change_resampler_of(qml_str)
        ls = QgsMapLayerStyle(bilinear_qml)
        ls.writeToLayer(raster)

        # add Copyright
        attribution_text = tile_json_data.get("attribution")
        raster.setAttribution(attribution_text)

        proj.addMapLayer(raster)

    def _add_vector_to_canvas(self, data_key='vector'):
        if not self._is_apikey_valid():
            self._openConfigueDialog()
            return

        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')

        attribution_text = ''
        # when not user custom map
        if data_key == 'vector':
            tile_json_url = self._dataset['raster'] + apikey
            tile_json_data = json.loads(requests.get(tile_json_url).text)
            attribution_text = tile_json_data.get("attribution")
        elif data_key == 'custom':
            custom_json_url = self._dataset['custom'] + apikey
            url_endpoint = custom_json_url.split("?")[0]
            if url_endpoint.endswith(".pbf"):
                # raw pbf has no attribution data
                pass
            # tiles or style json
            else:
                custom_json_data = json.loads(
                    requests.get(custom_json_url).text)
                if url_endpoint.endswith("style.json"):
                    attribution_text = custom_json_data.get("sources").get(
                        "maptiler_attribution").get("attribution")
                elif url_endpoint.endswith("tiles.json"):
                    attribution_text = custom_json_data.get("attribution", "")

        json_url = self._dataset[data_key] + apikey
        style_json_data = {}
        try:
            style_json_data = converter.get_style_json(json_url)
        except Exception as e:
            print(e)
        proj = QgsProject().instance()
        root = proj.layerTreeRoot()
        node_map = root.addGroup(self._name)
        node_map.setExpanded(False)

        # style_json_data can be None only when user custom maps.
        if style_json_data:
            # Add other layers from sources
            sources = converter.get_sources_dict_from_style_json(
                style_json_data)
            for source_name, source_data in sources.items():
                url = "type=xyz&url=" + source_data["zxy_url"]

                if source_data["type"] == "vector":
                    vector = QgsVectorTileLayer(url, source_name)
                    renderer, labeling = converter.get_renderer_labeling(
                        source_name, style_json_data)
                    vector.setLabeling(labeling)
                    vector.setRenderer(renderer)
                    vector.setAttribution(attribution_text)
                    proj.addMapLayer(vector, False)
                    node_map.addLayer(vector)
                elif source_data["type"] == "raster-dem":
                    # TODO solve layer style
                    raster = QgsRasterLayer(url, source_name, "wms")
                    raster.setAttribution(attribution_text)
                    proj.addMapLayer(raster, False)
                    node_map.addLayer(raster)
                elif source_data["type"] == "raster":
                    # TODO solve layer style
                    raster = QgsRasterLayer(url, source_name, "wms")
                    raster.setAttribution(attribution_text)
                    proj.addMapLayer(raster, False)
                    node_map.addLayer(raster)
            # Add background layer as last if exists
            bg_renderer = converter.get_bg_renderer(style_json_data)
            if bg_renderer:
                bg_vector = QgsVectorLayer(BG_VECTOR_PATH, "background", "ogr")
                bg_vector.setRenderer(bg_renderer)
                bg_vector.setAttribution(attribution_text)
                proj.addMapLayer(bg_vector, False)
                node_map.insertLayer(-1, bg_vector)

        else:
            # this case can run only when user custom map
            # when custom map url is loaded as vectortile and not valid style.json
            # e.g. .pbf or tiles.json as vectortile
            url_endpoint = json_url.split("?")[0]
            url = ''
            if url_endpoint.endswith("tiles.json"):
                tile_json_data = json.loads(requests.get(json_url).text)
                url = "type=xyz&url=" + tile_json_data.get("tiles")[0]
            # e.g. pbf
            else:
                url = "type=xyz&url=" + self._dataset[data_key] + apikey
            vector = QgsVectorTileLayer(url, self._name)
            vector.setAttribution(attribution_text)
            proj.addMapLayer(vector, False)
            node_map.insertLayer(-1, vector)

    def _add_custom_to_canvas(self):
        if not self._is_apikey_valid():
            self._openConfigueDialog()
            return

        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')

        json_url = self._dataset['custom'] + apikey
        if self._is_vector_json(json_url):
            if utils.is_qgs_vectortile_api_enable():
                self._add_vector_to_canvas(data_key='custom')
            else:
                QMessageBox.warning(None, 'Layer Loading Error',
                                    'This map\'s JSON is for Vector Tile. Vector Tile feature is not available on this QGIS version.')
                return
        else:
            self._add_raster_to_canvas(data_key='custom')

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

    def _openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()
        self.refreshConnections()

    def _qml_of(self, layer: QgsMapLayer):
        ls = QgsMapLayerStyle()
        ls.readFromLayer(layer)
        return ls.xmlData()

    def _change_resampler_of(self, qml_str):
        default_resampler_xmltext = '<rasterresampler'
        bilinear_resampler_xmltext = '<rasterresampler zoomedInResampler="bilinear"'
        replaced = qml_str.replace(
            default_resampler_xmltext, bilinear_resampler_xmltext)
        return replaced
