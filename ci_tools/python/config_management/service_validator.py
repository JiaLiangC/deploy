from validator import *


class ServiceValidator(Validator):
    def __init__(self, service_map):
        super().__init__()
        self.service_map = service_map

    def validate(self, service_name):
        if not self.service_map.is_service_supported(service_name):
            self.err_messages.append(f"Service '{service_name}' is not supported.")
