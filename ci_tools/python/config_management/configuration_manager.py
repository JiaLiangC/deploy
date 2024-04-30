# -*- coding: UTF-8 -*-

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.config_management.configurations.advanced_configuration import *
from python.config_management.configurations.hosts_info_configuration import *
from python.config_management.configurations.ambari_blueprint_configuration import *
from python.config_management.configurations.ambari_cluster_template_configuration import *
from python.config_management.configurations.ansible_host_configuration import *
from python.config_management.configurations.ansible_var_configuration import *
from python.config_management.configurations.standard_configuration import *
from python.config_management.group_consistency_validator import *
from python.config_management.hosts_info_validator import *
from python.config_management.topology_validator import *
from python.config_management.validation_manager import *
from python.config_management.conf_validator import *
from python.utils.os_utils import *

logger = get_logger()


class ConfigurationManager:
    def __init__(self, base_conf_name):
        self.base_conf_name = base_conf_name
        self.sd_conf = StandardConfiguration(self.base_conf_name)
        self.validators = []
        self.allowed_methods = {'is_ambari_repo_configured'}


    def __getattr__(self, name):
        if name in self.allowed_methods:
            def method(*args, **kwargs):
                if self.advanced_conf and hasattr(self.advanced_conf, name):
                    return getattr(self.advanced_conf, name)(*args, **kwargs)
                else:
                    raise AttributeError(f"'{type(self.advanced_conf).__name__}' object has no attribute '{name}'")
            return method
        else:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def load_confs(self):
        self.hosts_info_conf = HostsInfoConfiguration()
        self.advanced_conf = AdvancedConfiguration()

    def generate_confs(self, save=False):
        cv = ConfValidator(self.sd_conf)
        err = cv.validate().err_messages
        if err:
            error_messages = "\n".join(err)
            raise ValueError(f"Configuration validation failed with the following errors:\n{error_messages}")

        self.hosts_info_conf = self.sd_conf.generate_conf(StandardConfiguration.GenerateConfType.HostsInfoConfiguration,
                                                          save)
        self.advanced_conf = self.sd_conf.generate_conf(StandardConfiguration.GenerateConfType.AdvancedConfiguration,
                                                        save)

    def save_ambari_configurations(self):
        stack_version = self.sd_conf.get("stack_version","3.2.0")
        ambari_cluster_template_conf = AmbariClusterTemplateConfiguration(
            "cluster_template.json", DynamicVariableGenerator(self.advanced_conf))
        ambari_cluster_template_conf.save()

        ambari_blue_print_conf = AmbariBluePrintConfiguration(
            "blueprint.json", DynamicVariableGenerator(self.advanced_conf), ServiceManager(self.advanced_conf), stack_version)
        ambari_blue_print_conf.save()

    def setup_validators(self):
        self.validators.append(TopologyValidator(self.advanced_conf))
        self.validators.append(GroupConsistencyValidator(self.advanced_conf, self.hosts_info_conf))
        self.validators.append(HostsInfoValidator(self.hosts_info_conf))

    def validate_configurations(self):
        validation_manager = ValidationManager(self.validators)
        errors = validation_manager.validate_all()
        if errors:
            error_messages = "\n".join(errors)
            raise ValueError(f"Configuration validation failed with the following errors:\n{error_messages}")

    def save_ansible_configurations(self):
        AnsibleVarConfiguration("all", DynamicVariableGenerator(self.advanced_conf)).save()
        AnsibleHostConfiguration("hosts", self.hosts_info_conf, self.sd_conf, DynamicVariableGenerator(self.advanced_conf)).save()


if __name__ == '__main__':
    # Usage
    config_manager = ConfigurationManager(BASE_CONF_NAME)
    config_manager.generate_confs(save=True)
    config_manager.save_ambari_configurations()
    config_manager.setup_validators()
    config_manager.validate_configurations()
    config_manager.save_ansible_configurations()
