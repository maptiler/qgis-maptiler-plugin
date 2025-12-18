from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis, QgsColorRampShader, QgsNetworkAccessManager, QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.PyQt.QtCore import QUrl

import ssl
import json

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .settings_manager import SettingsManager
ssl._create_default_https_context = ssl._create_unverified_context


def validate_credentials() -> bool:
    testurl = 'https://api.maptiler.com/maps/basic/style.json'
    smanager = SettingsManager()
    auth_cfg_id = smanager.get_setting('auth_cfg_id')
    if auth_cfg_id:
        am = QgsApplication.authManager()
        cfg = QgsAuthMethodConfig()
        (res, cfg) = am.loadAuthenticationConfig(auth_cfg_id, cfg, True)
        if res:
            token = cfg.configMap().get("token")
            if token and len(token) > 33 and "_" in token:
                request = QNetworkRequest(QUrl(testurl))
                reply_content = QgsNetworkAccessManager.instance().blockingGet(request, auth_cfg_id)
                if reply_content.error() == QNetworkReply.NetworkError.NoError:
                    return True
    return False


def is_qgs_vectortile_api_enable():
    # judge vtile is available or not
    # e.g. QGIS3.10.4 -> 31004
    qgis_version_str = str(Qgis.QGIS_VERSION_INT)
    minor_ver = int(qgis_version_str[1:3])
    return minor_ver >= 13


def is_qgs_early_resampling_enabled():
    qgis_version_str = str(Qgis.QGIS_VERSION_INT)
    minor_ver = int(qgis_version_str[1:3])
    return minor_ver >= 25


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
    ramp_items = [[float(line.rstrip("\n").split(',')[0])] + list(map(int, line.rstrip("\n").split(',')[1:5])) for line in lines]
    ramp_lst = [QgsColorRampShader.ColorRampItem(ramp_item[0], QColor(ramp_item[1], ramp_item[2], ramp_item[3], ramp_item[4])) for ramp_item in ramp_items]
    min_ramp_value = ramp_items[0][0]
    max_ramp_value = ramp_items[-1][0]
    return min_ramp_value, max_ramp_value, ramp_lst


class MapTilerApiException(Exception):
    def __init__(self, message, content):
        self.message = message
        self.content = content
        super().__init__(self.message)


def _qgis_request(url: str):
    smanager = SettingsManager()
    auth_cfg_id = smanager.get_setting('auth_cfg_id')
    parsed = urlsplit(url)
    if "maptiler.com" in parsed.netloc:
        # remove only the 'key' query parameter (keep other query items)
        query_items = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() != 'key']
        new_query = urlencode(query_items, doseq=True)
        clean_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))
        request = QNetworkRequest(QUrl(clean_url))
        if auth_cfg_id:
            reply = QgsNetworkAccessManager.instance().blockingGet(request, auth_cfg_id)
        else:
            reply = QgsNetworkAccessManager.instance().blockingGet(request)
    else:
        request = QNetworkRequest(QUrl(url))
        reply = QgsNetworkAccessManager.instance().blockingGet(request)

    # Treat as success if HTTP status is 2xx, or there's non-empty content,
    # even if Qt sets a non-fatal error flag (observed in Qt6 builds).
    try:
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        status_int = int(status) if status is not None else None
        if status_int and 200 <= status_int < 300:
            return reply
    except Exception:
        pass

    if not reply.error():
        return reply

    # fallback: accept reply if it has content (helps when Qt6 marks error but returns valid JSON)
    raw = reply.content()
    content_bytes = raw.data() if hasattr(raw, "data") else raw
    if content_bytes:
        return reply

    # real error — raise with details
    err = reply.errorString() or ""
    content_text = content_bytes.decode("utf-8", errors="replace") if content_bytes else ""
    raise MapTilerApiException(err, content_text)


def qgis_request_json(url: str) -> dict:
    reply = _qgis_request(url)
    # attempt to decode JSON; if it fails raise MapTilerApiException with body
    raw = reply.content()
    data = raw.data() if hasattr(raw, "data") else raw
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        content_text = data.decode("utf-8", errors="replace") if data else ""
        raise MapTilerApiException(f"Invalid JSON response: {e}", content_text)


def qgis_request_data(url: str) -> bytes:
    reply_content = _qgis_request(url)
    return reply_content.content().data()


if __name__ == "__main__":
    validate_credentials()
