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
        self.log_file = os.path.join(LOGS_DIR, "ansible_playbook.log")

    def all_tasks(self):
        return  ["prepare_nodes.yml","install_ambari.yml","configure_ambari.yml","apply_blueprint.yml","post_install.yml"]

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
        inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
        env_vars = os.environ.copy()
        for playbook_path in playbook_tasks:
            command = ["python3", f"{PRJ_BIN_DIR}/ansible-playbook", playbook_path, f"--inventory={inventory_path}"]
            exit_status = self.executor.execute_command_withlog(command, self.log_file, workdir=PRJDIR, env_vars=env_vars)
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
        DISTRIBUTION = "jammy"
        CODENAME = "jammy"  # Use the appropriate codename for Ubuntu 22
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


    def check_prj_privileges(self):
        prj_dir = PRJDIR
        logger.info(f"check repo prj privileges prj_dir {prj_dir}")
        def get_top_level_directory(path):
            print(prj_dir)
            parts = path.split('/')
            if len(parts) == 3 and (parts[0]=='' and parts[-1]==''):
                raise ValueError("deployment script shouldn't be placed in / dir")

            if len(parts) <= 2 and parts[-1]:

                raise ValueError("deployment script shouldn't be placed in / dir")
            return '/' + parts[1]

        top_parent_dir = get_top_level_directory(prj_dir)
        try:
            env_vars = os.environ.copy()
            exit_status = self.executor.execute_command(['chmod', '-R', '755', top_parent_dir],  env_vars=env_vars)
            if exit_status != 0:
                logger.error(f"Cluster deployment failed, Failed to change permissions for {top_parent_dir}")
                raise Exception(f"Failed to change permissions for {top_parent_dir}")
        except Exception as e:
            raise Exception(f"Failed to change permissions for {top_parent_dir}: {e}")

    def _is_755(self, path):
        """Helper method to check if a directory has 755 permissions"""
        mode = os.stat(path).st_mode
        return (mode & 0o777) == 0o755

    def setup_yum_repo(self):
        self.check_prj_privileges()


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