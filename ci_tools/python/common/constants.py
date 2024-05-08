import os

PRJDIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../'))
PRJ_BIN_DIR = os.path.join(PRJDIR, 'bin')
CONF_DIR = os.path.join(PRJDIR, 'conf')

CONF_NAME = 'conf.yml'
BASE_CONF_NAME = 'base_conf.yml'
HOSTS_CONF_NAME = 'hosts_info.yml'
CI_CONF_NAME = 'ci_conf.yml'
GET_CONF_TPL_NAME = lambda x: f'{x}.template'

ANSIBLE_PRJ_DIR = os.path.join(PRJDIR, 'deploy/ansible-scripts')
BUILD_SCRIPT_RELATIVE_PATH = 'ci_tools/python/build/bigtop_utils.py'
BUILD_SCRIPT = os.path.join(PRJDIR, BUILD_SCRIPT_RELATIVE_PATH)
BLUEPRINT_FILES_DIR = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/roles/ambari-blueprint/files/')
CLUSTER_TEMPLATES_DIR = os.path.join(PRJDIR, "ci_tools/resources/cluster_templates")
PLUGINS_DIR = os.path.join(PRJDIR, 'ci_tools/python/plugins')
PLUGINS_FILES_DIR = os.path.join(PRJDIR, "ci_tools/resources/plugin_files")
OUTPUT_DIR = os.path.join(PRJDIR, "output/")
LOGS_DIR = os.path.join(PRJDIR, 'logs')
PIP_CONF_FILE = os.path.join(PRJDIR, 'ci_tools/python/build/templates/pip_conf/pip.conf')
PKG_RELATIVE_PATH = "ci_tools/resources/pkgs/"
TAR_FILE_PATH = os.path.join(PRJDIR, PKG_RELATIVE_PATH)
UDH_RPMS_RELATIVE_PATH = "ci_tools/resources/pkgs/udh-packages.tar.gz"
UDH_RPMS_PATH = os.path.join(PRJDIR, UDH_RPMS_RELATIVE_PATH)
PIGZ_SOURC_CODE_PATH = os.path.join(PRJDIR, "ci_tools/resources/pkgs/pigz-source.tar.gz")
CI_TOOLS_MODULE_PATH = os.path.join(PRJDIR, "ci_tools/python")
CI_CONF_FILE = os.path.join(CONF_DIR, "ci_conf.yml")
CI_CONF_FILE_TEMPLATE = os.path.join(CONF_DIR, "ci_conf.yml.template")
REPO_FILES_DIR = os.path.join(PRJDIR, "ci_tools/resources/repo_info")
SUPPORTED_ARCHS = ["x86_64", "aarch64", "c86_64"]
SUPPORTED_OS = ["centos", "kylin", "openeuler"]
GROOVY_FILE = os.path.join(PRJDIR, "ci_tools/python/install_utils/groovy/initialize.groovy")
NEXUS_TAR_RELATIVE_PATH = "ci_tools/resources/pkgs/nexus3.tar.gz"
RELEASE_NEXUS_TAR_FILE = os.path.join(PRJDIR, NEXUS_TAR_RELATIVE_PATH)
JDK_TAR_RELATIVE_PATH = "ci_tools/resources/pkgs/jdk.tar.gz"
RELEASE_JDK_TAR_FILE = os.path.join(PRJDIR, JDK_TAR_RELATIVE_PATH)
UDH_NEXUS_REPO_PATH = "udh3"
UDH_NEXUS_REPO_PACKAGES_PATH = f"{UDH_NEXUS_REPO_PATH}/Packages"
UDH_NEXUS_REPO_NAME = "yum"
HTTPD_TPL_FILE = os.path.join(PRJDIR, "ci_tools/resources/templates/httpd.conf.tpl")
HTTPD_CONF_FILE = "/etc/httpd/conf/httpd.conf"
APACHE2_TPL_FILE = os.path.join(PRJDIR, "ci_tools/resources/templates/apache2.conf.tpl")
APACHE2_CONF_FILE = "/etc/apache2/sites-enabled/apache2.conf"

DEB_REPO_BASE_DIR = "/var/repos/apt"
DEB_DISTRIBUTION = "ubuntu"
DEB_CODENAME = "focal"

ALL_COMPONENTS = ["hadoop", "spark", "hive", "hbase", "zookeeper", "kafka", "flink", "ranger", "kyuubi", "alluxio",
                  "knox", "celeborn", "tez", "ambari","trino",  # "dinky",
                  "ambari-infra", "ambari-metrics", "bigtop-select", "bigtop-jsvc", "bigtop-groovy", "bigtop-utils",
                  "bigtop-ambari-mpack"]

DOCKER_IMAGE_MAP = {"centos_7_x86_64": "bigtop/slaves:trunk-centos-7", "centos_8_x86_64": "bigtop/slaves:trunk-rockylinux-8", "centos_8_aarch64": "bigtop/slaves:3.2.1-rockylinux-8-aarch64"}