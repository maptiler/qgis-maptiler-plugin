import os
import sip
import json
import requests
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
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
        self._add_raster_to_canvas()
        return True

    def actions(self, parent):
        actions = []

        # judge vtile is available or not
        # e.g. QGIS3.10.4 -> 31004
        qgis_version_str = str(Qgis.QGIS_VERSION_INT)
        minor_ver = int(qgis_version_str[1:3])

        smanager = SettingsManager()
        isVectorEnabled = int(smanager.get_setting('isVectorEnabled'))

        # Vector Enable
        if minor_ver >= 13 and self._dataset['vector']:
            add_vector_action = QAction(QIcon(), 'Add as Vector', parent)
            add_vector_action.triggered.connect(self._add_vector_to_canvas)
            actions.append(add_vector_action)

        if self._dataset['raster']:
            add_raster_action = QAction(QIcon(), 'Add as Raster', parent)
            add_raster_action.triggered.connect(self._add_raster_to_canvas)
            actions.append(add_raster_action)

        if self._editable:
            edit_action = QAction(QIcon(), 'Edit', parent)
            edit_action.triggered.connect(self._edit)
            actions.append(edit_action)

            delete_action = QAction(QIcon(), 'Delete', parent)
            delete_action.triggered.connect(self._delete)
            actions.append(delete_action)
        else:
            remove_action = QAction(QIcon(), 'Remove', parent)
            remove_action.triggered.connect(self._remove)
            actions.append(remove_action)

        return actions

    def _add_raster_to_canvas(self):
        # apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return True

        proj = QgsProject().instance()
        tile_json_url = self._dataset['raster'] + apikey
        tile_json_data = json.loads(requests.get(tile_json_url).text)
        layer_zxy_url = tile_json_data.get("tiles")[0]
        url = "type=xyz&url=" + layer_zxy_url
        raster = QgsRasterLayer(url, self._name, "wms")

        # change resampler to bilinear
        qml_str = self._qml_of(raster)
        bilinear_qml = self._change_resampler_of(qml_str)
        ls = QgsMapLayerStyle(bilinear_qml)
        ls.writeToLayer(raster)

        proj.addMapLayer(raster)

        if not self._editable:
            self._update_recentmaps()

    def _add_vector_to_canvas(self):
        # apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return True

        style_json_url = self._dataset['vector'] + apikey
        style_json_data = {}
        try:
            style_json_data = converter.get_style_json(style_json_url)
        except Exception as e:
            print(e)

        proj = QgsProject().instance()
        root = proj.layerTreeRoot()
        node_map = root.addGroup(self._name)
        node_map.setExpanded(False)

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
                    proj.addMapLayer(vector, False)
                    node_map.addLayer(vector)
                elif source_data["type"] == "raster-dem":
                    # TODO solve layer style
                    raster = QgsRasterLayer(url, source_name, "wms")
                    proj.addMapLayer(raster, False)
                    node_map.addLayer(raster)
                elif source_data["type"] == "raster":
                    # TODO solve layer style
                    raster = QgsRasterLayer(url, source_name, "wms")
                    proj.addMapLayer(raster, False)
                    node_map.addLayer(raster)
            # Add background layer as last if exists
            bg_renderer = converter.get_bg_renderer(style_json_data)
            if bg_renderer:
                bg_vector = QgsVectorLayer(BG_VECTOR_PATH, "background", "ogr")
                bg_vector.setRenderer(bg_renderer)
                proj.addMapLayer(bg_vector, False)
                node_map.insertLayer(-1, bg_vector)
        else:
            url = "type=xyz&url=" + self._dataset['vector'] + apikey
            vector = QgsVectorTileLayer(url, self._name)
            proj.addMapLayer(vector)

        if not self._editable:
            self._update_recentmaps()

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
        self._parent.refreshConnections()

    def _remove(self):
        smanager = SettingsManager()
        selectedmaps = smanager.get_setting('selectedmaps')
        selectedmaps.remove(self._name)
        smanager.store_setting('selectedmaps', selectedmaps)
        self._parent.refreshConnections()

    def _openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()
        self._parent.parent().refreshConnections()
        self._parent.refreshConnections()

    def _update_recentmaps(self):
        smanager = SettingsManager()
        recentmaps = smanager.get_setting('recentmaps')

        # clean item name spacer
        key = self._name
        if key[0] == ' ':
            key = key[1:]

        if not key in recentmaps:
            recentmaps.append(key)

        MAX_RECENT_MAPS = 3
        if len(recentmaps) > MAX_RECENT_MAPS:
            recentmaps.pop(0)

        smanager.store_setting('recentmaps', recentmaps)
        self._parent.refreshConnections()

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
