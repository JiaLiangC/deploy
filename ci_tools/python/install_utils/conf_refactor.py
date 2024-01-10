# -*- coding: UTF-8 -*-
import json
import re
# import imp
import yaml
from jinja2 import Template
from python.common.basic_logger import get_logger
from python.common.constants import *
import os
import copy
from python.utils.os_utils import *
import socket
from ipaddress import ip_address
from python.install_utils.topology_manager import *

logger = get_logger()


class InvalidConfigurationException(Exception):
    pass


class Parser:

    def parse(self):
        pass

    def _expand_range(self, pattern):
        match = re.search(r'\[(\d+)-(\d+)]', pattern)
        if match:
            prefix = pattern[:match.start()]
            start = int(match.group(1))
            end = int(match.group(2))
            suffix = pattern[match.end():]
            return [f'{prefix}{i}{suffix}' for i in range(start, end + 1)]
        else:
            return [pattern]


class HostsInfoParser(Parser):
    def __init__(self, raw_conf):
        self.raw_conf = raw_conf

    def parse(self):

        hosts_configurations = self.raw_conf["hosts"]
        user = self.raw_conf["user"]
        parsed_configs = []

        for config in hosts_configurations:
            if len(config.split()) != 3:
                raise InvalidConfigurationException

            if '[' in config:
                hostname_part, ip_part, password = config.split()
                hosts = []
                ips = []
                if '[' in hostname_part:
                    hosts = self._expand_range(hostname_part)
                if '[' in ip_part:
                    ips = self._expand_range(ip_part)
                else:
                    raise InvalidConfigurationException

                if len(hosts) != len(ips):
                    raise InvalidConfigurationException("Configuration is invalid")
                for index, ip in enumerate(ips):
                    parsed_configs.append((hosts[index], ip, password))
            else:

                parsed_configs.append(tuple(config.split()))

        return parsed_configs, user


class ComponentTopologyParser(Parser):
    def __init__(self, raw_conf):
        self.raw_conf = raw_conf

    def parse(self):
        host_groups_conf = self.raw_conf["host_groups"]
        group_services_conf = self.raw_conf["group_services"]
        host_groups = {}
        host_group_services = group_services_conf

        for group_name, group_hosts in host_groups_conf.items():
            if group_name not in host_groups:
                host_groups[group_name] = []

            if isinstance(group_hosts, list):
                for host_name in group_hosts:
                    host_groups[group_name].append(host_name)
            else:
                hosts = self._expand_range(group_hosts)
                host_groups[group_name].extend(hosts)

        return host_groups, host_group_services


class Validator:
    def __init__(self):
        self.err_messages = []

    def validate(self):
        pass


