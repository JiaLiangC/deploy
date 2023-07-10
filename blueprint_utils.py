# -*- coding: UTF-8 -*-
import json
import re
import os
import yaml
import sys
from jinja2 import Template, Undefined
from conf_utils import ConfUtils

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

    def services_map(self):
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
                "server": ["NODEMANAGER", "RESOURCEMANAGER", "HISTORYSERVER"],
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
            "kerberos": {
                "server": ["KERBEROS_CLIENT"],
                "clients": ["KERBEROS_CLIENT"]
            }
        }
        return service_map

    def get_service_key_from_service(self, service_name):
        for service_key, service_info in self.services_map().items():
            if service_name in service_info["server"]:
                return service_key

    def get_services_need_install(self):
        services = []
        for group_name, host_components in self.host_group_services.items():
            services.extend(host_components)
        unique_services = list(set(services))
        return unique_services

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

    # 从template 中读取j2 模版，然后传入参数，组装各个组件的配置
    def assemble_service_configurations(self, jinja_context):
        configurations = []
        services_need_install = self.get_services_need_install()
        processed_services = []
        if self.conf.get("security") == 'mit-kdc':
            services_need_install.append("KERBEROS_CLIENT")

        for service_name in services_need_install:
            service_key = self.get_service_key_from_service(service_name)
            service_conf_j2template = self.get_conf_j2template_name(service_name)
            service_confs = self.get_confs_from_j2template(service_conf_j2template, jinja_context)
            if len(service_confs) == 0 or service_key in processed_services:
                continue

            if isinstance(service_confs, dict):
                for k in service_confs.keys():
                    if isinstance(service_confs[k], dict):
                        configurations.append({k: service_confs[k]})
                    else:
                        print("error conf template--------")

            processed_services.append(service_key)

        return configurations

    # 返回ambari blueprint 中的 host_groups 部分
    # "host_groups": [
    #         {
    #             "cardinality": "1",
    #             "name": "group1",
    #             "components": [
    #                 {
    #                     "name": "RANGER_ADMIN"
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

    def get_confs_from_j2template(self, file_path, context, decoder="json"):
        with open(file_path, 'r') as f:
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
        if security and security == "mit-kdc":
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




    def generate_ansible_variables_file(self, variables):
        for key in ["host_groups", "group_services"]:
            # 删除无用的属性
            variables.pop(key, None)

        variables_file_path = os.path.join(self.ANSIBLE_PRJ_DIR, 'playbooks/group_vars/all')
        with open(variables_file_path, 'w') as f:
            yaml.dump(variables, f)

    def build(self):
        cu = ConfUtils()
        self.conf = cu.run()
        blueprint_configurations = self.assemble_service_configurations(self.conf)
        blueprint_service_host_groups = self.assemble_service_by_host_groups()
        self.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        self.generate_ambari_cluster_template()
        self.generate_ansible_variables_file(self.conf)

def main():
    b = BlueprintUtils()
    b.build()


if __name__ == '__main__':
    main()
