
# Generated by CodiumAI

from ci_tools.python.install_utils.conf_refactor import StandardConfiguration

import pytest

class TestStandardConfiguration:

    #  can parse a valid configuration file and return the parsed configuration
    def test_parse_valid_configuration_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("valid_config")

        # Invoke the method being tested
        parsed_conf = sd_conf.get_conf()

        # Assert the expected result
        assert isinstance(parsed_conf, dict)
        assert "hosts" in parsed_conf
        assert "user" in parsed_conf
        assert "default_password" in parsed_conf
        assert "data_dirs" in parsed_conf
        assert "repos" in parsed_conf

    #  can generate a HostsInfoConfiguration object from a valid configuration file
    def test_generate_hosts_info_configuration_valid_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("valid_config")

        # Invoke the method being tested
        hosts_info_conf = sd_conf.generate_conf(StandardConfiguration.GenerateConfType.HostsInfoConfiguration)

        # Assert the expected result
        assert isinstance(hosts_info_conf, HostsInfoConfiguration)
        assert hosts_info_conf.get("user") == "root"
        assert hosts_info_conf.get_hosts_info() == ["host1 192.168.1.1 password", "host2 192.168.1.2 password"]

    #  can generate an AdvancedConfiguration object from a valid configuration file
    def test_generate_advanced_configuration_valid_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("valid_config")

        # Invoke the method being tested
        advanced_conf = sd_conf.generate_conf(StandardConfiguration.GenerateConfType.AdvancedConfiguration)

        # Assert the expected result
        assert isinstance(advanced_conf, AdvancedConfiguration)
        assert advanced_conf.get("default_password") == "password"
        assert advanced_conf.get("data_dirs") == ["/data1", "/data2"]
        assert advanced_conf.get("repos") == ["repo1", "repo2"]

    #  can merge two YAML configurations using a replace strategy
    def test_merge_yaml_replace_strategy(self):
        # Initialize the class
        sd_conf = StandardConfiguration("valid_config")

        # Define the YAML configurations to merge
        yaml1 = {"key1": "value1", "key2": "value2"}
        yaml2 = {"key2": "new_value2", "key3": "value3"}

        # Invoke the method being tested
        merged_yaml = sd_conf.merge_conf(yaml2, base_conf=yaml1, merge_strategy="replace")

        # Assert the expected result
        assert isinstance(merged_yaml, dict)
        assert merged_yaml == {"key1": "value1", "key2": "new_value2", "key3": "value3"}

    #  can merge two YAML configurations using a prepend strategy
    def test_merge_yaml_prepend_strategy(self):
        # Initialize the class
        sd_conf = StandardConfiguration("valid_config")

        # Define the YAML configurations to merge
        yaml1 = {"key1": "value1", "key2": "value2"}
        yaml2 = {"key2": "new_value2", "key3": "value3"}

        # Invoke the method being tested
        merged_yaml = sd_conf.merge_conf(yaml2, base_conf=yaml1, merge_strategy="prepend")

        # Assert the expected result
        assert isinstance(merged_yaml, str)
        assert merged_yaml == "key1: value1\nkey2: new_value2\nkey3: value3\n"

    #  raises InvalidConfigurationException when a configuration file is missing a required key
    def test_missing_required_key(self):
        # Initialize the class
        sd_conf = StandardConfiguration("missing_key_config")

        # Invoke the method being tested and assert the expected exception
        with pytest.raises(InvalidConfigurationException):
            sd_conf.get_conf()

    #  raises InvalidConfigurationException when a configuration file has an invalid format
    def test_invalid_configuration_format(self):
        # Initialize the class
        sd_conf = StandardConfiguration("invalid_format_config")

        # Invoke the method being tested and assert the expected exception
        with pytest.raises(InvalidConfigurationException):
            sd_conf.get_conf()

    #  can save a configuration to a file
    def test_save_configuration_to_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("test_config")

        # Set the configuration
        conf_data = {
            "hosts": [
                ["host1", "10.0.0.1", "password1"],
                ["host2", "10.0.0.2", "password2"]
            ],
            "user": "root",
            "default_password": "password",
            "data_dirs": ["/data1", "/data2"],
            "repos": ["repo1", "repo2"]
        }
        sd_conf.set_conf(conf_data)

        # Save the configuration
        sd_conf.save()

        # Read the saved configuration
        saved_conf = FileManager.read_file(sd_conf.conf_file_path, FileManager.FileType.YAML)

        # Assert the expected result
        assert saved_conf == yaml.dump(conf_data)

    #  raises InvalidConfigurationException when generating a HostsInfoConfiguration with an invalid configuration file
    def test_generate_hosts_info_configuration_invalid_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("invalid_config")

        # Assert that InvalidConfigurationException is raised
        with pytest.raises(InvalidConfigurationException):
            sd_conf.generate_conf(StandardConfiguration.GenerateConfType.HostsInfoConfiguration)

    #  raises InvalidConfigurationException when generating an AdvancedConfiguration with an invalid configuration file
    def test_generate_advanced_configuration_invalid_file(self):
        # Initialize the class
        sd_conf = StandardConfiguration("invalid_config")

        # Assert that InvalidConfigurationException is raised
        with pytest.raises(InvalidConfigurationException):
            sd_conf.generate_conf(StandardConfiguration.GenerateConfType.AdvancedConfiguration)
