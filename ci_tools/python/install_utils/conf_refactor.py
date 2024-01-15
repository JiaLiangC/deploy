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








# Define Service-related classes




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

# 两类conf 一种是直接读取得到的conf , 一种是需要render, 动态解析扩展形成的conf
# render 动态扩展的conf是给 ansible 的var conf 使用


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



if __name__ == '__main__':
    main()