# Define Validator classes
class TopologyValidator(Validator):
    def __init__(self, raw_conf):
        super().__init__()
        self.host_groups = raw_conf["host_groups"]
        self.host_group_services = raw_conf["group_services"]
        self.pattern_rules = self._default_pattern_rules()

    def _default_pattern_rules(self):
        return {
            "namenode": [
                {
                    "NAMENODE": {"min_instances": 2, "max_instances": 2,
                                 "desc": "hdfs 高可用部署模式必须满足 NAMENODE 组件数目为2; ZKFC 为2 且每个ZKFC 必须和 NAMENODE 部署在一起同一个机器; JOURNALNODE 至少大于等于3，且数目为奇数; 并且HA 模式不能选择 SECONDARY_NAMENODE"},
                    "ZKFC": {"min_instances": 2, "max_instances": 2},
                    "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
                },
                {
                    "NAMENODE": {"min_instances": 1, "max_instances": 1,
                                 "desc": "hdfs 普通部署模式需要部署1个 NAMENODE 和一个 SECONDARY_NAMENODE。ZKFC 和 JOURNALNODE 在该模式下不可选择"},
                    "SECONDARY_NAMENODE": {"min_instances": 1, "max_instances": 1},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "ZKFC": {"min_instances": 0, "max_instances": 0},
                    "JOURNALNODE": {"min_instances": 0, "max_instances": 0}
                }],
            "hive": {
                "HIVE_METASTORE": {"min_instances": 1, "max_instances": 1,
                                   "desc": "选择部署hive 组件时，HIVE_METASTORE只能部署一个，HIVE_SERVER 部署数量必须大于等于1，WEBHCAT_SERVER部署数量只能为1个"},
                "HIVE_SERVER": {"min_instances": 1, "max_instances": None},
                "WEBHCAT_SERVER": {"min_instances": 1, "max_instances": 1},
            },
            "yarn": {
                "RESOURCEMANAGER": {"min_instances": 1, "max_instances": 2,
                                    "desc": "选择部署yarn 时，RESOURCEMANAGER数量最少为1，最大为2。当选择为2时，RESOURCEMANAGER 会开启高可用模式。NODEMANAGER数量大于等于1，HISTORYSERVER 只能部署1台。"},
                "APP_TIMELINE_SERVER": {"min_instances": 1, "max_instances": 1},
                "YARN_REGISTRY_DNS": {"min_instances": 1, "max_instances": 1},
                "TIMELINE_READER": {"min_instances": 1, "max_instances": 1},
                "NODEMANAGER": {"min_instances": 1, "max_instances": None},
                "HISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "kafka": {
                "KAFKA_BROKER": {"min_instances": 1, "max_instances": None,
                                 "desc": "选择部署kafka 时，KAFKA_BROKER 部署数量大于等于1"},
            },
            "ambari": {
                "AMBARI_SERVER": {"min_instances": 1, "max_instances": 1,
                                  "desc": "AMBARI_SERVER 为必须选择部署的用来管理大数据集群的基础组件，只能部署一台"},
            },
            "hbase": {
                "HBASE_MASTER": {"min_instances": 1, "max_instances": 2,
                                 "desc": "选择部署hbase 时，HBASE_MASTER 数量为1-2，2台时，即为hbase master 的高可用模式。HBASE_REGIONSERVER 部署必须大于等于1台"},
                "HBASE_REGIONSERVER": {"min_instances": 1, "max_instances": None},
            },
            "ranger": {
                "RANGER_ADMIN": {"min_instances": 1, "max_instances": 2,
                                 "desc": "选择部署ranger 时，RANGER_ADMIN 数量为1-2，2台时，RANGER_ADMIN 的高可用模式，RANGER_TAGSYNC和RANGER_USERSYNC只能部署一台 "},
                "RANGER_TAGSYNC": {"min_instances": 1, "max_instances": 1},
                "RANGER_USERSYNC": {"min_instances": 1, "max_instances": 1},
            },
            "spark": {
                "SPARK_JOBHISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                           "desc": "选择部署spark时，SPARK_JOBHISTORYSERVER和SPARK_THRIFTSERVER 必须且只能各部署一台"},
                "SPARK_THRIFTSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "zookeeper": {
                "ZOOKEEPER_SERVER": {"min_instances": 3, "max_instances": None, "odd_only": True,
                                     "desc": "选择部署zookeeper时，最少部署3台，且部署数量必须为奇数"},
            },
            "flink": {
                "FLINK_HISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                        "desc": "选择部署flink时,FLINK_HISTORYSERVER 必须且只能各部署一台"},
            },
            "infra_solr": {
                "INFRA_SOLR": {"min_instances": 1, "max_instances": None,
                               "desc": "选择部署infra_solr时,INFRA_SOLR最少部署一台"},
            },
            "solr": {
                "SOLR_SERVER": {"min_instances": 1, "max_instances": None,
                                "desc": "选择部署solr时,SOLR_SERVER 最少部署一台"},
            },
            "ambari_metrics": {
                "METRICS_COLLECTOR": {"min_instances": 1, "max_instances": 1,
                                      "desc": "选择部署ambari_metrics时,METRICS_COLLECTOR 必须且只能各部署一台"},
                "METRICS_GRAFANA": {"min_instances": 1, "max_instances": 1,
                                    "desc": "选择部署ambari_metrics时,METRICS_GRAFANA 必须且只能各部署一台"}
            }
        }

    def check_pattern(self, service_rules, service_counter):
        messages = []
        tmp_desc = None
        for rule_service_name, rule in service_rules.items():

            service_count = service_counter.get(rule_service_name, 0)
            if rule.get("desc", None):
                tmp_desc = rule.get("desc")

            if service_count < rule["min_instances"]:
                messages.append(
                    "{} 的实例数 {} 小于最小实例数 {}".format(rule_service_name, service_count, rule['min_instances']))

            if rule["max_instances"] is not None and service_count > rule["max_instances"]:
                messages.append(
                    "{} 的实例数 {} 大于最大实例数 {}".format(rule_service_name, service_count, rule['max_instances']))

            if rule.get("odd_only") and service_count % 2 == 0:
                messages.append("{} 的实例数 {} 不是奇数".format(rule_service_name, service_count))

        if tmp_desc and len(tmp_desc) > 0 and len(messages) > 0:
            messages.append(tmp_desc)
        return messages

    # 这个函数是用来检查组件拓扑的。
    # 函数首先获取需要安装的服务和服务计数器。然后，定义一个模式规则字典，其中包含了各种服务及其对应的组件要求，如最小实例数、最大实例数等。
    # 接下来，函数遍历需要安装的所有服务，如果服务在模式规则中，就进行规则检查。如果服务的组件数量不满足规则要求，就将错误信息添加到消息列表中。
    # 最后，如果消息列表中有内容，说明有不满足规则的服务，函数返回False和错误信息；否则，返回True和None。

    # host_group_services example {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # host_groups example {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']}
    # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如同时部署了ZKFC 和 secondary 到一个 group 中  {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如namenode 高可用模式下没有在group1 数组中部署放置JOURNALNODE
    def validate(self):
        services_need_install, service_counter = self.get_service_distribution()
        checked_services = []
        messages = self.check_pattern(self.pattern_rules["ambari"], service_counter)
        self.err_messages.extend(messages)

        for service_name in services_need_install:
            for pattern_key, service_rules in self.pattern_rules.items():
                if pattern_key in checked_services:
                    continue

                if isinstance(service_rules, dict):
                    rule_services = service_rules.keys()
                    # 只要发现一个组件就触发规则检测
                    if service_name in rule_services:
                        # 规则集中的每个组件都要满足要求，因此必须迭代所有的rule
                        messages = self.check_pattern(service_rules, service_counter)
                        self.err_messages.extend(messages)
                        checked_services.append(pattern_key)
                elif isinstance(service_rules, list):
                    # 检测 namanode 的两种部署模式, 只能满足其中一种模式, 两个pattern 定义的时候条件都是互斥的，不可能出现同时满足两个pattern的情况。
                    #
                    pattern_res = []
                    tmp_err = []
                    for service_rules_item in service_rules:
                        if service_name in service_rules_item.keys():
                            messages = self.check_pattern(service_rules_item, service_counter)
                            if len(messages) <= 0:  # one pattern 忙
                                pattern_res.append(True)
                            else:
                                tmp_err.extend(messages)

                    if len(tmp_err) > 0 and True not in pattern_res:
                        self.err_messages.extend(tmp_err)
                        checked_services.append(pattern_key)
        return self

    def get_service_distribution(self):
        service_counter = {}
        services = []
        group_hosts = {}
        for group_name, hosts in self.host_groups.items():
            group_hosts[group_name] = hosts

        for group_name, host_components in self.host_group_services.items():
            services.extend(host_components)
            for service_name in host_components:
                hosts_count = len(group_hosts[group_name])
                service_counter[service_name] = service_counter.setdefault(service_name, 0) + hosts_count
        unique_services = list(set(services))
        return unique_services, service_counter

    def _count_services(self, host_group_services):
        service_counter = {}
        for services in host_group_services.values():
            for service in services:
                service_counter[service] = service_counter.get(service, 0) + 1
        return service_counter


