# -*- coding: UTF-8 -*-
import unittest
import re
import sys

from  conf_utils import ConfUtils

sys.path.append('../')
class InvalidConfigurationException(Exception):
    pass

# Usage
# configs = [
#     "10.1.1.12 hostname password",
#     "10.1.1.13 hostname2 password2",
#     "hostname10[1-2] 10.1.1.1[1-2] password",
#     "hostname[1-2]2 10.1.1.1[1-2] password",
#     "[1-2]hostname3 10.1[1-2].1.1 password"
# ]
#
# parsed = parse_config(configs)
# for config in parsed:
#     print(config)  # 将解析的配置打印出来
#

class TestConfigParser(unittest.TestCase):

    def test_parse_config(self):
        cu = ConfUtils()
        # 测试常规case
        configs_normal = {
            "host_groups": {
                'group1': ['gs-server2'],
                'group0': ['gs-server0'],
                'group2': ['gs-server3']
            },
            "group_services":{
                'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC'],
                'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC'],
                'group2': ['HBASE_REGIONSERVER']
            }
        }

        expected_output = {
           "host_groups": {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']},
            "group_services": {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC'],
                               'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC'],
                               'group2': ['HBASE_REGIONSERVER']}
        }

        self.assertItemsEqual(cu.parse_component_topology_conf(configs_normal)[0], expected_output["host_groups"])
        self.assertItemsEqual(cu.parse_component_topology_conf(configs_normal)[1], expected_output["group_services"])


        configs_regex = {
            "host_groups":{
                'group0': ['gs-server0'],
                'group1': ['gs-server1'],
                'group2': ['gs-server[2-4]']
            },
            "group_services":{
                'group0': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'],
                'group1': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'],
                'group2': ['HBASE_REGIONSERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'SOLR_SERVER', 'KAFKA_BROKER']
            }
        }

        expected_output_regex = {
            "host_groups": {'group0': ['gs-server0'], 'group1': ['gs-server1'], 'group2': ['gs-server2','gs-server3','gs-server4']},
            "group_services": {'group0': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'],
                               'group1': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'],
                               'group2': ['HBASE_REGIONSERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'SOLR_SERVER','KAFKA_BROKER']}
        }

        self.assertItemsEqual(cu.parse_component_topology_conf(configs_regex)[0], expected_output_regex["host_groups"])
        self.assertItemsEqual(cu.parse_component_topology_conf(configs_regex)[1], expected_output_regex["group_services"])




        # 测试范围格式不正确的异常情况
        configs_1 = {
            "host_groups": {
                'group0': ['gs[2-4]-server']
            },
            "group_services": {
                'group0': ['AMBARI_SERVER']
            }
        }
        expected_output1 = {
            "host_groups": {'group0': ['gs2-server','gs3-server','gs4-server']},
            "group_services": {'group0': ['AMBARI_SERVER']}
        }

        self.assertItemsEqual(cu.parse_component_topology_conf(configs_1)[0], expected_output1["host_groups"])
        self.assertItemsEqual(cu.parse_component_topology_conf(configs_1)[1], expected_output1["group_services"])

        # with self.assertRaises(Exception):
        #     parse_config(["hostname[1;2] 10.1.1.1 password"])
        #         todo add more invalid confs


if __name__ == '__main__':
    unittest.main()
