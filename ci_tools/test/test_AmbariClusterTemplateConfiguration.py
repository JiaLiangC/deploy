
# Generated by CodiumAI

from ci_tools.python.install_utils.conf_refactor import AmbariClusterTemplateConfiguration

import pytest

class TestAmbariClusterTemplateConfiguration:

    #  can generate ambari cluster template
    def test_generate_ambari_cluster_template(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        ambari_cluster_template_configuration.generate_ambari_cluster_template()
        assert ambari_cluster_template_configuration.conf is not None

    #  can get rendered advanced conf
    def test_get_rendered_advanced_conf(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        rendered_advanced_conf = ambari_cluster_template_configuration.get_rendered_advanced_conf()
        assert isinstance(rendered_advanced_conf, dict)

    #  can get conf
    def test_get_conf(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        conf = ambari_cluster_template_configuration.get_conf()
        assert isinstance(conf, dict)

    #  can save
    def test_save(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        ambari_cluster_template_configuration.save()
        assert os.path.exists(ambari_cluster_template_configuration.conf_file_path)

    #  can set format
    def test_set_format(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        ambari_cluster_template_configuration.set_format(FileManager.FileType.JSON)
        assert ambari_cluster_template_configuration.format == FileManager.FileType.JSON

    #  raises InvalidConfigurationException if configuration key is missing
    def test_missing_configuration_key(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        with pytest.raises(InvalidConfigurationException):
            ambari_cluster_template_configuration.get("missing_key")

    #  raises ValueError if input conf is not a dictionary
    def test_invalid_input_conf(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        with pytest.raises(ValueError):
            ambari_cluster_template_configuration.set_conf("invalid_conf")

    #  raises ValueError if input str_conf is not a string
    def test_invalid_input_str_conf(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        with pytest.raises(ValueError):
            ambari_cluster_template_configuration.save_with_str(123)

    #  raises FileNotFoundError if configuration file not found
    def test_file_not_found(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("nonexistent_file.json", dynamic_variable_generator)
        with pytest.raises(FileNotFoundError):
            ambari_cluster_template_configuration.save()

    #  can set path
    def test_set_path(self):
        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        ambari_cluster_template_configuration = AmbariClusterTemplateConfiguration("cluster_template.json", dynamic_variable_generator)
        ambari_cluster_template_configuration.set_path("/new/path")
        assert ambari_cluster_template_configuration


    #  Generates a cluster template with the correct blueprint name, config recommendation strategy, default password, and host groups
    def test_generate_cluster_template_with_correct_values(self):
        advanced_conf = {
            "security": "mit-kdc",
            "security_options": {
                "admin_principal": "admin",
                "realm": "EXAMPLE.COM",
                "admin_password": "password"
            },
            "host_groups": {
                "group1": ["host1", "host2"],
                "group2": ["host3", "host4"]
            },
            "blueprint_name": "my_blueprint",
            "ambari_options": {
                "config_recommendation_strategy": "ALWAYS_APPLY_RECOMMENDATIONS"
            },
            "default_password": "default_password"
        }

        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        cluster_template_configuration = AmbariClusterTemplateConfiguration("my_configuration", dynamic_variable_generator)
        cluster_template_configuration.generate_ambari_cluster_template()

        expected_cluster_template = {
            "blueprint": "my_blueprint",
            "config_recommendation_strategy": "ALWAYS_APPLY_RECOMMENDATIONS",
            "default_password": "default_password",
            "host_groups": [
                {
                    "name": "group1",
                    "hosts": [
                        {"fqdn": "host1"},
                        {"fqdn": "host2"}
                    ]
                },
                {
                    "name": "group2",
                    "hosts": [
                        {"fqdn": "host3"},
                        {"fqdn": "host4"}
                    ]
                }
            ]
        }

        assert cluster_template_configuration.conf == expected_cluster_template

    #  Includes credentials and security information when security is enabled with MIT-KDC
    def test_generate_cluster_template_with_security_enabled(self):
        advanced_conf = {
            "security": "mit-kdc",
            "security_options": {
                "admin_principal": "admin",
                "realm": "EXAMPLE.COM",
                "admin_password": "password"
            },
            "host_groups": {
                "group1": ["host1", "host2"],
                "group2": ["host3", "host4"]
            },
            "blueprint_name": "my_blueprint",
            "ambari_options": {
                "config_recommendation_strategy": "ALWAYS_APPLY_RECOMMENDATIONS"
            },
            "default_password": "default_password"
        }

        dynamic_variable_generator = DynamicVariableGenerator(advanced_conf)
        cluster_template_configuration = AmbariClusterTemplateConfiguration("my_configuration", dynamic_variable_generator)
        cluster_template_configuration.generate_ambari_cluster_template()

        expected_cluster_template = {
            "blueprint": "my_blueprint",
            "config_recommendation_strategy": "ALWAYS_APPLY_RECOMMENDATIONS",
            "default_password": "default_password",
            "host_groups": [
                {
                    "name": "group1",
                    "hosts": [
                        {"fqdn": "host1"},
                        {"fqdn": "host2"}
                    ]
                },
                {
                    "name": "group2",
                    "hosts": [
                        {"fqdn": "host3"},
                        {"fqdn": "host4"}
                    ]
                }
            ],
            "credentials": [
                {
                    "alias": "kdc.admin.credential",
                    "principal": "admin@EXAMPLE.COM",
                    "key": "password",
                    "type": "TEMPORARY"
                }
            ],
            "security": {
                "type": "KERBEROS"
            }
        }

        assert cluster_template_configuration.conf == expected_cluster_template