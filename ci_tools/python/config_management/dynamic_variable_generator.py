import socket

from python.config_management.template_renderer import *


class DynamicVariableGenerator:
    def __init__(self, advanced_conf):
        self.advanced_conf = advanced_conf
        self.group_services = self.advanced_conf.get("group_services")
        self.hosts_groups = self.advanced_conf.get("host_groups")
        self.template_renderer = TemplateRenderer()

    def generate(self):
        conf = self.generate_dynamic_j2template_variables()
        return conf

    def get_kdc_server_host(self):
        if len(self.advanced_conf.get("security_options")["external_hostname"].strip()) > 0:
            return self.advanced_conf.get("security_options")["external_hostname"]
        else:
            ambari_server_host = self.get_ambari_server_host()
            return ambari_server_host

    def get_ambari_server_host(self):
        ambari_server_group = None
        for group_name, services in self.group_services.items():
            if "AMBARI_SERVER" in services:
                ambari_server_group = group_name
                break
        if ambari_server_group:
            ambari_server_host = self.hosts_groups[ambari_server_group][0]
            return ambari_server_host
        else:
            raise InvalidConfigurationException

    def generate_hosts_groups_variables(self):
        group_hosts = {}
        hosts_groups_variables = {}

        for group_name, hosts in self.hosts_groups.items():
            group_hosts[group_name] = hosts

        for group_name, group_services in self.group_services.items():
            if "NAMENODE" in group_services:
                hosts_groups_variables.setdefault("namenode_hosts", []).extend(group_hosts[group_name])
            if "ZKFC" in group_services:
                hosts_groups_variables.setdefault("zkfc_hosts", []).extend(group_hosts[group_name])
            if "RESOURCEMANAGER" in group_services:
                hosts_groups_variables.setdefault("resourcemanager_hosts", []).extend(group_hosts[group_name])
            if "JOURNALNODE" in group_services:
                hosts_groups_variables.setdefault("journalnode_hosts", []).extend(group_hosts[group_name])
            if "ZOOKEEPER_SERVER" in group_services:
                hosts_groups_variables.setdefault("zookeeper_hosts", []).extend(group_hosts[group_name])
            if "HIVE_SERVER" in group_services or "HIVE_METASTORE" in group_services:
                hosts_groups_variables.setdefault("hiveserver_hosts", []).extend(group_hosts[group_name])
            if "KAFKA_BROKER" in group_services:
                hosts_groups_variables.setdefault("kafka_hosts", []).extend(group_hosts[group_name])
            if "RANGER_ADMIN" in group_services:
                hosts_groups_variables.setdefault("rangeradmin_hosts", []).extend(group_hosts[group_name])
            if "RANGER_KMS_SERVER" in group_services:
                hosts_groups_variables.setdefault("rangerkms_hosts", []).extend(group_hosts[group_name])
            if "SOLR_SERVER" in group_services:
                hosts_groups_variables.setdefault("solr_hosts", []).extend(group_hosts[group_name])

        for k, v in hosts_groups_variables.items():
            hosts_groups_variables[k] = list(set(v))

        return hosts_groups_variables

    def generate_dynamic_j2template_variables(self):
        str_conf = self.advanced_conf.get_str_conf()
        # 原始的conf, 存在很懂变量
        # 动态生成一些蓝图的需要用到的namenode_hosts 等变量
        ambari_repo_url = self._generate_ambari_repo_url()
        # 根据用户配置动态生成一些变量
        extra_vars = {
            "ntp_server_hostname": self._generate_ntp_server_hostname(),
            "hadoop_base_dir": self.advanced_conf.get("data_dirs")[0],
            "kdc_hostname": self.get_kdc_server_host(),
            "database_hostname": self._generate_database_host(),
            "ambari_server_host": self.get_ambari_server_host(),
            "ambari_repo_url": ambari_repo_url
        }
        conf_j2_context = self.advanced_conf.get_conf()
        conf_j2_context.update(extra_vars)
        hosts_groups_variables = self.generate_hosts_groups_variables()
        rendered_conf_vars = self.template_renderer.render_template(str_conf, conf_j2_context).decode_result(
            decoder="yaml")
        rendered_conf_vars.update(hosts_groups_variables)
        rendered_conf_vars.update(extra_vars)
        if not rendered_conf_vars["repos"]:
            rendered_conf_vars["repos"] = []
        if not self.advanced_conf.is_ambari_repo_configured():
            rendered_conf_vars["repos"].append({"name": "ambari_repo", "url": ambari_repo_url})
        return rendered_conf_vars

    def _generate_ntp_server_hostname(self):
        if len(self.advanced_conf.get("external_ntp_server_hostname").strip()) > 0:
            return self.advanced_conf.get("external_ntp_server_hostname").strip()
        else:
            ambari_server_host = self.get_ambari_server_host()
            return ambari_server_host

    def _generate_database_host(self):
        ambari_host = self.get_ambari_server_host()
        external_database_server_ip = self.advanced_conf.get("database_options")["external_hostname"]
        if len(external_database_server_ip.strip()) == 0:
            database_host = ambari_host
        else:
            database_host = self.advanced_conf.get("database_options")["external_hostname"]
        return database_host

    def get_ip_address(self):
        try:
            # 创建一个UDP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 连接到一个公共的域名，此处使用Google的域名
            sock.connect(("8.8.8.8", 80))
            # 获取本地套接字的IP地址
            ip_address = sock.getsockname()[0]
            return ip_address
        except socket.error:
            return "Unable to retrieve IP address"

    def _generate_ambari_repo_url(self):
        ipaddress = self.get_ip_address()
        if not self.advanced_conf.is_ambari_repo_configured():
            ambari_repo_rl = f"http://{ipaddress}:8881/repository/yum/udh3"
            # todo 在 conf 中生成 {"name": "ambari_repo", "url": ambari_repo_rl}
        else:
            repos = self.advanced_conf.get('repos', [])
            for repo_item in repos:
                if "ambari_repo" == repo_item["name"]:
                    return repo_item["url"]
        return ambari_repo_rl

