# -*- coding: UTF-8 -*-
import json
import re
import os
import yaml
import sys
from jinja2 import Template,Undefined

reload(sys)
sys.setdefaultencoding('utf-8')


class InvalidConfigurationException(Exception):
    pass

class DelayedUndefined(Undefined):
    def __getattr__(self, name):
        return '{{{0}.{1}}}'.format(self._undefined_name, name)

class BlueprintUtils:
    CONF_DIR = os.path.dirname(os.path.abspath(__file__))
    ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-udh')
    BLUEPRINT_FILES_DIR = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/roles/ambari-blueprint/files/')

    def __init__(self):
        self.ambari_blueprint_files_path = BlueprintUtils.BLUEPRINT_FILES_DIR
        self.cluster_templates_path = os.path.join(BlueprintUtils.CONF_DIR, "cluster_templates")
        self.conf_path = BlueprintUtils.CONF_DIR
        self.host_groups = {}
        self.host_group_services = {}
        self.conf = None

    def get_conffile(self):
        dir_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(dir_path, 'conf.yml')
        return file_path

    def services_map(self):
        service_map = {
            "hbase": {
                "server": ["HBASE_MASTER", "HBASE_REGIONSERVER"],
                "clients": ["HBASE_CLIENT"]
            },
            "hdfs": {
                "server": ["NAMENODE", "DATANODE", "SECONDARY_NAMENODE","JOURNALNODE"],
                "clients": ["HDFS_CLIENT", "MAPREDUCE2_CLIENT"]
            },
            "yarn": {
                "server": ["NODEMANAGER", "RESOURCEMANAGER", "HISTORYSERVER"],
                "clients": ["YARN_CLIENT"]
            },
            "hive": {
                "server": ["HIVE_METASTORE", "WEBHCAT_SERVER", "HIVE_SERVER"],
                "clients": ["HIVE_CLIENT", "HCAT"]
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
            "tez": {
                "server": [],
                "clients": ["TEZ_CLIENT"]
            },
            "solr": {
                "server": ["SOLR_SERVER"],
                "clients": []
            },
            "ambari": {
                "server": ["AMBARI_SERVER"],
                "clients": []
            },
            "kerberos": {
                "server": ["AMBARI_SERVER"],
                "clients": ["KERBEROS_CLIENT"]
            }
        }
        return service_map

    def get_service_key_from_service(self, service_name):
        for service_key, service_info in self.services_map().items():
            if service_name in service_info["server"]:
                return service_key

    def get_service_clients_need_install(self, services):
        clients = []
        for service_name in services:
            for service_key, service_info in self.services_map().items():
                if service_name in service_info["server"]:
                    clients.extend(service_info["clients"])

        unique_clients = list(set(clients))
        return unique_clients

    def get_conf_j2template_name(self, service_name):
        for service_key, service_info in self.services_map().items():
            if service_name in service_info["server"]:
                file_name = service_key + "_configuration.json.j2"
                file_path = os.path.join(self.cluster_templates_path, file_name)
                return file_path

    # 组装各个组件的配置
    def assemble_service_configurations(self, jinja_context):
        configurations = []
        services_need_install = self.get_services_need_install()
        processed_services = []
        for service_name in services_need_install:
            service_key = self.get_service_key_from_service(service_name)
            service_conf_j2template = self.get_conf_j2template_name(service_name)
            service_confs = self.get_confs_from_j2template(service_conf_j2template, jinja_context)
            if len(service_confs) == 0 or service_key in processed_services:
                continue

            configurations.append(service_confs)
            processed_services.append(service_key)

        return configurations

    def assemble_service_by_host_groups(self):
        host_groups = []
        services_need_install = self.get_services_need_install()
        all_services_clients = self.get_service_clients_need_install(services_need_install)

        for group_name, services in self.host_group_services.items():
            group_services = services
            group_services.extend(all_services_clients)
            host_group_components_config = [{'name': service_name} for service_name in group_services]

            host_group = {
                "name": group_name,
                "configurations": [],
                "cardinality": "1",
                "components": host_group_components_config
            }
            host_groups.append(host_group)
        return host_groups

    # 解析并返回service 的多个配置
    def get_confs_from_j2template(self, file, context, decoder="json"):
        # 读取模板文件
        # todo 增加异常检测
        # if not os.path.exists(file):
        #     raise Exception("s")

        with open(file, 'r') as f:
            template_str = f.read()
        # 创建模板对象
        if len(template_str) == 0:
            return {}
        template = Template(template_str, undefined=DelayedUndefined)
        # 渲染模板
        result = template.render(context)
        if decoder == "json":
            return json.loads(result)
        else:
            return yaml.load(result)

    def parse_cluster_install_config(self):
        host_groups_conf = self.conf["host_groups"]
        group_services_conf = self.conf["group_services"]

        # 可以解析 node[1-3] node[1-3]xx [1-3]node  或者 node1 的主机组配置
        # node[1 - 3].example.com，则函数会将其扩展为 `node1.example.com`、`node2.example.com` 和 `node3.example.com`# 三个主机名。
        host_groups = {}
        host_group_services = {}

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

        self.host_groups = host_groups
        self.host_group_services = host_group_services

    def generate_ambari_blueprint(self, configurations, host_groups):

        blueprint = {
            "configurations": configurations,
            "host_groups": host_groups,
            "Blueprints": {
                "security": {
                    "type": "KERBEROS"
                },
                "stack_name": "BIGTOP",
                "stack_version": "3.2.0"
            }
        }

        file_name = os.path.join(self.ambari_blueprint_files_path, "blueprint.json")
        with open(file_name, 'w') as f:
            json.dump(blueprint, f, indent=4)

    def get_nexus_base_url(self):
        group_services = self.conf["group_services"]
        host_groups = self.conf["host_groups"]
        ambari_server_group = ""

        install_nexus = False
        external_nexus_server_ip = self.conf["nexus_options"]["external_nexus_server_ip"]
        nexus_port = self.conf["nexus_options"]["port"]
        if len(external_nexus_server_ip.strip()) == 0:
            install_nexus = True

        if install_nexus:
            for group_name, services in group_services.items():
                if "AMBARI_SERVER" in services:
                    ambari_server_group = group_name
                    break
            nexus_host = host_groups[ambari_server_group][0]
        else:
            nexus_host = self.conf["nexus_options"]["external_nexus_server_ip"]

        nexus_url = "http://{}:{}".format(nexus_host, nexus_port)
        return nexus_url

    def generate_ambari_cluster_template(self):
        conf = self.conf
        security = conf["security"]
        kerberos_admin_principal = conf["security_options"]["admin_principal"] + "@" + conf["security_options"]["realm"]
        kerberos_admin_password = conf["security_options"]["admin_password"]
        host_groups = []
        for group_name, group_hosts in self.host_groups.items():
            result = [{'fqdn': host} for host in group_hosts]
            tmp_host_groups = {
                "name": group_name,
                "hosts": result
            }
            host_groups.append(tmp_host_groups)

        res = {
            "blueprint": conf["blueprint_name"],
            "default_password": conf["default_password"],
            "host_groups": host_groups,
        }
        if security and security == "KERBEROS":
            res["credentials"] = [
                {
                    "alias": "kdc.admin.credential",
                    "principal": kerberos_admin_principal,
                    "key": kerberos_admin_password,
                    "type": "TEMPORARY"
                }
            ]

            res["security"] = {
                "type": "KERBEROS"
            }

        file_name = os.path.join(self.ambari_blueprint_files_path, "cluster_template.json")
        with open(file_name, 'w') as f:
            json.dump(res, f, indent=4)

    def get_ntp_server(self):
        if len(self.conf["ntpserver"].strip()) > 0:
            return self.conf["ntpserver"].strip()
        else:
            group_services = self.conf["group_services"]
            host_groups = self.conf["host_groups"]
            ambari_server_group = None
            for group_name, services in group_services.items():
                if "AMBARI_SERVER" in services:
                    ambari_server_group = group_name
                    break
            if ambari_server_group:
                ntp_host = host_groups[ambari_server_group][0]
                return ntp_host
            else:
                raise InvalidConfigurationException

    def generate_ansible_variables_file(self, variables):
        for key in ["host_groups", "group_services"]:
            # 删除无用的属性
            variables.pop(key, None)

        variables_file_path = os.path.join(self.ANSIBLE_PRJ_DIR, 'playbooks/group_vars/all')
        with open(variables_file_path, 'w') as f:
            yaml.dump(variables, f)

    def conf_j2template_variables(self):
        group_hosts = {}
        groups_var = {}
        extral_vars = {}
        for group_name, hosts in self.host_groups.items():
            group_hosts[group_name] = hosts

        extral_vars["repo_base_url"] = self.get_nexus_base_url()
        extral_vars["ntpserver"] = self.get_ntp_server()
        extral_vars["hadoop_base_dir"] = self.conf["data_dirs"][0]
        extral_vars.update(self.conf)
        conf_vars = self.get_confs_from_j2template(os.path.join(self.conf_path, 'conf.yml'), extral_vars, decoder="yaml")

        for group_name, group_services in self.host_group_services.items():
            if "NAMENODE" in group_services:
                groups_var.setdefault("namenode_groups", []).append(group_name)
                groups_var.setdefault("namenode_hosts", []).extend(group_hosts[group_name])
            if "ZKFC" in group_services:
                groups_var.setdefault("zkfc_groups", []).append(group_name)
            if "RESOURCEMANAGER" in group_services:
                groups_var.setdefault("resourcemanager_groups", []).append(group_name)
            if "JOURNALNODE" in group_services:
                groups_var.setdefault("journalnode_groups", []).append(group_name)
            if "ZOOKEEPER_SERVER" in group_services:
                groups_var.setdefault("zookeeper_groups", []).append(group_name)
                groups_var.setdefault("zookeeper_hosts", []).extend(group_hosts[group_name])
            if "HIVE_SERVER" in group_services or "HIVE_METASTORE" in group_services:
                groups_var.setdefault("hiveserver_hosts", []).extend(group_hosts[group_name])
            if "KAFKA_BROKER" in group_services:
                groups_var.setdefault("kafka_groups", []).append(group_name)
                groups_var.setdefault("kafka_hosts", []).extend(group_hosts[group_name])
            if "RANGER_ADMIN" in group_services or "RANGER_USERSYNC" in group_services:
                groups_var.setdefault("rangeradmin_groups", []).append(group_name)
                groups_var.setdefault("rangeradmin_hosts", []).extend(group_hosts[group_name])
            if "RANGER_KMS_SERVER" in group_services:
                groups_var.setdefault("rangerkms_hosts", []).extend(group_hosts[group_name])
            if "SOLR_SERVER" in group_services:
                groups_var.setdefault("solr_hosts", []).extend(group_hosts[group_name])

        for k, v in groups_var.items():
            groups_var[k] = list(set(v))

        groups_var.update(conf_vars)
        return groups_var

    def build(self):
        self.load_conf()

        # 解析host_group 和 group_services
        self.parse_cluster_install_config()

        # 检查给定的 group_services 配置
        is_valid, messages = self.check_config_rules()
        if not is_valid:
            for message in messages:
                print(message)
            raise InvalidConfigurationException("Configuration is invalid")

        j2template_variables = self.conf_j2template_variables()
        self.generate_ansible_variables_file(j2template_variables)

        blueprint_configurations = self.assemble_service_configurations(j2template_variables)
        blueprint_service_host_groups = self.assemble_service_by_host_groups()
        print(blueprint_configurations)

        self.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        self.generate_ambari_cluster_template()

    def load_conf(self):
        file_path = os.path.join(self.conf_path, 'conf.yml')
        with open(file_path, 'r') as f:
            data = yaml.load(f)
        self.conf = data

    def get_services_need_install(self):
        services = []
        for group_name, host_components in self.host_group_services.items():
            services.extend(host_components)
        unique_services = list(set(services))
        return unique_services

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

    # group 名不能重复，不可以出现在多个组中
    def check_config_rules(self):
        all_services, service_counter = self.get_service_distribution()
        all_services = set(all_services)
        messages = []

        component_rules = {
            "NAMENODE": {"min_instances": 1, "max_instances": 2},
            "RESOURCEMANAGER": {"min_instances": 1, "max_instances": 2},
            "HBASE_MASTER": {"min_instances": 1, "max_instances": 2},
            "ZOOKEEPER_SERVER": {"min_instances": 1, "max_instances": None, "odd_only": True},
            "SPARK_JOBHISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            "AMBARI_SERVER": {"min_instances": 1, "max_instances": 1},
            "HIVE_METASTORE": {"min_instances": 1, "max_instances": 1}
        }

        component_relations = [
            {"service": ["NAMENODE", "DATANODE"], "type": "consist"},
            {"service": ["NODEMANAGER", "RESOURCEMANAGER"], "type": "consist"},
            {"service": ["HBASE_MASTER", "HBASE_REGIONSERVER"], "type": "consist"},
            {"service": ["RANGER_TAGSYNC", "RANGER_TAGSYNC", "RANGER_ADMIN"], "type": "consist"},
            {"service": ["HIVE_METASTORE", "HIVE_SERVER"], "type": "consist"},
            {"service": ["SPARK_JOBHISTORYSERVER", "SPARK_THRIFTSERVER"], "type": "consist"},
            {"service": ["ZOOKEEPER_SERVER"], "type": "consist"},
        ]

        for component, count in service_counter.items():
            rule = component_rules.get(component, None)
            if not rule:
                continue

            if count < rule["min_instances"]:
                messages.append("{} 的实例数 {} 小于最小实例数 {}".format(component, count, rule['min_instances']))

            if rule["max_instances"] is not None and count > rule["max_instances"]:
                messages.append("{} 的实例数 {} 大于最大实例数 {}".format(component, count, rule['max_instances']))

            if rule.get("odd_only") and count % 2 == 0:
                messages.append("{} 的实例数 {} 不是奇数".format(component, count))

        for relation in component_relations:
            services = set(relation["service"])
            type = relation["type"]
            if type == "consist":
                installed = has_common_elements(services, all_services)
                contained = services.issubset(all_services)
                if installed:
                    if not contained:
                        res = services.intersection(all_services)
                        installed_components = ",".join(res)
                        correct_relations = ",".join(services)
                        messages.append(
                            "配置安装的组件 {} 不完整, 该服务的组件必须全部配置安装，完整列表如: {}".format(
                                installed_components, correct_relations))

        if len(messages) > 0:
            return False, messages

        return True, messages


def has_common_elements(array1, array2):
    return any(elem in array2 for elem in array1)


def main():
    b = BlueprintUtils()
    b.build()



if __name__ == '__main__':
    main()
