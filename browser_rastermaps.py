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

from .configue_dialog import ConfigueDialog
from .new_connection_dialog import RasterNewConnectionDialog
from .edit_connection_dialog import RasterEditConnectionDialog
from .settings_manager import SettingsManager
from . import utils

ICON_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")

class RasterCollection(QgsDataCollectionItem):
    def __init__(self, name, dataset, user_editable=False):
        QgsDataCollectionItem.__init__(self, None, name, "/MapTiler/raster/" + name)
        self.setIcon(QIcon(os.path.join(ICON_PATH, "raster_collection_icon.png")))
        self._dataset = dataset
        self._user_editable = user_editable

    def createChildren(self):
        items = []
        for key in self._dataset:
            item = RasterMapItem(self, key, self._dataset[key])
            sip.transferto(item, self)
            items.append(item)
        
        if self._user_editable:
            smanager = SettingsManager()
            rastermaps = smanager.get_setting('rastermaps')
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
        new_dialog = RasterNewConnectionDialog()
        new_dialog.exec_()
        #reload browser
        self.parent().refreshConnections()

class RasterMapItem(QgsDataItem):
    def __init__(self, parent, name, url, editable=False):
        QgsDataItem.__init__(self, QgsDataItem.Custom, parent, name, "/MapTiler/raster/" + parent.name() + '/' + name)
        self.populate() #set this item as not-folder-like

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
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')

        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return True
        
        proj = QgsProject().instance()
        url = "type=xyz&url=" + self._url + apikey
        raster = QgsRasterLayer(url, self._name, "wms")
        proj.addMapLayer(raster)

    def _edit(self):
        edit_dialog = RasterEditConnectionDialog(self._name)
        edit_dialog.exec_()
        self.parent().refreshConnections()

    def _remove(self):
        smanager = SettingsManager()
        rastermaps = smanager.get_setting('rastermaps')
        del rastermaps[self._name]
        smanager.store_setting('rastermaps', rastermaps)
        self.parent().refreshConnections()

    def _openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()