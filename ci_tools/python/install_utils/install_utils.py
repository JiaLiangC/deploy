import os
import requests
import tarfile
import zipfile
import shutil
from urllib.parse import urlparse
from urllib.request import url2pathname
from python.common.basic_logger import get_logger
logger = get_logger()

class Installer:
    def __init__(self, package_name, file_url, install_dir):
        self.package_name = package_name
        self.file_url = file_url
        self.install_dir = install_dir

    def download_package(self):
        if not os.path.exists(self.file_url):
            # todo  增加下载远程包的支持
            logger.info(f"Downloading {self.package_name} package from URL...")
            response = requests.get(self.file_url, stream=True)
            response.raise_for_status()
        else:
            local_path = self.file_url
            if os.path.exists(local_path):
                logger.info(f" local {local_path} file exist")
            else:
                raise FileNotFoundError(f"Local file {local_path} does not exist.")

    def get_local_path(self):
        # todo 下载后的文件位置和文件名和本地保持一致
        parsed_url = urlparse(self.file_url)
        local_path = url2pathname(parsed_url.path)
        return local_path

    def extract_package(self):
        logger.info(f" install_dir {self.install_dir}")
        if os.path.exists(self.install_dir):
            shutil.rmtree(self.install_dir,ignore_errors=True)

        os.makedirs(self.install_dir)
        extension = os.path.splitext(self.file_url)[1]
        file_path = self.get_local_path()
        if extension == ".gz":
            with tarfile.open(file_path, "r:gz") as tar:
                tar.extractall(path=self.install_dir)
        elif extension == ".bz2":
            with tarfile.open(file_path, "r:bz2") as tar:
                tar.extractall(path=self.install_dir)
        elif extension == ".zip":
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(path=self.install_dir)
        else:
            raise ValueError(f"Unsupported file extension: {extension}. Only .tar.gz and .zip are supported.")

    def fetch_and_unpack(self):
        self.download_package()
        self.extract_package()
        logger.info(f"{self.package_name} 安装完成！")


class NexusInstaller(Installer):
    def __init__(self, file_url, install_dir):
        super().__init__("nexus", file_url, install_dir)

    def create_user(self):
        os.system("useradd --system --shell /bin/false nexus")
        os.system(f"chown -R nexus:nexus {self.install_dir}")

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
ExecStart={self.install_dir}/nexus3/bin/nexus start
ExecStop={self.install_dir}/nexus3/bin/nexus stop
User=nexus
Restart=on-abort

[Install]
WantedBy=multi-user.target
""")

    def start_service(self):
        os.system("systemctl daemon-reload")
        os.system("systemctl enable nexus")
        os.system("systemctl start nexus")

    def install(self):
        self.fetch_and_unpack()
        self.create_user()
        self.configure_service()
        self.start_service()
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

    def install(self):
        self.fetch_and_unpack()
        self.set_environment_variables()
        logger.info("JDK 安装完成！")


class AnsibleInstaller(Installer):
    def __init__(self, file_url, install_dir):
        super().__init__("ansible", file_url, install_dir)

    def install(self):
        self.fetch_and_unpack()
        logger.info("ansible 安装完成！")


class PigzInstaller(Installer):
    import subprocess
    def __init__(self, file_url, install_dir):
        super().__init__("pigz", file_url, install_dir)
    def install(self):
        self.fetch_and_unpack()
        install_dir = self.install_dir
        pigz_source_dir = os.path.join(install_dir,"pigz")
        os.chdir(pigz_source_dir)
        # 编译源代码
        result = subprocess.run(['make'], stderr=subprocess.PIPE)
        return_code = result.returncode
        error_message = result.stderr.decode()
        logger.info(f' pig build Return code: {return_code}  Error message: {error_message}')
        # 将可执行文件复制到安装目录
        shutil.copy('pigz', install_dir)
        shutil.copy('unpigz', install_dir)
        os.chdir('../..')
        # 删除源代码压缩包
        os.remove(pigz_source_dir)

