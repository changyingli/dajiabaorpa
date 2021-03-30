import logging
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import webdriverhelper

logger = logging.getLogger(__name__)

class LoadingDlg:
    """加载对话框，如点击车型查询后的白屏"""
    def __init__(self, driver):
        self.driver = driver
        self.driverwait = webdriverhelper.WebDriverHelper(driver, 2)
        self.root = None

    def exists(self, timeout=2.0):
        if self.root:
            return True
        try:
            # self.root = WebDriverWait(self.driver, timeout).until(
            #     EC.presence_of_element_located(
            #         (By.CLASS_NAME, 'el-loading-mask is-fullscreen')))

            # 这样才行，上面的不行，气死了....
            self.root = self.driverwait.until_find_element(By.XPATH, '//*[@class="el-loading-mask is-fullscreen"]')
        except TimeoutException:
            return False
        return True

    def wait_for_disappear(self, timeout=10.0):
        if self.exists():
            print('LoadingDlg 35')
            print(self.root.get_attribute('display'))
            # 界面里面始终有一个，不能用这个
            # WebDriverWait(self.driver,timeout).until(EC.staleness_of(self.root))


class WarningDlg:
    """提醒对话框"""
    def __init__(self, driver):
        self.driver = driver
        self.driverwait = webdriverhelper.WebDriverHelper(driver, 2)
        self.root = None

    def exists(self, timeout=2.0):
        if self.root:
            return True
        try:
            # self.root = WebDriverWait(self.driver, timeout).until(
            #     EC.presence_of_element_located(
            #         (By.CLASS_NAME, 'el-message el-message--warning is-closable')))

            # 这样才行，上面的不行，气死了....
            self.root = self.driverwait.until_find_element(By.XPATH,'//*[@class="el-message el-message--warning is-closable"]')
        except TimeoutException:
            return False
        return True

    def get_content(self) -> str:
        return self.root.find_element_by_class_name('el-message__content').text

    def close(self):
        # elem = self.root.find_element_by_class_name('el-message__closeBtn el-icon-close')

        # 上面的这种查找方法竟然也不行，get_content那里却可以，你说气不气？？？
        elems = self.root.find_elements_by_tag_name('i')
        elem = elems[1]
        self.driver.execute_script("arguments[0].click()", elem)
        # self.wait_for_disappear()

    def wait_for_disappear(self, timeout=10.0):
        if self.exists():
            WebDriverWait(self.driver,timeout).until(EC.staleness_of(self.root))
            # 等待元素不再存在于DOM


class ErrorMsgDlg:
    """失败或错误提示对话框"""
    def __init__(self, driver):
        self.driver = driver
        self.driverwait = webdriverhelper.WebDriverHelper(driver, 2)
        self.root = None

    def exists(self, timeout=3.0):
        if self.root:
            return True
        try:
            # self.root = WebDriverWait(self.driver, timeout).until(EC.presence_of_element_located((By.CLASS_NAME, 'el-message el-message--error is-closable')))

            # 这样才行，上面的不行，气死了....
            self.root = self.driverwait.until_find_element(By.XPATH,'//*[@class="el-message el-message--error is-closable"]')
            print('zhaodaole747474')
        except TimeoutException:
            print(75,'meidengdao ')
            return False
        return True

    def get_content(self) -> str:
        return self.root.find_element_by_class_name('el-message__content').text

    def close(self):
        # elem = self.root.find_elements_by__name('el-message__closeBtn el-icon-close')

        # 上面的这种查找方法竟然也不行，get_content那里却可以，你说气不气？？？
        elems = self.root.find_elements_by_tag_name('i')
        elem = elems[1]
        # elem.click()
        self.driver.execute_script("arguments[0].click()", elem)
        # self.wait_for_disappear()

    def wait_for_disappear(self, timeout=10.0):
        if self.exists():
            WebDriverWait(self.driver,timeout).until(EC.staleness_of(self.root))
            # 等待元素不再存在于DOM


class SuccessMsgDlg:
    """成功提示对话框"""
    def __init__(self, driver):
        self.driver = driver
        self.driverwait = webdriverhelper.WebDriverHelper(driver, 2)
        self.root = None

    def exists(self, timeout=2.0):
        if self.root:
            return True
        try:
            # self.root = WebDriverWait(self.driver, timeout).until(
            #     EC.presence_of_element_located((By.CLASS_NAME, 'el-message el-message--success is-closable')))
            # 这样才行，上面的不行，气死了....
            self.root = self.driverwait.until_find_element(By.XPATH,
                                                           '//*[@class="el-message el-message--success is-closable"]')
        except TimeoutException:
            print(106,'meizhaodao ')
            return False
        return True

    def get_content(self) -> str:
        return self.root.find_element_by_class_name('el-message__content').text

    def close(self):
        # elem = self.root.find_element_by_class_name('el-message__closeBtn el-icon-close')

        # 上面的这种查找方法竟然也不行，get_content那里却可以，你说气不气？？？
        elems = self.root.find_elements_by_tag_name('i')
        elem = elems[1]
        self.driver.execute_script("arguments[0].click()", elem)
        # self.wait_for_disappear()

    def wait_for_disappear(self, timeout=10.0):
        if self.exists():
            WebDriverWait(self.driver, timeout).until(EC.staleness_of(self.root))


class NoticeDialog:
    """alert弹窗
    """
    def __init__(self, driver):
        self.driver = driver
        self.alert = None

    def exists(self, timeout=5):
        try:
            WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            return True
        except:
            print('no alert')
            return False

    def switch_to(self):
        self.alert = self.driver.switch_to.alert

    def cancel(self):
        self.alert.dismiss()

    def confirm(self):
        self.alert.accept()

    def send_keys(self, key):
        self.alert.send_keys(key)

    @property
    def detail_text(self):
        return self.alert.text