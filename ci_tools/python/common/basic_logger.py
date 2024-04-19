# !/usr/bin/python3
# -*- coding: UTF-8 -*-
import logging
from logging.handlers import MemoryHandler

from .constants import *


def get_logger(name="bigdata_deploy_logger", log_file="bigdata_deploy.log", level=logging.DEBUG):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(f'{LOGS_DIR}/{log_file}')
        file_handler.setLevel(level)

        memory_handler = MemoryHandler(capacity=20, target=file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        memory_handler.setFormatter(formatter)

        logger.addHandler(memory_handler)
        logger.addHandler(console_handler)
    return logger

