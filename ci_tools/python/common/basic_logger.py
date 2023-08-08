# -*- coding: UTF-8 -*-
import logging
from logging.handlers import MemoryHandler

from .constants import *
# 创建一个日志记录器
logger = logging.getLogger('bigdata_deploy_logger')
logger.setLevel(logging.INFO)

# 创建一个文件处理器，用于将日志记录到文件
file_handler = logging.FileHandler(f'{LOGS_DIR}/bigdata_deploy.log')
file_handler.setLevel(logging.DEBUG)

# 创建一个内存处理器，设置缓存大小为200条日志记录
memory_handler = MemoryHandler(capacity=50, target=file_handler)

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