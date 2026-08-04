"""
تنضيف النصوص الراجعة من الموديل:
- إزالة العلامات المائية/نصوص الديمو (زي "Demonstration License") اللي مالهاش
  علاقة بمحتوى المستند الحقيقي.
- إزالة التشكيل اللي الموديل بيهلوسه على عبارات رسمية متكررة.
- توحيد المسافات وتنضيف قيم الحقول.
- التعامل مع سطور الخط الزخرفي المشكّل (ترويسة المراسيم).
- قص ذيل الـ prompt echo اللي بييجي كلمة في كل سطر.

الملف ده مقصود إنه يفضل "نقي": مفيش import للـ settings جواه، وكل قرار
(العتبة، الوضع، مفتوح/مقفول) بيتبعت كـ parameter من ocr_service. كده الدوال
دي تتختبر لوحدها من غير ما تلمس الكونفج.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_WATERMARK_PATTERNS = (
    r"demonstration\s*license",
    r"\bdemo\s*license\b",
    r"\bsample\s*document\b",
    r"\bevaluation\s*copy\b",
    # العلامة المائية المطبوعة على مسح النشرات الرسمية. بتظهر باهتة ورا النص
    # فالموديل بيقراها كأنها سطر توقيع في آخر الصفحة.
    #
    # النمط الأصلي كان بيطلب كلمة "for" وكلمة "records" بالظبط، فلو الموديل
    # قرا العلامة الباهتة ناقصة أو بصيغة مختلفة شوية ("Centre of Archives"،
    # "National Center Archives") مكانش بيمسكها - وده اللي حصل فعلًا.
    # النمط الجديد بيقف عند "archives" وسايب اللي بعدها اختياري.
    r"national\s*cent(?:er|re)\s*(?:for\s*|of\s*)?archives(?:\s*(?:&|and)\s*records)?",
    r"\bdarah\b",
)
_WATERMARK_RE = re.compile("|".join(_WATERMARK_PATTERNS), re.IGNORECASE)

# التشكيل (الحركات: فتحة/ضمة/كسرة/شدة/سكون...) نادرًا ما يكون موجود فعليًا في
# المستندات الرسمية، فشيله افتراضيًا أأمن من احتمال هلوسة الموديل له.
_TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")

def strip_watermarks(text: str) -> str:
    return _WATERMARK_RE.sub("", text)


def strip_tashkeel(text: str) -> str:
    return _TASHKEEL_RE.sub("", text)


# حرف لاتيني منفرد أو كلمة من حرفين لاتينيين معزولة داخل نص عربي.
# "معزولة" = لا يسبقها ولا يليها حرف لاتيني أو رقم.
# بيشيل: "e"، "a"، "al" وما شابه حين تظهر كأثر جانبي للموديل.
# بيسيب: تواريخ (15/01/2024)، اختصارات (VAT، CEO)، كلمات إنجليزية حقيقية.
_STRAY_LATIN_RE = re.compile(
    r"(?<![A-Za-z\d])"  # لا يسبقها حرف/رقم
    r"[A-Za-z]{1,2}"    # حرف أو حرفان لاتينيان فقط
    r"(?![A-Za-z\d])",  # لا يليها حرف/رقم
)

_ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF]")
_LATIN_CHAR_RE  = re.compile(r"[A-Za-z]")


def strip_stray_latin_in_arabic_value(value: str) -> str:
    """
    يشيل الحروف اللاتينية المنفردة (1-2 حرف) التي يضيفها الموديل بالغلط
    في قيم الحقول العربية.

    الشرط: النص لازم يكون في معظمه عربي (أكتر من 70% حروف عربية من إجمالي
    الحروف العربية + اللاتينية)، عشان ما نيجيش على فواتير أو حقول إنجليزية/
    مختلطة حقيقية.

    بيشيل: حرف واحد أو اتنين عائم في النص (e, a, al, وما شابه).
    بيسيب: أرقام، تواريخ، كلمات إنجليزية بثلاثة أحرف أو أكثر (VAT/CEO/etc.).
    """
    arabic_count = len(_ARABIC_CHAR_RE.findall(value))
    latin_count  = len(_LATIN_CHAR_RE.findall(value))

    if arabic_count == 0 or latin_count == 0:
        return value  # نص نقي (عربي أو إنجليزي) → لا تعديل

    # لو النص مخلوط بالتساوي → محتوى حقيقي (فاتورة ثنائية اللغة مثلًا)
    if arabic_count / (arabic_count + latin_count) < 0.70:
        return value

    cleaned = _STRAY_LATIN_RE.sub("", value)
    if cleaned != value:
        logger.info(
            "تمت إزالة حروف لاتينية منفردة من قيمة حقل عربي: %r → %r",
            value[:80], cleaned[:80],
        )
    return re.sub(r"\s+", " ", cleaned).strip()


def clean_field_value(value: Any) -> Any:
    """
    تنضيف قيمة حقل واحد بعد استلامها من الموديل:
    1. إزالة العلامات المائية والتشكيل المهلوس.
    2. إزالة الحروف اللاتينية المنفردة المتسربة في قيم الحقول العربية.
    3. توحيد المسافات/الأسطر الفاضية (trim + collapse).
    وتطبيق نفس المنطق تكراريًا على القوائم والقواميس.
    """
    if isinstance(value, str):
        cleaned = strip_tashkeel(strip_watermarks(value))
        cleaned = strip_stray_latin_in_arabic_value(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None
    if isinstance(value, list):
        cleaned_list = [clean_field_value(v) for v in value]
        return [v for v in cleaned_list if v not in (None, "")]
    if isinstance(value, dict):
        return {k: clean_field_value(v) for k, v in value.items()}
    return value


def clean_extracted_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {k: clean_field_value(v) for k, v in data.items()}


def parse_json_response(text: str) -> dict[str, Any]:
    """يحاول يفك الـ JSON من رد الموديل، مع fallback لاستخراج أول object صالح لو الرد فيه نص زيادة حواليه."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"خطأ": "لم يستطع تحليل رد الموديل", "النص_الخام": text}


