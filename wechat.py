import io
import re
import time
from typing import NamedTuple, Iterable, Literal

import keyboard
from pywinauto import mouse
from pywinauto.timings import TimeoutError
from pywinauto.application import Application

from file import WeChatFilePath


class Sender(NamedTuple):
    name: str
    type: Literal['user', 'wechat', 'self']


def mouse_scroll(control, distance):
    rect = control.rectangle()
    cx = int((rect.left+rect.right)/2)
    cy = int((rect.top + rect.bottom)/2)
    mouse.scroll(coords=(cx, cy), wheel_dist=distance)


class SaveAsDlg:
    def __init__(self, parent_win):
        self.dialog = parent_win.child_window(class_name='#32770')
        self.dialog.wait('ready')

    @property
    def file_suffix(self):
        ftctrl = self.dialog.child_window(auto_id='FileTypeControlHost')
        matches = re.search(r'\(*(\..*)\)', ftctrl.selected_text())
        return matches.group(1)

    def save(self, file_path):
        fnctrl = self.dialog.child_window(title="文件名:", auto_id="1001", control_type="Edit")
        fnctrl.type_keys(file_path, with_spaces=True)
        self.dialog.child_window(title="保存(S)", auto_id="1", control_type="Button").click()
        self.dialog.wait_not('visible')


class OpenFileDlg:
    def __init__(self, wechat):
        self.dialog = wechat.win_main.child_window(class_name='#32770')
        self.dialog.wait('ready')

    def open_file(self, file_path):
        fnctrl = self.dialog.child_window(title="文件名(N):", auto_id="1148", control_type="Edit")
        # fnctrl.set_text(file_path)
        fnctrl.type_keys(file_path, with_spaces=True)
        self.dialog.child_window(title="打开(O)", control_type="SplitButton").click_input()
        self.dialog.wait_not('visible')


class ImagePreview:
    def __init__(self, wechat):
        self.imageviewer = wechat.app.window(class_name='ImagePreviewWnd')
        self.imageviewer.wait('ready')

    def close(self):
        self.imageviewer.close()

    def open_saveas_dlg(self) -> SaveAsDlg:
        saveas_btn = self.imageviewer.child_window(title='另存为', control_type='Button')
        saveas_btn.wait('ready')
        try:  # try twice
            saveas_btn.click_input()
            return SaveAsDlg(self.imageviewer)
        except:
            saveas_btn.click_input()
            return SaveAsDlg(self.imageviewer)


