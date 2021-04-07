# coding=utf8
from subprocess import run as prun
from datetime import datetime, date, timedelta
from io import StringIO
import logging
import json
import os
import re

import cpca
import keyboard
import requests
import time
import psutil
import tempfile
from pathlib import Path
from zipfile import ZipFile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.wait import WebDriverWait, TimeoutException
from selenium.webdriver.support import expected_conditions as EC


from pywinauto.application import Application

import script
import dialog
import settings
import webdriverhelper
import msg as strings
import errors
from file import ScreenShotMgr
from settings import PLANS



logger = logging.getLogger(__name__)


def entry_wrap(func):
    """wrap函数。处理函数的异常。如异常会截图，并返回:

        {'error': code, 'msg': error_message, 'screenshot': screenshot_file_path}

    如果正常，则返回:

        {'content': function_return_value }
    """
    def wrapper(*args, **kwargs):
        this = args[0]
        try:
            content = func(*args, **kwargs)
            result = {'content': content}
        except errors.RpaError as err:
            logger.exception('Exception.')
            result = {'error': err.error, 'msg': err.message}
        except:
            logger.exception('Exception.')
            result = {'error': errors.E_UNKOWN, 'msg': strings.err_unknown}

        if 'error' in result:
            try:
                error_screenshot = this.screenshot_mgr.new_screenshot_name()
                this.driver.save_screenshot(error_screenshot)
                result['screenshot'] = error_screenshot
                logger.error('Screenshot is %s', error_screenshot)
            except:
                pass

        this.close()
        return result

    return wrapper

class ChromeAuto:
    def __init__(self, process=None):
        self.app = None
        self._start(process=process)

    def _start(self, process=None):
        if process:
            self.app = Application(backend='uia').connect(process=process)
        else:
            logger.debug(f'ChromeAuto _start err')

    def send_file(self,file_path):
        keyboard.write(file_path.strip())
        keyboard.send('enter')

