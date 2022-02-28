import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .browser_mapitem import MapDataItem
from .add_connection_dialog import AddConnectionDialog
from .configure_dialog import ConfigureDialog
from .settings_manager import SettingsManager
from . import mapdatasets

IMGS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")


class DataItemProvider(QgsDataItemProvider):
    def __init__(self):
        QgsDataItemProvider.__init__(self)

    def name(self):
        return "MapTilerProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def createDataItem(self, path, parentItem):
        root = RootCollection()
        sip.transferto(root, None)
        return root


class RootCollection(QgsDataCollectionItem):
    STANDARD_DATASET = mapdatasets.STANDARD_DATASET
    LOCAL_JP_DATASET = mapdatasets.LOCAL_JP_DATASET
    LOCAL_NL_DATASET = mapdatasets.LOCAL_NL_DATASET
    LOCAL_UK_DATASET = mapdatasets.LOCAL_UK_DATASET

    def __init__(self):
        QgsDataCollectionItem.__init__(self, None, "MapTiler", "/MapTiler")

        self.setIcon(QIcon(os.path.join(IMGS_PATH, "icon_maptiler.svg")))

    def createChildren(self):
        children = []

        DATASETS = dict(**self.STANDARD_DATASET,
                        **self.LOCAL_JP_DATASET,
                        **self.LOCAL_NL_DATASET,
                        **self.LOCAL_UK_DATASET,
                        )
        smanager = SettingsManager()
        selectedmaps = smanager.get_setting('selectedmaps')

        for key in DATASETS:
            if not key in selectedmaps:
                continue
            md_item = MapDataItem(self, key, DATASETS[key])
            sip.transferto(md_item, self)
            children.append(md_item)

        custommaps = smanager.get_setting('custommaps')
        for key in custommaps:
            md_item = MapDataItem(self, key,
                                  custommaps[key], editable=True)
            sip.transferto(md_item, self)
            children.append(md_item)

        return children

    def actions(self, parent):
        actions = []

        add_action = QAction(QIcon(), 'Add a new map...', parent)
        add_action.triggered.connect(self._open_add_dialog)
        actions.append(add_action)

        configure_action = QAction(QIcon(), 'Account...', parent)
        configure_action.triggered.connect(self._open_configure_dialog)
        actions.append(configure_action)

        return actions

    def _open_add_dialog(self):
        add_dialog = AddConnectionDialog()
        add_dialog.exec_()
        self.refreshConnections()

    def _open_configure_dialog(self):
        configure_dialog = ConfigureDialog()
        configure_dialog.exec_()
        self.refreshConnections()
