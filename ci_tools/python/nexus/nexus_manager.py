# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.nexus.nexus_client import NexusClient
from python.nexus.nexus_repo_sync import NexusSynchronizer
from python.install_utils.install_utils import *
from python.utils.os_utils import *
from python.utils.filesystem_util import *
from python.executor.command_executor import *
import os
import shutil
logger = get_logger()
class NexusManager:
    def __init__(self, ci_conf, os_info):
        self.ci_conf = ci_conf
        self.os_type = os_info[0]
        self.os_version = os_info[1]
        self.os_arch = os_info[2]
        self.synchronizer = NexusSynchronizer(os_info, self.ci_conf["nexus"]["os_repo_data_dir"])
        self.nexus_client = NexusClient(self.ci_conf["nexus"]["host"], self.ci_conf["nexus"]["user_name"],
                                        self.ci_conf["nexus"]["user_pwd"])
        self.nexus_installer = NexusInstaller(self.ci_conf["nexus"]["local_tar"],
                                              self.ci_conf["nexus"]["install_dir"], self.ci_conf["nexus"]["user_pwd"])
        self.path_manager = PathManager(ci_conf)
        self.executor = CommandExecutor

    def install_and_configure_nexus(self):
        logger.info("Starting Nexus installation")
        jdk_installer = JDKInstaller(self.ci_conf["nexus"]["jdk_local_tar"], self.ci_conf["nexus"]["jdk_install_dir"])
        jdk_installer.install()
        self.nexus_installer.install()

    def upload_bigdata_components(self, components):
        logger.info("Uploading big data components to Nexus")
        for comp in components:
            pkg_dir = os.path.join(self.path_manager.compiled_pkg_out_dir, comp)
            logger.info(f"uploading {pkg_dir} {comp}")
            self.nexus_client.repo_create(UDH_NEXUS_REPO_NAME, remove_old=False)
            self.nexus_client.batch_upload_bigdata_pkgs(pkg_dir, comp)
        logger.info(f'start upload bigdata rpms to nexus')

    def sync_os_repositories(self):
        logger.info("Synchronizing OS repositories")
        self.synchronizer.sync_repository()

    def upload_os_packages(self):
        pkgs_dirs = self.synchronizer.get_local_pkgs_dirs()
        logger.info(f'start upload {self.os_type + self.os_version + self.os_arch} os pkgs to local nexus repository')
        # The reponame of the os package equals the os type, for example, redhat.
        self.nexus_client.repo_create(self.os_type, remove_old=True)
        self.nexus_client.batch_upload_os_pkgs(pkgs_dirs, (self.os_type, self.os_version, self.os_arch))

    def package_nexus(self):
        logger.info(f'start package nexus ')
        pigz_installer = PigzInstaller(PIGZ_SOURC_CODE_PATH, PRJ_BIN_DIR)
        pigz_installer.install()
        udh_release_output_dir = self.ci_conf["udh_nexus_release_output_dir"]

        self.install_and_configure_nexus()
        # create repo if not exist and upload bigdata pkgs to nexus
        # create repo and sync and upload os pkgs to nexus
        self.sync_os_repositories()
        self.upload_os_packages()
        kill_nexus_process()
        kill_user_processes("nexus")

        install_dir = self.ci_conf["nexus"]["install_dir"]
        nexus_dir = self.nexus_installer.comp_dir
        pigz_path = self.path_manager.pigz_path
        nexus_tar = os.path.join(install_dir, "nexus3.tar.gz")

        os.chdir(install_dir)
        command = f"tar cf - {os.path.basename(nexus_dir)} | {pigz_path} -k -5 -p 16 > {nexus_tar}"
        self.executor.execute_command(command, shell=True)

        logger.info("package_nexus finished")
        name = f"UDH_NEXUS_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}"
        nexus_release_dir = os.path.join(udh_release_output_dir, name)
        FilesystemUtil.create_dir(nexus_release_dir, empty_if_exists=True)
        release_nexus_tar = os.path.join(nexus_release_dir, "nexus3.tar.gz")
        shutil.move(nexus_tar, release_nexus_tar)
        logger.info(f"move compressed nexus tar from {nexus_tar} to {release_nexus_tar}")

        local_jdk = self.ci_conf["nexus"]["jdk_local_tar"]
        dest_jdk = os.path.join(nexus_release_dir, os.path.basename(local_jdk))
        shutil.copy(local_jdk, dest_jdk)
        logger.info(f"move compressed nexus tar from {local_jdk} to {dest_jdk}")
        nexus_release_tar = os.path.join(udh_release_output_dir, f"{name}.tar.gz")
        os.chdir(udh_release_output_dir)
        logger.info(f"compressing {nexus_release_tar}")
        command = f"tar cf - {os.path.basename(nexus_release_dir)} | {pigz_path} -k -5 -p 16 > {nexus_release_tar}"
        exit_code, output, error = self.executor.execute_command(command, shell=True)

        if exit_code == 0:
            shutil.rmtree(nexus_release_dir)
        else:
            logger.error(f"package rpm failed, check the log {error}")
