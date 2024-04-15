# -*- coding: UTF-8 -*-
# !/usr/bin/python3
import os
import shutil
import subprocess
import sys

DEBIAN_OS="debian"

class ClusterClear:
    stack_name = "bigtop"

    def __init__(self, stack_name, data_dirs_str,system_type):
        self.system_type = system_type
        self.stack_name = stack_name
        self.stackVersion = "3_2_0"
        self.data_dirs = self.get_data_dirs(data_dirs_str)

    def get_info(self):
        infos = {
            "package_white_list": ["hdp"],
            "whitelist_paths": [
                "/bin", "/etc", "/home", "/root", "/usr", "/sbin", "/lib", "/var",
                "/tmp", "/proc", "/dev", "/sys", "/run", "/boot", "/srv",
                "/lib64", "/media", "/mnt", "/opt", "/usr/local", "/usr/sbin",
                "/usr/bin", "/usr/lib", "/usr/include", "/usr/share"
            ],
            "components": [
                "ambari", self.stack_name, "flink", "grafana", "hadoop", "hbase", "hive",
                "kafka", "knox", "livy", "phoenix", "pig", "ranger", "ranger-kms",
                "spark", "tez", "webhcat", "zookeeper", "solr", "hdfs", "yarn",
                "ambari-infra-solr", "knox", "celeborn", "alluxio", "kyuubi", "trino"
            ],
            "bins": [
                "beeline", "flume-ng", "hadoop", "hbase",
                "hcat", "hdfs", "hive", "hiveserver2", "kafka", "mapred",
                "phoenix-psql",
                "phoenix-queryserver", "phoenix-sqlline", "phoenix-sqlline-thin", "python-wrap", "ranger-admin",
                "ranger-admin-start", "ranger-admin-stop", "ranger-kms", "ranger-usersync", "ranger-usersync-start",
                "ranger-usersync-stop", "slider",
                "yarn", "zookeeper-client", "zookeeper-server", "zookeeper-server-cleanup", "solr"
            ],

            "user_array": [
                "yarn-ats" "ambari", "ambari-qa", "ams", "flink", "flume", "hadoop", "hbase",
                "hcat", "hdfs", "hive", "infra-solr", "kafka", "livy", "mapred", "postgres", "kms",
                "ranger", "slider", "spark", "solr", "tez", "yarn", "zookeeper", "knox", "kyuubi", "celeborn", "alluxio", "trino"
            ],

            "special_paths": [
                "/usr/%s" % self.stack_name,
                "/tmp/hadoop-hdfs",
                "/tmp/cluster_cache",
                "/var/kafka-logs",
                "/etc/default/%s" % self.stack_name,
                "/var/log/kadmin",
                "/var/log/krb5kdc",
                "/var/lib/pgsql",
                "/var/lib/mysql",
                "/var/kerberos",
                "/usr/pgsql",
                "/hadoop",
                "/pg_data",
                "/kafka",
                "/etc/init.d/ambari",
                "/etc/init.d/postgresql",
                "/etc/rc.d/init.d/postgresql",
                "/etc/security/keytabs"
            ],
            "packages": [
                "ambari-agent", self.stack_name + "-*", "ambari-infra", "ambari-server", "ambari-metrics",
                "nightingale", "knox", "kyuubi", "alluxio", "celeborn",
                "grafana_agent", "victoriametrics", self.stack_name + "-select", "postgresql", "postgresql*-server",
                "mysql-community-server", "mariadb-server"
            ]
        }

        return infos

    def patterns_delete(self, dirname, target_file_keyword):
        if os.path.exists(dirname):
            for item in os.listdir(dirname):
                item_path = os.path.join(dirname, item)
                if target_file_keyword in item:
                    print("remove file or dir {}".format(item_path))
                    self.safe_delete(item_path)

    def kill_user_processes(self, username):
        try:
            # uid = int(subprocess.check_output(["id", "-u", username]))
            subprocess.call(["killall", "-u", str(username)])
            print("All processes owned by", username, "have been killed.")
        except subprocess.CalledProcessError:
            print("User", username, "does not exist.")

    def remove_special_path(self, files_arr):
        for path in files_arr:
            dirname = os.path.dirname(path)
            basename = os.path.basename(path)
            print("Removing special path {}".format(path))
            self.patterns_delete(dirname, basename)

    def batch_delete(self, files_arr, target_dir):
        print("batch_delete: Removing  target_dir {}".format(target_dir))
        for file_path in files_arr:
            self.patterns_delete(target_dir, file_path)

    def uninstall_packages(self, packages):
        package_white_list = self.get_info()["package_white_list"]
        for package in packages:
            if package not in package_white_list:
                print("Removing", package + "...")
                if self.system_type == DEBIAN_OS:
                    command = ['apt-get', 'purge', '-y', package + "*"]
                    env = {'DEBIAN_FRONTEND': 'noninteractive'}
                    result = subprocess.call(command, env=dict(os.environ, **env))
                else:
                    subprocess.call(["yum", "remove", "-y", package + "*"])



    def clean(self):
        info = self.get_info()
        user_array = info["user_array"]
        packages = info["packages"]
        components = info["components"]
        special_paths = info["special_paths"]
        bins = info["bins"]

        print("close bigdata process")
        p1 = subprocess.Popen(["pgrep", "-f", "ambari|hadoop|grafana"], stdout=subprocess.PIPE)
        output, _ = p1.communicate()

        if output:
            p2 = subprocess.Popen(["xargs", "kill", "-9"], stdin=subprocess.PIPE)
            p2.communicate(input=output)

        for user in user_array:
            self.kill_user_processes(user)

        self.uninstall_packages(packages)
        self.uninstall_packages(components)

        print("uninstall custom package {}".format(special_paths))
        self.remove_special_path(special_paths)

        print("batch_delete batch delete dir {}".format(components))
        self.batch_delete(components, "/etc/security/limits.d")
        self.batch_delete(components, "/opt")
        self.batch_delete(components, "/var/lib")
        self.batch_delete(components, "/usr/lib")
        self.batch_delete(components, "/var/log")
        self.batch_delete(components, "/etc")
        self.batch_delete(components, "/var/run")
        self.batch_delete(components, "/hadoop/")

        print("batch_delete dir or file in bin")
        self.batch_delete(bins, "/usr/bin")

        print("delete data dir {}".format(self.data_dirs[0]))
        for data_dir in self.data_dirs:
            print("delete data dir {}".format(data_dir))
            if os.path.exists(data_dir):
                self.batch_delete(components, data_dir)

    def get_data_dirs(self, data_dirs_str):
        data_dirs_list = data_dirs_str.split(",")
        if data_dirs_list and len(data_dirs_list) > 0:
            return data_dirs_list
        else:
            return []

    def is_path_important(self, path):
        white_list = self.get_info()["whitelist_paths"]
        normalized_path = os.path.normpath(path)

        is_important = False

        for white_dir in white_list:
            exists = os.path.exists(white_dir)
            if not exists:
                continue

            else:
                if os.path.exists(normalized_path):
                    is_important_dir = os.path.samefile(normalized_path, white_dir)
                    if is_important_dir:
                        return True

                if normalized_path == white_dir:
                    return True
                else:
                    if os.path.islink(path):
                        return False

        return is_important

    def safe_delete(self, path):
        if not self.is_path_important(path):

            if os.path.isfile(path):
                print("Deleting file:", path)
                os.remove(path)
            elif os.path.isdir(path):
                print("Deleting dir:", path)
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.islink(path):
                print("Deleting link :", path)
                os.remove(path)
        else:
            print("Cannot delete: {} because this path is protected.".format(path))


def main():
    stack_name = sys.argv[1]
    data_dirs = sys.argv[2]
    system_type = sys.argv[3]
    c = ClusterClear(stack_name, data_dirs, system_type)
    c.clean()


if __name__ == '__main__':
    main()
