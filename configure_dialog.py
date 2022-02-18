# -*- coding: utf-8 -*-

import os

from PyQt5 import uic, QtWidgets, QtGui
from qgis.core import Qgis, QgsAuthMethodConfig, QgsApplication
from qgis.PyQt.QtWidgets import QMessageBox

from .settings_manager import SettingsManager
from . import utils


class ConfigureDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'configure_dialog_base.ui'), self)

        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

        # Load saved token
        smanager = SettingsManager()
        auth_cfg_id = smanager.get_setting('auth_cfg_id')
        if auth_cfg_id:
            am = QgsApplication.authManager()
            cfg = QgsAuthMethodConfig()
            am.loadAuthenticationConfig(auth_cfg_id, cfg, True)
            token = cfg.configMap().get("token")
            self.ui.token_txt.setText(token)

        # e.g. QGIS3.10.4 -> 31004
        qgis_version_str = str(Qgis.QGIS_VERSION_INT)
        #major_ver = int(qgis_version_str[0])
        minor_ver = int(qgis_version_str[1:3])
        #micro_ver = int(qgis_version_str[3:])

        # Checkbox are available only when on QGIS version having feature of Vectortile
        if minor_ver > 12:
            self.ui.vtileCheckBox.setEnabled(True)
            prefervector = bool(int(smanager.get_setting('prefervector')))
            self.ui.vtileCheckBox.setChecked(prefervector)

        # when OS in darkmode change icon to darkmode one
        if utils.is_in_darkmode():
            darkmode_icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                              "imgs",
                                              "logo_maptiler_dark.svg")
            pixmap = QtGui.QPixmap(darkmode_icon_path)
            self.ui.label_2.setPixmap(pixmap)

    def _accepted(self):
        # get and store UI values
        smanager = SettingsManager()
        am = QgsApplication.authManager()
        auth_cfg_id = smanager.get_setting('auth_cfg_id')
        token = self.ui.token_txt.text()
        cfg = QgsAuthMethodConfig('MapTilerHmacSha256')
        if token:
            if auth_cfg_id:
                (res, cfg) = am.loadAuthenticationConfig(auth_cfg_id, cfg, True)
                if res:
                    saved_token = cfg.configMap().get("token")
                    if not saved_token == token:
                        cfg.setConfigMap({'token': token})
                        (res, cfg) = am.storeAuthenticationConfig(cfg, True)
                        if res:
                            smanager.store_setting('auth_cfg_id', cfg.id())
                else:
                    cfg.setName('qgis-maptiler-plugin')
                    cfg.setConfigMap({'token': token})
                    (res, cfg) = am.storeAuthenticationConfig(cfg, True)
                    if res:
                        smanager.store_setting('auth_cfg_id', cfg.id())
            else:
                cfg.setName('qgis-maptiler-plugin')
                cfg.setConfigMap({'token': token})
                (res, cfg) = am.storeAuthenticationConfig(cfg, True)
                if res:
                    smanager.store_setting('auth_cfg_id', cfg.id())
            prefervector = str(int(self.ui.vtileCheckBox.isChecked()))
            smanager.store_setting('prefervector', prefervector)
            self.close()
        else:
            QMessageBox.warning(None, 'Missing token', "Token is required!")

    def _rejected(self):
        self.close()
