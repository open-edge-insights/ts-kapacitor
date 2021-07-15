# Copyright (c) 2021 Intel Corporation.

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
ARG ARTIFACTS="/artifacts"
ARG UBUNTU_IMAGE_VERSION
FROM ia_common:$EII_VERSION as common
FROM ubuntu:$UBUNTU_IMAGE_VERSION as base

FROM base as builder
ARG HOST_TIME_ZONE
ENV GOPATH="/go"
ENV PATH ${PATH}:/usr/local/go/bin:${GOPATH}/bin:/opt/conda/bin

# Installing build related packages
RUN apt-get update && \
    apt-get install -y git \
                       g++ \
                       wget

WORKDIR /app
ARG ARTIFACTS
RUN mkdir $ARTIFACTS \
          $ARTIFACTS/bin \
          $ARTIFACTS/kapacitor

ARG DEBIAN_FRONTEND=noninteractive
# Installing Golang and other deps
ARG GO_VERSION
RUN apt-get update && \
    wget https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz && \
    apt-get install -y pkg-config

# Setting timezone inside the container
RUN echo "$HOST_TIME_ZONE" >/etc/timezone && \
    cat /etc/timezone && \
    apt-get install -y tzdata && \ 
    ln -sf /usr/share/zoneinfo/${HOST_TIME_ZONE} /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata


ENV HOME /app
ENV KAPACITOR_REPO ${GOPATH}/src/github.com/influxdata/kapacitor

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-4.7.12-Linux-x86_64.sh && \
    chmod +x Miniconda3-4.7.12-Linux-x86_64.sh && \
    ./Miniconda3-4.7.12-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-4.7.12-Linux-x86_64.sh

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
COPY ./eii_msgbus_integration.patch /tmp/eii_msgbus_integration.patch
RUN mkdir -p ${KAPACITOR_REPO} && \
    git clone https://github.com/influxdata/kapacitor.git ${KAPACITOR_REPO} && \
    /bin/bash -c "source activate idp && \
    cd ${KAPACITOR_REPO} && \
    git checkout -b v${KAPACITOR_VERSION} tags/v${KAPACITOR_VERSION} && \
    cd .. && \
    patch -p0 < /tmp/eii_msgbus_integration.patch && \
    rm -rf /tmp/eii_msgbus_integration.patch"

COPY ./kapacitor/services/  \
     ${KAPACITOR_REPO}/vendor/github.com/influxdata/influxdb/services/
COPY ./kapacitor/eii_out.go  ${KAPACITOR_REPO}/
COPY ./kapacitor/pipeline/eii_out.go ${KAPACITOR_REPO}/pipeline/

ARG CMAKE_INSTALL_PREFIX
ENV CMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}
COPY --from=common ${CMAKE_INSTALL_PREFIX}/include ${CMAKE_INSTALL_PREFIX}/include
COPY --from=common ${CMAKE_INSTALL_PREFIX}/lib ${CMAKE_INSTALL_PREFIX}/lib
COPY --from=common ${GOPATH}/src ${GOPATH}/src/
COPY --from=common /eii/common/util util
COPY --from=common /eii/common/libs libs

ENV PATH="$PATH:/usr/local/go/bin" \
    PKG_CONFIG_PATH="$PKG_CONFIG_PATH:${CMAKE_INSTALL_PREFIX}/lib/pkgconfig" \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${CMAKE_INSTALL_PREFIX}/lib"

# These flags are needed for enabling security while compiling and linking with cpuidcheck in golang
ENV CGO_CFLAGS="$CGO_FLAGS -I ${CMAKE_INSTALL_PREFIX}/include -O2 -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fPIC" \
    CGO_LDFLAGS="$CGO_LDFLAGS -L${CMAKE_INSTALL_PREFIX}/lib -z noexecstack -z relro -z now"


# Build kapacitor
RUN /bin/bash -c "source activate idp && \
    cd ${KAPACITOR_REPO} && \
    cp -pr ${GOPATH}/src/EIIMessageBus ./vendor/ && \
    cp -pr ${GOPATH}/src/ConfigMgr ./vendor/ && \
    python3.7 build.py --clean -o $ARTIFACTS/bin"

RUN cd ./libs/ConfigMgr/python && \
    sed "s/\${CMAKE_CURRENT_SOURCE_DIR}/./g;s/\${CMAKE_CURRENT_BINARY_DIR}/./g" setup.py.in > setup.py && \
    /bin/bash -c "source activate idp && \
    python3.7 setup.py install --user && \
    cd ../../../"

# Adding classifier program
COPY ./udfs/ $ARTIFACTS/kapacitor/udfs/
COPY ./training_data_sets/ $ARTIFACTS/kapacitor/training_data_sets/
COPY classifier_startup.py $ARTIFACTS/kapacitor
COPY classifier_startup.sh $ARTIFACTS/kapacitor
# Add tick scripts and configs
COPY ./tick_scripts/* $ARTIFACTS/kapacitor/tick_scripts/
COPY ./config/kapacitor*.conf $ARTIFACTS/kapacitor/config/

FROM base as runtime
LABEL description="Kapacitor image"

ARG EII_UID
ARG EII_USER_NAME
RUN groupadd $EII_USER_NAME -g $EII_UID && \
    useradd -r -u $EII_UID -g $EII_USER_NAME $EII_USER_NAME

WORKDIR /EII
ENV GOPATH="/go"
ARG ARTIFACTS
ARG CMAKE_INSTALL_PREFIX
ENV CMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}

COPY --from=builder /usr/local/go /usr/local
COPY --from=builder $ARTIFACTS/bin/ /usr/local/bin
COPY --from=builder $ARTIFACTS/kapacitor .
COPY --from=builder /app/.local/lib .local/lib
COPY --from=builder /opt/conda /opt/conda
COPY --from=builder ${GOPATH}/src/github.com ${GOPATH}/src/github.com
COPY --from=common ${CMAKE_INSTALL_PREFIX}/lib ${CMAKE_INSTALL_PREFIX}/lib
COPY --from=common /eii/common/util util
COPY --from=common /root/.local/lib .local/lib
COPY --from=common ${GOPATH}/src/github.com/golang/glog ${GOPATH}/src/github.com/golang/glog

RUN chown -R ${EII_UID} .local/lib/python3.7
RUN chmod +x ./classifier_startup.sh
ENV PYTHONPATH $PYTHONPATH:${GOPATH}/src/github.com/influxdata/kapacitor/udf/agent/py/:/opt/conda/lib/python3.7/:/EII/.local/lib/python3.7/site-packages/
ENV GOCACHE "/tmp"
ENV LD_LIBRARY_PATH $LD_LIBRARY_PATH:/usr/local/lib/:/opt/conda/lib/libfabric/:${CMAKE_INSTALL_PREFIX}/lib
RUN echo "source activate idp" >> /etc/bash.bashrc
USER $EII_USER_NAME
ENV PATH $PATH:/app/.local/bin:/opt/conda/bin
HEALTHCHECK NONE

ENTRYPOINT ["./classifier_startup.sh"]
