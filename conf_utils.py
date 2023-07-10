# -*- coding: UTF-8 -*-
import json
import re
import os
import sys
import yaml
from jinja2 import Template, Undefined


class InvalidConfigurationException(Exception):
    pass


class DelayedUndefined(Undefined):
    def __getattr__(self, name):
        return '{{{0}.{1}}}'.format(self._undefined_name, name)


class ConfUtils:
    CONF_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        self.conf_path = ConfUtils.CONF_DIR
        self.conf = None
        self.err_messages=[]

    # 这个函数是用来检查组件拓扑的。
    # 函数首先获取需要安装的服务和服务计数器。然后，定义一个模式规则字典，其中包含了各种服务及其对应的组件要求，如最小实例数、最大实例数等。
    # 接下来，函数遍历需要安装的所有服务，如果服务在模式规则中，就进行规则检查。如果服务的组件数量不满足规则要求，就将错误信息添加到消息列表中。
    # 最后，如果消息列表中有内容，说明有不满足规则的服务，函数返回False和错误信息；否则，返回True和None。
    def check_component_topology(self, host_groups, host_group_services):
        #host_group_services example {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
        #host_groups example {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']}
        # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如同时部署了ZKFC 和 secondary 到一个 group 中  {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
        # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如namenode 高可用模式下没有在group1 数组中部署放置JOURNALNODE
        err_messages = []
        services_need_install, service_counter = self.get_service_distribution(host_groups, host_group_services)
        checked_services = []

        pattern_rules = {
            "namenode": [
                {
                    "NAMENODE": {"min_instances": 2, "max_instances": 2},
                    "ZKFC": {"min_instances": 2, "max_instances": 2},
                    "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
                },
                {
                    "NAMENODE": {"min_instances": 1, "max_instances": 1},
                    "SECONDARY_NAMENODE": {"min_instances": 1, "max_instances": 1},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "ZKFC": {"min_instances": 0, "max_instances": 0},
                    "JOURNALNODE": {"min_instances": 0, "max_instances": 0}
                }],
            "hive": {
                "HIVE_METASTORE": {"min_instances": 1, "max_instances": 1},
                "HIVE_SERVER": {"min_instances": 1, "max_instances": None},
                "WEBHCAT_SERVER": {"min_instances": 1, "max_instances": 1},
            },
            "yarn": {
                "RESOURCEMANAGER": {"min_instances": 1, "max_instances": 2},
                "NODEMANAGER": {"min_instances": 1, "max_instances": None},
                "HISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "kafka": {
                "KAFKA_BROKER": {"min_instances": 1, "max_instances": None},
            },
            "ambari": {
                "AMBARI_SERVER": {"min_instances": 1, "max_instances": 1},
            },
            "hbase": {
                "HBASE_MASTER": {"min_instances": 1, "max_instances": 2},
                "HBASE_REGIONSERVER": {"min_instances": 1, "max_instances": None},
            },
            "ranger": {
                "RANGER_ADMIN": {"min_instances": 1, "max_instances": 2},
                "RANGER_TAGSYNC": {"min_instances": 1, "max_instances": 1},
                "RANGER_USERSYNC": {"min_instances": 1, "max_instances": 1},
            },
            "spark": {
                "SPARK_JOBHISTORYSERVER": {"min_instances": 1, "max_instances": 1},
                "SPARK_THRIFTSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "zookeeper": {
                "ZOOKEEPER_SERVER": {"min_instances": 1, "max_instances": None, "odd_only": True},
            },
            "flink": {
                "FLINK_HISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "infra_solr": {
                "INFRA_SOLR": {"min_instances": 1, "max_instances": None},
            },
            "solr": {
                "SOLR_SERVER": {"min_instances": 1, "max_instances": None},
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
                        err_messages.extend(messages)
                        checked_services.append(pattern_key)
                elif isinstance(service_rules, list):
                    # 检测namanode 的两种部署模式
                    res = []
                    tmp_err = []
                    for service_rules_item in service_rules:
                        if service_name in service_rules_item.keys():
                            messages = self.check_pattern(service_rules_item, service_counter)
                            tmp_err.extend(messages)
                    if True not in res:
                        err_messages.extend(tmp_err)
                        checked_services.append(pattern_key)

        if len(err_messages) > 0:
            err_messages.insert(0, "配置错误")
            return False, err_messages

        return True, None

    def check_pattern(self, service_rules, service_counter):
        messages = []
        for rule_service_name, rule in service_rules.items():

            service_count = service_counter.get(rule_service_name, 0)

            if service_count < rule["min_instances"]:
                messages.append(
                    "{} 的实例数 {} 小于最小实例数 {}".format(rule_service_name, service_count, rule['min_instances']))

            if rule["max_instances"] is not None and service_count > rule["max_instances"]:
                messages.append(
                    "{} 的实例数 {} 大于最大实例数 {}".format(rule_service_name, service_count, rule['max_instances']))

            if rule.get("odd_only") and service_count % 2 == 0:
                messages.append("{} 的实例数 {} 不是奇数".format(rule_service_name, service_count))
        if len(messages) > 0 and "NAMENODE" in service_rules.keys():
            hdfs_msg = '''\
                       hdfs高可用部署模式必须满足 NAMENODE 组件数目为2，ZKFC 为2 且每个ZKFC 必须和 NAMENODE 部署在一起同一个机器，JOURNALNODE 至少大于等于3，且数目为奇数，HA 模式不能选择 SECONDARY_NAMENODE
                       hdfs 普通部署模式需要部署1个 NAMENODE 和一个 SECONDARY_NAMENODE，ZKFC 和 JOURNALNODE 在该模式下不可选择。
                       因此请从两种部署模式中配置一种模式部署。
                       '''
            messages.append(hdfs_msg)

        return messages

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

    # 一个组件和host只能在一个group中出现一次
    # 组件名必须符合支持的组件的规则
    # group 必须互相对应
    # conf 两组group 数量和名字检测一致性
    # 每个组的机器不可以有重复
    # 暂时不支持hdfs数据目录以外的目录配置多个目录
    # Fail if ZooKeeper is not present
    # Fail if the selected components should not be part of an HDP 3 blueprint
    # "HA NameNode has been requested but the ZKFC component must be present in the nodes running the NAMENODE (only)."
    # if the ambari_groups list is empty
    # Fail if no Ansible inventory group called 'hadoop-cluster' exists
    # def check_config(self):
    #     is_valid, messages = self.check_component_topology()
    #     if not is_valid:
    #         for message in messages:
    #             print(message)
    #         raise InvalidConfigurationException("Configuration is invalid")
    #     return True, None

    def load_conf(self):
        file_path = os.path.join(self.conf_path, 'conf.yml')
        with open(file_path, 'r') as f:
            data = yaml.load(f)
        return data

    # 解析哪些组件部署在哪些机器上，主要解析通配符
    # 可以解析 node[1-3] node[1-3]xx [1-3]node  或者 node1 的主机组配置
    # node[1 - 3].example.com，则函数会将其扩展为 `node1.example.com`、`node2.example.com` 和 `node3.example.com`# 三个主机名。
    def parse_component_topology_conf(self, raw_conf):
        host_groups_conf = raw_conf["host_groups"]
        group_services_conf = raw_conf["group_services"]
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

    # 从jinja2 j2 模版渲染提取变量
    def get_data_from_j2template(self, conf_str, context, decoder="json"):
        if len(conf_str) == 0:
            return {}
        print(conf_str)
        print(context)
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
    def generate_dynamic_j2template_variables(self, raw_conf, host_groups, host_group_services):
        str_conf = yaml.dump(raw_conf)
        # 原始的conf, 存在很懂变量
        conf_j2_context = raw_conf

        # 动态生成一些蓝图的需要用到的namenode_hosts 等变量
        hosts_groups_variables = self.generate_hosts_groups_variables(host_groups, host_group_services)

        # 根据用户配置动态生成一些变量
        extra_vars = {
            "repo_base_url": self.generate_nexus_base_url(raw_conf),
            "ntp_server_hostname": self.generate_ntp_server_hostname(raw_conf),
            "hadoop_base_dir": raw_conf["data_dirs"][0], "kdc_hostname": self.get_kdc_server_host(raw_conf),
            "database_hostname": self.generate_database_host(raw_conf)
        }
        conf_j2_context.update(extra_vars)

        rendered_conf_vars = self.get_data_from_j2template(str_conf, conf_j2_context, decoder="yaml")

        rendered_conf_vars.update(hosts_groups_variables)
        rendered_conf_vars.update(extra_vars)
        return rendered_conf_vars

    # 根据配置 生成 ambari hive ranger 依赖的数据库地址
    def generate_database_host(self, raw_conf):
        ambari_host = self.get_ambari_server_host(raw_conf)
        external_database_server_ip = raw_conf["database_options"]["external_hostname"]
        if len(external_database_server_ip.strip()) == 0:
            database_host = ambari_host
        else:
            database_host = raw_conf["database_options"]["external_hostname"]
        return database_host

    # 根据配置生成后续安装需要依赖的nexus 地址
    def generate_nexus_base_url(self, raw_conf):
        ambari_host = self.get_ambari_server_host(raw_conf)
        external_nexus_server_ip = raw_conf["nexus_options"]["external_nexus_server_ip"]
        nexus_port = raw_conf["nexus_options"]["port"]
        if len(external_nexus_server_ip.strip()) == 0:
            nexus_host = ambari_host
        else:
            nexus_host = raw_conf["nexus_options"]["external_nexus_server_ip"]
        nexus_url = "http://{}:{}".format(nexus_host, nexus_port)
        return nexus_url

    # 根据配置，生成集群时间同步需要用到的ntp server 的地址
    def generate_ntp_server_hostname(self, raw_conf):
        if len(raw_conf["external_ntp_server_hostname"].strip()) > 0:
            return raw_conf["external_ntp_server_hostname"].strip()
        else:
            ambari_server_host = self.get_ambari_server_host(raw_conf)
            return ambari_server_host

    # 获取ambari server 所在地址
    def get_ambari_server_host(self, raw_conf):
        group_services = raw_conf["group_services"]
        host_groups = raw_conf["host_groups"]
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
    def get_kdc_server_host(self, raw_conf):
        if len(raw_conf["security_options"]["external_hostname"].strip()) > 0:
            return raw_conf["security_options"]["external_hostname"]
        else:
            ambari_server_host = self.get_ambari_server_host(raw_conf)
            return ambari_server_host

    # 执行配置验证，配置解析，动态的变量的渲染和生成，返回conf 给后续使用
    def run(self):
        raw_conf = self.load_conf()
        host_groups, host_group_services = self.parse_component_topology_conf(raw_conf)
        is_valid, messages = self.check_component_topology(host_groups, host_group_services)
        if not is_valid:
            for message in messages:
                print(message)
            raise InvalidConfigurationException("Configuration is invalid")

        conf = self.generate_dynamic_j2template_variables(raw_conf, host_groups, host_group_services)
        return conf


# todo load hosts info and check
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


def main():
    b = ConfUtils()
    conf = b.run()
    print(conf)


if __name__ == '__main__':
    main()
