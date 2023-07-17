# -*- coding: UTF-8 -*-
import json
import re
import os
import sys
import imp
import yaml
from jinja2 import Template, Undefined


class InvalidConfigurationException(Exception):
    pass


# 服务支持列表
def services_map():
    service_map = {
        "hbase": {
            "server": ["HBASE_MASTER", "HBASE_REGIONSERVER"],
            "clients": ["HBASE_CLIENT"]
        },
        "hdfs": {
            "server": ["NAMENODE", "DATANODE", "SECONDARY_NAMENODE", "JOURNALNODE", "ZKFC"],
            "clients": ["HDFS_CLIENT", "MAPREDUCE2_CLIENT"]
        },
        "yarn": {
            "server": ["NODEMANAGER", "RESOURCEMANAGER", "HISTORYSERVER", "APP_TIMELINE_SERVER", "YARN_REGISTRY_DNS",
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
        "solr": {
            "server": ["SOLR_SERVER"],
            "clients": []
        },
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
    return service_map


class ConfUtils:
    CONF_DIR = os.path.dirname(os.path.abspath(__file__))
    PLUGINS_DIR = os.path.join(CONF_DIR, 'plugins')

    def __init__(self):
        self.conf_path = ConfUtils.CONF_DIR
        self.conf = None
        self.hosts_info = None
        self.raw_conf = self.load_conf()
        self.err_messages = []

    def get_err_messages(self):
        return self.err_messages

    # 这个函数是用来检查组件拓扑的。
    # 函数首先获取需要安装的服务和服务计数器。然后，定义一个模式规则字典，其中包含了各种服务及其对应的组件要求，如最小实例数、最大实例数等。
    # 接下来，函数遍历需要安装的所有服务，如果服务在模式规则中，就进行规则检查。如果服务的组件数量不满足规则要求，就将错误信息添加到消息列表中。
    # 最后，如果消息列表中有内容，说明有不满足规则的服务，函数返回False和错误信息；否则，返回True和None。
    def check_component_topology(self, host_groups, host_group_services):
        # host_group_services example {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
        # host_groups example {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']}
        # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如同时部署了ZKFC 和 secondary 到一个 group 中  {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
        # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如namenode 高可用模式下没有在group1 数组中部署放置JOURNALNODE
        services_need_install, service_counter = self.get_service_distribution(host_groups, host_group_services)
        checked_services = []
        pattern_rules = {
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
                "APP_TIMELINE_SERVER":  {"min_instances": 1, "max_instances": 1},
                "YARN_REGISTRY_DNS":  {"min_instances": 1, "max_instances": 1},
                "TIMELINE_READER":  {"min_instances": 1, "max_instances": 1},
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
            }
        }

        for service_name in services_need_install:
            for pattern_key, service_rules in pattern_rules.items():
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

    def is_service_supported(self, service_name):
        services = services_map()
        all_services = []
        for service_key, info in services.items():
            all_services.extend(info["server"])

        if service_name not in all_services:
            return False
        return True

    # 1. group 组名必须一致
    # 2. 组件和host 在每个组内只能出现一次
    # 3. group 不能重名
    # 4. 用户选择的组件不在支持列表中

    def check_group_consistency(self, host_groups, host_group_services, hosts_info):
        parsed_hosts, user = hosts_info
        conf_defined_hosts = {}
        host_groups_group_names = []
        host_group_services_group_names = []

        for host_info in parsed_hosts:
            ip = host_info[0]
            hostname = host_info[1]
            passwd = host_info[2]
            conf_defined_hosts[hostname] = ip

        for group_name, group_hosts in host_groups.items():
            host_groups_group_names.append(group_name)
            if len(list(set(group_hosts))) != len(group_hosts):
                self.err_messages.append("每个机器名只能在同一个组内列出一次")
            for host_name in group_hosts:
                if host_name not in conf_defined_hosts:
                    self.err_messages.append(
                        "{} conf.yml 中配置的host 也必须在 hosts.yml 中提供配置信息".format(host_name))

        for group_name, services in host_group_services.items():
            host_group_services_group_names.append(group_name)
            duplicated_services = [sname for sname in services if services.count(sname)>=2]
            if len(duplicated_services)>0:
                self.err_messages.append("每个被部署组件名只能在同一个组内列出一次,请检查如下组的配置 组: {} , 组件名: {}".format(group_name, " ".join(list(set(duplicated_services)))))

            for service_name in services:
                is_supported = self.is_service_supported(service_name)
                if not is_supported:
                    self.err_messages.append("{} 选择部署的该组件目前不支持".format(service_name))

        if not (len(host_groups_group_names) == len(host_group_services_group_names) and set(
                host_groups_group_names) == set(host_group_services_group_names)):
            self.err_messages.append("host_groups 配置和group_services 中的组名不一致")

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

    # user: admin
    # hosts:
    # - 10.1.1.10 gs-server0 password0
    # - 10.1.1.12 gs-server2 password2
    # - 10.1.1.2[5-10] gs-server[5-10]  password
    def check_hosts_info_conf(self, hosts_info):
        parsed_hosts, user = hosts_info
        for host_info in parsed_hosts:
            ip = host_info[0]
            hostname = host_info[1]
            passwd = host_info[2]
            if not is_valid_ip(ip):
                self.err_messages.append("{} 该IP地址不合法，请检查hosts_info.yml 配置文件".format(ip))

    # 获取要部署的组件和部署组件的数量
    def get_service_distribution(self, host_groups, host_group_services):
        service_counter = {}
        services = []
        group_hosts = {}
        for group_name, hosts in host_groups.items():
            group_hosts[group_name] = hosts

        for group_name, host_components in host_group_services.items():
            services.extend(host_components)
            for service_name in host_components:
                hosts_count = len(group_hosts[group_name])
                service_counter[service_name] = service_counter.setdefault(service_name, 0) + hosts_count
        unique_services = list(set(services))
        return unique_services, service_counter

    # todo Fail if ZooKeeper is not present
    # Fail if the selected components should not be part of an HDP 3 blueprint
    # "HA NameNode has been requested but the ZKFC component must be present in the nodes running the NAMENODE (only)."
    # if the ambari_groups list is empty
    # Fail if no Ansible inventory group called 'hadoop-cluster' exists

    def load_conf(self):
        file_path = os.path.join(self.conf_path, 'conf.yml')
        with open(file_path, 'r') as f:
            data = yaml.load(f)
        return data

    # 解析哪些组件部署在哪些机器上，主要解析通配符
    # 可以解析 node[1-3] node[1-3]xx [1-3]node  或者 node1 的主机组配置
    # node[1 - 3].example.com，则函数会将其扩展为 `node1.example.com`、`node2.example.com` 和 `node3.example.com`# 三个主机名。
    def parse_component_topology_conf(self):
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
                match = re.search(r'\[(\d+)-(\d+)]', group_hosts)
                if match:
                    prefix = group_hosts[:match.start()]
                    start = int(match.group(1))
                    end = int(match.group(2))
                    suffix = group_hosts[match.end():]
                    for i in range(start, end + 1):
                        host = '{}{}{}'.format(prefix, i, suffix)
                        host_groups[group_name].append(host)
                else:
                    host_groups[group_name].append(group_hosts)

        return host_groups, host_group_services

    def parse_hosts_config(self):
        import yaml
        file_path = os.path.join(self.CONF_DIR, 'hosts_info.yml')
        with open(file_path, 'r') as f:
            data = yaml.load(f)
        configurations = data["hosts"]
        user = data["user"]
        parsed_configs = []

        for config in configurations:
            if len(config.split()) != 3:
                raise InvalidConfigurationException

            if '[' in config:
                hostname_part, ip_part, password = config.split()
                hosts = []
                ips = []
                if '[' in hostname_part:
                    match = re.search(r'\[(\d+)-(\d+)]', hostname_part)
                    if match:
                        hostname_prefix = hostname_part[:match.start()]
                        hostname_range_start = int(match.group(1))
                        hostname_range_end = int(match.group(2))
                        hostname_suffix = hostname_part[match.end():]

                        for i in range(hostname_range_start, hostname_range_end + 1):
                            host = '{}{}{}'.format(hostname_prefix, i, hostname_suffix)
                            hosts.append(host)
                    else:
                        raise InvalidConfigurationException
                if '[' in ip_part:
                    match = re.search(r'\[(\d+)-(\d+)]', ip_part)
                    if match:
                        ip_prefix = ip_part[:match.start()]
                        ip_range_start = int(match.group(1))
                        ip_range_end = int(match.group(2))
                        ip_suffix = ip_part[match.end():]

                        for i in range(ip_range_start, ip_range_end + 1):
                            ip = '{}{}{}'.format(ip_prefix, i, ip_suffix)
                            ips.append(ip)
                else:
                    raise InvalidConfigurationException

                if len(hosts) != len(ips):
                    raise InvalidConfigurationException("Configuration is invalid")
                for index, ip in enumerate(ips):
                    parsed_configs.append((hosts[index], ip, password))
            else:

                parsed_configs.append(tuple(config.split()))

        return parsed_configs, user

    # 从jinja2 j2 模版渲染提取变量
    def get_data_from_j2template(self, conf_str, context, decoder="json"):
        if len(conf_str) == 0:
            return {}
        template = Template(conf_str)
        # 渲染模板
        result = template.render(context)
        if decoder == "json":
            return json.loads(result)
        else:
            return yaml.load(result)

    # 生成host_group 相关变量，后续蓝图会用到
    def generate_hosts_groups_variables(self, host_groups, host_group_services):
        group_hosts = {}
        hosts_groups_variables = {}

        for group_name, hosts in host_groups.items():
            group_hosts[group_name] = hosts

        for group_name, group_services in host_group_services.items():
            if "NAMENODE" in group_services:
                hosts_groups_variables.setdefault("namenode_groups", []).append(group_name)
                hosts_groups_variables.setdefault("namenode_hosts", []).extend(group_hosts[group_name])
            if "ZKFC" in group_services:
                hosts_groups_variables.setdefault("zkfc_groups", []).append(group_name)
            if "RESOURCEMANAGER" in group_services:
                hosts_groups_variables.setdefault("resourcemanager_groups", []).append(group_name)
            if "JOURNALNODE" in group_services:
                hosts_groups_variables.setdefault("journalnode_groups", []).append(group_name)
            if "ZOOKEEPER_SERVER" in group_services:
                hosts_groups_variables.setdefault("zookeeper_groups", []).append(group_name)
                hosts_groups_variables.setdefault("zookeeper_hosts", []).extend(group_hosts[group_name])
            if "HIVE_SERVER" in group_services or "HIVE_METASTORE" in group_services:
                hosts_groups_variables.setdefault("hiveserver_hosts", []).extend(group_hosts[group_name])
            if "KAFKA_BROKER" in group_services:
                hosts_groups_variables.setdefault("kafka_groups", []).append(group_name)
                hosts_groups_variables.setdefault("kafka_hosts", []).extend(group_hosts[group_name])
            if "RANGER_ADMIN" in group_services:
                hosts_groups_variables.setdefault("rangeradmin_groups", []).append(group_name)
                hosts_groups_variables.setdefault("rangeradmin_hosts", []).extend(group_hosts[group_name])
            if "RANGER_KMS_SERVER" in group_services:
                hosts_groups_variables.setdefault("rangerkms_hosts", []).extend(group_hosts[group_name])
            if "SOLR_SERVER" in group_services:
                hosts_groups_variables.setdefault("solr_hosts", []).extend(group_hosts[group_name])

        for k, v in hosts_groups_variables.items():
            hosts_groups_variables[k] = list(set(v))

        return hosts_groups_variables

    # 这里生成一些根据计算得到的动态的变量，后续蓝图和ansible 部署会用到
    def generate_dynamic_j2template_variables(self, host_groups, host_group_services):
        str_conf = yaml.dump(self.raw_conf)
        # 原始的conf, 存在很懂变量
        conf_j2_context = self.raw_conf

        # 动态生成一些蓝图的需要用到的namenode_hosts 等变量
        hosts_groups_variables = self.generate_hosts_groups_variables(host_groups, host_group_services)

        # 根据用户配置动态生成一些变量
        extra_vars = {
            "ntp_server_hostname": self.generate_ntp_server_hostname(),
            "hadoop_base_dir": self.raw_conf["data_dirs"][0], "kdc_hostname": self.get_kdc_server_host(),
            "database_hostname": self.generate_database_host()
        }
        conf_j2_context.update(extra_vars)

        rendered_conf_vars = self.get_data_from_j2template(str_conf, conf_j2_context, decoder="yaml")

        rendered_conf_vars.update(hosts_groups_variables)
        rendered_conf_vars.update(extra_vars)
        return rendered_conf_vars

    # 根据配置 生成 ambari hive ranger 依赖的数据库地址
    def generate_database_host(self):
        ambari_host = self.get_ambari_server_host()
        external_database_server_ip = self.raw_conf["database_options"]["external_hostname"]
        if len(external_database_server_ip.strip()) == 0:
            database_host = ambari_host
        else:
            database_host = self.raw_conf["database_options"]["external_hostname"]
        return database_host

    # 根据配置，生成集群时间同步需要用到的ntp server 的地址
    def generate_ntp_server_hostname(self):
        if len(self.raw_conf["external_ntp_server_hostname"].strip()) > 0:
            return self.raw_conf["external_ntp_server_hostname"].strip()
        else:
            ambari_server_host = self.get_ambari_server_host()
            return ambari_server_host

    # 获取ambari server 所在地址
    def get_ambari_server_host(self):
        group_services = self.raw_conf["group_services"]
        host_groups = self.raw_conf["host_groups"]
        ambari_server_group = None
        for group_name, services in group_services.items():
            if "AMBARI_SERVER" in services:
                ambari_server_group = group_name
                break
        if ambari_server_group:
            ambari_server_host = host_groups[ambari_server_group][0]
            return ambari_server_host
        else:
            raise InvalidConfigurationException

    # 获取kerberos kdc 服务器地址
    def get_kdc_server_host(self):
        if len(self.raw_conf["security_options"]["external_hostname"].strip()) > 0:
            return self.raw_conf["security_options"]["external_hostname"]
        else:
            ambari_server_host = self.get_ambari_server_host()
            return ambari_server_host

    # 执行配置验证，配置解析，动态的变量的渲染和生成，返回conf 给后续使用
    def parse_conf(self):
        hosts_info = self.parse_hosts_config()
        host_groups, host_group_services = self.parse_component_topology_conf()
        self.check_component_topology(host_groups, host_group_services)
        self.check_group_consistency(host_groups, host_group_services, hosts_info)
        self.check_hosts_info_conf(hosts_info)
        if len(self.err_messages) > 0:
            print("\n".join(self.err_messages))
            raise InvalidConfigurationException("Configuration is invalid")

        conf = self.generate_dynamic_j2template_variables(host_groups, host_group_services)
        self.conf = conf
        self.hosts_info = hosts_info

    def get_conf(self):
        if not self.conf:
            self.parse_conf()

        self.execute_plugins()

        return self.conf

    def get_hosts_info(self):
        if not self.hosts_info:
            self.parse_conf()
        return self.hosts_info

    def execute_plugins(self):
        # update_conf()
        plugins = self.instantiate_plugins()
        print(plugins)
        if len(plugins) == 0:
            return
        for plugin in plugins:
            if hasattr(plugin, "update_conf"):
                conf = plugin.update_conf(self.conf)
                self.conf = conf

    def instantiate_plugins(self):
        plugins_info = {}
        cf_plugins_list = self.raw_conf["plugins"]
        if len(cf_plugins_list) > 0:
            for plugin_item in cf_plugins_list:
                plugin_name = plugin_item.keys()[0]
                enabled = plugin_item[plugin_name]["enabled"]
                plugins_info[plugin_name] = enabled
        
        print(cf_plugins_list)

        plugins = []
        class_name_pattern = re.compile(".*?DeployPlugin", re.IGNORECASE)

        pfs = get_python_files(self.PLUGINS_DIR)
        print(pfs)
        if len(pfs) == 0:
            return []
        for py_file in pfs:
            if py_file is not None and os.path.exists(py_file) is not None:
                try:
                    plugin_file_name = os.path.basename(py_file)
                    print(plugin_file_name)
                    if not plugins_info.get(plugin_file_name.split(".")[0], None):
                        continue

                    with open(py_file, 'rb') as fp:
                        deploy_plugin = imp.load_source('deploy_plugin_impl', py_file, fp)


                        # Find the class name by reading from all of the available attributes of the python file.
                        attributes = dir(deploy_plugin)
                        best_class_name = None
                        for potential_class_name in attributes:
                            if not potential_class_name.startswith("__"):
                                m = class_name_pattern.match(potential_class_name)
                                if m:
                                    best_class_name = potential_class_name
                                    break

                        if hasattr(deploy_plugin, best_class_name):
                            print("plugin implementation  {0} was loaded".format(best_class_name))
                            plugins.append(getattr(deploy_plugin, best_class_name)())
                        else:
                            print("Failed to load or create plugin implementation  {0}: ".format(best_class_name))
                except Exception as e:
                    print("Failed to load plugin implementation ")

        return plugins


def is_valid_ip(ip):
    # 使用正则表达式匹配 IP 地址的格式
    pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    if pattern.match(ip):
        # 拆分 IP 地址的四个部分
        parts = ip.split('.')
        # 检查每个部分的取值范围是否合法
        for part in parts:
            if not (0 <= int(part) <= 255):
                return False
        return True
    else:
        return False


def get_python_files(directory):
    python_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


def main():
    b = ConfUtils()
    conf = b.get_conf()


if __name__ == '__main__':
    main()
