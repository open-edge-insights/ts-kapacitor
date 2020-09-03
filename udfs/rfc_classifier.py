from kapacitor.udf.agent import Agent, Handler
import math
import json
from kapacitor.udf import udf_pb2
import sys
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import daal4py as d4p

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger()


class RfcHandler(Handler):
    """
    Random Forest Classifier Handler
    """
    def __init__(self, agent):
        self._agent = agent
        self._history = None
        self._batch = None
        logging.info("Training started...")
        training = pd.read_csv('/EIS/training_data_sets/Log_rf.csv')
        training = training.sample(frac=1)

        y = training[['label']]
        X = training.iloc[:, :-1]
        X_train, X_test, y_train, y_test = train_test_split(X, y,
                                                            test_size=0.2,
                                                            random_state=20,
                                                            stratify=y)
        # The number of cores is tuned based on the hardware and dataset
        no_of_cores = 10
        d4p.daalinit(no_of_cores)
        # maxDepth, numOfTree are tuned based on dataset
        maxDepth = 50
        numOfTree = 600
        train_algo = d4p.decision_forest_classification_training(maxTreeDepth=maxDepth,
                                                                 nClasses=2, nTrees=numOfTree,
                                                                 engine=d4p.engines_mt2203(seed=0),
                                                                 varImportance='MDI', bootstrap=True)

        self.train_result = train_algo.compute(X_train, y_train)
        logging.info("training complete...")

    def info(self):
        """
        Respond with which type of edges we
        want/provide and any options we have.
        """
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.BATCH
        response.info.provides = udf_pb2.STREAM

        return response

    def init(self, init_req):
        """
        Given a list of options initialize this instance of the handler

        :param init_req: initialize the handler
        :type init_req: udf_pb2.InitRequest
        """
        response = udf_pb2.Response()
        response.init.success = True

        return response

    def begin_batch(self, begin_req):
        """
        Create new window for batch and initialize a structure for it

        :param begin_req: to start the batch
        :type begin_req: udf_pb2.BeginBatch
        """
        self.pred = []
        self.assetId = []
        self.batchTS = []

    def point(self, point):
        """
        Store and processing of the point

        :param point: the body of the point received
        :type point: udf_pb2.Point
        """
        self.response = udf_pb2.Response()
        jsonObj = json.loads(point.fieldsString['value'])
        df = pd.DataFrame(columns=['Message.Log.Name1',
                                   'Message.Log.Name2',
                                   'Message.Log.Name3',
                                   'Message.Log.Name4',
                                   'Message.Log.Name5',
                                   'Message.Log.ilsts1',
                                   'Message.Log.Name6',
                                   'Message.Log.Name7',
                                   'Message.Log.Name8',
                                   'Message.Log.Name9',
                                   'Message.Log.Name10',
                                   'Message.Log.Name11',
                                   'Message.Log.Name12',
                                   'Message.Log.Name13',
                                   'Message.Log.Name14',
                                   'Message.Log.Name15',
                                   'Message.Log.Name16',
                                   'Message.Log.Name17',
                                   'Message.Log.Name18',
                                   'Message.Log.Name19',
                                   'Message.Log.Name20',
                                   'Message.Log.Name21',
                                   'Message.Log.Name22',
                                   'Message.Log.Name23',
                                   'Message.Log.Name24',
                                   'Message.Log.Name25',
                                   'Message.Log.Name26',
                                   'Message.Log.Name27',
                                   'Message.Log.Name28',
                                   'Message.Log.Name29',
                                   'Message.Log.Name30',
                                   'Message.Log.Name31',
                                   'Message.Log.Name32',
                                   'Message.Log.Name33',
                                   'Message.Log.Name34',
                                   'Message.Log.Name35',
                                   'Message.Log.Name36',
                                   'Message.Log.Name37',
                                   'Message.Log.Name38'])

        df = df.append({
                    'Message.Log.Name1': jsonObj['Message']['Log']['Name1'],
                    'Message.Log.Name2': jsonObj['Message']['Log']['Name2'],
                    'Message.Log.Name3': jsonObj['Message']['Log']['Name3'],
                    'Message.Log.Name4': jsonObj['Message']['Log']['Name4'],
                    'Message.Log.Name5': jsonObj['Message']['Log']['Name5'],
                    'Message.Log.ilsts1': jsonObj['Message']['Log']['ilsts1'],
                    'Message.Log.Name6': jsonObj['Message']['Log']['Name6'],
                    'Message.Log.Name7': jsonObj['Message']['Log']['Name7'],
                    'Message.Log.Name8': jsonObj['Message']['Log']['Name8'],
                    'Message.Log.Name9': jsonObj['Message']['Log']['Name9'],
                    'Message.Log.Name10': jsonObj['Message']['Log']['Name10'],
                    'Message.Log.Name11': jsonObj['Message']['Log']['Name11'],
                    'Message.Log.Name12': jsonObj['Message']['Log']['Name12'],
                    'Message.Log.Name13': jsonObj['Message']['Log']['Name13'],
                    'Message.Log.Name14': jsonObj['Message']['Log']['Name14'],
                    'Message.Log.Name15': jsonObj['Message']['Log']['Name15'],
                    'Message.Log.Name16': jsonObj['Message']['Log']['Name16'],
                    'Message.Log.Name17': jsonObj['Message']['Log']['Name17'],
                    'Message.Log.Name18': jsonObj['Message']['Log']['Name18'],
                    'Message.Log.Name19': jsonObj['Message']['Log']['Name19'],
                    'Message.Log.Name20': jsonObj['Message']['Log']['Name20'],
                    'Message.Log.Name21': jsonObj['Message']['Log']['Name21'],
                    'Message.Log.Name22': jsonObj['Message']['Log']['Name22'],
                    'Message.Log.Name23': jsonObj['Message']['Log']['Name23'],
                    'Message.Log.Name24': jsonObj['Message']['Log']['Name24'],
                    'Message.Log.Name25': jsonObj['Message']['Log']['Name25'],
                    'Message.Log.Name26': jsonObj['Message']['Log']['Name26'],
                    'Message.Log.Name27': jsonObj['Message']['Log']['Name27'],
                    'Message.Log.Name28': jsonObj['Message']['Log']['Name28'],
                    'Message.Log.Name29': jsonObj['Message']['Log']['Name29'],
                    'Message.Log.Name30': jsonObj['Message']['Log']['Name30'],
                    'Message.Log.Name31': jsonObj['Message']['Log']['Name31'],
                    'Message.Log.Name32': jsonObj['Message']['Log']['Name32'],
                    'Message.Log.Name33': jsonObj['Message']['Log']['Name33'],
                    'Message.Log.Name34': jsonObj['Message']['Log']['Name34'],
                    'Message.Log.Name35': jsonObj['Message']['Log']['Name35'],
                    'Message.Log.Name36': jsonObj['Message']['Log']['Name36'],
                    'Message.Log.Name37': jsonObj['Message']['Log']['Name37'],
                    'Message.Log.Name38': jsonObj['Message']['Log']['Name38']},
                    ignore_index=True)

        # Inference with daal4py 
        self.predict_algo = d4p.decision_forest_classification_prediction(2)
        self.predict_result = self.predict_algo.compute(df, self.train_result.model)
        self.rfc_prediction_pred = self.predict_result.prediction
        self.pred.append(self.rfc_prediction_pred)
        self.assetId.append(jsonObj['NameOFLog'])
        self.batchTS.append(point.time)

        self.response.point.CopyFrom(point)
        self.response.point.ClearField('fieldsInt')
        self.response.point.ClearField('fieldsString')
        self.response.point.ClearField('fieldsDouble')

    def end_batch(self, batch_meta):
        """
        Update the point with response data and end the batch

        :param batch_meta: Create the meta data of the response
        :type batch_meta: udf_pb2.EndBatch
        """
        for i in range(len(self.assetId)):
            self.response.point.fieldsString['assetId'] = self.assetId[i]
            self.response.point.fieldsString['prediction'] = str(self.pred[i])
            self.response.point.time = self.batchTS[i]
            logging.info(self.response)
            self._agent.write_response(self.response)

    def snapshot(self):
        """
        Take snapshot
        """
        response = udf_pb2.Response()
        response.snapshot.snapshot = bytes('', 'utf-8')
        return response

    def restore(self, restore_req):
        """
        restore snapshot

        :param restore_req: to start the restore process
        :type restore_req: udf_pb2.RestoreRequest
        """
        response = udf_pb2.Response()
        response.restore.success = False
        response.restore.error = bytes('not implemented', 'utf-8')
        return response


if __name__ == '__main__':
    # Create an agent
    agent = Agent()

    # Create a handler and pass it an agent so it can write points
    h = RfcHandler(agent)

    # Set the handler on the agent
    agent.handler = h

    # Anything printed to STDERR from a UDF process gets captured
    # into the Kapacitor logs.
    agent.start()
    agent.wait()
