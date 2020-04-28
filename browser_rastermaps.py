#RasterCollection
#RasterMoreCollection
#RasterUserCollection
#RasterMapItem

#RasterCollection has following structure
#|-Recent used 3 maps : RasterMapItem
#|-more... : RasterMoreCollection
###|-standard maps : RasterMapItem
###|-local maps : RasterMapItem

import os
import sip

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .configue_dialog import ConfigueDialog
from .new_connection_dialog import RasterNewConnectionDialog
from .edit_connection_dialog import RasterEditConnectionDialog
from .settings_manager import SettingsManager
from . import utils

ICON_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")


class RasterCollection(QgsDataCollectionItem):

    STANDARD_DATASET = {
        'Basic':r'https://api.maptiler.com/maps/basic/{z}/{x}/{y}.png?key=',
        'Bright':r'https://api.maptiler.com/maps/bright/{z}/{x}/{y}.png?key=',
        'Dark Matter':r'https://api.maptiler.com/maps/darkmatter/{z}/{x}/{y}.png?key=',
        'Pastel':r'https://api.maptiler.com/maps/pastel/{z}/{x}/{y}.png?key=',
        'Positron':r'https://api.maptiler.com/maps/positron/{z}/{x}/{y}.png?key=',
        'Hybrid':r'https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=',
        'Streets':r'https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=',
        'Topo':r'https://api.maptiler.com/maps/topo/{z}/{x}/{y}.png?key=',
        'Topographique':r'https://api.maptiler.com/maps/topographique/{z}/{x}/{y}.png?key=',
        'Voyager':r'https://api.maptiler.com/maps/voyager/{z}/{x}/{y}.png?key='
    }

    LOCAL_JP_DATASET = {
        'JP MIERUNE Streets':r'https://api.maptiler.com/maps/jp-mierune-streets/{z}/{x}/{y}.png?key=',
        'JP MIERUNE Dark':r'https://api.maptiler.com/maps/jp-mierune-dark/{z}/{x}/{y}.png?key=',
        'JP MIERUNE Gray':r'https://api.maptiler.com/maps/jp-mierune-gray/{z}/{x}/{y}.png?key='
    }

    LOCAL_NL_DATASET = {
        'NL Cartiqo Dark':r'https://api.maptiler.com/maps/nl-cartiqo-dark/{z}/{x}/{y}.png?key=',
        'NL Cartiqo Light':r'https://api.maptiler.com/maps/nl-cartiqo-light/{z}/{x}/{y}.png?key=',
        'NL Cartiqo Topo':r'https://api.maptiler.com/maps/nl-cartiqo-topo/{z}/{x}/{y}.png?key='
    }

    LOCAL_UK_DATASET = {
        'UK OS Open Zoomstack Light':r'https://api.maptiler.com/maps/uk-openzoomstack-light/{z}/{x}/{y}.png?key=',
        'UK OS Open Zoomstack Night':r'https://api.maptiler.com/maps/uk-openzoomstack-night/{z}/{x}/{y}.png?key=',
        'UK OS Open Zoomstack Outdoor':r'https://api.maptiler.com/maps/uk-openzoomstack-outdoor/{z}/{x}/{y}.png?key=',
        'UK OS Open Zoomstack Road':r'https://api.maptiler.com/maps/uk-openzoomstack-road/{z}/{x}/{y}.png?key='
    }

    def __init__(self, name):
        QgsDataCollectionItem.__init__(self, None, name, "/MapTiler/raster/" + name)
        self.setIcon(QIcon(os.path.join(ICON_PATH, "raster_collection_icon.png")))

        self.ALL_DATASET = dict(**self.STANDARD_DATASET,
                                **self.LOCAL_JP_DATASET,
                                **self.LOCAL_NL_DATASET,
                                **self.LOCAL_UK_DATASET)

        self.LOCAL_DATASET = dict(**self.LOCAL_JP_DATASET,
                                **self.LOCAL_NL_DATASET,
                                **self.LOCAL_UK_DATASET)
    
    def createChildren(self):
        items = []
        
        for key in self.ALL_DATASET:
            #skip adding if it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if not key in recentmaps:
                continue
            
            #add space to put items above
            item = RasterMapItem(self, ' ' + key, self.ALL_DATASET[key])
            sip.transferto(item, self)
            items.append(item)

        more_collection = RasterMoreCollection(self.STANDARD_DATASET, self.LOCAL_DATASET)
        sip.transferto(more_collection, self)
        items.append(more_collection)

        return items


