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
class BaseTask:
    def __init__(self):
        self.conf = self.load_conf()

    def load_conf(self):
        # "ci_conf.yml.template"
        conf_file_template_path = CI_CONF_FILE_TEMPLATE
        if not os.path.exists(CI_CONF_FILE):
            shutil.copy(CI_CONF_FILE_TEMPLATE, CI_CONF_FILE)
        with open(CI_CONF_FILE, 'r') as f:
            data = yaml.load(f, yaml.SafeLoader)
        return data

    def get_bigtop_working_dir(self):
        if self.conf["bigtop"]["use_docker"]:
            return self.conf["docker"]["volumes"]["bigtop"]
        else:
            return self.conf["bigtop"]["prj_dir"]

    def get_prj_dir(self):
        if self.conf["bigtop"]["use_docker"]:
            return self.conf["docker"]["volumes"]["prj"]
        else:
            return PRJDIR

    def logged_exec_run(self, container, *args, **kwargs):
        if container and self.conf["bigtop"]["use_docker"]:
            logger.info(f"Executing command: {args} {kwargs}")
            response = container.exec_run(*args, **kwargs)
            logger.info(f'command in docker: {response}')
        else:
            cmd = kwargs.get('cmd', None)
            if cmd is not None:
                logger.info(f"Command to be executed: {cmd}")
            else:
                logger.error("No command provided.")
            env_vars = os.environ.copy()
            logger.info(f"PYTHONPATH : {env_vars['PYTHONPATH']}")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                       env=dict(env_vars),
                                       universal_newlines=True)
            output, error = process.communicate()
            exit_code = process.returncode
            logger.info(f"logged_exec_run output:{output} error:{error}")
            response = (exit_code, output)

        return response


class ContainerTask(BaseTask):
    def __init__(self,os):
        self.os=os
        super().__init__()

    def create_container(self):
        image = DOCKER_IMAGE_MAP.get(self.os)
        container_name = f"bigtop_{self.os}"
        client = docker.from_env()

        try:
            container = client.containers.get(container_name)

            if container.status == "running":
                container.stop()
                logger.info("Container is in running state, stopped it.")

            container.remove()
            logger.info("Container stopped and removed successfully.")

        except docker.errors.NotFound:
            logger.info("Container does not exist.")

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

        container = client.containers.run(image=image,
                                          detach=True,
                                          network_mode='host',
                                          volumes=volumes,
                                          working_dir=self.conf["docker"]["volumes"]["bigtop"],
                                          tty=True,
                                          name=container_name)

        logger.info(f"Container started, ID: {container.id}")
        logger.info(f"Container status: {container.status}")

        return container

    def setup_environment(self, container):
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

    def run(self):
        if self.conf["bigtop"]["use_docker"]:
            container = self.create_container()
        else:
            logger.info("not use docker to compile, build in local")
            container = None
        # todo
        self.setup_environment(container)
        return container


class BuildComponentsTask(BaseTask):
    def __init__(self, container, build_args):
        super().__init__()
        self.container = container
        self.build_args = build_args

    def build_components(self):
        prj_dir = self.get_prj_dir()
        conf_str = json.dumps(self.build_args)
        logger.info(f"start build components  params {conf_str}")
        conf_str_quoted = shlex.quote(conf_str)
        pycmd = f'python3 {prj_dir}/ci_tools/python/bigtop_compile/bigtop_utils.py --config={conf_str_quoted}'
        if self.container:
            pycmd = f'source ./venv.sh && {pycmd}'
        cmd = ['/bin/bash', '-c', pycmd]
        exit_code, output = self.logged_exec_run(self.container, cmd=cmd, workdir=f'{prj_dir}')
        return exit_code

    def run(self):
        exit_code = self.build_components()
        if exit_code == 0:
            logger.info("build components  successfully")
        else:
            logger.error("build components  failed check the log")
            raise Exception("build components  failed check the log")


