from python.config_management.dynamic_variable_generator import DynamicVariableGenerator

from .base_configuration import *


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
