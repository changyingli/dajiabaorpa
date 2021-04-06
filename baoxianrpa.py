
import logging
import re
import random
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta, date
from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook
from pywinauto import mouse
from PIL import ImageGrab

import errors
import msg as strings
import settings
from asynctask import AsyncTaskExecutor
from file import ScreenShotMgr
from dajiabaoweb import DajiabaoWeb
from cleanfile import CleanFile

logger = logging.getLogger(__name__)

SERVICE_REPLIES = (
    (
        ('file', Path('res/img/上海太保公众号.jpg').absolute()),
        ('msg', '请扫二维码进行如下步骤：享服务—权益中心—代为驾驶祝你使用愉快！如有问题可咨询人工服务专员。\n如需注册协助，请回复“注册”')
    ),
    (
        ('file', Path('res/img/上海太保公众号.jpg').absolute()),
        ('msg', '请扫二维码进行如下步骤：享服务—权益中心—特色代步车—立即使用—一键复制券码'),
        ('file', Path('res/img/代步车预约码.jpg').absolute()),
        ('msg', '请扫二维码将已领用券码兑换预约（取车地点请选择您车辆维修所在的钣喷中心）\n代步车服务专员将在您预约成功后30分钟内与您电话联系，请耐心等候（工作时间为9:00-18:00）。'),
    ),
    (
        ('file', Path('res/img/上海太保公众号.jpg').absolute()),
        ('msg', '请扫二维码进行如下步骤：享服务—权益中心—洗车。\n祝你使用愉快！如有问题可咨询人工服务专员。如需注册协助，请回复“注册”。')
    ),
    (
        ('file', Path('res/img/上海太保公众号.jpg').absolute()),
        ('msg', '请扫二维码进行如下步骤：享服务—权益中心—特色代泊—立即使用—一键复制券码。'),
        ('file', Path('res/img/车阵通小程序.jpg').absolute()),
        ('msg', '请扫二维码将已领用券码兑换预约。\n祝你使用愉快！如有问题可咨询人工服务专员。\n如需注册协助，请回复“注册”'),
    ),
    (
        ('msg', '您可以拨打110和95500报案，并第一时间拍摄多角度现场照片。\n您也可以进入太贴心小程序进行一键报案，万元以下案件微信定损快速理赔。'),
        ('file', Path('res/img/太贴心.jpg').absolute()),
    ),
)


def get_title(task):
    gender = task.get('性别')
    if gender:
        return '女士' if gender == '女' else '先生'
    else:
        return '客户'


def _handle_order_msg(task, msgctrl=None, end=False) -> bool:
    """ 处理任务的图片和文件消息
    Args:
        msgctrl: wechat msg control instance.
        end: set True if no more msg
    """
    num_pic = task['num_pic']
    num_pdf = task['num_pdf']
    # 消息列表遍历完毕也没有遇到上一个'录单'或者材料数目>3，会有这个参数，此时如果缺少材料会报错
    if end:
        if num_pdf + num_pic < 2:
            task.update({
                'error': errors.E_MSG,
                'msg': strings.ERR_FILE_COUNT.format(num_pic=num_pic, num_pdf=num_pdf)
            })
        return True

    msg = msgctrl.text
    if num_pic < 3 and msg == '[图片]':
        pic_file = msgctrl.save_pic()
        logger.info('Save image to %s', pic_file)
        task['files'].append({'type': 'pic', 'path': pic_file})
        task['num_pic'] += 1

    # 暂时不做PDF
    # elif num_pdf < 1 and msg == '[文件]':
    #     pdf_file = msgctrl.save_file()
    #     logger.info('Save file to %s', pdf_file)
    #     if Path(pdf_file).suffix.lower() == '.pdf':
    #         task['files'].append(
    #             {'type': 'pdf', 'path': pdf_file})
    #         task['num_pdf'] += 1

    if task['num_pic'] + task['num_pdf'] == 2:
        logger.info('Complete task option. Task: %s', task)
        return True
    else:
        return False


