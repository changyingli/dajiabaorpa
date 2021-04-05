import random
import shutil
import string
from pathlib import Path

class TaskFileMgr:
    def __init__(self, base_dir):
        self.__basedir = Path(base_dir).absolute()
    
    def clean(self):
        shutil.rmtree(str(self.__basedir), ignore_errors=True)

    def create_task_dir(self, task_id):
        task_dir = self.__basedir / f'task_{task_id}'
        if not task_dir.exists():
            task_dir.mkdir(parents=True)
        return task_dir
    
    def new_task_file_name(self, task_id: int, suffix: str) -> str:
        task_dir = self.create_task_dir(task_id)
        filename = None
        while True:
            name = ''.join([random.choice(string.ascii_lowercase) for _ in range(10)])
            filename = task_dir / Path(name).with_suffix(suffix)
            if not filename.exists():
                break
        return str(filename)

class ScreenShotMgr:
    def __init__(self, base_dir:str):
        self.__basedir = Path(base_dir).absolute()
        self.mkdir()

    def mkdir(self):
        if not self.__basedir.exists():
            # shutil.rmtree(str(self.__basedir))
            self.__basedir.mkdir(parents=True)
    
    def new_screenshot_path(self) -> str:
        filename = None
        while True:
            name = ''.join([random.choice(string.ascii_lowercase) for _ in range(10)])
            filename = self.__basedir / Path(name).with_suffix('.png')
            if not filename.exists():
                break
        return str(filename)

    new_screenshot_name = new_screenshot_path

class WeChatFilePath:
    def __init__(self, base_dir):
        self.__basedir = Path(base_dir).absolute()

    def mkdir(self):
        if not self.__basedir.exists():
            # shutil.rmtree(str(self.__basedir), ignore_errors=True)
            self.__basedir.mkdir(parents=True)
        
    def unique_file_path(self, suffix: str) -> str:
        filename = None
        while True:
            name = ''.join([random.choice(string.ascii_lowercase) for _ in range(10)])
            filename = self.__basedir / Path(name).with_suffix(suffix)
            if not filename.exists():
                break
        return str(filename)
