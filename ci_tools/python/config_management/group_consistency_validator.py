from python.config_management.configurations.advanced_configuration import *
from python.config_management.configurations.hosts_info_configuration import *

from .service_map import *
from .validator import *


class GroupConsistencyValidator(Validator):

    def __init__(self, advanced_conf: AdvancedConfiguration, hosts_info_conf: HostsInfoConfiguration):
        super().__init__()
        self.hosts_info_conf = hosts_info_conf.get_conf()
        self.host_groups = advanced_conf.get("host_groups")
        self.host_group_services = advanced_conf.get("group_services")

    def validate(self):
        parsed_hosts = self.hosts_info_conf.get("hosts")
        conf_defined_hosts = {}
        host_groups_group_names = []
        host_group_services_group_names = []

        for host_info_str in parsed_hosts:
            host_info = host_info_str.split()
            ip = host_info[0]
            hostname = host_info[1]
            passwd = host_info[2]
            conf_defined_hosts[hostname] = ip

        for group_name, group_hosts in self.host_groups.items():
            host_groups_group_names.append(group_name)
            if len(list(set(group_hosts))) != len(group_hosts):
                self.err_messages.append("Each machine name can only be listed once within the same group.")
            for host_name in group_hosts:
                if host_name not in conf_defined_hosts:
                    self.err_messages.append(f"{host_name} Defined in conf.yml but not configured in hosts.yml.")

        for group_name, services in self.host_group_services.items():
            host_group_services_group_names.append(group_name)
            duplicated_services = [sname for sname in services if services.count(sname) >= 2]
            if len(duplicated_services) > 0:
                self.err_messages.append(
                    f"Each deployed component name can only be listed once within the same group. Please check the configuration of the following group: {group_name} , component name: {' '.join(list(set(duplicated_services)))}")

            for service_name in services:
                is_supported = ServiceMap.is_service_supported(service_name)
                if not is_supported:
                    self.err_messages.append("{}The selected component for deployment is currently not supported.".format(service_name))

        if not (len(host_groups_group_names) == len(host_group_services_group_names) and set(
                host_groups_group_names) == set(host_group_services_group_names)):
            self.err_messages.append("The host_groups configuration and the group names in group_services are inconsistent.")

        return self
