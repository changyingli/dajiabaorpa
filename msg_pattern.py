# coding=utf8

from datetime import date, timedelta
from settings import PLANS

PLAN_OPTIONS = { k for v in PLANS.values() for k in v.keys() }

def filter_effect_date(context, matches: dict) -> dict:
    val = matches['生效']
    if val.startswith('周'):
        chi_week = '一二三四五六日'
        weekday = chi_week.find(val[1])
        today = date.today()
        days_ahead = weekday - today.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        effect_date = today + timedelta(days_ahead)
        matches['生效'] = effect_date.isoformat()
    return matches

def populate_plan_option(plan_name: str, options_str: str) -> dict:
    plan = PLANS[plan_name].copy()
    if not options_str:
        return {'plan': plan}

    customs = options_str.split()
    for custom_str in customs:
        option = None
        value = None
        if ':' in custom_str:
            rst = custom_str.split(':')
            option = rst[0].strip()
            value = rst[1].strip()
            if value.endswith('万'):
                value = value[:-1] + '0000'
        else:
            option = custom_str.strip()
            value = True
        if option.startswith('+'):
            option = option[1:]
        if option.startswith('-'):
            key = option[1:]
            if key in plan:
                del plan[key]
            else:
                return {'error': True, 'msg': '选项"{}"不在{}中。{}的选项是{}'.format(key, plan_type, plan_type, ','.join(plan.keys()))}
        else:
            if option in PLAN_OPTIONS:
                plan[option] = value
            else:
                return {'error': True, 'msg': '选项"{}"不是正确的选项。可用的选项是：{}。'.format(option, ','.join(PLAN_OPTIONS))}
    return {'plan': plan}

def filter_plan(context, matches: dict):
    result = {}
    plan_name = matches['险款'].lower()
    plan_maps = {'a款':'基本款','b款':'优质款','c款':'尊享款'}
    if plan_name == '基础款':
        plan_name = '基本款'
    elif plan_name in plan_maps:
        plan_name = plan_maps[plan_name]
    result['险款']=plan_name
    options_str = None
    if 'option' in matches:
        options_str = matches['option']
    rst = handle_plan_option(plan_name=plan_name, options_str=options_str)

re_plans = '|'.join(PLANS.keys())

patterns = [
    {'pattern': r"(?P<邮箱>[a-zA-Z0-9\._-]+@[a-zA-Z0-9\._-]+)",
     'required': False},
    {'pattern': r"(?P<手机>1[35678]\d{9})\b",
     'required': True, 'msg': '没有找到录单需要的手机号码。'},
    {
        'pattern': [
            r'生效:\s*(?P<生效>\d+-\d+-\d+)',
            r'生效:\s*(?P<生效>周[一二三四五六日])',
            r'生效:\s*(?P<生效>即时)'
        ],
        'filter': filter_effect_date,
        'required': True,
        'msg': '没有输入时间。请输入"生效：2020-01-01 或 生效：即时|周一|周二|...|周日"格式的时间。'
    },
    {'pattern':
        [
            r'(?P<险款>基础款|基本款|优质款|尊享款|[ABCabc]款)\s*\((?P<option>.*?)\)',
            r'(?P<险款>基础款|基本款|优质款|尊享款|[ABCabc]款)'
        ],
     'msg': '录单时请输入[基本款|优质款|尊享款]或者[a款|b款|c款]。', 'required': True},
    {'pattern': r'\((.*)\)', 'filter': filter_custom_plan},
    {'pattern': r'经办人:\s*(?P<经办人>\w+)',
     'msg': '请输入经办人。格式是"经办人：小明"', 'required': True},
    {'pattern': r'手机实名人:\s*(?P<手机实名人>\w+)'},
    {'pattern': r'手机实名身份证:\s*(?P<手机实名身份证号>[1-9]\d{5}(18|19|([23]\d))\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx])'},
    {'pattern': r'姓名:\s*(?P<姓名>\w+)'},
    {'pattern': r'身份证:\s*(?P<身份证号>[1-9]\d{5}(18|19|([23]\d))\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx])'}
]
