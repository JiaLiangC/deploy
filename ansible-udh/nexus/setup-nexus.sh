#!/usr/bin/env bash

#1.  创建$DATA_DIR目录
if [ ! -d $DATA_DIR ]; then
  mkdir $DATA_DIR
fi

#2.  Install pigz util to speed up uncompress
install_local_rpms pigz

#3.  Display information message
display_and_log "即将开始安装nexus，该过程预计等待时间小于5分钟"

#4.  解压nexus
if [[ -d "${DATA_DIR}/nexus" ]]; then
  display_and_log "${DATA_DIR}/nexus目录已经存在，请先删除" "error"
  exit 1
fi
  
nexus_package_name="nexus.${OS_RELEASE_NAME}.${CPU_ARCH}.tar.gz"
if [[ -e "${nexus_package_name}" ]]; then
  display_and_log "解压 ${nexus_package_name}  软件包到 $DATA_DIR 目录"
  time tar -I pigz -xf ${nexus_package_name} -C $DATA_DIR
else
  display_and_log "请将 ${nexs_package_name} 放置到zeta-nexus目录下" "error"
  exit 1
fi

#5.  解压jdk
jdk_package_name="${DATA_DIR}/nexus/jdk.tar.gz"
if [ -e "${jdk_package_name}" ]; then
  display_and_log "解压 ${jdk_package_name}"
  time tar -I pigz -xf ${jdk_package_name} -C /usr/local/
fi

#6.  setup nexus3.service
display_and_log "生成nexus3.service"
cp -rp nexus3.service.template nexus3.service
sed -i "s#DATA_DIR#${DATA_DIR}#" nexus3.service

display_and_log "将nexus3.service拷贝到 /usr/lib/systemd/system 目录下"
cp -rp nexus3.service /usr/lib/systemd/system
systemctl enable nexus3

display_and_log "nexus启动中..."
systemctl start nexus3

#7.  setup environment variables
#7.1 设置超时时间为300秒，300秒后nexus仍然不可用，则报错
MAX_WAIT_TIME="5 minute"
MAX_END_TIME=$(date -ud "${MAX_WAIT_TIME}" +%s)

#7.2 nexus服务不可用时，http_code状态码为000
NEXUS_SERVICE_RESPONSE_CODE="000"
NEXUS_SERVICE_OK=1

#7.3 通过nexus的/service/rest/v1/status/writable接口判断nexus服务是否可用
while [[ $(date -u +%s) -le ${MAX_END_TIME} ]]; do
  NEXUS_SERVICE_RESPONSE_CODE=$(curl --write-out %{http_code} --silent http://localhost:8081/service/rest/v1/status/writable)
  if [ "${NEXUS_SERVICE_RESPONSE_CODE}" == "200" ]; then
    display_and_log "nexus服务已经可用"
    NEXUS_SERVICE_OK=0
    break
  else
    display_and_log "nexus正在启动中，服务还不可用，等待3秒后重试。。。" "warn"
    sleep 3
  fi
done

if [ "${NEXUS_SERVICE_OK}" == "0" ]; then
  display_and_log "nexus安装启动完成"
else
  display_and_log "nexus安装启动未完成，请先排除问题再重新安装" "error"
fi

#8.  installation finish, and return the result
exit ${NEXUS_SERVICE_OK}