# جمل من البرومبت نفسه. لما القصاصة تبقى شبه فاضية (شريط تذييل فيه خط زخرفي
# بس مثلًا) الموديل مبيلاقيش حاجة يترجمها فبيرجّع البرومبت نفسه. الجمل دي
# مستحيل تكون موجودة في مستند حقيقي، فوجودها = رد مش من الصورة.
_PROMPT_ECHO_MARKERS = (
    "You are a verbatim OCR",
    "You are an expert OCR",
    "SCRIPT AND FIDELITY",
    "THIS IMAGE ONLY",
    "READING ORDER",
    "NO LOOPING",
    "NO INVENTED CONTENT",
    "Output ONLY the transcription",
    "Never translate and never transliterate",
    "Transcribe ALL text visible",
    # الموديل ساعات بيترجم عناوين البرومبت للعربي بدل ما ينقلها بالإنجليزي.
    # الجمل دي مستحيل تكون محتوى مستند حقيقي.
    "الأخطاء الثلاثة",
    "الثلاثة الخطأ",
    "ترتيب القراءة",
    "الأخطاء التي يجب",
)


def strip_prompt_echo(text: str) -> str:
    """يقص أي جزء من الرد الموديل رجّع فيه البرومبت بتاعنا بدل نص الصورة."""
    earliest = min(
        (text.find(marker) for marker in _PROMPT_ECHO_MARKERS if marker in text),
        default=-1,
    )
    if earliest < 0:
        return text
    logger.warning(
        "الموديل رجّع البرومبت بدل نص الصورة (قصاصة شبه فاضية غالبًا) - اتقص %d حرف.",
        len(text) - earliest,
    )
    return text[:earliest].strip()


