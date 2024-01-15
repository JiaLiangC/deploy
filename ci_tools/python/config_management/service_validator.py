from validator import *


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
