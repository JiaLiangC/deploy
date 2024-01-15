import os

from python.common.constants import *
from python.config_management.default_configuration_loader import *


class BaseConfiguration:
    def __init__(self, name, conf_loader=DefaultConfigurationLoader):
        self.conf_loader = conf_loader
        self.name = name
        self.conf = {}
        self.format = FileManager.FileType.YAML
        self.conf_file_path = os.path.join(CONF_DIR, self.name)

    def set_format(self, format):
        self.format = format
        return self

    def set_path(self, new_dir):
        self.conf_file_path = os.path.join(new_dir, self.name)
        return self

    def set_conf(self, conf):
        self.conf = conf
        return self

    def get_conf(self):
        if not self.conf:
            self.conf = self.conf_loader(CONF_DIR, self.format).load_conf(self.name)
        return self.conf

    def get_str_conf(self):
        str_conf = FileManager.read_file(os.path.join(CONF_DIR, self.name), FileManager.FileType.RAW)
        return str_conf

    def get(self, key, default=None):
        conf = self.get_conf()
        try:
            return conf[key]
        except KeyError:
            if default is not None:
                return default
            raise InvalidConfigurationException(f"Configuration key '{key}' is missing.")

    def save(self):
        FileManager.write_file(self.conf_file_path, self.get_conf(), self.format)

    def save_with_str(self, str_conf):
        if not isinstance(str_conf, str):
            raise ValueError("Input 'str_conf' must be a string")
        FileManager.write_file(self.conf_file_path, str_conf, FileManager.FileType.RAW)
