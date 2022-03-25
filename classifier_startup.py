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

"""Kapacitor service
"""

import subprocess
import os
import os.path
import time
import tempfile
import sys
import json
import socket
from distutils.util import strtobool
import cfgmgr.config_manager as cfg
from util.util import Util
from util.log import configure_logging
import shlex

TEMP_KAPACITOR_DIR = tempfile.gettempdir()
KAPACITOR_CERT = os.path.join(TEMP_KAPACITOR_DIR,
                              "kapacitor_server_certificate.pem")
KAPACITOR_KEY = os.path.join(TEMP_KAPACITOR_DIR, "kapacitor_server_key.pem")
KAPACITOR_CA = os.path.join(TEMP_KAPACITOR_DIR, "ca_certificate.pem")
KAPACITOR_DEV = "kapacitor_devmode.conf"
KAPACITOR_PROD = "kapacitor.conf"
SUCCESS = 0
FAILURE = -1
KAPACITOR_PORT = 9092
KAPACITOR_NAME = 'kapacitord'
CONFIG_KEY_PATH = 'config'


class KapacitorClassifier():
    """Kapacitor Classifier have all the methods related to
       starting kapacitor, udf and tasks
    """
    def __init__(self, logger):
        self.logger = logger

    def start_classifier(self, udf_type, udf_name):
        """Starts the classifier module
        """
        try:
            if udf_type == "go":
                self.logger.info("Running Go based UDF ... {0}".format(
                    udf_name))
                subprocess.Popen(["go", "run", "./udfs/" + udf_name + ".go",
                                  "&"])
            elif udf_type == "python":
                self.logger.info("Running Python based UDF ... {}".format(
                    udf_name))
                subprocess.Popen(["python3.7", "./udfs/" + udf_name + ".py",
                                  "&"])
            else:
                self.logger.error("Not a compatible type, please select "
                                  "either go or python")
            self.logger.info("classifier started successfully")
            return True
        except subprocess.CalledProcessError as err:
            self.logger.info("Exception Occured in Starting the Classifier " +
                             str(err))
            return False

    def write_cert(self, file_name, cert):
        """Write certificate to given file path
        """
        try:
            with open(file_name, 'wb+') as fpd:
                fpd.write(cert.encode())
            os.chmod(file_name, 0o400)
        except (OSError, IOError) as err:
            self.logger.debug("Failed creating file: {}, Error: {} ".format(
                file_name, err))

    def read_config(self, config, dev_mode, app_name):
        """Read the configuration from etcd
        """
        if 'influxdb' in config:
            os.environ['KAPACITOR_INFLUXDB_0_USERNAME'] = \
                os.environ["INFLUXDB_USERNAME"]
            os.environ['KAPACITOR_INFLUXDB_0_PASSWORD'] = \
                os.environ["INFLUXDB_PASSWORD"]

        if not dev_mode:
            server_cert = config["server_cert"]
            self.write_cert(KAPACITOR_CERT, server_cert)
            server_key = config["server_key"]
            self.write_cert(KAPACITOR_KEY, server_key)
            ca_cert = config["ca_cert"]
            self.write_cert(KAPACITOR_CA, ca_cert)

    def start_kapacitor(self,
                        config,
                        host_name,
                        dev_mode,
                        app_name):
        """Starts the kapacitor Daemon in the background
        """
        http_scheme = "http://"
        https_scheme = "https://"
        kapacitor_port = os.environ["KAPACITOR_URL"].split("://")[1]
        influxdb_hostname_port = os.environ[
            "KAPACITOR_INFLUXDB_0_URLS_0"].split("://")[1]

        try:
            if dev_mode:
                kapacitor_conf = 'config/' + KAPACITOR_DEV
                os.environ["KAPACITOR_URL"] = "{}{}".format(http_scheme,
                                                            kapacitor_port)
                os.environ["KAPACITOR_UNSAFE_SSL"] = "true"
                os.environ["KAPACITOR_INFLUXDB_0_URLS_0"] = "{}{}".format(
                    http_scheme, influxdb_hostname_port)
            else:
                # Populate the certificates for kapacitor server
                kapacitor_conf = 'config/' + KAPACITOR_PROD

                os.environ["KAPACITOR_URL"] = "{}{}".format(https_scheme,
                                                            kapacitor_port)
                os.environ["KAPACITOR_UNSAFE_SSL"] = "false"
                os.environ["KAPACITOR_INFLUXDB_0_URLS_0"] = "{}{}".format(
                    https_scheme, influxdb_hostname_port)

            self.read_config(config, dev_mode, app_name)
            subprocess.Popen(["kapacitord", "-hostname", host_name,
                              "-config", kapacitor_conf, "&"])
            self.logger.info("Started kapacitor Successfully...")
            return True
        except subprocess.CalledProcessError as err:
            self.logger.info("Exception Occured in Starting the Kapacitor " +
                             str(err))
            return False

    def process_zombie(self, process_name):
        """Checks the given process is Zombie State & returns True or False
        """
        try:
            out1 = subprocess.run(["ps", "-eaf"], stdout=subprocess.PIPE,
                                  check=False)
            out2 = subprocess.run(["grep", process_name], input=out1.stdout,
                                  stdout=subprocess.PIPE, check=False)
            out3 = subprocess.run(["grep", "-v", "grep"], input=out2.stdout,
                                  stdout=subprocess.PIPE, check=False)
            out4 = subprocess.run(["grep", "defunct"], input=out3.stdout,
                                  stdout=subprocess.PIPE, check=False)
            out = subprocess.run(["wc", "-l"], input=out4.stdout,
                                 stdout=subprocess.PIPE, check=False)
            out = out.stdout.decode('utf-8').rstrip("\n")

            if out == b'1':
                return True

            return False
        except subprocess.CalledProcessError as err:
            self.logger.info("Exception Occured in Starting Kapacitor " +
                             str(err))

    def kapacitor_port_open(self, host_name):
        """Verify Kapacitor's port is ready for accepting connection
        """
        if self.process_zombie(KAPACITOR_NAME):
            self.exit_with_failure_message("Kapacitor fail to start. "
                                           "Please verify the "
                                           "ia_kapacitor logs for "
                                           "UDF/kapacitor Errors.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.info("Attempting to connect to Kapacitor on port 9092")
        result = sock.connect_ex((host_name, KAPACITOR_PORT))
        self.logger.info("Attempted  Kapacitor on port 9092 : Result " +
                         str(result))
        if result == SUCCESS:
            self.logger.info("Successful in connecting to Kapacitor on"
                             "port 9092")
            return True

        return False

    def exit_with_failure_message(self, message):
        """Exit the container with failure message
        """
        if message:
            self.logger.error(message)
        sys.exit(FAILURE)

    def enable_classifier_task(self,
                               host_name,
                               tick_script,
                               task_name):
        """Enable the classifier TICK Script using the kapacitor CLI
        """
        retry_count = 5
        retry = 0
        while not self.kapacitor_port_open(host_name):
            time.sleep(1)
        self.logger.info("Kapacitor Port is Open for Communication....")
        while retry < retry_count:
            define_pointcl_cmd = ["kapacitor", "-skipVerify", "define",
                                  task_name, "-tick",
                                  "tick_scripts/" + tick_script]

            if subprocess.check_call(define_pointcl_cmd) == SUCCESS:
                define_pointcl_cmd = ["kapacitor", "-skipVerify", "enable",
                                      task_name]
                if subprocess.check_call(define_pointcl_cmd) == SUCCESS:
                    self.logger.info("Kapacitor Tasks Enabled Successfully")
                    self.logger.info("Kapacitor Initialized Successfully. "
                                     "Ready to Receive the Data....")
                    break

                self.logger.info("ERROR:Cannot Communicate to Kapacitor.")
            else:
                self.logger.info("ERROR:Cannot Communicate to Kapacitor. ")
            self.logger.info("Retrying Kapacitor Connection")
            time.sleep(0.0001)
            retry = retry + 1

    def start_udfs(self, config):
        """Starting the udf based on the config
           read from the etcd
        """
        # Checking if udf present in task and
        # run it based on etcd config
        if 'task' not in config.keys():
            error_msg = "task key is missing in config, EXITING!!!"
            return error_msg, FAILURE

        for task in config['task']:
            if 'udfs' in task.keys():
                for udf in task['udfs']:
                    if 'type' in udf:
                        udf_type = udf['type'].lower()
                    else:
                        error_msg = ("UDF type key is missing in config "
                                     "Please provide go or python "
                                     "EXITING!!!")
                        return error_msg, FAILURE

                    if 'name' in udf:
                        udf_name = udf['name']
                    else:
                        error_msg = ("UDF name key is missing in config "
                                     "EXITING!!!")
                        return error_msg, FAILURE

                    if self.start_classifier(udf_type, udf_name) is True:
                        self.logger.info("Classifier started successfully")
                    else:
                        error_msg = ("Classifier is not able to start. "
                                     "Fix all the Errors & try again")
                        return error_msg, FAILURE
            else:
                self.logger.info("Configured task has no UDF")

        return None, SUCCESS

    def enable_tasks(self, config, kapacitor_started, host_name, dev_mode):
        """Starting the task based on the config
           read from the etcd
        """
        for task in config['task']:
            if 'tick_script' in task:
                tick_script = task['tick_script']
            else:
                error_msg = ("tick_script key is missing in config "
                             "Please provide the tick script to run "
                             "EXITING!!!!")
                return error_msg, FAILURE

            if 'task_name' in task:
                task_name = task['task_name']
            else:
                error_msg = ("task_name key is missing in config "
                             "Please provide the task name "
                             "EXITING!!!")
                return error_msg, FAILURE

            if kapacitor_started:
                self.logger.info("Enabling {0}".format(tick_script))
                self.enable_classifier_task(host_name,
                                            tick_script,
                                            task_name)

        if not dev_mode:
            try:
                file_list = [KAPACITOR_CERT,
                             KAPACITOR_KEY]
                Util.delete_certs(file_list)
            except (OSError, IOError):
                self.logger.error("Exception Occured while removing"
                                  "kapacitor certs")

        while True:
            time.sleep(10)


def main():
    """Main to start kapacitor service
    """
    try:
        ctx = cfg.ConfigMgr()
        app_cfg = ctx.get_app_config()
        config = app_cfg.get_dict()
        app_name = ctx.get_app_name()
        dev_mode = ctx.is_dev_mode()
    except Exception as e:
        logger = configure_logging(os.getenv('PY_LOG_LEVEL', 'info').upper(),
                                   __name__, dev_mode)
        logger.exception("Fetching app configuration failed, Error: {}".format(e))
        sys.exit(1)

    logger = configure_logging(os.environ['PY_LOG_LEVEL'].upper(),
                               __name__, dev_mode)

    kapacitor_classifier = KapacitorClassifier(logger)

    logger.info("=============== STARTING kapacitor ==============")
    host_name = shlex.quote(os.environ["KAPACITOR_SERVER"])
    if not host_name:
        error_log = ('Kapacitor hostname is not Set in the container. '
                     'So exiting...')
        kapacitor_classifier.exit_with_failure_message(error_log)

    msg, status = kapacitor_classifier.start_udfs(config)
    if status is FAILURE:
        kapacitor_classifier.exit_with_failure_message(msg)

    kapacitor_started = False
    if(kapacitor_classifier.start_kapacitor(config,
                                            host_name,
                                            dev_mode,
                                            app_name) is True):
        kapacitor_started = True
    else:
        error_log = "Kapacitor is not starting. So Exiting..."
        kapacitor_classifier.exit_with_failure_message(error_log)

    msg, status = kapacitor_classifier.enable_tasks(config,
                                                    kapacitor_started,
                                                    host_name,
                                                    dev_mode)
    if status is FAILURE:
        kapacitor_classifier.exit_with_failure_message(msg)


if __name__ == '__main__':
    main()
