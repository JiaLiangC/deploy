# -*- coding:utf8 -*-
# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.container.container_manager import *
import subprocess

logger = get_logger()

class CommandExecutor:
    @staticmethod
    def execute_command(command, workdir=None, env_vars=None, shell=False, logfile=None):
        out = logfile or subprocess.PIPE
        print(f"Executing  command: {command}")
        env_vars = dict(env_vars) if env_vars else env_vars
        try:
            process = subprocess.Popen(
                command,
                stdout=out,
                stderr=out,
                shell=shell,
                cwd=workdir,
                env=env_vars,
                universal_newlines=True
            )

            if logfile:
                exit_status = process.wait()
                return exit_status

            output, error = process.communicate()
            exit_code = process.returncode
            if exit_code == 0:
                logger.info(f"Command executed successfully: {command}")
            else:
                logger.error(f"Command failed with exit code {exit_code}: cmd: {command}, out: {output}, err:{error}")
            return exit_code, output, error
        except Exception as e:
            logger.error(f"Exception occurred while executing command: {e}")
            return -1, "", str(e)

    @staticmethod
    def execute_command_withlog(command, log_file, workdir=None, env_vars=None, shell=False):
        with open(log_file, "w") as log:
            exit_status = CommandExecutor.execute_command(command, workdir, env_vars, shell, logfile=log)
            return exit_status

    @staticmethod
    def execute_docker_command(container_manager: ContainerManager, command, workdir=None):
        exit_code, output = container_manager.execute_command(command, workdir)
        return exit_code, output