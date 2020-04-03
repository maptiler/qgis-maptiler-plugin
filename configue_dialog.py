# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'configue_dialog_base.ui'))

class ConfigueDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(ConfigueDialog, self).__init__(parent)
        self.setupUi(self)

        smanager = SettingsManager()
        apikey = smanager.get_settings()['apikey']
        if apikey:
            self.user_txt.setText(apikey)
    
    def slot1(self):
        smanager = SettingsManager()
        smanager.store_setting('apikey', self.user_txt.text())
        self.close()
