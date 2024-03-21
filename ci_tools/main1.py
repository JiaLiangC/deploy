# -*- coding:utf8 -*-
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.config_management.configuration_manager import *
from python.nexus.nexus_client import NexusClient
from python.nexus.nexus_repo_sync import NexusSynchronizer
from python.install_utils.install_utils import *
from python.utils.os_utils import *
import docker
import subprocess
import yaml
import os
import glob
import argparse
import json
import shlex
from datetime import datetime
from urllib.parse import urlparse
import tempfile
import shutil
from pathlib import Path

logger = get_logger()

ALL_COMPONENTS = ["hadoop", "spark", "hive", "hbase", "zookeeper", "kafka", "flink", "ranger", "kyuubi", "alluxio",
                  "knox", "celeborn", "tez", "ambari",  # "dinky",
                  "ambari-infra", "ambari-metrics", "bigtop-select", "bigtop-jsvc", "bigtop-groovy", "bigtop-utils",
                  "bigtop-ambari-mpack"]

DOCKER_IMAGE_MAP = {"centos7":"bigtop/slaves:trunk-centos-7", "centos8": "bigtop/slaves:trunk-rockylinux-8"}

class ConfigurationManager:
    def __init__(self):
        self.config = None

    def load_conf(self):
        conf_file_template_path = CI_CONF_FILE_TEMPLATE
        if not os.path.exists(CI_CONF_FILE):
            shutil.copy(CI_CONF_FILE_TEMPLATE, CI_CONF_FILE)

        if not os.path.exists(CI_CONF_FILE):
            raise FileNotFoundError(f"Configuration file {self.conf_file} not found.")
        with open(self.conf_file, 'r') as f:
            self.config = yaml.safe_load(CI_CONF_FILE)

    def get_value(self, key_path):
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            value = value.get(key)
            if value is None:
                return None
        return value





class ContainerManager:
    def __init__(self, os_info):
        self.client = docker.from_env()
        self.image = DOCKER_IMAGE_MAP.get(full_os)
        self.volumes = self.get_volumes()
        self.name  = self.get_container_name(os_info)
        self.container = None

    def get_container_name(self,os_info):
        return  f"bigtop_{self.get_fullos(os_info)}"

    def get_fullos(os_info):
        os_type, os_version, os_arch = os_info.split(",")
        os = f"{os_type}{os_version}"
        return  os

    def get_volumes(self):
        volumes = {
            self.conf["bigtop"]["prj_dir"]: {'bind': self.conf["docker"]["volumes"]["bigtop"], 'mode': 'rw'},
            # bigtop /ws
            self.conf["bigtop"]["local_maven_repo_dir"]: {'bind': self.conf["bigtop"]["local_maven_repo_dir"],
                                                          'mode': 'rw'},
            self.conf["bigtop"]["dl_dir"]: {'bind': f'{self.conf["docker"]["volumes"]["bigtop"]}/dl', 'mode': 'rw'},
            # dl /ws/dl
            "/root/.ssh": {'bind': '/root/.ssh', 'mode': 'rw'},
            "/root/.gradle": {'bind': '/root/.gradle', 'mode': 'rw'},
            PRJDIR: {'bind': self.conf["docker"]["volumes"]["prj"], 'mode': 'rw'},
            PIP_CONF_FILE: {'bind': f'{os.path.expanduser("~/.config/pip/pip.conf")}', 'mode': 'rw'}
        }
        return  volumes



    #根据不同的任务在容器内设置不同的环境
    def setup_environment(self):
        conf_args = {"prepare_env": True, "local_repo": self.conf["bigtop"]["local_maven_repo_dir"]}
        conf_str = json.dumps(conf_args)
        conf_str_quoted = shlex.quote(conf_str)

        prj_dir = self.get_prj_dir()
        logger.info(f"conf_str is {conf_str_quoted}")

        py_cmd = f"python3 {prj_dir}/ci_tools/python/bigtop_compile/bigtop_utils.py --config={conf_str_quoted}"
        if container:
            py_cmd = f'source ./venv.sh && {py_cmd}'
        cmd = ['/bin/bash', '-c', py_cmd]
        self.logged_exec_run(container, cmd=cmd, workdir=f'{prj_dir}')

        if container:
            # todo check os type
            # cmd_install = 'yum install -y python3-devel' #add python.h dependency for ambari build
            # self.logged_exec_run(container, cmd=['/bin/bash', '-c', cmd_install])
            print("only ambari need install python3-devel ")



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
        client = docker.from_env()
        try:
            exec_log = client.containers.exec_run(
                cmd=command,
                workdir=workdir,
                stdout=True,
                stderr=True,
                stream=True
            )
            exit_code = exec_log.exit_code
            output = exec_log.output.decode('utf-8').strip()
            if exit_code == 0:
                logger.info(f"Docker command executed successfully: {command}")
            else:
                logger.error(f"Docker command failed with exit code {exit_code}: {command}")
            return exit_code, output
        except docker.errors.ContainerError as e:
            logger.error(f"Docker command failed: {e}")
            return -1, str(e)
        except docker.errors.NotFound as e:
            logger.error(f"Docker container not found: {e}")
            return -1, str(e)
        except Exception as e:
            logger.error(f"Exception occurred while executing docker command: {e}")
            return -1, str(e)


