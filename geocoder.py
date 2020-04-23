import json
import urllib
import ogr, osr
import requests
import io

from qgis.core import *

from .configue_dialog import ConfigueDialog
from .settings_manager import SettingsManager
from . import utils

class MapTilerGeocoder:
    def __init__(self, language='ja'):
        self._language = language

    def geocoding(self, searchword, center_lonlat):
        #apikey validation
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if not utils.validate_key(apikey):
            self._openConfigueDialog()
            return

        proximity = '%s,%s'%(str(center_lonlat[0]),str(center_lonlat[1]))
        params = {
            'key':apikey,
            'proximity':proximity,
            'language':self._language
        }
        p = urllib.parse.urlencode(params, safe=',')

        query = urllib.parse.quote(searchword)
        url = 'https://api.maptiler.com/geocoding/' + query + '.json?' + p
        geojson_str = requests.get(url).text
        geojson_dict = json.loads(geojson_str)
        return geojson_dict

    def _openConfigueDialog(self):
        configue_dialog = ConfigueDialog()
        configue_dialog.exec_()