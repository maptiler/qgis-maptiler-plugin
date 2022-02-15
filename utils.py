from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis, QgsColorRampShader, QgsNetworkAccessManager, QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.Qt import QColor
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

import ssl
import json

from .settings_manager import SettingsManager
ssl._create_default_https_context = ssl._create_unverified_context


def validate_key(apikey='') -> bool:
    testurl = f'https://api.maptiler.com/maps/basic/style.json?key={apikey}'
    request = QNetworkRequest(QUrl(testurl))
    reply_content = QgsNetworkAccessManager.instance().blockingGet(request)

    if reply_content.error() == 0:
        return True
    else:
        print(f"Validation error:{reply_content.content()}")
    return False


def validate_credentials(auth_cfg_id='') -> bool:
    testurl = 'https://api.maptiler.com/maps/basic/style.json'
    request = QNetworkRequest(QUrl(testurl))
    reply_content = QgsNetworkAccessManager.instance().blockingGet(request, auth_cfg_id)

    if not reply_content.error():
        return True
    else:
        print(f"Validation error:{reply_content.content()}")
    return False


def is_qgs_vectortile_api_enable():
    # judge vtile is available or not
    # e.g. QGIS3.10.4 -> 31004
    qgis_version_str = str(Qgis.QGIS_VERSION_INT)
    minor_ver = int(qgis_version_str[1:3])
    return minor_ver >= 13


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


def load_color_ramp_from_file(fp: str) -> list:
    with open(fp, 'r') as f:
        lines = f.readlines()[2:]  # get rid of header
    ramp_items = [list(map(float, line.rstrip("\n").split(',')[0:4])) for line in lines]
    ramp_lst = [QgsColorRampShader.ColorRampItem(ramp_item[0], QColor(ramp_item[1], ramp_item[2],
                                                                      ramp_item[3])) for ramp_item in ramp_items]
    min_ramp_value = ramp_items[0][0]
    max_ramp_value = ramp_items[-1][0]
    return min_ramp_value, max_ramp_value, ramp_lst


def _qgis_request(url: str):
    smanager = SettingsManager()
    auth_cfg_id = smanager.get_setting('auth_cfg_id')
    request = QNetworkRequest(QUrl(url))
    if "maptiler" in url:
        if "key=" in url:
            ki = url.find("key=") + len("key=")
            url_key = url[ki:].split("&")[0]
            am = QgsApplication.authManager()
            cfg = QgsAuthMethodConfig()
            am.loadAuthenticationConfig(auth_cfg_id, cfg, True)
            token = cfg.configMap().get('token')
            token_key = token.split("_")[0]
            if url_key == token_key:
                reply_content = QgsNetworkAccessManager.instance().blockingGet(request, auth_cfg_id)
            else:
                reply_content = QgsNetworkAccessManager.instance().blockingGet(request)
        else:
            reply_content = QgsNetworkAccessManager.instance().blockingGet(request, auth_cfg_id)
    else:
        reply_content = QgsNetworkAccessManager.instance().blockingGet(request)
    return reply_content


def qgis_request_json(url: str) -> dict:
    reply_content = _qgis_request(url)
    if not reply_content.error():
        json_data = json.loads(reply_content.content().data().decode())
        return json_data
    else:
        return None


def qgis_request_data(url: str) -> bytes:
    reply_content = _qgis_request(url)
    if not reply_content.error():
        return reply_content.content().data()
    return None


if __name__ == "__main__":
    validate_credentials('')
