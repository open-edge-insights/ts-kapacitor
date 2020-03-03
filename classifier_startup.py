# Copyright (c) 2020 Intel Corporation.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM,OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import subprocess
import os.path
import argparse
import shutil
import time
import stat
import json
import socket
import datetime
from eis.config_manager import ConfigManager
from util.log import configure_logging, LOG_LEVELS
from distutils.util import strtobool
import os
from util.util import Util

TEMP_KAPACITOR_DIR = "/tmp/"
KAPACITOR_CERT = TEMP_KAPACITOR_DIR + "kapacitor_server_certificate.pem"
KAPACITOR_KEY = TEMP_KAPACITOR_DIR + "kapacitor_server_key.pem"
KAPACITOR_CA = TEMP_KAPACITOR_DIR + "ca_certificate.pem"
KAPACITOR_DEV = "kapacitor_devmode.conf"
KAPACITOR_PROD = "kapacitor.conf"
SUCCESS = 0
FAILURE = -1
KAPACITOR_PORT = 9092
KAPACITOR_NAME = 'kapacitord'
logger = None
args = None


def start_classifier(udf_type, udf_name):
    """Starts the classifier module
    """
    try:
        if udf_type == "go":
            logger.info("Running Go based UDF ...")
            subprocess.call("go run ./udf/" + udf_name + ".go &", shell=True)
        elif udf_type == "python":
            logger.info("Running Python based UDF ...")
            subprocess.call("python3.6 ./udf/" + udf_name + ".py &",
                            shell=True)
        else:
            logger.error("Not a compatible type, please select \
                          either go or python")
        logger.info("classifier started successfully")
        return True
    except Exception as e:
        logger.info("Exception Occured in Starting the Classifier " + str(e))
        return False