class GroupConsistencyValidator(Validator):

    def __init__(self, raw_conf, hosts_info):
        super().__init__()
        self.hosts_info = hosts_info
        self.host_groups = raw_conf["host_groups"]
        self.host_group_services = raw_conf["group_services"]

    def validate(self):
        parsed_hosts, user = self.hosts_info
        conf_defined_hosts = {}
        host_groups_group_names = []
        host_group_services_group_names = []

        for host_info in parsed_hosts:
            ip = host_info[0]
            hostname = host_info[1]
            passwd = host_info[2]
            conf_defined_hosts[hostname] = ip

        for group_name, group_hosts in self.host_groups.items():
            host_groups_group_names.append(group_name)
            if len(list(set(group_hosts))) != len(group_hosts):
                self.err_messages.append("每个机器名只能在同一个组内列出一次")
            for host_name in group_hosts:
                if host_name not in conf_defined_hosts:
                    self.err_messages.append(f"{host_name} 在  conf.yml 定义了，但是没在 hosts.yml 中配置")

        for group_name, services in self.host_group_services.items():
            host_group_services_group_names.append(group_name)
            duplicated_services = [sname for sname in services if services.count(sname) >= 2]
            if len(duplicated_services) > 0:
                self.err_messages.append(
                    f"每个被部署组件名只能在同一个组内列出一次,请检查如下组的配置 组: {group_name} , 组件名: {' '.join(list(set(duplicated_services)))}")

            for service_name in services:
                is_supported = ServiceMap().is_service_supported(service_name)
                if not is_supported:
                    self.err_messages.append("{} 选择部署的该组件目前不支持".format(service_name))

        if not (len(host_groups_group_names) == len(host_group_services_group_names) and set(
                host_groups_group_names) == set(host_group_services_group_names)):
            self.err_messages.append("host_groups 配置和group_services 中的组名不一致")

        return self


class HostsInfoValidator(Validator):
    def __init__(self, hosts_info):
        super().__init__()
        self.hosts_info = hosts_info

    def validate(self):
        parsed_hosts, user = self.hosts_info

        # Validate IP addresses
        for host in parsed_hosts:
            ip, hostname, _ = host
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


class FileManager:
    @staticmethod
    def read_file(file_path):
        with open(file_path, 'r') as file:
            return file.read()

    @staticmethod
    def write_file(file_path, content):
        with open(file_path, 'w') as file:
            file.write(content)

    @staticmethod
    def read_json(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    @staticmethod
    def write_json(file_path, data):
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def read_yaml(file_path):
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)

    @staticmethod
    def write_yaml(file_path, data):
        with open(file_path, 'w') as file:
            yaml.dump(data, file)


