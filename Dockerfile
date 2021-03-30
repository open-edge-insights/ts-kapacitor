# Copyright (c) 2020 Intel Corporation.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Dockerfile for Point Data Analytics

ARG EII_VERSION
ARG DOCKER_REGISTRY
ARG UBUNTU_IMAGE_VERSION
FROM ubuntu:$UBUNTU_IMAGE_VERSION as base
LABEL description="Kapacitor image"

FROM ${DOCKER_REGISTRY}ia_common:$EII_VERSION as common
FROM base
ARG HOST_TIME_ZONE
ENV GO_WORK_DIR /EII/go/src/IEdgeInsights
ENV GOPATH="/EII/go"
ENV PATH ${PATH}:/usr/local/go/bin:${GOPATH}/bin:/opt/conda/bin

WORKDIR ${GO_WORK_DIR}
# Installing build related packages
RUN apt-get update && apt-get install -y wget git g++

#Installing Go and dep package manager tool for Go
ARG GO_VERSION
RUN apt-get update && \
    wget https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz

ARG DEBIAN_FRONTEND=noninteractive
# Setting timezone inside the container
RUN echo "$HOST_TIME_ZONE" >/etc/timezone && \
    cat /etc/timezone && \
    apt-get install -y tzdata && \ 
    ln -sf /usr/share/zoneinfo/${HOST_TIME_ZONE} /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

ENV GLOG_GO_PATH ${GOPATH}/src/github.com/golang/glog
ENV GLOG_VER 23def4e6c14b4da8ac2ed8007337bc5eb5007998
RUN mkdir -p ${GLOG_GO_PATH} && \
    git clone https://github.com/golang/glog ${GLOG_GO_PATH} && \
    cd ${GLOG_GO_PATH} && \
    git checkout -b ${GLOG_VER} ${GLOG_VER}


ENV PY_WORK_DIR /EII
WORKDIR ${PY_WORK_DIR}
ENV HOME ${PY_WORK_DIR}
ENV KAPACITOR_REPO ${PY_WORK_DIR}/go/src/github.com/influxdata/kapacitor
ENV GO_ROOT_BIN ${PY_WORK_DIR}/go/bin

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x Miniconda3-latest-Linux-x86_64.sh && \
    ./Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh

ARG INTELPYTHON_VERSION
RUN conda update conda -y && \
    conda config --add channels intel && \
    conda create -y -n idp intelpython3_core=${INTELPYTHON_VERSION} python=3.7 && \
    conda install -y -n idp daal4py

# Installing required python library
COPY requirements.txt ./
RUN /bin/bash -c "source activate idp && \
    python3.7 -m pip install -r requirements.txt"

# Installing Kapacitor from source
ARG KAPACITOR_VERSION
RUN mkdir -p ${KAPACITOR_REPO} && \
    git clone https://github.com/influxdata/kapacitor.git ${KAPACITOR_REPO} && \
    /bin/bash -c "source activate idp && \
    cd ${KAPACITOR_REPO} && \
    git checkout -b v${KAPACITOR_VERSION} tags/v${KAPACITOR_VERSION} && \
    python3.7 build.py --clean -o ${GO_ROOT_BIN}"

COPY --from=common ${GO_WORK_DIR}/common/libs ${PY_WORK_DIR}/libs
COPY --from=common ${GO_WORK_DIR}/common/util ${PY_WORK_DIR}/util
COPY --from=common /usr/local/lib /usr/local/lib
COPY --from=common /usr/local/include /usr/local/include

RUN cd ${PY_WORK_DIR}/libs/ConfigMgr/python && \
    /bin/bash -c "source activate idp && \
    python3.7 setup.py install && \
    cd ../../../"

# Adding classifier program
COPY . ./
RUN chmod +x ./classifier_startup.sh
ENV PYTHONPATH $PYTHONPATH:${KAPACITOR_REPO}/udf/agent/py/:/opt/conda/lib/python3.7/
ENV GOCACHE "/tmp"
ENV LD_LIBRARY_PATH $LD_LIBRARY_PATH:/usr/local/lib/:/opt/conda/lib/libfabric/
RUN echo "source activate idp" >> /etc/bash.bashrc
#Removing build dependencies
RUN apt-get remove -y --auto-remove --purge curl \
                                            git \
                                            libmagic1 \
                                            libcurl3-gnutls \
                                            wget && \
    rm -rf requirements.txt

HEALTHCHECK NONE

ENTRYPOINT ["./classifier_startup.sh"]
