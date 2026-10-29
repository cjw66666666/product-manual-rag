from rag_app.answering.models import RiskLevel

_SAFETY_TERMS = (
    "冒烟",
    "起火",
    "着火",
    "漏液",
    "进水",
    "触电",
    "电源线损坏",
    "损坏电源线",
    "异常发热",
    "发热异常",
    "拆机",
    "维修",
    "改装",
    "短接",
    "绕过保护",
    "电池鼓包",
    "电池膨胀",
    "异味",
    "异常声音",
    "爆炸",
)

_GENERAL_CONCEPT_TERMS = (
    "什么是",
    "是什么意思",
    "有何区别",
    "有何差异",
    "有什么区别",
    "有什么差异",
    "的区别是什么",
    "的差异是什么",
    "主要差异",
    "分别代表什么",
    "分别表示什么",
    "定义是什么",
    "含义是什么",
)

_SPECIFIC_STEP_TERMS = (
    "如何连接",
    "如何设置",
    "如何操作",
    "怎么连接",
    "怎么设置",
    "怎么操作",
    "操作步骤",
)


def classify_risk(question: str) -> RiskLevel:
    normalized = question.casefold()
    if any(term in normalized for term in _SAFETY_TERMS):
        return RiskLevel.SAFETY_CRITICAL
    return RiskLevel.NORMAL


def is_general_concept_question(question: str) -> bool:
    normalized = question.casefold()
    if classify_risk(normalized) is not RiskLevel.NORMAL:
        return False
    if any(term in normalized for term in _SPECIFIC_STEP_TERMS):
        return False
    return any(term in normalized for term in _GENERAL_CONCEPT_TERMS)
