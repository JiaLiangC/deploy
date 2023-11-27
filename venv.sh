#!/bin/bash

# 获取当前脚本所在的目录
prjdir=$(pwd)

# 如果 prjdir/bin/ 目录不存在，创建它
if [[ ! -d "${prjdir}/bin" ]]; then
  echo "Directory ${prjdir}/bin/ does not exist. Creating it..."
  mkdir -p "${prjdir}/bin"
fi

# 解压 portable-ansible.zip 到 prjdir/bin/ 目录
echo "Unzipping portable-ansible.zip to ${prjdir}/bin/..."
if [[ ! -d "${prjdir}/bin/portable-ansible" ]]; then
	unzip -o ${prjdir}/ci_tools/resources/pkgs/portable-ansible.zip -d "${prjdir}/bin"
fi
# 如果软链接 prjdir/bin/ansible-playbook 不存在，创建它
if [[ ! -L "${prjdir}/bin/ansible-playbook" ]]; then
  echo "Symbolic link ${prjdir}/bin/ansible-playbook does not exist. Creating it..."
  ln -s "${prjdir}/bin/portable-ansible" "${prjdir}/bin/ansible-playbook"
fi

# 设置环境变量
echo "Setting environment variables..."
export ANSIBLE_COLLECTIONS_PATHS="${prjdir}"
export PYTHONPATH="${prjdir}/ci_tools:${prjdir}/bin/portable-ansible:${prjdir}/bin/portable-ansible/extras:${PYTHONPATH}"

echo "Done."