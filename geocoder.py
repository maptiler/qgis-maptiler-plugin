import json
import urllib
import ogr, osr
import requests
import io

from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPoint, QgsCoordinateTransform, QgsCoordinateReferenceSystem

from .settings_manager import SettingsManager

class MapTilerGeocoder:
    def __init__(self, language='ja'):
        self._language = language

    def geocoding(self, searchword, center_lonlat):
        query = urllib.parse.quote(searchword)

        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        proximity = '%s,%s'%(str(center_lonlat[0]),str(center_lonlat[1]))
        params = {
            'key':apikey,
            'proximity':proximity,
            'language':self._language
        }
        p = urllib.parse.urlencode(params, safe=',')

        url = 'https://api.maptiler.com/geocoding/' + query + '.json?' + p
        geojson_str = requests.get(url).text
        geojson_dict = json.loads(geojson_str)
        return geojson_dict