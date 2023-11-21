#!/bin/bash

install_dir="${PYTHON_VENV_INSTALL_DIR}"
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
    pip3 install requests xml2dict ansible

    # Deactivate the virtual environment
    deactivate

    # Archive the venv directory
    tar zcvf venv.tar.gz venv
fi

# Activate the virtual environment
source ${install_dir}/venv/bin/activate