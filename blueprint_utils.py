# -*- coding: UTF-8 -*-
import json
import re
import os
import yaml
import sys
from jinja2 import Template, Undefined
from conf_utils import ConfUtils
from conf_utils import services_map

reload(sys)
sys.setdefaultencoding('utf-8')


class BlueprintUtils:
    CONF_DIR = os.path.dirname(os.path.abspath(__file__))
    ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-udh')
    BLUEPRINT_FILES_DIR = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/roles/ambari-blueprint/files/')
    CLUSTER_TEMPLATES_DIR = os.path.join(CONF_DIR, "cluster_templates")

    def __init__(self):
        self.host_group_services = {}
        self.conf = None

    def get_service_key_from_service(self, service_name):
        for service_key, service_info in services_map().items():
            if service_name in service_info["server"]:
                return service_key

    def get_services_need_install(self):
        services = []
        for group_name, host_components in self.conf["group_services"].items():
            services.extend(host_components)
        unique_services = list(set(services))
        return unique_services

    def get_service_clients_need_install(self, services):
        clients = []
        for service_name in services:
            for service_key, service_info in services_map().items():
                if service_name in service_info["server"]:
                    clients.extend(service_info["clients"])

        unique_clients = list(set(clients))
        return unique_clients

    def get_conf_j2template_name(self, service_name):
        for service_key, service_info in services_map().items():
            if service_name in service_info["server"]:
                file_name = service_key + "_configuration.json.j2"
                file_path = os.path.join(self.CLUSTER_TEMPLATES_DIR, file_name)
                return file_path

    # 从template 中读取j2 模版，然后传入参数，组装各个组件的配置
    def generate_blueprint_configurations(self, jinja_context):
        configurations = []
        services_need_install = self.get_services_need_install()
        processed_services = []
        if self.conf.get("security") == 'mit-kdc':
            services_need_install.append("KERBEROS_CLIENT")

        for service_name in services_need_install:
            service_key = self.get_service_key_from_service(service_name)
            service_conf_j2template = self.get_conf_j2template_name(service_name)
            service_confs = self.j2template_render(service_conf_j2template, jinja_context)
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
    def generate_blueprint_host_groups(self):
        conf = self.conf
        host_groups = []
        services_need_install = self.get_services_need_install()
        all_services_clients = self.get_service_clients_need_install(services_need_install)

        for group_name, services in conf["group_services"].items():
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

    def j2template_render(self, file_path, context, decoder="json"):
        with open(file_path, 'r') as f:
            template_str = f.read()
        # 创建模板对象
        if len(template_str) == 0:
            return {}
        template = Template(template_str)
        # 渲染模板
        result = template.render(context)
        if decoder == "json":
            return json.loads(result)
        else:
            return yaml.load(result)

    def generate_ambari_blueprint(self, ambari_blueprint_configurations, ambari_blueprint_host_groups):

        blueprint = {
            "configurations": ambari_blueprint_configurations,
            "host_groups": ambari_blueprint_host_groups,
            "Blueprints": {
                "security": {
                    "type": "KERBEROS"
                },
                "stack_name": "BIGTOP",
                "stack_version": "3.2.0"
            }
        }

        file_name = os.path.join(self.BLUEPRINT_FILES_DIR, "blueprint.json")
        with open(file_name, 'w') as f:
            json.dump(blueprint, f, indent=4)

    def generate_ambari_cluster_template(self):
        conf = self.conf
        security = conf["security"]
        kerberos_admin_principal = conf["security_options"]["admin_principal"] + "@" + conf["security_options"]["realm"]
        kerberos_admin_password = conf["security_options"]["admin_password"]
        ambari_cluster_template_host_groups = []
        for group_name, group_hosts in conf["host_groups"].items():
            result = [{'fqdn': host} for host in group_hosts]
            tmp_host_groups = {
                "name": group_name,
                "hosts": result
            }
            ambari_cluster_template_host_groups.append(tmp_host_groups)

        res = {
            "blueprint": conf["blueprint_name"],
            "default_password": conf["default_password"],
            "host_groups": ambari_cluster_template_host_groups,
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

        file_name = os.path.join(self.BLUEPRINT_FILES_DIR, "cluster_template.json")
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
        conf, hosts_info = cu.run()
        self.conf = conf
        blueprint_configurations = self.generate_blueprint_configurations(self.conf)
        blueprint_service_host_groups = self.generate_blueprint_host_groups()
        self.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        self.generate_ambari_cluster_template()
        self.generate_ansible_variables_file(self.conf)


def main():
    b = BlueprintUtils()
    b.build()


if __name__ == '__main__':
    main()