class TemplateRenderer:
    def __init__(self):
        self.rendered_result = None

    def render_template(self, template_str, context):
        # template_str = FileManager.read_file(self.file_path)
        if not template_str:
            return {}
        template = Template(template_str)
        logger.debug(f"Rendering config templates, template_str: {template_str}, context:{context}")
        self.rendered_result = template.render(context)
        return self

    def decode_result(self, decoder="json"):
        if not self.rendered_result:
            raise Exception("render_template first")
        if decoder == "json":
            return json.loads(self.rendered_result)
        elif decoder == "yaml":
            return yaml.safe_load(self.rendered_result)
        else:
            raise ValueError("Unsupported decoder specified")


class DynamicVariableGenerator:
    def __init__(self):
        self.raw_conf = None
        self.group_services = None
        self.hosts_groups = None
        self.template_renderer = TemplateRenderer()

    def lazy_init(self, raw_conf):
        self.raw_conf = raw_conf
        self.group_services = self.raw_conf["group_services"]
        self.hosts_groups = self.raw_conf["host_groups"]

    def generate(self, raw_conf):
        self.lazy_init(raw_conf)
        conf = self.generate_dynamic_j2template_variables()
        return conf

    def get_kdc_server_host(self):
        if len(self.raw_conf["security_options"]["external_hostname"].strip()) > 0:
            return self.raw_conf["security_options"]["external_hostname"]
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
        str_conf = yaml.dump(self.raw_conf)
        # 原始的conf, 存在很懂变量
        conf_j2_context = self.raw_conf

        # 动态生成一些蓝图的需要用到的namenode_hosts 等变量
        hosts_groups_variables = self.generate_hosts_groups_variables()

        # 根据用户配置动态生成一些变量
        extra_vars = {
            "ntp_server_hostname": self._generate_ntp_server_hostname(),
            "hadoop_base_dir": self.raw_conf["data_dirs"][0], "kdc_hostname": self.get_kdc_server_host(),
            "database_hostname": self._generate_database_host(),
            "ambari_server_host": self.get_ambari_server_host()
        }
        conf_j2_context.update(extra_vars)
        rendered_conf_vars = self.template_renderer.render_template(str_conf, conf_j2_context).decode_result(
            decoder="yaml")

        rendered_conf_vars.update(hosts_groups_variables)
        rendered_conf_vars.update(extra_vars)
        return rendered_conf_vars

    def _generate_ntp_server_hostname(self):
        if len(self.raw_conf["external_ntp_server_hostname"].strip()) > 0:
            return self.raw_conf["external_ntp_server_hostname"].strip()
        else:
            ambari_server_host = self.get_ambari_server_host()
            return ambari_server_host

    def _generate_database_host(self):
        ambari_host = self.get_ambari_server_host()
        external_database_server_ip = self.raw_conf["database_options"]["external_hostname"]
        if len(external_database_server_ip.strip()) == 0:
            database_host = ambari_host
        else:
            database_host = self.raw_conf["database_options"]["external_hostname"]
        return database_host

    def _generate_ambari_repo_url(self):
        repos = self.raw_conf.get('repos', [])
        for repo in repos:
            if repo.get('name') == 'ambari_repo':
                return repo.get('url')
        # If Ambari repo URL is not configured, generate one based on the host's IP address
        ip_address = socket.gethostbyname(socket.gethostname())
        return f"http://{ip_address}:8080/path/to/ambari/repo"


# Define Service-related classes
class ServiceMap:
    def __init__(self):
        self.service_map = {
            "hbase": {
                "server": ["HBASE_MASTER", "HBASE_REGIONSERVER"],
                "clients": ["HBASE_CLIENT"]
            },
            "hdfs": {
                "server": ["NAMENODE", "DATANODE", "SECONDARY_NAMENODE", "JOURNALNODE", "ZKFC"],
                "clients": ["HDFS_CLIENT", "MAPREDUCE2_CLIENT"]
            },
            "yarn": {
                "server": ["NODEMANAGER", "RESOURCEMANAGER", "HISTORYSERVER", "APP_TIMELINE_SERVER",
                           "YARN_REGISTRY_DNS",
                           "TIMELINE_READER"],
                "clients": ["YARN_CLIENT"]
            },
            "hive": {
                "server": ["HIVE_METASTORE", "WEBHCAT_SERVER", "HIVE_SERVER"],
                "clients": ["HIVE_CLIENT", "HCAT", "TEZ_CLIENT"]
            },
            "zookeeper": {
                "server": ["ZOOKEEPER_SERVER"],
                "clients": ["ZOOKEEPER_CLIENT"]
            },
            "kafka": {
                "server": ["KAFKA_BROKER", ],
                "clients": []
            },
            "spark": {
                "server": ["SPARK_JOBHISTORYSERVER", "SPARK_THRIFTSERVER"],
                "clients": ["SPARK_CLIENT"]
            },
            "flink": {
                "server": ["FLINK_HISTORYSERVER"],
                "clients": ["FLINK_CLIENT"]
            },
            "ranger": {
                "server": ["RANGER_ADMIN", "RANGER_TAGSYNC", "RANGER_USERSYNC"],
                "clients": []
            },
            "infra_solr": {
                "server": ["INFRA_SOLR"],
                "clients": ["INFRA_SOLR_CLIENT"]
            },
            # 不支持solr 了，没人使用
            # "solr": {
            #     "server": ["SOLR_SERVER"],
            #     "clients": []
            # },
            "ambari": {
                "server": ["AMBARI_SERVER"],
                "clients": []
            },
            "ambari_metrics": {
                "server": ["METRICS_COLLECTOR", "METRICS_GRAFANA"],
                "clients": ["METRICS_MONITOR"]
            },
            "kerberos": {
                "server": ["KERBEROS_CLIENT"],
                "clients": ["KERBEROS_CLIENT"]
            }
        }

    def is_service_supported(self, service_name):
        for service_key, info in self.service_map.items():
            if service_name in info["server"]:
                return True
        return False

    def get_services(self, service_name):
        if self.is_service_supported(service_name):
            return self.service_map[service_name]
        else:
            return None

    def get_services_map(self):
        return self.service_map


