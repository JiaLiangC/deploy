from enum import Enum
import yaml
#from python.common.basic_logger import get_logger
#logger = get_logger()

class TopologyManager:
    def __init__(self, host_fetcher):
        self.host_fetcher = host_fetcher
        self.host_groups = {}
        self.group_services = {}

    class Policy(Enum):
        THREE_NODE = 1
        MULTI_NODE = 2

    def determine_policy(self, hosts):
        # 根据 hosts 的数量决定策略
        if len(hosts) == 3:
            return self.Policy.THREE_NODE
        else:
            return self.Policy.MULTI_NODE

    def generate_topology(self):
        hosts = self.host_fetcher()
        self._configure_hosts(hosts)

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
        # 根据分组配置分配主机和服务
        for group_name, host_indices in group_assignments:
            self.host_groups[group_name] = [hosts[i] for i in host_indices]
            self.group_services[group_name] = self._get_services(int(group_name[-1]), policy)

    def _get_services(self, group_number, policy):
        services_a = {
            0: ['NAMENODE', 'ZKFC', 'JOURNALNODE', 'RESOURCEMANAGER', 'ZOOKEEPER_SERVER', 'HBASE_MASTER', 'NODEMANAGER',
                'HIVE_METASTORE', 'SPARK_THRIFTSERVER', 'FLINK_HISTORYSERVER', 'HISTORYSERVER', 'RANGER_TAGSYNC',
                'RANGER_USERSYNC', 'AMBARI_SERVER'],
            1: ['NAMENODE', 'ZKFC', 'JOURNALNODE', 'RESOURCEMANAGER', 'ZOOKEEPER_SERVER', 'HBASE_MASTER', 'DATANODE',
                'NODEMANAGER', 'APP_TIMELINE_SERVER', 'RANGER_ADMIN', 'METRICS_GRAFANA', 'SPARK_JOBHISTORYSERVER',
                'KAFKA_BROKER'],
            2: ['ZOOKEEPER_SERVER', 'JOURNALNODE', 'DATANODE', 'NODEMANAGER', 'TIMELINE_READER', 'YARN_REGISTRY_DNS',
                'METRICS_COLLECTOR', 'HBASE_REGIONSERVER', 'HIVE_SERVER', 'WEBHCAT_SERVER', 'KAFKA_BROKER',
                'INFRA_SOLR']
        }
        services_b = {
            0: ['NAMENODE', 'RESOURCEMANAGER', 'ZKFC', 'HBASE_MASTER', 'ZOOKEEPER_SERVER', 'NODEMANAGER', 'JOURNALNODE',
                'DATANODE', 'HIVE_SERVER'],
            1: ['APP_TIMELINE_SERVER', 'RANGER_ADMIN', 'METRICS_GRAFANA', 'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER',
                'SPARK_JOBHISTORYSERVER', 'INFRA_SOLR', 'JOURNALNODE', 'KAFKA_BROKER', 'HIVE_METASTORE',
                'SPARK_THRIFTSERVER', 'HISTORYSERVER', 'RANGER_USERSYNC'],
            2: ['AMBARI_SERVER', 'TIMELINE_READER', 'YARN_REGISTRY_DNS', 'METRICS_COLLECTOR', 'HBASE_REGIONSERVER',
                'ZOOKEEPER_SERVER', 'DATANODE', 'NODEMANAGER', 'WEBHCAT_SERVER', 'KAFKA_BROKER', 'FLINK_HISTORYSERVER',
                'RANGER_TAGSYNC'],
            3: ['NODEMANAGER', 'DATANODE']
        }

        services = services_a if policy == self.Policy.THREE_NODE else services_b

        return services.get(group_number, [])

    def write_to_yaml(self, file_path):
        try:
            with open(file_path, 'r') as file:
                existing_data = file.read()
                existing_yaml = yaml.safe_load(existing_data)
        except FileNotFoundError:
            existing_data = ""
            existing_yaml = {}

        existing_yaml['host_groups'] = self.host_groups
        existing_yaml['group_services'] = self.group_services

        combined_yaml = yaml.dump(existing_yaml, default_flow_style=None,sort_keys=False)

        with open(file_path, 'w') as file:
            file.write(combined_yaml)



if __name__ == '__main__':
    topology = TopologyManager(lambda: ["server1", "server2", "server3", "server4", "server5"])
    topology.generate_topology()
    topology.write_to_yaml("/Users/jialiangcai/szl/prjs/opensource/bigdata_deploy/output/test.yaml")
