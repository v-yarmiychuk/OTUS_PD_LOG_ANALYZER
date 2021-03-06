import gzip
import logging
import re
import statistics
import time
from typing import AnyStr
from typing import Match
from typing import Optional
from typing import TextIO


class LogParser:
    def __init__(self, path: str, gz: bool) -> None:
        self.logger = logging.getLogger(f'log_analyzer.Parser')
        self.path = path
        self.log_opener = gzip.open if gz else open
        self._pattern = re.compile(
            r'(?P<ipaddress>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) .* '
            r'(?P<remoteuser>.*) .* '
            r'\[(?P<dateandtime>\d{2}\/[a-z]{3}\/\d{4}:\d{2}:\d{2}:\d{2} (\+|\-)\d{4})\] '
            r'((\"(?P<method>.+) )(?P<url>.+)(http\/[1-2]\.[0-9]")) '
            r'(?P<statuscode>\d{3}) '
            r'(?P<bytessent>\d+) '
            r'(["](?P<refferer>(\-)|(.+))["]) '
            r'(?P<http_user_agent>.+?(?=\ ))\s+"-"\s+"'
            r'(?P<x_forwaded_for>(.+?))"\s+"'
            r'(?P<http_xb_user>(.+?))"\s+'
            r'(?P<request_time>[+-]?([0-9]*[.])?[0-9]+)',
            re.IGNORECASE
        )
        self.status_len = [0, 0]
        self.raw_data = {}
        self.processed_data = []
        self.total_request_time = 0

    def __call__(self, *args, **kwargs) -> list:
        start = time.perf_counter()

        with self.log_opener(self.path, mode="rt") as f:
            for url in self._log_parser(f):
                raw_data = self.raw_data.setdefault(url.group('url'), {'request_times': []})
                raw_data['request_times'].append(float(url.group('request_time')))
                self.total_request_time += float(url.group('request_time'))

        self._check_status_len()
        self._data_calculation()

        self.logger.info(f'log file parsed in: {time.perf_counter() - start} ')
        return self.processed_data

    def _check_status_len(self, error_threshold: int = 50) -> None:
        error_perc = self.status_len[1] * 100 / sum(self.status_len)
        if error_perc > error_threshold:
            raise Exception(f'error percentage ({error_perc}) exceeds the threshold ({error_threshold})')

    def _data_calculation(self) -> None:
        for url, url_data in self.raw_data.items():
            data_item = {}

            data_item['url'] = url
            data_item['count'] = len(url_data['request_times'])
            data_item['count_perc'] = data_item['count'] * 100 / self.status_len[0]
            data_item['time_sum'] = sum(url_data['request_times'])
            data_item['time_perc'] = data_item['time_sum'] * 100 / self.total_request_time
            data_item['time_avg'] = sum(url_data['request_times']) / len(url_data['request_times'])
            data_item['time_max'] = max(url_data['request_times'])
            data_item['time_med'] = statistics.median(url_data['request_times'])

            self.processed_data.append(data_item)

    def _log_parser(self, file_obj: TextIO) -> Optional[Match[AnyStr]]:
        while True:
            data = file_obj.readline()
            if not data:
                break
            res = self._pattern.search(data)
            if res:
                self.status_len[0] += 1
                yield res
            else:
                self.status_len[1] += 1