class ServiceValidator:
    def __init__(self, service_map):
        self.service_map = service_map

    def validate_service(self, service_name):
        errors = []
        if not self.service_map.is_service_supported(service_name):
            errors.append(f"Service '{service_name}' is not supported.")
        # Additional service-specific validation can be added here
        return errors


class ParserFactory:
    _parsers = {
        'hosts_info': HostsInfoParser,
        'component_topology': ComponentTopologyParser,
        # Add other parsers as needed
    }

    @classmethod
    def get_parser(cls, parser_type, conf_data):
        parser_class = cls._parsers.get(parser_type)
        if not parser_class:
            raise ValueError(f"Unknown parser type: {parser_type}")
        return parser_class(conf_data)


# class ValidatorFactory:
#     _validators = {
#         'service': ServiceValidator,
#         'topology': TopologyValidator,
#         'group_consistency': GroupConsistencyValidator,
#         'hosts_info': HostsInfoValidator,
#         # Add other validators as needed
#     }
#
#     @classmethod
#     def get_validator(cls, validator_type, conf_data, parsed_data=None):
#         validator_class = cls._validators.get(validator_type)
#         if not validator_class:
#             raise ValueError(f"Unknown validator type: {validator_type}")
#         return validator_class(conf_data, parsed_data) if parsed_data else validator_class(conf_data)

class ValidatorFactory:
    _validators = {
        'service': ServiceValidator,
        'topology': TopologyValidator,
        'group_consistency': GroupConsistencyValidator,
        'hosts_info': HostsInfoValidator,
        # Add other validators as needed
    }

    @classmethod
    def get_validator(cls, validator_type, conf_data, parsed_data=None):
        if validator_type == 'service':
            return ServiceValidator(ServiceMap())
        elif validator_type == 'topology':
            return TopologyValidator(conf_data)
        elif validator_type == 'group_consistency':
            return GroupConsistencyValidator(conf_data, parsed_data)
        elif validator_type == 'hosts_info':
            return HostsInfoValidator(parsed_data)


# Main ConfUtils class using the above components

class ConfigurationLoader:
    def __init__(self, conf_dir):
        self.conf_dir = conf_dir

    def load_conf(self, conf_name):
        file_path = os.path.join(self.conf_dir, conf_name)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(file_path, 'r') as f:
            return yaml.safe_load(f)


class ValidationManager:
    def __init__(self, validators):
        self.validators = validators

    def validate_all(self):
        errors = []
        for validator in self.validators:
            errors.extend(validator.validate().err_messages)
        return errors


