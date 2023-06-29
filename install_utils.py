import os
import subprocess
import time
import re
# import requests
from blueprint_utils import BlueprintUtils


class InvalidConfigurationException(Exception):
    pass


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONF_DIR = SCRIPT_DIR
ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-udh')

PKG_BASE_DIR = os.path.join(SCRIPT_DIR, "pkgs")
OS_RELEASE_NAME = "centos7"

jdk_package_name = "jdk-8u322.zip"
nexus_package_name = "nexus-3.49.0.tar.gz"
pigz_package_name = "pigz-2.3.4-1.el7.x86_64.rpm"


# 安装nexus 到指定目录下
def nexus_install(data_dir):
    command = "ps -ef | grep org.sonatype.nexus.karaf.NexusMain | grep -v grep | wc -l"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    # 获取命令输出的结果
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
    subprocess.run(["yum", "install", "-y", pigz_rpm])

    # 3. 显示信息消息
    print("即将开始安装nexus，该过程预计等待时间小于5分钟")

    # 4. 解压 Nexus
    nexus_dir = os.path.join(data_dir, "nexus")
    if os.path.isdir(nexus_dir):
        print(f"{nexus_dir} 目录已经存在，请先删除", "error")
        exit(1)

    nexus_pkg = os.path.join(PKG_BASE_DIR, "nexus", nexus_package_name)
    if os.path.exists(nexus_pkg):
        print(f"解压 {nexus_pkg} 软件包到 {data_dir} 目录")
        subprocess.run(["tar", "-I", "pigz", "-xf", nexus_package_name, "-C", data_dir])
    else:
        print(f"请将 {nexus_package_name} 放置到 nexus 目录下", "error")
        exit(1)

    jdk_install()
    setup_nexus_service(data_dir)

    print("nexus 启动中...")
    subprocess.run(["systemctl", "start", "nexus3"])

    # 7. 设置环境变量
    MAX_WAIT_TIME = 300
    MAX_END_TIME = time.time() + MAX_WAIT_TIME

    NEXUS_SERVICE_RESPONSE_CODE = "000"
    NEXUS_SERVICE_OK = 1

    # 通过 /service/rest/v1/status/writable 接口判断 nexus 服务是否可用
    while time.time() <= MAX_END_TIME:
        response = requests.get("http://localhost:8081/service/rest/v1/status/writable")
        NEXUS_SERVICE_RESPONSE_CODE = str(response.status_code)
        if NEXUS_SERVICE_RESPONSE_CODE == "200":
            print("nexus 服务已经可用")
            NEXUS_SERVICE_OK = 0
            break
        else:
            print("nexus 正在启动中，服务还不可用，等待3秒后重试...", "warn")
            time.sleep(3)

    if NEXUS_SERVICE_OK == 0:
        print("nexus 安装启动完成")
    else:
        print("nexus 安装启动未完成，请先排除问题再重新安装", "error")


# 安装jdk 作为nexus 的依赖
def jdk_install():
    jdk_pkg = os.path.join(PKG_BASE_DIR, "jdk", jdk_package_name)
    if os.path.exists(jdk_pkg):
        print(f"解压 {jdk_package_name}")
        subprocess.run(["tar", "-I", "pigz", "-xf", jdk_package_name, "-C", "/usr/local/"])

    # 设置 JAVA_HOME 和 PATH
    env_lines = [
        'export JAVA_HOME=/usr/local/jdk-8u322',
        'export PATH=.:$JAVA_HOME/bin:$PATH'
    ]

    with open('/etc/profile', 'a') as profile_file:
        profile_file.write('\n'.join(env_lines))


def ansible_install():
    ansible_pkg_dir = os.path.join(PKG_BASE_DIR, "ansible")
    rpm_cmds = ansible_pkg_dir + "/*.rpm"
    if os.path.exists(ansible_pkg_dir):
        print("安装 ansible")
        subprocess.run(["yum", "install", "-y", rpm_cmds])


