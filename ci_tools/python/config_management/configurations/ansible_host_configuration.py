from python.config_management import *
from python.config_management.dynamic_variable_generator import DynamicVariableGenerator

from .base_configuration import *
from .hosts_info_configuration import *


class AnsibleHostConfiguration(BaseConfiguration):
    def __init__(self, name, hosts_info_configuration: HostsInfoConfiguration,
                 dynamic_variable_generator: DynamicVariableGenerator):
        self.hosts_info_configuration = hosts_info_configuration
        self.dynamic_variable_generator = dynamic_variable_generator
        super().__init__(name)

    def _generate_hosts_content(self, ambari_server_host):
        parsed_hosts = self.hosts_info_configuration.get_hosts_info()
        parsed_hosts = [p.split() for p in parsed_hosts]
        hosts_dict = {hostname: (ip, passwd) for ip, hostname, passwd in parsed_hosts}
        node_groups = {"ambari-server": [ambari_server_host]}
        for host_info in parsed_hosts:
            ip, hostname, passwd = host_info
            node_groups.setdefault("hadoop-cluster", []).append(hostname)

        hosts_content = ""
        for group, hosts in node_groups.items():
            hosts_content += "[{}]\n".format(group)
            for host_name in hosts:
                if host_name not in hosts_dict:
                    raise InvalidConfigurationException(f"Host '{host_name}' not found in parsed hosts.")
                ip, passwd = hosts_dict[host_name]
                hosts_content += "{} ansible_host={} ansible_ssh_pass={}\n".format(host_name, ip, passwd)
            hosts_content += "\n"

        ansible_user = self.hosts_info_configuration.get_user()
        hosts_content += "[all:vars]\nansible_user={}\n".format(ansible_user)

        return hosts_content

    def get_rendered_conf(self):
        rendered_conf_dict = self.dynamic_variable_generator.generate()
        return rendered_conf_dict

    def generate_ansible_hosts(self):
        rendered_conf_dict = self.get_rendered_conf()
        ambari_server_host = rendered_conf_dict.get("ambari_server_host")
        hosts_content = self._generate_hosts_content(ambari_server_host)
        self.set_conf(hosts_content)

    def get_conf(self):
        self.generate_ansible_hosts()
        return self.conf

    def save(self):
        self.set_path(os.path.join(ANSIBLE_PRJ_DIR, "inventory")).set_format(FileManager.FileType.RAW)
        super().save()
