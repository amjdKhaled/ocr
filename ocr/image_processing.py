"""تجهيز الصور قبل إرسالها للموديل: base64 encoding، resize، وتقسيم الأعمدة."""

from __future__ import annotations

import base64
import io
import logging

from PIL import Image, ImageChops

from app.config import settings

logger = logging.getLogger(__name__)

# عتبة اعتبار البكسل "حبر" (أغمق من كده = حبر). كريمة عن قصد: بتتستخدم في
# كشف التخطيط (السطور، فراغ الأعمدة) واللي الأأمن فيه إننا نشوف كل حاجة.
_INK_THRESHOLD = 160
# عتبة "الحبر الغامق" - النص المطبوع الحقيقي بيعدّيها، العلامة المائية
# والختم الباهت لأ. بتتستخدم في has_enough_ink بس.
_DARK_INK_THRESHOLD = 110
# لو أقل من النسبة دي من حبر القصاصة غامق فعلًا، يبقى اللي فيها خلفية
# باهتة (ختم/علامة مائية) مش نص مطبوع.
_MIN_DARK_INK_SHARE = 0.15
# متوسط الحبر في العمود اللي تحته نعتبره فاضي (0-255)
_EMPTY_COLUMN_INK = 3
# أقل عرض للفراغ الفاصل بين عمودين، كنسبة من عرض الصفحة
_MIN_GUTTER_RATIO = 0.012
# الفراغ لازم يكون في النص، مش عند الحواف
_GUTTER_SEARCH_RANGE = (0.28, 0.72)
# جسم الأعمدة لازم يغطي على الأقل الجزء ده من ارتفاع الصفحة، وإلا فمفيش أعمدة
_MIN_BODY_HEIGHT_RATIO = 0.5
# الصفحة بتتقسم لشرائح أفقية بالارتفاع ده (نسبة من ارتفاع الصفحة) وبنشوف كل
# شريحة فيها فراغ رأسي ولا لأ
_SLICE_RATIO = 0.01
# أقل نسبة من شرائح الجسم لازم تكون دليل عمودين واضح، عشان منقسمش صفحة
# عمود واحد فيها منطقة بيضا كبيرة
_MIN_COLUMN_EVIDENCE = 0.25
# هامش بسيط حوالين كل قصاصة عشان محرفش حرف عند الحافة
_CROP_PADDING = 8
# متوسط الحبر في الصف اللي فوقه نعتبره سطر نص (أعلى من عتبة الأعمدة عشان
# النقط والشوائب في السكانر ماتتحسبش سطر)
_LINE_INK_THRESHOLD = 6
# أقل نسبة بكسل حبر في القصاصة عشان نعتبرها فيها نص. أقل من كده = هامش/خط
# زخرفي/خلفية ختم، وإرسالها للموديل بيولّد هلوسة بدل ما يرجّع فاضي.
#
# كانت 0.0025 (ربع في المية) - واطية جدًا لدرجة إن إطار جدول لوحده كان
# بيعدّيها، وده اللي خلى قصاصة الختم في الفاتورة توصل للموديل. لو لقيت
# قصاصات نص حقيقي بتتتخطى، رجّعها تحت شوية بالتدريج.
_MIN_INK_RATIO = 0.006
# أقل بُعد للقصاصة (بكسل) - أي حاجة أصغر مش هتكون سطر نص
_MIN_CROP_SIDE = 40
# أقل نسبة أعمدة فاضية جوه شريط عشان نعتبره كلام مش خط أفقي مصمت
_MIN_WORD_GAP_RATIO = 0.06
# سطر الكلام الحقيقي بيمتد أعرض من النسبة دي من عرض القصاصة
_MAX_DECORATIVE_SPAN = 0.80
# ومركزه بيبقى في النص، مش عند حافة (بوكس الرقم/التاريخ مركزه عند الحافة)
_DECORATIVE_CENTER = (0.35, 0.65)
# نسبة عرض الكتلة لارتفاعها. سطر الكلام دايمًا عريض وقصير (20:1 أو أكتر)،
# والعنصر الزخرفي (الطغراء، الشعار، الختم) كتلة مربعة تقريبًا (2:1 أو أقل).
_MAX_DECORATIVE_ASPECT = 4.0
# أقل عدد "سطور" في القصاصة عشان نحكم عليها إنها زخرفة
_MIN_DECORATIVE_LINES = 2

