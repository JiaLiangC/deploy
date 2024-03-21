from python.exceptions.invalid_configuration_exception import *


class ServiceMap:

    @staticmethod
    def get_service_key_from_service(service_name):
        for service_key, service_info in ServiceMap.get_services_map().items():
            if service_name in service_info["server"]:
                return service_key
        raise InvalidConfigurationException(f"Service '{service_name}' not found in services map.")

    @staticmethod
    def is_service_supported(service_name):
        for service_key, info in ServiceMap.get_services_map().items():
            if service_name in info["server"]:
                return True
        return False

    @staticmethod
    def get_service_info(service_name):
        key = ServiceMap.get_service_key_from_service(service_name)
        if ServiceMap.is_service_supported(service_name):
            return ServiceMap.get_services_map().get(key)
        else:
            return None

    @staticmethod
    def get_service_info_by_component_name(component_name):
        return ServiceMap.get_services_map().get(component_name)

    @staticmethod
    def get_services_map():
        service_map = {
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
            "ranger_kms": {
                "server": ["RANGER_KMS_SERVER"],
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
            },
            "celeborn": {
                "server": ["CELEBORN_MASTER", "CELEBORN_WORKER"],
                "clients": []
            },
            "kyuubi": {
                "server": ["KYUUBI_SERVER"],
                "clients": []
            },
            "knox": {
                "server": ["KNOX_GATEWAY"],
                "clients": []
            },
            "alluxio": {
                "server": ["ALLUXIO_MASTER", "ALLUXIO_WORKER"],
                "clients": []
            },
            "trino": {
                "server": ["TRINO_COORDINATOR", "TRINO_WORKER"],
                "clients": ["TRINO_CLI"]
            }
        }
        return service_map