class CommandExecutor:
    @staticmethod
    def execute_command(command, workdir=None, env_vars=None, shell=False, logfile=None):
        out = logfile or subprocess.PIPE
        try:
            process = subprocess.Popen(
                command,
                stdout=out,
                stderr=out,
                shell=shell,
                cwd=workdir,
                env=dict(env_vars),
                universal_newlines=True
            )

            if logfile:
                exit_status = process.wait()
                return  exit_status

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
            exit_status = CommandExecutor.execute_command(command, workdir, env_vars, shell, logfile=log_file)
            return exit_status


    @staticmethod
    def execute_docker_command(container_manager:ContainerManager, command, workdir=None):
        container_manager.execute_command(command,workdir)

# Example usage:
# executor = CommandExecutor()
# exit_code, output, error = executor.execute_command(['ls', '-la'])
# exit_code, output = executor.execute_docker_command('container_id', ['echo', 'hello world'])

# Example usage:
# container_manager = ContainerManager('image_name', {'/host/path': {'bind': '/container/path', 'mode': 'rw'}}, 'container_name')
# container_manager.create_container()
# exit_code, output = container_manager.execute_in_container(['echo', 'hello world'], workdir='/container/path')
# container_manager.remove_container()

class BuildManager:
    def __init__(self, ci_config, container_manager:ContainerManager):
        self.container_manager = container_manager
        self.ci_config = ci_config
        self.executor  = CommandExecutor

    def clean_logs():
        log_files = glob.glob(os.path.join(LOGS_DIR, '*.log'))
        for log_file in log_files:
            try:
                os.remove(log_file)
                print(f"File {log_file} has been removed successfully")
            except Exception as e:
                print(f"Problem occurred: {str(e)}")

    def build_components(self, clean_all, clean_components, components_str, stack, parallel):
        self.clean_logs()
        prj_dir = self.ci_config.get('prj_dir')

        build_args = {"clean_all": clean_all, "clean_components": clean_components, "components": components_str,
                      "stack": stack, "max_workers": parallel}

        build_args_str = json.dumps(build_args)
        build_args_str_quoted = shlex.quote(build_args_str)


        build_cmd = f'python3 {prj_dir}/ci_tools/python/bigtop_compile/bigtop_utils.py --config={build_args_str_quoted}'
        logger.info(f"Start building components with cmd {build_cmd}")

        if  self.ci_config["bigtop"]["use_docker"]:
            assert container_manager != None
            #execute the build command inside the container
            build_cmd = f'source ./venv.sh && {build_cmd}'
            cmd = ['/bin/bash', '-c', build_cmd]
            exit_code, output = self.executor.execute_docker_command(self.container_manager, cmd=cmd, workdir=prj_dir)
        else:
            # If no container is provided, execute the build command locally
            env_vars = os.environ.copy()
            logger.info(f"PYTHONPATH : {env_vars['PYTHONPATH']}")
            cmd = ['/bin/bash', '-c', build_cmd]
            exit_code, output, error = self.executor.execute_command(cmd,env_vars=env_vars,workdir=prj_dir)

        if exit_code == 0:
            logger.info("Build components successfully")
        else:
            logger.error(f"Build components failed with exit code {exit_code}: {output} {error}")
            raise Exception("Build components failed, check the log")

