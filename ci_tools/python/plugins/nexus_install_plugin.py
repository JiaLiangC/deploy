# -*- coding: UTF-8 -*-
# !/usr/bin/python3
import os
import subprocess
import time
import socket
from python.common.basic_logger import get_logger
from python.common.constants import *
from python.install_utils.install_utils import *
from python.utils.os_utils import *

logger = get_logger()


class InstallNexusDeployPlugin:

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
        nexus_url = "http://{}:{}".format(nexus_host, "8081")
        self.run(conf)
        os_type = get_os_type()
        os_version = get_os_version()
        os_architecture = get_os_arch()

        ambari_repo_rl = f"{nexus_url}/repository/{UDH_NEXUS_REPO_NAME}/{UDH_NEXUS_REPO_PATH}"
        centos_base_repo_url = f"{nexus_url}/repository/{os_type}/{os_version}/os/{os_architecture}/Packages"
        repos = [
            {"name": "centos_base_repo", "url": centos_base_repo_url},
            {"name": "ambari_repo", "url": ambari_repo_rl}
        ]

        if len(conf["repos"]) > 0:
            self.combine_repos(conf["repos"], ambari_repo_rl, centos_base_repo_url)
        else:
            conf["repos"].extend(repos)
        logger.debug("nexus_install_plugin update_conf {}".format(repos))
        return conf

    def run(self, conf):
        data_dir = conf["data_dirs"][0]
        logger.debug("data dir is {}".format(data_dir))
        logger.info(f"{RELEASE_NEXUS_TAR_FILE} {RELEASE_JDK_TAR_FILE}")
        nexus_installer = NexusInstaller(RELEASE_NEXUS_TAR_FILE,
                                         conf["nexus"]["install_dir"], conf["nexus"]["user_pwd"])

        jdk_installer = JDKInstaller(RELEASE_JDK_TAR_FILE, conf["nexus"]["jdk_install_dir"])

        jdk_installer.install()
        nexus_installer.install()

    def combine_repos(self, old_repos, ambari_repo, centos_base_repo):
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
        if not centos_base_repo_updated:
            old_repos.append({"name": "centos_base_repo", "url": centos_base_repo})
        return old_repos