# ─────────────────────────────────────────────────────────────────────────────
# ذيل الـ echo: كلمة واحدة في كل سطر
# ─────────────────────────────────────────────────────────────────────────────
# المطاردة بالجمل الحرفية في _PROMPT_ECHO_MARKERS معركة خسرانة: الموديل ساعات
# بيترجم البرومبت للعربي وبيفكّه كلمة كلمة على سطور، فالمقارنة الحرفية
# مبتشوفهوش. المثال اللي ظهر فعلًا في آخر فاتورة:
#
#     الثلاثة
#     الخطأ
#     الذي
#     لا
#     تقم
#     به
#
# الـ signature هنا هو الشكل مش الكلمات، فالفحص على الشكل بيمسك أي صياغة.

# سطر كله أرقام/ترقيم/فواصل جدول = محتوى حقيقي (عمود أرقام في فاتورة)، مش echo.
_NUMERIC_LINE_RE = re.compile(r"^[\d\u0660-\u0669.,/\\|:;()\[\]\-–—\s٫٬]+$")


def strip_single_word_tail(text: str, min_run: int = 4) -> str:
    """
    يقص ذيل النص لو آخره سلسلة سطور كل واحد فيها كلمة واحدة.

    مفيش مستند حقيقي بيقفل بـ 4 سطور ورا بعض كل واحد كلمة واحدة، لكن الـ
    prompt echo المفكوك بيعمل كده بالظبط.

    الفحص من آخر النص لفوق عن قصد، مش من أوله: هيدر الجدول في الفاتورة
    (Description / Unit / Quantity / Unit Price / Total) هو كمان 5 سطور
    بكلمة واحدة، بس مكانه في نص النص مش في آخره. المسح من الآخر بيسيبه.

    والسطر اللي كله أرقام بيقطع العد (مش بيتحسب echo): عمود الأرقام في آخر
    قصاصة جدول محتوى حقيقي.
    """
    lines = text.split("\n")
    cut = len(lines)
    single_words = 0

    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].strip()
        if not stripped:
            continue  # سطر فاضي: لا بيقطع الذيل ولا بيتحسب فيه
        if _NUMERIC_LINE_RE.match(stripped):
            break  # عمود أرقام = محتوى حقيقي، نوقف هنا
        if len(stripped.split()) != 1:
            break  # أول سطر فيه كلمتين أو أكتر = نهاية الذيل
        single_words += 1
        cut = index

    if single_words < min_run:
        return text

    logger.warning(
        "اتقص ذيل %d سطر بكلمة واحدة (prompt echo مفكوك غالبًا): %s",
        single_words,
        [line.strip() for line in lines[cut:] if line.strip()],
    )
    return "\n".join(lines[:cut]).strip()


# حرف واحد متكرر أكتر من كده ورا بعضه = لوب من الموديل. الحد عالي عن قصد عشان
# الاستخدامات الحقيقية (نقط الحشو في الفهارس، التطويل في العناوين) متتأثرش.
_DEGENERATE_RUN_RE = re.compile(r"(\S)\1{15,}")


def collapse_degenerate_runs(text: str) -> str:
    """
    يقصّر أي حرف متكرر عشرات المرات ورا بعضه (زي "...................").

    ده بيحصل لما الموديل يوصل لجزء مش قادر يقراه فيدخل في لوب على حرف واحد،
    وبياكل باقي الـtokens فالصفحة بتطلع مبتورة. القص هنا بيشيل حاجة الموديل
    اخترعها، مش محتوى من الصورة.
    """

    def shorten(match: re.Match[str]) -> str:
        logger.warning(
            "اتقص تكرار الحرف '%s' (%d مرة ورا بعض) - لوب من الموديل.",
            match.group(1), len(match.group()),
        )
        return match.group(1) * 3

    return _DEGENERATE_RUN_RE.sub(shorten, text)


