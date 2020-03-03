# Dockerfile for Point Data Analytics
ARG EIS_VERSION
FROM ia_eisbase:$EIS_VERSION as eisbase
LABEL description="Kapacitor image"

ENV PY_WORK_DIR /EIS
WORKDIR ${PY_WORK_DIR}
ENV PYTHONPATH .
ENV HOME /EIS
ENV KAPACITOR_REPO /EIS/go/src/github.com/influxdata/kapacitor
ENV GO_ROOT_BIN /EIS/go/bin
ENV PYTHONPATH ${PYTHONPATH}
ARG EIS_UID

# Adding kapacitor related files
ARG KAPACITOR_VERSION
RUN mkdir -p ${KAPACITOR_REPO} && \
    git clone https://github.com/influxdata/kapacitor.git ${KAPACITOR_REPO} && \
    cd ${KAPACITOR_REPO} && \
    git checkout -b v${KAPACITOR_VERSION} tags/v${KAPACITOR_VERSION} && \
    python3.6 build.py --clean -o ${GO_ROOT_BIN}

ENV PYTHONPATH $PYTHONPATH:${KAPACITOR_REPO}/udf/agent/py/

FROM ia_common:$EIS_VERSION as common

FROM eisbase

COPY --from=common ${GO_WORK_DIR}/common/libs ${PY_WORK_DIR}/libs
COPY --from=common ${GO_WORK_DIR}/common/util ${PY_WORK_DIR}/util
COPY --from=common ${GO_WORK_DIR}/common/cmake ${PY_WORK_DIR}/common/cmake
COPY --from=common /usr/local/lib /usr/local/lib
COPY --from=common /usr/local/lib/python3.6/dist-packages/ /usr/local/lib/python3.6/dist-packages/

# Adding classifier program
COPY . ./

#Removing build dependencies
RUN apt-get remove -y wget && \
    apt-get remove -y git && \
    apt-get remove curl && \
    apt-get autoremove -y

ENTRYPOINT ["python3.6", "./classifier_startup.py"]