class ConfUtils:
    def __init__(self, parser_factory, validator_factory, conf_loader):
        self.parser_factory = parser_factory
        self.validator_factory = validator_factory
        self.conf_loader = conf_loader
        self.dynamic_variable_generator = None
        self.confs = {}
        self.conf = {}
        self.hosts_conf = {}
        self.parsers = {}
        self.validators = {}

    def load_all_confs(self):
        self.confs['HOSTS_CONF'] = self.conf_loader.load_conf(HOSTS_CONF_NAME)
        self.confs['COMPONENT_TOPOLOGY_CONF'] = self.conf_loader.load_conf(CONF_NAME)
        self.confs['BASE_CONF'] = self.conf_loader.load_conf(BASE_CONF_NAME)
        # Load other configurations as needed

    def initialize_parsers(self):
        self.parsers['hosts_info'] = self.parser_factory.get_parser('hosts_info', self.confs['HOSTS_CONF'])
        self.parsers['component_topology'] = self.parser_factory.get_parser('component_topology',
                                                                            self.confs['COMPONENT_TOPOLOGY_CONF'])
        # Initialize other parsers as needed

    def initialize_validators(self):
        hosts_info_parsed = self.parsers['hosts_info'].parse()
        self.validators['topology'] = self.validator_factory.get_validator('topology',
                                                                           self.confs['COMPONENT_TOPOLOGY_CONF'])
        self.validators['group_consistency'] = self.validator_factory.get_validator('group_consistency', self.confs[
            'COMPONENT_TOPOLOGY_CONF'], hosts_info_parsed)
        self.validators['hosts_info'] = self.validator_factory.get_validator('hosts_info', None, hosts_info_parsed)

    def parse_conf(self):
        # Parse hosts information
        hosts_info = self.parsers['hosts_info'].parse()
        self.hosts_conf = hosts_info

        print(hosts_info)
        # Parse component topology
        host_groups, host_group_services = self.parsers['component_topology'].parse()
        print(host_groups, host_group_services)
        cf = self.generate_dynamic_variables()
        self.conf.update(cf)
        print(cf)
        # Combine all parts to produce the final configuration


    def validate_conf(self):
        validation_manager = ValidationManager(self.validators.values())
        errors = validation_manager.validate_all()
        if errors:
            error_messages = "\n".join(errors)
            raise ValueError(f"Configuration validation failed with the following errors:\n{error_messages}")

    def get_conf(self):
        # Parse and validate the configuration if it hasn't been done yet
        #if not self.conf:
        self.parse_conf()
        self.validate_conf()

        # Return the final configuration data
        return self.conf

    def generate_dynamic_variables(self):
        if not self.dynamic_variable_generator:
            self.dynamic_variable_generator = DynamicVariableGenerator()
        conf_data = self.conf_loader.load_conf(CONF_NAME)
        dynamic_variables = self.dynamic_variable_generator.generate(conf_data)
        return dynamic_variables

    def get_hosts_names(self):
        hosts_info = self.parsers['hosts_info'].parse()
        hosts_names = []
        parsed_hosts, user = hosts_info
        for host_info in parsed_hosts:
            hostname = host_info[1]
            hosts_names.append(hostname)
        return hosts_names

    def is_ambari_repo_configured(self):
        repos = self.conf["repos"]
        if len(repos) > 0:
            for repo_item in repos:
                if "ambari_repo" == repo_item["name"]:
                    return True
        return False

    def generate_conf(self, yaml_dict, dest_file, source_file=None, method="new"):
        supported_methods = ["new", "prepend", "replace"]
        assert method in supported_methods
        final_yaml_str = ""

        if method == "new":
            final_yaml_str = yaml.dump(yaml_dict, default_flow_style=None, sort_keys=False)
        elif method == "prepend":
            try:
                with open(source_file, 'r') as file:
                    existing_data = file.read()
            except FileNotFoundError:
                existing_data = ""
            new_yaml_str = yaml.dump(yaml_dict, default_flow_style=None, sort_keys=False)

            final_yaml_str = new_yaml_str + "\n" + existing_data
        elif method == "replace":
            try:
                with open(source_file, 'r') as file:
                    existing_data = file.read()
                    existing_yaml = yaml.safe_load(existing_data)
            except FileNotFoundError:
                existing_yaml = {}

            for k, v in yaml_dict.items():
                existing_yaml[k] = v

            final_yaml_str = yaml.dump(existing_yaml, default_flow_style=None, sort_keys=False)

        with open(dest_file, 'w') as file:
            file.write(final_yaml_str)

    def generate_deploy_conf(self):
        yaml_data = self.confs['BASE_CONF']
        print(yaml_data)
        conf_yaml_data = {
            "default_password": yaml_data["default_password"],
            "data_dirs": yaml_data["data_dirs"],
            "repos": yaml_data["repos"]
        }

        hosts_info_yaml_data = {
            "user": yaml_data["user"],
            "hosts": yaml_data["hosts"]
        }

        hosts_info_conf_file = os.path.join(CONF_DIR, HOSTS_CONF_NAME)
        self.generate_conf(hosts_info_yaml_data, hosts_info_conf_file, method="new")

        conf_fie = os.path.join(CONF_DIR, CONF_NAME)
        conf_tpl_file = GET_CONF_TPL_NAME(conf_fie)
        topology_manager = TopologyManager(self.get_hosts_names)
        topology = topology_manager.generate_topology()
        topology.update(conf_yaml_data)
        self.generate_conf(topology, conf_fie, source_file=conf_tpl_file, method="prepend")


class ConfigurationHandler:
    def __init__(self, conf):
        self.conf = conf
        self.get_ambari_repo()
        self.validate()

    def get_ambari_repo(self):
        ambari_repo = None
        repos = self.conf["repos"]
        if len(repos) > 0:
            for repo_item in repos:
                if "ambari_repo" == repo_item["name"]:
                    ambari_repo = repo_item["url"]
                    break
        else:
            raise InvalidConfigurationException("ambari_repo not configured")
        if not ambari_repo:
            ambari_repo = repos[0]["url"]

        self.conf.update({"ambari_repo_url": ambari_repo})

    def get(self, key, default=None):
        try:
            return self.conf[key]
        except KeyError:
            if default is not None:
                return default
            raise InvalidConfigurationException(f"Configuration key '{key}' is missing.")

    def validate(self):
        required_keys = ["group_services", "repos", "host_groups", "security_options", "ambari_options",
                         "blueprint_name"]
        for key in required_keys:
            if key not in self.conf:
                raise InvalidConfigurationException(f"Required configuration key '{key}' is missing.")


