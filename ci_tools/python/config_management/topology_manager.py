from enum import Enum
from python.config_management.service_map import *


# from python.common.basic_logger import get_logger
# logger = get_logger()

class TopologyManager:
    def __init__(self, host_fetcher, components):
        self.host_fetcher = host_fetcher
        self.host_groups = {}
        self.group_services = {}
        self.topology = {}
        self.components = components

    class Policy(Enum):
        THREE_NODE = 1
        MULTI_NODE = 2

    def determine_policy(self, hosts):
        if len(hosts) == 3:
            return self.Policy.THREE_NODE
        else:
            return self.Policy.MULTI_NODE

    def generate_topology(self):
        hosts = self.host_fetcher()
        self._configure_hosts(hosts)
        self.topology = {
            'host_groups': self.host_groups,
            'group_services': self.group_services
        }
        self.topology_filter()
        return self.topology

    def topology_filter(self):
        if len(self.components) == 0:
            return
        all_service_components = []
        for component_name in self.components:
            service_info = ServiceMap.get_service_info_by_component_name(component_name)
            service_components = service_info.get("server")
            all_service_components.extend(service_components)

        for group, services in self.topology['group_services'].items():
            self.topology['group_services'][group] = [service for service in services if
                                                      service in all_service_components]

    def _configure_hosts(self, hosts):
        num_hosts = len(hosts)

        if num_hosts == 3:
            group_assignments = [(f'group{i}', [i]) for i in range(num_hosts)]
        elif num_hosts >= 4:
            group_assignments = [
                ('group0', [0, 1]),
                ('group1', [2]),
                ('group2', [3])
            ]
            if num_hosts > 4:  # 为第五个及之后的主机分配到 group3
                group_assignments.append(('group3', list(range(4, num_hosts))))

        self._assign_hosts_to_groups(group_assignments, hosts)

    def _assign_hosts_to_groups(self, group_assignments, hosts):
        policy = self.determine_policy(hosts)
        for group_name, host_indices in group_assignments:
            self.host_groups[group_name] = [hosts[i] for i in host_indices]
            self.group_services[group_name] = self._get_services(int(group_name[-1]), policy)

    def _get_services(self, group_number, policy):
        # {
        #     "celeborn": {
        #         "server": ["CELEBORN_MASTER", "CELEBORN_WORKER"],
        #             "clients": []
        #         },
        #     "kyuubi": {
        #         "server": ["KYUUBI_SERVER"],
        #         "clients": []
        #     },
        #     "knox": {
        #         "server": ["KNOX_GATEWAY"],
        #         "clients": []
        #     },
        #     "alluxio": {
        #         "server": ["ALLUXIO_MASTER", "ALLUXIO_WORKER"],
        #         "clients": []
        #     }
        # }

        services_a = {
            0: ['NAMENODE', 'ZKFC', 'JOURNALNODE', 'RESOURCEMANAGER', 'ZOOKEEPER_SERVER', 'HBASE_MASTER', 'NODEMANAGER',
                'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC',
                'RANGER_USERSYNC', 'AMBARI_SERVER', 'KNOX_GATEWAY'],
            1: ['NAMENODE', 'ZKFC', 'JOURNALNODE', 'RESOURCEMANAGER', 'ZOOKEEPER_SERVER', 'HBASE_MASTER', 'DATANODE',
                'NODEMANAGER', 'APP_TIMELINE_SERVER', 'RANGER_ADMIN', 'METRICS_GRAFANA', 'SPARK_JOBHISTORYSERVER',
                'KAFKA_BROKER', 'CELEBORN_MASTER', 'ALLUXIO_MASTER'],
            2: ['ZOOKEEPER_SERVER', 'JOURNALNODE', 'DATANODE', 'NODEMANAGER', 'TIMELINE_READER', 'YARN_REGISTRY_DNS',
                'METRICS_COLLECTOR', 'HBASE_REGIONSERVER', 'HIVE_SERVER', 'WEBHCAT_SERVER',
                'INFRA_SOLR', 'KYUUBI_SERVER', 'CELEBORN_WORKER', 'ALLUXIO_WORKER']
        }
        services_b = {
            0: ['NAMENODE', 'RESOURCEMANAGER', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'NODEMANAGER', 'JOURNALNODE',
                'DATANODE', 'HIVE_SERVER', 'KYUUBI_SERVER', 'ALLUXIO_MASTER', 'CELEBORN_MASTER'],
            1: ['APP_TIMELINE_SERVER', 'RANGER_ADMIN', 'METRICS_GRAFANA', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER',
                'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER', 'HIVE_METASTORE',
                'SPARK_THRIFTSERVER', 'HISTORYSERVER', 'RANGER_USERSYNC', 'ALLUXIO_MASTER', 'CELEBORN_MASTER'],
            2: ['AMBARI_SERVER', 'TIMELINE_READER', 'YARN_REGISTRY_DNS', 'METRICS_COLLECTOR', 'HBASE_REGIONSERVER',
                'DATANODE', 'NODEMANAGER', 'WEBHCAT_SERVER', 'KAFKA_BROKER', 'FLINK_HISTORYSERVER',
                'RANGER_TAGSYNC', 'CELEBORN_WORKER', 'ALLUXIO_WORKER', "KNOX_GATEWAY"],
            3: ['NODEMANAGER', 'DATANODE']
        }

        services = services_a if policy == self.Policy.THREE_NODE else services_b

        return services.get(group_number, [])


if __name__ == '__main__':
    topology = TopologyManager(lambda: ["server1", "server2", "server3", "server4", "server5"],
                               ["hbase", "hdfs", "yarn", "hive", "zookeeper", "kafka", "spark", "flink", "ranger",
                                "infra_solr", "ambari", "ambari_metrics", "kerberos"])
    print(topology.generate_topology())
    topology.topology_filter()
