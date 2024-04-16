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
    def __init__(self, ci_config, deploy_ambari_only=False, prepare_nodes_only=False):
        self.deploy_ambari_only=deploy_ambari_only
        self.prepare_nodes_only=prepare_nodes_only
        self.executor = CommandExecutor
        self.ci_config = ci_config
        self.conf_manager = ConfigurationManager(BASE_CONF_NAME)


    def all_tasks(self):
        return  ["prepare_nodes.yml","install_ambari.yml","configure_ambari.yml","apply_blueprint.yml"]

    def generate_deploy_tasks(self):
        if self.deploy_ambari_only:
            playbook_tasks = [task for task in self.all_tasks() if task != "apply_blueprint.yml"]
        elif self.prepare_nodes_only:
            playbook_tasks = [self.all_tasks()[0]]
        else:
            playbook_tasks =self.all_tasks()
        print(playbook_tasks)
        return [os.path.join(ANSIBLE_PRJ_DIR, f'playbooks/{task}') for task in playbook_tasks]

    def execute_tasks(self, playbook_tasks):
        for playbook_path in playbook_tasks:
            inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
            log_file = os.path.join(LOGS_DIR, "ansible_playbook.log")
            env_vars = os.environ.copy()
            command = ["python3", f"{PRJ_BIN_DIR}/ansible-playbook", playbook_path, f"--inventory={inventory_path}"]
            exit_status = self.executor.execute_command_withlog(command, log_file, workdir=PRJDIR, env_vars=env_vars)
            # 等待子进程完成
            logger.info(f"run_playbook {command} exit_status: {exit_status}")

            if exit_status == 0:
                logger.info("Cluster deployed successfully")
            else:
                logger.error(f"Cluster deployment failed")
                raise Exception("Cluster deployment failed, check the log")

    def deploy_cluster(self):
        #playbook_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/install_cluster.yml')
        conf_manager = self.conf_manager
        conf_manager.load_confs()
        conf_manager.save_ambari_configurations()
        conf_manager.setup_validators()
        conf_manager.validate_configurations()
        conf_manager.save_ansible_configurations()
        if not conf_manager.is_ambari_repo_configured():
            self.setup_repo()

        self.deploy_ambari_only = conf_manager.advanced_conf.get("deploy_ambari_only")
        self.prepare_nodes_only = conf_manager.advanced_conf.get("prepare_nodes_only")

        self.execute_tasks(self.generate_deploy_tasks())



    def generate_deploy_conf(self):
        # Generate deployment configuration
        self.conf_manager.generate_confs(save=True)


    def setup_repo(self):
        if get_os_type() == "ubuntu":
            self.setup_apt_repo()
        else:
            self.setup_yum_repo()

    def setup_apt_repo(self):
        if not os.path.exists(UDH_RPMS_PATH) == True:
            raise Exception(f"{os.path.basename(UDH_RPMS_PATH)} not exist, please check")
        logger.info(f'start  decompress {UDH_RPMS_PATH} ')

        DISTRIBUTION = "jammy"
        CODENAME = "jammy"  # Use the appropriate codename for Ubuntu 22

        command = f"tar  -zxvf {UDH_RPMS_PATH} -C {TAR_FILE_PATH}"
        self.executor.execute_command(command, shell=True)
        pkgs_dir = os.path.join(TAR_FILE_PATH, os.path.basename(UDH_RPMS_PATH).split(".")[0])
        repodata_dir = os.path.join(pkgs_dir, "apt")
        if os.path.exists(repodata_dir):
            shutil.rmtree(repodata_dir)
        REPO_BASE_DIR = os.path.join(pkgs_dir,"apt")
        setup_and_process_repository(REPO_BASE_DIR, DISTRIBUTION, CODENAME, pkgs_dir)

        if not is_apache2_installed():
            install_apache2()
            assert is_apache2_installed() == True

        render_template(APACHE2_TPL_FILE, {"udh_local_repo_path": pkgs_dir}, APACHE2_CONF_FILE)

        run_shell_command("systemctl restart apache2", shell=True)


    def setup_yum_repo(self):
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