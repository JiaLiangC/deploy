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

def run_shell_cmd(cmd_list):
    process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    print("run_shell_cmd: {}".format(cmd_list))

    if process.returncode == 0:
        print("Execution successful")
    else:
        print("Execution failed. Error:", error)

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


def run_playbook():
    command = "ansible-playbook 'ansible-scripts/playbooks/install_cluster.yml' --inventory='inventory/hosts'"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    # 获取命令输出的结果
    succeed = int(output.decode().strip())


def main():
    #todo fot test ansible_install()  # include yaml package,so later code can use it

    from conf_utils import ConfUtils
    from blueprint_utils import BlueprintUtils

    cf_util = ConfUtils()
    conf = cf_util.get_conf()

    hosts_info = cf_util.get_hosts_info()
    ambari_server_host = cf_util.get_ambari_server_host()

    b = BlueprintUtils(conf)
    b.build()
    b.generate_ansible_hosts(conf, hosts_info, ambari_server_host)

    # run_playbook()


if __name__ == '__main__':
    main()

