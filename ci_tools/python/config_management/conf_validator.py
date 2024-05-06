from .validator import *
from python.config_management.service_map import *

class ConfValidator(Validator):
    def __init__(self, base_conf):
        self.base_conf = base_conf
        super().__init__()

    def validate(self):
        if self.base_conf.get("components_to_install") == None or len(self.base_conf.get("components_to_install"))==0:
            self.err_messages.append(f"components_to_install property must be configured")

        for com in self.base_conf.get("components_to_install"):
            if not ServiceMap.is_component_supported(com):
                self.err_messages.append(f"component '{com}' is not supported.")
        return self
