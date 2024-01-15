from python.common.constants import *

from .base_configuration import *


class AdvancedConfiguration(BaseConfiguration):
    def __init__(self, name=CONF_NAME):
        super().__init__(name)

    def is_ambari_repo_configured(self):
        repos = self.get('repos', [])
        if len(repos) > 0:
            for repo_item in repos:
                if "ambari_repo" == repo_item["name"]:
                    return True
        return False