def trim_runaway_repetition(text: str, max_repeats: int = 3) -> str:
    """
    يقص اللوب اللي بيقع فيه الموديل على الصفحات اللي فيها سطور شبه متطابقة.

    في المستندات النظامية بيتكرر نفس السطر بصيغته ("وبعد الاطلاع على...") عدة
    مرات، والموديل ساعات بيفضل يعيد إنتاج نفس السطر بالحرف عشرات المرات لحد ما
    يخلص السقف. السطر المتكرر حرفيًا أكتر من max_repeats مرة ورا بعض مش محتوى
    حقيقي من الصفحة - بيتقص وبيتسجل تحذير.

    الشرط "حرفيًا ومتتالي" مقصود: السطور المتكررة الحقيقية في المستندات دي
    بتختلف في الرقم والتاريخ، فمبتتأثرش.
    """
    lines = text.split("\n")
    result: list[str] = []
    trimmed = 0
    for line in lines:
        stripped = line.strip()
        if stripped and len(result) >= max_repeats:
            if all(previous.strip() == stripped for previous in result[-max_repeats:]):
                trimmed += 1
                continue
        result.append(line)

    if trimmed:
        logger.warning(
            "اتقص %d سطر مكرر حرفيًا (لوب من الموديل، مش محتوى من الصفحة).", trimmed
        )
    return "\n".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# الخط الزخرفي المشكّل (ترويسة المراسيم)
# ─────────────────────────────────────────────────────────────────────────────
# ترويسة المرسوم فيها "بسم الله الرحمن الرحيم" بخط الثلث مشكّل بالكامل،
# والطغراء، والنص الدائري حوالين الشعار. نسبة الحركات للحروف في السطور دي
# بتوصل ~0.6، بينما متن المستند نفسه نسبته صفر تقريبًا.
#
# نفس الفلتر بيمسك حاجة تانية مجانًا: التشكيل اللي الموديل بيهلوسه على
# العبارات الرسمية المعروفة. المصدرين مختلفين بس العلاج واحد.

# حروف بس، من غير الحركات ومن غير التطويل (\u0640). استبعاد التطويل مهم:
# الخط الزخرفي بيستخدمه بكتافة، ولو اتحسب حرف كان هيقلل النسبة ويخفي الزخرفة.
_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u063F\u0641-\u064A\u0671-\u06D3]")

# فوق النسبة دي = خط مشكّل عمدًا، مش حركة أو اتنين عابرة
_CALLIGRAPHY_RATIO = 0.15
# السطر القصير جدًا نسبته مضللة (كلمة من حرفين عليها حركة = 0.5)
_CALLIGRAPHY_MIN_LETTERS = 4


def calligraphy_ratio(line: str) -> float:
    """نسبة الحركات للحروف في السطر. بترجّع 0.0 لو السطر أقصر من الحد الأدنى."""
    letters = len(_ARABIC_LETTER_RE.findall(line))
    if letters < _CALLIGRAPHY_MIN_LETTERS:
        return 0.0
    return len(_TASHKEEL_RE.findall(line)) / letters


def clean_calligraphy_lines(
    text: str,
    mode: str = "strip",
    max_ratio: float = _CALLIGRAPHY_RATIO,
) -> str:
    """
    يعالج السطور اللي نسبة تشكيلها عالية.

    mode="strip"  (الافتراضي، الأأمن): بيشيل الحركات من السطر وبيسيب الكلمات.
                  "بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيْمِ" مطبوعة فعلًا في المستند، فحذفها
                  بيخلي النص المستخرج مش نسخة حرفية 100% وبيكسر البحث عنها
                  في Laserfiche. شيل التشكيل بس بيحل مشكلة عدم الاتساق
                  (نفس العبارة مرة مشكّلة ومرة لأ) من غير ما يضيّع محتوى.
    mode="drop"   بيشيل السطر بالكامل. استخدمه بس لو مش عايز الترويسة الزخرفية
                  في النص أصلًا.
    mode="off"    بيرجّع النص زي ما هو.

    ملحوظة: ده مختلف عن strip_tashkeel اللي بيشيل التشكيل من النص كله. هنا
    السطور العادية مبتتلمسش خالص - لو التشكيل مطبوع فعلًا في سطر من المتن
    بيفضل زي ما هو.
    """
    if mode == "off":
        return text

    kept: list[str] = []
    touched: list[str] = []

    for line in text.split("\n"):
        if calligraphy_ratio(line) <= max_ratio:
            kept.append(line)
            continue

        touched.append(line.strip())
        if mode == "strip":
            # collapse للمسافات كمان: شيل الحركة من خط الثلث بيسيب فراغات مضاعفة
            kept.append(re.sub(r"[ \t]{2,}", " ", strip_tashkeel(line)))
        # mode == "drop" → السطر مبيتضافش خالص

    if touched:
        logger.warning(
            "%d سطر نسبة تشكيله عالية (خط زخرفي/تشكيل مهلوس) - %s: %s",
            len(touched),
            "اتشال التشكيل منه" if mode == "strip" else "السطر اتحذف",
            touched,
        )
    return "\n".join(kept)




