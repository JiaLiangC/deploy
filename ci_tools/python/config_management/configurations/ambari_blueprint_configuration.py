from python.config_management.dynamic_variable_generator import DynamicVariableGenerator
from python.config_management.service_manager import *
from python.config_management.template_renderer import *

from .base_configuration import *


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
