# PowerShell Script

# 获取当前脚本所在的目录
$prjdir = Get-Location

# 如果 prjdir\bin\ 目录不存在，创建它
if (-not (Test-Path "${prjdir}\bin")) {
    Write-Host "Directory ${prjdir}\bin\ does not exist. Creating it..."
    New-Item -ItemType Directory -Path "${prjdir}\bin" | Out-Null
}

# 解压 portable-ansible.zip 到 prjdir\bin\ 目录
Write-Host "Unzipping portable-ansible.zip to ${prjdir}\bin\..."
if (-not (Test-Path "${prjdir}\bin\portable-ansible")) {
    Expand-Archive -Path "${prjdir}\ci_tools\resources\pkgs\portable-ansible.zip" -DestinationPath "${prjdir}\bin" -Force
}

# 检查符号链接是否存在
if (Test-Path "${prjdir}\bin\ansible-playbook" -PathType SymbolicLink) {
    Write-Host "Symbolic link ${prjdir}\bin\ansible-playbook exists. Removing it..."
    Remove-Item "${prjdir}\bin\ansible-playbook" -Force
}

# 如果符号链接 prjdir\bin\ansible-playbook 不存在，创建它
if (-not (Test-Path "${prjdir}\bin\ansible-playbook" -PathType SymbolicLink)) {
    Write-Host "Symbolic link ${prjdir}\bin\ansible-playbook does not exist. Creating it..."
    New-Item -ItemType SymbolicLink -Path "${prjdir}\bin\ansible-playbook" -Target "${prjdir}\bin\portable-ansible" | Out-Null
}

# 设置环境变量
Write-Host "Setting environment variables..."
$env:ANSIBLE_COLLECTIONS_PATHS = "${prjdir}\bin\portable-ansible\ansible\collections"
$env:PYTHONPATH = "${prjdir}\ci_tools;${prjdir}\bin\portable-ansible;${prjdir}\bin\portable-ansible\extras;${env:PYTHONPATH}"

Write-Host "Done."
