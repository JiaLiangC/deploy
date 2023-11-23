import requests
from python.common.basic_logger import get_logger
import os
import glob
import platform
from python.common.constants import *

logger = get_logger()


# architecture


class NexusClient:
    def __init__(self, server_host, username, password):
        self.server_host = server_host
        self.server_por = "8081"
        self.auth = (username, password)

    def get_nexus_url(self):
        return f"http://{self.server_host}:{self.server_por}"

    # repository/centos/7/os/x86_64/Packages/Cython-0.19-5.el7.x86_64.rpm

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

    def get_os_packages_relative_dir(self):
        os_type = self.get_os_type()
        os_architecture = platform.machine()
        os_version = self.get_os_version()
        relative_path = f"{os_type}/{os_version}/os/{os_architecture}/Packages"
        return relative_path

    def get_os_packages_url(self):
        import platform
        os_type = self.get_os_type()
        os_architecture = platform.machine()
        os_version = self.get_os_version()
        if os_architecture not in SUPPORTED_ARCHS:
            raise Exception(f"os architecture {os_architecture} not supported. only support: {SUPPORTED_ARCHS} ")
        base_url = f"{self.get_nexus_url()}/repository/{os_type}/{os_version}/os/{os_architecture}/Packages"
        logger.info(f"nexus client get_os_packages_url: {base_url}")
        return base_url

    def get_bigdata_component_url(self, component_dir_name):
        repo_name = "yum"
        relative_dir = "udh3/packages"
        base_url = f"{self.get_nexus_url()}/repository/{repo_name}/{relative_dir}/{component_dir_name}"
        return base_url

    def upload(self, file_path, base_url):
        # self.get_bigdata_component_url(component_dir_name)
        # base_url = f"{self.get_nexus_url()}/repository/{repo_type}/{bigdata_packages_base_dir}/{component_dir_name}/{os.path.basename(file_path)}"
        with open(file_path, 'rb') as f:
            response = requests.put(base_url, data=f, auth=self.auth)
            # 打印状态码
            logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
            logger.info(f"Upload completed for {file_path}")

    def upload_os_pkgs(self, file_path):
        base_url = self.get_os_packages_url()
        base_url = f"{base_url}/{os.path.basename(file_path)}"
        self.upload(file_path, base_url)

    def upload_bigdata_pkgs(self, file_path, component_dir_name):
        base_url = self.get_bigdata_component_url(component_dir_name)
        base_url = f"{base_url}/{os.path.basename(file_path)}"
        self.upload(file_path, base_url)

    def batch_upload_os_pkgs(self, source_dir):
        for filepath in glob.glob(os.path.join(source_dir, "**", "*.rpm"), recursive=True):
            logger.info(f"finding {filepath}")
            if not filepath.endswith("src.rpm"):
                self.upload_os_pkgs(filepath)

    def batch_upload_bigdata_pkgs(self, source_dir, component_dir_name):
        repo_name = "yum"
        component_relative_path = f"udh3/packages/{component_dir_name}"
        self.delete_folder(repo_name, component_relative_path)
        for filepath in glob.glob(os.path.join(source_dir, "**", "*.rpm"), recursive=True):
            logger.info(f"finding {filepath}")
            if not filepath.endswith("src.rpm"):
                self.upload_bigdata_pkgs(filepath, component_dir_name)

    # 假定所有的组件都在预定的目录下存储
    def delete_folder(self, repo_name, relative_path):
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }

        data = {
            'action': 'coreui_Component',
            'method': 'deleteFolder',
            'data': [f'{relative_path}', repo_name],
            'type': 'rpc',
            'tid': 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(
            f"nexus delete_folder url:{url} params:{repo_name} {relative_path} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def do_repo_create(self, repo_name):
        recipe = "yum-hosted"
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            "action": "coreui_Repository",
            "method": "create",
            "data": [{"attributes": {f"{repo_name}": {"repodataDepth": 3, "deployPolicy": "STRICT"},
                                     "storage": {"blobStoreName": "default", "strictContentTypeValidation": True,
                                                 "writePolicy": "ALLOW_ONCE"},
                                     "component": {"proprietaryComponents": False}, "cleanup": {"policyName": []}},
                      "name": repo_name, "format": "", "type": "", "url": "", "online": True, "recipe": recipe}],
            "type": "rpc", "tid": 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(
            f"do_repo_create url:{url} repo_name:{repo_name} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def repo_create(self, repo_name, remove_old=False):
        repo_list = self.get_repos()
        result = list(filter(lambda d: d['name'] == repo_name, repo_list))
        logger.info(f"repo_create check  {repo_name} whether exist, result: {result}")
        if len(result) > 0:
            if remove_old:
                self.repo_remove(repo_name)
        else:
            logger.info(f"do_repo_create {repo_name}")
            self.do_repo_create(repo_name)

    def repo_remove(self, repo_name):
        recipe = "yum-hosted"
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }
        data = {"action": "coreui_Repository", "method": "remove", "data": [repo_name], "type": "rpc", "tid": 60}

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(f" url:{url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def get_repos(self):
        url = f"{self.get_nexus_url()}/service/extdirect"
        data = {"action": "coreui_Repository", "method": "read", "data": None, "type": "rpc", "tid": 44}
        headers = {
            'Content-Type': 'application/json',
        }
        response = requests.get(url, headers=headers, json=data, auth=self.auth)

        if response.status_code == 200:
            response_data = response.json()  # 获取响应体的 JSON 格式内容
            repo_list = response_data["result"]["data"]
            return repo_list
        else:
            logger.error(
                f"request faild, Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
            return []

    def change_password(self, new_pwd):
        url = f"{self.get_nexus_url()}/service/rest/v1/security/users/admin/change-password"
        # 发送 PUT 请求
        headers = {
            'Content-Type': 'text/plain',
        }
        response = requests.put(
            url,
            auth=self.auth,
            headers=headers,
            data=new_pwd
        )
        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def set_pwd_first_launch(self, initila_pwd, new_pwd):
        url = f"{self.get_nexus_url()}/service/rest/internal/ui/onboarding/change-admin-password"
        response = requests.put(
            url,
            auth=("admin", initila_pwd),
            data=new_pwd
        )
        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
        headers = {
            'Content-Type': 'application/json',
        }
        url = f"{self.get_nexus_url()}/service/extdirect"
        data = {"action": "coreui_AnonymousSettings", "method": "update",
                "data": [{"enabled": True, "userId": "anonymous", "realmName": "NexusAuthorizingRealm"}], "type": "rpc",
                "tid": 7}
        response = requests.post(url, headers=headers, json=data, auth=("admin", initila_pwd))
        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")


if __name__ == '__main__':
    repo = "http://172.27.8.25:8081/repository/yum/sdp_3.1/packages/test"
    nexus_client = NexusClient("172.27.8.25", "admin", "admin123")
    # nexus_client.component_upload("/home/jialiang/sdp/prjs/tmp/ambari-agent-3.0.0.0-SNAPSHOT.x86_64.rpm", "test")
    # nexus_client.component_delete("test")
    # nexus_client.repo_create("test1")
