from python.common.constants import *
from python.config_management.hosts_info_parser import HostsInfoParser

from .base_configuration import BaseConfiguration


class HostsInfoConfiguration(BaseConfiguration, HostsInfoParser):
    def __init__(self, name=HOSTS_CONF_NAME):
        super().__init__(name)

    def get_hosts_info(self):
        hosts_info_arr = self.get_conf()
        return hosts_info_arr.get("hosts")

    def get_user(self):
        # 默认部署user 为root
        return self.get("user", "root")