class MsgItem:
    def __init__(self, wechat, msg_list, msg_item):
        self.wechat = wechat
        self.msg_list = msg_list
        self.msg_item = msg_item
        self._text = None
        self._sender = None

    @property
    def text(self):
        if not self._text:
            self._text = self.msg_item.window_text()
        return self._text

    @property
    def sender_btn(self):
        btns = self.msg_item.descendants(control_type='Button')
        if btns:
            return btns[0]
        else:
            return None

    # @property
    # def sender(self):
    #     if not self._sender:
    #         btn = self.sender_btn
    #         if btn:
    #             self._sender = btn.window_text()
    #     return self._sender

    @property
    def sender(self) -> Sender:
        """Get sender name and type.

        returns:
            return named tuple (name, type). `name` is sender name. `type` is 'user', 'wechat' or 'self'.
        """
        if self._sender:
            return self._sender
        c0 = self.msg_item.children()
        if c0:
            c1 = c0[0].children()
            if c1:
                btn = c1[0]
                if btn.element_info.control_type == 'Button':
                    self._sender = Sender(btn.window_text(), 'user')
                else:
                    btn = c1[-1]
                    if btn.element_info.control_type == 'Button':
                        self._sender = Sender(btn.window_text(), 'self')
        if not self._sender:
            self._sender = Sender('wechat', 'wechat')

        return self._sender


    def scroll_visible(self):
        p_rect = self.msg_list.rectangle()
        up = p_rect.top
        down = p_rect.bottom
        up += 5
        down -= 5
        rect = self.msg_item.rectangle()
        center_y = (rect.top + rect.bottom)/2
        if center_y > up and center_y < down:
            return
        self.msg_list.click_input(coords=(p_rect.left+5, up), absolute=True)
        while center_y < up:
            self.msg_list.type_keys('{PGUP}')
            time.sleep(0.1)
            rect = self.msg_item.rectangle()
            center_y = (rect.top + rect.bottom)/2

        while center_y > down:
            self.msg_list.type_keys('{PGDN}')
            time.sleep(0.1)
            rect = self.msg_item.rectangle()
            center_y = (rect.top + rect.bottom)/2

    def at_sender(self):
        self.scroll_visible()
        self.sender_btn.right_click_input()
        menu = self.wechat.win_main.child_window(class_name='CMenuWnd')
        menu.wait('ready')
        menu.click_input()

    def save_pic(self) -> str:
        self.scroll_visible()
        btns = self.msg_item.descendants(control_type='Button')
        btns[-1].click_input()
        impreview = ImagePreview(self.wechat)
        try:
            dlg = impreview.open_saveas_dlg()
            suffix = dlg.file_suffix
            flpath = self.wechat.filemgr.unique_file_path(suffix)
            dlg.save(flpath)
        finally:
            impreview.close()
        return flpath

    def save_file(self) -> str:
        self.scroll_visible()
        btns = self.msg_item.descendants(control_type='Button')
        btns[-1].right_click_input()
        # TODO close menu when no saveas item in menu.
        self.wechat.win_main.child_window(class_name='CMenuWnd').child_window(
            title='另存为...', control_type='MenuItem').click_input()
        dlg = SaveAsDlg(self.wechat.win_main)
        suffix = dlg.file_suffix
        flpath = self.wechat.filemgr.unique_file_path(suffix)
        dlg.save(flpath)
        return flpath


class ChatTip:
    """@了我 界面"""
    def __init__(self, win_main):
        self.win_chattip = win_main.child_window(class_name='ChatTipsBarWnd')

    def exists(self):
        return self.win_chattip.exists()

    def close(self):
        self.win_chattip.descendants(control_type='Button')[-1].click_input()


class ChatWnd:
    """双击聊天项，出现的个人聊天窗口
    """
    def __init__(self, wechat):
        self.chatwnd = wechat.app.window(class_name='ChatWnd')
        self.edit_btn = self.chatwnd.child_window(title='输入', control_type='Edit')

    def close(self):
        self.chatwnd.close()

    def exists(self):
        return self.chatwnd.exists()

class FTSMsgSearchWnd:
    """搜索聊天记录弹窗界面
    """
    def __init__(self, wechat):
        self.msg_search_wnd = wechat.app.window(class_name='FTSMsgSearchWnd')

    def close(self):
        self.msg_search_wnd.close()

    def exists(self):
        return self.msg_search_wnd.exists()