class RasterMoreCollection(QgsDataCollectionItem):
    def __init__(self, dataset, local_dataset):
        QgsDataCollectionItem.__init__(self, None, "more...", "/MapTiler/raster/more")
        self.setIcon(QIcon(os.path.join(ICON_PATH, "raster_more_collection_icon.png")))
        self._dataset = dataset
        self._local_dataset = local_dataset

    def createChildren(self):
        items = []
        for key in self._dataset:
            #add item only when it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if key in recentmaps:
                continue
            
            #add space to put items above
            item = RasterMapItem(self, ' ' + key, self._dataset[key])
            sip.transferto(item, self)
            items.append(item)

        for key in self._local_dataset:
            #add item only when it is not recently used
            smanager = SettingsManager()
            recentmaps = smanager.get_setting('recentmaps')
            if key in recentmaps:
                continue
            
            #add space to put items above
            item = RasterMapItem(self, key, self._local_dataset[key])
            sip.transferto(item, self)
            items.append(item)

        return items


class RasterUserCollection(QgsDataCollectionItem):
    def __init__(self, name="User Maps"):
        QgsDataCollectionItem.__init__(self, None, name, "/MapTiler/raster/user")
        self.setIcon(QIcon(os.path.join(ICON_PATH, "raster_user_collection_icon.png")))

    def createChildren(self):
        items = []

        smanager = SettingsManager()
        rastermaps = smanager.get_setting('rastermaps')
        for key in rastermaps:
            item = RasterMapItem(self, key, rastermaps[key], editable=True)
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
        new_dialog = RasterNewConnectionDialog()
        new_dialog.exec_()
        #reload browser
        self.refreshConnections()


class RasterMapItem(QgsDataItem):
    def __init__(self, parent, name, url, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom, parent, name, "/MapTiler/raster/" + parent.name() + '/' + name)
        self.populate() #set to treat Item as not-folder-like

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
        #apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return True
        
        proj = QgsProject().instance()
        url = "type=xyz&url=" + self._url + apikey
        raster = QgsRasterLayer(url, self._name, "wms")

        #change resampler to bilinear
        qml_str = self._qml_of(raster)
        bilinear_qml = self._change_resampler_of(qml_str)
        ls = QgsMapLayerStyle(bilinear_qml)
        ls.writeToLayer(raster)

        proj.addMapLayer(raster)

        if not self._editable:
            self._update_recentmaps()

    def _edit(self):
        edit_dialog = RasterEditConnectionDialog(self._name)
        edit_dialog.exec_()
        #to reload item's info, once delete item
        self._parent.deleteChildItem(self)
        self._parent.refreshConnections()

    def _remove(self):
        smanager = SettingsManager()
        rastermaps = smanager.get_setting('rastermaps')
        del rastermaps[self._name]
        smanager.store_setting('rastermaps', rastermaps)
        self._parent.refreshConnections()

    def _openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()
        self._parent.parent().refreshConnections()
        self._parent.refreshConnections()

    def _update_recentmaps(self):
        smanager = SettingsManager()
        recentmaps = smanager.get_setting('recentmaps')

        #clean item name spacer
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

    def _qml_of(self, layer: QgsMapLayer):
        ls = QgsMapLayerStyle()
        ls.readFromLayer(layer)
        return ls.xmlData()

    def _change_resampler_of(self, qml_str):
        default_resampler_xmltext = '<rasterresampler'
        bilinear_resampler_xmltext = '<rasterresampler zoomedInResampler="bilinear"'
        replaced = qml_str.replace(default_resampler_xmltext, bilinear_resampler_xmltext)
        return replaced