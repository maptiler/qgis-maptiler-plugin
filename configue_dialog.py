# -*- coding: utf-8 -*-

import os

from PyQt5 import uic, QtWidgets, QtCore
from qgis.core import Qgis

from .settings_manager import SettingsManager


class ConfigueDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()

        self.ui = uic.loadUi(os.path.join(os.path.dirname(__file__), 'configue_dialog_base.ui'), self)
        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)
        
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        self.ui.apikey_txt.setText(apikey)

        qgis_version_str = str(Qgis.QGIS_VERSION_INT) #e.g. QGIS3.10.4 -> 31004
        #major_ver = int(qgis_version_str[0])
        minor_ver = int(qgis_version_str[1:3])
        #micro_ver = int(qgis_version_str[3:])
        
        #Checkbox are available only when on QGIS version having feature of Vectortile
        if minor_ver > 12:
            self.ui.vtileCheckBox.setEnabled(True)
            isVectorEnabled = int(smanager.get_setting('isVectorEnabled'))
            self.ui.vtileCheckBox.setChecked(isVectorEnabled)

    def _accepted(self):
        #get and store UI values
        smanager = SettingsManager()

        apikey = self.ui.apikey_txt.text()
        smanager.store_setting('apikey', apikey)

        isVectorEnabled = int(self.ui.vtileCheckBox.isChecked())
        smanager.store_setting('isVectorEnabled', isVectorEnabled)

        self.close()

    def _rejected(self):
        self.close()