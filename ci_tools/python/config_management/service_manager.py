from .service_map import *


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
