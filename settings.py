from datetime import time

CLEAN_TIME = time(hour=23,minute=30) # 每天清理文件时间
REPORT_TIME = time(hour=17)  # 每天生成报告的时间
ADMIN = 'admin' # Admin的微信名

CHAT_PROCESS_MODE = 0 # 正常逻辑
# CHAT_PROCESS_MODE = 1 # demo 逻辑


PLANS = {
    '基本款': {
        '三者': '100',
        '车损': '10000',
        '司机': '10000',
        '乘客': '10000',
        '道路救援': '2',
        '代为驾驶': '1',
        '折扣系数': '1.35',
    },
    '综合款': {
        '三者': '100',
        '车损': '10000',
        '司机': '10000',
        '乘客': '10000',
        '道路救援': '2',
        '代为驾驶': '1',
        '折扣系数': '1.35',
    },
}

# 行驶证车辆
LICEENSE_VEHICLE = {'J13': 'J13轮式平地机械', 'K11': 'K11大型普通客车', 'K12': 'K12大型双层客车', 'K13': 'K13大型卧铺客车', 'K14': 'K14大型铰接客车', 'K15': 'K15大型越野客车', 'K21': 'K21中型普通客车',
       'K22': 'K22中型双层客车', 'K23': 'K23中型卧铺客车', 'K24': 'K24中型铰接客车', 'K25': 'K25中型越野客车', 'K31': 'K31小型普通客车', 'K32': 'K32小型越野客车', 'K33': 'K33轿车', 'K41': 'K41微型普通客车',
       'K42': 'K42微型越野客车', 'K43': 'K43微型轿车', 'M11': 'M11普通正三轮摩托车', 'M12': 'M12轻便正三轮摩托车', 'M13': 'M13正三轮载客摩托车', 'M14': 'M14正三轮载货摩托车', 'M15': 'M15侧三轮摩托车',
       'M21': 'M21普通二轮摩托车', 'M22': 'M22轻便二轮摩托车', 'N11': 'N11三轮汽车', 'Q11': 'Q11重型半挂牵引车', 'Q21': 'Q21中型半挂牵引车', 'Q31': 'Q31轻型半挂牵引车', 'S特种': 'S特种作业专用车',
       'T11': 'T11大型轮式拖拉机', 'T21': 'T21小型轮式拖拉机', 'T22': 'T22手扶拖拉机', 'T23': 'T23手扶变形运输机', 'X99': 'X99其它', 'Z11': 'Z11大型专项作业车', 'Z21': 'Z21中型专项作业车', 'Z31': 'Z31小型专项作业车',
       'Z41': 'Z41微型专项作业车', 'Z51': 'Z51重型专项作业车', 'Z71': 'Z71轻型专项作业车', 'B11': 'B11重型普通半挂车', 'B12': 'B12重型厢式半挂车', 'B13': 'B13重型罐式半挂车', 'B14': 'B14重型平板半挂车',
       'B15': 'B15重型集装箱半挂车', 'B16': 'B16重型自卸半挂车', 'B17': 'B17重型特殊结构半挂车', 'B21': 'B21中型普通半挂车', 'B22': 'B22中型厢式半挂车', 'B23': 'B23中型罐式半挂车', 'B24': 'B24中型平板半挂车',
       'B25': 'B25中型集装箱半挂车', 'B26': 'B26中型自卸半挂车', 'B27': 'B27中型特殊结构半挂车', 'B31': 'B31轻型普通半挂车', 'B32': 'B32轻型厢式半挂车', 'B33': 'B33轻型罐式半挂车', 'B34': 'B34轻型平板半挂车',
       'B35': 'B35轻型自卸半挂车', 'D11': 'D11无轨电车', 'D12': 'D12有轨电车', 'G11': 'G11重型普通全挂车', 'G12': 'G12重型厢式全挂车', 'G13': 'G13重型罐式全挂车', 'G14': 'G14重型平板全挂车', 'G15': 'G15重型集装箱全挂车',
       'G16': 'G16重型自卸全挂车', 'G21': 'G21中型普通全挂车', 'G22': 'G22中型厢式全挂车', 'G23': 'G23中型罐式全挂车', 'G24': 'G24中型平板全挂车', 'G25': 'G25中型集装箱全挂车', 'G26': 'G26中型自卸全挂车',
       'G31': 'G31轻型普通全挂车', 'G32': 'G32轻型厢式全挂车', 'G33': 'G33轻型罐式全挂车', 'G34': 'G34轻型平板全挂车', 'G35': 'G35轻型自卸全挂车', 'H11': 'H11重型普通货车', 'H12': 'H12重型厢式货车',
       'H13': 'H13重型封闭货车', 'H14': 'H14重型罐式货车', 'H15': 'H15重型平板货车', 'H16': 'H16重型集装厢车', 'H17': 'H17重型自卸货车', 'H18': 'H18重型特殊结构货车', 'H21': 'H21中型普通货车',
       'H22': 'H22中型厢式货车', 'H23': 'H23中型封闭货车', 'H24': 'H24中型罐式货车', 'H25': 'H25中型平板货车', 'H26': 'H26中型集装厢车', 'H27': 'H27中型自卸货车', 'H28': 'H28中型特殊结构货车',
       'H31': 'H31轻型普通货车', 'H32': 'H32轻型厢式货车', 'H33': 'H33轻型封闭货车', 'H34': 'H34轻型罐式货车', 'H35': 'H35轻型平板货车', 'H37': 'H37轻型自卸货车', 'H38': 'H38轻型特殊结构货车',
       'H41': 'H41微型普通货车', 'H42': 'H42微型厢式货车', 'H43': 'H43微型封闭货车', 'H44': 'H44微型罐式货车', 'H45': 'H45微型自卸货车', 'H46': 'H46微型特殊结构货车', 'H51': 'H51低速普通货车',
       'H52': 'H52低速厢式货车', 'H53': 'H53低速罐式货车', 'H54': 'H54低速自卸货车', 'J11': 'J11轮式装载机械', 'J12': 'J12轮式挖掘机械'}

# 使用性质
NATURE_OF_USE = {'A0': '家庭自用客车', 'A1': '非营业企业客车', 'A2': '非营业机关客车', 'A3': '非营业个人货车', 'A4': '非营业企业货车', 'A5': '非营业机关货车', 'A6': '营业个人.出租.租赁', 'A7': '营业个人.城市公交',
                 'A8': '营业个人.公路客运', 'A9': '营业个人.货车', 'A10': '营业企业.出租.租赁', 'A11': '营业企业.城市公交', 'A12': '营业企业.公路客运', 'A13': '营业企业.货车', 'A14': '营业特种车',
                 'A15': '非营业特种车', 'A16': '营业特种车挂车', 'A17': '非营业特种车挂车', 'A18': '营业挂车', 'A19': '非营业挂车'}
