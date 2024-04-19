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
                                 "desc": "HDFS high availability deployment mode must satisfy the following: the number of NAMENODE components is 2; ZKFC is 2, and each ZKFC must be deployed on the same machine as a NAMENODE; JOURNALNODE must be 3 or more and the number must be odd; and HA mode cannot select SECONDARY_NAMENODE."},
                    "ZKFC": {"min_instances": 2, "max_instances": 2},
                    "JOURNALNODE": {"min_instances": 3, "max_instances": None, "odd_only": True},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "SECONDARY_NAMENODE": {"min_instances": 0, "max_instances": 0}
                },
                {
                    "NAMENODE": {"min_instances": 1, "max_instances": 1,
                                 "desc": "HDFS standard deployment mode requires deploying 1 NAMENODE and one SECONDARY_NAMENODE. ZKFC and JOURNALNODE cannot be selected in this mode."},
                    "SECONDARY_NAMENODE": {"min_instances": 1, "max_instances": 1},
                    "DATANODE": {"min_instances": 1, "max_instances": None},
                    "ZKFC": {"min_instances": 0, "max_instances": 0},
                    "JOURNALNODE": {"min_instances": 0, "max_instances": 0}
                }],
            "hive": {
                "HIVE_METASTORE": {"min_instances": 1, "max_instances": 1,
                                   "desc": "When deploying the Hive component, only one HIVE_METASTORE can be deployed, the number of HIVE_SERVER deployments must be one or more, and only one WEBHCAT_SERVER can be deployed."},
                "HIVE_SERVER": {"min_instances": 1, "max_instances": None},
                "WEBHCAT_SERVER": {"min_instances": 1, "max_instances": 1},
            },
            "yarn": {
                "RESOURCEMANAGER": {"min_instances": 1, "max_instances": 2,
                                    "desc": "When deploying YARN, the number of RESOURCEMANAGERS must be at least 1 and no more than 2. If 2 RESOURCEMANAGERS are chosen, high availability mode is enabled. The number of NODEMANAGERS must be one or more, and only one HISTORYSERVER can be deployed."},
                "APP_TIMELINE_SERVER": {"min_instances": 1, "max_instances": 1},
                "YARN_REGISTRY_DNS": {"min_instances": 1, "max_instances": 1},
                "TIMELINE_READER": {"min_instances": 1, "max_instances": 1},
                "NODEMANAGER": {"min_instances": 1, "max_instances": None},
                "HISTORYSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "kafka": {
                "KAFKA_BROKER": {"min_instances": 1, "max_instances": None,
                                 "desc": "When deploying Kafka, the number of KAFKA_BROKER deployments must be one or more."},
            },
            "ambari": {
                "AMBARI_SERVER": {"min_instances": 1, "max_instances": 1,
                                  "desc": "AMBARI_SERVER, a fundamental component for managing big data clusters, must be deployed and can only be deployed on one machine."},
            },
            "hbase": {
                "HBASE_MASTER": {"min_instances": 1, "max_instances": 2,
                                 "desc": "When deploying HBase, the number of HBASE_MASTER should be 1-2. With 2, it enters the high availability mode for HBase Master. The number of HBASE_REGIONSERVER deployments must be one or more."},
                "HBASE_REGIONSERVER": {"min_instances": 1, "max_instances": None},
            },
            "ranger": {
                "RANGER_ADMIN": {"min_instances": 1, "max_instances": 2,
                                 "desc": "When deploying Ranger, the number of RANGER_ADMIN should be 1-2. With 2, it enables the high availability mode for RANGER_ADMIN. Both RANGER_TAGSYNC and RANGER_USERSYNC can only have one deployment each."},
                "RANGER_TAGSYNC": {"min_instances": 1, "max_instances": 1},
                "RANGER_USERSYNC": {"min_instances": 1, "max_instances": 1},
            },
            "spark": {
                "SPARK_JOBHISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                           "desc": "When deploying Spark, both SPARK_JOBHISTORYSERVER and SPARK_THRIFTSERVER must be deployed and can only have one deployment each."},
                "SPARK_THRIFTSERVER": {"min_instances": 1, "max_instances": 1},
            },
            "zookeeper": {
                "ZOOKEEPER_SERVER": {"min_instances": 3, "max_instances": None, "odd_only": True,
                                     "desc": "When deploying ZooKeeper, a minimum of three instances must be deployed, and the number of deployments must be an odd number."},
            },
            "flink": {
                "FLINK_HISTORYSERVER": {"min_instances": 1, "max_instances": 1,
                                        "desc": "When deploying Flink, FLINK_HISTORYSERVER must be deployed and can only have one deployment."},
            },
            "infra_solr": {
                "INFRA_SOLR": {"min_instances": 1, "max_instances": None,
                               "desc": "When deploying Infra Solr, at least one INFRA_SOLR must be deployed."},
            },
            "solr": {
                "SOLR_SERVER": {"min_instances": 1, "max_instances": None,
                                "desc": "When deploying Solr, at least one SOLR_SERVER must be deployed."},
            },
            "ambari_metrics": {
                "METRICS_COLLECTOR": {"min_instances": 1, "max_instances": 1,
                                      "desc": "When deploying Ambari Metrics, METRICS_COLLECTOR must be deployed and can only have one deployment."},
                "METRICS_GRAFANA": {"min_instances": 1, "max_instances": 1,
                                    "desc": "When deploying Ambari Metrics, METRICS_GRAFANA must be deployed and can only have one deployment."}
            },
            "knox": {
                "KNOX_GATEWAY": {"min_instances": 1, "max_instances": None,
                                           "desc": "When deploying Knox, Knox must be deployed and can only have one deployment."},
            },
            "kyuubi": {
                "KYUUBI_SERVER": {"min_instances": 1, "max_instances": None,
                                           "desc": "When deploying Kyuubi, at least one KYUUBI_SERVER must be deployed."},
            },
            "celeborn": {
                "CELEBORN_MASTER": {"min_instances": 1, "max_instances": 3,
                                           "desc": "When deploying Celeborn, CELEBORN_MASTER can be deployed with either one or three instances for high availability, and at least one CELEBORN_WORKER must be deployed."},
                "CELEBORN_WORKER": {"min_instances": 1, "max_instances": None},
            },
            "trino": {
                "TRINO_COORDINATOR": {"min_instances": 1, "max_instances": 1,
                                           "desc": "When deploying Trino, only one TRINO_COORDINATOR can be deployed, and at least one TRINO_WORKER must be deployed."},
                "TRINO_WORKER": {"min_instances": 1, "max_instances": None},
            },
            "router": {
                "HADOOP_ROUTER": {"min_instances": 1, "max_instances": None,
                                      "desc": "When deploying Hadoop Router, at least one HADOOP_ROUTER must be deployed."}
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
                    "The number of instances for {} is {} which is less than the minimum required instances of {}.".format(rule_service_name, service_count, rule['min_instances']))

            if rule["max_instances"] is not None and service_count > rule["max_instances"]:
                messages.append(
                    "The number of instances for {} is {} which exceeds the maximum allowed instances of {}.".format(rule_service_name, service_count, rule['max_instances']))

            if rule.get("odd_only") and service_count % 2 == 0:
                messages.append("The number of instances for {} is {}, which is not an odd number.".format(rule_service_name, service_count))

        if tmp_desc and len(tmp_desc) > 0 and len(messages) > 0:
            messages.append(tmp_desc)
        return messages

    # This function is used to check the topology of components.
    # First, the function retrieves the services to be installed and their counters. Then, it defines a pattern rules dictionary containing various services and their component requirements, such as minimum and maximum instance numbers.
    # Next, the function iterates through all services to be installed. If a service is in the pattern rules, it checks the rules. If the number of service components does not meet the rule requirements, error messages are added to a list.
    # Finally, if there are messages in the list, indicating that some services do not meet the rules, the function returns False along with the error messages; otherwise, it returns True and None.
    #
    # Example of `host_group_services`: {'group1': ['RANGER_ADMIN', 'NAMENODE', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'RESOURCEMANAGER', 'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # Example of `host_groups`: {'group1': ['gs-server2'], 'group0': ['gs-server0'], 'group2': ['gs-server3']}
    # These are correct examples, but there will be many other incorrect examples input by users, such as deploying ZKFC and Secondary_Namenode together in a group: {'group1': ['SECONDARY_NAMENODE', 'NAMENODE', 'ZKFC'], 'group0': ['AMBARI_SERVER', 'NAMENODE', 'ZKFC', 'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC', 'RANGER_USERSYNC', 'ZOOKEEPER_SERVER', 'JOURNALNODE'], 'group2': ['HBASE_REGIONSERVER', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'HIVE_SERVER', 'JOURNALNODE', 'SOLR_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER']}
    # Another example of incorrect input is not deploying JOURNALNODE in group1 array during high availability mode of Namenode.

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
                    # Trigger rule check as soon as a component is discovered.
                    if service_name in rule_services:
                        # Every component in the rule set must meet the requirements, so all rules must be iterated through.
                        messages = self.check_pattern(service_rules, service_counter)
                        self.err_messages.extend(messages)
                        checked_services.append(pattern_key)
                elif isinstance(service_rules, list):
                    # Check the two deployment modes of Namenode, can only satisfy one of the modes. The conditions defined by the two patterns are mutually exclusive; it's impossible to meet both patterns simultaneously.
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
