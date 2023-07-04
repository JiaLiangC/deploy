# -*- coding: UTF-8 -*-
#!/usr/bin/python2
import os
import shutil
import subprocess
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

stack_name = sys.argv[1]

stackVersion = "3_2_0"
components = [
    "ambari", stack_name, "elasticsearch", "falcon", "flink", "grafana", "hadoop", "hbase", "hive",
    "impala", "janusgraph", "kafka", "knox", "livy", "nightingale", "oozie", "phoenix", "pig", "ranger",
    "redis", "spark", "storm", "tez", "victoriametrics", "webhcat", "zookeeper", "solr"
]

bins = [
    "impala", "accumulo", "atlas-start", "atlas-stop", "beeline", "falcon", "flume-ng", "hadoop", "hbase",
    "hcat", "hdfs", "hive", "hiveserver2", "kafka", "mahout", "mapred", "oozie", "oozied.sh", "phoenix-psql",
    "phoenix-queryserver", "phoenix-sqlline", "phoenix-sqlline-thin", "pig", "python-wrap", "ranger-admin",
    "ranger-admin-start", "ranger-admin-stop", "ranger-kms", "ranger-usersync", "ranger-usersync-start",
    "ranger-usersync-stop", "slider", "sqoop", "sqoop-codegen", "sqoop-create-hive-table", "sqoop-eval",
    "sqoop-export", "sqoop-help", "sqoop-import", "sqoop-import-all-tables", "sqoop-job", "sqoop-list-databases",
    "sqoop-list-tables", "sqoop-merge", "sqoop-metastore", "sqoop-version", "storm", "storm-slider",
    "worker-lanucher", "yarn", "zookeeper-client", "zookeeper-server", "zookeeper-server-cleanup", "solr"
]
user_array = [
    "ambari", "ambari-qa", "ams", "elasticsearch", "flink", "flume", "gsadmin", "hadoop", "hbase",
    "hcat", "hdfs", "hive", "impala", "infra-solr", "janusgraph", "kafka", "livy", "mapred", "postgres",
    "ranger", "redis", "slider", "spark", "solr", "tez", "user", "yarn", "zookeeper"
]

special_paths = [
    "/usr/%s" % stack_name,
    "/usr/lib/python2.6",
    "/tmp/hadoop-hdfs",
    "/etc/ssoconf",
    "/etc/krb5",
    "/etc/default/%s" % stack_name,
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
]

packages = [
        "ambari-agent", stack_name + "-*", "ambari-infra", "ambari-server", "ambari-metrics", "nightingale",
        "grafana_agent", "victoriametrics", stack_name + "-select", "redis", "postgresql", "krb5-devel",
        "krb5-workstation", "libkadm5", "krb5-server", "postgresql*-server"
    ]

package_white_list = ["hdp"]

# 删除 dirname 下的 包含 target_file_keyword 名的 文件
def patterns_delete(dirname, target_file_keyword):
    if os.path.exists(dirname):
        for item in os.listdir(dirname):
            item_path = os.path.join(dirname, item)
            # 检查是否包含基准名称
            if target_file_keyword in item:
                # 删除包含基准名称的文件和目录
                if os.path.islink(item_path):
                    os.remove(item_path)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)


# 杀死所有大数据相关进程
def kill_user_processes(username):
    try:
        # uid = int(subprocess.check_output(["id", "-u", username]))
        subprocess.call(["killall", "-u", str(username)])
        print("All processes owned by", username, "have been killed.")
    except subprocess.CalledProcessError:
        print("User", username, "does not exist.")

# 删除无规则的路径
def remove_special_path(files_arr):
    for path in files_arr:
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
        patterns_delete(dirname, basename)

def batch_delete(files_arr, target_dir):
    for file in files_arr:
        patterns_delete(target_dir,file)


def uninstall_packages(packages):
    for package in packages:
        if package not in package_white_list:
            print("Removing", package + "...")
            subprocess.call(["yum", "remove", "-y", package + "*"])

def clean():
    print("循环关闭所有大数据用及其相关进程")
    p1 = subprocess.Popen(["pgrep", "-f", "ambari|hadoop|n9e|grafana|impala"], stdout=subprocess.PIPE)
    output, _ = p1.communicate()

    if output:
        p2 = subprocess.Popen(["xargs", "kill", "-9"], stdin=subprocess.PIPE)
        p2.communicate(input=output)

    for user in user_array:
        kill_user_processes(user)

    uninstall_packages(packages)
    uninstall_packages(components)

    # 调用函数删除不规则的路径
    print("卸载一些自定义的特殊的安装包")
    remove_special_path(special_paths)

    batch_delete(components, "/opt")
    batch_delete(components, "/var/lib")
    batch_delete(components, "/usr/lib")
    batch_delete(components, "/var/log")
    batch_delete(components, "/etc")
    batch_delete(components, "/var/run")
    batch_delete(components, "/hadoop/")
    batch_delete(components, "/data1/")
    batch_delete(components, "/etc/security/limits.d/")

    print("循环删除bin下的相关组件的文件")
    batch_delete(bins, "/usr/bin")
    # print("清除/etc/hosts文件中原来的主机信息")
    # subprocess.call(["sed", "-i", "3,$d", "/etc/hosts"])

def main():
    clean()


if __name__ == '__main__':
    main()
