# -*- coding: UTF-8 -*-
import json
import re
# import imp
from enum import Enum
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


def to_camel_case(name):
    return ''.join(word.capitalize() for word in name.split('_'))


class InvalidConfigurationException(Exception):
    pass


class Parser:

    def parse(self, *args, **kwargs):
        raise NotImplementedError("Parse method must be implemented by subclasses")

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
    # 解析 10.1.1.[1-3] server[1-3] password4 的机器组

    def parse_hosts(self, data):
        hosts = self._expand_range(data)
        return hosts

    def parse(self, hosts_configurations):
        parsed_configs = []

        for config in hosts_configurations:
            if len(config.split()) != 3:
                raise InvalidConfigurationException

            if '[' in config:
                hostname_part, ip_part, password = config.split()
                hosts = []
                ips = []
                if '[' in hostname_part and '[' in ip_part:
                    hosts = self.parse_hosts(hostname_part)
                    ips = self.parse_hosts(ip_part)
                else:
                    raise InvalidConfigurationException

                if len(hosts) != len(ips):
                    raise InvalidConfigurationException("Configuration is invalid")
                for index, ip in enumerate(ips):
                    parsed_configs.append((hosts[index], ip, password))
            else:
                parsed_configs.append(tuple(config.split()))

        return parsed_configs




class Validator:
    def __init__(self):
        self.err_messages = []

    def validate(self):
        pass


class FileManager:
    class FileType(Enum):
        RAW = 'raw'
        JSON = 'json'
        YAML = 'yaml'

    @staticmethod
    def read_file(file_path, file_type: FileType):
        if file_type == FileManager.FileType.RAW:
            with open(file_path, 'r') as file:
                return file.read()
        elif file_type == FileManager.FileType.JSON:
            with open(file_path, 'r') as file:
                try:
                    return json.load(file)
                except Exception as e:
                    print("")
        elif file_type == FileManager.FileType.YAML:
            with open(file_path, 'r') as file:
                return yaml.safe_load(file)
        else:
            raise ValueError("Unsupported file type")

    @staticmethod
    def write_file(file_path, data, file_type: FileType):
        if file_type == FileManager.FileType.RAW:
            with open(file_path, 'w') as file:
                file.write(data)
        elif file_type == FileManager.FileType.JSON:
            with open(file_path, 'w') as file:
                json.dump(data, file, indent=4)
        elif file_type == FileManager.FileType.YAML:
            with open(file_path, 'w') as file:
                yaml.dump(data, file)
        else:
            raise ValueError("Unsupported file type")


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




class ParserFactory:
    _parsers = {}

    @classmethod
    def register_parser(cls, parser_cls):
        parser_name = to_camel_case(parser_cls.__name__).lower()
        cls._parsers[parser_name] = parser_cls

    @classmethod
    def get_parser(cls, parser_type):
        parser_class = cls._parsers.get(parser_type)
        if not parser_class:
            raise ValueError(f"Unknown parser type: {parser_type}")
        return parser_class()


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
#         if validator_type == 'service':
#             return ServiceValidator(ServiceMap())
#         elif validator_type == 'topology':
#             return TopologyValidator(conf_data)
#         elif validator_type == 'group_consistency':
#             return GroupConsistencyValidator(conf_data, parsed_data)
#         elif validator_type == 'hosts_info':
#             return HostsInfoValidator(parsed_data)


# Main ConfUtils class using the above components

class DefaultConfigurationLoader:
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


