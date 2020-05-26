# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager


class EditConnectionDialog(QtWidgets.QDialog):
    def __init__(self, current_name):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'edit_connection_dialog_base.ui'), self)
        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

        self._current_name = current_name
        smanager = SettingsManager()
        custommaps = smanager.get_setting('custommaps')
        self._current_data = custommaps[self._current_name]

        self.ui.nameLineEdit.setText(self._current_name)
        self.ui.rasterLineEdit.setText(self._current_data['raster'])
        self.ui.vectorLineEdit.setText(self._current_data['vector'])

    def _accepted(self):
        name = self.ui.nameLineEdit.text()
        raster_url = self.ui.rasterLineEdit.text()
        vector_url = self.ui.vectorLineEdit.text()

        # when inputed URL includes APIKEY
        smanager = SettingsManager()
        apikey = smanager.get_setting('apikey')
        if apikey:
            if raster_url.endswith(apikey):
                apikey_char_count = len(apikey) * -1
                raster_url = raster_url[:apikey_char_count]
            if vector_url.endswith(apikey):
                apikey_char_count = len(apikey) * -1
                vector_url = vector_url[:apikey_char_count]

        if self._has_error():
            return

        custommaps = smanager.get_setting('custommaps')
        del custommaps[self._current_name]
        custommaps[name] = {
            'raster': raster_url,
            'vector': vector_url
        }
        smanager.store_setting('custommaps', custommaps)
        self.close()

    def _rejected(self):
        self.close()

    def _has_error(self):
        name = self.ui.nameLineEdit.text()
        raster_url = self.ui.rasterLineEdit.text()
        vector_url = self.ui.vectorLineEdit.text()

        is_empty_name = False
        is_empty_url = False
        is_existing_name = False
        error_message = ''

        if name == '':
            is_empty_name = True
            error_message += 'Name is empty, please input.\n'

        if raster_url == '' and vector_url == '':
            is_empty_url = True
            error_message += 'Url to map is empty, please input.\n'

        smanager = SettingsManager()
        custommaps = smanager.get_setting('custommaps')
        if not name == self._current_name and name in custommaps:
            is_existing_name = True
            error_message += str('"' + name + '"' +
                                 ' already exists, please input other name.\n')

        if is_empty_name or is_empty_url or is_existing_name:
            QtWidgets.QMessageBox.warning(None, 'Error', error_message)
            return True
