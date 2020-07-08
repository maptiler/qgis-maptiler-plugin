# -*- coding: utf-8 -*-

import os

from PyQt5 import uic, QtWidgets, QtCore, QtGui
from qgis.core import Qgis

from .settings_manager import SettingsManager
from . import utils


class ConfigueDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'configue_dialog_base.ui'), self)

        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        self.ui.apikey_txt.setText(apikey)

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

        apikey = self.ui.apikey_txt.text()
        smanager.store_setting('apikey', apikey)

        prefervector = str(int(self.ui.vtileCheckBox.isChecked()))
        smanager.store_setting('prefervector', prefervector)

        self.close()

    def _rejected(self):
        self.close()
