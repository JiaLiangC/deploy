import os
import atexit
import signal
import subprocess
import concurrent.futures
from python.common.basic_logger import logger
from python.common.constants import *
from python.easyprocess import EasyProcess
import shutil
from urllib.parse import urlparse, urljoin
import json
from datetime import datetime
import argparse
import platform
import sys
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUCCESS_FILE = os.path.join(OUTPUT_DIR, 'success_components.json')


class BigtopBuilder(object):

    def __init__(self, conf):
        self.conf = conf
        self.success_components = self.load_success_components()
        # 存储所有子进程的 PID
        self.child_pids = []
        atexit.register(self.kill_child_processes)

    def get_bigtop_working_dir(self):
        ci_conf = self.get_ci_conf()
        if ci_conf["bigtop"]["use_docker"]:
            return ci_conf["docker"]["volumes"]["bigtop"]
        else:
            return ci_conf["bigtop"]["prj_dir"]

    # bigdata 项目会挂载到容器执行
    def get_prj_dir(self):
        ci_conf = self.get_ci_conf()
        if ci_conf["bigtop"]["use_docker"]:
            return ci_conf["docker"]["volumes"]["prj"]
        else:
            return PRJDIR

    def is_same_url(self, url1, url2):
        normalized_url1 = urljoin(url1, '/')
        normalized_url2 = urljoin(url2, '/')

        return normalized_url1 == normalized_url2

    def get_full_os_major_version(self):
        os_type = self.get_os_type()
        os_version = self.get_os_version()
        full_os_major_version = os_type + os_version
        logger.info(f"full_os_and_major_version is {full_os_major_version}")
        return full_os_major_version

    def get_os_type(self):
        operatingSystem = platform.system().lower()
        if operatingSystem == 'linux':
            operatingSystem = platform.linux_distribution()[0].lower()

        # special cases
        if operatingSystem.startswith('ubuntu'):
            operatingSystem = 'ubuntu'
        elif operatingSystem.startswith('red hat enterprise linux'):
            operatingSystem = 'redhat'
        elif operatingSystem.startswith('kylin linux'):
            operatingSystem = 'kylin'
        elif operatingSystem.startswith('centos linux'):
            operatingSystem = 'redhat'
        elif operatingSystem.startswith('rocky linux'):
            operatingSystem = 'redhat'
        elif operatingSystem.startswith('uos'):
            operatingSystem = 'uos'
        elif operatingSystem.startswith('anolis'):
            operatingSystem = 'anolis'
        elif operatingSystem.startswith('asianux server'):
            operatingSystem = 'asianux'
        elif operatingSystem.startswith('bclinux'):
            operatingSystem = 'bclinux'
        elif operatingSystem.startswith('openeuler'):
            operatingSystem = 'openeuler'

        if operatingSystem == '':
            raise Exception("Cannot detect os type. Exiting...")

        return operatingSystem

    def get_os_version(self):
        os_type = self.get_os_type()
        version = platform.linux_distribution()[1]

        if version:
            if os_type == "kylin":
                # kylin v10
                if version == 'V10':
                    version = 'v10'
            elif os_type == 'anolis':
                if version == '20':
                    version = '20'
            elif os_type == 'uos':
                # uos 20
                if version == '20':
                    version = '20'
            elif os_type == 'openeuler':
                # openeuler 22
                version = '22'
            elif os_type == 'bclinux':
                version = '8'
            elif os_type == '4.0.':
                # support nfs (zhong ke fang de)
                version = '4'
            elif len(version.split(".")) > 2:
                # support 8.4.0
                version = version.split(".")[0]
            else:
                version = version
            return version
        else:
            raise Exception("Cannot detect os version. Exiting...")

    def mv_repo_files(self, source_folder, target_folder):
        for filename in os.listdir(source_folder):
            source_file = os.path.join(source_folder, filename)

            # 检查文件是否以 .repo 结尾
            if filename.endswith(".repo") and os.path.isfile(source_file):
                # 构建目标文件路径
                target_file = os.path.join(target_folder, filename)

                # 移动文件到目标文件夹
                shutil.move(source_file, target_file)
                logger.info(f"Moved file: {source_file} --> {target_file}")

    def set_yum_repo(self):
        repo_path = "/etc/yum.repos.d"
        backup_dir = "/etc/yum.repos.d/bakup"

        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        os.makedirs(backup_dir)
        self.mv_repo_files(repo_path, backup_dir)

        os_full_name = self.get_full_os_major_version()
        repo_tpl_file_path = os.path.join(SCRIPT_DIR, f"templates/{os_full_name}_repos/{os_full_name}.repo")
        dest_path = os.path.join(repo_path, f"{os_full_name}.repo")
        with open(repo_tpl_file_path, 'r') as file_a, open(dest_path, 'w') as file_b:
            file_b.write(file_a.read())

        logger.info(f"write new repo {dest_path} to {dest_path}")

        # 3.skip unavailable
        conf_return_code = EasyProcess(
            ["yum-config-manager", "--save", '--setopt="*.skip_if_unavailable=true"']).call().return_code
        logger.info(
            f"skip broken repo set: yum-config-manager --save --setopt=*.skip_if_unavailable=true skip unavailable {conf_return_code}")
        # 3.make cache
        # mk_return_code = EasyProcess(["yum", "makecache"]).call().return_code

    def set_debian_repo(self):
        # 1.back_up_old_repo
        # 2.write new repo
        # 3.make cache
        logger.info("set_debian_repo do nothing")

    def set_maven_conf(self, maven_conf_path):
        from jinja2 import Template
        maven_local_repo_path = os.path.expanduser(self.conf["local_repo"])
        assert os.path.exists(maven_conf_path) == True
        logger.info("set maven conf")
        # set and test container maven conf
        conf_file = os.path.join(SCRIPT_DIR, "templates/maven/settings.xml.j2")
        with open(conf_file, 'r') as fp:
            m_conf = fp.read()

        template = Template(m_conf)
        # 渲染模板
        result = template.render({"maven_local_repo_path": maven_local_repo_path})
        maven_conf_file = os.path.join(maven_conf_path, "settings.xml")
        with open(maven_conf_file, 'w') as fp:
            fp.write(result)

        with open(maven_conf_file, 'r') as fp:
            dest_content = fp.read()
        assert dest_content == result, "Content of the destination file does not match the expected content"

    def set_web_compile_envirment(self):
        logger.info("set web compile envirment")
        self.set_npm_proxy()
        self.set_yarn_registry()
        self.set_bowerrc_proxy()

    def set_npm_proxy(self):
        logger.info("set npm registry")
        content = "registry=https://registry.npmmirror.com/"
        file_path = os.path.expanduser("~/.npmrc")
        with open(file_path, 'w') as f:
            f.write(content)

    def set_yarn_registry(self):
        logger.info("set yarn registry")
        content = 'registry "https://registry.npmmirror.com/"'
        file_path = os.path.expanduser("~/.yarnrc")
        with open(file_path, 'w') as f:
            f.write(content)

    def set_git_config(self):
        logger.info("set git config")
        content = f"""
[user]
    email = jialiangcai@gmail.com
[https]
    proxy = http://{self.conf["proxy"]}
[http]
    proxy = http://{self.conf["proxy"]}
        """
        file_path = os.path.expanduser("~/.gitconfig")
        with open(file_path, 'w') as f:
            f.write(content)

    def set_bowerrc_proxy(self):
        logger.info("set bower proxy")
        content = f"""{{
"strict-ssl": false,
"allow_root": true,
"proxy": "http://{self.conf["proxy"]}",
"https-proxy":"http://{self.conf["proxy"]}"
}}
        """
        file_path = os.path.expanduser("~/.bowerrc")
        with open(file_path, 'w') as f:
            f.write(content)

    def kill_child_processes(self):
        for pid in self.child_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # 进程已经结束

    def get_ci_conf(self):
        import yaml
        conf_file_template_path = CI_CONF_FILE_TEMPLATE
        if not os.path.exists(CI_CONF_FILE):
            shutil.copy(CI_CONF_FILE_TEMPLATE, CI_CONF_FILE)
        with open(CI_CONF_FILE, 'r') as f:
            data = yaml.load(f, yaml.SafeLoader)
        return data

    # bigtop git 项目需要clean，不然不会拉取最新代码
    def clean_bigtop_git_prj(self, component):
        # todo bigtop 中定义的git组件version 要优化
        ci_conf = self.get_ci_conf()
        version = "3.1"
        bigtop_dl = ci_conf["bigtop"]["dl_dir"]

        if component.strip() in ["ambari", "ambari-infra", "ambari-metrics"]:
            name = f"apache-{component}-{version}.tar.gz"
            file_path = os.path.join(bigtop_dl, name)
            if os.path.exists(file_path):
                os.remove(file_path)

    def get_compile_command(self, component):
        cmd = f". /etc/profile.d/bigtop.sh;./gradlew {component}-clean {component}-pkg"
        if self.conf["stack"] == "ambari":
            cmd += " -PpkgSuffix -PparentDir=/usr/bigtop"
        if "repo" in self.conf and self.conf["repo"]:
            cmd += " repo"
        return cmd

    def compile_component(self, component, working_dir):
        compile_command = self.get_compile_command(component)
        logger.info(f"{component} start compile, compile infos will be  write to {component}.log {working_dir}")
        log_path = os.path.join(LOGS_DIR, f"{component}.log")
        with open(log_path, "w") as log_file:
            process = subprocess.Popen(compile_command, shell=True, stdout=log_file, stderr=subprocess.STDOUT,
                                       cwd=working_dir)
            logger.info(f"compile command is {compile_command}, command submitted, wait for compile finish")
            self.child_pids.append(process.pid)

            # 等待子进程完成
            exit_status = process.wait()

            if exit_status != 0:
                logger.error(f"Failed to compile {component}")
                return False, component

            logger.info(f"Successfully compiled {component}")
            return True, component

    def build(self):
        components = self.conf["components"].split(",") if self.conf["components"] else []
        clean_all = self.conf["clean_all"]
        clean_components = self.conf["clean_components"].split(",") if self.conf["clean_components"] else []
        bigtop_working_dir = self.get_bigtop_working_dir()

        failed_components = []

        if clean_all:
            self.success_components = {}
            self.save_success_components()
            for component in components:
                self.clean_bigtop_git_prj(component)

        if len(clean_components) > 0:
            for component in clean_components:
                self.clean_bigtop_git_prj(component)
                if component in self.success_components:
                    del self.success_components[component]

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.conf["max_workers"]) as executor:
            future_to_component = {}

            if "hadoop" in components and "hadoop" not in self.success_components.keys():
                first_task_future = executor.submit(self.compile_component, "hadoop", bigtop_working_dir)
                # 使用Future.result()来阻塞直到hadoop 编译任务完成，其他任务编译依赖于hadoop
                success, component = first_task_future.result()
                self.clean_after_build(component)
                if success:
                    self.success_components[component] = datetime.now().isoformat()
                    self.save_success_components()
                else:
                    logger.info("build hadoop failed")
                    failed_components.append(component)
                    return

            for component in components:
                if component not in self.success_components.keys() and component.strip() != "hadoop":
                    future = executor.submit(self.compile_component, component, bigtop_working_dir)
                    future_to_component[future] = component

            logger.info(f"future_to_component : {len(future_to_component)} {future_to_component}")

            if len(future_to_component) > 0:
                for future in concurrent.futures.as_completed(list(future_to_component.keys())):
                    try:
                        success, component = future.result()
                        self.clean_after_build(component)
                        if success:
                            logger.info(f"build success {component} {success}")
                            self.success_components[component] = datetime.now().isoformat()
                            self.save_success_components()
                        else:
                            failed_components.append(component)
                            logger.info(f"Error build failed {component}")
                    except Exception as exc:
                        logger.error(f"{component} generated an exception: {exc}")
                        logger.error(traceback.format_exc())
        return failed_components

    def clean_after_build(self, component):
        ci_conf = self.get_ci_conf()
        bigtop_dir = self.get_bigtop_working_dir()
        if len(bigtop_dir) < 2:
            raise Exception(f"clean_after_build: get wrong bigtop_dir {bigtop_dir}")

        # todo  启动的时候映射到了容器里的目录也抽出来单独管理
        buid_dir = os.path.join(bigtop_dir, f"build/{component}")
        output = subprocess.check_output(f"rm -rf {buid_dir}", shell=True)
        # shutil.rmtree(buid_dir, ignore_errors=True)
        logger.info(f"{buid_dir} clean_after_build finished  {output}")

    def config_host_env(self):
        self.set_git_config()
        self.set_yum_repo()
        self.set_maven_conf("/usr/local/maven/conf")
        self.set_web_compile_envirment()

    def load_success_components(self):
        if os.path.exists(SUCCESS_FILE):
            with open(SUCCESS_FILE, 'r') as f:
                res = json.load(f)
                logger.info(f"load_success_components: {res}")
                return res
        else:
            return {}

    def save_success_components(self):
        with open(SUCCESS_FILE, 'w') as f:
            logger.info(f"save_success_components: {self.success_components} ")
            json.dump(self.success_components, f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='build bigdata components.')
    parser.add_argument('--config', type=str, help='Configuration in JSON format')
    args = parser.parse_args()
    config = json.loads(args.config)
    logger.info(f"params config: {config},")

    builder = BigtopBuilder(config)
    failed_components = []
    if "prepare_env" in config:
        builder.config_host_env()
        success = True
    elif "components" in config and len(config["components"]) > 0:
        failed_components = builder.build()
        success = True if len(failed_components) == 0 else False

    if success:
        logger.info("component build success s")
        sys.exit(0)
    else:
        logger.info(f"component build failed , please check the log failed components: {failed_components}")
        sys.exit(1)