class ServiceManager:
    def __init__(self, config_handler):
        self.config_handler = config_handler

    def get_service_key_from_service(self, service_name):
        for service_key, service_info in ServiceMap().get_services_map().items():
            if service_name in service_info["server"]:
                return service_key
        raise InvalidConfigurationException(f"Service '{service_name}' not found in services map.")

    def get_services_need_install(self):
        group_services = self.config_handler.get("group_services")
        services = []
        for group_name, host_components in group_services.items():
            services.extend(host_components)
        return list(set(services))

    def get_service_clients_need_install(self, services):
        clients = []
        for service_name in services:
            service_key = self.get_service_key_from_service(service_name)
            service_info = ServiceMap().get_services(service_key)
            if service_info and "clients" in service_info:
                clients.extend(service_info["clients"])
        return list(set(clients))


class FileManager:
    @staticmethod
    def read_file(file_path):
        with open(file_path, 'r') as file:
            return file.read()

    @staticmethod
    def write_file(file_path, content):
        with open(file_path, 'w') as file:
            file.write(content)

    @staticmethod
    def read_json(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)

    @staticmethod
    def write_json(file_path, data):
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def read_yaml(file_path):
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)

    @staticmethod
    def write_yaml(file_path, data):
        with open(file_path, 'w') as file:
            yaml.dump(data, file)


# Initialize with ConfigurationHandler and ServiceManager instances
# Methods to generate blueprint configurations and host groups
class BlueprintGenerator:
    def __init__(self, config_handler, service_manager):
        self.config_handler = config_handler
        self.service_manager = service_manager

    def generate_blueprint_configurations(self):
        services_need_install = self.service_manager.get_services_need_install()
        configurations = []
        processed_services = []

        for service_name in services_need_install:
            service_key = self.service_manager.get_service_key_from_service(service_name)
            if service_key in processed_services:
                continue

            template_render = TemplateRenderer()
            tpl_str = FileManager.read_file(self.get_conf_j2template_path(service_name))
            if not tpl_str:
                # 有的配置模版为空白
                continue

            service_confs = template_render.render_template(
                tpl_str,
                self.config_handler.conf).decode_result(decoder="json")

            if service_confs:
                configurations.extend([{k: v} for k, v in service_confs.items() if isinstance(v, dict)])
            else:
                logger.error(f"Error in configuration template for service {service_name}")

            processed_services.append(service_key)

        return configurations

    def generate_blueprint_host_groups(self):
        conf = self.config_handler.conf
        host_groups = []
        services_need_install = self.service_manager.get_services_need_install()
        all_services_clients = self.service_manager.get_service_clients_need_install(services_need_install)

        for group_name, services in conf["group_services"].items():
            group_services = list(set(services + all_services_clients))
            host_group_components_config = [{'name': service_name} for service_name in group_services]

            host_group = {
                "name": group_name,
                "configurations": [],
                "cardinality": "1",
                "components": host_group_components_config
            }
            host_groups.append(host_group)

        return host_groups

    def get_conf_j2template_path(self, service_name):
        service_key = self.service_manager.get_service_key_from_service(service_name)
        file_name = f"{service_key}_configuration.json.j2"
        return os.path.join(CLUSTER_TEMPLATES_DIR, file_name)


# Initialize with BlueprintGenerator, TemplateRenderer, and FileManager instances
# Methods to generate Ambari blueprint and cluster template
class AmbariBlueprintBuilder:
    def __init__(self, blueprint_generator, file_manager):
        self.blueprint_generator = blueprint_generator
        self.file_manager = file_manager

    def generate_ambari_blueprint(self, configurations, host_groups):
        security = self.blueprint_generator.config_handler.get("security")
        blueprint_security = "KERBEROS" if security.strip().lower() != "none" else "NONE"
        ambari_repo_url = self.blueprint_generator.config_handler.get("ambari_repo_url")

        j2_context = {
            "blueprint_security": blueprint_security,
            "ambari_blueprint_configurations": json.dumps(configurations),
            "ambari_blueprint_host_groups": json.dumps(host_groups),
            "ambari_repo_url": ambari_repo_url,
        }

        template_renderer = TemplateRenderer(
            # file_path=os.path.join(CLUSTER_TEMPLATES_DIR, "base_blueprint.json.j2"),
            # context=j2_context
        )

        blueprint_json = template_renderer.render_template(
            FileManager.read_file(os.path.join(CLUSTER_TEMPLATES_DIR, "base_blueprint.json.j2")),
            j2_context).decode_result()

        self.file_manager.write_json(
            file_path=os.path.join(BLUEPRINT_FILES_DIR, "blueprint.json"),
            data=blueprint_json
        )

    def generate_ambari_cluster_template(self):
        conf = self.blueprint_generator.config_handler.conf
        security = conf["security"]
        kerberos_admin_principal = f"{conf['security_options']['admin_principal']}@{conf['security_options']['realm']}"
        kerberos_admin_password = conf["security_options"]["admin_password"]
        ambari_cluster_template_host_groups = []

        for group_name, group_hosts in conf["host_groups"].items():
            hosts = [{'fqdn': host} for host in group_hosts]
            ambari_cluster_template_host_groups.append({
                "name": group_name,
                "hosts": hosts
            })

        cluster_template = {
            "blueprint": conf["blueprint_name"],
            "config_recommendation_strategy": conf["ambari_options"]["config_recommendation_strategy"],
            "default_password": conf["default_password"],
            "host_groups": ambari_cluster_template_host_groups,
        }

        if security and security == "mit-kdc":
            cluster_template["credentials"] = [{
                "alias": "kdc.admin.credential",
                "principal": kerberos_admin_principal,
                "key": kerberos_admin_password,
                "type": "TEMPORARY"
            }]
            cluster_template["security"] = {"type": "KERBEROS"}

        self.file_manager.write_json(
            file_path=os.path.join(BLUEPRINT_FILES_DIR, "cluster_template.json"),
            data=cluster_template
        )