class NexusTask(BaseTask):
    def __init__(self, os_type, os_version, os_arch):
        super().__init__()
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.synchronizer = NexusSynchronizer(os_type, os_version, os_arch, self.conf["nexus"]["os_repo_data_dir"])
        self.nexus_client = NexusClient(self.conf["nexus"]["host"], self.conf["nexus"]["user_name"],
                                        self.conf["nexus"]["user_pwd"])
        self.nexus_installer = NexusInstaller(self.conf["nexus"]["local_tar"],
                                              self.conf["nexus"]["install_dir"], self.conf["nexus"]["user_pwd"])

    def install_nexus_and_jdk(self):
        logger.info(f"start install nexus and jdk ")
        jdk_installer = JDKInstaller(self.conf["nexus"]["jdk_local_tar"], self.conf["nexus"]["jdk_install_dir"])
        jdk_installer.install()
        self.nexus_installer.install()

    def upload_bigdata_copms2nexus(self, comps):
        logger.info(f'start upload bigdata rpms to nexus')
        for comp in comps:
            pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
            logger.info(f"uploading {pkg_dir} {comp}")
            self.nexus_client.repo_create(UDH_NEXUS_REPO_NAME, remove_old=False)
            self.nexus_client.batch_upload_bigdata_pkgs(pkg_dir, comp)

    def repo_sync(self):
        logger.info(f'start nexus repository synchronize')
        self.synchronizer.sync_repository()

    def upload_os_pkgs(self):
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

        # todo delete nexus dir

    def run(self):
        logger.info()


class DeployClusterTask(BaseTask):
    def __init__(self):
        super().__init__()

    def deploy(self):
        playbook_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/install_cluster.yml')
        inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
        log_file = os.path.join(LOGS_DIR, "ansible_playbook.log")

        conf_manager = ConfigurationManager(BASE_CONF_NAME)
        conf_manager.load_confs()
        conf_manager.save_ambari_configurations()
        conf_manager.setup_validators()
        conf_manager.validate_configurations()
        conf_manager.save_ansible_configurations()
        if not conf_manager.is_ambari_repo_configured():
            self.set_udh_repo()

        env_vars = os.environ.copy()

        command = ["python3", f"{PRJ_BIN_DIR}/ansible-playbook", playbook_path, f"--inventory={inventory_path}"]
        with open(log_file, "w") as log:
            logger.info(f"run playbook {command}")
            process = subprocess.Popen(command, shell=False, stdout=log, stderr=log,
                                       universal_newlines=True, env=dict(env_vars), cwd=PRJDIR)
        # 等待子进程完成
        exit_status = process.wait()
        logger.info(f"run_playbook {command} exit_status: {exit_status}")

    def set_udh_repo(self):
        if not os.path.exists(UDH_RPMS_PATH) == True:
            raise Exception(f"{os.path.basename(UDH_RPMS_PATH)} not exist, please check")
        logger.info(f'start  decompress {UDH_RPMS_PATH} ')
        command = f"tar  -zxf {UDH_RPMS_PATH} -C {TAR_FILE_PATH}"
        run_shell_command(command, shell=True)
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

    def generate_deploy_conf(self):
        conf_manager = ConfigurationManager(BASE_CONF_NAME)
        conf_manager.generate_confs(save=True)

    def run(self):
        logger.info("deploy ")
        self.deploy()


