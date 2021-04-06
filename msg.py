
rex_trigger = '@{robot_name}.*录单'
TRIGGER_WORD = '录单'
rpa_ticket = '已收到{num_pdf}个PDF和{num_pic}个图片，后台录单中请稍候。'
NEW_TASK = '收到录单任务，手机：{mobile}。任务处理中，请稍候。'
# qrcode = '报价单{quotation_id}的{name}客户的付款二维码。'
qrcode = '{name}客户的订单信息和付款二维码，请确认信息并及时付款。'
WAIT_APPROVAL = '{name}客户的报价单已提交，单号是{quotation_id}，等待审核中。'
INSURANCE_TICKET = '{name}客户的保单{quotation_id}的电子保单。'
CUSTOMER_PAY_MSG = '尊敬的{name}，请您确认以上保险方案。确认后请于30分钟内二维码支付。如需修改可联系业务人员。'
CUSTOMER_INSURANCE_MSG = '尊敬的{name}，这是您的电子保单。如由问题可联系业务人员。'

err_recognize = '未能识别材料内容。请人工处理。'
err_network = '后台识别服务请求失败，请重试或人工处理。'
err_unknown = '遇到未知错误，请重试或人工处理。'
ERR_UNKNOWN = '遇到未知错误，请重试或人工处理。'
ERR_SAVE_FILE = '保存材料遇到未知错误，请重试或人工处理。'
err_no_mobile = '录单时请输入手机号。'
err_no_seat = '录单时请输入座位数，如： 5座。'
err_no_email = '录单时请输入邮箱。'
err_no_insurance_plan = '录单时请输入[基本款|优质款|尊享款]。'
ERR_NO_DATE='没有输入时间。请输入"生效:2020-01-01"格式的时间。'

ERR_WRONG_IDENT = '图片未能正确识别为身份证或发票。请人工处理。'
ERR_WRONG_VEH_FILE = '未能识别PDF文件。请检查PDF是否为车辆合格证或购车发票。'
ERR_WRONG_VEH_PIC = '未能识别PIC，可能是车辆合格证或者发票识别错误。'
ERR_INSURANCE_DOWNLOAD = '未能下载电子保单，请人工处理。'
ERR_MAKE_QRCODE ='未能创建支付二维码，请人工处理。'
# ERR_FILE_COUNT = '收到{num_pic}张图片和{num_pdf}张PDF文件。录单需要一张车辆合格证(PDF/PIC)或发票(PDF/PIC)和一张身份证图片，企业单还需要一张营业执照相片。请重新输入。'
ERR_FILE_COUNT = '收到{num_pic}张图片和{num_pdf}张PDF文件。录单需要一张车辆行驶证PIC和一张身份证图片。请重新输入。'

# 大家保话术
ERR_CITY_MATCH = "没有找到对应的 市"
ERR_AREA_MATCH = "没有找到对应的县、区"
ERR_IDCARD_RECOGNIZE = "身份证识别失败"
ERR_CAR_INFO_RECOGNIZE = "行驶证识别失败"
ERR_MSG_LOAD = "推荐人等信息未正常加载"
ERR_CUSTOMER_CONFIRM = "客户确认失败:{err_msg}"