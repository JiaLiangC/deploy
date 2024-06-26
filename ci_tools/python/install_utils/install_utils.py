import os
import requests
import tarfile
import zipfile
import shutil
from urllib.parse import urlparse
from urllib.request import url2pathname
from python.common.basic_logger import get_logger
from python.common.constants import *
import subprocess
import time
import pwd
from python.nexus.nexus_client import NexusClient
from python.utils.os_utils import *

logger = get_logger()


class Installer:
    def __init__(self, package_name, file_url, install_dir):
        self.package_name = package_name
        self.file_url = file_url
        self.install_dir = install_dir
        self.comp_dir = self.get_comp_dir()

    def read_file_contents(self, file_path):
        with open(file_path, 'r') as file:
            contents = file.read()
        return contents

    def create_user(self, user):
        os.system(f"useradd --system --shell /bin/false {user}")
        os.system(f"chown -R {user}:{user} {self.comp_dir}")

    def delete_user_if_exists(self, username):
        kill_user_processes(username)
        try:
            pwd.getpwnam(username)
            # If the above function did not raise an error, the user exists. Delete it.
            run_shell_command(['userdel', '-r', username])
            logger.info(f"User {username} has been deleted.")
        except KeyError:
            # If getpwnam() didn't find the user, it raises a KeyError.
            logger.info(f"User {username} does not exist.")
        except Exception as err:
            logger.error(f"Something went wrong: {err}")

    def download_package(self):
        if not os.path.exists(self.file_url):
            logger.info(f"Downloading {self.package_name} package from URL...")
            response = requests.get(self.file_url, stream=True)
            response.raise_for_status()
        else:
            local_path = self.file_url
            if os.path.exists(local_path):
                logger.info(f" local {local_path} file exist")
            else:
                raise FileNotFoundError(f"Local file {local_path} does not exist.")

    def pigz_decompress(self, tar_file):
        pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        command = f"tar -I {pigz_path} -xf {tar_file} -C {self.comp_dir} --strip-components=1"
        run_shell_command(command, shell=True)

    def get_top_level_dir_name(self, file_path):
        logger.info(f"get_top_level_dir_name {file_path}")
        if not os.path.exists(file_path):
            raise Exception(f"get_top_level_dir_name {file_path} not exist")
        extension = os.path.splitext(file_path)[1]
        if extension == ".gz" or extension == ".bz2":
            with tarfile.open(file_path, "r") as tar:
                return self._get_top_level_dir_name_from_members(tar.getnames())
        elif extension == ".zip":
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                return self._get_top_level_dir_name_from_members(zip_ref.namelist())
        else:
            raise ValueError(f"Unsupported file extension: {extension}. Only .tar.gz, .bz2 and .zip are supported.")

    def _get_top_level_dir_name_from_members(self, members):
        top_level_dirs = {name.split("/", 1)[0] for name in members}
        if len(top_level_dirs) != 1:
            raise ValueError("The archive has more than one top-level directory or no top-level directory.")
        return next(iter(top_level_dirs))

    def get_local_path(self):
        parsed_url = urlparse(self.file_url)
        local_path = url2pathname(parsed_url.path)
        return local_path

    def get_comp_dir(self):
        fdir = os.path.join(self.install_dir, self.package_name)
        logger.info(f"get_comp_dir {fdir}")
        return fdir

    def extract_package(self):
        logger.info(f"will install into {self.comp_dir}")
        if os.path.exists(self.comp_dir):
            logger.info(f"delete existing dir {self.comp_dir}")
            shutil.rmtree(self.comp_dir)
        os.makedirs(self.comp_dir)

        extension = os.path.splitext(self.file_url)[1]
        file_path = self.get_local_path()
        if extension == ".gz":
            if os.path.exists(os.path.join(PRJ_BIN_DIR, "pigz")):
                logger.info(f"{os.path.join(PRJ_BIN_DIR, 'pigz')} exist, use pigz in decompress")
                self.pigz_decompress(file_path)
            else:
                run_shell_command(['tar', '-xzf', file_path, '-C', self.comp_dir, '--strip-components=1'])
        elif extension == ".bz2":
            # Use tar command to extract .bz2 file
            run_shell_command(['tar', '-xjf', file_path, '-C', self.comp_dir, '--strip-components=1'])
        elif extension == ".zip":
            run_shell_command(['unzip', '-d', self.install_dir, file_path])
        else:
            raise ValueError(f"Unsupported file extension: {extension}. Only .tar.gz, .tar.bz2 and .zip are supported.")

    def fetch_and_unpack(self):
        self.download_package()
        self.extract_package()
        logger.info(f"{self.package_name} 安装完成！")