# """
# تنضيف النصوص الراجعة من الموديل:
# - إزالة العلامات المائية/نصوص الديمو (زي "Demonstration License") اللي مالهاش
#   علاقة بمحتوى المستند الحقيقي.
# - إزالة التشكيل اللي الموديل بيهلوسه على عبارات رسمية متكررة.
# - توحيد المسافات وتنضيف قيم الحقول.
# - التعامل مع سطور الخط الزخرفي المشكّل (ترويسة المراسيم).
# - قص ذيل الـ prompt echo اللي بييجي كلمة في كل سطر.

# الملف ده مقصود إنه يفضل "نقي": مفيش import للـ settings جواه، وكل قرار
# (العتبة، الوضع، مفتوح/مقفول) بيتبعت كـ parameter من ocr_service. كده الدوال
# دي تتختبر لوحدها من غير ما تلمس الكونفج.
# """

# from __future__ import annotations

# import json
# import logging
# import re
# from typing import Any

# logger = logging.getLogger(__name__)

# _WATERMARK_PATTERNS = (
#     r"demonstration\s*license",
#     r"\bdemo\s*license\b",
#     r"\bsample\s*document\b",
#     r"\bevaluation\s*copy\b",
#     # العلامة المائية المطبوعة على مسح النشرات الرسمية. بتظهر باهتة ورا النص
#     # فالموديل بيقراها كأنها سطر توقيع في آخر الصفحة.
#     #
#     # النمط الأصلي كان بيطلب كلمة "for" وكلمة "records" بالظبط، فلو الموديل
#     # قرا العلامة الباهتة ناقصة أو بصيغة مختلفة شوية ("Centre of Archives"،
#     # "National Center Archives") مكانش بيمسكها - وده اللي حصل فعلًا.
#     # النمط الجديد بيقف عند "archives" وسايب اللي بعدها اختياري.
#     r"national\s*cent(?:er|re)\s*(?:for\s*|of\s*)?archives(?:\s*(?:&|and)\s*records)?",
#     r"\bdarah\b",
# )
# _WATERMARK_RE = re.compile("|".join(_WATERMARK_PATTERNS), re.IGNORECASE)

# # التشكيل (الحركات: فتحة/ضمة/كسرة/شدة/سكون...) نادرًا ما يكون موجود فعليًا في
# # المستندات الرسمية، فشيله افتراضيًا أأمن من احتمال هلوسة الموديل له.
# _TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")

# def strip_watermarks(text: str) -> str:
#     return _WATERMARK_RE.sub("", text)


# def strip_tashkeel(text: str) -> str:
#     return _TASHKEEL_RE.sub("", text)


# def clean_field_value(value: Any) -> Any:
#     """
#     تنضيف قيمة حقل واحد بعد استلامها من الموديل: إزالة العلامات المائية
#     والتشكيل، توحيد المسافات/الأسطر الفاضية (trim + collapse)، وتطبيق نفس
#     المنطق تكراريًا على القوائم والقواميس.
#     """
#     if isinstance(value, str):
#         cleaned = strip_tashkeel(strip_watermarks(value))
#         cleaned = re.sub(r"\s+", " ", cleaned).strip()
#         return cleaned or None
#     if isinstance(value, list):
#         cleaned_list = [clean_field_value(v) for v in value]
#         return [v for v in cleaned_list if v not in (None, "")]
#     if isinstance(value, dict):
#         return {k: clean_field_value(v) for k, v in value.items()}
#     return value