# فوق المستوى ده بعد قناة الأقصى = بقايا حبر ملوّن، بتتحوّل لأبيض صريح.
# الخط الأسود المطبوع بيقع تحت 100 بكتير حتى في المسح الباهت.
_COLOR_INK_WHITE_LEVEL = 140


def encode_image_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def remove_color_ink(image_bytes: bytes) -> bytes:
    """
    يشيل الحبر الملوّن (الأختام، التواقيع، الشعارات) وبيسيب النص الأسود.

    الطريقة: قناة الأقصى max(R,G,B). أي حبر ملوّن عنده قناة واحدة على الأقل
    عالية (الأزرق: B عالية، الأحمر: R عالية) فبيبهت لأبيض. الحبر الأسود
    المطبوع كل قنواته واطية فبيفضل أسود.

    ليه دي أحسن من كشف الدوائر (Hough) أو التبييض بقناع تشبّع:
    - بتمسك الختم الدائري والبيضاوي والمستطيل والتوقيع اليدوي بنفس السطر.
    - أهم حاجة: النص المطبوع اللي *تحت* الختم بيتحافظ عليه. القناع بيبيّض
      منطقة التقاطع كلها فبياكل الكلام اللي تحت الختم، والقناة دي لأ.
    - رخيصة جدًا (تلات عمليات على مستوى البكسل) - مش بتأثر على الوقت.

    ⚠ اقفلها (OCR_REMOVE_COLOR_INK=false) لو مستنداتك فيها عناوين أو أختام
    مطبوعة بالأحمر كمحتوى حقيقي مطلوب استخراجه.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    r, g, b = img.split()
    gray = ImageChops.lighter(ImageChops.lighter(r, g), b)
    # اللي فضل رمادي فاتح بعد القناة = بقايا الختم الباهتة، بتتدفع لأبيض
    # صريح عشان has_enough_ink ميحسبهاش حبر ويبعت قصاصة الختم للموديل.
    gray = gray.point(lambda p: 255 if p >= _COLOR_INK_WHITE_LEVEL else p)

    buffer = io.BytesIO()
    gray.save(buffer, format="JPEG", quality=settings.jpeg_quality)
    return buffer.getvalue()


def _to_ink(img: Image.Image, threshold: int = _INK_THRESHOLD) -> Image.Image:
    """
    يحوّل الصورة لماسك أبيض/أسود: الأبيض (255) = حبر، الأسود (0) = خلفية.

    كان مكرر حرفيًا في 3 أماكن، فأي تغيير في العتبة كان لازم يتعمل 3 مرات.
    """
    return img.convert("L").point(lambda v: 255 if v < threshold else 0, mode="L")


def _ink_profile(ink: Image.Image, axis: str) -> list[int]:
    """
    متوسط الحبر لكل عمود (axis="x") أو لكل صف (axis="y").

    الـ resize بفلتر BOX بياخد متوسط كل عمود/صف في بكسل واحد - أسرع بكتير من
    اللف على البكسلات، ومن غير ما نحتاج numpy.
    """
    width, height = ink.size
    size = (width, 1) if axis == "x" else (1, height)
    return list(ink.resize(size, Image.BOX).getdata())


def _longest_clean_run(profile: list[int], start: int, end: int, minimum: int) -> tuple[int, int] | None:
    """أطول مدى متصل في [start, end) قيمه كلها تحت عتبة الفراغ."""
    best: tuple[int, int] | None = None
    run_start = None
    for index in range(start, end + 1):
        clean = index < end and profile[index] <= _EMPTY_COLUMN_INK
        if clean:
            run_start = index if run_start is None else run_start
        elif run_start is not None:
            if best is None or index - run_start > best[1] - best[0]:
                best = (run_start, index)
            run_start = None
    if best is None or best[1] - best[0] < minimum:
        return None
    return best


def _find_gutter(ink: Image.Image, top: int, bottom: int) -> tuple[int, int] | None:
    """يلاقي أعرض شريط رأسي فاضي في نص الصفحة بين الصفين top و bottom."""
    width, _ = ink.size
    profile = _ink_profile(ink.crop((0, top, width, bottom)), "x")
    start, end = (int(width * ratio) for ratio in _GUTTER_SEARCH_RANGE)
    return _longest_clean_run(profile, start, end, int(width * _MIN_GUTTER_RATIO))


def _column_band(ink: Image.Image) -> tuple[int, int] | None:
    """
    يرجّع نطاق الصفوف اللي الصفحة فيها متقسّمة أعمدة فعلًا.

    بنقسّم الصفحة شرايح أفقية رفيعة، وكل شريحة بنشوف فيها فراغ رأسي كفاية ولا
    لأ. الترويسة/التذييل الممتدين على عرض الصفحة مفيهمش فراغ، فبيتستبعدوا.

    ليه مش مجرد "الفراغ نضيف من فوق لتحت": في الصفحات المضبوطة (justified)
    بيحصل إن سطر أو اتنين يوصلوا لحافة الفراغ ويقفلوه. الفحص بالشريحة بيتحمّل
    ده، لأن الشريحة بيفضل فيها فراغ رأسي حتى لو اتزحزح شوية.
    """
    width, height = ink.size
    slice_height = max(4, int(height * _SLICE_RATIO))
    slices = max(1, height // slice_height)
    search_start, search_end = (int(width * ratio) for ratio in _GUTTER_SEARCH_RANGE)
    min_gutter = int(width * _MIN_GUTTER_RATIO)

    # resize واحدة بترجّع متوسط الحبر لكل (x, شريحة) - أرخص من قراءة كل شريحة
    reduced = list(ink.resize((width, slices), Image.BOX).getdata())

    # تصنيف كل شريحة:
    #   COLUMNS  فيها فراغ رأسي ونص على جنبيه الاتنين = دليل على عمودين
    #   FULL     مفيش فيها فراغ رأسي خالص = سطر ممتد على عرض الصفحة (ترويسة/تذييل)
    #   NEUTRAL  الباقي (فراغ بين السطور، أو نص في عمود واحد بس) - لا بيأكد ولا بينفي
    COLUMNS, FULL, NEUTRAL = "C", "F", "N"
    states = []
    for index in range(slices):
        row = reduced[index * width : (index + 1) * width]
        gutter = _longest_clean_run(row, search_start, search_end, min_gutter)
        if gutter is None:
            states.append(FULL)
        elif (
            sum(row[: gutter[0]]) > _EMPTY_COLUMN_INK * gutter[0]
            and sum(row[gutter[1] :]) > _EMPTY_COLUMN_INK * (width - gutter[1])
        ):
            states.append(COLUMNS)
        else:
            states.append(NEUTRAL)

    # جسم الأعمدة = أطول مدى مفيهوش شريحة FULL. الشرايح الفاضية بين السطور
    # عادي تعدي جواه، لكن أول سطر عابر للعمودين بيقفل المدى.
    best = None
    run_start = None
    for index in range(slices + 1):
        if index < slices and states[index] != FULL:
            run_start = index if run_start is None else run_start
        elif run_start is not None:
            if best is None or index - run_start > best[1] - best[0]:
                best = (run_start, index)
            run_start = None

    if best is None:
        return None
    # لازم جزء معتبر من المدى يكون دليل عمودين فعلي، مش مجرد بياض
    columns_slices = states[best[0] : best[1]].count(COLUMNS)
    if columns_slices < (best[1] - best[0]) * _MIN_COLUMN_EVIDENCE:
        return None

    top, bottom = best[0] * slice_height, min(best[1] * slice_height, height)
    if bottom - top < height * _MIN_BODY_HEIGHT_RATIO:
        return None
    return top, bottom


def split_into_columns(image_bytes: bytes) -> list[bytes]:
    """
    يقسّم صفحة ذات عمودين لقصاصات مرتبة بترتيب القراءة العربي.

    الموديل بيتلخبط في الصفحات ذات العمودين: ساعات بيقرا العمود الشمال الأول
    (فالمواد بتطلع بترتيب مقلوب) وساعات بيخلط سطر من عمود مع سطر من التاني.
    التقسيم هنا بيشيل المشكلة دي من على الموديل خالص - كل نداء بيشوف عمود
    واحد بس، والترتيب بيتحدد هنا: الترويسة، بعدين العمود اليمين، بعدين اللي
    على شماله.

    لو الصفحة عمود واحد (أو التقسيم مش واضح) بترجع الصورة الأصلية زي ما هي.
    """
    if not settings.split_columns:
        return [image_bytes]

    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        ink = _to_ink(img)

        band = _column_band(ink)
        if band is None:
            return [image_bytes]

        body_top, body_bottom = band
        gutter = _find_gutter(ink, body_top, body_bottom)
        if gutter is None:
            logger.debug("جسم أعمدة اتلقى بس من غير فراغ واضح، الصفحة هتتبعت كاملة.")
            return [image_bytes]

        pad = _CROP_PADDING
        top = max(body_top - pad, 0)
        bottom = min(body_bottom + pad, height)

        boxes = []
        if body_top > 0:  # ترويسة ممتدة على عرض الصفحة
            boxes.append((0, 0, width, min(body_top + pad, height)))
        # اليمين الأول (ترتيب القراءة العربي)، بعدين الشمال
        boxes.append((max(gutter[1] - pad, 0), top, width, bottom))
        boxes.append((0, top, min(gutter[0] + pad, width), bottom))
        if body_bottom < height:  # تذييل ممتد على عرض الصفحة
            boxes.append((0, max(body_bottom - pad, 0), width, height))

        crops = []
        for box in boxes:
            buffer = io.BytesIO()
            img.crop(box).convert("RGB").save(buffer, format="JPEG", quality=settings.jpeg_quality)
            crops.append(buffer.getvalue())

        logger.info(
            "الصفحة اتقسمت لـ %d قصاصة (فراغ الأعمدة x=%d..%d، جسم الأعمدة y=%d..%d).",
            len(crops), gutter[0], gutter[1], body_top, body_bottom,
        )
        return crops
    except Exception:
        logger.warning("فشل تقسيم الأعمدة، الصفحة هتتبعت كاملة.", exc_info=True)
        return [image_bytes]


def _text_lines(ink: Image.Image) -> list[tuple[int, int]]:
    """يرجّع (بداية، نهاية) كل سطر نص في الصورة، من فوق لتحت."""
    _, height = ink.size
    profile = _ink_profile(ink, "y")

    lines: list[tuple[int, int]] = []
    line_start = None
    for y in range(height + 1):
        has_ink = y < height and profile[y] > _LINE_INK_THRESHOLD
        if has_ink:
            line_start = y if line_start is None else line_start
        elif line_start is not None:
            lines.append((line_start, y))
            line_start = None
    return lines


def count_text_lines(image_bytes: bytes) -> int:
    """
    عدد سطور النص المطبوعة في القصاصة.

    بيتقارن بعدد سطور رد الموديل في _transcribe: الرد اللي سطوره أكتر بكتير
    من السطور المطبوعة معناه إن الموديل ملى من ذاكرته بدل ما يقرا من الصورة.
    ده أقوى حارس عندنا ضد التلوث الكامل (فقرة من مستند تاني)، لأن الفقرة
    المهلوسة بتبقى عربي سليم الشكل فمفيش فلتر نصي بيمسكها.

    بيرجّع 0 لو الفحص فشل - يعني "اتجاهل المقارنة"، مش "القصاصة فاضية".
    """
    try:
        return len(_text_lines(_to_ink(Image.open(io.BytesIO(image_bytes)))))
    except Exception:
        logger.warning("فشل عدّ سطور القصاصة، المقارنة هتتجاهل.", exc_info=True)
        return 0


def split_into_bands(image_bytes: bytes) -> list[bytes]:
    """
    يقسّم قصاصة طويلة لشرايح أفقية، والقص بيحصل في الفراغ بين السطور.

    الصفحات المصوّرة الكثيفة (قرار فيه ١٥-٢٠ سطر بخط صغير على سكان قديم) الموديل
    بيقرا أول فقرة كويس وبعدين يقف أو يدخل في لوب - مش لأن السقف خلص، لكن لأنه
    بيفقد مكانه في الصفحة. لما الشريحة تبقى ٥-٦ سطور بس، النداء بيخلص وهو لسه
    ماسك مكانه، والنص بيكمل لآخر الصفحة.

    القص بيحصل في نص الفراغ بين سطرين، فمستحيل يتقطع سطر في النص. لو الصفحة
    قصيرة أو مفيهاش سطور واضحة بترجع زي ما هي.
    """
    if not settings.split_bands:
        return [image_bytes]

    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        ink = _to_ink(img)

        lines = _text_lines(ink)
        if len(lines) < settings.band_max_lines * 2:
            # صفحة قصيرة - التقسيم مش هيفيد، وكل نداء زيادة بيكلّف وقت
            return [image_bytes]

        # بنجمّع السطور في شرايح، والقص في نص الفراغ اللي بعد آخر سطر في الشريحة
        cuts: list[int] = [0]
        for index in range(settings.band_max_lines, len(lines), settings.band_max_lines):
            gap_start = lines[index - 1][1]
            gap_end = lines[index][0]
            cuts.append((gap_start + gap_end) // 2)
        cuts.append(height)

        crops = []
        for top, bottom in zip(cuts, cuts[1:]):
            buffer = io.BytesIO()
            crop = img.crop((0, max(top - _CROP_PADDING, 0), width, min(bottom + _CROP_PADDING, height)))
            crop.convert("RGB").save(buffer, format="JPEG", quality=settings.jpeg_quality)
            crops.append(buffer.getvalue())

        logger.info(
            "القصاصة اتقسمت لـ %d شريحة أفقية (%d سطر، %d سطر لكل شريحة).",
            len(crops), len(lines), settings.band_max_lines,
        )
        return crops
    except Exception:
        logger.warning("فشل التقسيم لشرايح، القصاصة هتتبعت كاملة.", exc_info=True)
        return [image_bytes]


def _looks_like_text(ink: Image.Image, top: int, bottom: int) -> bool:
    """
    هل الشريط ده (من top لـ bottom) كلمات ولا خط أفقي مصمت؟

    الكلام فيه فراغات بين الكلمات، فنسبة الأعمدة الفاضية جواه معتبرة. الخط
    الزخرفي/إطار الجدول/تسطير التوقيع ممتد ومصمت، فكل أعمدته فيها حبر.
    """
    width, _ = ink.size
    profile = _ink_profile(ink.crop((0, top, width, bottom)), "x")
    inked = sum(1 for value in profile if value > _EMPTY_COLUMN_INK)
    if not inked:
        return False
    empty_ratio = 1 - (inked / width)
    return empty_ratio >= _MIN_WORD_GAP_RATIO


def _line_geometry(ink: Image.Image, top: int, bottom: int) -> tuple[float, float] | None:
    """(الامتداد الأفقي، مركز الامتداد) للسطر، الاتنين كنسبة من عرض القصاصة."""
    width, _ = ink.size
    profile = _ink_profile(ink.crop((0, top, width, bottom)), "x")
    inked = [x for x, value in enumerate(profile) if value > _EMPTY_COLUMN_INK]
    if not inked:
        return None
    return (inked[-1] - inked[0]) / width, (inked[0] + inked[-1]) / 2 / width


def looks_decorative(image_bytes: bytes) -> bool:
    """
    هل القصاصة دي شعار/خط زخرفي مركزي بدل سطور كلام؟

    الشرط: كل السطور المكتشفة ضيقة (مش ممتدة لعرض القصاصة) ومركزها في نص
    القصاصة. سطر الكلام العربي الحقيقي بيمتد من الهامش للهامش.

    ⚠ شرط "المركز في النص" هو اللي بيحمي بوكس "الرقم" و"التاريخ": هو كمان
    سطور ضيقة، بس مركزه عند حافة الصفحة مش في نصها. من غير الشرط ده كان
    الفلتر هياكل أهم حقلين في المستند.

    وبالتالي: في قصاصة الترويسة اللي فيها الشعار + بوكس الرقم مع بعض، الدالة
    دي هترجّع False والقصاصة هتتبعت عادي. ده تصرف مقصود - أحسن من إننا
    نخاطر بالرقم والتاريخ.

    مقفولة افتراضيًا (skip_decorative=False): مكسبها إنها بتوفر نداء واحد
    للموديل، وخسارتها المحتملة إنها تاكل بند قصير متمركز من المتن (زي
    "أمرنا بما هو آت:"). فلتر التشكيل في text_cleaning بيغطي الشعار بعد
    القراءة أصلًا، فدي تحسين مش ضرورة.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, _ = img.size
        ink = _to_ink(img)
        lines = _text_lines(ink)
        if len(lines) < _MIN_DECORATIVE_LINES:
            return False

        has_block = False
        for top, bottom in lines:
            geometry = _line_geometry(ink, top, bottom)
            if geometry is None:
                continue
            span, center = geometry
            if span > _MAX_DECORATIVE_SPAN:
                return False  # سطر ممتد على عرض القصاصة = كلام
            if not _DECORATIVE_CENTER[0] < center < _DECORATIVE_CENTER[1]:
                return False  # مركزه عند حافة = بوكس رقم/تاريخ
            if span * width / max(bottom - top, 1) <= _MAX_DECORATIVE_ASPECT:
                has_block = True

        # لازم يكون فيه كتلة مربعة واحدة على الأقل (شعار/طغراء/ختم). صفحة
        # كلام مهما كانت سطورها قصيرة ومتمركزة مش بتحتوي على كتلة زي دي،
        # فالشرط ده هو اللي بيمنع أكل بند قصير متمركز من المتن.
        if not has_block:
            return False

        logger.info(
            "قصاصة زخرفية (%d عنصر متمركز فيهم كتلة شعار/طغراء) - اتتخطت.", len(lines)
        )
        return True
    except Exception:
        logger.warning("فشل فحص الزخرفة، القصاصة هتتبعت عادي.", exc_info=True)
        return False