class WeChat:
    def __init__(self):
        self.app = None
        self.__win_main = None
        self.__msg_edit = None
        self.current_chat_name = None
        self.filemgr = WeChatFilePath('log/wechat_files/')

    def start(self):
        self.filemgr.mkdir()
        self.app = Application(backend="uia").start(r'C:\Program Files (x86)\Tencent\WeChat\WeChat.exe')

    def quit(self):
        self.app.kill()

    @property
    def win_login(self):
        return self.app.window(class_name='WeChatLoginWndForPC')

    @property
    def win_main(self):
        if not self.__win_main:
            self.__win_main = self.app.window(class_name='WeChatMainWndForPC')
        return self.__win_main

    @property
    def name(self):
        return self.win_main.children()[1].children()[1].children()[0].children()[0].children()[0].window_text()

    @property
    def msg_edit(self):
        if not self.__msg_edit:
            self.__msg_edit = self.win_main.window(title="输入", control_type="Edit")
        return self.__msg_edit

    @property
    def msg_list(self):
        return self.win_main.child_window(control_type="List", title="消息")

    @property
    def file_saveas_dlg(self) -> SaveAsDlg:
        return SaveAsDlg(self.win_main)

    @property
    def image_prevew(self) -> ImagePreview:
        return ImagePreview(self)

    @property
    def msg_items(self):
        return [MsgItem(self, self.msg_list, item) for item in self.msg_list.items()]

    @property
    def chattip(self):
        return ChatTip(self.win_main)

    @property
    def chat_wnd(self) -> ChatWnd:
        return ChatWnd(self)

    @property
    def msg_search_wnd(self) -> FTSMsgSearchWnd:
        return FTSMsgSearchWnd(self)

    @property
    def chat_list(self):
        return self.win_main.child_window(control_type='List', title='会话')

    @property
    def visible_chat_items(self):
        chat_list = self.chat_list
        rect = chat_list.rectangle()
        top = rect.top + 5
        bottom = rect.bottom - 5
        chat_items = chat_list.items()
        first = 0
        for chat in chat_list:
            rect = chat.rectangle()
            center = (rect.top + rect.bottom) / 2.0
            if center < top:
                first += 1
            else:
                break
        last = len(chat_items)
        for chat in reversed(chat_items):
            rect = chat.rectangle()
            center = (rect.top + rect.bottom) / 2.0
            if center > bottom:
                last -= 1
            else:
                break
        return chat_items[first:last]

    def back_to_main_win(self):
        while True:
            dlg = self.app.top_window()
            if dlg.class_name() == 'WeChatMainWndForPC':
                break
            else:
                dlg.close()

    def chat_scroll_top(self):
        prev_chat = None
        while True:
            curr_chat = self.chat_list.items()[0]
            if prev_chat == curr_chat:
                break
            else:
                prev_chat = curr_chat
                try:
                    self.chat_list.scroll(direction='up', amount='page')
                except:
                    return

    def select_first_chat(self) -> str:
        self.chat_scroll_top()
        first = self.chat_list.items()[0]
        first.click_input()
        time.sleep(0.5)
        self.current_chat_name = first.window_text()
        return self.current_chat_name

    # def next_at_chat(self) -> str:
    #     self.chat_scroll_top()
    #     while True:
    #         items = self.chat_list.items()
    #         has_at_chat = False
    #         for chat in items:
    #             ats = chat.descendants(control_type='Text', title='[有人@我]')
    #             if ats:
    #                 has_at_chat = True
    #                 chat.click_input()
    #                 self.current_chat_name = chat.window_text()
    #                 yield self.current_chat_name
    #         if not has_at_chat:
    #             break
    #         else:
    #             try:
    #                 # self.chat_list.scroll(direction='down', amount='page')
    #                 mouse_scroll(control=self.chat_list, distance=-5)
    #                 time.sleep(0.5)
    #             except:
    #                 break

    def next_chat(self) -> str:
        """逐个点击可见chat列表
        """
        self.chat_scroll_top()
        num = 0
        while num < 2:
            items = self.visible_chat_items
            if not items:
                return
            # items = self.chat_list.items()
            # if not items:
            #     return
            for chat in items:
                if chat.window_text() in ('文件传输助手', '腾讯新闻', '订阅号', '微信团队'):
                    self.del_chat(chat.window_text())
                    continue

                chat.click_input()
                try:
                    # 如果出现放大的个人聊天窗口，关闭
                    if self.chat_wnd.exists():
                        self.chat_wnd.close()
                        continue
                        # break
                    self.msg_edit.wait('exists')
                    self.current_chat_name = chat.window_text()
                    try:
                        # 过滤群聊不回复
                        # 右上角...
                        ele = self.win_main.child_window(title='聊天信息', control_type='Button')
                        # 聊天界面左上角群名/群备注名/个人名
                        name_btn = ele.parent().parent().descendants(control_type='Button')[0]
                        # print(name_btn.window_text())
                        btn_group_chat = name_btn.parent().children()
                        # 群聊处理：群聊名后会多带一个(num)项，微信3.0.1.41版本升级，结构变化，
                        # 企业微信群3：群名+人数+图标
                        # 微信群2：群名+人数
                        # 企业用户2：名字+公司名
                        # 微信用户1：名字
                        if len(btn_group_chat) != 1:
                            if len(btn_group_chat) == 2:
                                enterprise_re = re.search('^@.+', btn_group_chat[1].window_text())
                                if not enterprise_re:
                                    self.del_chat(self.current_chat_name)
                                    continue
                            else:
                                self.del_chat(self.current_chat_name)
                                continue
                    except BaseException as e:
                        print(f'next_chat_all_msg btn_group_chat error has msgs: {e}')
                        # logger.exception('next_chat_all_msg btn_group_chat error has msgs: <%s>', e)

                    yield self.current_chat_name
                    # break
                except:
                    if num == 2:
                        self.del_chat(chat.window_text())
                    num += 1
                    continue


    def select_chat(self, chat_name) -> str:
        """通过名字查找聊天，只找前两页
        returns:
            chat_name or None
        """
        self.chat_scroll_top()
        last_chat = None
        times = 0
        while times < 2:
            items = self.chat_list.items()
            if not items:
                return
            # if items[-1] == last_chat:
            #     return None
            # else:
            #     last_chat = items[-1]

            for chat in items:
                if chat_name == chat.window_text():
                    chat.click_input()
                    self.current_chat_name = chat_name
                    return chat_name
            try:
                mouse_scroll(control=self.chat_list, distance=-5)
                times += 1
                time.sleep(0.5)
            except:
                return

    def select_chat_with(self, name) -> str:
        """select chat which name contains `name`.

        return:
            chat_name if succeed, or None if cannot find.
        """
        self.chat_scroll_top()
        last_chat = None
        while True:
            items = self.chat_list.items()
            if items[-1] == last_chat:
                return None
            else:
                last_chat = items[-1]

            for chat in items:
                chat_name = chat.window_text()
                if chat_name and (name in chat_name):
                    chat.click_input()
                    self.current_chat_name = chat_name
                    return chat_name
            try:
                self.chat_list.scroll(direction='down', amount='page')
                time.sleep(0.5)
            except:
                return None

    def send_msg(self,  msg: str, recipient: str = None):
        self.msg_edit.click_input()
        if recipient:
            for msg_item in reversed(self.msg_items):
                if msg_item.sender.name != recipient:
                    continue
                else:
                    msg_item.at_sender()
                    time.sleep(0.5)
                    break

        # msg = msg.replace('{', '{{').replace('}', '}}').replace('{{', '{{}').replace('}}', '{}}')
        # msg = msg.replace('+', '{+}').replace('^', '{^}').replace('%', '{%}')
        # self.msg_edit.type_keys(msg, with_spaces=True)
        # self.msg_edit.type_keys('{ENTER}')
        for line in io.StringIO(msg):
            keyboard.write(line.strip())
            keyboard.send('ctrl+enter')
        keyboard.send('enter')

    reply_msg = send_msg

    def send_file(self, filepath: str):
        self.win_main.child_window(title='发送文件', control_type='Button').click_input()
        openfiledlg = OpenFileDlg(self)
        openfiledlg.open_file(filepath)
        self.msg_edit.type_keys('{ENTER}')

    reply_file = send_file

    def del_chat(self, chat_name):
        """删除聊天
        """
        # self.chat_scroll_top()
        times = 0
        while True:
            items = self.chat_list.items()
            if not items:
                return
            if times > 1:
                return None
            for chat in items:
                if chat_name == chat.window_text():
                    chat.right_click_input()
                    try:
                        a = self.app.window(class_name='CMenuWnd').descendants(title='删除聊天', control_type='MenuItem')[0]
                        a.click_input()
                        return True
                    except:
                        continue
            try:
                mouse_scroll(control=self.chat_list, distance=-5)
                times += 1
                time.sleep(0.5)
            except:
                return None


    def handle_updatewnd_dlg(self):
        """关闭更新提示界面
        """
        dialog = self.win_main.child_window(title="新版本", class_name="UpdateWnd")
        if dialog.exists():
            dialog.child_window(title='忽略这次更新', control_type='Button').click_input()

    def handle_msg_search_wnd(self):
        """关闭偶尔失误打开的搜索聊天记录界面
        """
        if self.msg_search_wnd.exists():
            self.msg_search_wnd.close()