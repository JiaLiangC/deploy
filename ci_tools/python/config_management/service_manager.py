from .service_map import *


class ServiceManager:
    def __init__(self, advanced_conf):
        self.advanced_conf = advanced_conf


    def get_services_need_install(self):
        group_services = self.advanced_conf.get("group_services")
        services = []
        for group_name, host_components in group_services.items():
            services.extend(host_components)
        return list(set(services))



    def get_service_clients_need_install(self, services):
        clients = []
        for service_name in services:
            service_info = ServiceMap.get_service_info(service_name)
            if service_info and "clients" in service_info:
                clients.extend(service_info["clients"])
        return list(set(clients))
