from ipaddress import ip_address

from python.config_management.configurations.hosts_info_configuration import *

from .validator import *


class HostsInfoValidator(Validator):
    def __init__(self, hosts_info_conf: HostsInfoConfiguration):
        super().__init__()
        self.hosts_info_conf = hosts_info_conf.get_conf()

    def validate(self):
        parsed_hosts = self.hosts_info_conf.get("hosts")

        # Validate IP addresses
        for host in parsed_hosts:
            ip, hostname, _ = host.split()
            if not HostsInfoValidator._is_valid_ip(ip):
                self.err_messages.append(f"Invalid IP address: {ip}")

        # Additional validations can be added here (e.g., hostname format)

        return self

    @staticmethod
    def _is_valid_ip(ip):
        try:
            ip_address(ip)
            return True
        except ValueError:
            return False
