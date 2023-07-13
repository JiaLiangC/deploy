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
ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-udh')

PKG_BASE_DIR = os.path.join(SCRIPT_DIR, "pkgs")
OS_RELEASE_NAME = "centos7"

jdk_install_path = "/usr/local"
jdk_package_name = "jdk.zip"
nexus_package_name = "nexus-3.49.0.tar.gz"
pigz_package_name = "pigz-2.3.4-1.el7.x86_64.rpm"


def get_java_home():
    file_name = os.path.splitext(jdk_package_name)[0]
    java_home = os.path.join(jdk_install_path, file_name)
    return java_home


def run_shell_cmd(cmd_list):
    process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    print("run_shell_cmd: {}".format(cmd_list))

    if process.returncode == 0:
        print("Execution successful")
    else:
        print("Execution failed. Error:", error)


def nexus_install(data_dir, nexus_base_url):
    command = "ps -ef | grep org.sonatype.nexus.karaf.NexusMain | grep -v grep | wc -l"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    is_nexus_installed = int(output.decode().strip())

    # 检查 Nexus 进程是否已安装
    if is_nexus_installed > 0:
        print("Nexus 进程已安装")
        return
    else:
        print("Nexus 进程未安装")

    # 1. 创建 data_dir 目录
    if not os.path.isdir(data_dir):
        os.mkdir(data_dir)

    pigz_rpm = os.path.join(PKG_BASE_DIR, "tools", pigz_package_name)
    # 2. 安装 pigz 工具以加快解压速度
    process = subprocess.Popen(["yum", "install", "-y", pigz_rpm], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode == 0:
        print("Installation successful")
    else:
        print("Installation failed. Error:", error)

    # 3. 显示信息消息
    print("即将开始安装nexus，该过程预计等待时间小于5分钟")

    # 4. 解压 Nexus
    nexus_dir = os.path.join(data_dir, "nexus")
    if os.path.isdir(nexus_dir):
        print("{} 目录已经存在，请先删除".format(nexus_dir))
        exit(1)

    nexus_pkg = os.path.join(PKG_BASE_DIR, "nexus", nexus_package_name)
    if os.path.exists(nexus_pkg):
        print("解压 {} 软件包到 {} 目录".format(nexus_pkg, data_dir))
        run_shell_cmd(["tar", "-I", "pigz", "-xf", nexus_package_name, "-C", data_dir])
    else:
        print("请将 {} 放置到 nexus 目录下", "error".format(nexus_package_name))
        exit(1)

    jdk_install()
    setup_nexus_service(data_dir)

    print("nexus 启动中...")
    run_shell_cmd(["systemctl", "start", "nexus3"])

    # 7. 设置环境变量
    max_wait_time = 300
    max_end_time = time.time() + max_wait_time
    nexus_service_ok = False

    # 通过 /service/rest/v1/status/writable 接口判断 nexus 服务是否可用
    while time.time() <= max_end_time:
        response = urllib2.urlopen("{}/service/rest/v1/status/writable".format(nexus_base_url))

        nexus_service_response_code = str(response.getcode())
        if nexus_service_response_code == "200":
            print("nexus 服务已经可用")
            nexus_service_ok = True
            break
        else:
            print("nexus 正在启动中，服务还不可用，等待3秒后重试...")
            time.sleep(3)

    if nexus_service_ok == 0:
        print("nexus 安装启动完成")
    else:
        print("nexus 安装启动未完成，请先排除问题再重新安装")


# 安装jdk 作为nexus 的依赖
def jdk_install():
    java_home = get_java_home()
    jdk_pkg = os.path.join(PKG_BASE_DIR, "jdk", jdk_package_name)
    if os.path.exists(jdk_pkg):
        print("解压 {}".format(jdk_package_name))
        run_shell_cmd(["tar", "-I", "pigz", "-xf", jdk_package_name, "-C", "/usr/local/"])

    # 设置 JAVA_HOME 和 PATH
    env_lines = [
        'export JAVA_HOME={}'.format(java_home),
        'export PATH=.:$JAVA_HOME/bin:$PATH'
    ]

    with open('/etc/profile', 'a') as profile_file:
        profile_file.write('\n'.join(env_lines))


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


def setup_nexus_service(data_dir):
    jdk_home = get_java_home()
    nexus_basename = os.path.splitext(nexus_package_name)[0]
    nexus_bin_dir = os.path.join(data_dir, "nexus", nexus_basename, "bin")

    file_content = '''\
[Unit]
Description=nexus3 - private repository
After=network.target remote-fs.target nss-lookup.target

[Service]
User=root
Type=forking
Environment=JAVA_HOME={java_home}
ExecStart={nexus_bin_path}/nexus start
ExecReload={nexus_bin_path}/nexus restart
ExecStop={nexus_bin_path}/bin/nexus stop

[Install]
WantedBy=multi-user.target
    '''.format(java_home=jdk_home, nexus_bin_path=nexus_bin_dir)

    file_path = '/usr/lib/systemd/system/nexus3.service'

    with open(file_path, 'w') as file:
        file.write(file_content)

    run_shell_cmd(["systemctl", "enable", "nexus3"])


# 设置本地仓库，作为ansible 安装其他依赖时的仓库
def setup_local_repo(centos_repo_url):
    repo = '''\
[ansible-nexus]
name=Nexus Repository for Ansible
baseurl={}
enabled=1
gpgcheck=0
    '''.format(centos_repo_url, OS_RELEASE_NAME)
    # 复制文件
    with open("/etc/yum.repos.d/ansible-nexus.repo", 'w') as file:
        file.write(repo)

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
    command = "ansible-playbook 'ansible-udh/playbooks/install_cluster.yml' --inventory='inventory/hosts'"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    # 获取命令输出的结果
    succeed = int(output.decode().strip())


def main():
    ansible_install()  # include yaml package,so later code can use it
    from conf_utils import ConfUtils
    from blueprint_utils import BlueprintUtils
    cu = ConfUtils()
    ambari_server_host = cu.get_ambari_server_host()
    nexus_base_url = cu.generate_nexus_base_url()
    conf, hosts_info = cu.run()

    generate_ansible_hosts(conf, hosts_info, ambari_server_host)
    setup_local_repo(conf["centos_repo_url"])

    b = BlueprintUtils()
    b.build()
    # run_playbook()


if __name__ == '__main__':
    main()

# todo nexus url 检测
