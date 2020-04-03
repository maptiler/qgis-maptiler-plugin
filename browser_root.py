import os
import sip
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsDataCollectionItem,
    QgsDataItemProvider,
    QgsDataProvider
)

from .browser_rastermaps import RasterCollection
from .browser_vectormaps import VectorCollection

from .configue_dialog import ConfigueDialog

ICON_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "imgs")

class DataItemProvider(QgsDataItemProvider):
    def __init__(self):
        QgsDataItemProvider.__init__(self)

    def name(self):
        return "MapTilerProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def actions(self, parent):
        action_configure = QAction("Configure", parent)
        actions = [action_configure]
        return actions

    def createDataItem(self, path, parentItem):
        root = RootCollection()
        sip.transferto(root, None)
        return root

class RootCollection(QgsDataCollectionItem):
    def __init__(self):
        QgsDataCollectionItem.__init__(self, None, "MapTiler", "/MapTiler")
        self.setIcon(QIcon(os.path.join(ICON_PATH, "maptiler_icon.svg")))
    
    def createChildren(self):
        #init default dataset
        standard_dataset = {
            'Basic':r'https://api.maptiler.com/maps/basic/256/{z}/{x}/{y}.png?key=',
            'Bright':r'https://api.maptiler.com/maps/bright/256/{z}/{x}/{y}.png?key='
        }
        local_dataset = {
            'JP MIERUNE Street':r'https://api.maptiler.com/maps/jp-mierune-streets/256/{z}/{x}/{y}.png?key='
        }
        #init Collections
        standard_raster = RasterCollection('Standard raster tile', standard_dataset)
        local_raster = RasterCollection('Local raster tile', local_dataset)
        user_raster = RasterCollection('User raster tile', {}, user_editable=True)
        vector = VectorCollection()

        sip.transferto(standard_raster, self)
        sip.transferto(local_raster, self)
        sip.transferto(user_raster, self)
        sip.transferto(vector, self)

        return [standard_raster, local_raster, user_raster, vector]

    def actions(self, parent):
        actions = []

        configue_action = QAction(QIcon(), 'Configue', parent)
        configue_action.triggered.connect(self.openConfigueDialog)
        actions.append(configue_action)

        return actions

    def openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.show()
        result = configue_dialog.exec_()
        #reload browser
        self.refreshConnections()