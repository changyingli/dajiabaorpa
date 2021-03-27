import os
import logging
import threading
from datetime import datetime
from datetime import timedelta

import settings

logger = logging.getLogger(__name__)
class CleanFile:
    """定时清理文件夹保存的文件
    Args:
        dir_path: 文件路径或者文件夹路径
    """

    def __init__(self):
        self._should_clean = False
        self._set_next_clean_time()
        self._timer = None

    def _set_next_clean_time(self):
        """设置下次报告时间
        """
        now = datetime.now()
        next_time = datetime.combine(
            date=now.date(), time=settings.CLEAN_TIME) # 晚上十一点半清理
        if now + timedelta(seconds=20) > next_time:
            next_time += timedelta(days=1)
        logger.info('Next clean file time: %s', next_time)
        delta = next_time - now

        def _set_should_clean():
            self._should_clean = True
        self._timer = threading.Timer(interval=delta.total_seconds(), function=_set_should_clean)
        self._timer.daemon = True
        self._timer.start()

    def start_clean(self,dir_path):
        if not self._should_clean:
            return
        self._should_clean = False
        self._set_next_clean_time()
        logger.info('Start clean file.')
        self.del_files(dir_path)

    def del_files(self,dir_path):
        if os.path.isfile(dir_path):
            try:
                os.remove(dir_path)
            except:
                logger.warning('del_files err in :%s',dir_path)
        elif os.path.isdir(dir_path):
            file_lis = os.listdir(dir_path)
            for file_name in file_lis:
                # if file_name != 'rpa.log':
                tf = os.path.join(dir_path, file_name)
                self.del_files(tf)