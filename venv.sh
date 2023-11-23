#!/bin/bash

install_dir=/opt/bigdata_tools_venv
mkdir -p ${install_dir}

# 配置pip源
if [ ! -d "$HOME/.config/pip" ]; then
    mkdir -p "$HOME/.config/pip"
fi

# 将内容写入 pip.conf 文件
cat << EOF > $HOME/.config/pip/pip.conf
[global]
index-url = https://mirrors.aliyun.com/pypi/simple

[install]
trusted-host = mirrors.aliyun.com
EOF

# Check if virtual environment does not exist
if [ ! -d "${install_dir}/venv" ]; then
	if ! command -v python3 > /dev/null; then
        echo "python3 未找到，正在进行安装..."
        sudo yum install -y python3
    else
        echo "python3 已存在."
    fi
    # Create virtual environment
    python3 -m pip install virtualenv

    (cd ${install_dir} && python3 -m virtualenv -p /usr/bin/python3 venv)

    # Activate the virtual environment
    source ${install_dir}/venv/bin/activate

    # Install Python packages
    pip3 install requests xmltodict ansible docker

    # Deactivate the virtual environment
    deactivate

    # Archive the venv directory
    tar zcvf venv.tar.gz venv
fi

# Activate the virtual environment
source ${install_dir}/venv/bin/activate
