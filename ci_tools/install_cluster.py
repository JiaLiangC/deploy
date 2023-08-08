# -*- coding: UTF-8 -*-
# !/usr/bin/python3
import subprocess
import signal
import os
from python import *
def run_shell_cmd(cmd_list):
    process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    logger.info("run_shell_cmd: {}".format(cmd_list))

    if process.returncode == 0:
        logger.info("Execution successful")
    else:
        logger.info("Execution failed. Error:", error)


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
        logger.info("安装 ansible {}".format(install_command))
        run_shell_cmd(install_command)


def run_playbook():
    playbook_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/install_cluster.yml')
    inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
    command = "ansible-playbook '{}' --inventory='{}'".format(playbook_path, inventory_path)

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,shell=True,cwd=CONF_DIR)
    
    def signal_handler(signum, frame):
        os.kill(process.pid, signal.SIGTERM)
        raise KeyboardInterrupt("Program was interrupted")
    
    signal.signal(signal.SIGINT, signal_handler)

    while process.poll() is None:
        output_line = process.stdout.readline()
        if output_line:
            logger.info(output_line.strip())

    # Process any remaining output after the process completes
    for output_line in process.stdout.readlines():
        logger.info(output_line.strip())

    # Wait for the process to finish and get the return code
    return_code = process.returncode
    logger.info("playbook return_code is %s",return_code)
    

def main():

    #create ouptut dir for some test data
    if not os.path.exists(OUTPUT_DIR):
        os.mkdir(OUTPUT_DIR)

    #ansible_install()

    from python.install_utils.conf_utils import ConfUtils
    from python.install_utils.blueprint_utils import BlueprintUtils

    cf_util = ConfUtils()
    conf = cf_util.get_conf()

    hosts_info = cf_util.get_hosts_info()
    ambari_server_host = cf_util.get_ambari_server_host()

    b = BlueprintUtils(conf)
    b.build()
    b.generate_ansible_hosts(conf, hosts_info, ambari_server_host)

    #run_playbook()


if __name__ == '__main__':
    main()