def setup_nexus_service(data_dir):
    # 6. 设置 nexus3.service
    print("生成 nexus3.service")
    subprocess.run(["cp", "-rp", "nexus3.service.template", "nexus3.service"])
    subprocess.run(["sed", "-i", f"s#data_dir#{data_dir}#", "nexus3.service"])
    subprocess.run(["cp", "-rp", "nexus3.service", "/usr/lib/systemd/system"])
    subprocess.run(["systemctl", "enable", "nexus3"])


# 设置本地仓库，作为ansible 安装其他依赖时的仓库
def setup_local_repo(server_url):
    # cp -f zeta-nexus/ansible-nexus.repo.template /etc/yum.repos.d/ansible-nexus.repo
    # sed -i "s#YUM_SERVER#${YUM_SERVER}#g" /etc/yum.repos.d/ansible-nexus.repo
    # sed -i "s#OS_RELEASE_NAME#${OS_RELEASE_NAME}#g" /etc/yum.repos.d/ansible-nexus.repo
    import shutil
    import fileinput
    # 复制文件
    shutil.copyfile("zeta-nexus/ansible-nexus.repo.template", "/etc/yum.repos.d/ansible-nexus.repo")
    # 替换文件中的内容
    with fileinput.FileInput("/etc/yum.repos.d/ansible-nexus.repo", inplace=True) as file:
        for line in file:
            line = line.replace("YUM_SERVER", server_url)
            line = line.replace("OS_RELEASE_NAME", OS_RELEASE_NAME)
            print(line, end="")


# 加载配置文件
def load_conf():
    import yaml
    file_path = os.path.join(CONF_DIR, 'conf.yml')
    with open(file_path, 'r') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    return data


# 根据用户配置，设置nexus
# 1.当用户配置了external_nexus_server_ip 时，整个安装都讲使用整个nexus 作为仓库，然后设置为本地repo
# 2.默认配置，即安装nexus 到ambari 所在的机器，所有的后续安装都将使用该仓库
def setup_nexus(conf):
    group_services = conf["group_services"]
    host_groups = conf["host_groups"]
    ambari_server_group = ""

    install_nexus = False
    external_nexus_server_ip = conf["nexus_options"]["external_nexus_server_ip"]
    nexus_port = conf["nexus_options"]["port"]
    if len(external_nexus_server_ip.strip()) == 0:
        install_nexus = True

    if install_nexus:
        for group_name, services in group_services.items():
            if "AMBARI_SERVER" in services:
                ambari_server_group = group_name
                break
        nexus_data_dir = conf["nexus_options"]["data_dir"]
        nexus_host = host_groups[ambari_server_group][0]
        nexus_install(nexus_data_dir)
    else:
        nexus_host = conf["nexus_options"]["external_nexus_server_ip"]

    nexus_url = f"http://{nexus_host}:{nexus_port}"
    setup_local_repo(nexus_url)


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
def generate_ansible_hosts(conf):
    parsed_hosts, user = parse_hosts_config()
    host_groups = parse_cluster_install_config(conf)
    hosts_dict = {}
    for host_info in parsed_hosts:
        ip = host_info[0]
        hostname = host_info[1]
        passwd = host_info[2]
        hosts_dict[hostname] = (ip, passwd)

    group_services = conf["group_services"]
    ambari_server_group = ""
    node_groups = {}
    for group_name, services in group_services.items():
        if "AMBARI_SERVER" in services:
            ambari_server_group = group_name
            break

    for group_name, hosts in host_groups.items():
        node_groups.setdefault("hadoop-cluster", []).extend(hosts)
        if group_name == ambari_server_group:
            node_groups.setdefault("ambari-server", []).extend(hosts)

    hosts_content = ""
    for group, hosts in node_groups.items():
        hosts_content += f"[{group}]\n"
        for host_name in hosts:
            info = hosts_dict.get(host_name)
            if not info:
                raise InvalidConfigurationException
            ip = info[0]
            passwd = info[1]
            # arm-1 ansible_host=10.202.62.78 ansible_ssh_pass=
            hosts_content += f"{host_name} ansible_host={ip} ansible_ssh_pass={passwd}\n"
        hosts_content += "\n"

    ansible_user = user
    # ansible_ssh_pass = conf["ansible_options"]["ansible_ssh_pass"]
    # ansible_ssh_port = conf["ansible_options"]["ansible_ssh_port"]

    hosts_content += "[all:vars]\n"
    hosts_content += f"ansible_user={ansible_user}\n"
    # hosts_content += f"ansible_ssh_pass={ansible_ssh_pass}\n"
    # hosts_content += f"ansible_ssh_port={ansible_ssh_port}\n"

    hosts_path = os.path.join(ANSIBLE_PRJ_DIR, "inventory", "hosts")
    with open(hosts_path, "w") as file:
        file.write(hosts_content)


