import os
import sip
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsDataCollectionItem
)

class VectorCollection(QgsDataCollectionItem):
    def __init__(self):
        QgsDataCollectionItem.__init__(self, None, "Vector", "/MapTiler/vector")