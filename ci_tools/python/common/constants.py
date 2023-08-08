
import os

PRJDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../')
CONF_DIR = os.path.join(PRJDIR, 'conf')
ANSIBLE_PRJ_DIR = os.path.join(PRJDIR, 'deploy/ansible-scripts')
BLUEPRINT_FILES_DIR = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/roles/ambari-blueprint/files/')
CLUSTER_TEMPLATES_DIR = os.path.join(PRJDIR, "ci_tools/resources/cluster_templates")
PKG_BASE_DIR = os.path.join(PRJDIR, "files/pkgs")
PLUGINS_DIR = os.path.join(PRJDIR, 'ci_tools/python/plugins')
PLUGINS_FILES_DIR = os.path.join(PRJDIR, "ci_tools/resources/plugin_files")
OUTPUT_DIR = os.path.join(PRJDIR, "output/")
LOGS_DIR = os.path.join(PRJDIR, 'logs')
PIP_CONF_FILE = os.path.join(PRJDIR, 'ci_tools/python/bigtop_compile/templates/pip_conf/pip.conf')
PORTABLE_ANSIBLE_PATH = os.path.join(PRJDIR, "ci_tools/resources/pkgs/portable-ansible-py3.tar.bz2")
CI_TOOLS_MODULE_PATH = os.path.join(PRJDIR, "ci_tools/python")
CI_CONF_FILE = os.path.join(CONF_DIR, "ci_conf.yml")
CI_CONF_FILE_TEMPLATE = os.path.join(CONF_DIR, "ci_conf.yml.template")