# Example usage:
# executor = CommandExecutor()
# container_manager = ContainerManager(...)
# build_manager = BuildManager(executor, container_manager.container, build_args)
# build_manager.build_components()


class NexusManager:
    def __init__(self,ci_conf, os_info, os_version, os_arch):
        self.ci_conf = ci_conf
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.synchronizer = NexusSynchronizer(os_type, os_version, os_arch, self.ci_conf["nexus"]["os_repo_data_dir"])
        self.nexus_client = NexusClient(self.ci_conf["nexus"]["host"], self.conf["nexus"]["user_name"],
                                        self.ci_conf["nexus"]["user_pwd"])
        self.nexus_installer = NexusInstaller(self.ci_conf["nexus"]["local_tar"],
                                              self.ci_conf["nexus"]["install_dir"], self.ci_conf["nexus"]["user_pwd"])


    def install_and_configure_nexus(self):
        logger.info("Starting Nexus installation")
        jdk_installer = JDKInstaller(self.ci_conf["nexus"]["jdk_local_tar"], self.ci_conf["nexus"]["jdk_install_dir"])
        jdk_installer.install()
        self.nexus_installer.install()

    def upload_bigdata_components(self, components):
        logger.info("Uploading big data components to Nexus")
        for comp in components:
            pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
            logger.info(f"uploading {pkg_dir} {comp}")
            self.nexus_client.repo_create(UDH_NEXUS_REPO_NAME, remove_old=False)
            self.nexus_client.batch_upload_bigdata_pkgs(pkg_dir, comp)
        logger.info(f'start upload bigdata rpms to nexus')

    def sync_os_repositories(self):
        logger.info("Synchronizing OS repositories")
        self.synchronizer.synchronize_repository()

    def upload_os_packages(self):
        pkgs_dirs = self.synchronizer.get_local_pkgs_dirs()
        logger.info(f'start upload {self.os_type + self.os_version + self.os_arch} os pkgs to local nexus repository')
        # os package 的 reponame 等于 os type 比如 redhat
        self.nexus_client.repo_create(self.os_type, remove_old=True)
        self.nexus_client.batch_upload_os_pkgs(pkgs_dirs, (self.os_type, self.os_version, self.os_arch))


    def package_nexus(self):
        logger.info(f'start package nexus ')
        pigz_installer = PigzInstaller(PIGZ_SOURC_CODE_PATH, PRJ_BIN_DIR)
        pigz_installer.install()
        udh_release_output_dir = self.conf["udh_nexus_release_output_dir"]

        self.install_nexus_and_jdk()
        # create repo if not exist and upload bigdata pkgs to nexus
        # create repo and sync and upload os pkgs to nexus
        self.repo_sync()
        self.upload_os_pkgs()
        kill_nexus_process()
        kill_user_processes("nexus")

        install_dir = self.conf["nexus"]["install_dir"]
        nexus_dir = self.nexus_installer.comp_dir
        pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        nexus_tar = os.path.join(install_dir, "nexus3.tar.gz")

        os.chdir(install_dir)
        command = f"tar cf - {os.path.basename(nexus_dir)} | {pigz_path} -k -5 -p 16 > {nexus_tar}"
        run_shell_command(command, shell=True)

        logger.info("package_nexus finished")
        name = f"UDH_NEXUS_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}"
        nexus_release_dir = os.path.join(udh_release_output_dir, name)
        if os.path.exists(nexus_release_dir):
            shutil.rmtree(nexus_release_dir, ignore_errors=True)
        os.makedirs(nexus_release_dir)

        release_nexus_tar = os.path.join(nexus_release_dir, "nexus3.tar.gz")
        shutil.move(nexus_tar, release_nexus_tar)
        logger.info(f"move compressed nexus tar from {nexus_tar} to {release_nexus_tar}")

        local_jdk = self.conf["nexus"]["jdk_local_tar"]
        dest_jdk = os.path.join(nexus_release_dir, os.path.basename(local_jdk))
        shutil.copy(local_jdk, dest_jdk)
        logger.info(f"move compressed nexus tar from {local_jdk} to {dest_jdk}")

        nexus_release_tar = os.path.join(udh_release_output_dir, f"{name}.tar.gz")
        os.chdir(udh_release_output_dir)
        logger.info(f"compresssing {nexus_release_tar}")
        command = f"tar cf - {os.path.basename(nexus_release_dir)} | {pigz_path} -k -5 -p 16 > {nexus_release_tar}"
        returncode = run_shell_command(command, shell=True)

        if returncode == 0:
            shutil.rmtree(nexus_release_dir)
        else:
            logger.error("package rpm failed, check the log")


