import os
import requests
import tarfile
import zipfile
import shutil
from urllib.parse import urlparse
from urllib.request import url2pathname
from python.common.basic_logger import get_logger
import subprocess
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
ExecStart={self.install_dir}/nexus/nexus/bin/nexus start
ExecStop={self.install_dir}/nexus/nexus/bin/nexus stop
User=nexus
Restart=on-abort

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
        nexus_base_url = "localhost:8081"
        max_wait_time = 300
        max_end_time = time.time() + max_wait_time
        nexus_service_ok = False

        nexus_test_url = "{}/service/rest/v1/status/writable".format(nexus_base_url)
        logger.info(nexus_test_url)
        while time.time() <= max_end_time:
            try:
                response = urllib.request.urlopen(nexus_test_url)
                nexus_service_response_code = str(response.getcode())
                logger.info(nexus_service_response_code)
                if nexus_service_response_code == "200":
                    logger.info("nexus 服务已经可用")
                    nexus_service_ok = True
                    break
                else:
                    logger.info("nexus 正在启动中，服务还不可用，等待3秒后重试...")
            except urllib.error.HTTPError as e:
                logger.error('HTTPError = ' + str(e.code))
                continue
            except urllib.error.URLError as e:
                continue
            except http.client.HTTPException as e:
                logger.error('HTTPException')
                continue
            except Exception:
                import traceback
                logger.error('generic exception: ' + traceback.format_exc())
                continue
            time.sleep(5)

        if nexus_service_ok:
            logger.info("nexus 安装启动完成")
            return True
        else:
            logger.error("nexus 安装启动未完成，请先排除问题再重新安装")
            return False


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

    def is_java_installed(self, version):
        command = "java -version"
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
            if 'version "{}'.format(version) in str(output):
                return True
            else:
                return False
        except subprocess.CalledProcessError:
            # java 命令未找到，说明 Java 没有安装
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

