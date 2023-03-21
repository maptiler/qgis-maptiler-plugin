from PyQt5.QtCore import QSettings

# QSettings holds variables as list or dict or str.
# if int or bool value is set, they are converted to str in the Class.
# In particular, isVectorEnabled is treated as bool by cast str '0' or '1' to int(bool).


class SettingsManager:
    SETTING_GROUP = '/maptiler'

    def __init__(self):
        self._settings = {
            'selectedmaps': ['Basic', 'Bright', 'Outdoor', 'OpenStreetMap', 'Satellite', 'Streets',
                             'Terrain', 'Toner', 'Topo', 'Voyager'],
            'prefervector': '1',
            'custommaps': {},
            'auth_cfg_id': ''
        }
        self.load_settings()

    def load_setting(self, key):
        qsettings = QSettings()
        qsettings.beginGroup(self.SETTING_GROUP)
        value = qsettings.value(key)
        qsettings.endGroup()
        if value:
            self._settings[key] = value

    def load_settings(self):
        for key in self._settings:
            self.load_setting(key)

    def store_setting(self, key, value):
        if key == "auth_cfg_id":
            value = value.strip()
        qsettings = QSettings()
        qsettings.beginGroup(self.SETTING_GROUP)
        qsettings.setValue(key, value)
        qsettings.endGroup()

        self.load_settings()

    def get_setting(self, key):
        return self._settings[key]

    def get_settings(self):
        return self._settings
