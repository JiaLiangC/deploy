import requests
from python.common.basic_logger import logger
import os
import glob

bigdata_packages_base_dir = "sdp_3.1/packages"
repo_type = "yum"

class NexusClient:
    def __init__(self, server_host, username, password):
        self.server_host = server_host
        self.auth = (username, password)

    def get_nexus_url(self):
        return f"http://{self.server_host}"

    def get_bigdata_component_url(self, component_dir_name):
        base_url = f"{self.get_nexus_url()}/repository/{repo_type}/{bigdata_packages_base_dir}/{component_dir_name}"
        return base_url

    def component_upload(self, file_path, component_dir_name):
        base_url = f"{self.get_nexus_url()}/repository/{repo_type}/{bigdata_packages_base_dir}/{component_dir_name}/{os.path.basename(file_path)}"

        with open(file_path, 'rb') as f:
            response = requests.put(base_url, data=f, auth=self.auth)
            # 打印状态码
            logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
            logger.info(f"Upload completed for {file_path}")

    # 假定所有的组件都在预定的目录下存储
    def component_delete(self, component_name):
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }

        data = {
            'action': 'coreui_Component',
            'method': 'deleteFolder',
            'data': [f'{bigdata_packages_base_dir}/{component_name}', repo_type],
            'type': 'rpc',
            'tid': 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

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
            "data": [{"attributes": {f"{repo_type}": {"repodataDepth": 3, "deployPolicy": "STRICT"},
                                     "storage": {"blobStoreName": "default", "strictContentTypeValidation": True,
                                                 "writePolicy": "ALLOW_ONCE"},
                                     "component": {"proprietaryComponents": False}, "cleanup": {"policyName": []}},
                      "name": repo_name, "format": "", "type": "", "url": "", "online": True, "recipe": recipe}],
            "type": "rpc", "tid": 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def repo_create(self, repo_name):
        repo_list = self.get_repos()
        result = filter(lambda d: d['name'] == repo_name, repo_list)
        if len(result) > 0:
            self.repo_remove(repo_name)
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
        logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

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

    def batch_upload(self, source_dir, component_dir_name):
        self.component_delete(component_dir_name)
        for filepath in glob.glob(os.path.join(source_dir, "**", "*.rpm"), recursive=True):
            logger.info(f"finding {filepath}")
            if not filepath.endswith("src.rpm"):
                self.component_upload(filepath, component_dir_name)

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
        logger.info(f"Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")


if __name__ == '__main__':
    repo = "http://172.27.8.25:8081/repository/yum/sdp_3.1/packages/test"
    nexus_client = NexusClient("172.27.8.25", "admin", "admin123")
    # nexus_client.component_upload("/home/jialiang/sdp/prjs/tmp/ambari-agent-3.0.0.0-SNAPSHOT.x86_64.rpm", "test")
    # nexus_client.component_delete("test")
    #nexus_client.repo_create("test1")