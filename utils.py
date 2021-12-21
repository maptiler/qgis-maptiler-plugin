import requests
import os
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis
from .settings_manager import SettingsManager

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

def validate_key(apikey='') -> bool:
    testurl = 'https://api.maptiler.com/maps/basic/style.json?key='
    response = requests.get(testurl + apikey)
    
    if response.status_code == 200:
        return True
    
    print(f"key validation error code:{response.status_code}")
    return False


def is_qgs_vectortile_api_enable():
    # judge vtile is available or not
    # e.g. QGIS3.10.4 -> 31004
    qgis_version_str = str(Qgis.QGIS_VERSION_INT)
    minor_ver = int(qgis_version_str[1:3])
    return minor_ver >= 13


def is_qgs_virtual_raster_enable():
    # judge raster on-the-fly
    qgis_version_str = str(Qgis.QGIS_VERSION_INT)
    version = int(qgis_version_str[:3])
    return version >= 322


def create_virtual_raster_url(trgb_xml, custom_trgb_xml):
    with open(trgb_xml, 'r') as f:
        xml_str = f.read()
    smanager = SettingsManager()
    apikey = smanager.get_setting('apikey')
    xml_str_with_key = xml_str.replace("INSERTKEY", apikey)
    with open(custom_trgb_xml, 'w') as f:
        f.write(xml_str_with_key)
    url = f"?crs=EPSG:3857" \
          f"&extent=-20037508.33999999985098839,-20037508.33999999985098839," \
          f"20037508.33999999985098839,20037508.33999999985098839" \
          f"&width=2097152" \
          f"&height=2097152" \
          f"&formula=-10000+((%22trgb@1%22*256*256+%22trgb@2%22*256+%22trgb@3%22)*0.1)" \
          f"&trgb:uri={custom_trgb_xml}&trgb:provider=gdal"
    return url


def create_hillshade_url(zxy_url):
    replaced_url = zxy_url.replace('terrain-rgb', 'hillshade').replace('png', 'webp')
    url = f"zmin=0&zmax=12&type=xyz&url={replaced_url}"
    return url


def is_in_darkmode(threshold=383):
    """detect the Qt in Darkmode or not 

    This function has a dependancy on PyQt, QMessageBox.
    Although Qt has no API to detect running in Darkmode or not,
    it is able to get RGB value of widgets, including UI parts of them.
    This function detect Darkmode by evaluating a sum of RGB value of the widget with threshold.

    Args:
        threshold (int, optional): a sum of RGB value (each 0-255, sum 0-765). Default to 383, is just median.
    Returns:
        bool: True means in Darkmode, False in not.
    """
    # generate empty QMessageBox to detect
    # generated widgets has default color palette in the OS
    empty_mbox = QMessageBox()

    # get a background color of the widget
    red = empty_mbox.palette().window().color().red()
    green = empty_mbox.palette().window().color().green()
    blue = empty_mbox.palette().window().color().blue()

    sum_rgb_value = red + green + blue
    return sum_rgb_value < threshold


if __name__ == "__main__":
    validate_key('')
