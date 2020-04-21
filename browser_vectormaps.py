import os
import sip

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsDataCollectionItem,
    QgsProject,
    QgsDataItem,
    QgsDataCollectionItem,
    QgsVectorTileLayer
)

from .new_connection_dialog import VectorNewConnectionDialog
from .settings_manager import SettingsManager

ICON_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")

class VectorCollection(QgsDataCollectionItem):
    def __init__(self, name, dataset, user_editable=False):
        QgsDataCollectionItem.__init__(self, None, name, "/MapTiler/vector/" + name)
        self.setIcon(QIcon(os.path.join(ICON_PATH, "vector_collection_icon.png")))
        self._dataset = dataset
        self._user_editable = user_editable

    def createChildren(self):
        items = []
        for key in self._dataset:
            item = VectorMapItem(self, key, self._dataset[key])
            sip.transferto(item, self)
            items.append(item)
        
        if self._user_editable:
            smanager = SettingsManager()
            vectormaps = smanager.get_setting('vectormaps')
            for key in vectormaps:
                item = VectorMapItem(self, key, vectormaps[key], editable=True)
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
        new_dialog = VectorNewConnectionDialog()
        new_dialog.exec_()
        #reload browser
        self.parent().refreshConnections()


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