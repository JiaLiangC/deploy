#file name:  site_customize.py
import sys
sys.setdefaultencoding('utf-8')

#由于有的系统的默认python encoding 是ascii,导致很多ambari python 脚本无法正常运行，可以使用如下命令测试
# python -c "import sys; print(sys.getdefaultencoding())"
# ascii
# 发现python这里默认是asii

# 当然可以专门改报错的文件在文件头加入
# import sys
# reload(sys)
# sys.setdefaultencoding('utf-8')

# 但是要改很多ambari 的文件，只要涉及中文的文件读写的py 脚本都要加,侵入性大,改动大,不合适

# 因此需要设置一下全局生效,目前找到最好的办法是创建一个文件指定编码让python 自动加载
# site_customize.py
# 这个文件丢在/usr/lib/python2.7/site-packages/会被自动加载

# vi /usr/lib/python2.7/site-packages/site_customize.py
# #file name:  site_customize.py
# import sys
# sys.setdefaultencoding('utf-8')