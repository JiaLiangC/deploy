class ServiceMap:
    def __init__(self):
        self.service_map = {
            "hbase": {
                "server": ["HBASE_MASTER", "HBASE_REGIONSERVER"],
                "clients": ["HBASE_CLIENT"]
            },
            "hdfs": {
                "server": ["NAMENODE", "DATANODE", "SECONDARY_NAMENODE", "JOURNALNODE", "ZKFC"],
                "clients": ["HDFS_CLIENT", "MAPREDUCE2_CLIENT"]
            },
            "yarn": {
                "server": ["NODEMANAGER", "RESOURCEMANAGER", "HISTORYSERVER", "APP_TIMELINE_SERVER",
                           "YARN_REGISTRY_DNS",
                           "TIMELINE_READER"],
                "clients": ["YARN_CLIENT"]
            },
            "hive": {
                "server": ["HIVE_METASTORE", "WEBHCAT_SERVER", "HIVE_SERVER"],
                "clients": ["HIVE_CLIENT", "HCAT", "TEZ_CLIENT"]
            },
            "zookeeper": {
                "server": ["ZOOKEEPER_SERVER"],
                "clients": ["ZOOKEEPER_CLIENT"]
            },
            "kafka": {
                "server": ["KAFKA_BROKER", ],
                "clients": []
            },
            "spark": {
                "server": ["SPARK_JOBHISTORYSERVER", "SPARK_THRIFTSERVER"],
                "clients": ["SPARK_CLIENT"]
            },
            "flink": {
                "server": ["FLINK_HISTORYSERVER"],
                "clients": ["FLINK_CLIENT"]
            },
            "ranger": {
                "server": ["RANGER_ADMIN", "RANGER_TAGSYNC", "RANGER_USERSYNC"],
                "clients": []
            },
            "infra_solr": {
                "server": ["INFRA_SOLR"],
                "clients": ["INFRA_SOLR_CLIENT"]
            },
            # 不支持solr 了，没人使用
            # "solr": {
            #     "server": ["SOLR_SERVER"],
            #     "clients": []
            # },
            "ambari": {
                "server": ["AMBARI_SERVER"],
                "clients": []
            },
            "ambari_metrics": {
                "server": ["METRICS_COLLECTOR", "METRICS_GRAFANA"],
                "clients": ["METRICS_MONITOR"]
            },
            "kerberos": {
                "server": ["KERBEROS_CLIENT"],
                "clients": ["KERBEROS_CLIENT"]
            }
        }

    def is_service_supported(self, service_name):
        for service_key, info in self.service_map.items():
            if service_name in info["server"]:
                return True
        return False

    def get_services(self, service_name):
        if self.is_service_supported(service_name):
            return self.service_map[service_name]
        else:
            return None

    def get_services_map(self):
        return self.service_map
