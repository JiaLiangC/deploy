# -*- coding:utf8 -*-
# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.config_management.configuration_manager import *
from python.install_utils.install_utils import *
from python.utils.os_utils import *
from python.executor.command_executor import *
import os
import shutil

logger = get_logger()
class Deployment:
    def __init__(self, ci_config):
        self.executor = CommandExecutor
        self.ci_config = ci_config
        self.conf_manager = ConfigurationManager(BASE_CONF_NAME)

    def deploy_cluster(self):
        playbook_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/install_cluster.yml')
        inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
        log_file = os.path.join(LOGS_DIR, "ansible_playbook.log")

        conf_manager = self.conf_manager
        conf_manager.load_confs()
        conf_manager.save_ambari_configurations()
        conf_manager.setup_validators()
        conf_manager.validate_configurations()
        conf_manager.save_ansible_configurations()
        if not conf_manager.is_ambari_repo_configured():
            self.setup_repo()

        env_vars = os.environ.copy()

        command = ["python3", f"{PRJ_BIN_DIR}/ansible-playbook", playbook_path, f"--inventory={inventory_path}"]

        exit_status = self.executor.execute_command_withlog(command, log_file, workdir=PRJDIR, env_vars=env_vars)
        # 等待子进程完成
        logger.info(f"run_playbook {command} exit_status: {exit_status}")

        if exit_status == 0:
            logger.info("Cluster deployed successfully")
        else:
            logger.error(f"Cluster deployment failed: {error}")
            raise Exception("Cluster deployment failed, check the log")

    def generate_deploy_conf(self):
        # Generate deployment configuration
        self.conf_manager.generate_confs(save=True)

    def setup_repo(self):
        if not os.path.exists(UDH_RPMS_PATH) == True:
            raise Exception(f"{os.path.basename(UDH_RPMS_PATH)} not exist, please check")
        logger.info(f'start  decompress {UDH_RPMS_PATH} ')
        pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        command = f"tar  -I {pigz_path} -xf {UDH_RPMS_PATH} -C {TAR_FILE_PATH}"
        self.executor.execute_command(command, shell=True)
        rpms_dir = os.path.join(TAR_FILE_PATH, os.path.basename(UDH_RPMS_PATH).split(".")[0])
        repodata_dir = os.path.join(rpms_dir, "repodata")
        if os.path.exists(repodata_dir):
            shutil.rmtree(repodata_dir)
        create_yum_repository(rpms_dir)

        if not is_httpd_installed():
            install_httpd()
            assert is_httpd_installed() == True

        render_template(HTTPD_TPL_FILE, {"udh_local_repo_path": rpms_dir}, HTTPD_CONF_FILE)

        run_shell_command("pgrep -f httpd | xargs kill -9", shell=True)
        run_shell_command("service httpd start", shell=True)