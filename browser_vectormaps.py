import os
import sip

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .configue_dialog import ConfigueDialog
from .new_connection_dialog import VectorNewConnectionDialog
from .edit_connection_dialog import VectorEditConnectionDialog
from .settings_manager import SettingsManager
from . import utils

import json
import requests
from .gl2qgis import converter

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")
DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")
BG_VECTOR_PATH = os.path.join(DATA_PATH, "background.geojson")


def maps_icon_path():
    icon_path = os.path.join(IMGS_PATH, "icon_maps_light.svg")
    if utils.is_in_darkmode():
        icon_path = os.path.join(IMGS_PATH, "icon_maps_dark.svg")
    return icon_path


class VectorCollection(QgsDataCollectionItem):

    STANDARD_DATASET = {
        'Basic': r'https://api.maptiler.com/maps/basic/style.json?key=',
        'Bright': r'https://api.maptiler.com/maps/bright/style.json?key=',
        'Dark Matter': r'https://api.maptiler.com/maps/darkmatter/style.json?key=',
        'Pastel': r'https://api.maptiler.com/maps/pastel/style.json?key=',
        'Positron': r'https://api.maptiler.com/maps/positron/style.json?key=',
        'Satellite Hybrid': r'https://api.maptiler.com/maps/hybrid/style.json?key=',
        'Streets': r'https://api.maptiler.com/maps/streets/style.json?key=',
        'Toner': r'https://api.maptiler.com/maps/toner/style.json?key=',
        'Topo': r'https://api.maptiler.com/maps/topo/style.json?key=',
        'Topographique': r'https://api.maptiler.com/maps/topographique/style.json?key=',
        'Voyager': r'https://api.maptiler.com/maps/voyager/style.json?key='
    }

    LOCAL_JP_DATASET = {
        'MIERUNE Dark': r'https://api.maptiler.com/maps/jp-mierune-dark/style.json?key=',
        'MIERUNE Gray': r'https://api.maptiler.com/maps/jp-mierune-gray/style.json?key=',
        'MIERUNE Streets': r'https://api.maptiler.com/maps/jp-mierune-streets/style.json?key='
    }

    LOCAL_NL_DATASET = {
        'Cartigo Dark': r'https://api.maptiler.com/maps/nl-cartiqo-dark/style.json?key=',
        'Cartigo Light': r'https://api.maptiler.com/maps/nl-cartiqo-light/style.json?key=',
        'Cartigo Topo': r'https://api.maptiler.com/maps/nl-cartiqo-topo/style.json?key='
    }

    LOCAL_UK_DATASET = {
        'OS Open Zoomstack Light': r'https://api.maptiler.com/maps/uk-openzoomstack-light/style.json?key=',
        'OS Open Zoomstack Night': r'https://api.maptiler.com/maps/uk-openzoomstack-night/style.json?key=',
        'OS Open Zoomstack Outdoor': r'https://api.maptiler.com/maps/uk-openzoomstack-outdoor/style.json?key=',
        'OS Open Zoomstack Road': r'https://api.maptiler.com/maps/uk-openzoomstack-road/style.json?key='
    }

    def __init__(self, name):
        QgsDataCollectionItem.__init__(
            self, None, name, "/MapTiler/vector/" + name)

        self.setIcon(QIcon(maps_icon_path()))

        self.ALL_DATASET = dict(**self.STANDARD_DATASET,
                                **self.LOCAL_JP_DATASET,
                                **self.LOCAL_NL_DATASET,
                                **self.LOCAL_UK_DATASET)

        self.LOCAL_DATASET = {"JP": self.LOCAL_JP_DATASET,
                              "NL": self.LOCAL_NL_DATASET,
                              "UK": self.LOCAL_UK_DATASET}

    def createChildren(self):
        items = []

        for key in self.ALL_DATASET:
            # skip adding if it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if not key in recentmaps:
                continue

            # add space to put items above
            item = VectorMapItem(self, ' ' + key, self.ALL_DATASET[key])
            sip.transferto(item, self)
            items.append(item)

        more_collection = VectorMoreCollection(
            self.STANDARD_DATASET, self.LOCAL_DATASET)
        sip.transferto(more_collection, self)
        items.append(more_collection)

        return items


