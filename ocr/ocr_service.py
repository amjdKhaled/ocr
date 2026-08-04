# """
# منطق الاستخراج: بناء البرومبت، نداء Ollama، تنضيف الرد.

# مبدأ أساسي في /extract-all-text: النص الراجع من الموديل بيترجّع زي ما هو.
# أي تعديل بعدي (شيل تشكيل، استبدال أرقام) بيغيّر نص المستند فعليًا، فكله
# اختياري ومقفول افتراضيًا في config.

# استثناء واحد مفتوح افتراضيًا: clean_calligraphy_lines في وضع "strip". هو
# مبيحذفش أي كلمة - بيوحّد بس سطر الترويسة المشكّل مع باقي النص.
# """

# from __future__ import annotations

# import logging

# from app.config import settings
# from app.image_processing import (
#     count_text_lines,
#     encode_image_bytes,
#     has_enough_ink,
#     looks_decorative,
#     remove_color_ink,
#     resize_image_if_needed,
#     split_into_bands,
#     split_into_columns,
# )
# from app.prompts import build_fields_prompt, build_raw_text_prompt
# from app.text_cleaning import (
#     clean_calligraphy_lines,
#     clean_extracted_fields,
#     collapse_degenerate_runs,
#     parse_json_response,
#     strip_prompt_echo,
#     strip_single_word_tail,
#     strip_tashkeel,
#     strip_watermarks,
#     trim_runaway_repetition,
# )
# from app.ollama_client import generate

# logger = logging.getLogger(__name__)

# _EMPTY_VALUES = (None, "", [], {})


# async def extract_fields(image_bytes: bytes, fields: list[str], doc_type: str = "") -> dict:
#     """استخراج حقول محددة من صورة صفحة واحدة."""
#     resized = resize_image_if_needed(image_bytes, max_dimension=settings.max_image_dimension)

#     raw = await generate(
#         prompt=build_fields_prompt(fields, doc_type=doc_type),
#         image_b64=encode_image_bytes(resized),
#         num_predict=settings.fields_num_predict,
#         response_format_json=True,
#     )

#     logger.debug("رد الموديل الخام (المرور الأول) للحقول %s: %s", fields, raw[:600])

#     parsed = parse_json_response(raw)
#     if "خطأ" in parsed:
#         logger.warning(
#             "فشل تحليل JSON (المرور الأول) للحقول %s — الرد: %s",
#             fields, raw[:300],
#         )

#     result = clean_extracted_fields(parsed)

#     # الموديل ساعات بيرجّع مفاتيح زيادة أو ناقصة عن اللي اتطلب. بنثبّت الشكل
#     # على الحقول المطلوبة بالظبط عشان المستهلك (Laserfiche) يلاقي كل مفتاح
#     # متوقع موجود، والمفاتيح المخترعة متعديش.
#     normalized = {f: result.get(f) for f in fields}
#     extra_keys = [k for k in result if k not in normalized and k != "النص_الخام"]
#     if extra_keys:
#         logger.info("الموديل رجّع مفاتيح مش مطلوبة، هيتم تجاهلها: %s", extra_keys)

#     final_empty = [k for k, v in normalized.items() if v in _EMPTY_VALUES]
#     if final_empty:
#         logger.info("حقول فارغة في النتيجة النهائية: %s", final_empty)

#     return normalized


# def merge_page_fields(pages: list[dict], fields: list[str]) -> dict:
#     """
#     يدمج نتائج الحقول من عدة صفحات: أول قيمة غير فاضية بتكسب.

#     الصفحات بتتقرا بالترتيب، والحقل عادة بيكون في الصفحة الأولى؛ الصفحات
#     اللي بعدها بتملا الفاضي بس (زي التوقيع/التاريخ في آخر صفحة) من غير ما
#     تدوس على قيمة اتقرت قبل كده.
#     """
#     merged: dict = {f: None for f in fields}
#     for page_result in pages:
#         for key in fields:
#             if merged[key] in _EMPTY_VALUES:
#                 value = page_result.get(key)
#                 if value not in _EMPTY_VALUES:
#                     merged[key] = value
#     return merged


