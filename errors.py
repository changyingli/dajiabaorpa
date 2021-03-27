E_UNKOWN = 'e_unknown'
E_NETWORK = 'e_network'
E_SERVER = 'e_server'
E_PROC = 'e_proc' # 流程操作出错
E_MSG = 'e_msg' #微信消息解析出错

class RpaError(Exception):
    """Error for Rpa

    Attributes:
        error -- error code
        message -- error message
    """
    def __init__(self, error, message):
        self.error = error
        self.message = message