def has_enough_ink(image_bytes: bytes) -> bool:
    """
    هل القصاصة دي فيها نص فعلًا ولا شبه فاضية؟

    ده أهم حاجز ضد الهلوسة. قصاصة زي شريط تذييل فيه خط زخرفي بس، أو هامش
    فاضي، أو خلفية ختم باهتة - الموديل مبيلاقيش فيها حاجة يقراها، فبدل ما
    يسكت بيملا الفراغ من ذاكرته (بيرجّع نص البرومبت أو boilerplate بتاع
    مستندات شبيهة). أرخص وأضمن حل: منبعتش القصاصة دي للموديل من الأصل.

    تلات فحوص، كلهم لازم يعدّوا:
    1. نسبة الحبر الكلية فوق الحد الأدنى
    2. نسبة معتبرة من الحبر ده غامق فعلًا (مش خلفية ختم باهتة)
    3. فيه سطر واحد على الأقل شكله كلام مش خط مصمت
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if width < _MIN_CROP_SIDE or height < _MIN_CROP_SIDE:
            logger.info("قصاصة صغيرة جدًا (%dx%d) - اتتخطت.", width, height)
            return False

        ink = _to_ink(img)
        # متوسط الحبر على الصورة كلها (0-255) ÷ 255 = نسبة البكسل الغامق
        ink_ratio = sum(_ink_profile(ink, "y")) / (height * 255)
        if ink_ratio < _MIN_INK_RATIO:
            logger.info(
                "قصاصة شبه فاضية (نسبة حبر %.4f < %.4f) - اتتخطت قبل ما تتبعت للموديل.",
                ink_ratio, _MIN_INK_RATIO,
            )
            return False

        # الختم الدائري الباهت والعلامة المائية بيعدّوا فحص الحبر فوق لأنهم
        # بيغطوا مساحة كبيرة، بس رماديين. النص المطبوع الحقيقي أغمق بكتير.
        # المقارنة نسبية مش مطلقة، عشان السكان الفاتح ككل ميتعاقبش.
        dark = _to_ink(img, threshold=_DARK_INK_THRESHOLD)
        dark_ratio = sum(_ink_profile(dark, "y")) / (height * 255)
        if ink_ratio and dark_ratio / ink_ratio < _MIN_DARK_INK_SHARE:
            logger.info(
                "قصاصة حبرها باهت (غامق %.4f من إجمالي %.4f = %.0f%%) - "
                "خلفية ختم/علامة مائية غالبًا، اتتخطت.",
                dark_ratio, ink_ratio, dark_ratio / ink_ratio * 100,
            )
            return False

        lines = _text_lines(ink)
        if not lines:
            logger.info("قصاصة مفيهاش سطور نص واضحة - اتتخطت.")
            return False

        # الخط الأفقي الزخرفي (فاصل/إطار/تسطير التوقيع) بيعدّي فحص الحبر عادي
        # لأنه ممتد على عرض الصفحة. الفرق إنه مصمت: كل أعمدته فيها حبر. سطر
        # النص الحقيقي لازم يكون فيه فراغات بين الكلمات.
        if not any(_looks_like_text(ink, top, bottom) for top, bottom in lines):
            logger.info(
                "قصاصة فيها خطوط زخرفية/إطار بس من غير كلمات (%d خط) - اتتخطت.", len(lines)
            )
            return False
        return True
    except Exception:
        # لو الفحص نفسه فشل، منمنعش القصاصة - أسوأ حاجة إنها تتبعت زي الأول
        logger.warning("فشل فحص كثافة الحبر، القصاصة هتتبعت عادي.", exc_info=True)
        return True


def resize_image_if_needed(image_bytes: bytes, max_dimension: int) -> bytes:
    """
    يكبّر/يصغّر الصورة بس لو أكبر من max_dimension. لو الصورة أصلاً أصغر أو
    تساوي الحد، بترجع البايتس الأصلية من غير أي تعديل (لتفادي أي فقدان جودة
    من غير داعي). عند الفشل (صورة تالفة مثلًا) بيرجع البايتس الأصلية بدل ما
    يكسر الطلب كله.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        if max(width, height) <= max_dimension:
            return image_bytes

        ratio = max_dimension / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.convert("RGB").resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=settings.jpeg_quality)
        return buffer.getvalue()
    except Exception:
        logger.warning("تعذّر عمل resize للصورة، هيتم استخدام النسخة الأصلية.", exc_info=True)
        return image_bytes