#!/bin/bash

# 定义下载的ZIP文件的地址
ZIP_URL="https://github.com/JiaLiangC/ambari/archive/refs/heads/udh3.zip"
# 定义下载后的ZIP文件名
ZIP_FILE="ambari.zip"
# 定义解压后临时文件夹名称，避免冲突
TEMP_FOLDER="ambari_temp"
# 定义最终要重命名的文件夹名称
FOLDER_NAME="apache-ambari-3.1"
# 定义最终tar.gz的文件名
TAR_GZ_FILE="${FOLDER_NAME}.tar.gz"

# 1. 从a地址下载zip文件
wget $ZIP_URL -O $ZIP_FILE

# 检查ZIP文件是否成功下载
if [ ! -f "$ZIP_FILE" ]; then
    echo "下载ZIP文件失败"
    exit 1
fi

# 2. 解压ZIP文件
unzip $ZIP_FILE -d $TEMP_FOLDER

# 3. 把解压后的文件夹重命名为x
# 注意：解压后如果包含多个文件夹或文件，需要具体情况具体分析
# 这里假设解压后只有一个文件夹
mv $TEMP_FOLDER/* $FOLDER_NAME



# 4. tar压缩该文件夹为tar.gz格式
tar -czvf $TAR_GZ_FILE $FOLDER_NAME

# 清理中间文件
rm -rf $FOLDER_NAME
rm -f $ZIP_FILE
## 清理临时文件夹
rm -rf $TEMP_FOLDER

echo "操作完成，生成的tar.gz文件为: $TAR_GZ_FILE"