class VectorMoreCollection(QgsDataCollectionItem):
    def __init__(self, dataset, local_dataset):
        QgsDataCollectionItem.__init__(
            self, None, "more...", "/MapTiler/vector/more")

        self.setIcon(QIcon(maps_icon_path()))
        self._dataset = dataset
        self._local_dataset = local_dataset

    def createChildren(self):
        items = []
        for key in self._dataset:
            # add item only when it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if key in recentmaps:
                continue

            # add space to put items above
            item = VectorMapItem(self, ' ' + key, self._dataset[key])
            sip.transferto(item, self)
            items.append(item)

        for dataset_name, dataset in self._local_dataset.items():
            local_collection = VectorLocalCollection(dataset, dataset_name)
            sip.transferto(local_collection, self)
            items.append(local_collection)

        return items


class VectorLocalCollection(QgsDataCollectionItem):
    def __init__(self, local_dataset, dataset_name):
        QgsDataCollectionItem.__init__(
            self, None, dataset_name, f"/MapTiler/vector/more/{dataset_name}")

        self.setIcon(QIcon(maps_icon_path()))
        self._local_dataset = local_dataset

    def createChildren(self):
        items = []
        for key in self._local_dataset:
            # add item only when it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if key in recentmaps:
                continue

            # add space to put items above
            item = VectorMapItem(self, key, self._local_dataset[key])
            sip.transferto(item, self)
            items.append(item)

        return items


class VectorUserCollection(QgsDataCollectionItem):
    def __init__(self, name="User Maps"):
        QgsDataCollectionItem.__init__(
            self, None, name, "/MapTiler/vector/user")

        self.setIcon(QIcon(maps_icon_path()))

    def createChildren(self):
        items = []

        smanager = SettingsManager()
        vectormaps = smanager.get_setting('vectormaps')
        for key in vectormaps:
            item = VectorMapItem(self, key, vectormaps[key], editable=True)
            sip.transferto(item, self)
            items.append(item)

        return items

    def actions(self, parent):
        actions = []
        new = QAction(QIcon(), 'Add new connection', parent)
        new.triggered.connect(self.openDialog)
        actions.append(new)

        return actions

    def openDialog(self):
        new_dialog = VectorNewConnectionDialog()
        new_dialog.exec_()
        # reload browser
        self.refreshConnections()


class VectorMapItem(QgsDataItem):
    def __init__(self, parent, name, url, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom, parent,
                             name, "/MapTiler/vector/" + parent.name() + '/' + name)
        self.populate()  # set to treat Item as not-folder-like

        self._parent = parent
        self._name = name
        self._url = url
        self._editable = editable

    def acceptDrop(self):
        return False

    def handleDoubleClick(self):
        self._add_to_canvas()
        return True

    def actions(self, parent):
        actions = []

        add_action = QAction(QIcon(), 'Add to Canvas', parent)
        add_action.triggered.connect(self._add_to_canvas)
        actions.append(add_action)

        if self._editable:
            edit_action = QAction(QIcon(), 'Edit', parent)
            edit_action.triggered.connect(self._edit)
            actions.append(edit_action)

            remove_action = QAction(QIcon(), 'Remove', parent)
            remove_action.triggered.connect(self._remove)
            actions.append(remove_action)

        return actions

    def _add_to_canvas(self):
        # apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return True

        style_json_url = self._url + apikey
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
            sources = converter.get_sources_dict_from_style_json(style_json_data)
            for source_name, source_data in sources.items():
                url = "type=xyz&url=" + source_data["zxy_url"]

                if source_data["type"] == "vector":
                    vector = QgsVectorTileLayer(url, source_name)
                    renderer, labeling = converter.get_renderer_labeling(source_name, style_json_data)
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
            url = "type=xyz&url=" + self._url + apikey
            vector = QgsVectorTileLayer(url, self._name)
            proj.addMapLayer(vector)

        if not self._editable:
            self._update_recentmaps()

    def _edit(self):
        edit_dialog = VectorEditConnectionDialog(self._name)
        edit_dialog.exec_()
        # to reload item's info, once delete item
        self._parent.deleteChildItem(self)
        self._parent.refreshConnections()

    def _remove(self):
        smanager = SettingsManager()
        vectormaps = smanager.get_setting('vectormaps')
        del vectormaps[self._name]
        smanager.store_setting('vectormaps', vectormaps)
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
        self._parent.parent().refreshConnections()
        self._parent.refreshConnections()