# async def _transcribe(image_bytes: bytes) -> str:
#     """
#     نداء واحد للموديل على قصاصة واحدة، والرد بيرجع زي ما هو تقريبًا.

#     ترتيب التنضيف مقصود: بنشيل الحاجات اللي الموديل ملهاش أي أصل في الصورة
#     (علامة مائية، برومبت راجع، ذيل مفكوك) الأول، وبعدين بنعالج اللوبات. لو
#     اتعكس، اللوب بيتقص من نص كلامنا إحنا بدل نص المستند.
#     """
#     resized = resize_image_if_needed(
#         image_bytes, max_dimension=settings.max_image_dimension_text
#     )
#     raw_text = await generate(
#         prompt=build_raw_text_prompt(),
#         image_b64=encode_image_bytes(resized),
#         num_predict=settings.text_num_predict,
#     )

#     text = strip_prompt_echo(strip_watermarks(raw_text).strip())
#     # الـ echo المفكوك (كلمة في كل سطر) مبيتمسكش بالمقارنة الحرفية فوق،
#     # فبيتقص هنا بالشكل. لازم قبل trim_runaway_repetition عشان السطور
#     # المفردة المتشابهة متتحسبش لوب تكرار حقيقي.
#     text = strip_single_word_tail(text, min_run=settings.echo_tail_min_run)
#     text = trim_runaway_repetition(collapse_degenerate_runs(text))

#     return _guard_line_inflation(image_bytes, text)


# def _guard_line_inflation(image_bytes: bytes, text: str) -> str:
#     """
#     يلغي الرد لو سطوره أكتر بكتير من السطور المطبوعة في القصاصة.

#     ده الحارس الوحيد اللي بيمسك التلوث الكامل - يعني لما الموديل يجيب فقرة
#     من مستند تاني خالص (نص وزارة الداخلية اللي ظهر في فاتورة مواد بناء).
#     الفقرة دي عربي سليم الشكل، فمفيش أي فلتر نصي بيفرّقها عن المحتوى
#     الحقيقي. الدليل الوحيد إنها مش من الصورة هو إنها أطول من الصورة.

#     العدّ بيتم على image_bytes الأصلية مش المصغّرة: التصغير بيلزّق السطور
#     المتقاربة في بعض فبيقلل العدد ويولّد إنذار كاذب.
#     """
#     if settings.max_line_inflation <= 0 or not text:
#         return text

#     expected = count_text_lines(image_bytes)
#     actual = sum(1 for line in text.split("\n") if line.strip())
#     if not expected or actual <= expected * settings.max_line_inflation:
#         return text

#     logger.warning(
#         "الرد %d سطر والقصاصة فيها %d سطر مطبوع (تضخم %.1f×) - هلوسة غالبًا.%s",
#         actual, expected, actual / expected,
#         " اتسجل بس، الرد اتساب." if settings.line_inflation_log_only else " الرد اتلغى.",
#     )
#     return text if settings.line_inflation_log_only else ""


# async def extract_all_text(original_image_bytes: bytes) -> str:
#     """
#     استخراج النص الكامل من صورة صفحة واحدة، حرفيًا زي ما هو.

#     لو الصفحة عمودين بتتقسم الأول لقصاصات (ترويسة، عمود يمين، عمود شمال،
#     تذييل) وكل قصاصة بتتبعت لوحدها - كده الموديل مش مضطر يحل مشكلة الترتيب،
#     وكمان رد كل نداء بيبقى أقصر فاحتمال دخوله في لوب تكرار بيقل.

#     القصاصات الشبه فاضية بتتشال قبل ما تتبعت خالص: الموديل لما ميلاقيش نص
#     مبيسكتش، بيملا الفراغ من ذاكرته (نص البرومبت أو boilerplate من مستندات
#     شبيهة). ده كان مصدر أغلب السطور المزيفة في النتايج.
#     """
#     # ⚠ أول خطوة: شيل الحبر الملوّن (الختم/التوقيع/الشعار). لازم تحصل قبل
#     # التقطيع عشان has_enough_ink و looks_decorative يحكموا على الحبر
#     # الأسود الحقيقي بس - كده قصاصة الختم بتتفلتر لوحدها ومبتوصلش للموديل.
#     if settings.remove_color_ink:
#         original_image_bytes = remove_color_ink(original_image_bytes)

