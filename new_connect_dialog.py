# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'new_connect_dialog_base.ui'))

class NewConnectDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(NewConnectDialog, self).__init__(parent)
        self.setupUi(self)
    
    def slot1(self):
        input_name = self.user_txt.text()
        input_url = self.pass_txt.text()
        smanager = SettingsManager()

        #when inputed URL includes APIKEY
        apikey = smanager.get_setting('apikey')
        if apikey:
            if input_url.endswith(apikey):
                apikey_char_count = len(apikey) * -1
                input_url = input_url[:apikey_char_count]

        rastermaps = smanager.get_setting('rastermaps')
        rastermaps[input_name] = input_url
        smanager.store_setting('rastermaps', rastermaps)

        self.close()
