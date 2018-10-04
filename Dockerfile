FROM centos:latest

RUN yum update -y \
    && yum upgrade -y \
    && yum install -y httpd \
    svn

# Clone migrid
RUN cd /root \
    && svn checkout https://svn.code.sf.net/p/migrid/code/trunk migrid-code