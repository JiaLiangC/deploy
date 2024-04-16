# -*- coding:utf8 -*-
# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.config_management.configuration_manager import *
from python.install_utils.install_utils import *
from python.utils.os_utils import *
from python.container.container_manager import *
from python.executor.command_executor import *
import os
import glob
import json
import shlex

logger = get_logger()

DOCKER_IMAGE_MAP = {"centos7": "bigtop/slaves:trunk-centos-7", "centos8": "bigtop/slaves:trunk-rockylinux-8"}


class BuildManager:
    def __init__(self, ci_config, container_manager: ContainerManager):
        self.container_manager = container_manager
        self.ci_config = ci_config
        self.executor = CommandExecutor

    def clean_logs(self):
        log_files = glob.glob(os.path.join(LOGS_DIR, '*.log'))
        for log_file in log_files:
            try:
                os.remove(log_file)
                print(f"File {log_file} has been removed successfully")
            except Exception as e:
                print(f"Problem occurred: {str(e)}")

    def get_prj_dir(self):
        if self.ci_config["bigtop"]["use_docker"]:
            return self.ci_config["docker"]["volumes"]["prj"]
        else:
            return PRJDIR

    def build_components(self, clean_all, clean_components, components_str, stack, parallel):
        self.clean_logs()
        prj_dir = self.get_prj_dir()

        build_args = {"clean_all": clean_all, "clean_components": clean_components, "components": components_str,
                      "stack": stack, "max_workers": parallel}

        build_args_str = json.dumps(build_args)
        build_args_str_quoted = shlex.quote(build_args_str)
        build_script = os.path.join(prj_dir, BUILD_SCRIPT_RELATIVE_PATH)
        build_cmd = f'python3 {build_script} --config={build_args_str_quoted}'
        logger.info(f"Start building components with cmd {build_cmd}")

        if self.ci_config["bigtop"]["use_docker"]:
            assert self.container_manager is not None
            # execute the build command inside the container
            build_cmd = f'source ./venv.sh && {build_cmd}'
            cmd = ['/bin/bash', '-c', build_cmd]
            exit_code, output = self.executor.execute_docker_command(self.container_manager, cmd, workdir=prj_dir)
        else:
            # If no container is provided, execute the build command locally
            env_vars = os.environ.copy()
            logger.info(f"PYTHONPATH : {env_vars['PYTHONPATH']}")
            cmd = ['/bin/bash', '-c', build_cmd]
            exit_code, output, error = self.executor.execute_command(cmd, env_vars=env_vars, workdir=prj_dir)

        if exit_code == 0:
            logger.info("Build components successfully")
        else:
            logger.error(f"Build components failed with exit code {exit_code}: {output} ")
            raise Exception("Build components failed, check the log")