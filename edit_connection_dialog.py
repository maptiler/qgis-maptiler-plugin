# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets
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
        self.ui.jsonLineEdit.setText(self._current_data['custom'])

    def _accepted(self):
        name = self.ui.nameLineEdit.text()
        json_url = self.ui.jsonLineEdit.text()
        smanager = SettingsManager()

        if self._has_error():
            return

        custommaps = smanager.get_setting('custommaps')
        del custommaps[self._current_name]
        custommaps[name] = {
            'custom': json_url,
        }
        smanager.store_setting('custommaps', custommaps)
        self.close()

    def _rejected(self):
        self.close()

    def _has_error(self):
        name = self.ui.nameLineEdit.text()
        json_url = self.ui.jsonLineEdit.text()

        is_empty_name = False
        is_empty_url = False
        is_existing_name = False
        error_message = ''

        if name == '':
            is_empty_name = True
            error_message += 'Name is empty, please input.\n'

        if json_url == '':
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
