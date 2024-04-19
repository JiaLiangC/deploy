# -*- coding:utf8 -*-
# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.install_utils.install_utils import *
from python.utils.os_utils import *
import os
import shutil

logger = get_logger()
class FilesystemUtil:
    @staticmethod
    def create_dir(path, empty_if_exists=True):
        """Create a directory. If empty_if_exists is True, empty the dir if it exists."""
        print("Creating dir:", path)
        if os.path.exists(path) and empty_if_exists:
            FilesystemUtil.empty_dir(path)
        else:
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def empty_dir(path):
        """Empty the specified directory."""
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    @staticmethod
    def copy(src, dest):
        """Copy file or directory from src to dest."""
        if os.path.isdir(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    @staticmethod
    def recursive_glob(rootdir='.', prefix=None, suffix=None, filter_func=None):
        """Recursively glob files from rootdir with specific prefix and/or suffix, and apply an optional filter."""
        files = [
            os.path.join(looproot, filename)
            for looproot, _, filenames in os.walk(rootdir)
            # Filter filenames based on both prefix and suffix.
            for filename in filenames if
            (prefix is None or filename.startswith(prefix)) and (suffix is None or filename.endswith(suffix))
        ]

        # If a filter function is provided, further filter the file list.
        if filter_func is not None:
            files = [file for file in files if filter_func(file)]

        return files

    @staticmethod
    def delete(path):
        if os.path.isfile(path):
            print("Deleting file:", path)
            os.remove(path)
        elif os.path.isdir(path):
            print("Deleting dir:", path)
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.islink(path):
            print("Deleting link :", path)
            os.remove(path)