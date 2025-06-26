import unittest
import unittest.mock
import micro_logger_unittest
import relations.unittest

import json

import service


class MockRedis:

    host = None

    queue = None

    def __init__(self, host, **kwargs):

        self.host = host
        self.queue = {}
        self.groups = {}
        self.read = {}
        self.ack = {}

    def exists(self, stream):

        return stream in self.queue

    def xinfo_groups(self, stream):

        return self.groups[stream]

    def xgroup_create(self, stream, name, mkstream=False):

        self.groups[stream] = {
            "name": name
        }

        if mkstream:
            self.queue[stream] = []

    def xadd(self, stream, fields):

        self.queue.setdefault(stream, [])
        self.queue[stream].append({"fields": fields})

    def xreadgroup(self, group, consumer, streams, count=0, block=5000):

        self.read = {
            "group": group,
            "consumer": consumer,
            "streams": streams,
            "count": count,
            "block": block
        }

        stream = list(streams.keys())[0]

        return [
            [
                stream,
                [
                    [
                        "id",
                        self.queue[stream].pop(0)
                    ]
                ]
            ]
        ]

    def xack(self, stream, group, id):

        self.ack = {
            "stream": stream,
            "group": group,
            "id": id
        }


class TestDaemon(micro_logger_unittest.TestCase):

    maxDiff = None

    @unittest.mock.patch.dict('os.environ', {"K8S_POD": "unit", "SLEEP": "7", "LOG_LEVEL": "INFO"})
    @unittest.mock.patch("micro_logger.getLogger", micro_logger_unittest.MockLogger)
    @unittest.mock.patch('relations_rest.Source', relations.unittest.MockSource)
    @unittest.mock.patch('redis.Redis', MockRedis)
    @unittest.mock.patch('service.open', new_callable=unittest.mock.mock_open, read_data='{"key": "funspot"}')
    def setUp(self, mock_open):

        self.daemon = service.Daemon()

    @unittest.mock.patch.dict('os.environ', {"K8S_POD": "test", "SLEEP": "7", "LOG_LEVEL": "INFO"})
    @unittest.mock.patch("micro_logger.getLogger", micro_logger_unittest.MockLogger)
    @unittest.mock.patch('relations_rest.Source', relations.unittest.MockSource)
    @unittest.mock.patch('redis.Redis', MockRedis)
    @unittest.mock.patch('service.open', new_callable=unittest.mock.mock_open, read_data='{"key": "funspot"}')
    def test___init__(self, mock_open):

        daemon = service.Daemon()

        self.assertEqual(daemon.name, "ayaye-daemon")
        self.assertEqual(daemon.unifist, "ledger")
        self.assertEqual(daemon.group, "ayaye-daemon")
        self.assertEqual(daemon.group_id, "test")

        self.assertEqual(daemon.sleep, 7)

        self.assertEqual(daemon.logger.name, "ayaye-daemon")

        self.assertIsInstance(relations.source("ledger"), relations.unittest.MockSource)

    def test_process(self):

        self.daemon.redis.queue["ledger/fact"].append({})

        self.daemon.process()

    @unittest.mock.patch('prometheus_client.start_http_server')
    @unittest.mock.patch('service.Daemon.process')
    def test_run(self, mock_run, mock_prom):

        mock_run.side_effect = Exception("loop")

        self.assertRaisesRegex(Exception, "loop", self.daemon.run)

        mock_prom.assert_called_once_with(80)