class NexusInstaller(Installer):
    def __init__(self, file_url, install_dir, password):
        self.password = password
        super().__init__("nexus3", file_url, install_dir)

    def configure_service(self):
        nexus_service_path = "/etc/systemd/system/nexus.service"
        with open(nexus_service_path, "w") as file:
            file.write(f"""
[Unit]
Description=Nexus service
After=network.target

[Service]
Type=forking
LimitNOFILE=65536
ExecStart={self.comp_dir}/nexus-3/bin/nexus start
ExecStop={self.comp_dir}/nexus-3/bin/nexus stop
User=root

[Install]
WantedBy=multi-user.target
""")

    def start_service(self):
        os.system("systemctl daemon-reload")
        os.system("systemctl enable nexus")
        os.system("systemctl start nexus")
        self.test_nexus_service()

    def test_nexus_service(self):
        # 300s
        nexus_base_url = "http://localhost:8081"
        max_wait_time = 600
        max_end_time = time.time() + max_wait_time
        nexus_service_ok = False

        nexus_test_url = f"{nexus_base_url}/service/rest/v1/status/writable"
        logger.info(nexus_test_url)
        while time.time() <= max_end_time:
            try:
                response = requests.get(nexus_test_url)
                response.raise_for_status()  # 如果响应的状态码不是 200，会抛出 HTTPError 异常
                logger.info(str(response.status_code))
                if response.status_code == 200:
                    logger.info("nexus 服务已经可用")
                    nexus_service_ok = True
                    break
                else:
                    logger.info("nexus 正在启动中，服务还不可用，等待3秒后重试...")
                    time.sleep(3)
            except requests.exceptions.HTTPError as errh:
                logger.error(f"HTTPError: {errh}")
            except requests.exceptions.ConnectionError as errc:
                logger.error(f"Error Connecting: {errc}")
            except requests.exceptions.Timeout as errt:
                logger.error(f"Timeout Error: {errt}")
            except requests.exceptions.RequestException as err:
                logger.error(f"Something went wrong: {err}")
            time.sleep(5)

        if nexus_service_ok:
            logger.info("nexus 安装启动完成")
            return True
        else:
            logger.error("nexus 安装启动未完成，请先排除问题再重新安装")
            return False

    def generate_properties(self):
        user = "nexus"
        group = "nexus"
        nexus_etc_dir = os.path.join(self.comp_dir, "sonatype-work/nexus3/etc")
        if not os.path.exists(nexus_etc_dir):
            os.makedirs(nexus_etc_dir, exist_ok=True)
        content = "nexus.scripts.allowCreation=true"
        file_path = os.path.join(nexus_etc_dir, "nexus.properties")
        with open(file_path, 'w') as f:
            f.write(content)

        run_shell_command(["chown", "-R", f"{user}:{group}", nexus_etc_dir])

    def set_pwd_first_launch(self):
        pwd_file = os.path.join(self.comp_dir, "sonatype-work/nexus3/admin.password")
        if not os.path.exists(pwd_file):
            logger.info("set_pwd_first_launch not pwd file exist return")
            return
        initial_password = self.read_file_contents(pwd_file).strip()
        nexus_client = NexusClient("localhost", "admin", initial_password)
        logger.info(f"change pwd from initial password is{initial_password}to {self.password}")
        nexus_client.set_pwd_first_launch(initial_password, self.password)
        if os.path.exists(pwd_file):
            os.remove(pwd_file)
            logger.info(f"nexus initialize fineshed delete pwd file")

    def fix_nexus_pref(self):
        data_dir = os.path.join(self.comp_dir, "sonatype-work/nexus3/javaprefs")
        prefs = f"-Djava.util.prefs.userRoot={data_dir}"
        file_path = f"{self.comp_dir}/nexus-3/bin/nexus.vmoptions"

        with open(file_path, 'a') as file:
            file.write('\n' + prefs)

    def install(self):
        kill_nexus_process()
        self.fetch_and_unpack()
        self.delete_user_if_exists("nexus")
        self.create_user("nexus")
        self.fix_nexus_pref()
        self.configure_service()
        self.generate_properties()
        self.start_service()
        self.set_pwd_first_launch()
        logger.info("Nexus 安装完成！")


class JDKInstaller(Installer):
    def __init__(self, file_url, install_dir):
        super().__init__("jdk", file_url, install_dir)

    def set_environment_variables(self):
        with open("/etc/profile.d/jdk.sh", "w") as file:
            file.write(f"""
export JAVA_HOME={self.install_dir}/jdk
export PATH=$JAVA_HOME/bin:$PATH
""")

    def is_java_installed(self, version):
        command = "java -version"
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
            if f'version "{version}' in str(output):
                return True
            else:
                return False
        except subprocess.CalledProcessError:
            return False

    def install(self):
        if self.is_java_installed("1.8.0"):
            logger.info("java already installed")
            return
        self.fetch_and_unpack()
        self.set_environment_variables()
        logger.info("JDK 安装完成！")


class AnsibleInstaller(Installer):
    def __init__(self, file_url, install_dir):
        super().__init__("ansible", file_url, install_dir)

    def install(self):
        self.fetch_and_unpack()


class PigzInstaller(Installer):
    import subprocess
    def __init__(self, file_url, install_dir):
        super().__init__("pigz_source", file_url, install_dir)

    def install(self):
        logger.info("start pigz install")
        self.fetch_and_unpack()
        pigz_source_dir = self.comp_dir
        os.chdir(pigz_source_dir)
        # 编译源代码
        logger.info(f"start pigz compile {pigz_source_dir}")
        run_shell_command(['make'])
        pigz_source_file = os.path.join(pigz_source_dir, "pigz")
        pigz_dest_file = os.path.join(self.install_dir, "pigz")
        logger.info(f"{pigz_source_dir}   s: {pigz_source_file} d: {pigz_dest_file} ")
        logger.info(f"start pigz install,will copy {pigz_source_file} to {pigz_dest_file}")
        copy_file(pigz_source_file, pigz_dest_file)
        os.chmod(pigz_dest_file, 0o777)
        os.chdir('../..')
        shutil.rmtree(pigz_source_dir)
