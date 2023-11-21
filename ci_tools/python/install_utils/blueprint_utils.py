# -*- coding: UTF-8 -*-
import json
import copy
import yaml
from jinja2 import Template
from .conf_utils import services_map
from .conf_utils import InvalidConfigurationException
from python.common.constants import *
from python.common.basic_logger import get_logger
logger = get_logger()

class BlueprintUtils:
    def __init__(self, conf):
        self.host_group_services = {}
        self.conf = conf

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
                file_path = os.path.join(CLUSTER_TEMPLATES_DIR, file_name)
                return file_path

    def write_json_data(self, filepath, json_data):
        with open(filepath, 'w') as jsonfile:
            json.dump(json_data, jsonfile, indent=4)


    # 从template 中读取j2 模版，然后传入参数，组装各个组件的配置
    def generate_blueprint_configurations(self, jinja_context):
        configurations = []
        services_need_install = self.get_services_need_install()
        processed_services = []
        if self.conf.get("security") == 'mit-kdc':
            services_need_install.append("KERBEROS_CLIENT")

        for service_name in services_need_install:
            service_key = self.get_service_key_from_service(service_name)
            service_conf_j2template_path = self.get_conf_j2template_name(service_name)
            service_confs = self.j2template_render(service_conf_j2template_path, jinja_context)

            if len(service_confs) == 0 or service_key in processed_services:
                continue

            if isinstance(service_confs, dict):
                for k in service_confs.keys():
                    if isinstance(service_confs[k], dict):
                        configurations.append({k: service_confs[k]})
                    else:
                        logger.error("error conf template--------")



            rendered_template_name = os.path.basename(service_conf_j2template_path.replace(".j2", ""))
            output_location = os.path.join(OUTPUT_DIR, rendered_template_name)
            logger.info(f"write rendered data to output dir for review { rendered_template_name} {OUTPUT_DIR} {output_location} ")
            self.write_json_data(output_location, service_confs)

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
        logger.info("rendering {} config templates  ".format(os.path.basename(file_path)))
        result = template.render(context)
        if decoder == "json":
            return json.loads(result)
        else:
            return yaml.load(result,yaml.SafeLoader)

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

        return ambari_repo

    def generate_ambari_blueprint(self, ambari_blueprint_configurations, ambari_blueprint_host_groups):
        security = self.conf["security"]
        if security.strip().lower() != "none":
            blueprint_security = "KERBEROS"
        else:
            blueprint_security = "NONE"
        ambari_repo_url = self.get_ambari_repo()

        self.conf["ambari_repo_url"] = ambari_repo_url

        configurations = ambari_blueprint_configurations
        host_groups = ambari_blueprint_host_groups
        j2_context = {
            "blueprint_security": blueprint_security,
            "ambari_blueprint_configurations": json.dumps(configurations),
            "ambari_blueprint_host_groups": json.dumps(host_groups),
            "ambari_repo_url": ambari_repo_url,
        }
        base_blueprint_template_path = os.path.join(CLUSTER_TEMPLATES_DIR, "base_blueprint.json.j2")
        blueprint_json = self.j2template_render(base_blueprint_template_path, j2_context)

        file_name = os.path.join(BLUEPRINT_FILES_DIR, "blueprint.json")
        with open(file_name, 'w') as f:
            json.dump(blueprint_json, f, indent=4)

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
            "config_recommendation_strategy": conf["ambari_options"]["config_recommendation_strategy"],
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

        file_name = os.path.join(BLUEPRINT_FILES_DIR, "cluster_template.json")
        with open(file_name, 'w') as f:
            json.dump(res, f, indent=4)

    def generate_ansible_variables_file(self, variables):
        variables_cp = copy.deepcopy(variables)
        ambari_repo_url = self.get_ambari_repo()
        variables_cp["ambari_repo_url"] = ambari_repo_url
        for key in ["host_groups", "group_services"]:
            variables_cp.pop(key, None)

        variables_file_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/group_vars/all')
        with open(variables_file_path, 'w') as f:
            yaml.dump(variables_cp, f)

    def generate_ansible_hosts(self, conf, hosts_info, ambari_server_host):
        logger.info("动态生成ansible hosts 文件")

        parsed_hosts, user = hosts_info
        host_groups = conf["host_groups"]

        hosts_dict = {}
        for host_info in parsed_hosts:
            ip = host_info[0]
            hostname = host_info[1]
            passwd = host_info[2]
            hosts_dict[hostname] = (ip, passwd)

        node_groups = {}
        node_groups.setdefault("ambari-server", []).extend([ambari_server_host])
        for group_name, hosts in host_groups.items():
            node_groups.setdefault("hadoop-cluster", []).extend(hosts)

        hosts_content = ""
        for group, hosts in node_groups.items():
            hosts_content += "[{}]\n".format(group)
            for host_name in hosts:
                info = hosts_dict.get(host_name)
                if not info:
                    raise InvalidConfigurationException
                ip = info[0]
                passwd = info[1]
                hosts_content += "{} ansible_host={} ansible_ssh_pass={}\n".format(host_name, ip, passwd)
            hosts_content += "\n"

        ansible_user = user

        hosts_content += "[all:vars]\n"
        hosts_content += "ansible_user={}\n".format(ansible_user)
        hosts_path = os.path.join(ANSIBLE_PRJ_DIR, "inventory", "hosts")
        with open(hosts_path, "w") as f:
            f.write(hosts_content)

    def build(self):
        blueprint_configurations = self.generate_blueprint_configurations(self.conf)
        blueprint_service_host_groups = self.generate_blueprint_host_groups()
        self.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        self.generate_ambari_cluster_template()
        self.generate_ansible_variables_file(self.conf)