def grant_permission_socket(socket_path):
    """Grants chmod 0x777 permission for the classifier's socket file
    """
    while not os.path.exists(socket_path):
        pass
    logger.info("Socket file present...")
    if os.path.isfile(socket_path):
        os.chmod(socket_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    logger.info("Permission Granted for Socket files")


def write_cert(file_name, cert):
    """Write certificate to given file path
    """
    try:
        with open(file_name, 'wb+') as fd:
            fd.write(cert.encode())
    except Exception as e:
        logger.debug("Failed creating file: {}, Error: {} ".format(file_name,
                                                                   e))


def read_config(client, dev_mode, app_name, config_key_path):
    """Read the configuration from etcd
    """
    configfile = client.GetConfig("/{0}/{1}".format(
                 app_name, config_key_path))
    config = json.loads(configfile)
    os.environ['KAPACITOR_INFLUXDB_0_USERNAME'] = config['influxdb'
                                                         ]['username']
    os.environ['KAPACITOR_INFLUXDB_0_PASSWORD'] = config['influxdb'
                                                         ]['password']

    if not dev_mode:
        cert = client.GetConfig("/{0}/{1}".format(
               app_name, "server_cert"))
        write_cert(KAPACITOR_CERT, cert)
        key = client.GetConfig("/{0}/{1}".format(
               app_name, "server_key"))
        write_cert(KAPACITOR_KEY, key)
        ca = client.GetConfig("/{0}/{1}".format(
               app_name, "ca_cert"))
        write_cert(KAPACITOR_CA, ca)


def start_kapacitor(client,
                    host_name,
                    dev_mode,
                    app_name,
                    config_key_path,
                    socket_path):
    """Starts the kapacitor Daemon in the background
    """
    HTTP_SCHEME = "http://"
    HTTPS_SCHEME = "https://"
    KAPACITOR_HOSTNAME_PORT = os.environ["KAPACITOR_URL"].split("://")[1]
    INFLUXDB_HOSTNAME_PORT = os.environ["KAPACITOR_INFLUXDB_0_URLS_0"].split(
        "://")[1]

    try:
        if dev_mode:
            kapacitor_conf = TEMP_KAPACITOR_DIR + KAPACITOR_DEV
            shutil.copy("/EIS/config/" + KAPACITOR_DEV, kapacitor_conf)
            os.environ["KAPACITOR_URL"] = "{}{}".format(
                                                HTTP_SCHEME,
                                                KAPACITOR_HOSTNAME_PORT)
            os.environ["KAPACITOR_UNSAFE_SSL"] = "true"
            os.environ["KAPACITOR_INFLUXDB_0_URLS_0"] = "{}{}".format(
                HTTP_SCHEME, INFLUXDB_HOSTNAME_PORT)
        else:
            # Populate the certificates for kapacitor server
            kapacitor_conf = TEMP_KAPACITOR_DIR + KAPACITOR_PROD
            shutil.copy("/EIS/config/" + KAPACITOR_PROD, kapacitor_conf)
            os.environ["KAPACITOR_URL"] = "{}{}".format(
                                                HTTPS_SCHEME,
                                                KAPACITOR_HOSTNAME_PORT)
            os.environ["KAPACITOR_UNSAFE_SSL"] = "false"
            os.environ["KAPACITOR_INFLUXDB_0_URLS_0"] = "{}{}".format(
                HTTPS_SCHEME, INFLUXDB_HOSTNAME_PORT)

        subprocess.run("sed -i 's#socket = .*#socket = \"" +
                       socket_path + "\"#'g " + kapacitor_conf,
                       shell=True)
        read_config(client, dev_mode, app_name, config_key_path)
        subprocess.run("kapacitord -hostname " + host_name +
                       " -config " + kapacitor_conf + " &", shell=True)

        logger.info("Started kapacitor Successfully...")
        return True
    except Exception as e:
        logger.info("Exception Occured in Starting the Kapacitor " + str(e))
        return False


def process_zombie(process_name):
    """Checks the given process is Zombie State & returns True or False
    """
    try:
        out = subprocess.check_output('ps -eaf | grep ' + process_name +
                                      '| grep -v grep | grep defunct | wc -l',
                                      shell=True).strip()
        return True if (out == b'1') else False
    except Exception as e:
        logger.info("Exception Occured in Starting Kapacitor " + str(e))


def kapacitor_port_open(host_name):
    """Verify Kapacitor's port is ready for accepting connection
    """
    if process_zombie(KAPACITOR_NAME):
        exit_with_failure_message("Kapacitor fail to start.Please verify the \
            ia_data_analytics logs for UDF/kapacitor Errors.")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger.info("Attempting to connect to Kapacitor on port 9092")
    result = sock.connect_ex((host_name, KAPACITOR_PORT))
    logger.info("Attempted  Kapacitor on port 9092 : Result " + str(result))
    if result == SUCCESS:
        logger.info("Successful in connecting to Kapacitor on port 9092")
        return True
    else:
        return False


def exit_with_failure_message(message):
    logger.error(message)
    exit(FAILURE)


def enable_classifier_task(host_name, dev_mode, tick_script, task_name):
    """Enable the classifier TICK Script using the kapacitor CLI
    """
    retry_count = 5
    retry = 0
    while not kapacitor_port_open(host_name):
        time.sleep(1)
    logger.info("Kapacitor Port is Open for Communication....")
    while(retry < retry_count):
        definePointClCmd = ["kapacitor", "-skipVerify", "define",
                            task_name, "-tick",
                            "tick_scripts/" + tick_script + ".tick"]

        if (subprocess.check_call(definePointClCmd) == SUCCESS):
            definePointClCmd = ["kapacitor", "-skipVerify", "enable",
                                task_name]

            if (subprocess.check_call(definePointClCmd) == SUCCESS):
                logger.info("Kapacitor Tasks Enabled Successfully")
                break
            else:
                logger.info("ERROR:Cannot Communicate to Kapacitor. ")
        else:
            logger.info("ERROR:Cannot Communicate to Kapacitor. ")
        logger.info("Retrying Kapacitor Connection")
        time.sleep(0.0001)
        retry = retry + 1

    if not (dev_mode):
        try:
            file_list = [KAPACITOR_CERT,
                         KAPACITOR_KEY]
            Util.delete_certs(file_list)
        except Exception:
            logger.error("Exception Occured while removing kapacitor certs")


if __name__ == '__main__':

    dev_mode = bool(strtobool(os.environ["DEV_MODE"]))
    # Initializing Etcd to set env variables
    app_name = os.environ["AppName"]
    conf = Util.get_crypto_dict(app_name)

    cfg_mgr = ConfigManager()
    config_client = cfg_mgr.get_config_client("etcd", conf)
    app_name = os.environ["AppName"]
    config_key_path = "config"
    configfile = config_client.GetConfig("/{0}/{1}".format(
                 app_name, config_key_path))
    config = json.loads(configfile)

    # TODO Enable support for more than one UDF simultaneously
    udf_type = config['udfs']['type'].lower()
    udf_name = config['udfs']['name']
    socket_path = config['udfs']['socket_path']
    tick_script = config['udfs']['tick_script']
    task_name = config['udfs']['task_name']

    logger = configure_logging(os.environ['PY_LOG_LEVEL'].upper(),
                               __name__, dev_mode)
    os.environ["SOCKET_PATH"] = socket_path

    logger.info("=============== STARTING data_analytics ==============")

    host_name = os.environ["KAPACITOR_SERVER"]
    if not host_name:
        exit_with_failure_message('Kapacitor hostname is not Set in the \
         container.So exiting..')
    if (start_classifier(udf_type, udf_name) is True):
        grant_permission_socket(socket_path)
        if(start_kapacitor(config_client,
                           host_name,
                           dev_mode,
                           app_name,
                           config_key_path,
                           socket_path) is True):
            enable_classifier_task(host_name, dev_mode, tick_script, task_name)
        else:
            logger.info("Kapacitor is not starting.So Exiting...")
            exit(FAILURE)
        logger.info(
            "DataAnalytics Initialized Successfully.Ready to Receive the \
            Data....")
        while(True):
            time.sleep(10)
    else:
        logger.info("Classifier is not able to start.Fix all the Errors &\
                    try again")
