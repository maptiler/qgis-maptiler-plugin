# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager


class NewConnectionDialog(QtWidgets.QDialog):
    def __init__(self, layertype):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'new_connection_dialog_base.ui'), self)
        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

        self._layertype = layertype

    def _accepted(self):
        input_name = self.ui.name_txt.text()
        input_url = self.ui.url_txt.text()

        # when inputed URL includes APIKEY
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if apikey:
            if input_url.endswith(apikey):
                apikey_char_count = len(apikey) * -1
                input_url = input_url[:apikey_char_count]

        if self._has_error():
            return

        maps = smanager.get_setting(self._layertype)
        maps[input_name] = input_url
        smanager.store_setting(self._layertype, maps)

        self.close()

    def _rejected(self):
        self.close()

    def _has_error(self):
        input_name = self.ui.name_txt.text()
        input_url = self.ui.url_txt.text()

        is_empty_name = False
        is_empty_url = False
        is_existing_name = False
        error_message = ''

        if input_name == '':
            is_empty_name = True
            error_message += 'Name is empty, please input.\n'

        if input_url == '':
            is_empty_url = True
            error_message += 'Url to map is empty, please input.\n'

        smanager = SettingsManager()
        maps = smanager.get_setting(self._layertype)
        if input_name in maps:
            is_existing_name = True
            error_message += str('"' + input_name + '"' +
                                 ' already exists, please input other name.\n')

        if is_empty_name or is_empty_url or is_existing_name:
            QtWidgets.QMessageBox.warning(None, 'Error', error_message)
            return True


class RasterNewConnectionDialog(NewConnectionDialog):
    def __init__(self):
        super().__init__('rastermaps')


class VectorNewConnectionDialog(NewConnectionDialog):
    def __init__(self):
        super().__init__('vectormaps')