# def clean_extracted_fields(data: dict[str, Any]) -> dict[str, Any]:
#     return {k: clean_field_value(v) for k, v in data.items()}


# def parse_json_response(text: str) -> dict[str, Any]:
#     """يحاول يفك الـ JSON من رد الموديل، مع fallback لاستخراج أول object صالح لو الرد فيه نص زيادة حواليه."""
#     text = text.strip()
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         pass

#     match = re.search(r"\{.*\}", text, re.DOTALL)
#     if match:
#         try:
#             return json.loads(match.group())
#         except json.JSONDecodeError:
#             pass

#     return {"خطأ": "لم يستطع تحليل رد الموديل", "النص_الخام": text}


# # جمل من البرومبت نفسه. لما القصاصة تبقى شبه فاضية (شريط تذييل فيه خط زخرفي
# # بس مثلًا) الموديل مبيلاقيش حاجة يترجمها فبيرجّع البرومبت نفسه. الجمل دي
# # مستحيل تكون موجودة في مستند حقيقي، فوجودها = رد مش من الصورة.
# _PROMPT_ECHO_MARKERS = (
#     "You are a verbatim OCR",
#     "You are an expert OCR",
#     "SCRIPT AND FIDELITY",
#     "THIS IMAGE ONLY",
#     "READING ORDER",
#     "NO LOOPING",
#     "NO INVENTED CONTENT",
#     "Output ONLY the transcription",
#     "Never translate and never transliterate",
#     "Transcribe ALL text visible",
#     # الموديل ساعات بيترجم عناوين البرومبت للعربي بدل ما ينقلها بالإنجليزي.
#     # الجمل دي مستحيل تكون محتوى مستند حقيقي.
#     "الأخطاء الثلاثة",
#     "الثلاثة الخطأ",
#     "ترتيب القراءة",
#     "الأخطاء التي يجب",
# )


# def strip_prompt_echo(text: str) -> str:
#     """يقص أي جزء من الرد الموديل رجّع فيه البرومبت بتاعنا بدل نص الصورة."""
#     earliest = min(
#         (text.find(marker) for marker in _PROMPT_ECHO_MARKERS if marker in text),
#         default=-1,
#     )
#     if earliest < 0:
#         return text
#     logger.warning(
#         "الموديل رجّع البرومبت بدل نص الصورة (قصاصة شبه فاضية غالبًا) - اتقص %d حرف.",
#         len(text) - earliest,
#     )
#     return text[:earliest].strip()


# # ─────────────────────────────────────────────────────────────────────────────
# # ذيل الـ echo: كلمة واحدة في كل سطر
# # ─────────────────────────────────────────────────────────────────────────────
# # المطاردة بالجمل الحرفية في _PROMPT_ECHO_MARKERS معركة خسرانة: الموديل ساعات
# # بيترجم البرومبت للعربي وبيفكّه كلمة كلمة على سطور، فالمقارنة الحرفية
# # مبتشوفهوش. المثال اللي ظهر فعلًا في آخر فاتورة:
# #
# #     الثلاثة
# #     الخطأ
# #     الذي
# #     لا
# #     تقم
# #     به
# #
# # الـ signature هنا هو الشكل مش الكلمات، فالفحص على الشكل بيمسك أي صياغة.

# # سطر كله أرقام/ترقيم/فواصل جدول = محتوى حقيقي (عمود أرقام في فاتورة)، مش echo.
# _NUMERIC_LINE_RE = re.compile(r"^[\d\u0660-\u0669.,/\\|:;()\[\]\-–—\s٫٬]+$")


# def strip_single_word_tail(text: str, min_run: int = 4) -> str:
#     """
#     يقص ذيل النص لو آخره سلسلة سطور كل واحد فيها كلمة واحدة.

#     مفيش مستند حقيقي بيقفل بـ 4 سطور ورا بعض كل واحد كلمة واحدة، لكن الـ
#     prompt echo المفكوك بيعمل كده بالظبط.

