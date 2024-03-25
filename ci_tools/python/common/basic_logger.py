# !/usr/bin/python3
# -*- coding: UTF-8 -*-
import logging
from logging.handlers import MemoryHandler

from .constants import *


def get_logger(name="bigdata_deploy_logger", log_file="bigdata_deploy.log", level=logging.DEBUG):
    """设置日志记录器以将日志写入指定的文件。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # 创建一个文件处理器，用于将日志记录到文件
        file_handler = logging.FileHandler(f'{LOGS_DIR}/{log_file}')
        file_handler.setLevel(level)

        # 创建一个内存处理器，设置缓存大小为200条日志记录
        memory_handler = MemoryHandler(capacity=20, target=file_handler)

        # 创建一个控制台处理器，用于将日志输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 创建一个日志格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # 将格式器添加到处理器
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        memory_handler.setFormatter(formatter)

        # 将处理器添加到日志记录器
        logger.addHandler(memory_handler)
        logger.addHandler(console_handler)
    return logger