# Example usage:
# config_manager = ConfigurationManager(...)
# nexus_manager = NexusManager(config_manager.config, 'centos', '7', 'x86_64')
# nexus_manager.install_and_configure_nexus()
# nexus_manager.upload_bigdata_components(['hadoop', 'spark'])
# nexus_manager.sync_os_repositories()

class DeploymentManager:
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
            self.set_udh_repo()

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



class FilesystemUtil:
    @staticmethod
    def create_dir(path, empty_if_exists=True):
        """Create a directory. If empty_if_exists is True, empty the dir if it exists."""
        if os.path.exists(path) and empty_if_exists:
            FilesystemUtil.empty_dir(path)
        else:
            os.makedirs(path, exist_ok=True)

    @staticmethod
    def empty_dir(path):
        """Empty the specified directory."""
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    @staticmethod
    def copy(src, dest):
        """Copy file or directory from src to dest."""
        if os.path.isdir(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

    @staticmethod
    def recursive_glob(rootdir='.', prefix=None, suffix=None, filter_func=None):
        """Recursively glob files from rootdir with specific prefix and/or suffix, and apply an optional filter."""
        files = [
            os.path.join(looproot, filename)
            for looproot, _, filenames in os.walk(rootdir)
            # 对文件名同时根据前缀和后缀进行过滤
            for filename in filenames if (prefix is None or filename.startswith(prefix)) and (suffix is None or filename.endswith(suffix))
        ]

        # 如果提供了过滤函数，进一步过滤文件列表
        if filter_func is not None:
            files = [file for file in files if filter_func(file)]

        return files


    @staticmethod
    def delete():
        if os.path.isfile(path):
            print("Deleting file:", path)
            os.remove(path)
        elif os.path.isdir(path):
            print("Deleting dir:", path)
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.islink(path):
            print("Deleting link :", path)
            os.remove(path)


class PathManager:
    def __init__(self, ci_config):
        # 各种目录的基目录，所有其他目录都基于此目录
        self.ci_config = ci_config
        self.initialize_paths()

    def initialize_paths(self):
        # 初始化所有需要的路径
        self.release_output_dir =  self.ci_config["udh_release_output_dir"]
        self.incremental_release_dir = os.path.join(udh_release_output_dir, "release_tmp")

        self.release_project_dir = os.path.join(self.release_output_dir, os.path.basename(PRJDIR))
        self.incremental_project_dir = os.path.join(self.incremental_release_dir, os.path.basename(PRJDIR))

        self.pkg_relative_path = os.path.join(self.project_dir, "pkg")
        self.incremental_rpm_tar = os.path.join(self.get_tmp_project_dir, UDH_RPMS_RELATIVE_PATH)
        self.release_project_rpm_tar = os.path.join(self.get_release_prj_dir(), UDH_RPMS_RELATIVE_PATH)
        self.incremental_rpm_parent_dir = self.get_parent_dir(self.incremental_rpm_tar())

        self.release_project_rpm_dir = self.get_rpm_dir(self.release_project_dir)
        self.incremental_rpm_dir = self.get_rpm_dir(self.incremental_project_dir)

        self.pigz_path = os.path.join(PRJ_BIN_DIR, "bin", "pigz")
        self.centos7_pg_10_source_dir = self.ci_config["centos7_pg_10_dir"]
        self.compiled_pkg_out_dir = os.path.join(self.ci_config["bigtop"]["prj_dir"], "output")
        # 根据需要可以继续添加其他路径


    def get_trino_jdk_source_path(self, os_arch):
        if self.os_arch == "x86_64":
            jdk_source = self.ci_config["jdk17_x86_location"]
        else:
            jdk_source = self.ci_config["jdk17_arm_location"]
        return jdk_source


    def get_rpm_dir(self,prj_dir):
        bigdata_rpm_dir = os.path.join(prj_dir, PKG_RELATIVE_PATH, os.path.basename(UDH_RPMS_PATH).split(".")[0])
        return bigdata_rpm_dir


    def get_parent_dir(self,p_dir):
        dir_path = Path(p_dir)
        parent_dir = dir_path.parent
        return  parent_dir

    def get_pigz_path(self):
        return self.pigz_path



class UDHReleaseManager:
    def __init__(self, os_type, os_version, os_arch, comps=[], incremental_release_src_tar=""):
        super().__init__()
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.comps = comps
        self.incremental_release_src_tar = incremental_release_src_tar
        self.path_manager = PathManager(base_dir=some_base_dir)
        self.release_prj_dir = self.path_manager.release_project_dir()
        self.pigz_path = os.path.join(self.path_manager.base_dir, "bin", "pigz")
        self.executor = CommandExecutor()
        self.initialize()


    def get_release_name(self):
        time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        release_name = f"UDH_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}-{time_dir_name}.tar.gz"
        return release_name

    def incremental_package(self):
        # 设置临时目录并初始化
        self.setup_temp_dir()
        # 解压存量发布包到临时目录
        self.extract_existing_release()
        # 更新组件
        self.update_components()
        # 重新打包
        self.compress_and_cleanup_dir(self.path_manager.get_tmp_release_prj_rpm_dir(), self.path_manager.get_release_prj_rpm_tar())
        # 清理临时目录（如果需要）
        FilesystemUtil.delete_dir(self.path_manager.get_release_temp_dir())

    def setup_temp_dir(self):
        """初始化临时目录"""
        udh_release_output_dir = self.path_manager.get_release_temp_dir()
        FilesystemUtil.create_dir(udh_release_output_dir, empty_if_exists=True)


    def extract_existing_release(self):
        """解压存量发布包到临时目录"""
        command = f"tar -I {self.pigz_path} -xf {self.incremental_release_src_tar} -C {self.temp_dir}"
        self.executor.execute_command(command,shell=True)

        rpms_tar = self.path_manager.get_tmp_release_prj_rpm_tar()
        rpms_tar_parent_dir = self.path_manager.get_tmp_release_prj_rpm_tar_parent_dir()
        pigz_path = self.path_manager.get_pigz_path()
        command = f"tar -I  {pigz_path} -xf  {rpms_tar} -C {rpms_tar_parent_dir}"
        self.executor.execute_command(command,shell=True)

    def update_components(self):
        """更新需要增量更新的组件"""
        for comp in self.comps:
            self.package_component(self.path_manager.get_tmp_release_prj_rpm_dir(), comp)

    def package_component(self,rpms_dir, comp):
        comp_dir = os.path.join(rpms_dir, comp)
        FilesystemUtil.create_dir(comp_dir, empty_if_exists=True)

        non_src_filepaths = self.get_compiled_packages(comp)
        for filepath in non_src_filepaths:
            dest_path = os.path.join(comp_dir, os.path.basename(filepath))
            shutil.copy(filepath, dest_path)

    def compress_and_cleanup_dir(self, source_rpms_dir, dest_rpms_tar):
        parent_dir = self.path_manager.get_parent_dir(source_rpms_dir)
        os.chdir(parent_dir)
        command = f"tar cf - {source_rpms_dir} | {self.pigz_path} -k -5 -p 16 > {dest_rpms_tar}"
        self.executor.execute_command(command,shell=True)
        FilesystemUtil.delete_dir(source_rpms_dir)


    def compress_release_directory(self):
        release_name = self.get_release_name()
        #release_prj_dir = self.path_manager.get_release_prj_dir()
        #os.chdir(self.path_manager.get_release_output_dir())
        self.compress_and_cleanup_dir(self.path_manager.get_release_prj_dir(), release_name)
        #command = f"tar cf - {os.path.basename(release_prj_dir)} | {self.pigz_path} -k -5 -p 16 > {release_name}"
        #self.executor.execute_command(command, shell=True)
        logger.info(f"UDH Release packaged successfully, removing {os.path.basename(self.release_prj_dir)}")
        #FilesystemUtil.delete_dir(release_prj_dir, ignore_errors=False)


    def package_bigdata_rpms(self):
        FilesystemUtil.create_dir(self.path_manager.get_release_prj_rpm_dir(), empty_if_exists=True)
        self.package_all_components()
        self.handle_special_conditions()
        self.create_yum_repository()
        self.compress_and_cleanup_dir(self.path_manager.get_release_prj_rpm_dir(), self.path_manager.get_release_prj_rpm_tar())


    def package_trino_jdk(self):
        #根据架构 cp jdk 到resource 目录下，在generate的时候，动态生成jdk 文件的位置填充到asible里
        jdk_source = self.path_manager.get_trino_jdk_source_path(self.os_arch)
        dest_path = os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH, os.path.basename(jdk_source))
        logger.info(f"trino jdk will copy from  {jdk_source} to {dest_path} ")
        shutil.copy(jdk_source, dest_path)


    def package_all_components(self):
        rpms_dir = self.path_manager.get_release_prj_rpm_dir()
        for comp in ALL_COMPONENTS:
            self.package_component(rpms_dir, comp)

    def get_compiled_packages(self, comp):
        # 搜索bigtop项目的编译的输出目录，获取编译好的某个组件的rpm包的路径,排除"src.rpm"文件
        pkg_dir = os.path.join(self.path_manager.get_compiled_pkg_out_dir(), comp)
        non_src_filepaths = FilesystemUtil.recursive_glob(pkg_dir, suffix='.rpm', filter_func=lambda fp: not fp.endswith("src.rpm"))
        return non_src_filepaths


    def handle_special_conditions(self):
        if self.os_type.lower().strip() == "centos" and self.os_version.strip() == "7":
            self.handle_centos7_special()
        self.package_trino_jdk()

    def handle_centos7_special(self):
        pg_dir = os.path.join(self.path_manager.get_release_prj_rpm_dir(), "pg10")
        FilesystemUtil.create_dir(pg_dir)
        pg_rpm_source = self.path_manager.get_centos7_pg_10_source_dir()
        pg_filepaths = FilesystemUtil.recursive_glob(pg_rpm_source, suffix=".rpm")
        for filepath in pg_filepaths:
            dest_path = os.path.join(pg_dir, os.path.basename(filepath))
            FilesystemUtil.copy(filepath, dest_path)

    def create_yum_repository(self):
        # 需要调用特定命令创建YUM仓库 # 确保系统拥有此类操作的工具
        res = create_yum_repository(self.bigdata_rpm_dir)
        if not res:
            raise Exception("Create YUM repository failed, check the log.")


    def package(self):
        self.prepare_release_directory()
        self.copy_project_to_release_directory()
        self.cleanup_unnecessary_files()

        if self.should_perform_incremental_packaging():
            self.incremental_package()
        else:
            self.package_bigdata_rpms()
        self.compress_release_directory()

    def prepare_release_directory(self):
        # 根据需要，准备发布目录，如创建或清理
        release_output_dir = self.path_manager.get_release_output_dir()
        FilesystemUtil.create_dir(release_output_dir, empty_if_exists=True)

    def copy_project_to_release_directory(self):
        # 这里的实现需要根据实际业务逻辑具体处理，以下仅为示例
        shutil.copytree(PRJDIR, self.path_manager.get_release_prj_dir(), symlinks=True, ignore=None)

    def cleanup_unnecessary_files(self):
        base_dir = self.path_manager.get_release_prj_dir()
        # 清理项目目录中不需要的文件和目录，如.git目录、未使用的配置文件等
        unnecessary_paths = [os.path.join(base_dir, ".git"),
                             os.path.join(base_dir, "bin/portable-ansible"),
                             os.path.join(base_dir, "bin/ansible-playbook")]
        for path in unnecessary_paths:
            FilesystemUtil.delete(path)

    def should_perform_incremental_packaging(self):
        # 这个方法根据实际情况来决定是否执行增量打包
        return len(self.comps) > 0 and len(self.incremental_release_src_tar) > 0







