from selenium.webdriver.support.ui import WebDriverWait

class WebDriverHelper:
    def __init__(self, driver, timeout):
        self._driverwait = WebDriverWait(driver, timeout)
    
    def until_find_element(self, by, value):
        return self._driverwait.until(lambda d: d.find_element(by, value))

    def until_find_elements(self, by, value):
        return self._driverwait.until(lambda d: d.find_elements(by, value))