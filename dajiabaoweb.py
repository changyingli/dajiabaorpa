# coding=utf8
from subprocess import run as prun
import datetime
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
import webdriverhelper
import msg as strings
import errors
from file import ScreenShotMgr
from settings import PLANS, AGENTS



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

    def login(self):
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
                    break
                except:
                    pass
        else:
            logger.error('Wrong captcha result when logging.')

    def goto_category_page(self, organization='05--浙江分公司',category='车险投保'):
        """进入车险投保、保单查询界面
        """
        if organization:
            # 选择机构
            elem = self.driver.find_element_by_id('loginCompleteCode')
            elem.send_keys(organization)
            # li式的下拉选择框，先输入关键词，然后等待对应的li元素加载出来后再点击
            elem = self.driverwait.until_find_element(By.XPATH, '//span[contains(text(),"05--浙江分公司")]')
            self.driver.execute_script("arguments[0].click()",elem)
            time.sleep(2)
        # 首页
        elem = self.driver.find_element_by_xpath('//li[@class="el-menu-item is-active submenu-title-noDropdown"]')
        elem.click()
        # 车险投保、保单查询
        elem = self.driver.find_element_by_xpath(f'//span[../div][contains(text(),"{category}")]')
        elem.click()
        # 等待元素消失
        WebDriverWait(self.driver, 3).until(EC.invisibility_of_element(elem))

    def fill_header_info(self, data):
        """填写头部机构、代理人、业务来源等信息
        """
        # organization_code = data['organization_code']
        # agent_code = data['agent_code']
        organization_code = '05700205'
        agent_code = '105002267'
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
        # files = [{'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\不是身份证.png'},
        #         {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\身份证.jpg'},]
        files = [{'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\身份证.jpg'}, ]
        # 点击识别按钮  input和img都不能点击，要点击外层的div
        # prv_chrome_pid_list = self.get_pid("chrome.exe")
        # print(prv_chrome_pid_list)
        # logger.debug(f'prv_chrome_pid_list:{prv_chrome_pid_list}')
        # self.driver.find_element_by_xpath('//div[./input[@id="insuranceCarOwncarOwnImgMessageOCR"]]').click()
        # cur_chrome_pids = self.get_pid("chrome.exe")
        # logger.debug(f'cur_chrome_pid_list:{cur_chrome_pids}')
        # print(cur_chrome_pids)
        # pid_list = [i for i in cur_chrome_pids if i not in prv_chrome_pid_list]
        # print(pid_list)
        # self.chrome_auto = ChromeAuto(pid_list[0])
        # self.chrome_auto.send_file(file_path=file_path)
        for f in files:
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
                    print([333, ownr_addr, card_id])
                    return [ownr_addr, card_id]
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
        ownr_addr, card_id = self.idcard_ocr(data)
        data['车主地址'] = ownr_addr
        data['身份证号'] = card_id
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

        dlg_success = dialog.SuccessMsgDlg(self.driver)
        dlg_fail = dialog.ErrorMsgDlg(self.driver)
        for i in range(10):
            if not dlg_success.exists():
                print(457)
                time.sleep(0.5)
        if dlg_success.exists():
            logger.info(f'{dlg_success.get_content()}')
            dlg_success.close()
        if dlg_fail.exists(timeout=0.5):
            err_msg = dlg_fail.get_content()
            raise errors.RpaError(error=errors.E_PROC, message=strings.ERR_CUSTOMER_CONFIRM.format(err_msg))

    def car_info_ocr(self, data):
        """识别行驶证,得到车辆相关各种信息
        """
        # 滚动页面至车辆信息位置可见且合适
        input_elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarOwnInfoCity"]')
        self.driver.execute_script("arguments[0].scrollIntoView();", input_elem)
        # files = [
        #         {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\身份证.jpg'},
        #          {'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\行驶证.jpg'},]
        files = [{'type': 'pic', 'path': 'C:\\Users\\13154\\Desktop\\各个项目\\大家保\\行驶证.jpg'}, ]
        for f in files:
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
            # elem = self.driver.find_element_by_xpath('//span[text()="行驶证"]/..')
            elem = self.driverwait.until_find_element(By.XPATH, '//span[text()="行驶证"]/..')
            print(489,time.time()-t)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click()", elem)
            # elem.click()

            elem = self.driver.find_element_by_xpath('//input[@id="carOcrInput"]/../button[./span[text()="确认"]]')
            # elem = self.driverwait.until_find_element(By.XPATH,'//input[@id="carOcrInput"]/../button[./span[text()="确认"]]')
            time.sleep(0.5)
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
                    dlg = dialog.ErrorMsgDlg(self.driver)
                    # if dlg.exists(timeout=0.5) and '识别失败' in dlg.get_content():
                    if dlg.exists():
                        logger.info(f'{dlg.get_content()}')
                        print(493,dlg.get_content())
                        dlg.close()
                        print("11行驶证识别失败")
                        break

                    dlg = dialog.WarningDlg(self.driver)
                    print(530)
                    if dlg.exists():
                        logger.info(f'{dlg.get_content()}')
                        print(511, dlg.get_content())
                        dlg.close()
                        break
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
        dlg = dialog.ErrorMsgDlg(self.driver)
        dlg2 = dialog.WarningDlg(self.driver)
        for i in range(4):
            time.sleep(1)
            if dlg.exists():
                logger.info(f'search_car_model ErrorMsgDlg:{dlg.get_content()}')
                dlg.close()
                break
            if dlg2.exists():
                logger.info(f'search_car_model WarningDlg:{dlg2.get_content()}')
                dlg2.close()
                break
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

        #

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
            nature_of_use = data.get('使用性质')
        elem = self.driver.find_element_by_xpath('//input[@id="insuranceCarInfoNatureOfUsage"]')
        self.driver.execute_script("arguments[0].click()", elem)

        # 获取列表，后续使用
        elem1 = self.driverwait.until_find_element(By.XPATH,f'//li[contains(string(),"{nature_of_use}")]/..')
        text_list = []
        for li in elem1.find_elements_by_tag_name('li'):
            text_list.append(li.text)
        print(text_list)

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

        # 获取列表项，合成大字典，指令匹配
        elem1 = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{liceense_vehicle}")]/..')
        text_dict = {}
        for li in elem1.find_elements_by_tag_name('li'):
            text_dict[li.text[0:3]]= li.text
        print(text_dict)

        liceense_vehicle = text_dict[liceense_vehicle]
        elem.send_keys(liceense_vehicle)
        elem = self.driverwait.until_find_element(By.XPATH, f'//li[contains(string(),"{liceense_vehicle}")]')
        elem.click()
        # self.driver.execute_script('arguments[0].value="{}";'.format(liceense_vehicle), elem)

        # 能源类型++++++++++++++++++++++++++++++++++++++
        energy_type = '燃油'
        if data.get('燃料'):
            fule_type = data.get('燃料')
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
        if data.get('燃料'):
            fule_type = data.get('燃料')
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

    def set_date(self,data):
        """设值交强险商业险起保日期
        """
        start_datetime = data['start_date']
        elem = self.driver.find_element(By.ID, "compulsoryStartDate")
        self.driver.execute_script(
            'arguments[0].value="{}";'.format(start_datetime), elem)
        elem.click()
        elem.send_keys(Keys.ENTER)
        time.sleep(0.5)
        pass

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




if __name__ == "__main__":
    # apply_insurance_ticket
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    # data.update(car)
    web_screenshot_mgr = ScreenShotMgr('log/screenshot_baoxianweb/')
    web_screenshot_mgr.mkdir()
    w = DajiabaoWeb(web_screenshot_mgr)
    w.open()
    w.login()
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
    data = { '邮箱':'131545@qq.com', '手机':'15518899777','证件有效期':'2021-11-11',
             'plan':{'车损':'1000',
                     '三者':'50',
                     '司机':'5000',
                     '乘客':'5000',
                     '道路救援':'5',
                     '代为驾驶':'2',
                     '折扣系数':'1.35'}
             }
    w.goto_category_page()
    w.fill_header_info(data)
    w.fill_car_owner_info(data)
    w.fill_car_info(data)
    w.vehicle_tax(data)
    w.fill_insurance_plan(data)
    w.policy_holder(data)
    # w.fill_person_car_info(data)
    # w.add_person_msg(data)
    # w.fill_insurance_plan(data)
    # w.apply_payment(vin=data['options']['车架号'], payway_name='xx')
    w.close()



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