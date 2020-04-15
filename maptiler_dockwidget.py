# -*- coding: utf-8 -*-
from PyQt5 import uic, QtWidgets, QtCore
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsPoint, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsVectorLayer, QgsRectangle

import os
import json

from .geocoder import MapTilerGeocoder
from .settings_manager import SettingsManager

class MapTilerDockWidget(QtWidgets.QDockWidget):
    closingPlugin = pyqtSignal()
    def __init__(self, iface):
        super().__init__()
        self._proj = QgsProject.instance()
        self._ui = uic.loadUi(os.path.join(os.path.dirname(__file__), 'maptiler_dockwidget_base.ui'), self)
        self._iface = iface
        self.search_results = []

        #init QCompleter
        self.completer = QtWidgets.QCompleter([])
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(30)
        self.completer.setModelSorting(QtWidgets.QCompleter.UnsortedModel)
        self.completer.setCompletionMode(QtWidgets.QCompleter.UnfilteredPopupCompletion)
        self.completer.activated[QtCore.QModelIndex].connect(self.on_result_clicked)

        #init LineEdit of searchword
        self._ui.searchword_text.setCompleter(self.completer)
        self._ui.searchword_text.textEdited.connect(self.on_searchword_edited)
        self._ui.searchword_text.returnPressed.connect(self.on_searchword_returned)

    #LineEdit edited event
    def on_searchword_edited(self):
        model = self.completer.model()
        model.setStringList([])
        self.completer.complete()
    
    #LineEdit returned event
    def on_searchword_returned(self):
        searchword = self._ui.searchword_text.text()
        geojson_dict = self._fetch_geocoding_api(searchword)
        
        self.result_features = geojson_dict['features']

        result_list = []
        for feature in self.result_features:
            result_list.append('%s:%s'%(feature['text'],feature['place_name']))

        model = self.completer.model()
        model.setStringList(result_list)
        self.completer.complete()

    def _fetch_geocoding_api(self, searchword):
        #get a center point of MapCanvas
        center = self._iface.mapCanvas().center()
        center_as_qgspoint = QgsPoint(center.x(), center.y())

        #transform the center point to EPSG:4326
        target_crs = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(self._proj.crs(), target_crs, self._proj)
        center_as_qgspoint.transform(transform)
        center_lonlat = [center_as_qgspoint.x(), center_as_qgspoint.y()]

        #start Geocoding
        geocoder = MapTilerGeocoder()
        geojson_dict = geocoder.geocoding(searchword, center_lonlat)
        return geojson_dict

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def on_result_clicked(self, result_index):
        #add selected feature to Project
        selected_feature = self.result_features[result_index.row()]
        geojson_str = json.dumps(selected_feature)
        vlayer = QgsVectorLayer(geojson_str, selected_feature['place_name'], 'ogr')
        self._proj.addMapLayer(vlayer)

        #get leftbottom and righttop points of vlayer
        vlayer_extent_rect = vlayer.extent()
        vlayer_extent_leftbottom = QgsPoint(vlayer_extent_rect.xMinimum(), vlayer_extent_rect.yMinimum()) 
        vlayer_extent_righttop = QgsPoint(vlayer_extent_rect.xMaximum(), vlayer_extent_rect.yMaximum()) 
        
        #transform 2points to project CRS
        current_crs = vlayer.sourceCrs()
        target_crs = self._proj.crs()
        transform = QgsCoordinateTransform(current_crs, target_crs, self._proj)
        vlayer_extent_leftbottom.transform(transform)
        vlayer_extent_righttop.transform(transform)

        #make rectangle same to new extent by transformed 2points
        target_extent_rect = QgsRectangle(vlayer_extent_leftbottom.x(), vlayer_extent_leftbottom.y(),
                         vlayer_extent_righttop.x(), vlayer_extent_righttop.y() )

        self._iface.mapCanvas().zoomToFeatureExtent(target_extent_rect)