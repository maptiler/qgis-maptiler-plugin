# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager

class NewConnectionDialog(QtWidgets.QDialog):
    def __init__(self, layertype):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(__file__), 'new_connection_dialog_base.ui'), self)
        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

        self._layertype = layertype

    def _accepted(self):
        input_name = self.ui.name_txt.text()
        input_url = self.ui.url_txt.text()

        #when inputed URL includes APIKEY
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if apikey:
            if input_url.endswith(apikey):
                apikey_char_count = len(apikey) * -1
                input_url = input_url[:apikey_char_count]

        if input_name == '':
            print('layer name is empty, please input name.')
            return

        if input_url == '':
            print('layer url is empty, please input name.')
            return
            
        maps = smanager.get_setting(self._layertype)
        if input_name in maps:
            print(input_name + ' already exist, input other name.')
            return
        
        maps[input_name] = input_url
        smanager.store_setting(self._layertype, maps)

        self.close()

    def _rejected(self):
        self.close()

class RasterNewConnectionDialog(NewConnectionDialog):
    def __init__(self):
        super().__init__('rastermaps')

class VectorNewConnectionDialog(NewConnectionDialog):
    def __init__(self):
        super().__init__('vectormaps')