class UDHReleaseTask(BaseTask):
    def __init__(self, os_type, os_version, os_arch, comps=[], release_tar=""):
        super().__init__()
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.release_prj_dir = ""
        self.pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        self.comps = comps
        self.release_tar = release_tar
        self.initialize()

    def initialize(self):
        udh_release_output_dir = self.conf["udh_release_output_dir"]
        self.release_prj_dir = os.path.join(udh_release_output_dir, os.path.basename(PRJDIR))
        if os.path.exists(udh_release_output_dir):
            logger.info(f"rmtree udh_release_output_dir {udh_release_output_dir}")
            shutil.rmtree(udh_release_output_dir, ignore_errors=True)
        os.makedirs(udh_release_output_dir)
        pigz_installer = PigzInstaller(PIGZ_SOURC_CODE_PATH, PRJ_BIN_DIR)
        pigz_installer.install()

    def get_compiled_packages(self, comp):
        pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
        logger.info(f"package bigdata rpms pkg_dir:{pkg_dir} comp:{comp}")
        filepaths = glob.glob(os.path.join(pkg_dir, "**", "*.rpm"), recursive=True)
        non_src_filepaths = [fp for fp in filepaths if not fp.endswith("src.rpm")]
        return non_src_filepaths

    def package_bigdata_rpms(self):
        rpm_dir_name = os.path.basename(UDH_RPMS_PATH).split(".")[0]
        bigdata_rpm_dir = os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH, rpm_dir_name)
        if os.path.exists(bigdata_rpm_dir):
            logger.info(f"rmtree bigdata_rpm_dir {bigdata_rpm_dir}")
            shutil.rmtree(bigdata_rpm_dir, ignore_errors=True)
        os.makedirs(bigdata_rpm_dir)

        for comp in ALL_COMPONENTS:
            comp_dir = os.path.join(bigdata_rpm_dir, comp)
            if not os.path.exists(comp_dir):
                os.makedirs(comp_dir)

            non_src_filepaths = self.get_compiled_packages(comp)

            for filepath in non_src_filepaths:
                dest_path = os.path.join(comp_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")

        if self.os_type.lower().strip() == "centos" and self.os_version.strip() == "7":
            pg_dir = os.path.join(bigdata_rpm_dir, "pg10")
            pg_rpm_source = self.conf["centos7_pg_10_dir"]
            if not os.path.exists(pg_dir):
                os.makedirs(pg_dir)
            pg_filepaths = glob.glob(os.path.join(pg_rpm_source, "**", "*.rpm"), recursive=True)
            for filepath in pg_filepaths:
                dest_path = os.path.join(pg_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")

        res = create_yum_repository(bigdata_rpm_dir)
        if not res:
            raise Exception("create repo failed, check the log")

        dest_tar = f"{bigdata_rpm_dir}.tar.gz"
        os.chdir(os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH))
        command = f"tar cf - {os.path.basename(bigdata_rpm_dir)} | {self.pigz_path} -k -5 -p 16 > {dest_tar}"
        returncode = run_shell_command(command, shell=True)
        if returncode == 0:
            shutil.rmtree(bigdata_rpm_dir)
        else:
            logger.error("package rpm failed, check the log")

    def incremental_package(self):
        udh_release_output_dir = self.conf["udh_release_output_dir"]
        pigz_path = self.pigz_path
        # 创建临时目录并自动清理
        temp_dir = os.path.join(udh_release_output_dir,"release_tmp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        # with tempfile.TemporaryDirectory(dir=udh_release_output_dir) as temp_dir:
        os.makedirs(temp_dir)
        print(f"临时目录已创建在: {temp_dir}")
        # 1.在 self.release_tar 所在的目录创建一个临时目录，然后把 self.release_tar 压缩包解压到那个临时目录里
        command = f" tar -I  {pigz_path} -xf  {self.release_tar} -C {temp_dir}"
        returncode = run_shell_command(command, shell=True)
        temp_release_prj_dir = os.path.join(temp_dir, "bigdata-deploy")
        udh_rpms_tar = os.path.join(temp_release_prj_dir, UDH_RPMS_RELATIVE_PATH)

        rpm_dir_name = os.path.basename(UDH_RPMS_PATH).split(".")[0]
        bigdata_rpm_dir = os.path.join(temp_release_prj_dir, PKG_RELATIVE_PATH, rpm_dir_name)
        dir_path = Path(bigdata_rpm_dir)
        udh_rpms_parent_dir = dir_path.parent
        print(f"父目录路径是: {udh_rpms_parent_dir}")
        # 2.解压 UDH_RPMS_PATH 中 udh-rpms 压缩包
        command = f" tar -I  {pigz_path} -xf  {udh_rpms_tar} -C {udh_rpms_parent_dir}"
        returncode = run_shell_command(command, shell=True)

        # 3.删除  comps 中的rpm
        for comp in self.comps:
            comp_dir = os.path.join(bigdata_rpm_dir, comp)
            if os.path.exists(comp_dir):
                shutil.rmtree(comp_dir)
            os.makedirs(comp_dir)

            # 4.从 output 中复制对应的rpm 到 udh-rpms 中
            non_src_filepaths= self.get_compiled_packages(comp)
            for filepath in non_src_filepaths:
                dest_path = os.path.join(comp_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")

        # 5.压缩 udh-rpms
        dest_tar = f"{bigdata_rpm_dir}.tar.gz"
        os.chdir(os.path.join(temp_release_prj_dir, PKG_RELATIVE_PATH))
        command = f"tar cf - {os.path.basename(bigdata_rpm_dir)} | {self.pigz_path} -k -5 -p 16 > {dest_tar}"
        returncode = run_shell_command(command, shell=True)
        if returncode == 0:
            # 6.删除 udh-rpms文件夹
            shutil.rmtree(bigdata_rpm_dir)
        else:
            logger.error("package rpm failed, check the log")
            # 7.重新压缩release 压缩包
        # 临时目录将在这个块结束时自动删除
        os.chdir(temp_dir)
        time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        udh_release_name = f"UDH_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}-{time_dir_name}.tar.gz"

        command = f"tar cf - {os.path.basename(PRJDIR)} | {self.pigz_path} -k -5 -p 16 > {udh_release_name}"
        run_shell_command(command, shell=True)

    def package(self):
        # todo centos7 增加pg10的包 tar cf - nexus | pigz -k -5 -p 8 > nexus.tar.gz
        if len(self.comps) > 0 and len(self.release_tar) > 0:
            self.incremental_package()
            return

        udh_release_output_dir = self.conf["udh_release_output_dir"]
        release_prj_dir = self.release_prj_dir

        # 1. Copy project directory into udh_release_output_dir
        logger.info(f"packaging: copy {PRJDIR} to {release_prj_dir}")
        shutil.copytree(PRJDIR, release_prj_dir)
        # 2. Change into the copied directory and remove .git
        os.chdir(release_prj_dir)
        git_dir = os.path.join(release_prj_dir, ".git")
        if os.path.exists(git_dir):
            logger.info(f"remove git dir {git_dir}")
            shutil.rmtree(git_dir)

        # 3. remove conf file
        conf_dir = os.path.join(release_prj_dir, "conf")
        for filename in os.listdir(conf_dir):
            if not filename.endswith(".template"):
                conf_file = os.path.join(conf_dir, filename)
                if os.path.isfile(conf_file):
                    os.remove(conf_file)
                    logger.info(f"Removed file: {conf_file}")

        portable_ansible_dir = os.path.join(release_prj_dir, "bin/portable-ansible")
        if os.path.exists(portable_ansible_dir):
            logger.info(f"remove portable_ansible dir {portable_ansible_dir}")
            shutil.rmtree(portable_ansible_dir)
        ansible_playbook_link = os.path.join(release_prj_dir, "bin/ansible-playbook")
        if os.path.exists(ansible_playbook_link):
            if os.path.islink(ansible_playbook_link):
                try:
                    # 删除软链接
                    os.unlink(ansible_playbook_link)
                    logger.info(f"Successfully removed the symlink at {ansible_playbook_link}")
                except OSError as e:
                    logger.error(f"Error: {e.filename} - {e.strerror}.")
            else:
                shutil.rmtree(ansible_playbook_link)
                logger.info(f"Successfully removed the ansible plaobook at {ansible_playbook_link}")

        if not os.path.exists(os.path.join(udh_release_output_dir, "pigz")):
            shutil.copy(self.pigz_path, os.path.join(udh_release_output_dir, "pigz"))


        else:
            self.package_bigdata_rpms()

            os.chdir(udh_release_output_dir)
            time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
            udh_release_name = f"UDH_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}-{time_dir_name}.tar.gz"

            command = f"tar cf - {os.path.basename(PRJDIR)} | {self.pigz_path} -k -5 -p 16 > {udh_release_name}"
            run_shell_command(command, shell=True)
            logger.info(f"UDH Release packaged success, remove {os.path.basename(release_prj_dir)}")
            shutil.rmtree(os.path.basename(release_prj_dir))


class InitializeTask(BaseTask):
    def __init__(self):
        super().__init__()

    def run(self):
        if not os.path.exists(OUTPUT_DIR):
            os.mkdir(OUTPUT_DIR)


def setup_options():
    parser = argparse.ArgumentParser(description='CI Tools.')

    # Add the arguments
    parser.add_argument('-components',
                        metavar='components',
                        type=str,
                        help='The components to be build, donat split')
    parser.add_argument('-install-nexus',
                        action='store_true',
                        help='install nexus ')

    parser.add_argument('-upload-nexus',
                        action='store_true',
                        help='upload components rpms to nexus')

    parser.add_argument('-upload-os-pkgs',
                        action='store_true',
                        help='upload os pkgs to nexus')

    parser.add_argument('-deploy',
                        action='store_true',
                        help='deploy a cluster')

    parser.add_argument('-generate-conf',
                        action='store_true',
                        help='generate all configuration files')

    parser.add_argument('-clean-components',
                        metavar='clean_components',
                        type=str,
                        default=False,
                        help='clean components that already build')

    parser.add_argument('-clean-all',
                        action='store_true',
                        help='rebuild all packages')

    parser.add_argument('-build-all',
                        action='store_true',
                        help='build all packages')

    parser.add_argument('-repo-sync',
                        action='store_true',
                        help='sync the os repo from remote mirror to local disk')

    parser.add_argument('-pkg-nexus',
                        action='store_true',
                        help='create the nexus package with os repo')

    parser.add_argument('-os-info',
                        metavar='os_info',
                        type=str,
                        default="",
                        help='the release params: os_name,os_version,arch exp:centos,7,x86_64')

    parser.add_argument('-stack',
                        metavar='stack',
                        type=str,
                        default="ambari",
                        help='The stack to be build')

    parser.add_argument('-parallel',
                        metavar='parallel',
                        type=int,
                        default=3,
                        help='The parallel build threads used in build')

    parser.add_argument('-release',
                        action='store_true',
                        help='make  bigdata platform release')

    parser.add_argument('-release-tar',
                        type=str,
                        help='recreate release tar useing exist release tar when repackage some component')

    # Parse the arguments
    args = parser.parse_args()
    logger.info(f"main program params is : {args}")
    return args


def clean_logs():
    # 使用 glob 模块找到目录下的所有 .log 文件
    log_files = glob.glob(os.path.join(LOGS_DIR, '*.log'))
    for log_file in log_files:
        try:
            os.remove(log_file)
            print(f"File {log_file} has been removed successfully")
        except Exception as e:
            print(f"Problem occurred: {str(e)}")


def config_check():
    # 1.supportted os arch version check
    # 2.configged jar check
    # 3.supported commponents check
    # 4.stack check
    # 5.
    print("placeholder")


def build_components(clean_all, clean_components, components_str, stack, parallel,os):
    clean_logs()
    # create container for building
    container_task = ContainerTask(os)
    container = container_task.run()
    build_args = {"clean_all": clean_all, "clean_components": clean_components, "components": components_str,
                  "stack": stack, "max_workers": parallel}
    build_components_task = BuildComponentsTask(container, build_args)
    build_components_task.run()


def check_os_info(os_info):
    os_type, os_version, os_arch = os_info.split(",")
    assert os_arch in SUPPORTED_ARCHS
    assert os_type in SUPPORTED_OS
    os = f"{os_type}{os_version}"

def get_fullos(os_info):
    os_type, os_version, os_arch = os_info.split(",")
    os = f"{os_type}{os_version}"
    return  os

def main():
    args = setup_options()
    release = args.release
    deploy = args.deploy
    clean_all = args.clean_all
    build_all = args.build_all
    parallel = args.parallel
    clean_components = args.clean_components
    components_str = args.components
    stack = args.stack
    upload_nexus = args.upload_nexus
    repo_sync = args.repo_sync
    os_info = args.os_info
    install_nexus = args.install_nexus
    pkg_nexus = args.pkg_nexus
    upload_os_pkgs = args.upload_os_pkgs
    generate_conf = args.generate_conf
    release_tar = args.release_tar

    init_task = InitializeTask()
    init_task.run()

    if install_nexus:
        check_os_info(os_info)
        nexus_task = NexusTask(os_type, os_version, os_arch)
        nexus_task.install_nexus_and_jdk()

    if build_all:
        components_str = ",".join(ALL_COMPONENTS)

    if components_str and len(components_str) > 0:
        check_os_info(os_info)
        os = get_fullos(os_info)
        build_components(clean_all, clean_components, components_str, stack, parallel,os)

    if upload_nexus:
        # 如果没通过buid参数指定传哪些包，默认传全部
        if not components_str or len(components_str) == 0:
            components_str = ",".join(ALL_COMPONENTS)
        components_arr = components_str.split(",")
        if len(components_arr) > 0:
            nexus_task = NexusTask(os_type, os_version, os_arch)
            nexus_task.upload_bigdata_copms2nexus(components_arr)

    if repo_sync and os_info and len(os_info) > 0:
        nexus_task = NexusTask(os_type, os_version, os_arch)
        nexus_task.repo_sync()

    if deploy:
        deploy_cluster_task = DeployClusterTask()
        deploy_cluster_task.run()

    if generate_conf:
        deploy_cluster_task = DeployClusterTask()
        deploy_cluster_task.generate_deploy_conf()

    if pkg_nexus:
        nexus_task = NexusTask(os_type, os_version, os_arch)
        nexus_task.package_nexus()

    if release:
        check_os_info(os_info)
        os = get_fullos(os_info)
        components_arr = []
        if components_str and len(components_str) > 0:
            components_arr = components_str.split(",")
            build_components(clean_all, clean_components, components_str, stack, parallel,os)

        os_type, os_version, os_arch = os_info.split(",")
        udh_release_task = UDHReleaseTask(os_type, os_version, os_arch, components_arr, release_tar)
        udh_release_task.package()
        logger.info("do release")

    if upload_os_pkgs:
        nexus_task = NexusTask(os_type, os_version, os_arch)
        nexus_task.upload_os_pkgs()


if __name__ == '__main__':
    main()

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
# todo 程序退出时杀死ansible 进程
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