class ServiceManager:
    def __init__(self, advanced_conf):
        self.advanced_conf = advanced_conf

    def get_service_key_from_service(self, service_name):
        for service_key, service_info in ServiceMap().get_services_map().items():
            if service_name in service_info["server"]:
                return service_key
        raise InvalidConfigurationException(f"Service '{service_name}' not found in services map.")

    def get_services_need_install(self):
        group_services = self.advanced_conf.get("group_services")
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

        # 根据用户配置动态生成一些变量
        extra_vars = {
            "ntp_server_hostname": self._generate_ntp_server_hostname(),
            "hadoop_base_dir": self.advanced_conf.get("data_dirs")[0],
            "kdc_hostname": self.get_kdc_server_host(),
            "database_hostname": self._generate_database_host(),
            "ambari_server_host": self.get_ambari_server_host(),
            "ambari_repo_url": self._generate_ambari_repo_url()
        }
        conf_j2_context = self.advanced_conf.get_conf()
        conf_j2_context.update(extra_vars)
        hosts_groups_variables = self.generate_hosts_groups_variables()
        rendered_conf_vars = self.template_renderer.render_template(str_conf, conf_j2_context).decode_result(
            decoder="yaml")
        rendered_conf_vars.update(hosts_groups_variables)
        rendered_conf_vars.update(extra_vars)
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

    def is_ambari_repo_configured(self):
        repos = self.advanced_conf.get('repos', [])
        if len(repos) > 0:
            for repo_item in repos:
                if "ambari_repo" == repo_item["name"]:
                    return True
        return False

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
        ipaddress= self.get_ip_address()
        if not self.is_ambari_repo_configured():
            ambari_repo_rl = f"http://{ipaddress}:8881/repository/yum/udh3"
            #todo 在 conf 中生成 {"name": "ambari_repo", "url": ambari_repo_rl}
            # self.conf["repos"].append({"name": "ambari_repo", "url": ambari_repo_rl})
            # logger.info(f"generate_ambari_repo {ambari_repo_rl}")

        return ambari_repo_rl


# 两类conf 一种是直接读取得到的conf , 一种是需要render, 动态解析扩展形成的conf
# render 动态扩展的conf是给 ansible 的var conf 使用
class BaseConfiguration:
    def __init__(self, name, conf_loader=DefaultConfigurationLoader):
        self.conf_loader = conf_loader
        self.name = name
        self.conf = {}
        self.format = FileManager.FileType.YAML
        self.conf_file_path = self.get_default_path()

    def get_parser(self):
        class_name = self.__class__.__name__.lower()
        ParserFactory.get_parser(class_name)

    def set_format(self, format):
        self.format = format
        return self

    def set_path(self, new_dir):
        self.conf_file_path = os.path.join(new_dir, self.name)
        return self

    def get_default_path(self):
        return os.path.join(CONF_DIR, self.name)

    def set_conf(self, conf):
        self.conf = conf
        return self

    def get_conf(self):
        if not self.conf:
            self.conf = self.conf_loader(CONF_DIR).load_conf(self.name)
        return self.conf

    def get_str_conf(self):
        str_conf = FileManager.read_file(os.path.join(CONF_DIR, self.name), FileManager.FileType.RAW)
        return str_conf

    def get(self, key, default=None):
        conf = self.get_conf()
        try:
            return conf[key]
        except KeyError:
            if default is not None:
                return default
            raise InvalidConfigurationException(f"Configuration key '{key}' is missing.")

    def save(self):
        FileManager.write_file(self.conf_file_path, self.get_conf(), self.format)

    def save_with_str(self, str_conf):
        FileManager.write_file(self.conf_file_path, str_conf, FileManager.FileType.RAW)