#     الفحص من آخر النص لفوق عن قصد، مش من أوله: هيدر الجدول في الفاتورة
#     (Description / Unit / Quantity / Unit Price / Total) هو كمان 5 سطور
#     بكلمة واحدة، بس مكانه في نص النص مش في آخره. المسح من الآخر بيسيبه.

#     والسطر اللي كله أرقام بيقطع العد (مش بيتحسب echo): عمود الأرقام في آخر
#     قصاصة جدول محتوى حقيقي.
#     """
#     lines = text.split("\n")
#     cut = len(lines)
#     single_words = 0

#     for index in range(len(lines) - 1, -1, -1):
#         stripped = lines[index].strip()
#         if not stripped:
#             continue  # سطر فاضي: لا بيقطع الذيل ولا بيتحسب فيه
#         if _NUMERIC_LINE_RE.match(stripped):
#             break  # عمود أرقام = محتوى حقيقي، نوقف هنا
#         if len(stripped.split()) != 1:
#             break  # أول سطر فيه كلمتين أو أكتر = نهاية الذيل
#         single_words += 1
#         cut = index

#     if single_words < min_run:
#         return text

#     logger.warning(
#         "اتقص ذيل %d سطر بكلمة واحدة (prompt echo مفكوك غالبًا): %s",
#         single_words,
#         [line.strip() for line in lines[cut:] if line.strip()],
#     )
#     return "\n".join(lines[:cut]).strip()


# # حرف واحد متكرر أكتر من كده ورا بعضه = لوب من الموديل. الحد عالي عن قصد عشان
# # الاستخدامات الحقيقية (نقط الحشو في الفهارس، التطويل في العناوين) متتأثرش.
# _DEGENERATE_RUN_RE = re.compile(r"(\S)\1{15,}")


# def collapse_degenerate_runs(text: str) -> str:
#     """
#     يقصّر أي حرف متكرر عشرات المرات ورا بعضه (زي "...................").

#     ده بيحصل لما الموديل يوصل لجزء مش قادر يقراه فيدخل في لوب على حرف واحد،
#     وبياكل باقي الـtokens فالصفحة بتطلع مبتورة. القص هنا بيشيل حاجة الموديل
#     اخترعها، مش محتوى من الصورة.
#     """

#     def shorten(match: re.Match[str]) -> str:
#         logger.warning(
#             "اتقص تكرار الحرف '%s' (%d مرة ورا بعض) - لوب من الموديل.",
#             match.group(1), len(match.group()),
#         )
#         return match.group(1) * 3

#     return _DEGENERATE_RUN_RE.sub(shorten, text)


# def trim_runaway_repetition(text: str, max_repeats: int = 3) -> str:
#     """
#     يقص اللوب اللي بيقع فيه الموديل على الصفحات اللي فيها سطور شبه متطابقة.

#     في المستندات النظامية بيتكرر نفس السطر بصيغته ("وبعد الاطلاع على...") عدة
#     مرات، والموديل ساعات بيفضل يعيد إنتاج نفس السطر بالحرف عشرات المرات لحد ما
#     يخلص السقف. السطر المتكرر حرفيًا أكتر من max_repeats مرة ورا بعض مش محتوى
#     حقيقي من الصفحة - بيتقص وبيتسجل تحذير.

#     الشرط "حرفيًا ومتتالي" مقصود: السطور المتكررة الحقيقية في المستندات دي
#     بتختلف في الرقم والتاريخ، فمبتتأثرش.
#     """
#     lines = text.split("\n")
#     result: list[str] = []
#     trimmed = 0
#     for line in lines:
#         stripped = line.strip()
#         if stripped and len(result) >= max_repeats:
#             if all(previous.strip() == stripped for previous in result[-max_repeats:]):
#                 trimmed += 1
#                 continue
#         result.append(line)

#     if trimmed:
#         logger.warning(
#             "اتقص %d سطر مكرر حرفيًا (لوب من الموديل، مش محتوى من الصفحة).", trimmed
#         )
#     return "\n".join(result)


