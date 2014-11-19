change-root-passwd
==================                                                                               
                                                              
    有时从网上下载的虚拟机镜像，没有root密码，必须通过秘钥登录，然后秘钥又需要麻烦的注入到里面去。想用，却无法登录，很头痛。
    该脚本用于修改虚拟机镜像的roo密码，使用时，changerootpasswd.py\changerootpasswd.sh两个文件需要放在同一目录下面，使用前请安装python-guestfs及相关包。ubuntu系统执行：
sudo apt-get install python-guestfs                                             
    centos系统请执行：                                                          
sudo yum install python-libguestfs                                              
    执行：                                                                      
sudo bash changerootpasswd.sh ubuntu.qcow2 123456                               
    即可将ubuntu.qcow2镜像的root登录密码设定为123456.该脚本可支持多种镜像格式，经过验证的有raw\qcow2。
