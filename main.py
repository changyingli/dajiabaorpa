# coding=utf8

# import json
import logging
import psutil
# import queue
# import requests
import sys
import time
import threading
import types
from subprocess import run as prun
from pathlib import Path

from wechat import WeChat
from baoxianrpa import BaoxianWeChatRpa

logger = logging.getLogger(__name__)


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\':
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False
def init_log():
    log_dir = Path('log')
    if not log_dir.exists():
        log_dir.mkdir()
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s', handlers=[
        logging.StreamHandler(),
        logging.FileHandler(filename='./log/rpa.log', encoding='utf8')
    ])

def get_pid(pname):
    for proc in psutil.process_iter():
        #print(“pid-%d,name:%s” % (proc.pid,proc.name()))
        if proc.name() == pname:
            return proc.pid

def main():
    init_log()

    username = input('请输入保单系统登录用户名[使用默认值请直接回车]：')
    if not username:
        username = '1231130012'
    password = input('请输入登录密码[使用默认值请直接回车]：')
    if not password:
        password='tesla2020'

    pid = get_pid('WeChat.exe')
    if pid:
        logger.info(f'existing WetChat process:{pid}')
        wechat = WeChat(process=pid)
    else:
        logger.info('Kill existing WetChat process.')
        prun(['taskkill', '/f', '/t', '/im', 'WeChat.exe'])
        wechat = WeChat()
        wechat.win_login.wait('ready', 5)
        print('请登录微信...')
        with Spinner():
            while wechat.win_login.exists():
                time.sleep(2)
    wechat.win_main.wait('ready', 5)
    # wechat.win_main.maximize()
    try:
        rpa = BaoxianWeChatRpa(wechat=wechat, username=username, password=password)
        rpa.loop()
    except:
        logger.exception('Exception in main func entry.')

    # logger.info('Kill WetChat process.')
    # prun(['taskkill', '/f', '/t', '/im', 'WeChat.exe'])


if __name__ == "__main__":
    main()
