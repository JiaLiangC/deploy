from python.config_management.configurations.advanced_configuration import *

from .validator import *


class TopologyValidator(Validator):
    def __init__(self, conf: AdvancedConfiguration):
        super().__init__()
        self.host_groups = conf.get("host_groups")
        self.host_group_services = conf.get("group_services")
        self.pattern_rules = self._default_pattern_rules()

    def _default_pattern_rules(self):
        return {
            "namenode": [
                {
                    "NAMENODE": {"min_instances": 2, "max_instances": 2,
                                 "desc": "hdfs 高可用部署模式必须满足 NAMENODE 组件数目为2; ZKFC 为2 且每个ZKFC 必须和 NAMENODE 部署在一起同一个机器; JOURNALNODE 至少大于等于3，且数目为奇数; 并且HA 模式不能选择 SECONDARY_NAMENODE"},
                    "ZKFC": {"min_instances": 2, "max_instances": 2},
                    "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
                },
                {
                    "NAMENODE": {"min_instances": 1, "max_instances": 1,
                                 "desc": "hdfs 普通部署模式需要部署1个 NAMENODE 和一个 SECONDARY_NAMENODE。ZKFC 和 JOURNALNODE 在该模式下不可选择"},
                    "SECONDARY_NAMENODE": {"min_instances": 1, "max_instances": 1},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "ZKFC": {"min_instances": 0, "max_instances": 0},
                    "JOURNALNODE": {"min_instances": 0, "max_instances": 0}
                }],
            "hive": {
                "HIVE_METASTORE": {"min_instances": 1, "max_instances": 1,
                                   "desc": "选择部署hive 组件时，HIVE_METASTORE只能部署一个，HIVE_SERVER 部署数量必须大于等于1，WEBHCAT_SERVER部署数量只能为1个"},
                "HIVE_SERVER": {"min_instances": 1, "max_instances": None},
                "WEBHCAT_SERVER": {"min_instances": 1, "max_instances": 1},
            },
            "yarn": {
                "RESOURCEMANAGER": {"min_instances": 1, "max_instances": 2,
                                    "desc": "选择部署yarn 时，RESOURCEMANAGER数量最少为1，最大为2。当选择为2时，RESOURCEMANAGER 会开启高可用模式。NODEMANAGER数量大于等于1，HISTORYSERVER 只能部署1台。"},
                "APP_TIMELINE_SERVER": {"min_instances": 1, "max_instances": 1},
                "YARN_REGISTRY_DNS": {"min_instances": 1, "max_instances": 1},
                "TIMELINE_READER": {"min_instances": 1, "max_instances": 1},
                "NODEMANAGER": {"min_instances": 1, "max_instances": None},
                "HISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "kafka": {
                "KAFKA_BROKER": {"min_instances": 1, "max_instances": None,
                                 "desc": "选择部署kafka 时，KAFKA_BROKER 部署数量大于等于1"},
            },
            "ambari": {
                "AMBARI_SERVER": {"min_instances": 1, "max_instances": 1,
                                  "desc": "AMBARI_SERVER 为必须选择部署的用来管理大数据集群的基础组件，只能部署一台"},
            },
            "hbase": {
                "HBASE_MASTER": {"min_instances": 1, "max_instances": 2,
                                 "desc": "选择部署hbase 时，HBASE_MASTER 数量为1-2，2台时，即为hbase master 的高可用模式。HBASE_REGIONSERVER 部署必须大于等于1台"},
                "HBASE_REGIONSERVER": {"min_instances": 1, "max_instances": None},
            },
            "ranger": {
                "RANGER_ADMIN": {"min_instances": 1, "max_instances": 2,
                                 "desc": "选择部署ranger 时，RANGER_ADMIN 数量为1-2，2台时，RANGER_ADMIN 的高可用模式，RANGER_TAGSYNC和RANGER_USERSYNC只能部署一台 "},
                "RANGER_TAGSYNC": {"min_instances": 1, "max_instances": 1},
                "RANGER_USERSYNC": {"min_instances": 1, "max_instances": 1},
            },
            "spark": {
                "SPARK_JOBHISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                           "desc": "选择部署spark时，SPARK_JOBHISTORYSERVER和SPARK_THRIFTSERVER 必须且只能各部署一台"},
                "SPARK_THRIFTSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "zookeeper": {
                "ZOOKEEPER_SERVER": {"min_instances": 3, "max_instances": None, "odd_only": True,
                                     "desc": "选择部署zookeeper时，最少部署3台，且部署数量必须为奇数"},
            },
            "flink": {
                "FLINK_HISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                        "desc": "选择部署flink时,FLINK_HISTORYSERVER 必须且只能各部署一台"},
            },
            "infra_solr": {
                "INFRA_SOLR": {"min_instances": 1, "max_instances": None,
                               "desc": "选择部署infra_solr时,INFRA_SOLR最少部署一台"},
            },
            "solr": {
                "SOLR_SERVER": {"min_instances": 1, "max_instances": None,
                                "desc": "选择部署solr时,SOLR_SERVER 最少部署一台"},
            },
            "ambari_metrics": {
                "METRICS_COLLECTOR": {"min_instances": 1, "max_instances": 1,
                                      "desc": "选择部署ambari_metrics时,METRICS_COLLECTOR 必须且只能各部署一台"},
                "METRICS_GRAFANA": {"min_instances": 1, "max_instances": 1,
                                    "desc": "选择部署ambari_metrics时,METRICS_GRAFANA 必须且只能各部署一台"}
            }
        }

    def check_pattern(self, service_rules, service_counter):
        messages = []
        tmp_desc = None
        for rule_service_name, rule in service_rules.items():

            service_count = service_counter.get(rule_service_name, 0)
            if rule.get("desc", None):
                tmp_desc = rule.get("desc")

            if service_count < rule["min_instances"]:
                messages.append(
                    "{} 的实例数 {} 小于最小实例数 {}".format(rule_service_name, service_count, rule['min_instances']))

            if rule["max_instances"] is not None and service_count > rule["max_instances"]:
                messages.append(
                    "{} 的实例数 {} 大于最大实例数 {}".format(rule_service_name, service_count, rule['max_instances']))

            if rule.get("odd_only") and service_count % 2 == 0:
                messages.append("{} 的实例数 {} 不是奇数".format(rule_service_name, service_count))

        if tmp_desc and len(tmp_desc) > 0 and len(messages) > 0:
            messages.append(tmp_desc)
        return messages

    # 这个函数是用来检查组件拓扑的。
    # 函数首先获取需要安装的服务和服务计数器。然后，定义一个模式规则字典，其中包含了各种服务及其对应的组件要求，如最小实例数、最大实例数等。
    # 接下来，函数遍历需要安装的所有服务，如果服务在模式规则中，就进行规则检查。如果服务的组件数量不满足规则要求，就将错误信息添加到消息列表中。
    # 最后，如果消息列表中有内容，说明有不满足规则的服务，函数返回False和错误信息；否则，返回True和None。

    # host_group_services example {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # host_groups example {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']}
    # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如同时部署了ZKFC 和 secondary 到一个 group 中  {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # 这两个是正确的，但是会有很多其他的用户输入的错误的例子，比如namenode 高可用模式下没有在group1 数组中部署放置JOURNALNODE
    def validate(self):
        services_need_install, service_counter = self.get_service_distribution()
        checked_services = []
        messages = self.check_pattern(self.pattern_rules["ambari"], service_counter)
        self.err_messages.extend(messages)

        for service_name in services_need_install:
            for pattern_key, service_rules in self.pattern_rules.items():
                if pattern_key in checked_services:
                    continue

                if isinstance(service_rules, dict):
                    rule_services = service_rules.keys()
                    # 只要发现一个组件就触发规则检测
                    if service_name in rule_services:
                        # 规则集中的每个组件都要满足要求，因此必须迭代所有的rule
                        messages = self.check_pattern(service_rules, service_counter)
                        self.err_messages.extend(messages)
                        checked_services.append(pattern_key)
                elif isinstance(service_rules, list):
                    # 检测 namanode 的两种部署模式, 只能满足其中一种模式, 两个pattern 定义的时候条件都是互斥的，不可能出现同时满足两个pattern的情况。
                    #
                    pattern_res = []
                    tmp_err = []
                    for service_rules_item in service_rules:
                        if service_name in service_rules_item.keys():
                            messages = self.check_pattern(service_rules_item, service_counter)
                            if len(messages) <= 0:  # one pattern 忙
                                pattern_res.append(True)
                            else:
                                tmp_err.extend(messages)

                    if len(tmp_err) > 0 and True not in pattern_res:
                        self.err_messages.extend(tmp_err)
                        checked_services.append(pattern_key)
        return self

    def get_service_distribution(self):
        service_counter = {}
        services = []
        group_hosts = {}
        for group_name, hosts in self.host_groups.items():
            group_hosts[group_name] = hosts

        for group_name, host_components in self.host_group_services.items():
            services.extend(host_components)
            for service_name in host_components:
                hosts_count = len(group_hosts[group_name])
                service_counter[service_name] = service_counter.setdefault(service_name, 0) + hosts_count
        unique_services = list(set(services))
        return unique_services, service_counter

    def _count_services(self, host_group_services):
        service_counter = {}
        for services in host_group_services.values():
            for service in services:
                service_counter[service] = service_counter.get(service, 0) + 1
        return service_counter
