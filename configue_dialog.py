# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

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

    def _accepted(self):
        apikey = self.ui.apikey_txt.text()
        smanager = SettingsManager()
        smanager.store_setting('apikey', apikey)
        self.close()

    def _rejected(self):
        self.close()