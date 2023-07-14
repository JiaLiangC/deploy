# -*- coding: UTF-8 -*-
# !/usr/bin/python2
import os
import subprocess
import time
import urllib2
import socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_BASE_DIR = os.path.join(SCRIPT_DIR, "files")

jdk_install_path = "/usr/local"
jdk_package_name = "jdk.zip"
nexus_package_name = "nexus-3.49.0.tar.gz"
pigz_package_name = "pigz-2.3.4-1.el7.x86_64.rpm"


class InstallNexusDeployPlugin:
    def run_shell_cmd(self, cmd_list):
        process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        print("run_shell_cmd: {}".format(cmd_list))

        if process.returncode == 0:
            print("Execution successful")
        else:
            print("Execution failed. Error:", error)

    def get_java_home(self):
        file_name = os.path.splitext(jdk_package_name)[0]
        java_home = os.path.join(jdk_install_path, file_name)
        return java_home

    def setup_nexus_service(self, data_dir):
        jdk_home = self.get_java_home()
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

        self.run_shell_cmd(["systemctl", "enable", "nexus3"])

    def nexus_install(self, data_dir, nexus_base_url):
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

        pigz_rpm = os.path.join(PKG_BASE_DIR, pigz_package_name)
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
            self.run_shell_cmd(["tar", "-I", "pigz", "-xf", nexus_package_name, "-C", data_dir])
        else:
            print("请将 {} 放置到 nexus 目录下", "error".format(nexus_package_name))
            exit(1)

        self.jdk_install()
        self.setup_nexus_service(data_dir)

        print("nexus 启动中...")
        self.run_shell_cmd(["systemctl", "start", "nexus3"])

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

    def jdk_install(self):
        java_home = self.get_java_home()
        jdk_pkg = os.path.join(PKG_BASE_DIR, "jdk", jdk_package_name)
        if os.path.exists(jdk_pkg):
            print("解压 {}".format(jdk_package_name))
            self.run_shell_cmd(["tar", "-I", "pigz", "-xf", jdk_package_name, "-C", "/usr/local/"])

        # 设置 JAVA_HOME 和 PATH
        env_lines = [
            'export JAVA_HOME={}'.format(java_home),
            'export PATH=.:$JAVA_HOME/bin:$PATH'
        ]

        with open('/etc/profile', 'a') as profile_file:
            profile_file.write('\n'.join(env_lines))

    def get_ip_address(self):
        try:
            # 创建一个UDP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 连接到一个公共的域名，此处使用Google的域名
            sock.connect(("8.8.8.8", 80))
            # 获取本地套接字的IP地址
            ip_address = sock.getsockname()[0]
            return ip_address
        except socket.error:
            return "Unable to retrieve IP address"

    def update_conf(self, conf):
        nexus_host = self.get_ip_address()
        self.run()
        nexus_url = "http://{}:{}".format(nexus_host, "8081")
        ambari_repo_rl = "{}/repository/yum/sdp_3.1".format(nexus_url)
        centos_base_repo_url = "{}/repository/centos/7/os/x86_64".format(nexus_url)
        repos = [
            {"name": "centos_base_repo", "url": centos_base_repo_url},
            {"name": "ambari_repo", "url": ambari_repo_rl}
        ]

        conf["repos"].extend(repos)
        return conf

    def run(self):
        self.nexus_install()
