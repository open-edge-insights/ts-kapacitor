# Point-data (Time-series data) analytics introduction

Any integral value that gets generated over time, we can say it is a point data.
The examples can be :
* Temperature at a different time in a day.
* Number of oil barrels processed per minute.

By doing the analytics over point data, the factory can have an anomaly detection mechanism.
That's where the PointDataAnalytics come into the picture.

IEdgeInsights uses the [TICK stack](https://www.influxdata.com/time-series-platform/)
to do point data analytics.

IEdgeInsights has a temperature anomaly detection example for demonstrating the time-series data analytics flow.

The high-level flow of the data, in the example, can be seen as MQTT-temp-sensor-->Telegraf-->Influx-->Kapacitor-->Influx.

MQTT-temp-sensor simulator sends the data to the Telegraf. Telegraf just sends the same data to the
Influx and Influx send it to Kapacitor. Kapacitor does anomaly detection and publishes the results back to
Influx.

Here,
Telegraf is the TICK stack component and supporting the number of input plug-ins for data ingestion.
Influx is a time-series database.
Kapacitor is an analytics engine where users can write custom analytics plug-ins (TICK scripts).

## Starting the example

1. To start the mqtt-temp-sensor, please refer [tools/mqtt-temp-sensor/README.md](../tools/mqtt-temp-sensor/README.md) .

2. In case, if SI wants to use the IEdgeInsights only for Point Data Analytics,
   then comment Video use case containers ia_video_ingestion and ia_video_analytics in [docker_setup/docker-compose.yml](../docker_setup/docker-compose.yml)

3. Starting the EIS.
   To start the EIS in production mode, provisioning is required. For more information on provisioning
   please refer the [README](../README.md#provision-eis).
   After provisioning, please follow the below commands
   ```
   cd docker_setup
   docker-compose build
   docker-compose up -d
   ```

   To start the EIS in developer mode, please refer to the [README](../README.md#provision-eis).

4. To verify the output please check the output of below command
   ```
   docker logs -f ia_influxdbconnector
   ```

   Below is the snapshot of sample output of the ia_influxdbconnector command.
   ```
   I0822 09:03:01.705940       1 pubManager.go:111] Published message: map[data:point_classifier_results,host=ia_telegraf,topic=temperature/simulated/0 temperature=19.29358085726703,ts=1566464581.6201317 1566464581621377117] 
   I0822 09:03:01.927094       1 pubManager.go:111] Published message: map[data:point_classifier_results,host=ia_telegraf,topic=temperature/simulated/0 temperature=19.29358085726703,ts=1566464581.6201317 1566464581621377117]
   I0822 09:03:02.704000       1 pubManager.go:111] Published message: map[data:point_data,host=ia_telegraf,topic=temperature/simulated/0 ts=1566464582.6218634,temperature=27.353740759929877 1566464582622771952]
   ```

   The data can be visualized using the Grafana dashboard, to know more refer [Grafana/README.md](../Grafana/README.md)

## Purpose of Telegraf
Telegraf is one of the data entry points for IEdgeInsights. It supports many input plugins, which can be used for
point data ingestion. In the above example, the MQTT input plugin of Telegraf is used. And below is the configuration
of the plugin.

    ```
    # # Read metrics from MQTT topic(s)
    [[inputs.mqtt_consumer]]
    #   ## MQTT broker URLs to be used. The format should be scheme://host:port,
    #   ## schema can be tcp, ssl, or ws.
        servers = ["tcp://localhost:1883"]
    #
    #   ## MQTT QoS, must be 0, 1, or 2
    #   qos = 0
    #   ## Connection timeout for initial connection in seconds
    #   connection_timeout = "30s"
    #
    #   ## Topics to subscribe to
        topics = [
        "temperature/simulated/0",
        ]
        name_override = "point_data"
        data_format = "json"
    #
    #   # if true, messages that can't be delivered while the subscriber is offline
    #   # will be delivered when it comes back (such as on service restart).
    #   # NOTE: if true, client_id MUST be set
        persistent_session = false
    #   # If empty, a random client ID will be generated.
        client_id = ""
    #
    #   ## username and password to connect MQTT server.
        username = ""
        password = ""
    ```

The production mode Telegraf configuration file is
[Telegraf/config/telegraf.conf](../Telegraf/config/telegraf.conf) and in developer mode,
the configuration file is
[Telegraf/config/telegraf_devmode.conf](../Telegraf/config/telegraf_devmode.conf).

For more information on the supported input and output plugins please refer
[https://docs.influxdata.com/telegraf/v1.10/plugins/](https://docs.influxdata.com/telegraf/v1.10/plugins/)

## Purpose of Kapacitor

  About Kapacitor and UDF
  * User can write the custom anomaly detection algorithm in PYTHON/GOLANG. And these algorithms will be called as
    UDF (user-defined function). These algorithms have to follow certain API standards so that the Kapacitor will be able to
    call these UDFs at run time.

  * IEdgeInsights has come up with the sample UDF written in GOLANG. Kapacitor is subscribed to the InfluxDB, and
    gets the temperature data. After getting this data, Kapacitor calls these UDF, which detects the anomaly in the temperature
    and sends back the results to Influx.

  * The sample Go UDF is at [go_classifier.go](udf/go_point_classifier.go) and
    the tick script  is at [go_point_classifier.tick](TICK_script/go_point_classifier.tick)

  * The sample Python UDF is at [py_classifier.py](udf/py_point_classifier.py) and
    the tick script  is at [py_point_classifier.tick](TICK_script/py_point_classifier.tick)

    For more details, on Kapacitor and UDF, please refer below links
    i)  Writing a sample UDF at [anomaly detection](https://docs.influxdata.com/kapacitor/v1.5/guides/anomaly_detection/)
    ii) UDF and kapacitor interaction [here](https://docs.influxdata.com/kapacitor/v1.5/guides/socket_udf/)

  * In production mode the Kapacitor config file is
    [Kapacitor/config/kapacitor.conf](./config/kapacitor.conf)
    and in developer mode the config file would be
    [Kapacitor/config/kapacitor_devmode.conf](./config/kapacitor_devmode.conf)

## Steps to configure the UDFs in kapacitor.

  * Keep the custom UDFs in the [udf](udf) directory and the TICK script in the [tick_scripts](tick_scripts) directory.

  * Modify the udf section in the [kapacitor.conf](config/kapacitor.conf) and in the [kapacitor_devmode.conf](config/kapacitor_devmode.conf).
    Mention the custom udf in the conf
    for example
    ```
    [udf.functions.customUDF]
      socket = $SOCKET_PATH
      timeout = "20s"
    ```

  * Update the following details in the [etcd_pre_load.json](../../docker_setup/provision/config/etcd_pre_load.json) file.
    ```
    "udfs": {
            "type": "python",
            "name": "py_classifier",
            "socket_path": "/tmp/point_classifier",
            "tick_script": "py_point_classifier.tick",
            "task_name": "py_point_classifier"
        }
    ```
    ### Note:
    1. Currently only one UDF is supported at a time and by default, go_classifier is configured.

    2. Mention the task name the same as mentioned in the TICK script udf function.
      ```
       @py_point_classifier()
      ```

  * Do the [provisioning](../README.md#provision-eis) and run the EIS stack.