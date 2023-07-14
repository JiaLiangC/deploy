# -*- coding: UTF-8 -*-
import unittest
from conf_utils import ConfUtils
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

class TestTopologyChecker(unittest.TestCase):
    def setUp(self):
        conf_utils = ConfUtils()
        self.conf_utils = conf_utils

    # 测试正确的情况
    def test_check_component_topology_positive(self):
        host_groups = {'group1': ['server2'], 'group0': ['server0'], 'group2': ['server3']}
        host_group_services = {
            'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE',
                       'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE',
                       'KAFKA_BROKER'],
            'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER',
                       'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER',
                       'JOURNALNODE'],
            'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER',
                       'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
        self.conf_utils.check_component_topology(host_groups, host_group_services)
        self.assertEqual(len(self.conf_utils.get_err_messages()), 0)


    # 测试只部署部分组件的错误
    # 该测试case namenode 部署错误
    # spark 缺少组件
    # ranger 缺少组件
    # yarn 缺少组件
    def test_check_component_topology_negative(self):
        host_groups = {'group1': ['server2'], 'group0': ['server0'], 'group2': ['server3']}
        host_group_services = {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC','HBASE_MASTER','ZOOKEEPER_SERVER'],
                               'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER',
                                          'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC',
                                          'ZOOKEEPER_SERVER', 'JOURNALNODE'],
                               'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER',
                                          'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER',
                                          'KAFKA_BROKER']}
        self.conf_utils.check_component_topology(host_groups, host_group_services)
        self.assertGreater(len(self.conf_utils.get_err_messages()), 0,"配置错误")
        print("\n".join(self.conf_utils.get_err_messages()))


    def test_check_component_topology_negative1(self):
        host_groups = {'group1': ['server2']}
        host_group_services = {'group1': ['AMBARI_SERVER']}
        result, message = self.conf_utils.check_component_topology(host_groups, host_group_services)
        self.assertTrue(result)
        self.assertIsNone(message)


if __name__ == '__main__':
    unittest.main()