class BaoxianWeChatRpa:
    DOWNLOAD_CHECK_INTERVAL = 10 * 60

    def __init__(self, wechat, username, password):
        # self.file_mgr = TaskFileMgr('task_files')
        self.wechat = wechat
        self.username = username
        self.password = password

        self.screenshot_mgr = ScreenShotMgr('log/screenshot_wechat/')
        self.web_screenshot_mgr = ScreenShotMgr('log/screenshot_taiboweb/')

        self.robot_name = None
        self.__task_id = 0
        self.__flag_quit = False

        self.waiting_execute_tasks = {}
        self.waiting_recog = {}
        self.recoging_tasks = {}  # {task_id: task}

        self.waiting_approvals = {}  # {quotation_id: task}

        self.flag_download_insurance = True
        self.waiting_downloads = {}  # {quotation_id: task}

        # self.done_tasks = []
        self._baoxianweb = DajiabaoWeb(
            screenshotmgr=self.web_screenshot_mgr, username=self.username, password=self.password)
        # self._reporter = Reporter(
        #     report_dir='report/', baoxianweb=self._baoxianweb)
        self._cleanfile = CleanFile()

        self._task_handlers = {
            'order': self._process_new_order_task,
            'ping': self._process_ping_task,
        }

    def new_task_id(self):
        self.__task_id += 1
        return self.__task_id

    def send_msg(self, msg, recipient=None, task_hash=None):
        # self.wechat.select_chat(recipient)
        prefix = 'RPA'
        if task_hash:
            prefix += f'[{task_hash}]'
        self.wechat.send_msg(msg=prefix+': '+msg)

    def send_chat_msg(self, chat_name, msg, file_paths=None, recipient=None, task_hash=None):
        self.wechat.select_chat(chat_name)
        if file_paths:
            for file_path in file_paths:
                self.wechat.send_file(str(file_path))
        self.send_msg(msg=msg, recipient=recipient, task_hash=task_hash)

    def send_group_msg(self, msg, recipient=None, task_hash=None):
        prefix = 'RPA'
        if task_hash:
            prefix += f'[{task_hash}]'
        self.wechat.send_msg(msg=prefix+': '+msg, recipient=recipient)

    def send_chat_group_msg(self, chat_name, msg, file_paths=None, recipient=None, task_hash=None):
        self.wechat.select_chat(chat_name)
        if file_paths:
            for file_path in file_paths:
                self.wechat.send_file(str(file_path))
        self.send_group_msg(msg=msg, recipient=recipient, task_hash=task_hash)

    def next_weekday(self, start_date: date, weekday: int):
        days_ahead = weekday - start_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return start_date + timedelta(days_ahead)

    def parse_string(self, patterns: list, string: str) -> dict:
        """
        patterns:
            [
                {pattern: regex_with_name_group, required:true_or_false, msg: err_message}
            ]

        returns:
            {name: value, name: value} or {error, msg}
        """
        rst = {}
        for item in patterns:
            patterns = item['pattern']
            if not isinstance(patterns, list):
                patterns = [patterns, ]
            matches = None
            for pattern in patterns:
                pat_obj = re.compile(pattern)
                mtch = pat_obj.search(string)
                if mtch:
                    matches = mtch.groupdict()
                    string = pat_obj.sub('', string)
                    break
            else:
                if item.get('required'):
                    return {'error': errors.E_MSG, 'msg': item['msg']}
            filter_func = item.get('filter')
            if filter_func:
                matches = filter_func(
                    context={'values': rst.copy()}, matches=matches)
                if matches.get('error'):
                    return {'error': errors.E_MSG, 'msg': matches['msg']}
            rst.update(matches)
        return rst

    def parse_order_msg(self, msg) -> dict:
        logger.info('parse msg: %s', msg)
        msg = msg.replace(' ', '')
        msg = msg.replace('（', '(').replace('）', ')').replace('：', ':')
        msg = msg.replace(',', ' ').replace('，', ' ').replace('、', ' ')
        result = {}
        matches = re.search(r"(1[356789]\d{9})\b", msg)
        if not matches:
            return {'error': errors.E_MSG, 'msg': strings.err_no_mobile}
        else:
            result['mobile'] = matches.group(1)
            result['手机'] = matches.group(1)

        matches = re.search(r"([a-zA-Z0-9\._-]+@[a-zA-Z0-9\._-]+)", msg)
        if not matches:
            return {'error': errors.E_MSG, 'msg': strings.err_no_email}
        if matches:
            result['邮箱'] = result['email'] = matches.group(1)

        matches = re.search(r"(基础款|基本款|综合款)", msg)
        if matches:
            plan = matches.group(1)
            if plan == '基础款':
                plan = '基本款'
            result['plan'] = plan
        else:
            return {'error': errors.E_MSG, 'msg': '录单时请输入[基本款|综合款]'}

        matches = re.search(r"\((.*)\)", msg)
        if matches:
            customs = matches.group(1).split()
            plan_custom = {}
            for custom_str in customs:
                if ':' in custom_str:
                    rst = custom_str.split(':')
                    name = rst[0].strip()
                    if name.startswith('+'):
                        name = name[1:]
                    value = rst[1].strip()
                    # if name == '三者':
                    #     mat = re.search(r'\d+', value)
                    #     if mat:
                    #         num_str = mat.group(0)
                    #         if int(num_str) < 10000:
                    #             value = mat.group(0) + '0000'
                    # if value.endswith('万'):
                    #     value = value[:-1] + '0000'
                    plan_custom[name] = value
                # else:
                #     plan_custom[custom_str.strip()] = True
            key_maps = {
                '三者险': '三者',
                '车损险': '车损',
                '司机': '司机',
                '乘客': '乘客',
                '道路救援服务': '道路救援',
                '代驾': '代为驾驶',
                '折扣': '折扣系数',
            }
            valid_keys = set(key_maps.values())
            custom_options = {}
            for k, v in plan_custom.items():
                name = k
                prefix = ''
                # if k.startswith('-'):
                #     name = k[1:]
                #     prefix = '-'
                option_name = name
                if name in key_maps:
                    option_name = key_maps[name]
                if option_name not in valid_keys:
                    return {'error': errors.E_MSG, 'msg': '保险选项错误，可指定的选项是：{}。'.format('、'.join(valid_keys))}
                custom_options[prefix+option_name] = v
            result['plan_custom'] = custom_options

        matches = re.search(r'(生效)(日期)?:\s*(\d+-\d+-\d+)', msg)
        if matches:
            # result['生效'] = result['start_date'] = matches.group(3) + ' 00:00'
            result['生效'] = result['start_date'] = matches.group(3)

        matches = re.search(r'证件有效期:\s*(\d+-\d+-\d+)', msg)
        if matches:
            result['证件有效期'] = matches.group(1) + ' 00:00'

        matches = re.search(r'使用性质:\s*(\w+)', msg)
        if matches:
            result['使用性质'] = matches.group(1)

        matches = re.search(r'行车证车辆:\s*(\w+)', msg)
        if matches:
            result['行车证车辆'] = matches.group(1)

        matches = re.search(r'燃料种类:\s*(\w+)', msg)
        if matches:
            result['燃料种类'] = matches.group(1)

        logger.info('parse_order_msg has reslut: %s', result)
        return result

    def is_trigger(self, msg):
        prefix = '@'+self.robot_name
        return msg.startswith(prefix) and (strings.TRIGGER_WORD in msg[len(prefix):])

    def _collect_demo_task(self, chat_name):
        """ 
        tasks = [
            {
                error,
                msg,
                task_id,
                sender,
                email,
                mobile,
                plan,
                plan_custom,
                files:[
                    type: pic|pdf,
                    path
                ]
            }
        ]
        """
        msg_items = self.wechat.msg_items
        # tasks = []
        # re_task_hash = re.compile(r'^@.*? RPA\[([0-9a-f]+)\]')
        # re_reply = re.compile(r'^(RPA|@.*? RPA)')
        # can_reply_ping = True
        # has_new_cmd = True
        # done_cmd_hashs = set()
        # pending_sender_tasks = {}  # {sender: task}
        msgctrl = msg_items[-1]
        msg = msgctrl.text
        at_head = '@'+self.robot_name
        if not msg.startswith(at_head):
            return

        msg_content = msg[len(at_head):]
        if not('录单' in msg_content):
            return

        
        option_str = msg_content
        msg_hash = sha256(msg.encode('utf-8')).hexdigest()[:7]
        logger.info('Found @robot message(hash:%s): %s', msg_hash, msg)
        sender = msgctrl.sender.name
        task = {
            'chat': chat_name,
            'sender': sender,
            'task_id': self.new_task_id(),
            'task_hash': msg_hash,
            'num_pdf': 0,
            'num_pic': 0,
            'files': []
        }  # new task
        # for msgctrl in reversed(msg_items):
        #     msg = msgctrl.text
        #     if msg == '[文件]':
        #         pdf_file = msgctrl.save_file()
        #         task['files'].append(
        #             {'type': 'pdf', 'path': pdf_file})
        #         task['num_pdf'] += 1
        #         break

        msgctrl = msg_items[-2]
        msg = msgctrl.text
        if msg != '[文件]':
            logger.error('Previous message is not file.')
            return
        pdf_file = msgctrl.save_file()
        task['files'].append(
            {'type': 'pdf', 'path': pdf_file})
        task['num_pdf'] += 1

        send_msgs = [
            '请提供清晰的身份证照片（无反光，水印勿遮挡重要信息）',
            '请提供实名认证的手机号（若手机号为他人注册，则提供手机号登记人的身份证信息：包括姓名、身份证号）',
            '请提供邮箱'
        ]
        for smsg in send_msgs:
            logger.info('send msg: %s', smsg)
            self.send_group_msg(msg=smsg)
            while True:
                msgctrl = self.wechat.msg_items[-1]
                msg = msgctrl.text
                if smsg in msg:
                    time.sleep(1)
                    continue
                elif msg == '[图片]':
                    pic_file = msgctrl.save_pic()
                    task['files'].append(
                        {'type': 'pic', 'path': pic_file})
                    task['num_pic'] += 1
                    break
                else:
                    logger.info('get msg: %s', msg)
                    option_str += ' ' + msg
                    break
        msg_option = self.parse_order_msg(option_str)
        if 'error' in msg_option:
            self.send_group_msg(
                recipient=sender, task_hash=msg_hash, msg=msg_option['msg'])
        else:
            task.update(msg_option)
            task['options'] = msg_option
            task['num_recoging'] = 0
            for fl in task['files']:
                recog_id = uuid.uuid4()
                self.async_recog.put_task(
                    {'recog_id': recog_id, 'type': fl['type'], 'path': fl['path']})
                self.waiting_recog[recog_id] = task
                task['num_recoging'] += 1
            self.recoging_tasks[task['task_id']] = task
            mobile = task['手机']
            msg = strings.NEW_TASK.format(mobile=mobile)
            self.send_group_msg(recipient=sender, task_hash=msg_hash, msg=msg)

    def _process_new_order_task(self, task: dict):
        """发送收到录单任务提示，放入等待处理字典，

        Args:
            task(dict): 任务大字典，一个task就是一个录单任务
        """
        sender = task['sender']
        task_hash = task['task_hash']
        if 'error' in task:
            msg = task['msg']
        else:
            self.waiting_execute_tasks[task['task_id']] = task
            mobile = task['手机']
            msg = strings.NEW_TASK.format(mobile=mobile)
        self.send_msg(recipient=sender, task_hash=task_hash, msg=msg)

    def _process_ping_task(self, task: dict):
        sender = task['sender']
        task_hash = task['task_hash']
        self.send_msg(recipient=sender, task_hash=task_hash, msg='pong')

    def _get_new_msg(self, interval: float) -> str:
        new_msg = None
        now = time.time()
        timeout = now + interval
        while now < timeout:
            last_item = self.wechat.msg_items[-1]
            if last_item.sender.type != 'self':
                new_msg = last_item.text
                break
            time.sleep(1)
            now = time.time()
        return new_msg


    def _collect_chat_task(self, chat_name):
        """
        处理所有信息，包括指令和图文，返回tasks列表
        tasks = [
            {
                error,
                msg,
                task_id,
                sender,
                email,
                mobile,
                plan,
                plan_custom,
                files:[
                    type: pic|pdf,
                    path
                ]
            }
        ]
        """
        msg_items = self.wechat.msg_items
        tasks = []
        done_cmd_hashs = set()
        has_new_cmd = True
        pending_sender_tasks = {}  # 还未完成信息收集的任务，格式：{sender: task}。
        for msgctrl in reversed(msg_items):
            if (not has_new_cmd) and (not pending_sender_tasks):
                # logger.info('stop scanning message in chat %s', chat_name)
                break

            msg = msgctrl.text
            if msg.startswith('RPA') and msgctrl.sender.type == 'self':
                has_new_cmd = False
                continue

            # 检测机器人收到录单任务 就把任务“RPA[3ddc586]”的单号3ddc586放进done_cmd_hashs集合，返会for循环检测下一条消息
            re_task_hash = re.compile(r'RPA\[([0-9a-f]+)\]')
            mtch = re_task_hash.search(msg)
            if mtch:
                cmd_hash = mtch.group(1)
                logger.info('Find cmd messge hash: %s', cmd_hash)
                done_cmd_hashs.add(cmd_hash)
                continue

            at_head = '@录单'
            sender = msgctrl.sender.name
            if msg.startswith(at_head):
                msg = msg.replace('\r', ' ').replace('\n', ' ')
                msg_hash = sha256(msg.encode('utf-8')).hexdigest()[:7]
                logger.info('Found  message(hash:%s): %s', msg_hash, msg)
                sender = msgctrl.sender.name
                # 这里表明匹配到了之前一个任务的 录单...  说明再往前没有新信息了，不需要再for消息列表了
                # 从pending_sender_tasks拿出核心的task字典，并清空pending_sender_tasks，去除task里面的_handle_order_msg函数，放入tasks
                if sender in pending_sender_tasks:
                    task = pending_sender_tasks[sender]
                    del pending_sender_tasks[sender]
                    task['handler'](task=task, end=True)
                    del task['handler']
                    tasks.append(task)
                    # logger.error('Get task: %s', task)

                # 任务已经被记录就不再记录
                if msg_hash in done_cmd_hashs:
                    logger.info('Message has been processed.')
                    # for循环信息列表找到 上个任务的 @www.pu RPA【xxooxxoo】和 @机器人录单。。后表示该任务处理过，往上已经没有新任务了，不需要再for
                    has_new_cmd = False
                    continue

                new_task = {
                    'chat': chat_name,
                    'sender': sender,
                    'task_id': self.new_task_id(),
                    'task_hash': msg_hash,
                }

                msg_content = msg[1:]
                if '录单' in msg_content:
                    new_task['task_type'] = 'order'
                    new_task.update({
                        'num_pdf': 0,
                        'num_pic': 0,
                        'files': []
                    })
                    msg_option = self.parse_order_msg(msg)
                    new_task.update(msg_option)
                    if 'error' in msg_option:
                        logger.info('Task option error: %s', msg_option)
                        tasks.append(new_task)
                    else:
                        # new_task['options'] = msg_option # 不要这个了
                        new_task['handler'] = _handle_order_msg # 函数：检查pdf和图片，并保存
                        pending_sender_tasks[sender] = new_task
                elif 'ping' in msg_content:
                    new_task['task_type'] = 'ping'
                    tasks.append(new_task)
                continue # 直接返回去处理其他的消息

            # 匹配到当前任务上一个 录单指令 则不再网上查找材料，查看图片材料是否够了
            elif re.search('录单', msg) and sender in pending_sender_tasks:
                logger.info('Find pre task: %s', msg)
                task = pending_sender_tasks[sender]
                del pending_sender_tasks[sender]
                task['handler'](task=task, end=True)  # new_task['handler'] = _handle_order_msg  # 函数：检查pdf和图片，并保存
                del task['handler']
                tasks.append(task)
                has_new_cmd = False
                continue

            # pdf和pic消息直接就到这里了
            if pending_sender_tasks:
                sender = msgctrl.sender.name
                if sender not in pending_sender_tasks:
                    continue
                task = pending_sender_tasks[sender]
                try:
                    handler = task['handler']
                    completed = handler(task=task, msgctrl=msgctrl)  # new_task['handler'] = _handle_order_msg  # 函数：检查pdf和图片，并保存
                    if not completed: # 收集完毕则继续往下走，还没够就直接返回循环继续收集下一条
                        continue
                except:
                    logger.exception('error when save %s', msg)
                    task.update({
                        'error': errors.E_UNKOWN,
                        'msg': strings.ERR_SAVE_FILE
                    })
                del pending_sender_tasks[sender]
                del task['handler']
                tasks.append(task)

        # 信息列表for完毕，没有遇到任务发送者的上一个'录单指令'，或者材料数量没有大于2，任务收集结束，走这里如果缺少材料提醒缺少材料
        for task in pending_sender_tasks.values():
            handler = task['handler'] # new_task['handler'] = _handle_order_msg  # 函数：检查pdf和图片，并保存
            handler(task=task, end=True)
            del task['handler']
            tasks.append(task)
            logger.error('Get task: %s', task)

        return tasks

    def handle_chat_task(self, chat_name):
        try:
            if settings.CHAT_PROCESS_MODE == 0:
                # 收集页面任务，保存图片文件等，返回任务列表
                tasks = self._collect_chat_task(chat_name=chat_name)
                for task in reversed(tasks):
                    # 根据任务类型order|ping|service去拿到相应的函数，如order就是self._process_new_order_task(task)
                    # 对于task的files中的需要识别的任务 AsyncTaskExecutor.__que_task.put(task)，去识别
                    # task新增{num_recoging：2}
                    # self.waiting_recog = {uuid：task}
                    # self.recoging_tasks ={task_id：task}
                    # 发送'收到录单任务，手机：{mobile}。任务处理中，请稍候
                    # self._process_new_order_task(task)
                    #### 看完全注释掉上面一句
                    self._task_handlers[task['task_type']](task)
                return tasks
            else:
                logger.error('Unexpected CHAT_PROCESS_MODE: %d', settings.CHAT_PROCESS_MODE)

        except:
            logger.exception('has error in handling chat task.')
            self.wechat.back_to_main_win()
            # self.send_group_msg(msg='处理任务遇到问题，请重试。')
            self.wechat.select_first_chat()

    def handle_next_chat(self):
        curr_chat_name = self.wechat.current_chat_name
        try:
            if curr_chat_name in ('文件传输助手', '腾讯新闻', '订阅号', '微信团队'):
                self.wechat.del_chat(curr_chat_name)
            else:
                tasks = self.handle_chat_task(chat_name=curr_chat_name)
                if tasks:
                    return curr_chat_name
        except:
            self.wechat.del_chat(curr_chat_name)
        for chat_name in self.wechat.next_chat():
            # logger.info('At message in chat: %s', chat_name)
            curr_chat_name = chat_name
            tasks = self.handle_chat_task(chat_name)
            if tasks:
                return curr_chat_name

    def signal_handler(self, sig, frame):
        logger.info('Exiting by ctrl+c.')
        self.__flag_quit = True

    def _get_waiting_execute_task(self):
        logger.info(f"_get_waiting_execute_task has tasks:{self.waiting_execute_tasks.keys()}")
        logger.info(f"_get_waiting_execute_task has tasks:{self.waiting_execute_tasks}")
        done_tasks = []
        has_done_task = []
        for task_id,task in self.waiting_execute_tasks.items():
            has_done_task.append(task_id)
            # del self.waiting_execute_tasks[task_id]
            done_tasks.append(task)
        for task_id in has_done_task:
            del self.waiting_execute_tasks[task_id]
        return done_tasks

    def download_insurance_ticket(self):
        if not self.waiting_downloads:
            return
        quot_ids = list(self.waiting_downloads)
        result = self._baoxianweb.get_insurance_files(quot_ids)
        if 'error' in result:
            file_paths = (result['screenshot'],
                          ) if 'screenshot' in result else None
            msg = strings.ERR_INSURANCE_DOWNLOAD
            for task in self.waiting_downloads.values():
                self.send_chat_msg(
                    chat_name=task['chat'],
                    recipient=task['sender'],
                    task_hash=task['task_hash'],
                    msg=msg,
                    file_paths=file_paths)
            self.waiting_downloads = {}
        else:
            for quot_id, pdfs in result['content'].items():
                task = self.waiting_downloads[quot_id]
                del self.waiting_downloads[quot_id]
                name = task['姓名']
                msg = strings.INSURANCE_TICKET.format(
                    name=name, quotation_id=quot_id)
                sender = task['sender']
                logger.info(
                    'reply to sender %s of quotation: %s with pdfs: %s', sender, quot_id, pdfs)
                self.send_chat_msg(
                    chat_name=task['chat'],
                    recipient=task['sender'],
                    task_hash=task['task_hash'],
                    msg=msg,
                    file_paths=pdfs)
                # if '订单号' in task:
                #     title = get_title(task)
                #     msg = strings.CUSTOMER_INSURANCE_MSG.format(name=name+title)
                #     self._send_insurance_and_video(
                #         order_id=task['订单号'],
                #         msg=msg,
                #         files=pdfs
                #     )

    def set_download_insurance_flag(self):
        self.flag_download_insurance = True


    def _send_insurance_and_video(self, order_id: str, msg: str, files):
        """发送电子保单和公众号介绍视频
        """
        chat_name = self.wechat.select_chat_with(order_id)
        if chat_name:
            for file in files:
                self.wechat.send_file(filepath=file)
            self.wechat.send_msg(msg=msg)
            video_file = Path('res/vid/上海太保.mp4').absolute()
            self.wechat.send_file(str(video_file))
            msg = '请用投保时提供的的实名制信息绑定我司官微以便于查询和使用您的增值服务权益，具体操作流程详见视频，如有疑问可咨询人工服务专员。'
            self.wechat.send_msg(msg=msg)

    def send_to_order_chat(self, order_id: str, msg: str, files):
        """发送给群名里有order_id的群
        """
        chat_name = self.wechat.select_chat_with(order_id)
        if chat_name:
            for file in files:
                self.wechat.send_file(filepath=file)
            self.wechat.send_msg(msg=msg)

    def _apply_new_insurance(self, task):
        """apply new insurance
        """
        self.wechat.win_main.minimize()
        result = self._baoxianweb.apply_insurance_ticket(task) # quotation_id,qrcode,quotation_preview
        print(f'_apply_new_insurance result:{result}')
        self.wechat.win_main.maximize()
        if 'error' in result:
            file_paths = (
                result['screenshot'],) if 'screenshot' in result else None
            self.send_chat_msg(
                chat_name=task['chat'],
                recipient=task['sender'],
                task_hash=task['task_hash'],
                msg=result['msg'],
                file_paths=file_paths)

        else:
            new_task = result['content']
            quotation_id = new_task['quotation_id']
            name = new_task['车主姓名']
            if 'quotation_preview' in new_task:
                msg = '这是保险单{}的预览。'.format(quotation_id)
                self.send_chat_msg(
                    chat_name=task['chat'],
                    recipient=task['sender'],
                    task_hash=task['task_hash'],
                    msg=msg,
                    file_paths=(new_task['quotation_preview'],))

            if 'qrcode' in new_task:
                qrcode = new_task['qrcode']
                # msg = strings.qrcode.format(name=name, quotation_id=quotation_id)
                msg = strings.qrcode.format(name=name)
                self.send_chat_msg(
                    chat_name=task['chat'],
                    recipient=task['sender'],
                    task_hash=task['task_hash'],
                    msg=msg,
                    file_paths=(qrcode,))
                # if '订单号' in task:
                #     title = get_title(task)
                #     msg = strings.CUSTOMER_PAY_MSG.format(
                #         name=name+title)
                #     self.send_to_order_chat(
                #         order_id=task['订单号'],
                #         msg=msg,
                #         files=[
                #             new_task['quotation_preview'],
                #             qrcode,
                #         ]
                #     )
                self.waiting_downloads[quotation_id] = new_task


    def loop(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.robot_name = self.wechat.name
        logger.info('robot name: %s', self.robot_name)
        self.wechat.del_chat('文件传输助手')
        self.wechat.select_first_chat()
        logger.info('Rpa start looping')
        while True:
            try:
                if self.__flag_quit:
                    break
                if not self.wechat.win_main.exists():
                    logger.error('Wechat main window does not exist. Quit rpa.')
                    break

                # 每天晚上清理保存的pdf等文件
                self._cleanfile.start_clean('log')
                # 关闭更新界面
                self.wechat.handle_updatewnd_dlg()
                # 关闭搜索聊天记录界面
                self.wechat.handle_msg_search_wnd()

                if self.flag_download_insurance:
                    self.download_insurance_ticket()
                    self.flag_download_insurance = False
                    timer = threading.Timer(
                        self.DOWNLOAD_CHECK_INTERVAL, self.set_download_insurance_flag)
                    timer.daemon = True
                    timer.start()

                tasks = self._get_waiting_execute_task()
                logging.info(f'_get_waiting_execute_task has tasks:{tasks}')
                for task in tasks:
                    if 'error' in task:
                        self.send_chat_msg(
                            chat_name=task['chat'],
                            recipient=task['sender'],
                            task_hash=task['task_hash'],
                            msg=task['msg'])
                        continue
                    logger.info('Task for new insurance: %s', task)
                    self._apply_new_insurance(task)
                print('loop826', self.waiting_downloads)
                self.handle_next_chat()
                time.sleep(1)
                # 移动鼠标防止锁屏
                # coordx = random.randint(100, 200)
                # mouse.move(coords=(coordx, coordx))
            except:
                logger.exception('error in loop. continue.')
                try:
                    screenshot_path = self.screenshot_mgr.new_screenshot_name()
                    ImageGrab.grab().save(screenshot_path)
                    logger.error('screenshot is %s', screenshot_path)
                except:
                    pass
                if self.wechat.win_main.exists():
                    self.wechat.back_to_main_win()
                    self.wechat.select_first_chat()
                continue