class StandardConfiguration(BaseConfiguration, HostsInfoParser):
    def __init__(self, name):
        super().__init__(name)
        self.parsed_conf={}

    class GenerateConfType(Enum):
        AdvancedConfiguration = 'AdvancedConfiguration'
        HostsInfoConfiguration = 'HostsInfoConfiguration'

    def get_conf(self):
        if not self.parsed_conf:
            original_conf = super().get_conf()
            hosts_info_arr = self.parse(original_conf.get("hosts"))
            original_conf.update({"hosts": hosts_info_arr})
            self.parsed_conf = original_conf

        return self.parsed_conf

    def get_parsed_hosts_names(self ):
        parsed_hosts = self.get_conf().get("hosts")
        hosts_names = []
        for host_info in parsed_hosts:
            hostname = host_info[1]
            hosts_names.append(hostname)
        return hosts_names

    def generate_conf(self, conf_type: GenerateConfType):
        conf = self.get_conf()
        make_hosts_string = lambda arr: [" ".join(tple) for tple in arr]
        if conf_type == StandardConfiguration.GenerateConfType.HostsInfoConfiguration:
            hosts_info_yaml_data = {
                "user": conf["user"],
                "hosts": make_hosts_string(conf["hosts"])
            }
            hosts_info_conf = HostsInfoConfiguration()
            hosts_info_conf.set_conf(hosts_info_yaml_data).save()
            return hosts_info_conf

        if conf_type == StandardConfiguration.GenerateConfType.AdvancedConfiguration:
            conf_yaml_data = {
                "default_password": conf["default_password"],
                "data_dirs": conf["data_dirs"],
                "repos": conf["repos"]
            }
            conf_tpl_file = GET_CONF_TPL_NAME(CONF_NAME)
            # todo hostname fetcher
            advanced_tpl_str_conf = AdvancedConfiguration(conf_tpl_file).get_str_conf()
            hosts_names = self.get_parsed_hosts_names()
            topology_manager = TopologyManager(lambda: hosts_names)
            topology = topology_manager.generate_topology()
            topology.update(conf_yaml_data)

            merged_conf_str = self.merge_conf(topology, base_conf=advanced_tpl_str_conf, merge_strategy="prepend")
            advanced_conf = AdvancedConfiguration()
            advanced_conf.save_with_str(merged_conf_str)
            return advanced_conf

    def merge_conf(self, yaml_need_merge, base_conf=None, merge_strategy="replace"):
        current_conf = yaml_need_merge
        valid_strategies = ["prepend", "replace"]
        assert merge_strategy in valid_strategies, f"Invalid merge strategy. Supported: {valid_strategies}"

        existing_conf = base_conf or {}
        if merge_strategy == "prepend":
            raw_data = base_conf
            prepend_yaml_str = yaml.dump(current_conf, default_flow_style=None, sort_keys=False)
            merged_conf = prepend_yaml_str + "\n" + raw_data
        elif merge_strategy == "replace":
            # dict
            existing_conf.update(current_conf)
            merged_conf = existing_conf
        else:
            raise Exception(f"Invalid merge strategy. Supported: {valid_strategies}")
        return merged_conf


class AdvancedConfiguration(BaseConfiguration):
    def __init__(self, name=CONF_NAME):
        super().__init__(name)


class HostsInfoConfiguration(BaseConfiguration, HostsInfoParser):
    def __init__(self, name=HOSTS_CONF_NAME):
        super().__init__(name)

    # def get_parsed_hosts_names(self):
    #     parsed_hosts = self.get_hosts_info()
    #     hosts_names = []
    #     for host_info in parsed_hosts:
    #         hostname = host_info[1]
    #         hosts_names.append(hostname)
    #     return hosts_names

    # def get_hosts_info(self):
    #     hosts_info_arr = self.parse(self.get_conf().get("hosts"))
    #     return hosts_info_arr

    def get_hosts_info(self):
        hosts_info_arr = self.get_conf()
        return hosts_info_arr.get("hosts")

    def get_user(self):
        # 默认部署user 为root
        return self.get("user", "root")


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


