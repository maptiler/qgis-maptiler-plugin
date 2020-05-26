import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import *

from .browser_mapitem import MapDataItem
from .new_connection_dialog import NewConnectionDialog
from .configue_dialog import ConfigueDialog
from .settings_manager import SettingsManager
from . import mapdatasets
from . import utils

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
                        **self.LOCAL_UK_DATASET)

        for key in DATASETS:
            md_item = MapDataItem(self, key, DATASETS[key])
            sip.transferto(md_item, self)
            children.append(md_item)

        config_action = OpenConfigItem(self)
        sip.transferto(config_action, self)
        children.append(config_action)

        return children

    def actions(self, parent):
        actions = []

        new_action = QAction(QIcon(), 'Add a new map...', parent)
        new_action.triggered.connect(self.open_new_dialog)
        actions.append(new_action)

        return actions

    def open_new_dialog(self):
        new_dialog = NewConnectionDialog()
        new_dialog.exec_()
        self.parent().refreshConnections()


class OpenConfigItem(QgsDataItem):
    def __init__(self, parent):
        QgsDataItem.__init__(self, QgsDataItem.Custom,
                             parent, "Account", "/MapTiler/config")

        icon_path = os.path.join(IMGS_PATH, "icon_account_light.svg")
        if utils.is_in_darkmode():
            icon_path = os.path.join(IMGS_PATH, "icon_account_dark.svg")
        self.setIcon(QIcon(icon_path))
        self.populate()

    def handleDoubleClick(self):
        self.open_configue_dialog()
        return True

    def actions(self, parent):
        actions = []

        config_action = QAction(QIcon(), 'Open', parent)
        config_action.triggered.connect(self.open_configue_dialog)
        actions.append(config_action)

        return actions

    def open_configue_dialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()
        self.parent().refreshConnections()