#     crops = [
#         band
#         for column in split_into_columns(original_image_bytes)
#         for band in split_into_bands(column)
#     ]
#     readable = [
#         crop
#         for crop in crops
#         if has_enough_ink(crop)
#         and not (settings.skip_decorative and looks_decorative(crop))
#     ]
#     if len(readable) < len(crops):
#         logger.info(
#             "اتتخطت %d قصاصة من %d لأنها شبه فاضية.", len(crops) - len(readable), len(crops)
#         )
#     if not readable:
#         logger.warning("مفيش أي قصاصة فيها نص مقروء في الصفحة دي - هترجع فاضية.")
#         return ""

#     parts = [await _transcribe(crop) for crop in readable]
#     text = "\n".join(part for part in parts if part).strip()

#     # ⚠ ترتيب حرج: ده لازم يجي قبل strip_tashkeel. الفلتر ده بيتعرّف على
#     # السطر الزخرفي من نسبة الحركات فيه، فلو التشكيل اتشال من النص كله
#     # الأول، النسبة بتبقى صفر والفلتر بيبقى كود ميت.
#     text = clean_calligraphy_lines(text, mode=settings.calligraphy_mode)

#     if settings.strip_tashkeel_from_text:
#         text = strip_tashkeel(text)

#     return text

"""
منطق الاستخراج: بناء البرومبت، نداء Ollama، تنضيف الرد.

مبدأ أساسي في /extract-all-text: النص الراجع من الموديل بيترجّع زي ما هو.
أي تعديل بعدي (شيل تشكيل، استبدال أرقام) بيغيّر نص المستند فعليًا، فكله
اختياري ومقفول افتراضيًا في config.

استثناء واحد مفتوح افتراضيًا: clean_calligraphy_lines في وضع "strip". هو
مبيحذفش أي كلمة - بيوحّد بس سطر الترويسة المشكّل مع باقي النص.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.image_processing import (
    count_text_lines,
    encode_image_bytes,
    has_enough_ink,
    looks_decorative,
    remove_color_ink,
    resize_image_if_needed,
    split_into_bands,
    split_into_columns,
)
from app.prompts import build_fields_prompt, build_raw_text_prompt
from app.text_cleaning import (
    clean_calligraphy_lines,
    clean_extracted_fields,
    collapse_degenerate_runs,
    parse_json_response,
    strip_prompt_echo,
    strip_single_word_tail,
    strip_tashkeel,
    strip_watermarks,
    trim_runaway_repetition,
)
from app.ollama_client import generate

logger = logging.getLogger(__name__)

_EMPTY_VALUES = (None, "", [], {})

# الحقول اللي المفروض تكون سطر واحد قصير. الموديل بيميل إنه يملاها بمتن
# المستند لما ملقيش سطر موضوع صريح مطبوع.
_SUBJECT_FIELD_MARKERS = ("موضوع", "عنوان", "Subject", "Title")


def _guard_subject_length(fields: dict) -> dict:
    """
    يلغي قيمة حقل الموضوع لو رجعت فقرة كاملة بدل سطر.

    السيناريو الحقيقي: قرار مجلس وزراء مفيهوش سطر "الموضوع:" مطبوع، فالموديل
    حط الديباجة كلها ("بعد الاطلاع على... يقرر ما يلي:") في "موضوع القرار".
    القيمة دي بتتكتب في Laserfiche وبتفسد البحث والفهرسة.

    null أنضف من فقرة غلط: البرومبت بيطلب null صراحة في الحالة دي، والحارس
    ده شبكة الأمان لو الموديل مسمعش الكلام.
    """
    if settings.max_subject_words <= 0:
        return fields

    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            continue
        if not any(marker in name for marker in _SUBJECT_FIELD_MARKERS):
            continue
        word_count = len(value.split())
        if word_count > settings.max_subject_words:
            logger.warning(
                "الحقل '%s' رجع %d كلمة (السقف %d) - ده متن المستند مش سطر "
                "موضوع، القيمة اتلغت. أول 80 حرف: %s",
                name, word_count, settings.max_subject_words, value[:80],
            )
            fields[name] = None
    return fields


async def extract_fields(image_bytes: bytes, fields: list[str], doc_type: str = "") -> dict:
    """استخراج حقول محددة من صورة صفحة واحدة."""
    resized = resize_image_if_needed(image_bytes, max_dimension=settings.max_image_dimension)

    raw = await generate(
        prompt=build_fields_prompt(fields, doc_type=doc_type),
        image_b64=encode_image_bytes(resized),
        num_predict=settings.fields_num_predict,
        response_format_json=True,
    )

    logger.debug("رد الموديل الخام (المرور الأول) للحقول %s: %s", fields, raw[:600])

    parsed = parse_json_response(raw)
    if "خطأ" in parsed:
        logger.warning(
            "فشل تحليل JSON (المرور الأول) للحقول %s — الرد: %s",
            fields, raw[:300],
        )

    result = clean_extracted_fields(parsed)

    # الموديل ساعات بيرجّع مفاتيح زيادة أو ناقصة عن اللي اتطلب. بنثبّت الشكل
    # على الحقول المطلوبة بالظبط عشان المستهلك (Laserfiche) يلاقي كل مفتاح
    # متوقع موجود، والمفاتيح المخترعة متعديش.
    normalized = {f: result.get(f) for f in fields}
    extra_keys = [k for k in result if k not in normalized and k != "النص_الخام"]
    if extra_keys:
        logger.info("الموديل رجّع مفاتيح مش مطلوبة، هيتم تجاهلها: %s", extra_keys)

    normalized = _guard_subject_length(normalized)

    final_empty = [k for k, v in normalized.items() if v in _EMPTY_VALUES]
    if final_empty:
        logger.info("حقول فارغة في النتيجة النهائية: %s", final_empty)

    return normalized


def merge_page_fields(pages: list[dict], fields: list[str]) -> dict:
    """
    يدمج نتائج الحقول من عدة صفحات: أول قيمة غير فاضية بتكسب.

    الصفحات بتتقرا بالترتيب، والحقل عادة بيكون في الصفحة الأولى؛ الصفحات
    اللي بعدها بتملا الفاضي بس (زي التوقيع/التاريخ في آخر صفحة) من غير ما
    تدوس على قيمة اتقرت قبل كده.
    """
    merged: dict = {f: None for f in fields}
    for page_result in pages:
        for key in fields:
            if merged[key] in _EMPTY_VALUES:
                value = page_result.get(key)
                if value not in _EMPTY_VALUES:
                    merged[key] = value
    return merged


async def _transcribe(image_bytes: bytes) -> str:
    """
    نداء واحد للموديل على قصاصة واحدة، والرد بيرجع زي ما هو تقريبًا.

    ترتيب التنضيف مقصود: بنشيل الحاجات اللي الموديل ملهاش أي أصل في الصورة
    (علامة مائية، برومبت راجع، ذيل مفكوك) الأول، وبعدين بنعالج اللوبات. لو
    اتعكس، اللوب بيتقص من نص كلامنا إحنا بدل نص المستند.
    """
    resized = resize_image_if_needed(
        image_bytes, max_dimension=settings.max_image_dimension_text
    )
    raw_text = await generate(
        prompt=build_raw_text_prompt(),
        image_b64=encode_image_bytes(resized),
        num_predict=settings.text_num_predict,
    )

    text = strip_prompt_echo(strip_watermarks(raw_text).strip())
    # الـ echo المفكوك (كلمة في كل سطر) مبيتمسكش بالمقارنة الحرفية فوق،
    # فبيتقص هنا بالشكل. لازم قبل trim_runaway_repetition عشان السطور
    # المفردة المتشابهة متتحسبش لوب تكرار حقيقي.
    text = strip_single_word_tail(text, min_run=settings.echo_tail_min_run)
    text = trim_runaway_repetition(collapse_degenerate_runs(text))

    return _guard_line_inflation(image_bytes, text)


def _guard_line_inflation(image_bytes: bytes, text: str) -> str:
    """
    يلغي الرد لو سطوره أكتر بكتير من السطور المطبوعة في القصاصة.

    ده الحارس الوحيد اللي بيمسك التلوث الكامل - يعني لما الموديل يجيب فقرة
    من مستند تاني خالص (نص وزارة الداخلية اللي ظهر في فاتورة مواد بناء).
    الفقرة دي عربي سليم الشكل، فمفيش أي فلتر نصي بيفرّقها عن المحتوى
    الحقيقي. الدليل الوحيد إنها مش من الصورة هو إنها أطول من الصورة.

    العدّ بيتم على image_bytes الأصلية مش المصغّرة: التصغير بيلزّق السطور
    المتقاربة في بعض فبيقلل العدد ويولّد إنذار كاذب.
    """
    if settings.max_line_inflation <= 0 or not text:
        return text

    expected = count_text_lines(image_bytes)
    actual = sum(1 for line in text.split("\n") if line.strip())
    if not expected or actual <= expected * settings.max_line_inflation:
        return text

    logger.warning(
        "الرد %d سطر والقصاصة فيها %d سطر مطبوع (تضخم %.1f×) - هلوسة غالبًا.%s",
        actual, expected, actual / expected,
        " اتسجل بس، الرد اتساب." if settings.line_inflation_log_only else " الرد اتلغى.",
    )
    return text if settings.line_inflation_log_only else ""


async def extract_all_text(original_image_bytes: bytes) -> str:
    """
    استخراج النص الكامل من صورة صفحة واحدة، حرفيًا زي ما هو.

    لو الصفحة عمودين بتتقسم الأول لقصاصات (ترويسة، عمود يمين، عمود شمال،
    تذييل) وكل قصاصة بتتبعت لوحدها - كده الموديل مش مضطر يحل مشكلة الترتيب،
    وكمان رد كل نداء بيبقى أقصر فاحتمال دخوله في لوب تكرار بيقل.

    القصاصات الشبه فاضية بتتشال قبل ما تتبعت خالص: الموديل لما ميلاقيش نص
    مبيسكتش، بيملا الفراغ من ذاكرته (نص البرومبت أو boilerplate من مستندات
    شبيهة). ده كان مصدر أغلب السطور المزيفة في النتايج.
    """
    # ⚠ أول خطوة: شيل الحبر الملوّن (الختم/التوقيع/الشعار). لازم تحصل قبل
    # التقطيع عشان has_enough_ink و looks_decorative يحكموا على الحبر
    # الأسود الحقيقي بس - كده قصاصة الختم بتتفلتر لوحدها ومبتوصلش للموديل.
    if settings.remove_color_ink:
        original_image_bytes = remove_color_ink(original_image_bytes)

    crops = [
        band
        for column in split_into_columns(original_image_bytes)
        for band in split_into_bands(column)
    ]
    readable = [
        crop
        for crop in crops
        if has_enough_ink(crop)
        and not (settings.skip_decorative and looks_decorative(crop))
    ]
    if len(readable) < len(crops):
        logger.info(
            "اتتخطت %d قصاصة من %d لأنها شبه فاضية.", len(crops) - len(readable), len(crops)
        )
    if not readable:
        logger.warning("مفيش أي قصاصة فيها نص مقروء في الصفحة دي - هترجع فاضية.")
        return ""

    parts = [await _transcribe(crop) for crop in readable]
    text = "\n".join(part for part in parts if part).strip()

    # ⚠ ترتيب حرج: ده لازم يجي قبل strip_tashkeel. الفلتر ده بيتعرّف على
    # السطر الزخرفي من نسبة الحركات فيه، فلو التشكيل اتشال من النص كله
    # الأول، النسبة بتبقى صفر والفلتر بيبقى كود ميت.
    text = clean_calligraphy_lines(text, mode=settings.calligraphy_mode)

    if settings.strip_tashkeel_from_text:
        text = strip_tashkeel(text)

    return text