class AnsibleVarConfiguration(BaseConfiguration):
    def __init__(self, name, dynamic_variable_generator: DynamicVariableGenerator):
        self.dynamic_variable_generator = dynamic_variable_generator
        super().__init__(name)

    def generate_ansible_variables_conf(self):
        rendered_advanced_conf = self.dynamic_variable_generator.generate()
        for key in ["host_groups", "group_services"]:
            rendered_advanced_conf.pop(key, None)

        self.set_conf(rendered_advanced_conf)

    def get_conf(self):
        self.generate_ansible_variables_conf()
        return self.conf

    def save(self):
        self.set_path(os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/group_vars')).set_format(FileManager.FileType.YAML)
        super().save()


class AmbariBluePrintConfiguration(BaseConfiguration):
    def __init__(self, name, dynamic_variable_generator: DynamicVariableGenerator, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.dynamic_variable_generator = dynamic_variable_generator
        super().__init__(name)

    def get_rendered_advanced_conf(self):
        rendered_advanced_conf = self.dynamic_variable_generator.generate()
        return rendered_advanced_conf

    def get_conf_j2template_path(self, service_name):
        service_key = self.service_manager.get_service_key_from_service(service_name)
        file_name = f"{service_key}_configuration.json.j2"
        return os.path.join(CLUSTER_TEMPLATES_DIR, file_name)

    def generate_blueprint_configurations(self):
        rendered_conf = self.get_rendered_advanced_conf()
        services_need_install = self.service_manager.get_services_need_install()
        configurations = []
        processed_services = []

        for service_name in services_need_install:
            service_key = self.service_manager.get_service_key_from_service(service_name)
            if service_key in processed_services:
                continue

            template_render = TemplateRenderer()
            tpl_str = FileManager.read_file(self.get_conf_j2template_path(service_name), FileManager.FileType.RAW)

            if not tpl_str:
                # 有的配置模版为空白
                continue

            service_confs = template_render.render_template(
                tpl_str,
                rendered_conf).decode_result(decoder="json")

            if service_confs:
                configurations.extend([{k: v} for k, v in service_confs.items() if isinstance(v, dict)])
            else:
                logger.error(f"Error in configuration template for service {service_name}")

            processed_services.append(service_key)

        return configurations

    def generate_blueprint_host_groups(self):
        rendered_conf = self.get_rendered_advanced_conf()
        host_groups = []
        services_need_install = self.service_manager.get_services_need_install()
        all_services_clients = self.service_manager.get_service_clients_need_install(services_need_install)

        for group_name, services in rendered_conf["group_services"].items():
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

    def generate_ambari_blueprint(self, blueprint_configurations, blueprint_service_host_groups):
        rendered_conf = self.get_rendered_advanced_conf()
        security = rendered_conf.get("security")
        blueprint_security = "KERBEROS" if security.strip().lower() != "none" else "NONE"
        ambari_repo_url = rendered_conf.get("ambari_repo_url")

        j2_context = {
            "blueprint_security": blueprint_security,
            "ambari_blueprint_configurations": json.dumps(blueprint_configurations),
            "ambari_blueprint_host_groups": json.dumps(blueprint_service_host_groups),
            "ambari_repo_url": ambari_repo_url,
        }

        template_renderer = TemplateRenderer()

        blueprint_json = template_renderer.render_template(
            FileManager.read_file(os.path.join(CLUSTER_TEMPLATES_DIR, "base_blueprint.json.j2"),
                                  FileManager.FileType.RAW),
            j2_context).decode_result()
        self.conf = blueprint_json

    def get_conf(self):
        blueprint_configurations = self.generate_blueprint_configurations()
        blueprint_service_host_groups = self.generate_blueprint_host_groups()
        self.generate_ambari_blueprint(blueprint_configurations, blueprint_service_host_groups)
        return self.conf

    def save(self):
        self.set_path(BLUEPRINT_FILES_DIR).set_format(FileManager.FileType.JSON)
        super().save()


class AmbariClusterTemplateConfiguration(BaseConfiguration):
    def __init__(self, name, dynamic_variable_generator: DynamicVariableGenerator):
        self.dynamic_variable_generator = dynamic_variable_generator
        super().__init__(name)

    def get_rendered_advanced_conf(self):
        rendered_advanced_conf = self.dynamic_variable_generator.generate()
        return rendered_advanced_conf

    def generate_ambari_cluster_template(self):
        rendered_advanced_conf = self.get_rendered_advanced_conf()
        security = rendered_advanced_conf["security"]
        kerberos_admin_principal = f"{rendered_advanced_conf['security_options']['admin_principal']}@{rendered_advanced_conf['security_options']['realm']}"
        kerberos_admin_password = rendered_advanced_conf["security_options"]["admin_password"]
        ambari_cluster_template_host_groups = []

        for group_name, group_hosts in rendered_advanced_conf["host_groups"].items():
            hosts = [{'fqdn': host} for host in group_hosts]
            ambari_cluster_template_host_groups.append({
                "name": group_name,
                "hosts": hosts
            })

        cluster_template = {
            "blueprint": rendered_advanced_conf["blueprint_name"],
            "config_recommendation_strategy": rendered_advanced_conf["ambari_options"][
                "config_recommendation_strategy"],
            "default_password": rendered_advanced_conf["default_password"],
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
        self.conf = cluster_template

    def get_conf(self):
        self.generate_ambari_cluster_template()
        return self.conf

    def save(self):
        self.set_path(BLUEPRINT_FILES_DIR).set_format(FileManager.FileType.JSON)
        super().save()


# Define Validator classes
class TopologyValidator(Validator):
    def __init__(self, conf: AdvancedConfiguration):
        super().__init__()
        self.host_groups = conf.get("host_groups")
        self.host_group_services = conf.get("group_services")
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


class ServiceValidator(Validator):
    def __init__(self, service_map):
        super().__init__()
        self.service_map = service_map

    def validate_service(self, service_name):
        errors = []
        if not self.service_map.is_service_supported(service_name):
            errors.append(f"Service '{service_name}' is not supported.")
        # Additional service-specific validation can be added here
        return errors


class GroupConsistencyValidator(Validator):

    def __init__(self, advanced_conf: AdvancedConfiguration, hosts_info_conf: HostsInfoConfiguration):
        super().__init__()
        self.hosts_info_conf = hosts_info_conf.get_conf()
        self.host_groups = advanced_conf.get("host_groups")
        self.host_group_services = advanced_conf.get("group_services")

    def validate(self):
        parsed_hosts = self.hosts_info_conf.get("hosts")
        conf_defined_hosts = {}
        host_groups_group_names = []
        host_group_services_group_names = []

        for host_info_str in parsed_hosts:
            host_info = host_info_str.split()
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


def main():
    # 目标 1.从stand_conf 动态生成复杂conf
    # 目标 2.解析复杂conf 生成 ambari blueprint 和 ambari cluster_template
    # 目标 3. 生成ansible hosts 和 variable 文件
    validators = []

    # todo validate
    sd_conf = StandardConfiguration(BASE_CONF_NAME)
    hosts_info_conf = sd_conf.generate_conf(StandardConfiguration.GenerateConfType.HostsInfoConfiguration)
    advanced_conf = sd_conf.generate_conf(StandardConfiguration.GenerateConfType.AdvancedConfiguration)

    ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json",
                                                                               DynamicVariableGenerator(advanced_conf))
    ambari_cluster_template_configuration.save()

    ambari_blue_print_configuration = AmbariBluePrintConfiguration("blueprint.json",
                                                                   DynamicVariableGenerator(advanced_conf),
                                                                   ServiceManager(advanced_conf))
    ambari_blue_print_configuration.save()

    validators.append(TopologyValidator(advanced_conf))
    validators.append(GroupConsistencyValidator(advanced_conf, hosts_info_conf))
    validators.append(HostsInfoValidator(hosts_info_conf))

    validation_manager = ValidationManager(validators)
    errors = validation_manager.validate_all()
    if errors:
        error_messages = "\n".join(errors)
        raise ValueError(f"Configuration validation failed with the following errors:\n{error_messages}")

    AnsibleVarConfiguration("all", DynamicVariableGenerator(advanced_conf)).save()
    AnsibleHostConfiguration("hosts", hosts_info_conf, DynamicVariableGenerator(advanced_conf)).save()

    # blueprint_utils.generate_ansible_hosts(conf, hosts_info, ambari_server_host)


if __name__ == '__main__':
    main()
