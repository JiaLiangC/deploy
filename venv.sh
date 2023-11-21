#!/bin/bash

install_dir=/opt/bigdata_tools_venv
mkdir -p ${install_dir}
cd ${install_dir}

# Check if virtual environment does not exist
if [ ! -d "${install_dir}/venv" ]; then
    # Create virtual environment
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
    pip config set install.trusted-host mirrors.aliyun.com
    python3 -m pip install virtualenv
    python3 -m virtualenv -p /usr/bin/python3 venv

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