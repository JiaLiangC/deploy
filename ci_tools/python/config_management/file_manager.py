import json
from enum import Enum

import yaml


class FileManager:
    class FileType(Enum):
        RAW = 'raw'
        JSON = 'json'
        YAML = 'yaml'

    @staticmethod
    def read_file(file_path, file_type: FileType):
        if file_type == FileManager.FileType.RAW:
            with open(file_path, 'r') as file:
                return file.read()
        elif file_type == FileManager.FileType.JSON:
            with open(file_path, 'r') as file:
                try:
                    return json.load(file)
                except Exception as e:
                    print("")
        elif file_type == FileManager.FileType.YAML:
            with open(file_path, 'r') as file:
                return yaml.safe_load(file)
        else:
            raise ValueError("Unsupported file type")

    @staticmethod
    def write_file(file_path, data, file_type: FileType):
        if file_type == FileManager.FileType.RAW:
            with open(file_path, 'w') as file:
                file.write(data)
        elif file_type == FileManager.FileType.JSON:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        elif file_type == FileManager.FileType.YAML:
            with open(file_path, 'w') as file:
                yaml.dump(data, file)
        else:
            raise ValueError("Unsupported file type")
