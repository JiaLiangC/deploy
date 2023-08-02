
import os

CONF_DIR =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANSIBLE_PRJ_DIR = os.path.join(CONF_DIR, 'ansible-scripts')
BLUEPRINT_FILES_DIR = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/roles/ambari-blueprint/files/')
CLUSTER_TEMPLATES_DIR = os.path.join(CONF_DIR, "cluster_templates")
PKG_BASE_DIR = os.path.join(CONF_DIR, "pkgs")
PLUGINS_DIR = os.path.join(CONF_DIR, 'plugins')
PLUGINS_FILES_DIR = os.path.join(CONF_DIR, "plugins/files")
