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

ARG EIS_VERSION
ARG DOCKER_REGISTRY
FROM ${DOCKER_REGISTRY}ia_eisbase:$EIS_VERSION as eisbase
LABEL description="Kapacitor image"

ENV PY_WORK_DIR /EIS
WORKDIR ${PY_WORK_DIR}
ENV HOME ${PY_WORK_DIR}
ENV KAPACITOR_REPO ${PY_WORK_DIR}/go/src/github.com/influxdata/kapacitor
ENV GO_ROOT_BIN ${PY_WORK_DIR}/go/bin

# Adding kapacitor related files and removing python3.6
ARG KAPACITOR_VERSION
RUN mkdir -p ${KAPACITOR_REPO} && \
    git clone https://github.com/influxdata/kapacitor.git ${KAPACITOR_REPO} && \
    cd ${KAPACITOR_REPO} && \
    git checkout -b v${KAPACITOR_VERSION} tags/v${KAPACITOR_VERSION} && \
    python3.6 build.py --clean -o ${GO_ROOT_BIN} && \
    apt-get remove -y python3.6


# Adding Intel distribution python
ENV ACCEPT_INTEL_PYTHON_EULA=yes

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x Miniconda3-latest-Linux-x86_64.sh && \
    ./Miniconda3-latest-Linux-x86_64.sh -b -p ${PY_WORK_DIR}/miniconda

ENV PATH $PATH:${PY_WORK_DIR}/miniconda/bin
ARG INTELPYTHON_VERSION
RUN conda clean --all \
    && conda config --add channels intel \
    && conda install  -y intelpython3_core=$INTELPYTHON_VERSION python=3 \
    && apt-get update \
    && apt-get install -y g++ \
    && apt-get autoremove -y \
    && rm Miniconda3-latest-Linux-x86_64.sh \
    && mv ${PY_WORK_DIR}/miniconda/bin/python3.7 /usr/local/bin \
    && mv ${PY_WORK_DIR}/miniconda/lib/python3.7/ /usr/local/lib/ \
    && cp -a ${PY_WORK_DIR}/miniconda/lib/. /usr/local/lib/

# Installing EIS related libs
RUN git clone https://github.com/kragniz/python-etcd3 && \
    cd python-etcd3 && \
    git checkout -b ${PY_ETCD3_VERSION} ${PY_ETCD3_VERSION} && \
    python3.7 setup.py install && \
    cd .. && \
    rm -rf python-etcd3

FROM ${DOCKER_REGISTRY}ia_common:$EIS_VERSION as common

FROM eisbase

COPY --from=common ${GO_WORK_DIR}/common/libs ${PY_WORK_DIR}/libs
COPY --from=common ${GO_WORK_DIR}/common/util ${PY_WORK_DIR}/util

RUN cd ${PY_WORK_DIR}/libs/ConfigManager/python && \
    python3.7 setup.py.in install && \
    cd ../../../

# Installing required python library
RUN python3.7 -m pip install jsonschema==3.2.0
COPY requirements.txt ./
RUN  python3.7 -m pip install -r requirements.txt

# Adding classifier program
COPY . ./

ENV PYTHONPATH $PYTHONPATH:${KAPACITOR_REPO}/udf/agent/py/
ENV GOCACHE "/tmp"

COPY schema.json .

#Removing build dependencies
RUN apt-get remove -y wget && \
    apt-get remove -y git && \
    apt-get remove curl && \
    rm -rf miniconda requirements.txt

ENTRYPOINT ["python3.7", "./classifier_startup.py"]
