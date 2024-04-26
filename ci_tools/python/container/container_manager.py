# !/usr/bin/python3

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.utils.os_utils import *
from python.common.path_manager import *
import os
import json
import shlex
import docker
logger = get_logger()




class ContainerManager:

    def __init__(self, os_info, path_manager: PathManager):
        self.path_manager = path_manager
        self.client = docker.from_env()
        self.image = DOCKER_IMAGE_MAP.get(self.get_fullos(os_info))
        self.volumes = self.get_volumes()
        self.name = self.get_container_name(os_info)
        self.container = None

    def get_container_name(self, os_info):
        return f"bigtop_{self.get_fullos(os_info)}"

    def get_fullos(self, os_info):
        os_type, os_version, os_arch = os_info
        os = f"{os_type}_{os_version}_{os_arch}"
        return os

    def get_volumes(self):
        volumes = {
            self.path_manager.bigtop_project_dir: {'bind': self.path_manager.bigtop_docker_volume_dir, 'mode': 'rw'},
            # bigtop /ws
            self.path_manager.bigtop_local_maven_repo_dir: {'bind': self.path_manager.bigtop_local_maven_repo_dir,
                                                            'mode': 'rw'},
            self.path_manager.bigtop_dl_dir: {'bind': self.path_manager.bigtop_dl_docker_volume_dir, 'mode': 'rw'},
            # dl /ws/dl
            "/root/.ssh": {'bind': '/root/.ssh', 'mode': 'rw'},
            "/root/.gradle": {'bind': '/root/.gradle', 'mode': 'rw'},
            PRJDIR: {'bind': self.path_manager.prj_docker_volume_dir, 'mode': 'rw'},
            PIP_CONF_FILE: {'bind': f'{os.path.expanduser("~/.config/pip/pip.conf")}', 'mode': 'rw'}
        }
        return volumes

    # Set different environments inside the container based on different tasks.
    def setup_environment(self):
        conf_args = {"prepare_env": True, "local_repo": self.path_manager.bigtop_local_maven_repo_dir}
        conf_str = json.dumps(conf_args)
        conf_str_quoted = shlex.quote(conf_str)

        prj_dir = self.path_manager.get_current_prj_dir()
        logger.info(f"conf_str is {conf_str_quoted}")
        build_script = os.path.join(prj_dir, BUILD_SCRIPT_RELATIVE_PATH)
        py_cmd = f"python3 {build_script} --config={conf_str_quoted}"
        py_cmd_with_source_in_container = f'source ./venv.sh && {py_cmd}'
        cmd = ['/bin/bash', '-c', py_cmd_with_source_in_container]
        self.execute_command(cmd, workdir=prj_dir)
        # cmd_install = 'yum install -y python3-devel'
        # self.execute_command(['/bin/bash', '-c', cmd_install])
        # print("only ambari need install python3-devel ")

    def create_container(self):
        try:
            # Check if container already exists and remove it
            try:
                existing_container = self.client.containers.get(self.name)
                if existing_container.status == "running":
                    existing_container.stop()
                existing_container.remove()
                logger.info(f"Existing container removed: {self.name}")
            except docker.errors.NotFound:
                logger.info("Container does not exist. Creating a new one.")

            # Create and start a new container
            self.container = self.client.containers.run(
                image=self.image,
                detach=True,
                name=self.name,
                volumes=self.volumes,
                network_mode='host',
                tty=True
            )
            logger.info(f"Container created: {self.container.short_id}")

            self.setup_environment()
        except docker.errors.ContainerError as e:
            logger.error(f"Container creation failed: {e}")
        except Exception as e:
            logger.error(f"Exception occurred while creating container: {e}")

    def remove_container(self):
        try:
            if self.container:
                self.container.stop()
                self.container.remove()
                logger.info(f"Container removed: {self.name}")
        except Exception as e:
            logger.error(f"Exception occurred while removing container: {e}")

    def execute_command(self, command, workdir=None):
        if not self.container:
            logger.error("No container is available to execute the command.")
            return -1, "No container"
        try:
            exec_log = self.container.exec_run(
                cmd=command,
                workdir=workdir
            )
            exit_code = exec_log.exit_code
            # Check if the output is a stream or bytes
            if hasattr(exec_log.output, 'decode'):
                # If it's bytes, decode it to a string
                output_str = exec_log.output.decode('utf-8')
            else:
                # If it's a stream, read and decode it
                output_str = exec_log.output.read().decode('utf-8')

            if exit_code == 0:
                logger.info(f"Docker command executed successfully: {command}")
            else:
                logger.error(f"Docker command failed with exit code {exit_code}: {command}")
            return exit_code, output_str
        except docker.errors.ContainerError as e:
            logger.error(f"Docker command failed: {e}")
            return -1, str(e)
        except docker.errors.NotFound as e:
            logger.error(f"Docker container not found: {e}")
            return -1, str(e)
        except Exception as e:
            logger.error(f"Exception occurred while executing docker command: {e}")
            return -1, str(e)