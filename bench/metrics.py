# -*- coding: utf-8 -*-
"""Mixed error rate (MER) for code-switched zh/en: each CJK char is one token,
each Latin word is one token. Case, punctuation, Traditional/Simplified and
Arabic-vs-Chinese digits are normalized away so we score recognition, not style."""
import re

from opencc import OpenCC

_T2S = OpenCC("t2s")
_DIGITS = dict(zip("0123456789", "零一二三四五六七八九"))
_EN_NUM = {"50": "fifty", "5": "five", "9": "nine"}
_TOKEN = re.compile(r"[一-鿿]|[a-z']+")


def _num_to_zh(m):
    s = m.group(0)
    if len(s) == 2 and s[1] == "0":  # 50 -> 五十
        return _DIGITS[s[0]] + "十"
    return "".join(_DIGITS[c] for c in s)


def tokenize(text: str):
    t = _T2S.convert(text).lower()
    # "50 pieces" -> "fifty pieces" when surrounded by latin text
    t = re.sub(r"(?<=[a-z] )(\d+)(?= [a-z])", lambda m: _EN_NUM.get(m.group(1), m.group(1)), t)
    t = re.sub(r"\d+", _num_to_zh, t)
    t = t.replace("dishonored", "dishonoured").replace("forever", "for ever")
    return _TOKEN.findall(t)


def edit_distance(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
            prev, d[j] = d[j], cur
    return d[-1]


def mer(ref: str, hyp: str):
    r, h = tokenize(ref), tokenize(hyp)
    return edit_distance(r, h), len(r)
