# -*- coding: UTF-8 -*-
# !/usr/bin/python2
import os
import shutil
import subprocess
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

class ClusterClear:
    stack_name = "bigtop"

    def __init__(self, stack_name, data_dirs_str):
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
                "ambari", self.stack_name, "elasticsearch", "falcon", "flink", "grafana", "hadoop", "hbase", "hive",
                "impala", "janusgraph", "kafka", "knox", "livy", "nightingale", "oozie", "phoenix", "pig", "ranger",
                "redis", "spark", "storm", "tez", "victoriametrics", "webhcat", "zookeeper", "solr"
            ],
            "bins": [
                "impala", "accumulo", "atlas-start", "atlas-stop", "beeline", "falcon", "flume-ng", "hadoop", "hbase",
                "hcat", "hdfs", "hive", "hiveserver2", "kafka", "mahout", "mapred", "oozie", "oozied.sh",
                "phoenix-psql",
                "phoenix-queryserver", "phoenix-sqlline", "phoenix-sqlline-thin", "pig", "python-wrap", "ranger-admin",
                "ranger-admin-start", "ranger-admin-stop", "ranger-kms", "ranger-usersync", "ranger-usersync-start",
                "ranger-usersync-stop", "slider", "sqoop", "sqoop-codegen", "sqoop-create-hive-table", "sqoop-eval",
                "sqoop-export", "sqoop-help", "sqoop-import", "sqoop-import-all-tables", "sqoop-job",
                "sqoop-list-databases",
                "sqoop-list-tables", "sqoop-merge", "sqoop-metastore", "sqoop-version", "storm", "storm-slider",
                "worker-lanucher", "yarn", "zookeeper-client", "zookeeper-server", "zookeeper-server-cleanup", "solr"
            ],

            "user_array": [
                "ambari", "ambari-qa", "ams", "elasticsearch", "flink", "flume", "gsadmin", "hadoop", "hbase",
                "hcat", "hdfs", "hive", "impala", "infra-solr", "janusgraph", "kafka", "livy", "mapred", "postgres",
                "ranger", "redis", "slider", "spark", "solr", "tez", "user", "yarn", "zookeeper"
            ],

            "special_paths": [
                "/usr/%s" % self.stack_name,
                "/usr/lib/python2.6",
                "/tmp/hadoop-hdfs",
                "/etc/ssoconf",
                "/etc/krb5",
                "/etc/default/%s" % self.stack_name,
                "/var/log/kadmin",
                "/var/log/krb5kdc",
                "/var/lib/pgsql",
                "/var/kerberos",
                "/usr/pgsql",
                "/hadoop",
                "/impalad",
                "/pg_data",
                "/kafka",
                "/etc/init.d/impala",
                "/etc/init.d/ambari",
                "/etc/init.d/postgresql",
                "/etc/rc.d/init.d/postgresql",
                "/etc/security/keytabs"
            ],
            "packages": [
                "ambari-agent", self.stack_name + "-*", "ambari-infra", "ambari-server", "ambari-metrics", "nightingale",
                "grafana_agent", "victoriametrics", self.stack_name + "-select", "redis", "postgresql", "krb5-devel",
                "krb5-workstation", "libkadm5", "krb5-server", "postgresql*-server"
            ]
        }

        return infos

    # 删除 dirname 下的 包含 target_file_keyword 名的 文件
    def patterns_delete(self, dirname, target_file_keyword):
        if os.path.exists(dirname):
            for item in os.listdir(dirname):
                item_path = os.path.join(dirname, item)
                # 检查是否包含基准名称
                if target_file_keyword in item:
                    # 删除包含基准名称的文件和目录
                    self.safe_delete(item_path)

    # 杀死所有大数据相关进程
    def kill_user_processes(self, username):
        try:
            # uid = int(subprocess.check_output(["id", "-u", username]))
            subprocess.call(["killall", "-u", str(username)])
            print("All processes owned by", username, "have been killed.")
        except subprocess.CalledProcessError:
            print("User", username, "does not exist.")

    # 删除无规则的路径
    def remove_special_path(self, files_arr):
        for path in files_arr:
            dirname = os.path.dirname(path)
            basename = os.path.basename(path)
            self.patterns_delete(dirname, basename)

    def batch_delete(self, files_arr, target_dir):
        for file_path in files_arr:
            self.patterns_delete(target_dir, file_path)

    def uninstall_packages(self, packages):
        package_white_list = self.get_info()["package_white_list"]
        for package in packages:
            if package not in package_white_list:
                print("Removing", package + "...")
                subprocess.call(["yum", "remove", "-y", package + "*"])

    def clean(self):
        info = self.get_info()
        user_array = info["user_array"]
        packages = info["packages"]
        components = info["components"]
        special_paths = info["special_paths"]
        bins = info["bins"]

        print("循环关闭所有大数据用及其相关进程")
        p1 = subprocess.Popen(["pgrep", "-f", "ambari|hadoop|n9e|grafana|impala"], stdout=subprocess.PIPE)
        output, _ = p1.communicate()

        if output:
            p2 = subprocess.Popen(["xargs", "kill", "-9"], stdin=subprocess.PIPE)
            p2.communicate(input=output)

        for user in user_array:
            self.kill_user_processes(user)

        self.uninstall_packages(packages)
        self.uninstall_packages(components)

        # 调用函数删除不规则的路径
        print("卸载一些自定义的特殊的安装包")
        self.remove_special_path(special_paths)

        self.batch_delete(components, "/opt")
        self.batch_delete(components, "/var/lib")
        self.batch_delete(components, "/usr/lib")
        self.batch_delete(components, "/var/log")
        self.batch_delete(components, "/etc")
        self.batch_delete(components, "/var/run")
        self.batch_delete(components, "/hadoop/")
        self.batch_delete(components, "/etc/security/limits.d/")
        print("循环删除bin下的相关组件的文件")
        self.batch_delete(bins, "/usr/bin")

        for data_dir in self.data_dirs:
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
            print("Deleting:", path)
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.islink(path):
                os.remove(path)
        else:
            print("Cannot delete: {} because this path is protected.".format(path))


def main():
    stack_name = sys.argv[1]
    data_dirs = sys.argv[2]
    c = ClusterClear(stack_name, data_dirs)
    c.clean()


if __name__ == '__main__':
    main()
