# -*- coding: UTF-8 -*-
# !/usr/bin/python2
import os
import subprocess
import time
import urllib2
import sys

reload(sys)
sys.setdefaultencoding('utf-8')


class InvalidConfigurationException(Exception):
    pass


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_DIR = SCRIPT_DIR
ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-scripts')

PKG_BASE_DIR = os.path.join(SCRIPT_DIR, "pkgs")
# 安装jdk 作为nexus 的依赖

def ansible_install():
    rpm_dir = os.path.join(PKG_BASE_DIR, "ansible")
    # 获取目录下所有 RPM 文件的列表
    rpm_files = [file for file in os.listdir(rpm_dir) if file.endswith(".rpm")]

    # 构建安装命令
    install_command = ["yum", "install", "-y"]

    # 添加所有 RPM 文件到安装命令中
    install_command.extend(os.path.join(rpm_dir, file) for file in rpm_files)

    test_install_cmd = "rpm -qa|grep ansible | wc -l"
    # 执行命令并获取输出
    test_output = subprocess.check_output(test_install_cmd, shell=True)
    # 将输出转换为整数
    component_installed = int(test_output.strip())
    if component_installed > 0:
        return

    # 执行安装命令
    if os.path.exists(rpm_dir):
        print("安装 ansible {}".format(install_command))
        run_shell_cmd(install_command)


# 示例用法
# host_groups = {
#     'group0': ['host1', 'host2', 'host3'],
#     'group1': ['host4', 'host5'],
#     'group2': ['host6', 'host7', 'host8'],
# }
# 这里只分组为 hadoop-cluster 代表集群所有机器
# 这里只分组为 ambari-server 代表ambari_server
# ===========================
# [all:vars]
# ansible_user=sys_admin
# ansible_ssh_pass=sys_admin
# ansible_ssh_port=22

def generate_ansible_hosts(conf, hosts_info, ambari_server_host):
    print("动态生成ansible hosts 文件")
    parsed_hosts, user = hosts_info
    host_groups = conf["host_groups"]

    hosts_dict = {}
    for host_info in parsed_hosts:
        ip = host_info[0]
        hostname = host_info[1]
        passwd = host_info[2]
        hosts_dict[hostname] = (ip, passwd)

    node_groups = {}
    node_groups.setdefault("ambari-server", []).extend([ambari_server_host])
    for group_name, hosts in host_groups.items():
        node_groups.setdefault("hadoop-cluster", []).extend(hosts)

    hosts_content = ""
    for group, hosts in node_groups.items():
        hosts_content += "[{}]\n".format(group)
        for host_name in hosts:
            info = hosts_dict.get(host_name)
            if not info:
                raise InvalidConfigurationException
            ip = info[0]
            passwd = info[1]
            # arm-1 ansible_host=10.202.62.78 ansible_ssh_pass=
            hosts_content += "{} ansible_host={} ansible_ssh_pass={}\n".format(host_name, ip, passwd)
        hosts_content += "\n"

    ansible_user = user

    hosts_content += "[all:vars]\n"
    hosts_content += "ansible_user={}\n".format(ansible_user)
    hosts_path = os.path.join(ANSIBLE_PRJ_DIR, "inventory", "hosts")
    with open(hosts_path, "w") as f:
        f.write(hosts_content)


def run_playbook():
    command = "ansible-playbook 'ansible-scripts/playbooks/install_cluster.yml' --inventory='inventory/hosts'"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    # 获取命令输出的结果
    succeed = int(output.decode().strip())


def main():
    ansible_install()  # include yaml package,so later code can use it

    from conf_utils import ConfUtils
    from blueprint_utils import BlueprintUtils

    conf_util = ConfUtils()
    ambari_server_host = conf_util.get_ambari_server_host()
    conf = conf_util.get_conf()

    hosts_info = conf_util.get_hosts_info()

    generate_ansible_hosts(conf, hosts_info, ambari_server_host)
    b = BlueprintUtils(conf)
    b.build()

    # run_playbook()


if __name__ == '__main__':
    main()

