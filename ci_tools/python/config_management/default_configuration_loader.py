import os

from python.config_management.file_manager import *


class DefaultConfigurationLoader:
    def __init__(self, conf_dir, format=FileManager.FileType.YAML):
        self.format = format
        self.conf_dir = conf_dir

    def load_conf(self, conf_name):
        file_path = os.path.join(self.conf_dir, conf_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        content = FileManager.read_file(file_path, self.format)
        return content
