# -*- coding: utf-8 -*-

from PyQt5 import uic, QtWidgets, QtCore
import os

from .settings_manager import SettingsManager
from . import mapdatasets


class AddConnectionDialog(QtWidgets.QDialog):

    STANDARD_DATASET = mapdatasets.STANDARD_DATASET
    LOCAL_JP_DATASET = mapdatasets.LOCAL_JP_DATASET
    LOCAL_NL_DATASET = mapdatasets.LOCAL_NL_DATASET
    LOCAL_UK_DATASET = mapdatasets.LOCAL_UK_DATASET

    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'add_connection_dialog_base.ui'), self)

        self._init_list()
        self.ui.button_box.accepted.connect(self._accepted)
        self.ui.button_box.rejected.connect(self._rejected)

    def _init_list(self):
        # support multiple selection
        self.ui.listWidget.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)

        DATASETS = dict(**self.STANDARD_DATASET,
                        **self.LOCAL_JP_DATASET,
                        **self.LOCAL_NL_DATASET,
                        **self.LOCAL_UK_DATASET
                        )

        smanager = SettingsManager()
        selectedmaps = smanager.get_setting('selectedmaps')
        for key in DATASETS:
            if key in selectedmaps:
                continue
            self.ui.listWidget.addItem(key)

    def _maptiler_tab_action(self):
        selecteditems = self.ui.listWidget.selectedItems()

        smanager = SettingsManager()
        selectedmaps = smanager.get_setting('selectedmaps')

        for item in selecteditems:
            # this lines is not runned in normal
            if item.text() in selectedmaps:
                print('Selected map already exist in Browser')
                return

            selectedmaps.append(item.text())
            smanager.store_setting('selectedmaps', selectedmaps)

    def _custom_tab_action(self):
        name = self.ui.nameLineEdit.text()
        json_url = self.ui.jsonLineEdit.text()

        smanager = SettingsManager()
        if self._has_error():
            return

        custommaps = smanager.get_setting('custommaps')
        custommaps[name] = {
            'custom': json_url
        }
        smanager.store_setting('custommaps', custommaps)

    def _accepted(self):
        if self.ui.tabWidget.currentIndex() == 0:
            self._maptiler_tab_action()
        else:
            self._custom_tab_action()
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
        if name in custommaps:
            is_existing_name = True
            error_message += str('"' + name + '"' +
                                 ' already exists, please input other name.\n')

        if is_empty_name or is_empty_url or is_existing_name:
            QtWidgets.QMessageBox.warning(None, 'Error', error_message)
            return True