def parse_cluster_install_config(conf):
    host_groups_conf = conf["host_groups"]

    # 可以解析 node[1-3] node[1-3]xx [1-3]node  或者 node1 的主机组配置
    # node[1 - 3].example.com，则函数会将其扩展为 `node1.example.com`、`node2.example.com` 和 `node3.example.com`# 三个主机名。
    host_groups = {}
    for group_name, group_hosts in host_groups_conf.items():
        if group_name not in host_groups:
            host_groups[group_name] = []

        if isinstance(group_hosts, list):
            for host_name in group_hosts:
                host_groups[group_name].append(host_name)
        else:
            match = re.search(r'\[(\d+)-(\d+)]', group_hosts)
            if match:
                prefix = group_hosts[:match.start()]
                start = int(match.group(1))
                end = int(match.group(2))
                suffix = group_hosts[match.end():]
                for i in range(start, end + 1):
                    host = '{}{}{}'.format(prefix, i, suffix)
                    host_groups[group_name].append(host)
            else:
                host_groups[group_name].append(group_hosts)

    host_groups = host_groups
    return host_groups


def parse_hosts_config():
    import yaml
    file_path = os.path.join(CONF_DIR, 'hosts_info.yml')
    with open(file_path, 'r') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    configurations = data["hosts"]
    user = data["user"]
    parsed_configs = []

    for config in configurations:
        if len(config.split()) != 3:
            raise InvalidConfigurationException

        if '[' in config:
            hostname_part, ip_part, password = config.split()
            hosts = []
            ips = []
            if '[' in hostname_part:
                match = re.search(r'\[(\d+)-(\d+)]', hostname_part)
                if match:
                    hostname_prefix = hostname_part[:match.start()]
                    hostname_range_start = int(match.group(1))
                    hostname_range_end = int(match.group(2))
                    hostname_suffix = hostname_part[match.end():]

                    for i in range(hostname_range_start, hostname_range_end + 1):
                        host = '{}{}{}'.format(hostname_prefix, i, hostname_suffix)
                        hosts.append(host)
                else:
                    raise InvalidConfigurationException
            if '[' in ip_part:
                match = re.search(r'\[(\d+)-(\d+)]', ip_part)
                if match:
                    ip_prefix = ip_part[:match.start()]
                    ip_range_start = int(match.group(1))
                    ip_range_end = int(match.group(2))
                    ip_suffix = ip_part[match.end():]

                    for i in range(ip_range_start, ip_range_end + 1):
                        ip = '{}{}{}'.format(ip_prefix, i, ip_suffix)
                        ips.append(ip)
            else:
                raise InvalidConfigurationException

            if len(hosts) != len(ips):
                raise InvalidConfigurationException("Configuration is invalid")
            for index, ip in enumerate(ips):
                parsed_configs.append((hosts[index], ip, password))
        else:

            parsed_configs.append(tuple(config.split()))

    return parsed_configs, user


def run_playbook():
    command = "ansible-playbook 'ansible-udh/playbooks/install_cluster.yml' --inventory='inventory/hosts'"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    # 获取命令输出的结果
    succeed = int(output.decode().strip())


def main():
    ansible_install()  # include yaml package,so later code can use it
    conf = load_conf()
    generate_ansible_hosts(conf)
    setup_nexus(conf)
    b = BlueprintUtils()
    b.build()
    # run_playbook()

if __name__ == '__main__':
    main()
# todo ansible 到所有节点的免密登录
# todo 多次执行幂等