class MainApplication:
    def __init__(self, ci_config):
        self.args = self.parse_arguments
        self.ci_config  = ci_config
        self.nexus_manager = None
        self.build_manager = None
        self.deployment_manager = None
        self.release_manager = None

    def initialize(self):
        self.initializer = Initialize()
        self.initializer.run()


    def check_os_info(self, os_info):
        os_type, os_version, os_arch = os_info.split(",")
        assert os_arch in SUPPORTED_ARCHS
        assert os_type in SUPPORTED_OS
        os = f"{os_type}{os_version}"

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description='UDH Release Tool.')

        # Add the arguments
        parser.add_argument('-components',metavar='components',type=str,help='The components to be build, donat split')
        parser.add_argument('-install-nexus',action='store_true',help='install nexus ')
        parser.add_argument('-upload-nexus',action='store_true',help='upload components rpms to nexus')
        parser.add_argument('-repo-sync',action='store_true',help='sync the os repo from remote mirror to local disk')
        parser.add_argument('-upload-os-pkgs',action='store_true',help='upload os pkgs to nexus')
        parser.add_argument('-pkg-nexus',action='store_true',help='create the nexus package with os repo')
        parser.add_argument('-deploy',action='store_true',help='deploy a cluster')
        parser.add_argument('-generate-conf',action='store_true',help='generate all configuration files')
        parser.add_argument('-clean-components',metavar='clean_components',type=str,default=False,help='clean components that already build')
        parser.add_argument('-clean-all',action='store_true',help='rebuild all packages')
        parser.add_argument('-build-all',action='store_true',help='build all packages')
        parser.add_argument('-os-info',metavar='os_info',type=str,default="",help='the release params: os_name,os_version,arch exp:centos,7,x86_64')
        parser.add_argument('-stack',metavar='stack',type=str,default="ambari",help='The stack to be build')
        parser.add_argument('-parallel',metavar='parallel', type=int, default=3, help='The parallel build threads used in build')
        parser.add_argument('-release',action='store_true', help='make  bigdata platform release')
        parser.add_argument('-incremental', help='Incrementally update a release.', action='store_true')
        # Add more arguments as needed
        self.args = parser.parse_args()

    def install_nexus_if_needed(self):
        if self.args.install_nexus:
            os_info = self.args.os_info
            self.check_os_info(os_info)
            self.nexus_manager = NexusManager(self.config, *os_info.split(","))
            self.nexus_manager.install_and_configure_nexus()

    def build_components_if_needed(self):
        executor = CommandExecutor()

        container_manager = ContainerManager()
        container_manager.create_container()
        container_name = container_manager.get_container_name()

        if self.args.build_all or self.args.components:
            components_str = self.args.components or ",".join(ALL_COMPONENTS)
            os_info = self.args.os_info
            self.check_os_info(os_info)
            self.build_manager = BuildManager(self.ci_config,container_manager)
            self.build_manager.build_components(self.args.clean_all,self.args.clean_components,components_str,self.args.stack,self.args.parallel)

    def upload_to_nexus_if_needed(self):
        if self.args.upload_nexus:
            components_str = self.args.components or ",".join(ALL_COMPONENTS)
            components_arr = components_str.split(",")
            self.nexus_manager.upload_bigdata_components(components_arr)

    def sync_repo_if_needed(self):
        if self.args.repo_sync:
            self.nexus_manager.sync_os_repositories()

    def deploy_cluster_if_needed(self):
        if self.args.deploy:
            self.deployment_manager = DeploymentManager(self.ci_config)
            self.deployment_manager.deploy_cluster()

    def generate_conf_if_needed(self):
        if self.args.generate_conf:
            self.deployment_manager.generate_deploy_conf()

    def package_nexus_if_needed(self):
        if self.args.pkg_nexus:
            self.nexus_manager.package_nexus()

    def release_if_needed(self):
        if self.args.release:
            self.check_os_info(self.args.os_info)
            os = self.get_fullos(self.config.os_info)
            components_str = self.args.components or ",".join(ALL_COMPONENTS)
            components_arr = components_str.split(",") if components_str else []

            self.release_manager = UDHReleaseManager(self.config, os, components_arr, self.config.release_tar)
            self.release_manager.package()

    def upload_os_packages_if_needed(self):
        if self.args.upload_os_pkgs:
            self.nexus_manager.upload_os_packages()

    def run(self):
        self.initialize()
        self.install_nexus_if_needed(self.args.os_info)
        self.build_components_if_needed()
        self.upload_to_nexus_if_needed()
        self.sync_repo_if_needed()
        self.deploy_cluster_if_needed()
        self.generate_conf_if_needed()
        self.package_nexus_if_needed()
        self.release_if_needed()
        self.upload_os_packages_if_needed()

