"""A rent amount stated the way Palestinian/Jordanian leases state it: digits,
the number in words, then the currency — "450 (أربعمائة وخمسون) ديناراً
أردنياً". The words are what stop a dot read as a thousands separator
("450.000") or a digit added later from changing the amount agreed.

Computed here, never left to the model. num2words (0.5.14, lang="ar") was
tried first and is wrong for this: it detaches the و joiner ("و خمسون"),
leaves a bare 200/2000 in the construct form ("مئتا", "ألفا"), writes
"أحد عشر ألف" without its tamyiz case, and ignores the currency code — every
amount comes out in ريال/هللة, and 0.500 JOD as fifty of them.

Forms are the standard rules of العدد والمعدود (number-noun agreement):
3-10 take the opposite gender of the noun and a genitive plural (ثلاثة دنانير،
ثلاث أغورات), 11-99 an accusative singular (أحد عشر ديناراً، إحدى عشرة أغورة),
hundreds/thousands/millions a genitive singular (مائة دينار), and 1 and 2 are
said by the noun itself (دينار واحد، ديناران). The words are the standalone
citation form, so a bare 200/2000 is مائتان/ألفان inside the parentheses.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class _Noun:
    one: str  # 1: the noun, then واحد
    dual: str  # 2: the dual alone
    plural: str  # after 3-10
    accusative: str  # after 11-99
    singular: str  # after 100, 1000, ...
    feminine: bool = False

    def after(self, n: int) -> str:
        last_two = n % 100
        if 3 <= last_two <= 10:
            return self.plural
        if last_two >= 11:
            return self.accusative
        # ponytail: x01/x02 (101, 1002) also land here — "مائة وواحد دينار",
        # the form cheques use. The classical "مائة دينار ودينار" isn't built;
        # both are unambiguous, so build it only if a reviewer asks.
        return self.singular


@dataclass(frozen=True)
class _Currency:
    major: _Noun
    minor: _Noun
    decimals: int


_FILS = _Noun("فلس واحد", "فلسان", "فلوس", "فلساً", "فلس")
_CENT = _Noun("سنت واحد", "سنتان", "سنتات", "سنتاً", "سنت")

# ponytail: JOD, ILS, USD, EUR only. Any other code keeps its raw
# price/currency in the prompt; add a row here to cover it.
CURRENCIES = {
    "JOD": _Currency(
        _Noun("دينار أردني واحد", "ديناران أردنيان", "دنانير أردنية", "ديناراً أردنياً", "دينار أردني"),
        _FILS, 3,
    ),
    "ILS": _Currency(
        _Noun("شيكل جديد واحد", "شيكلان جديدان", "شواكل جديدة", "شيكلاً جديداً", "شيكل جديد"),
        _Noun("أغورة واحدة", "أغورتان", "أغورات", "أغورة", "أغورة", feminine=True), 2,
    ),
    "USD": _Currency(
        _Noun("دولار أمريكي واحد", "دولاران أمريكيان", "دولارات أمريكية", "دولاراً أمريكياً", "دولار أمريكي"),
        _CENT, 2,
    ),
    # يورو is indeclinable: one form after every number but 1 and 2.
    "EUR": _Currency(_Noun("يورو واحد", "يوروان", "يورو", "يورو", "يورو"), _CENT, 2),
}

PERIODS = {
    "per_month": "شهرياً",
    "per_year": "سنوياً",
    "per_week": "أسبوعياً",
    "per_day": "يومياً",
    "per_hour": "عن كل ساعة",
}

_ONES_M = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة", "عشرة"]
_ONES_F = ["", "واحدة", "اثنتان", "ثلاث", "أربع", "خمس", "ست", "سبع", "ثماني", "تسع", "عشر"]
_TENS = ["", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
_HUNDREDS = ["", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]

# Scale nouns count like any masculine noun. ponytail: tops out below a
# trillion; a bigger amount keeps its raw price in the prompt.
_SCALES = [
    (10**9, _Noun("مليار", "ملياران", "مليارات", "ملياراً", "مليار")),
    (10**6, _Noun("مليون", "مليونان", "ملايين", "مليوناً", "مليون")),
    (10**3, _Noun("ألف", "ألفان", "آلاف", "ألفاً", "ألف")),
]


def _below_100(n: int, feminine: bool) -> str:
    ones = _ONES_F if feminine else _ONES_M
    tens, unit = divmod(n, 10)
    if n <= 10:
        return ones[n]
    if n == 11:
        return "إحدى عشرة" if feminine else "أحد عشر"
    if n == 12:
        return "اثنتا عشرة" if feminine else "اثنا عشر"
    if n < 20:
        return f"{ones[unit]} {'عشرة' if feminine else 'عشر'}"
    if not unit:
        return _TENS[tens]
    first = {1: "إحدى" if feminine else "واحد", 8: "ثمانٍ" if feminine else "ثمانية"}.get(unit, ones[unit])
    return f"{first} و{_TENS[tens]}"


def _below_1000(n: int, feminine: bool) -> str:
    hundreds, rest = divmod(n, 100)
    parts = [_HUNDREDS[hundreds]] if hundreds else []
    if rest:
        parts.append(_below_100(rest, feminine))
    return " و".join(parts)


def _words(n: int, feminine: bool) -> str:
    """0 < n < 10**12 in words, nominative."""
    parts = []
    for value, scale in _SCALES:
        count, n = divmod(n, value)
        if count == 1:
            parts.append(scale.singular)
        elif count == 2:
            parts.append(scale.dual)
        elif count:
            # 200 directly before its scale noun is construct: مائتا ألف.
            number = "مائتا" if count == 200 else _below_1000(count, feminine=False)
            parts.append(f"{number} {scale.after(count)}")
    if n:
        parts.append(_below_1000(n, feminine))
    return " و".join(parts)


def _stated(n: int, noun: _Noun) -> str:
    if n == 1:
        return f"1 ({noun.one})"
    if n == 2:
        return f"2 ({noun.dual})"
    return f"{n} ({_words(n, noun.feminine)}) {noun.after(n)}"


def amount_ar(price, currency) -> str | None:
    """Digits (words) currency, e.g. ("450.500", "JOD") ->
    "450 (أربعمائة وخمسون) ديناراً أردنياً و500 (خمسمائة) فلس" — no decimal
    point left to misread. None when the amount can't be stated exactly:
    unknown currency, not a positive number, more decimals than the currency
    has, or too large."""
    spec = CURRENCIES.get(currency)
    if spec is None:
        return None
    try:
        amount = Decimal(str(price))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    in_minor = amount.scaleb(spec.decimals)
    if in_minor != in_minor.to_integral_value():
        return None
    major, minor = divmod(int(in_minor), 10**spec.decimals)
    if major >= 10**12:
        return None
    parts = [_stated(major, spec.major)] if major else []
    if minor:
        parts.append(_stated(minor, spec.minor))
    return " و".join(parts)
