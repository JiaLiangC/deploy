from .base_configuration import BaseConfiguration
from .advanced_configuration import AdvancedConfiguration
from .hosts_info_configuration import HostsInfoConfiguration
from python.config_management.hosts_info_parser import HostsInfoParser
from python.config_management.topology_manager import TopologyManager
from python.common.constants import *
import yaml

# from .base_configuration import *
# from .hosts_info_configuration import *
from enum import Enum
# from .base_configuration import *
# from .hosts_info_configuration import *
from enum import Enum

import yaml
from python.common.constants import *
from python.config_management.hosts_info_parser import HostsInfoParser
from python.config_management.topology_manager import TopologyManager

from .advanced_configuration import AdvancedConfiguration
from .base_configuration import BaseConfiguration
from .hosts_info_configuration import HostsInfoConfiguration


class StandardConfiguration(BaseConfiguration, HostsInfoParser):
    def __init__(self, name):
        super().__init__(name)
        self.parsed_conf = {}

    class GenerateConfType(Enum):
        AdvancedConfiguration = 'AdvancedConfiguration'
        HostsInfoConfiguration = 'HostsInfoConfiguration'

    def get_conf(self):
        if not self.parsed_conf:
            original_conf = super().get_conf()
            hosts_info_arr = self.parse(original_conf.get("hosts"))
            original_conf.update({"hosts": hosts_info_arr})
            self.parsed_conf = original_conf

        return self.parsed_conf

    def get_parsed_hosts_names(self):
        parsed_hosts = self.get_conf().get("hosts")
        hosts_names = []
        for host_info in parsed_hosts:
            hostname = host_info[1]
            hosts_names.append(hostname)
        return hosts_names

    def generate_conf(self, conf_type: GenerateConfType):
        conf = self.get_conf()
        make_hosts_string = lambda arr: [" ".join(tple) for tple in arr]
        if conf_type == StandardConfiguration.GenerateConfType.HostsInfoConfiguration:
            hosts_info_yaml_data = {
                "user": conf["user"],
                "hosts": make_hosts_string(conf["hosts"])
            }
            hosts_info_conf = HostsInfoConfiguration()
            hosts_info_conf.set_conf(hosts_info_yaml_data).save()
            return hosts_info_conf

        if conf_type == StandardConfiguration.GenerateConfType.AdvancedConfiguration:
            conf_yaml_data = {
                "default_password": conf["default_password"],
                "data_dirs": conf["data_dirs"],
                "repos": conf["repos"]
            }
            conf_tpl_file = GET_CONF_TPL_NAME(CONF_NAME)
            # todo hostname fetcher
            advanced_tpl_str_conf = AdvancedConfiguration(conf_tpl_file).get_str_conf()
            hosts_names = self.get_parsed_hosts_names()
            topology_manager = TopologyManager(lambda: hosts_names)
            topology = topology_manager.generate_topology()
            topology.update(conf_yaml_data)

            merged_conf_str = self.merge_conf(topology, base_conf=advanced_tpl_str_conf, merge_strategy="prepend")
            advanced_conf = AdvancedConfiguration()
            advanced_conf.save_with_str(merged_conf_str)
            return advanced_conf

    def merge_conf(self, yaml_need_merge, base_conf=None, merge_strategy="replace"):
        current_conf = yaml_need_merge
        valid_strategies = ["prepend", "replace"]
        assert merge_strategy in valid_strategies, f"Invalid merge strategy. Supported: {valid_strategies}"

        existing_conf = base_conf or {}
        if merge_strategy == "prepend":
            raw_data = base_conf
            prepend_yaml_str = yaml.dump(current_conf, default_flow_style=None, sort_keys=False)
            merged_conf = prepend_yaml_str + "\n" + raw_data
        elif merge_strategy == "replace":
            # dict
            existing_conf.update(current_conf)
            merged_conf = existing_conf
        else:
            raise Exception(f"Invalid merge strategy. Supported: {valid_strategies}")
        return merged_conf
