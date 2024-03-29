
# Generated by CodiumAI

from ci_tools.python.install_utils.conf_refactor import TopologyValidator

import pytest

class TestTopologyValidator:

    #  validate method returns successfully when all service instances are within the allowed range
    def test_validate_all_instances_within_range(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when all service instances are at the minimum allowed range
    def test_validate_all_instances_at_minimum_range(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'ambari': {'AMBARI_SERVER': {'min_instances': 1, 'max_instances': 1}}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when all service instances are at the maximum allowed range
    def test_validate_all_instances_at_maximum_range(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'ambari': {'AMBARI_SERVER': {'min_instances': 1, 'max_instances': 2}}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when all service instances are at the odd number of instances allowed range
    def test_validate_all_instances_at_odd_number_range(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'ambari': {'AMBARI_SERVER': {'min_instances': 1, 'max_instances': None, 'odd_only': True}}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when all service instances are at the minimum allowed range and there is only one host group
    def test_validate_all_instances_at_minimum_range_single_host_group(self):
        conf = AdvancedConfiguration()
        conf.host_groups = {'group1': ['host1', 'host2']}
        conf.group_services = {'group1': ['AMBARI_SERVER']}
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'ambari': {'AMBARI_SERVER': {'min_instances': 1, 'max_instances': 1}}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method raises a ValueError when the input conf parameter is not an instance of AdvancedConfiguration
    def test_validate_raises_value_error_for_invalid_conf_type(self):
        with pytest.raises(ValueError):
            validator = TopologyValidator('invalid_conf')
            validator.validate()

    #  validate method raises an AttributeError when the input conf parameter does not have the 'host_groups' and 'group_services' attributes
    def test_validate_raises_attribute_error_for_invalid_conf_attributes(self):
        conf = AdvancedConfiguration()
        with pytest.raises(AttributeError):
            validator = TopologyValidator(conf)
            validator.validate()

    #  validate method returns an error message when a service instance is below the minimum allowed range
    def test_validate_returns_error_message_for_instance_below_minimum_range(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'ambari': {'AMBARI_SERVER': {'min_instances': 2, 'max_instances': 2}}}
        validator.validate()
        assert len(validator.err_messages) == 1
        assert 'AMBARI_SERVER 的实例数 0 小于最小实例数 2' in validator.err_messages

    #  validate method returns successfully when all service instances are at the maximum allowed range and there is only one host group
    def test_validate_all_instances_at_maximum_range_one_host_group(self):
        conf = AdvancedConfiguration()
        conf.host_groups = {'group1': ['host1', 'host2']}
        conf.group_services = {'group1': ['service1', 'service2']}
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'service1': {'min_instances': 1, 'max_instances': 2}, 'service2': {'min_instances': 1, 'max_instances': 2}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when all service instances are at the odd number of instances allowed range and there is only one host group
    def test_validate_all_instances_at_odd_number_range_one_host_group(self):
        conf = AdvancedConfiguration()
        conf.host_groups = {'group1': ['host1', 'host2', 'host3']}
        conf.group_services = {'group1': ['service1', 'service2']}
        validator = TopologyValidator(conf)
        validator.pattern_rules = {'service1': {'min_instances': 1, 'max_instances': None, 'odd_only': True}, 'service2': {'min_instances': 1, 'max_instances': None, 'odd_only': True}}
        validator.validate()
        assert len(validator.err_messages) == 0

    #  validate method returns successfully when there are no services to install
    def test_validate_no_services_to_install(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0




# Generated by CodiumAI

from ci_tools.python.install_utils.conf_refactor import TopologyValidator

import pytest

class TestCheckPattern:

    #  Verify that when all service counts are within their respective minimum and maximum limits, no error messages are returned.
    def test_all_counts_within_limits(self):
        service_rules = {
            "NAMENODE": {"min_instances": 2, "max_instances": 2},
            "ZKFC": {"min_instances": 2, "max_instances": 2},
            "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
            "DATANODE": {"min_instances": 1, "max_instances": None},
            "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
        }

        service_counter = {
            "NAMENODE": 2,
            "ZKFC": 2,
            "JOURNALNODE": 3,
            "DATANODE": 1,
            "SECONDARY_NAMENODE": 0
        }

        validator = TopologyValidator(AdvancedConfiguration())
        messages = validator.check_pattern(service_rules, service_counter)
        assert len(messages) == 0

    #  Ensure that when a service count is equal to its minimum limit, no error messages are returned.
    def test_count_equal_to_minimum(self):
        service_rules = {
            "NAMENODE": {"min_instances": 2, "max_instances": 2},
            "ZKFC": {"min_instances": 2, "max_instances": 2},
            "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
            "DATANODE": {"min_instances": 1, "max_instances": None},
            "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
        }

        service_counter = {
            "NAMENODE": 2,
            "ZKFC": 2,
            "JOURNALNODE": 3,
            "DATANODE": 1,
            "SECONDARY_NAMENODE": 0
        }

        validator = TopologyValidator(AdvancedConfiguration())
        messages = validator.check_pattern(service_rules, service_counter)
        assert len(messages) == 0

    #  Ensure that when a service count is equal to its maximum limit, no error messages are returned.
    def test_count_equal_to_maximum(self):
        service_rules = {
            "NAMENODE": {"min_instances": 2, "max_instances": 2},
            "ZKFC": {"min_instances": 2, "max_instances": 2},
            "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
            "DATANODE": {"min_instances": 1, "max_instances": None},
            "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
        }

        service_counter = {
            "NAMENODE": 2,
            "ZKFC": 2,
            "JOURNALNODE": 3,
            "DATANODE": 1,
            "SECONDARY_NAMENODE": 0
        }

        validator = TopologyValidator(AdvancedConfiguration())
        messages = validator.check_pattern(service_rules, service_counter)
        assert len(messages) == 0

    #  Verify that when a service count is odd and the 'odd_only' flag is set, no error messages are returned.
    def test_odd_count_with_odd_only_flag(self):
        service_rules = {
            "NAMENODE": {"min_instances": 2, "max_instances": 2},
            "ZKFC": {"min_instances": 2, "max_instances": 2},
            "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
            "DATANODE": {"min_instances": 1, "max_instances": None},
            "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
        }

        service_counter = {
            "NAMENODE": 2,
            "ZKFC": 2,
            "JOURNALNODE": 3,
            "DATANODE": 1,
            "SECONDARY_NAMENODE": 0
        }

        validator = TopologyValidator(AdvancedConfiguration())
        messages = validator.check_pattern(service_rules, service_counter)
        assert len(messages) == 0



# Generated by CodiumAI

from ci_tools.python.install_utils.conf_refactor import TopologyValidator

import pytest

class TestValidate:

    #  Validate a topology with all components within valid ranges
    def test_valid_topology(self):
        conf = AdvancedConfiguration()
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0

    #  Validate a topology with minimum number of components
    def test_min_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"namenode": 1})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0

    #  Validate a topology with maximum number of components
    def test_max_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"namenode": 10})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0

    #  Validate a topology with odd number of Zookeeper servers
    def test_odd_zookeeper_servers(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"zookeeper": 3})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) == 0

    #  Validate a topology with even number of Zookeeper servers
    def test_even_zookeeper_servers(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"zookeeper": 4})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0

    #  Validate a topology with missing required components
    def test_missing_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"namenode": 1})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0

    #  Validate a topology with unknown components
    def test_unknown_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"unknown_component": 1})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0

    #  Validate a topology with negative number of components
    def test_negative_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"namenode": -1})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0

    #  Validate a topology with non-integer number of components
    def test_non_integer_components(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"namenode": 1.5})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0

    #  Validate a topology with non-existent pattern
    def test_non_existent_pattern(self):
        conf = AdvancedConfiguration()
        conf.set("host_groups", {"non_existent_pattern": 1})
        validator = TopologyValidator(conf)
        validator.validate()
        assert len(validator.err_messages) > 0
