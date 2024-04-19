# -*- coding: UTF-8 -*-
# !/usr/bin/python3
import os
import subprocess
import time
import urllib.request, urllib.error, urllib.parse
import http.client
import socket
from python.common.basic_logger import logger
from python.common.constants import *

jdk_install_path = "/usr/local"
jdk_package_name = "jdk.zip"
nexus_package_name = "nexus.tar.gz"
pigz_package_name = "pigz-2.3.4-1.el7.x86_64.rpm"


class InstallNexusDeployPlugin:
    def run_shell_cmd(self, cmd_list,env=None,shell=False):
        process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE,env=env,shell=shell,universal_newlines=True)
        output, error = process.communicate()

        logger.info("run shell cmd: {}".format(cmd_list))

        if process.returncode == 0:
            logger.debug("Execution successful")
        else:
            logger.debug("Execution failed. Error:", error)
        return output,error

    def get_java_home(self):
        file_name = os.path.splitext(jdk_package_name)[0]
        java_home = os.path.join(jdk_install_path, file_name)
        return java_home

    def setup_nexus_service(self, data_dir):
        logger.info("setup linux service for nexus")
        jdk_home = self.get_java_home()

        nexus_bin_dir = os.path.join(data_dir, "nexus", "nexus3", "bin")

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

        self.run_shell_cmd(["systemctl", "enable", "nexus3"],shell=True)

    def nexus_install(self, data_dir, nexus_base_url):
        logger.info("start nexus install, data dir {}".format(data_dir))
        command = "ps -ef | grep org.sonatype.nexus.karaf.NexusMain | grep -v grep | wc -l"
        output, _ = self.run_shell_cmd(command,shell=True)
        is_nexus_installed = int(output.strip())

        if is_nexus_installed > 0:
            logger.info("Nexus process has been installed.")
            return
        else:
            logger.info("Nexus process is not installed.")

        if not os.path.isdir(data_dir):
            os.mkdir(data_dir)

        logger.info("install pigz")
        output, error = self.run_shell_cmd(["rpm", "-ivh", pigz_rpm])
        logger.info(output)
        logger.info(error)


        logger.info("Installation of Nexus will begin shortly, expected waiting time is less than 5 minutes.")

        nexus_dir = os.path.join(data_dir, "nexus")
        if os.path.isdir(nexus_dir):
            logger.error("{} Directory already exists, please delete it first.".format(nexus_dir))
            exit(1)

        nexus_pkg = os.path.join(PLUGINS_FILES_DIR, nexus_package_name)

        if os.path.exists(nexus_pkg):
            logger.info("Extract the {} package to the {} directory.".format(nexus_pkg, data_dir))
            self.run_shell_cmd(["tar", "-I", "pigz", "-xf", nexus_pkg, "-C", data_dir])
        else:
            logger.error("Please place {} into the {} directory.".format(nexus_package_name,PLUGINS_FILES_DIR))
            exit(1)

        self.jdk_install()
        self.setup_nexus_service(data_dir)
        
        logger.info("nexus starting...")
        self.run_shell_cmd(["systemctl", "start", "nexus3"], env={'INSTALL4J_JAVA_HOME': '/usr/local/jdk'})

        # 300s
        max_wait_time = 300
        max_end_time = time.time() + max_wait_time
        nexus_service_ok = False

        nexus_test_url = "{}/service/rest/v1/status/writable".format(nexus_base_url)
        logger.info(nexus_test_url)
        while time.time() <= max_end_time:
            try:
                response = urllib.request.urlopen(nexus_test_url)
                nexus_service_response_code = str(response.getcode())
                logger.info(nexus_service_response_code)
                if nexus_service_response_code == "200":
                    logger.info("Nexus service is now available.")
                    nexus_service_ok = True
                    break
                else:
                    logger.info("Nexus is starting up, service is not available yet, wait for 3 seconds before retrying...")
            except urllib.error.HTTPError as e:
                logger.error('HTTPError = ' + str(e.code))
                continue
            except urllib.error.URLError as e:
                # print('URLError = ' + str(e.reason))
                continue
            except http.client.HTTPException as e:
                logger.error('HTTPException')
                continue
            except Exception:
                import traceback
                logger.error('generic exception: ' + traceback.format_exc())
                continue
            time.sleep(5)

        if nexus_service_ok:
            logger.info("Nexus installation and startup completed.")
        else:
            logger.error("Nexus installation and startup not completed, please troubleshoot the issues before reinstalling.")

    def jdk_install(self):
        logger.info("install jdk for nexus")
        java_home = self.get_java_home()
        jdk_pkg = os.path.join(PLUGINS_FILES_DIR, jdk_package_name)
        if os.path.exists(jdk_pkg):
            logger.info("decompress {}".format(jdk_package_name))
            self.run_shell_cmd(["unzip", jdk_pkg, "-d", "/usr/local/"])
        else:
            logger.error("plz place  {} into {} ".format(nexus_package_name, PLUGINS_FILES_DIR))
            exit(1)

        # set JAVA_HOME 和 PATH
        env_lines = [
            '\nexport JAVA_HOME={}'.format(java_home),
            'export PATH=.:$JAVA_HOME/bin:$PATH'
        ]

        with open('/etc/profile', 'a') as profile_file:
            profile_file.write('\n'.join(env_lines))

    def get_ip_address(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
            return ip_address
        except socket.error:
            return "Unable to retrieve IP address"

    def update_conf(self, conf):
        nexus_host = self.get_ip_address()
        nexus_url = "http://{}:{}".format(nexus_host, "8081")
        self.run(conf,nexus_url)
        
        ambari_repo_rl = "{}/repository/yum/sdp_3.1".format(nexus_url)
        centos_base_repo_url = "{}/repository/centos/7/os/x86_64".format(nexus_url)
        repos = [
            {"name": "centos_base_repo", "url": centos_base_repo_url},
            {"name": "ambari_repo", "url": ambari_repo_rl}
        ]

        if len(conf["repos"])>0:
            self.combine_repos(conf["repos"], ambari_repo_rl,centos_base_repo_url)
        else:
            conf["repos"].extend(repos)    
        logger.debug("nexus_install_plugin update_conf {}".format(repos))
        return conf

    def run(self,conf,nexus_url):
        data_dir= conf["data_dirs"][0]
        logger.debug("data dir is {}".format(data_dir))
        self.nexus_install(data_dir,nexus_url)
        
    def combine_repos(self, old_repos, ambari_repo,centos_base_repo):
        # add or update
        ambari_repo_updated = False
        centos_base_repo_updated = False
        for i in old_repos:
            if i["name"] == "ambari_repo":
                i["url"] == ambari_repo
                ambari_repo_updated = True
            if i["name"] == "centos_base_repo":
                i["url"] == centos_base_repo
                centos_base_repo_updated = True
        if not ambari_repo_updated:
            old_repos.append({"name": "ambari_repo", "url": ambari_repo})
        if not  centos_base_repo_updated:
            old_repos.append({"name": "centos_base_repo", "url": centos_base_repo})
        return old_repos
        