# Example usage:
# config_manager = ConfigurationManager('path/to/config.yml')
# config_manager.load_conf()
# app = MainApplication(config_manager.config)
# app.run()



def check_config():
    pass
# Check configuration validity

if __name__ == '__main__':
    config_manager = ConfigurationManager()
    config_manager.load_conf()
    app = MainApplication(config_manager.config)
    app.run()

# todo 指定一个路径的release 包，重新打包


# todo generate 和deploy之前都检查配置
# generate 之后，如果用户改了配置，要重新动态生成文件

# pg10 包，打入udh rpm
# 打包nexus 的时候，OS 的包传进去，如果要UDH，单独上传。
# pip3 install -t requests ansible/extras
# todo 使用设计模式重构 gpt intepreter
# tar -I pigz -xf nexus.tar.gz -C /tmp
# todo 目前同步包等只能在对应的操作系统上
# 场景开发过程的宿主机编译，容器编译，nexus 安装，组件上传，部署集群，发布 release 包(主要是nexus 包)
# 客户部署场景的集群部署：1.手动解压大部署包 2.执行source venv.sh 如果选择nexus 就解压安装nexus 到配置目录, 然后自动化部署
# 目前只能在对应操作系统打发布包
# todo 容器默认安装python3-devel
# todo 梳理容器依赖和宿主机依赖
# todo 程序退出时杀死 ansible 进程
# todo component name and params check

# docker run -d -it --network host -v ${PWD}:/ws -v /data/sdv1/bigtop_reporoot:/root --workdir /ws --name BIGTOP bigtop/slaves:3.2.0-centos-7
# {根据os 获取对应的镜像的名字}
# todo 把容器需要的都丢到一个目录，挂载到容器对应的目录下
# yum install createrepo
# todo pg 包上传到centos7
# todo rpm db broker 处理
# todo ci_conf files check
# todo python3 check httpd check for deploy
# todo createrepo check for others


