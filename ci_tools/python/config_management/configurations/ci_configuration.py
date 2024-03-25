from python.common.constants import *

from .base_configuration import BaseConfiguration
class CIConfiguration(BaseConfiguration):
    def __init__(self, name=CI_CONF_NAME):
        super().__init__(name)