class DajiabaoWeb:
    #登录网址
    URL = "https://xkscd.djbx.com:9080/pc_vir/login?redirect=%2Fhome"
    # 验证码地址
    CAPT_RECOG_URL = 'http://api.wisight.cn/v1/vcode_t1?appsecret=AAAaaa123'
    # 下载等待时间
    DOWNLOAD_WAIT_TIME = 2*60

    def __init__(self, screenshotmgr=None, username='00000020', password='admin123'):
        self.driver = None
        self.driverwait = None
        if screenshotmgr is None:
            screenshotmgr = ScreenShotMgr('log/screenshot_baoxianweb/')
        self.screenshot_mgr = screenshotmgr
        self.username = username
        self.password = password

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info('quit driver.')

    # 给浏览器设置参数，并打开网页
    def open(self, url=None, download_dir=None):
        logger.info('Kill existing chrome process.')
        prun(['taskkill', '/f', '/t', '/im', 'chrome.exe'])

        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        if download_dir:
            preference = {'download.default_directory': download_dir,
                          "safebrowsing.enabled": "false",
                          }
            options.add_experimental_option('prefs', preference) # google

        driver_path = './driver/chrome/chromedriver.exe' if os.name == 'nt' else './driver/chrome/chromedriver'

        self.driver = webdriver.Chrome(driver_path, options=options)
        logger.info('start chrome driver.')

        # 自己写的带有等待功能的查找方法类
        self.driverwait = webdriverhelper.WebDriverHelper(self.driver, 10)
        if url:
            self.driver.get(url)
        else:
            self.driver.get(self.URL)
        self.driver.maximize_window()
        time.sleep(1)  # sometimes driver connection refused. try sleep

        # IE操作
        # options = webdriver.IeOptions()
        # options.add_argument('--start-maximized')
        # if download_dir:
        #     preference = {'download.default_directory': download_dir,
        #                   "safebrowsing.enabled": "false"}
        #     options.add_additional_option('prefs', preference)  # ie
        # self.driver = webdriver.Ie(executable_path='driver/ie/IEDriverServer.exe')
        # logger.info('start IE driver.')
        # # 自己写的带有等待功能的查找方法类
        # self.driverwait = webdriverhelper.WebDriverHelper(self.driver, 10)
        # if url:
        #     self.driver.get(url)
        # else:
        #     self.driver.get(self.URL)
        # # 解决IE提示此站点不安全->转到此网页
        # self.driver.get("javascript:document.getElementById('overridelink').click();")
        # self.driver.maximize_window()
        # time.sleep(1)  # sometimes driver connection refused. try sleep

    def login(self, organization):
        elem = self.driver.find_element_by_id('username')
        elem.clear()
        elem.send_keys(self.username)
        # self.driver.execute_script('arguments[0].value="{}";'.format(self.username), elem)
        elem = self.driver.find_element_by_id('password')
        elem.send_keys(Keys.CONTROL,"a")
        elem.send_keys(self.password)
        # self.driver.execute_script('arguments[0].value="{}";'.format(self.password), elem)

        # TODO 内网环境不支持验证码识别，暂时先用这个，后续需要另外提供方案，如登陆一次不再关闭
        for _ in range(10):
            capcha = self.driverwait.until_find_element(By.XPATH, '//*[@class="imgVerification"]')

            # 直接下载
            # capcha_url = capcha.get_attribute('src')
            # rsp = requests.get(capcha_url)
            # capt_path = self.screenshot_mgr.new_screenshot_name()
            # open(capt_path, 'wb').write(rsp.content)

           # 截图
            capt_path = self.screenshot_mgr.new_screenshot_name()
            capcha.screenshot(capt_path) # 自带方法，截图保存
            if not Path(capt_path).exists():
                logger.info('Cannot screenshot capcha image, try again.')
                self.driver.get(self.URL)
                time.sleep(1)
                continue
            capt_result = None
            with open(capt_path, 'rb') as fp:
                ret = requests.post(self.CAPT_RECOG_URL,
                                    files={'imagefile': fp})
                logger.info('Captcha recognization request reply: %s', ret)
                result = ret.json()
                logger.info(f'recogniz result:{result}')
                if (result['retcode']) != 0:
                    logger.error(
                        'captcha recognization result code %d is not zero.', result['retcode'])
                    logger.info('refresh captcha code.')
                    capcha.click()
                    time.sleep(3)
                    continue
                else:
                    capt_result = result['result']
                    logger.info('captcha result is %s', capt_result)
            # capt_result = '0'
            if capt_result:
                # 验证码错误一次，密码会自动被修改，需要重新输入
                elem = self.driver.find_element_by_id('password')
                elem.send_keys(Keys.CONTROL, "a")
                elem.send_keys(self.password)

                self.driver.find_element_by_id('checkCode').send_keys(capt_result)
                time.sleep(1)
                self.driver.find_element_by_id('loginBtn').click()
                try:
                    elem =  self.driverwait.until_find_element(By.ID, 'loginCompleteCode')

                    # 选择机构
                    # elem = self.driver.find_element_by_id('loginCompleteCode')
                    elem.send_keys(organization)
                    # li式的下拉选择框，先输入关键词，然后等待对应的li元素加载出来后再点击
                    # elem = self.driverwait.until_find_element(By.XPATH, '//span[contains(text(),"05--浙江分公司")]')
                    elem = self.driverwait.until_find_element(By.XPATH, f'//span[contains(text(),"{organization}")]')
                    self.driver.execute_script("arguments[0].click()", elem)
                    time.sleep(2)
                    # 首页
                    elem = self.driver.find_element_by_xpath('//li[@class="el-menu-item is-active submenu-title-noDropdown"]')
                    elem.click()
                    break
                except:
                    pass
        else:
            logger.error('Wrong captcha result when logging.')

    def goto_category_page(self, category):
        """进入车险投保、保单查询界面
        """
        # 首页
        elem = self.driver.find_element_by_xpath('//li[@class="el-menu-item is-active submenu-title-noDropdown"]')
        elem.click()
        # 车险投保、保单查询
        # elem = self.driver.find_element_by_xpath(f'//span[../div][contains(text(),"{category}")]')
        elem = self.driverwait.until_find_element(By.XPATH,f'//span[../div][contains(text(),"{category}")]')
        elem.click()
        # 等待元素消失
        WebDriverWait(self.driver, 3).until(EC.invisibility_of_element(elem))

    def fill_header_info(self, data):
        """填写头部机构、代理人、业务来源等信息
        """
        # organization_code = data['organization_code']
        # agent_code = data['agent_code']
        # 浙江
        organization_code = '05700205'
        agent_code = '105002267'
        # # 上海
        # organization_code = '03000063'
        # agent_code = '103005701'
        # 点击承保机构
        elem = self.driver.find_element_by_xpath("//span[../div/descendant::input[@id='insuranceChannelInfoUnderwritingAgency']]")
        self.driver.execute_script("arguments[0].click()", elem)
        # 等待出现 请选择 侧边区
        self.driverwait.until_find_element(By.XPATH, "//div[@class='el-table__fixed-right']")
        # 输入机构代码
        elem = self.driver.find_element_by_xpath("//input[../../../../label[contains(text(),'机构代码')]]")
        elem.send_keys(organization_code)
        # self.driver.execute_script('arguments[0].value="{}";'.format(organization_code), elem) # 这样会造成查询点击后无反应
        # 查询
        self.driver.find_element_by_id('underwritingAgencyDialogSearch').click()
        # 选择
        elem = self.driverwait.until_find_element(By.XPATH, f"// button[.. /../../ td / div[contains(text(), '{organization_code}')]][ancestor::div[@class='el-table__fixed-right']]")
        self.driver.execute_script("arguments[0].click()", elem)

        # 业务来源
        elem = self.driver.find_element_by_id('insuranceChannelInfoBusinessSource')
        self.driver.execute_script("arguments[0].click()", elem)
        elem = self.driverwait.until_find_element(By.XPATH, '//span[contains(text(),"19007--个人代理")]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 点击代理人 要点击最上面的span，点击input不行
        elem = self.driver.find_element_by_xpath('//div[@class="el-form-item__content"][./descendant::input[@id="insuranceChannelInfoDeputy"]]/span')
        self.driver.execute_script("arguments[0].click()", elem)
        # 等待出现 请选择 侧边区
        self.driverwait.until_find_element(By.XPATH, "//div[@class='el-table__fixed-right']")
        # 输入代理人编码
        elem = self.driver.find_element_by_xpath("//input[../../../../label[contains(text(),'代理人编码')]]")
        elem.send_keys(agent_code)
        # 查询
        self.driver.find_element_by_id('deputyDialogSearch').click()
        # 选择 页面有两个，必须加多个筛选条件
        elem = self.driverwait.until_find_element(By.XPATH, f"//button[./../../../td/div[contains(text(),'{agent_code}')]][ancestor::div[@class='el-table__fixed-right']]")
        # elem.click()
        self.driver.execute_script("arguments[0].click()", elem)
        elem = self.driver.find_element_by_id('insuranceChannelInfoSalesPersonIdcard')
        for i in range(8):
            time.sleep(0.5)
            if elem.get_attribute('value'):
                break
        else:
            print("推荐人等信息未正常加载")
            raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_MSG_LOAD)

    def idcard_ocr(self, data):
        """身份证识别
        """
        files = data['files']
        for index,f in enumerate(files):
            file_path = f['path']
            self.driver.find_element_by_xpath('//div[./input[@id="insuranceCarOwncarOwnImgMessageOCR"]]').click()
            time.sleep(2)
            # 鼠标光标默认在文件路径输入框，直接输入，回车就好了
            keyboard.write(file_path.strip())
            keyboard.send('enter')
            # 等待查询结果出来
            elem = self.driver.find_element_by_xpath('//div[@id="insuranceCarOwnInfoSuffixAddr"]/div/input')
            for i in range(10):
                time.sleep(0.5)
                if elem.get_attribute('value'):
                    ownr_addr = elem.get_attribute('value')
                    elem = self.driver.find_element_by_xpath('//*[@id="insuranceCarOwnInfoIdentifyNumber"]/div/input')
                    card_id = elem.get_attribute('value')
                    elem = self.driver.find_element_by_xpath('//*[@id="insuranceCarOwnInfoCarOwnName"]/div/input')
                    owner_name = elem.get_attribute('value')
                    print([333, ownr_addr, card_id, owner_name])
                    data['身份证索引'] = index # 车辆识别的时候就不需要重复识别了
                    return [ownr_addr, card_id, owner_name]
                else:
                    print(342)
                    # time.sleep(3)
                    dlg = dialog.ErrorMsgDlg(self.driver)
                    if dlg.exists() and '识别失败' in dlg.get_content():
                        print(353, dlg.get_content())
                        logger.info(f'{dlg.get_content()}')
                        dlg.close()
                        # dlg.wait_for_disappear()
                        break
        else:
            print("身份证识别失败")
            raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_IDCARD_RECOGNIZE)

    def fill_car_owner_info(self, data):
        phone= data['手机']
        ownr_addr, card_id, owner_name = self.idcard_ocr(data)
        data['车主地址'] = ownr_addr
        data['身份证号'] = card_id
        data['车主姓名'] = owner_name
        # 省份代码 根据网页内容修改过省名
        province_dic = {'11': '北京', '12': '天津', '13': '河北', '14': '山西', '15': '内蒙古', '22': '吉林',
                        '23': '黑龙江', '31': '上海', '32': '江苏', '33': '浙江', '35': '福建', '36': '江西',
                        '37': '山东省', '41': '河南', '42': '湖北', '44': '广东', '45': '广西', '46': '海南',
                        '50': '重庆', '51': '四川', '53': '云南', '54': '西藏', '61': '陕西', '62': '甘肃',
                        '63': '青海', '65': '新疆', '71': '台湾', '81': '香港', '82': '澳门'}
        province = province_dic.get(card_id[0:2])

        # 第一步 选择省份--------------------------
        # 先点击省份div
        elem = self.driver.find_element_by_xpath('//div[./input[@id="insuranceCarOwnInfoProvince"]]')
        self.driver.execute_script("arguments[0].click()", elem)
        # 直到ul出现，readonly属性才会移除
        self.driverwait.until_find_element(By.XPATH,'/html/body/div[4]/div[1]/div[1]/ul')
        # 省份是身份证号省份代码匹取网页显示的各个省份得到的，不需要和网页内容再次对比
        # 输入 省份
        input_elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarOwnInfoProvince"]')
        input_elem.send_keys(province)
        # 等待目标li加载出来，点击选择
        elem = self.driverwait.until_find_element(By.XPATH, f'/html/body/div[4]/div[1]/div[1]/ul/li[contains(string(),"{province}")]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 识别 市 区 信息（有的身份证地址不显示区，如：江苏省常熟市虞山镇金枫家园 其实是 江苏 苏州市 常熟区）
        df = cpca.transform([ownr_addr, ])
        city = df.iat[0, 1].strip('市')
        area = df.iat[0, 2].strip('区')
        print(city, area)
        # 第二步 选择 市--------------------------
        # 先点击市div
        elem = self.driver.find_element_by_xpath('//div[./input[@id="insuranceCarOwnInfoCity"]]')
        self.driver.execute_script("arguments[0].click()", elem)
        # 直到ul出现，readonly属性才会移除
        ul_elem = self.driverwait.until_find_element(By.XPATH, '/html/body/div[5]/div[1]/div[1]/ul')
        # 市是模块识别的，要和网页内容再次对比，如网页市一级有： 余杭镇，这种情况我们分以下两步：
            #1.网页list和模块识别结果对比，如果in则选择
            #2.网页list和area完整家庭地址对比，如果in则选择
        li_items = ul_elem.find_elements_by_tag_name("li")
        city_list = [li.find_element_by_tag_name("span").text for li in li_items]
        print(city_list)
        the_city_list = [c  for c in city_list if c in city]
        if the_city_list:
            city = the_city_list[0]
        else:
            the_city_list = [c for c in city_list if c in ownr_addr]
            if the_city_list:
                city = the_city_list[0]
            else:
                raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CITY_MATCH)
        # 输入 市
        input_elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarOwnInfoCity"]')
        input_elem.send_keys(city)
        # 等待目标li加载出来，点击选择
        elem = self.driverwait.until_find_element(By.XPATH,
                                                  f'/html/body/div[5]/div[1]/div[1]/ul/li[contains(string(),"{city}")]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 第三步 选择 县城、区--------------------------
        # 先点击县城、区div
        elem = self.driver.find_element_by_xpath('//div[./input[@id="insuranceCarOwnInfoCount"]]')
        self.driver.execute_script("arguments[0].click()", elem)
        # 直到ul出现，readonly属性才会移除
        ul_elem = self.driverwait.until_find_element(By.XPATH, '/html/body/div[6]/div[1]/div[1]/ul')
        # 市是模块识别的，要和网页内容再次对比，如 杭州市西湖区求是村，但网页上区只有杭州，没有西湖区，这种情况我们分以下两步：
        # 1.网页list和模块识别结果对比，如果in则选择
        # 2.网页list和area完整家庭地址对比，如果in则选择
        li_items = ul_elem.find_elements_by_tag_name("li")
        area_list = [li.find_element_by_tag_name("span").text for li in li_items]
        print(417,area_list)
        the_area_list = [a for a in area_list if a in area]
        if the_area_list:
            area = the_area_list[0]
        else:
            the_area_list = [a for a in area_list if a in ownr_addr]
            if the_area_list:
                area = the_city_list[0]
            else:
                raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_AREA_MATCH)
        # 输入 县/区
        input_elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarOwnInfoCount"]')
        input_elem.send_keys(area)
        # 等待目标li加载出来，点击选择
        elem = self.driverwait.until_find_element(By.XPATH,
                                                  f'/html/body/div[6]/div[1]/div[1]/ul/li[contains(string(),"{area}")]')
        self.driver.execute_script("arguments[0].click()", elem)
        elem = self.driver.find_element_by_xpath('//label[contains(string(),"车主地址")]')
        elem.click()

        # 选择后，车主通讯地址会变化，重新输入一下
        elem = self.driver.find_element_by_xpath('//div[@id="insuranceCarOwnInfoComAddress"]/div/input')
        elem.send_keys(Keys.CONTROL, "a")
        elem.send_keys(ownr_addr)


        # 输入手机号、确认客户
        phone_elem = self.driver.find_element_by_xpath('//*[@id="insuranceCarOwnInfoMobile"]/div/input')
        phone_elem.send_keys(phone)
        comfirm_elem = self.driver.find_element_by_xpath('//*[@id="insuranceCarOwnInfoClientConfirm"]')
        comfirm_elem.click()
        # self.driver.execute_script("arguments[0].click()", comfirm_elem)

        self.handle_success_dlg(timeout=5)
        err_msg = self.handle_err_dlg(timeout=0.5)
        if err_msg:
            raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CUSTOMER_CONFIRM.format(err_msg))

        # dlg_success = dialog.SuccessMsgDlg(self.driver)
        # dlg_fail = dialog.ErrorMsgDlg(self.driver)
        # for i in range(10):
        #     if not dlg_success.exists():
        #         print(457)
        #         time.sleep(0.5)
        # if dlg_success.exists():
        #     logger.info(f'{dlg_success.get_content()}')
        #     dlg_success.close()
        # if dlg_fail.exists(timeout=0.5):
        #     err_msg = dlg_fail.get_content()
        #     raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CUSTOMER_CONFIRM.format(err_msg))

    def car_info_ocr(self, data):
        """识别行驶证,得到车辆相关各种信息
        """
        # 滚动页面至车辆信息位置可见且合适
        input_elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarOwnInfoCity"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", input_elem)
        # files = [
        #         {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\身份证.jpg'},
        #          {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\行驶证.jpg'},]
        # files = [{'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\行驶证.jpg'}, ]
        files = data['files']
        for index,f in enumerate(files):
            # 不要重复识别
            if index == data['身份证索引']:
                continue
            print(463,f)
            file_path = f['path']
            # 点击识别按钮
            # 下面三项，会偶尔阻塞超长25秒左右，js点击很快
            # 点击 车辆识别按钮
            # elem = self.driver.find_element_by_xpath('//div[@class="isPlate"][../div[@id="insuranceCarInfoLicensePlateNumber"]]')
            # elem.click()
            elem = self.driver.find_element_by_xpath('//div[@class="isPlate"][../div[@id="insuranceCarInfoLicensePlateNumber"]]/a/img')
            self.driver.execute_script("arguments[0].click()", elem)
            t = time.time()
            # 一期只做行驶证，默认的就是
            # elem = self.driverwait.until_find_element(By.XPATH, '//span[text()="行驶证"]/..')
            # print(489,time.time()-t)
            # time.sleep(0.5)
            # self.driver.execute_script("arguments[0].click()", elem)

            elem = self.driverwait.until_find_element(By.XPATH, '//input[@id="carOcrInput"]/../button[./span[text()="确认"]]')
            # elem = self.driver.find_element_by_xpath('//input[@id="carOcrInput"]/../button[./span[text()="确认"]]')
            # time.sleep(0.5)
            # self.driver.execute_script("arguments[0].click()", elem)
            elem.click()
            print(499, time.time()-t)
            time.sleep(2)
            # 鼠标光标默认在文件路径输入框，直接输入，回车就好了
            keyboard.write(file_path.strip())
            keyboard.send('enter')
            # 等待查询结果出来
            vin_input = self.driver.find_element_by_xpath('//div[@id="insuranceCarInfoFrameNumber"]/div/input')
            licence_input = self.driver.find_element_by_xpath('//div[@id="insuranceCarInfoLicensePlateNumber"]/div/input')
            engine_input = self.driver.find_element_by_xpath('//div[@id="insuranceCarInfoNegineNumber"]/div/input')
            for i in range(5):
                print(483,i)
                time.sleep(0.5)
                if vin_input.get_attribute('value') and licence_input.get_attribute('value') and engine_input.get_attribute('value'):
                    print(486)
                    vin = vin_input.get_attribute('value')
                    car_licens_num = licence_input.get_attribute('value')
                    engine_num = engine_input.get_attribute('value')
                    first_regist_date = self.driver.find_element_by_xpath('//input[@id="insuranceCarInfoFirstRegistDate"]').get_attribute('value')
                    model = self.driver.find_element_by_xpath('//div[@id="insuranceCarInfoBrand"]/div/input').get_attribute('value')
                    ret_dict = {'车架号':vin, '车牌号码':car_licens_num, '发动机号':engine_num, '初登日期':first_regist_date, '厂牌型号':model,}
                    logging.info(f"car_info_ocr :{ret_dict}")
                    return ret_dict
                else:
                    print(496)
                    if self.handle_err_dlg():
                        break
                    if self.handle_warning_dlg():
                        break
                    print(534)

                    # dlg = dialog.ErrorMsgDlg(self.driver)
                    # if dlg.exists():
                    #     logger.info(f'{dlg.get_content()}')
                    #     print(493,dlg.get_content())
                    #     dlg.close()
                    #     print("11行驶证识别失败")
                    #     break
                    #
                    # dlg = dialog.WarningDlg(self.driver)
                    # print(530)
                    # if dlg.exists():
                    #     logger.info(f'{dlg.get_content()}')
                    #     print(511, dlg.get_content())
                    #     dlg.close()
                    #     break
        else:
            print("行驶证识别失败")
            raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CAR_INFO_RECOGNIZE)

    def search_car_model(self,data):
        """车型查询界面处理
        """
        # 点击 车型
        t=time.time()
        elem = self.driver.find_element_by_xpath('//button[@id="insuranceCarInfoMotorcycleType"]')
        self.driver.execute_script("arguments[0].click()", elem)
        print(536,time.time()-t)
        self.handle_warning_dlg(timeout=5)
        self.handle_err_dlg(timeout=1)

        # # 直接点击 查询
        # search_elem = self.driverwait.until_find_element(By.ID,"motorcycleTypeDialogSearch")
        # search_elem.click()
        # # 网络延迟可能会出现较长时间的白屏加载界面
        # time.sleep(3)
        # # 如果没默认的 车型 查询不到，会报错，我们处理车型再次查询
        # dlg = dialog.ErrorMsgDlg(self.driver)
        # dlg2 = dialog.WarningDlg(self.driver)
        # if dlg.exists() or dlg2.exists():
        #     print(508508)
        #     model = data['厂牌型号']
        #     model_re = re.search('[0-9A-Za-z]{1,}', model)
        #     if model_re:
        #         model = model_re.group()  # 如：'明锐牌SVW7206FPD'需要变成'SVW7206FPD'，内容才能查询得到
        #     input_elem = self.driver.find_element_by_xpath("//label[text()='车型名称:']/../descendant::input")
        #     print(517,model)
        #     input_elem.send_keys(Keys.CONTROL, "a")
        #     # elem.clear() # 这个不行会报错
        #     input_elem.send_keys(model)
        #     search_elem.click()

        # 去除车型中的汉字
        model = data['厂牌型号']
        model_re = re.search('[0-9A-Za-z]{1,}', model)
        if model_re:
            model = model_re.group()  # 如：'明锐牌SVW7206FPD'需要变成'SVW7206FPD'，内容才能查询得到
        input_elem = self.driverwait.until_find_element(By.XPATH, "//label[text()='车型名称:']/../descendant::input")
        print(517, model)
        input_elem.send_keys(Keys.CONTROL, "a")
        # elem.clear() # 这个不行会报错
        input_elem.send_keys(model)
        search_elem = self.driverwait.until_find_element(By.ID, "motorcycleTypeDialogSearch")
        search_elem.click()
        # 网络延迟可能会出现较长时间的白屏加载界面
        # dialog.LoadingDlg(self.driver).wait_for_disappear() # 用这个会出错，本身就是个大提醒窗口，不可能消失的
        time.sleep(4)

        time_index = ''
        price_index = ''
        select_index = ''
        # head_tr1和head_tr2 网页看上去是一样的，但是head_tr2只能获取到th.text='操作'，head_tr1中可以获取到其他的表头，莫名其妙？？？？
        head_tr1 = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'新车购置价')][ancestor::div[@class='el-table__header-wrapper']]")
        head_th_list1 = head_tr1.find_elements_by_tag_name('th')
        for th in head_th_list1:
            print(th.text)
            if '上市年月' in th.text:
                time_index = head_th_list1.index(th)
            elif '新车购置价' in th.text:
                price_index = head_th_list1.index(th)
        head_tr2 = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'新车购置价')][ancestor::div[@class='el-table__fixed-right']]")
        head_th_list = head_tr2.find_elements_by_tag_name('th')
        for th in head_th_list:
            if '操作' in th.text:
                select_index = head_th_list.index(th)
        if not (time_index and price_index and select_index):
            print(571, time_index, price_index, select_index)
            time_index = 8
            price_index = 9
            select_index = 16

        print(566,time_index,price_index,select_index)
        # 必须等待tr加载出来，主界面有tbody但是为空，需要等待他下面的tr加载出来
        self.driverwait.until_find_elements(By.XPATH, "//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__header-wrapper']/../div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr")
        # tbody_elem = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__fixed-right']/div[@class='el-table__fixed-body-wrapper']/table/tbody")
        tbody_elem = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__header-wrapper']/../div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody")
        # tbody_elem = self.driver.find_element_by_xpath("//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__fixed-right']/div[@class='el-table__fixed-body-wrapper']/table/tbody")
        tr_list = tbody_elem.find_elements_by_tag_name('tr')

        time_list = []
        price_list = []
        for tr in tr_list:
            time_list.append(tr.find_elements_by_tag_name('td')[time_index].text)
            price_list.append(tr.find_elements_by_tag_name('td')[price_index].text)
        # 将初等日期 2021-03-25 变成 20210325
        first_regist_date = data['初登日期'].replace('-','')
        print(577, first_regist_date)
        print(577, time_list)
        print(577, price_list)
        # 价格排序
        # 必须是price_list.copy()或者深拷贝，不然price_list本身也会变！！！！！
        # 列表是可变类型，引用传递后会影响原列表，因为列表内容是不可变类型，浅拷贝就好了，如果列表项是可变就要用深拷贝
        sort_price_list = self.insert_sort(price_list.copy())
        print(595,sort_price_list)
        for price in sort_price_list:
            print(price)
            print(price_list)
            print(59,price_list.index(price))
            print(597,int(time_list[price_list.index(price)]))

            print(598,int(first_regist_date[0:6]))
            if int(time_list[price_list.index(price)]) <= int(first_regist_date[0:6]):
                fin_chose_index = price_list.index(price)
                fin_price = price
                print(583,price,fin_chose_index)
                break
        else:
            print('实在找不到。。。。。')

        # 操作-选择 一栏只能操作这里面的，这里面不能操作其他t-head项
        select_btn = self.driver.find_element_by_xpath(f"//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__fixed-right']/div[@class='el-table__fixed-body-wrapper']/table/tbody/tr[{fin_chose_index+1}]/td[{select_index + 1}]/div/button")
        select_btn.click()
        # 这样不行，这里面唯独不能操作 操作-选择 的内容
        # #select_btn = self.driver.find_element_by_xpath(f"//tr[contains(string(),'新车购置价' )]/ancestor::div[@class='el-table__header-wrapper']/../div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[{fin_chose_index+1}]/td[{select_index + 1}]/div/button")
        # #select_btn.click()

        # 等待查询结果出来,新车购置价 会加载
        locator = (By.ID, "insuranceCarInfoNewCarPurchasePrice")
        WebDriverWait(self.driver, 2).until(EC.text_to_be_present_in_element_value(locator, fin_price))

    def insert_sort(self, ilist):
        """列表排序
        """
        for i in range(len(ilist)):
            for j in range(i):
                if ilist[i] < ilist[j]:
                    ilist.insert(j, ilist.pop(i))
                    break
        return ilist

    def fill_car_info(self, data):
        """车辆信息填写
        """
        car_info_dict = self.car_info_ocr(data)
        data.update(car_info_dict)
        self.search_car_model(data)

        # 使用性质++++++++++++++++++++++++++++++++++++++
        nature_of_use = '家庭自用客车'
        if data.get('使用性质'):
            nature_of_use = settings.NATURE_OF_USE[data.get('使用性质').upper()]
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarInfoNatureOfUsage"]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 获取列表，后续使用
        elem1 = self.driverwait.until_find_element(By.XPATH,f'//li[contains(string(),"{nature_of_use}")]/..')
        # text_list = []
        # for li in elem1.find_elements_by_tag_name('li'):
        #     text_list.append(li.text)
        # print(text_list)
        # NATURE_OF_USE = {}
        # for index,li in enumerate(elem1.find_elements_by_tag_name('li')):
        #     NATURE_OF_USE[f'A{index}'] = li.text
        # print(NATURE_OF_USE)

        # 方式一 直接js设值，虽然可以成功，但是会造成后面相关选项不会自动正常加载，不行
        # self.driver.execute_script('arguments[0].value="{}";'.format(nature_of_use), elem)
        # 方式二 点选的方式
        elem.send_keys(nature_of_use)
        elem = self.driverwait.until_find_element(By.XPATH,f'//li[contains(string(),"{nature_of_use}")]')
        elem.click()
        # self.driver.execute_script("arguments[0].click()", elem) # li选项JS点击加载不了，不行

        # 行车证车辆++++++++++++++++++++++++++++++++++++++
        liceense_vehicle = 'K33'
        if data.get('行车证车辆'):
            liceense_vehicle = data.get('行车证车辆').upper()
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarInfoMotorType"]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 动态获取列表项，合成大字典，指令匹配
        # elem1 = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{liceense_vehicle}")]/..')
        # text_dict = {}
        # for li in elem1.find_elements_by_tag_name('li'):
        #     text_dict[li.text[0:3]]= li.text
        # print(text_dict)
        # liceense_vehicle = text_dict[liceense_vehicle]

        liceense_vehicle = settings.LICEENSE_VEHICLE[liceense_vehicle]
        elem.send_keys(liceense_vehicle)
        elem = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{liceense_vehicle}")]')
        elem.click()

        # 能源类型++++++++++++++++++++++++++++++++++++++
        energy_type = '燃油'
        if data.get('燃料种类'):
            fule_type = data.get('燃料种类')
        # 使用性质
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarInfoEnergyType"]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 获取列表，TODO 这里其实要有一个对应规则，和燃料种类对应起来，暂时先做燃油
        elem1 = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"燃油")]/..')
        text_list = []
        for li in elem1.find_elements_by_tag_name('li'):
            text_list.append(li.text)
        print(text_list)

        elem.send_keys(energy_type)
        elem = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{energy_type}")]')
        elem.click()

        # 验车情况++++++++++++++++++++++++++++++++++++++
        elem = self.driver.find_element_by_xpath('//button[string()="验车信息"][ancestor::div[@class="el-form-item is-success is-required el-form-item--mini"]]')
        self.driver.execute_script("arguments[0].click()", elem)
        # time.sleep(1)
        # 选择 按期续保，未增加损失类险别
        elem = self.driverwait.until_find_element(By.XPATH,'//span[text()="按期续保，未增加损失类险别"]/../descendant::span')
        elem.click()
        # self.driver.execute_script('arguments[0].checked=true;', elem)
        # 确定
        elem = self.driver.find_element_by_xpath('//button[@id="insuranceCarInfoCarCheckConfirm"]')
        elem.click()
        # self.driver.execute_script('arguments[0].click();', elem)

    def vehicle_tax(self, data):
        """车船税
        """
        elem = self.driver.find_element_by_xpath(
            '//button[string()="验车信息"][ancestor::div[@class="el-form-item is-success is-required el-form-item--mini"]]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        elem = self.driverwait.until_find_element(By.XPATH,'//div[@id="insuranceCarboatCTaxpayerId"]/div/input')
        elem.send_keys(data['身份证号'])
        # 燃料种类
        fule_type = '汽油'
        if data.get('燃料种类'):
            fule_type = data.get('燃料种类')
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarboatFuelType"]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 获取列表，TODO 这里其实要有一个对应规则，和燃料种类对应起来，暂时先做燃油
        elem1 = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"汽油")]/..')
        text_list = []
        for li in elem1.find_elements_by_tag_name('li'):
            text_list.append(li.text)
        print(text_list)

        elem.send_keys(fule_type)
        elem = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{fule_type}")]')
        elem.click()

    def fill_insurance_plan(self, data):
        """商业险
        """
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarboatFuelType"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)

        plan = data['plan']
        logger.info('fill_insurance_plan  plan: %s', plan)
        if '车损' in plan:
            logger.info('fill_insurance_plan  车损')
            elem = self.driver.find_element(By.XPATH, '//span[text()="车辆损失险"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()
            # elem = self.driver.find_element(By.XPATH, '//span[text()="车辆损失险"]/ancestor::tr/td[1]/descendant::input')
            # self.driver.execute_script('arguments[0].checked=true;', elem)

            # 免赔额
            elem = self.driver.find_element(By.XPATH, '//span[text()="车辆损失险"]/ancestor::tr/td[4]/descendant::input')
            self.driver.execute_script("arguments[0].click()", elem)
            # 获取列表
            elem1 = self.driverwait.until_find_element(By.XPATH, f'//span[text()="300"]/ancestor::ul')
            text_list = []
            for li in elem1.find_elements_by_tag_name('li'):
                text_list.append(li.text)
            print(text_list)
            # 选择
            elem = self.driverwait.until_find_element(By.XPATH, f'//span[text()="300"]/ancestor::ul/descendant::li[contains(string(),"{plan["车损"]}")]')
            elem.click()

        if '三者' in plan:
            logger.info('fill_insurance_plan  三者: %s', plan['三者'])
            # self.driver.find_element(
            #     By.XPATH, "//tr[@id=\'thirdPartyCoverage\']/td/input").click()
            elem = self.driver.find_element(By.XPATH, '//span[text()="第三者责任险"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()

            # 免赔额
            elem = self.driver.find_element(By.XPATH, '//span[text()="第三者责任险"]/ancestor::tr/td[3]/descendant::input')
            self.driver.execute_script("arguments[0].click()", elem)
            # 获取列表
            elem1 = self.driverwait.until_find_element(By.XPATH, f'//span[text()="10万元"]/ancestor::ul')
            text_list = []
            for li in elem1.find_elements_by_tag_name('li'):
                text_list.append(li.text)
            print(850,text_list)

            elem = self.driver.find_element(By.XPATH, '//span[text()="第三者责任险"]/ancestor::tr/td[3]/descendant::input')
            elem.send_keys(plan["三者"])
            # 选择
            elem = self.driverwait.until_find_element(By.XPATH, f'//span[text()="10万元"]/ancestor::ul/descendant::li[contains(string(),"{plan["三者"]}万元")]')
            elem.click()

        if '司机' in plan:
            logger.info('fill_insurance_plan  司机: %s', plan['司机'])
            elem = self.driver.find_element(By.XPATH, '//span[text()="车上人员责任险驾驶人座位"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()

            elem = self.driver.find_element(By.XPATH, '//span[text()="车上人员责任险驾驶人座位"]/ancestor::tr/td[2]/descendant::input[3]')
            elem.send_keys(Keys.CONTROL, "a")
            elem.send_keys(plan["司机"])

        if '乘客' in plan:
            logger.info('fill_insurance_plan  乘客: %s', plan['乘客'])
            # elem = self.driver.find_element(By.XPATH, '//*[@id="checkbox8"]')
            elem = self.driver.find_element(By.XPATH, '//span[text()="车上人员责任险乘客座位"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()
            # self.driver.execute_script('arguments[0].checked=true;', elem)
            time.sleep(0.1)
            elem = self.driver.find_element(By.XPATH, '//span[text()="车上人员责任险乘客座位"]/ancestor::tr/td[2]/descendant::input[1]')
            elem.send_keys(Keys.CONTROL, "a")
            elem.send_keys(plan["乘客"])

        # 开始 附加险
        elem = self.driver.find_element(By.XPATH, '//span[text()="附加车轮单独损失险"]/ancestor::tr/td[1]/descendant::input/..')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        time.sleep(0.2)


        if '道路救援' in plan:
            logger.info('fill_insurance_plan  道路救援: %s', plan['道路救援'])
            elem = self.driverwait.until_find_element(By.XPATH, '//span[text()="道路救援服务特约条款"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()
            # self.driver.execute_script('arguments[0].checked=true;', elem)
            if plan['道路救援'] != 2: # 默认会刷新出2，就不需要设置了
                elem = self.driver.find_element(By.XPATH, '//span[text()="道路救援服务特约条款"]/ancestor::tr/td[3]/descendant::input')
                self.driver.execute_script("arguments[0].click()", elem)
                # 获取列表
                elem1 = self.driverwait.until_find_element(By.XPATH, f'//span[text()="2次"]/ancestor::ul')
                text_list = []
                for li in elem1.find_elements_by_tag_name('li'):
                    text_list.append(li.text)
                print('道路救援', text_list)
                # 选择
                elem = self.driverwait.until_find_element(By.XPATH, f'//span[text()="2次"]/ancestor::ul/descendant::li[contains(string(),"{plan["道路救援"]}次")]')
                elem.click()

        if '代为驾驶' in plan:
            elem = self.driver.find_element(By.XPATH, '//span[text()="代为驾驶服务特约条款"]/ancestor::tr/td[1]/descendant::input/..')
            elem.click()
            if plan['代为驾驶'] != 1: # 默认会刷新出1，就不需要设置了
                elem = self.driver.find_element(By.XPATH, '//span[text()="代为驾驶服务特约条款"]/ancestor::tr/td[3]/descendant::input')
                elem.send_keys(Keys.CONTROL, "a")
                elem.send_keys(plan["代为驾驶"])

        # 折扣系数
        elem = self.driver.find_element(By.XPATH, '//*[text()="交强险预期赔付率:"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        elem = self.driverwait.until_find_element(By.XPATH, '//input[@id="insuranceCoefficientBIInfoExpectedDiscountDoubleCoefficient"]')
        elem.send_keys(Keys.CONTROL, "a")
        elem.send_keys(str(plan["折扣系数"]))

    def policy_holder(self,data):
        """投保人、被保人资料
        """
        print(918,data)
        elem = self.driver.find_element(By.XPATH, '//input[@id="insuranceCoefficientBIInfoExpectedDiscountDoubleCoefficient"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        elem = self.driverwait.until_find_element(By.XPATH, '//span[text()="同车主"]/../span[1]')
        elem.click()
        # 等待加载
        locator = (By.XPATH, '//*[@id="insuranceApplicantInfoIdentifyNumber"]/div/input')
        text = data['身份证号']
        WebDriverWait(self.driver, 2).until(EC.text_to_be_present_in_element_value(locator, text))

        if data.get('证件有效期'):
            start_datetime = data['证件有效期']
            elem = self.driver.find_element(By.ID, 'insuranceApplicantInfoIdentifyEndDate')
            elem.send_keys(start_datetime)
            # self.driver.execute_script('arguments[0].value="{}";'.format(start_datetime), elem)
            elem.click()
            elem.send_keys(Keys.ENTER)
            time.sleep(0.5)
        else:
            # try:
            #     elem = self.driver.find_element(By.ID, 'insuranceApplicantInfoIdentifyEndDate')
            #     elem.send_keys('2021-12-12')
            #     print(940)
            # except:
            #     start_datetime = '2021-12-12'
            #     elem = self.driver.find_element(By.ID, 'insuranceApplicantInfoIdentifyEndDate')
            #     self.driver.execute_script('arguments[0].value="{}";'.format(start_datetime), elem)
            #     print(944)
            # 长期有效
            elem = self.driver.find_element(By.XPATH, '//span[text()="长期有效"]/../span[1]')
            elem.click()

        # 电子邮箱
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoCEmail"]/div/input')
        elem.send_keys(data['邮箱'])
        # 手机
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoMobile"]/div/input')
        elem.send_keys(Keys.CONTROL, "a")
        elem.send_keys(data['手机'])

        # 洗钱风险
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoCustomerIndustry"]')
        self.driver.execute_script("arguments[0].click()", elem)
        time.sleep(0.2)
        elem.send_keys('其他行业')
        # 页面上有两个一毛一样的元素，就用last()函数
        elem = self.driverwait.until_find_element(By.XPATH,'(//ul[./li/span[text()="金融业"]])[last()]/li[./span[text()="其他行业"]]')
        elem.click()

        # 职业洗钱风险  不便分类的其他从业人员 x 2
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoProfession"]')
        self.driver.execute_script("arguments[0].click()", elem)
        time.sleep(0.2)
        elem.send_keys('不便分类的其他从业人员')
        # 页面上有两个一毛一样的元素，就用last()函数
        elem = self.driverwait.until_find_element(By.XPATH, '(//ul[./li/span[text()="不便分类的其他从业人员"]])[last()]/li[./span[text()="不便分类的其他从业人员"]]')
        elem.click()
        time.sleep(1)

        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoProfessionMiddle"]')
        self.driver.execute_script("arguments[0].click()", elem)
        time.sleep(0.2)
        elem.send_keys('不便分类的其他从业人员')
        # 页面上有两个一毛一样的元素，就用last()函数
        elem = self.driverwait.until_find_element(By.XPATH,'(//ul[./li/span[text()="不便分类的其他从业人员"]])[last()]/li[./span[text()="不便分类的其他从业人员"]]')
        elem.click()

        # 洗钱风险登记
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoRiskGrade"]')
        self.driver.execute_script("arguments[0].click()", elem)
        time.sleep(0.2)
        elem = self.driverwait.until_find_element(By.XPATH, '(//ul[./li/span[text()="低风险"]])[last()]/li[./span[text()="低风险"]]')
        elem.click()

        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceApplicantInfoConfirm"]')
        elem.click()
        if '确认成功' in self.handle_success_dlg(timeout=3):
            logger.info('客户确认成功')
        self.handle_err_dlg(timeout=0.5)

        # 被保人 同车主
        elem = self.driverwait.until_find_element(By.XPATH, '//span[text()="同投保人"]/../span[1]')
        elem.click()
        # 等待加载
        locator = (By.XPATH, '//*[@id="insuranceApplicantInfoIdentifyNumber"]/div/input')
        text = data['身份证号']
        WebDriverWait(self.driver, 2).until(EC.text_to_be_present_in_element_value(locator, text))

    def get_calculate_dlg_msg(self):
        """点击计算保费得到所有弹窗提示信息的列表
        """
        # 点击计算保费
        elem = self.driver.find_element(By.XPATH, '//*[@id="calculatePremium"]')
        elem.click()
        success_msg_list = []
        err_or_warning_msg_list = []
        time.sleep(5)
        while True:
            print(1031)
            success_dlg = dialog.SuccessMsgDlg(self.driver)
            err_dlg = dialog.ErrorMsgDlg(self.driver)
            warning_dlg = dialog.WarningDlg(self.driver)
            if success_dlg.exists():
                success_text = success_dlg.get_content()
                logger.info('成功提示窗口： %s', success_text)
                success_msg_list.append(success_text)
                success_dlg.close()
                time.sleep(2) # 计算成功 后还有个 暂存成功
                # 得到两个消息后就是成功了
                prompt = '\n'.join(success_msg_list)
                if ('暂存成功' and '计算成功') in prompt:
                    print(1032,prompt)
                    break
            if err_dlg.exists():
                err_msg = err_dlg.get_content()
                logger.info('错误提示窗口： %s', err_msg)
                err_or_warning_msg_list.append(err_msg)
                err_dlg.close()
            if warning_dlg.exists():
                warning_msg = warning_dlg.get_content()
                logger.info('警示提示窗口： %s', warning_msg)
                err_or_warning_msg_list.append(warning_msg)
                warning_dlg.close()
            if not (success_dlg.exists(timeout=0.5) or err_dlg.exists(timeout=0.5) or warning_dlg.exists(timeout=0.5)):
                print('结束了')
                break
        print(success_msg_list,err_or_warning_msg_list)
        return success_msg_list,err_or_warning_msg_list

    def analysis_insurance_effect_date(self, content):
        """从弹窗内容解析出终保日期，确定起保日期
        return:{'交强险': '2021-04-22', '商业险': '20210606'}
        """
        re_date = re.compile('终保日期.*?(\d+-\d+-\d+)') # 交强险 2021-01-01 00:00
        re_date1 = re.compile('终保日期.*?(\d{8})') # 商业险 202101010000
        buf = StringIO(content)
        state = None
        commerce_text = '商业险'
        compul_text = '交强险'
        result = {}
        for line in buf:
            if line.startswith(commerce_text):
                state = commerce_text
            elif line.startswith(compul_text):
                state = compul_text
            if not state:
                continue

            rst = re_date.search(line)
            if rst:
                result[state] = rst.group(1)
                state = None
            rst1 = re_date1.search(line)
            if rst1:
                result[state] = rst1.group(1)
                state = None
        return result

    def parse_datetime(self, date_str):
        """将字符转化为日期
        """
        if not isinstance(date_str, str):
            return
        date_str = date_str.strip()
        fmts = ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y%m%d']
        for fmt in fmts:
            try:
                print(1085)
                return datetime.strptime(date_str, fmt).date().isoformat()
            except ValueError:
            # except:
                print(1089)
                continue
        else:
            print(f'未能将{date_str}解析为日期')
            raise errors.RpaError(error=errors.E_PROC,message=f'未能将{date_str}解析为日期')

    def set_effect_date(self,date_dict):
        """设值交强险、商业险起保日期
        """
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceInsuranceCIInfoChecked"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        time.sleep(0.2)
        logger.info(f'设置交强险、商业险起保日期：{date_dict}')
        if data.get('交强险'):
            start_datetime = data['start_date']
            elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceInsuranceCIInfoStartDate"]')
            self.driver.execute_script('arguments[0].value="{}";'.format(start_datetime), elem)
            elem.click()
            elem.send_keys(Keys.ENTER)
            time.sleep(0.5)
        if data.get('商业险'):
            start_datetime = data['start_date']
            elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceInsuranceBIInfoStartDate"]')
            self.driver.execute_script('arguments[0].value="{}";'.format(start_datetime), elem)
            elem.click()
            elem.send_keys(Keys.ENTER)
            time.sleep(0.5)

    def ensure_effect_date_and_calculate(self,data):
        """确定并修改起保日期，计算保费
        """
        # 指令支持交商一致的，如今日脱保，但是客户想一周后的周一生效，可以指令指定
        if data.get('生效日期'):
            date_dict = {}
            commerce_date = self.parse_datetime(str(data.get('生效日期')))
            date_dict['商业险'] = commerce_date
            date_dict['交强险'] = commerce_date
            self.set_effect_date(date_dict=date_dict)

        success_msg_list,err_or_warning_msg_list = self.get_calculate_dlg_msg()
        if err_or_warning_msg_list:
            # 识别成{'交强险': '2021-04-22', '商业险': '20210606'}
            dates = self.analysis_insurance_effect_date('\n'.join(err_or_warning_msg_list)) # 列表项转化为一行一行的文本
            # max_date = date.today() + timedelta(days=MAX_DAY_INTERVAL)
            tommorow = date.today() + timedelta(days=1)
            dates = {
                # k: v if date.fromisoformat(v) > tommorow else tommorow.isoformat() for (k, v) in dates.items() if date.fromisoformat(v) < max_date
                k: v if date.fromisoformat(v) > tommorow else tommorow.isoformat() for (k, v) in dates.items()
            }
            date_dict = {}
            commerce_date = dates.get('商业险')
            if commerce_date:
                commerce_date = self.parse_datetime(str(commerce_date))
                date_dict['商业险'] = commerce_date
                logger.info('设置商业险起保日期：%s', commerce_date)
            compul_date = dates.get('交强险', None)
            if compul_date:
                compul_date = self.parse_datetime(str(compul_date))
                date_dict['交强险'] = compul_date
                logger.info('设置交强险起保日期：%s', compul_date)
            self.set_effect_date(date_dict=date_dict)

        if success_msg_list:
            prompt = '\n'.join(success_msg_list)
            print(1156)
            logger.info(prompt)

        # 增加特约上传影像
        self.appoint_and_image(data)

        # 新增信息后需要再次保费试算得到提示信息
        success_msg_list, err_or_warning_msg_list = self.get_calculate_dlg_msg()
        prompt = '\n'.join(err_or_warning_msg_list)
        if ('出错' or '重复投保') in prompt:
            raise errors.RpaError(error=errors.E_PROC, message=prompt)
        prompt = '\n'.join(success_msg_list)
        if ('暂存成功' or '计算成功') in prompt:
            logger.info(prompt)
        return True


    def appoint_and_image(self, data):
        """特别约定和影响信息
        """
        # 添加特约++++++++++++++++++++++++++++++++++++++
        elem = self.driver.find_element(By.XPATH, '//*[@id="insuranceInsuredInfoRiskGrade"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        elem = self.driverwait.until_find_element(By.XPATH, '//*[text()="《 商业特别约定 》"]')
        elem.click()
        time.sleep(2)
        elem = self.driver.find_element(By.XPATH, '//input[@placeholder="请输入【特约编码】或【部分特约内容】以快速检索"]')
        elem.send_keys('05150326')
        # 查询
        elem = self.driver.find_element(By.XPATH, '//*[@class="el-button fontLeft Sybackground el-button--primary"]')
        elem.click()
        time.sleep(0.5)
        elem = self.driver.find_element(By.XPATH, '//*[text()="05150326---"]/../../../td[1]/descendant::input/..')
        elem.click()
        elem = self.driver.find_element(By.XPATH, '//*[@class="especiallySearch"]/ancestor::div[@class="el-dialog"]/div[@class="el-dialog__footer"]/div/button')
        elem.click()
        time.sleep(1)

        # 上传影像++++++++++++++++++++++++++++++++++++++


        files = data['files']
        for index, f in enumerate(files):
            elem = self.driver.find_element(By.XPATH,'//*[text()="验车照片 ( 若需要上传验车照，请将当天验车码和车辆一同拍照上传 )"]/ancestor::div[@class="imageInfo"]/div[3]/descendant::div[@class="el-upload el-upload--picture-card"]')
            self.driver.execute_script("arguments[0].scrollIntoView();", elem)
            time.sleep(0.5)
            file_path = f['path']
            elem = self.driverwait.until_find_element(By.XPATH, '//*[text()="验车照片 ( 若需要上传验车照，请将当天验车码和车辆一同拍照上传 )"]/ancestor::div[@class="imageInfo"]/div[3]/descendant::div[@class="el-upload el-upload--picture-card"]')
            elem.click()
            time.sleep(2)
            # 鼠标光标默认在文件路径输入框，直接输入，回车就好了
            keyboard.write(file_path.strip())
            print(file_path.strip())
            keyboard.send('enter')
            print(1204)
            time.sleep(1)
        elem = self.driver.find_element(By.XPATH,'//*[text()="验车照片 ( 若需要上传验车照，请将当天验车码和车辆一同拍照上传 )"]/ancestor::div[@class="imageInfo"]/div[3]/descendant::div[@class="el-upload el-upload--picture-card"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", elem)
        time.sleep(0.5)
        elem = self.driver.find_element(By.XPATH, '//button[./span[text()="全部上传"]]')
        elem.click()
        while True:
            msg = self.handle_success_dlg(timeout=40)
            if '上传成功' in msg:
                logger.info(msg)
                print(1216)
                break
            else:
                print('怎么没有上传成功呢？？？')

    def submit(self,data):
        elem = self.driver.find_element(By.XPATH, '//*[@id="submitInsure"]')
        elem.click()
        time.sleep(5)
        elem = self.driverwait.until_find_element(By.XPATH, '//*[@class="accountBoxJQ"]/..')
        all_text = elem.text
        print(elem.text)
        pay_content_path = self.screenshot_mgr.new_screenshot_name()
        elem.screenshot(pay_content_path)
        logger.info('payment qrcode path is: %s', pay_content_path)

        # elem = self.driverwait.until_find_element(By.XPATH, '//*[@class="accountBoxJQ"]')
        # print(elem.text)
        # elem = self.driverwait.until_find_element(By.XPATH, '//*[@class="accountBoxSY"]')
        # print(elem.text)

        re_commerce_result = re.compile('商业险核保结果:(.*?)\n')
        # re_commerce_cause = re.compile('商业险未通过原因(.*?)\n')
        re_commerce_cause = re.compile('商业险未通过原因(.*)') # 最后一条消息没有换行符，直接匹配所有就好了
        re_commerce_num = re.compile('商业险投保单号: (.*?)\n')

        re_compul_cause = re.compile('交强险未通过原因(.*?)\n')
        re_compul_result = re.compile('交强险核保结果:(.*?)\n')
        re_compul_num = re.compile('交强险投保单号: (.*?)\n')
        # commerce_text = '商业险'
        # compul_text = '交强险'
        err_msg = ''
        success_msg = ''

        commerce_num = re_commerce_num.search(all_text).group(1).strip()
        compul_num = re_compul_num.search(all_text).group(1).strip()
        # 商业险结果
        commerce_result = re_commerce_result.search(all_text)
        if commerce_result:
            commerce_result = commerce_result.group(1)
        # 交强险结果
        compul_result = re_compul_result.search(all_text)
        if compul_result:
            compul_result = compul_result.group(1)

        if '自核通过' not in commerce_result:
            print(11)
            commerce_cause = re_commerce_cause.search(all_text)
            if commerce_cause:
                commerce_cause = commerce_cause.group(1)
                err_msg = err_msg + f'商业险{commerce_num}核保结果:{commerce_result},未通过原因{commerce_cause}。'
                print(1253,err_msg)
        else:
            success_msg = success_msg + f'商业险{commerce_num}核保结果:{commerce_result}。'
        if '自核通过' not in compul_result:
            print(222)
            compul_cause = re_compul_cause.search(all_text)
            if compul_cause:
                compul_cause = compul_cause.group(1)
                err_msg = err_msg + f'交强险{compul_num}核保结果:{compul_result},未通过原因{compul_cause}。'
                print(1261,err_msg)
        else:
            success_msg = success_msg + f'交强险{compul_num}核保结果:{compul_result}。'
        print(111, err_msg)
        print(111, success_msg)
        if err_msg:
            err_msg = f'客户{data.get("车主姓名")}的' +success_msg + err_msg
            print(219, err_msg)

            elem_close = self.driver.find_element(By.XPATH, '//div[@aria-label="提交核保"]/div/button')
            self.driver.execute_script("arguments[0].click()", elem_close)
            time.sleep(0.5)


            # TODO 开始下载预览保单,暂时在这里测试，真正步骤要放在下面
            elem = self.driver.find_element(By.XPATH, '//span[contains(string(),"附加精神损害抚慰金责任险（车上人员责任保险（乘客））")]')
            self.driver.execute_script("arguments[0].scrollIntoView();", elem)
            time.sleep(0.2)
            elem = self.driver.find_element(By.XPATH, '//*[@id="quotation"]')
            elem.click()
            elem = self.driverwait.until_find_element(By.XPATH, '//li[text()="下载"]')
            time.sleep(0.5)
            # WebDriverWait(self.driver, timeout=2).until(EC.element_to_be_clickable(elem))
            try:
                print(1291)
                elem.click()
            except:
                print(1294)
                self.driver.execute_script("arguments[0].click()", elem)



            # raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CAR_INFO_RECOGNIZE)
            raise errors.RpaError(error=errors.E_PROC, message=err_msg)
        if ('自核通过' in commerce_result) and ('自核通过' in compul_result):
            elem = self.driverwait.until_find_element(By.XPATH, '//*[@class="accountBoxJQ"]/..')
            pay_content_path = self.screenshot_mgr.new_screenshot_name()
            elem.screenshot(pay_content_path)
            logger.info('payment qrcode path is: %s', pay_content_path)

            # 关闭核保成功界面
            elem_close = self.driver.find_element(By.XPATH, '//div[@aria-label="提交核保"]/div/button')
            self.driver.execute_script("arguments[0].click()", elem_close)
            WebDriverWait(self.driver, timeout=2).until(EC.staleness_of(elem))

            # 开始下载预览保单
            elem = self.driver.find_element(By.XPATH, '//span[contains(string(),"附加精神损害抚慰金责任险（车上人员责任保险（乘客））")]')
            self.driver.execute_script("arguments[0].scrollIntoView();", elem)
            time.sleep(0.2)
            elem = self.driver.find_element(By.XPATH, '//*[@id="quotation"]')
            elem.click()
            elem = self.driverwait.until_find_element(By.XPATH, '//li[text()="下载"]')
            WebDriverWait(self.driver, timeout=2).until(EC.element_to_be_clickable(elem))
            try:
                elem.click()
            except:
                self.driver.execute_script("arguments[0].click()", elem)

            qutation_path='' # TODO 需要返回电子保单

        return commerce_num,pay_content_path,qutation_path

    def ckeck_quotation_status(self, quotation_id):
        """查看是否已经付款生成电子保单，生成则返回保单号
        """

        self.driver.get('https://xkscd.djbx.com:9080/pc_vir/underwriting/renwPreminm')
        time.sleep(1)
        WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.XPATH, '//label[text()="保单号："]/../descendant::input'))).click()
        self.driver.find_element(By.XPATH, '//label[text()="保单号："]/../descendant::input').send_keys(quotation_id)
        self.driver.find_element(By.XPATH, '//span[text()="查询"]/..').click()
        time.sleep(2)


        # head_tr1和head_tr2 网页看上去是一样的，但是head_tr2只能获取到th.text='操作'，head_tr1中可以获取到其他的表头，莫名其妙？？？？
        # head_tr1 = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'保单号')][ancestor::div[@class='el-table__header-wrapper']]") # 结果的表头
        # head_th_list1 = head_tr1.find_elements_by_tag_name('th')
        # head_tr2 = self.driverwait.until_find_element(By.XPATH, "//tr[contains(string(),'保单号')][ancestor::div[@class='el-table__fixed-right']]")
        # head_th_list = head_tr2.find_elements_by_tag_name('th')

        trlist = self.driver.find_element(By.XPATH, "//tr[contains(string(),'保单号')][ancestor::div[@class='el-table__header-wrapper']]")
        if not trlist:
            return
            # raise errors.RpaError(error=errors.E_PROC, message='没有查到保单号：{} 的电子保单'.format(quotation_id))
        return quotation_id

    def handle_success_dlg(self, timeout=2):
        dlg_success = dialog.SuccessMsgDlg(self.driver)
        if dlg_success.exists(timeout):
            detail = dlg_success.get_content()
            logger.info('found success dialog: %s', detail)
            dlg_success.close()
            return  detail
        else:
            logger.info('not found success dialog.')

    def handle_err_dlg(self, timeout=2):
        dlg_fail = dialog.ErrorMsgDlg(self.driver)
        if dlg_fail.exists(timeout):
            err_msg = dlg_fail.get_content()
            logger.info('found err dialog: %s', err_msg)
            dlg_fail.close()
            return err_msg
        else:
            logger.info('not found err dialog.')

    def handle_warning_dlg(self, timeout=2):
        dlg_warning = dialog.WarningDlg(self.driver)
        if dlg_warning.exists(timeout):
            warning_msg = dlg_warning.get_content()
            logger.info('found warning dialog: %s', warning_msg)
            dlg_warning.close()
            return warning_msg
        else:
            logger.info('not found warning dialog.')

    @entry_wrap
    def apply_insurance_ticket(self, task):
        """录单主入口
        """
#         test_dic = {'姓名':'朱晓明','quotation_id': '123456789', 'quotation_preview': 'C:\\Users\\13154\\Desktop\\发票\\80.pdf', 'qrcode': 'C:\\Users\\13154\\Desktop\\荷包成功.png','订单号':'987654321',
#             'chat': '小小', 'sender': '小小', 'task_id': 1, 'task_hash': '6d272e0', 'task_type': 'order', 'num_pdf': 0, 'num_pic': 2,
# 'mobile': '15518507955', '手机': '15518507955', '邮箱': '132@qq.com', 'email': '132@qq.com',  '使用性质': 'A1', '燃料种类': '柴油', 'owner_type': 'person',
# 'plan': {'三者': '100', '车损': '10000', '司机': '10000', '乘客': '5000', '道路救援': '2', '代为驾驶': '1', '折扣系数': '1.35'},
# 'files': [{'type': 'pic', 'path': 'o.jpg'}, {'type': 'pic', 'path': 'qp.jpg'}],
# }
#
#         return test_dic

        def populate_insurance_data(data) -> dict:
            """根据基础款和自定义的附加内容，加以修改得到最后的plan，塞入data即task中
            """
            if not ('owner_type' in data):
                data['owner_type'] = 'person'

            plan = PLANS[data['plan']].copy()

            # 'plan_custom': {'三者': '1500000', '+划痕': '5000', '-意外': True}  # 不要意外，加划痕，修改三者
            custom = data.get('plan_custom')
            if custom:
                for option in custom:
                    if option.startswith('-'):
                        key = option[1:]
                        if key in plan:
                            del plan[key]
                        else:
                            logger.warn(
                                'try to remove plan option %s which does not exit', key)
                    elif option.startswith('+'):
                        plan[option[1:]] = custom[option]
                    else:
                        plan[option] = custom[option]
                else:
                    del data[custom]
            data['plan'] = plan
            return data

        logger.info('apply insurance ticket: %s', task)
        # populate：填充  根据基础款去拿到参数，放入task
        task = populate_insurance_data(task)
        logger.info('apply_insurance_ticket after populate data: %s', task)

        self.open()
        self.login(organization='05--浙江分公司')
        self.goto_category_page(category='车险投保')
        owner_type = task['owner_type']
        if owner_type == 'person':
            self.fill_header_info(task)
            self.fill_car_owner_info(task)
            self.fill_car_info(task)
            self.vehicle_tax(task)
            self.fill_insurance_plan(task)
            self.policy_holder(task)
            self.ensure_effect_date_and_calculate(task)
            quotation_id,qrcode,quotation_preview = self.submit(task)
        # elif owner_type == 'enterprise':
        #     pass
        else:
            raise errors.RpaError(
                error=errors.E_UNKOWN, message=strings.err_unknown)

        task['quotation_id'] = quotation_id
        task['quotation_preview'] = quotation_preview
        task['qrcode'] = qrcode
        print(930, 'apply_insurance_ticket:', task)
        return task

    @entry_wrap
    def get_insurance_files(self, quotation_ids: list) -> dict:
        """TODO 保单下载 未完成
        """
        logger.info('start getting insurance pdf files for %s', quotation_ids)
        dl_dir = tempfile.mkdtemp()
        logger.info('download path is %s', dl_dir)
        self.open(download_dir=dl_dir)
        self.login(organization='05--浙江分公司')
        # self.goto_category_page(category='保单查询')

        effect_tickets = {}
        cnt_dl = 0
        for quotation_id in quotation_ids:
            tickets = self.ckeck_quotation_status(quotation_id)
            if tickets:
                logger.info('quotation: %s has  been generated', quotation_id)
            else:
                logger.info('quotation: %s has not been generated yet', quotation_id)
                continue

            # head_tr1和head_tr2 网页看上去是一样的，但是head_tr2只能获取到th.text='操作'，head_tr1中可以获取到其他的表头，莫名其妙？？？？
            trlist1 = self.driver.find_element(By.XPATH, f"//tr[contains(string(),'{quotation_id}')][ancestor::div[@class='el-table__body-wrapper is-scrolling-none']]")
            trlist2 = self.driver.find_element(By.XPATH, f"//tr[contains(string(),'{quotation_id}')][ancestor::div[@class='el-table__fixed-body-wrapper']]")

            # 勾选
            elem = trlist2.find_element(By.XPATH, './td[1]/div')
            elem.click()
            # ...
            elem =trlist2.find_element(By.XPATH,'./td[13]//div[@class="underwritingStyle"]')
            elem.click()
            # 电子保单
            elem = self.driverwait.until_find_element(By.XPATH, '//body/div[@class="el-select-dropdown el-popper"]//span[text()="电子保单"]')
            elem.click()
            # 下载电子保单
            elem = self.driverwait.until_find_element(By.XPATH, '//div[@class="electricPolicyBtnBox"]/div[contains(string(),"下载电子保单")]')
            elem.click()
            time.sleep(2)
            # 关闭弹出界面
            self.driver.find_element(By.XPATH, '//div[@class="el-dialog__wrapper electricPolicyBox"]//button[@class="el-dialog__headerbtn"]').click()
            # TODO 暂时做到这里，后续待开发

        #     self.driver.find_element(By.CSS_SELECTOR, '#dzbdxz').click()
        #     time.sleep(2)
        #     cnt_dl += 1
        #     effect_tickets.update({t['policyNo']: t for t in tickets})
        # now = time.time()
        # download_timeout = now + self.DOWNLOAD_WAIT_TIME
        # done_zips = set()
        # quot_pdfs = {}
        # while now < download_timeout:
        #     zipfiles = [p for p in Path(dl_dir).glob(
        #         '*.zip') if p not in done_zips]
        #     logger.info('zip files: %s', zipfiles)
        #     for zfile in zipfiles:
        #         extract_dir = Path(tempfile.mkdtemp()).resolve()
        #         with ZipFile(zfile) as zf:
        #             zf.extractall(extract_dir)
        #         newpaths = []
        #         quot_id = None
        #         for pdf in Path(extract_dir).glob('*/*.pdf'):
        #             logger.info('Downloaded pdf: %s', pdf)
        #             # stem = pdf.stem
        #             # 之前文件名可能是 保单号：ASHH451Y2021B005048L.pdf，现在变化成 保单号+号牌号码 ：ASHH451Y2021B005048L_LS004151.pdf了
        #             stem = pdf.stem.split('_')[0]
        #             ticket = effect_tickets[stem]
        #             quot_id = ticket['quotationNo']
        #             # product_type = '交强险保单' if ticket['productType'] == '交强险' else '商业险保单'
        #             product_type = ticket['productType'] + '保单'
        #             newname = ticket['insurant'] + product_type + '.pdf'
        #             logger.info('pdf name to change: %s', newname)
        #             newpath = pdf.rename(Path(pdf.parent, newname))
        #             newpaths.append(newpath)
        #         if quot_id:
        #             quot_pdfs[quot_id] = newpaths
        #         logger.info('handled zip file: %s', zfile)
        #         done_zips.add(zfile)
        #     if cnt_dl == len(done_zips):
        #         logger.info('downloaded pdfs: %s', quot_pdfs)
        #         return quot_pdfs
        #     else:
        #         time.sleep(5)
        #         now = time.time()
        # else:
        #     logger.error('Timeout when downloading insurance pdfs.')
        #     raise errors.RpaError(error=errors.E_NETWORK,
        #                           message=strings.ERR_INSURANCE_DOWNLOAD)

if __name__ == "__main__":
    # apply_insurance_ticket
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    # data.update(car)
    web_screenshot_mgr = ScreenShotMgr('log/screenshot_baoxianweb/')
    web_screenshot_mgr.mkdir()
    w = DajiabaoWeb(web_screenshot_mgr)
    w.open()
    w.login(organization='05--浙江分公司')
    # w.login(organization='03--上海分公司')

    data = { '邮箱':'131545@qq.com', '手机':'15518899777','证件有效期':'2021-11-11',
             'files': [{'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\身份证.jpg'}, {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\行驶证.jpg'},],
             'plan':{'车损':'1000',
                     '三者':'50',
                     '司机':'5000',
                     '乘客':'5000',
                     '道路救援':'5',
                     '代为驾驶':'1',
                     '折扣系数':'1.35'}
             }
    w.goto_category_page(category='车险投保')
    w.fill_header_info(data)
    w.fill_car_owner_info(data)
    w.fill_car_info(data)
    w.vehicle_tax(data)
    w.fill_insurance_plan(data)
    w.policy_holder(data)
    w.ensure_effect_date_and_calculate(data)
    # w.appoint_and_image(data)
    w.submit(data)
    # w.fill_person_car_info(data)
    # w.add_person_msg(data)
    # w.fill_insurance_plan(data)
    # w.apply_payment(vin=data['options']['车架号'], payway_name='xx')
    w.close()

    # data = {'options': {'车架号': 'LRW3E7FA2LC146763', '发动机号': 'TG1203330046NM', '厂牌型号': 'TSL7000BEVAR1',
    #                     '姓名': '王皎莹', '身份证号': '320504197711303526', '住址': ' 上海市长宁区延安西路900号', '性别': '男', '车主类型': '个人',
    #                     'mobile': '18621998758', '手机': '18621998758',
    #                     '邮箱': 'zhang_xuelin@126.com', 'email': 'zhang_xuelin@126.com', 'plan': '基本款',
    #                     '生效': '2020-10-03 00:00', 'start_date': '2020-10-03 00:00',
    #                     '经办人': '王谨飞', 'agent': '王谨飞','座位数':'6','总金额':'255550',},
    #         '姓名': '王皎莹', '身份证号': '320504197711303526','总金额':'255550','mobile': '18621998758', '手机': '18621998758',
    #         'plan':{
    #             '交强': True,
    #             '三者': '200',
    #             '车损': True,
    #             '划痕': '5000',
    #             '司机': '20000',
    #             '乘客': '20000',
    #         },
    #         }

    # w.goto_car_info(agent='吴征')
    # data = {'chat': 'allen、慧慧、录单助手', 'sender': 'allen', 'task_id': 1, 'task_hash': 'be2d242', 'task_type': 'order', 'num_pdf': 1, 'num_pic': 1, 'mobile': '13801652382', '手机': '13801652382', '邮箱': 'zhang_xuelin@126.com', 'email': 'zhang_xuelin@126.com', 'plan': '基本款', '生效': '2020-10-03 00:00', 'start_date': '2020-10-03 00:00', '经办人': '陈佳燕', 'agent': '陈佳燕', 'options': {'车架号': 'LRW3E7EA6LC078016', '发动机号': 'TG1201270005HC', '厂牌型号': 'TSL7000BEVAR0', '姓名': '张学林', '身份证号': '522101197808245615', '住址': ' 上海市长宁区延安西路900号', '性别': '男', '车主类型': '个人', 'mobile': '13801652382', '手机': '13801652382', '邮箱': 'zhang_xuelin@126.com', 'email': 'zhang_xuelin@126.com', 'plan': '基本款', '生效': '2020-10-03 00:00', 'start_date': '2020-10-03 00:00', '经办人': '陈佳燕', 'agent': '陈佳燕'}, '姓名': '张学林', '身份证号': '522101197808245615', '住址': '上海市长宁区延安西路900号', '性别': '男', '车主类型': '个人', 'certno': 'YX475LC00078016', 'certdate': '2020年09月02日', 'name': '特斯拉牌纯电动轿车', 'model': 'TSL7000BEVAR0', 'vin': 'LRW3E7EA6LC078016', 'engineno': 'TG1201270005HC', 'color': '灰', 'seats': '5'}
    # data = {'options': {'车架号': 'LRWBBHHHHHUUUUUKK', '发动机号': '12345', '厂牌型号': 'TSL7000BEVAR1',
    # '姓名': '张学林', '身份证号': '522101197808245615', '住址': ' 上海市长宁区延安西路900号', '性别': '男', '车主类型': '个人', 'mobile': '13801652382', '手机': '13801652382',
    # '邮箱': 'zhang_xuelin@126.com', 'email': 'zhang_xuelin@126.com', 'plan': '基本款', '生效': '2020-10-03 00:00', 'start_date': '2020-10-03 00:00',
    # '经办人': '陈佳燕', 'agent': '陈佳燕'}, }
    # w.apply_insurance_ticket(data)

    # options = data['options']
    # today = datetime.date.today().isoformat()
    # self.driverwait.until_find_element(By.ID, "plateless").click()
    # self.driver.find_element(By.ID, "plateType").click()
    # dropdown = self.driver.find_element(By.ID, "plateType")
    # dropdown.find_element(By.XPATH, "//option[. = '小型新能源汽车']").click()
    # self.driver.find_element(By.ID, "carVIN").click()
    # self.driver.find_element(By.ID, "carVIN").send_keys(options['车架号'])
    # self.driver.find_element(By.ID, "engineNo").click()
    # self.driver.find_element(By.ID, "engineNo").send_keys(options['发动机号'])
    # self.driver.find_element(By.ID, "stRegisterDate").click()
    # self.driver.find_element(By.ID, "stRegisterDate").send_keys(today)
    # self.driver.find_element(
    #     By.NAME, "stInvoiceDate").send_keys(Keys.ENTER)
    # self.driver.find_element(By.NAME, "stInvoiceDate").click()
    # self.driver.find_element(By.NAME, "stInvoiceDate").send_keys(today)
    # self.driver.find_element(
    #     By.NAME, "stInvoiceDate").send_keys(Keys.ENTER)
    #
    # usage = self.driver.find_element(By.ID, "usage")
    # usage.click()
    # usage.find_element(By.XPATH, "//option[. = '家庭自用车']").click()
    # self.driver.find_element(By.ID, "ownerName").send_keys(data['姓名'])
    # ownerprop = self.driver.find_element(By.NAME, "ownerProp")
    # ownerprop.click()
    # ownerprop.find_element(By.XPATH, "//option[. = '个人']").click()
    # certype = self.driver.find_element(By.ID, "certType")
    # certype.click()
    # certype.find_element(By.XPATH, "//option[. = '身份证']").click()
    # self.driver.find_element(By.ID, "certNo").send_keys(data['身份证号'])
    #
    # # self.vin_search()
    # model = options['厂牌型号']
    # model_re = re.search('特斯拉.*车(X|x).*\d$', model.replace(" ", ""))
    # if model_re:
    #     model = 'model x'
    #     self.fill_model(model)
    #     self.set_seat(int(options['座位数']))
    #     self.set_price(data['总金额'])
    # else:
    #     self.fill_model(options['厂牌型号'])
    #
    # self.set_uniform_code(data['uniform_code'], data['uniform_name'])
    # self.driver.find_element(By.ID, 'next').click()
    # logger.info('click next in car info page. check if error dialog.')
    # self.handle_notice_dlg(2)