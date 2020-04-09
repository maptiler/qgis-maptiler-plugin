import os
import sip
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsDataCollectionItem,
    #QgsProject,
    #QgsDataItem,
    #QgsDataCollectionItem,
    #QgsVectorTileLayer
)

from .settings_manager import SettingsManager

class VectorCollection(QgsDataCollectionItem):
    def __init__(self):
        QgsDataCollectionItem.__init__(self, None, "Vector", "/MapTiler/vector")

'''
class VectorMapItem(QgsDataItem):
    def __init__(self, parent, name, url, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom, parent, name, "/MapTiler/vector/" + parent.name() + '/' + name)
        self._name = name
        self._url = url
        self._editable = editable

    def acceptDrop(self):
        return False

    def handleDoubleClick(self):
        proj = QgsProject().instance()
        url = self.reshape_url(self._url)
        vtlayer = QgsVectorTileLayer(url, self._name)
        proj.addMapLayer(vtlayer)
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
        vectormaps = smanager.get_setting('vectormaps')
        del vectormaps[self._name]
        smanager.store_setting('vectormaps', vectormaps)
        self.parent().refreshConnections()
'''