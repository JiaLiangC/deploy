from python.config_management.parsers import Parser
from python.exceptions.invalid_configuration_exception import *


class HostsInfoParser(Parser):

    def parse_hosts(self, data):
        hosts = self._expand_range(data)
        return hosts

    def parse(self, hosts_configurations):
        # Parse machine wildcards, similar to parsing ansible hosts configuration.
        # Can parse wildcard machine names or IP formats like node[1-3], node[1-3]xx, or [1-3]node.
        # hosts_configurations 为 ["10.1.1.15 server4 password4",...]
        # Given input hosts_configurations ["10.1.1.[1-3] node[1-3].example.com password4"], the function outputs [("node1.example.com","10.1.1.1","password4"), ("node2.example.com","10.1.1.2","password4"), ("node3.example.com","10.1.1.3","password4")].

        parsed_configs = []

        for config in hosts_configurations:
            if len(config.split()) != 3:
                raise InvalidConfigurationException

            if '[' in config:
                hostname_part, ip_part, password = config.split()
                hosts = []
                ips = []
                if '[' in hostname_part and '[' in ip_part:
                    hosts = self.parse_hosts(hostname_part)
                    ips = self.parse_hosts(ip_part)
                else:
                    raise InvalidConfigurationException

                if len(hosts) != len(ips):
                    raise InvalidConfigurationException("Configuration is invalid")
                for index, ip in enumerate(ips):
                    parsed_configs.append((hosts[index], ip, password))
            else:
                parsed_configs.append(tuple(config.split()))

        return parsed_configs
