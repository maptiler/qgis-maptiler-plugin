import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsRasterLayer,
    QgsDataItem,
    QgsDataCollectionItem,
    QgsDataItemProvider,
    QgsDataProvider
)

from .new_connect_dialog import NewConnectDialog
from .settings_manager import SettingsManager

class RasterCollection(QgsDataCollectionItem):
    def __init__(self, name, dataset, user_editable=False):
        QgsDataCollectionItem.__init__(self, None, name, "/MapTiler/raster/" + name)
        self._dataset = dataset
        self._user_editable = user_editable

    def createChildren(self):
        items = []
        for key in self._dataset:
            item = RasterMapItem(self, key, self._dataset[key])
            sip.transferto(item, self)
            items.append(item)
        
        if self._user_editable:
            sm = SettingsManager()
            rastermaps = sm.get_setting('rastermaps')
            for key in rastermaps:
                item = RasterMapItem(self, key, rastermaps[key], editable=True)
                sip.transferto(item, self)
                items.append(item)

        return items

    def actions(self, parent):
        actions = []
        if self._user_editable:
            new = QAction(QIcon(), 'Add new connection', parent)
            new.triggered.connect(self.openDialog)
            actions.append(new)

        return actions

    def openDialog(self):
        new_connect_dialog = NewConnectDialog()
        new_connect_dialog.show()
        new_connect_dialog.exec_()
        #reload browser
        self.parent().refreshConnections()

class RasterMapItem(QgsDataItem):
    def __init__(self, parent, name, url, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom, parent, name, "/MapTiler/raster/" + parent.name() + '/' + name)
        self._name = name
        self._url = url
        self._editable = editable

    def acceptDrop(self):
        return False

    def handleDoubleClick(self):
        proj = QgsProject().instance()
        url = self.reshape_url(self._url)
        raster = QgsRasterLayer(url, self._name, "wms")
        proj.addMapLayer(raster)
        return True

    def reshape_url(self, url):
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        
        #when URL includes APIKEY
        if url.endswith(apikey):
            return "type=xyz&url=" + url

        return "type=xyz&url=" + url + apikey

    def actions(self, parent):
        actions = []
        if self._editable:
            new = QAction(QIcon(), 'Remove', parent)
            new.triggered.connect(self._remove)
            actions.append(new)
        
        return actions

    def _remove(self):
        smanager = SettingsManager()
        rastermaps = smanager.get_setting('rastermaps')
        del rastermaps[self._name]
        smanager.store_setting('rastermaps', rastermaps)
        self.parent().refreshConnections()