# Initialize with ConfigurationHandler and FileManager instances
# Methods to generate Ansible variables file and hosts file
class AnsibleFileManager:
    def __init__(self, config_handler, file_manager):
        self.config_handler = config_handler
        self.file_manager = file_manager

    def generate_ansible_variables_file(self):
        variables = copy.deepcopy(self.config_handler.conf)
        ambari_repo_url = self.config_handler.get("ambari_repo_url")
        variables["ambari_repo_url"] = ambari_repo_url
        for key in ["host_groups", "group_services"]:
            variables.pop(key, None)

        variables_file_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/group_vars/all')
        self.file_manager.write_yaml(variables_file_path, variables)

    def generate_ansible_hosts(self,hosts_conf):
        conf = self.config_handler.conf
        parsed_hosts, user = hosts_conf
        ambari_server_host = conf["ambari_server_host"]
        host_groups = conf["host_groups"]

        hosts_content = self._generate_hosts_content(parsed_hosts, user, host_groups, ambari_server_host)
        ansible_user = user

        hosts_content += "[all:vars]\nansible_user={}\n".format(ansible_user)
        hosts_path = os.path.join(ANSIBLE_PRJ_DIR, "inventory", "hosts")
        self.file_manager.write_file(hosts_path, hosts_content)

    def _generate_hosts_content(self, parsed_hosts, user, host_groups, ambari_server_host):
        hosts_dict = {hostname: (ip, passwd) for ip, hostname, passwd in parsed_hosts}
        node_groups = {"ambari-server": [ambari_server_host]}
        for group_name, hosts in host_groups.items():
            node_groups.setdefault("hadoop-cluster", []).extend(hosts)

        hosts_content = ""
        for group, hosts in node_groups.items():
            hosts_content += "[{}]\n".format(group)
            for host_name in hosts:
                if host_name not in hosts_dict:
                    raise InvalidConfigurationException(f"Host '{host_name}' not found in parsed hosts.")
                ip, passwd = hosts_dict[host_name]
                hosts_content += "{} ansible_host={} ansible_ssh_pass={}\n".format(host_name, ip, passwd)
            hosts_content += "\n"

        return hosts_content


# Initialize with conf dictionary
# Compose all above classes and provide a build method to orchestrate the generation process
class BlueprintUtils:
    def __init__(self, conf):
        self.config_handler = ConfigurationHandler(conf)
        self.service_manager = ServiceManager(self.config_handler)
        self.file_manager = FileManager()
        self.blueprint_generator = BlueprintGenerator(self.config_handler, self.service_manager)
        self.ambari_blueprint_builder = AmbariBlueprintBuilder(self.blueprint_generator, self.file_manager)
        self.ansible_file_manager = AnsibleFileManager(self.config_handler, self.file_manager)

    def build(self,hosts_conf):
        blueprint_configurations = self.blueprint_generator.generate_blueprint_configurations()
        blueprint_service_host_groups = self.blueprint_generator.generate_blueprint_host_groups()
        self.ambari_blueprint_builder.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        self.ambari_blueprint_builder.generate_ambari_cluster_template()
        self.ansible_file_manager.generate_ansible_variables_file()
        self.ansible_file_manager.generate_ansible_hosts(hosts_conf)


# Main execution function
def main():
    conf_utils = ConfUtils(ParserFactory, ValidatorFactory, ConfigurationLoader(CONF_DIR))
    conf_utils.load_all_confs()
    conf_utils.initialize_parsers()
    conf_utils.initialize_validators()
    conf_utils.generate_deploy_conf()

    conf = conf_utils.get_conf()
    hosts_conf = conf_utils.hosts_conf
    print(conf)

    blueprint_utils = BlueprintUtils(conf)
    blueprint_utils.build(hosts_conf)
    # blueprint_utils.generate_ansible_hosts(conf, hosts_info, ambari_server_host)


if __name__ == '__main__':
    main()