# # ─────────────────────────────────────────────────────────────────────────────
# # الخط الزخرفي المشكّل (ترويسة المراسيم)
# # ─────────────────────────────────────────────────────────────────────────────
# # ترويسة المرسوم فيها "بسم الله الرحمن الرحيم" بخط الثلث مشكّل بالكامل،
# # والطغراء، والنص الدائري حوالين الشعار. نسبة الحركات للحروف في السطور دي
# # بتوصل ~0.6، بينما متن المستند نفسه نسبته صفر تقريبًا.
# #
# # نفس الفلتر بيمسك حاجة تانية مجانًا: التشكيل اللي الموديل بيهلوسه على
# # العبارات الرسمية المعروفة. المصدرين مختلفين بس العلاج واحد.

# # حروف بس، من غير الحركات ومن غير التطويل (\u0640). استبعاد التطويل مهم:
# # الخط الزخرفي بيستخدمه بكتافة، ولو اتحسب حرف كان هيقلل النسبة ويخفي الزخرفة.
# _ARABIC_LETTER_RE = re.compile(r"[\u0621-\u063F\u0641-\u064A\u0671-\u06D3]")

# # فوق النسبة دي = خط مشكّل عمدًا، مش حركة أو اتنين عابرة
# _CALLIGRAPHY_RATIO = 0.15
# # السطر القصير جدًا نسبته مضللة (كلمة من حرفين عليها حركة = 0.5)
# _CALLIGRAPHY_MIN_LETTERS = 4


# def calligraphy_ratio(line: str) -> float:
#     """نسبة الحركات للحروف في السطر. بترجّع 0.0 لو السطر أقصر من الحد الأدنى."""
#     letters = len(_ARABIC_LETTER_RE.findall(line))
#     if letters < _CALLIGRAPHY_MIN_LETTERS:
#         return 0.0
#     return len(_TASHKEEL_RE.findall(line)) / letters


# def clean_calligraphy_lines(
#     text: str,
#     mode: str = "strip",
#     max_ratio: float = _CALLIGRAPHY_RATIO,
# ) -> str:
#     """
#     يعالج السطور اللي نسبة تشكيلها عالية.

#     mode="strip"  (الافتراضي، الأأمن): بيشيل الحركات من السطر وبيسيب الكلمات.
#                   "بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيْمِ" مطبوعة فعلًا في المستند، فحذفها
#                   بيخلي النص المستخرج مش نسخة حرفية 100% وبيكسر البحث عنها
#                   في Laserfiche. شيل التشكيل بس بيحل مشكلة عدم الاتساق
#                   (نفس العبارة مرة مشكّلة ومرة لأ) من غير ما يضيّع محتوى.
#     mode="drop"   بيشيل السطر بالكامل. استخدمه بس لو مش عايز الترويسة الزخرفية
#                   في النص أصلًا.
#     mode="off"    بيرجّع النص زي ما هو.

#     ملحوظة: ده مختلف عن strip_tashkeel اللي بيشيل التشكيل من النص كله. هنا
#     السطور العادية مبتتلمسش خالص - لو التشكيل مطبوع فعلًا في سطر من المتن
#     بيفضل زي ما هو.
#     """
#     if mode == "off":
#         return text

#     kept: list[str] = []
#     touched: list[str] = []

#     for line in text.split("\n"):
#         if calligraphy_ratio(line) <= max_ratio:
#             kept.append(line)
#             continue

#         touched.append(line.strip())
#         if mode == "strip":
#             # collapse للمسافات كمان: شيل الحركة من خط الثلث بيسيب فراغات مضاعفة
#             kept.append(re.sub(r"[ \t]{2,}", " ", strip_tashkeel(line)))
#         # mode == "drop" → السطر مبيتضافش خالص

#     if touched:
#         logger.warning(
#             "%d سطر نسبة تشكيله عالية (خط زخرفي/تشكيل مهلوس) - %s: %s",
#             len(touched),
#             "اتشال التشكيل منه" if mode == "strip" else "السطر اتحذف",
#             touched,
#         )
#     return "\n".join(kept)


#     return "\n".join(kept)
