
from __future__ import annotations

import logging
import re
import textwrap

logger = logging.getLogger(__name__)

# FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
_INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


def _normalize_field_name(name: str) -> str:
    """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
    return _INVISIBLE_CHARS_RE.sub("", name.strip())


_GENERAL_RULES = """\
You are an expert OCR and document information extraction system specialized in
Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
commercial documents (invoices, receipts, quotations).
{doc_type_context}
Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
footers, stamps, logo areas) and extract ONLY these fields:
{fields_list}

OUTPUT FORMAT
1. Return ONLY a single valid, minified JSON object - no markdown, no ```
   fences, no comments, no explanations, no text before or after it.
2. Use EXACTLY the requested field names as JSON keys, character for
   character, in the same order they were given.
3. Never invent extra fields.

MISSING VALUES - read this before answering
4. This document may simply not contain some of the requested fields. That is
   normal and expected. If a field's value is not printed on this page, return
   null for it. Returning null is the CORRECT answer - it is never penalized.
5. Never fill a field by borrowing a different value from elsewhere on the
   page. A date that is not the requested date, or a number that belongs to a
   different label, is WRONG - more wrong than null. Do not reason about what
   the value "should" or "would typically" be: if you cannot point at the exact
   printed characters for that specific field, the answer is null.

TEXT FIDELITY
6. Copy the original text exactly (Arabic stays Arabic, English stays
   English - never translate, transliterate, paraphrase, or "correct" wording).
   If a printed word looks unusual or misspelled, copy it as printed anyway -
   do not substitute it with a different, more "expected" word. Do NOT add
   Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
   in the image, even for well-known phrases like country/ministry names -
   if the source text has no diacritics, your output must have none either.
7. Proper nouns (place names, personal names) need extra letter-by-letter
   care: several Arabic letters differ only by the number or position of
   their dots, and are easy to confuse. Verify each letter against the image
   instead of auto-completing to the most common or most familiar name.
   Never replace a printed name with a better-known name that looks similar.
8. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
   digit form as printed, keep commas/decimal separators/currency symbols as
   printed. Any reference/tracking number written inside parentheses or
   brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
   digit-by-digit against the image before being used - these are the
   numbers most often misread.
9. Date fields: copy exactly as printed, including any Hijri/Gregorian era
   marker, in the original order and with the original separators. Never
   convert calendars and never reformat. Keep every digit group in the exact
   left-to-right order shown in the image, even if another order is more
   familiar to you. Reference numbers that mix an Arabic letter with digits
   around a slash keep that letter as a letter - never turn it into a digit
   and never drop it.

LAYOUT
10. Arabic pages read RIGHT to LEFT. If the page is split into vertical
    columns, read the entire RIGHT column top-to-bottom first, then the next
    column to its left - never alternate between columns line by line.
11. Ignore watermarks, background stamps, or repeated translucent/diagonal
    overlay text that is not real document content (e.g. "Demonstration
    License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
12. Bilingual headers/letterheads often print the SAME info twice - once in
    English, once in Arabic (side by side or stacked, sometimes next to a
    logo). Treat them as two separate text blocks and read both fully; small
    Arabic text next to a logo is real text, not decoration.
13. When a requested field's NAME is written in Arabic and the document
    shows that information in both Arabic and English, return the ARABIC
    version by default (unless the field name is itself in English, in
    which case return the English version).
    CRITICAL — NO STRAY LATIN IN ARABIC FIELDS: When a field name is in
    Arabic, every character in its value must come from the Arabic script
    (including Arabic-Indic digits ٠-٩ and punctuation). Do NOT inject
    any Latin letter (a–z, A–Z) anywhere in the value — not as a
    spurious initial, not as a transliteration fragment, not as a
    "helpful" label. If the printed value is purely Arabic, your output
    must be purely Arabic. Even one stray Latin character (like a lone
    "e" or "a") is an error.
14. Tables: first read the header row fully (both languages if bilingual)
    to establish the real column order as printed on THIS document. Then map
    each number in a row to its column strictly by its printed position -
    never assume a "typical" order.
15. If a field's value wraps across multiple printed lines, join it into
    ONE continuous value with single spaces between words - no merged
    words, no leftover line breaks, no double spaces.

Before answering, check every non-null value one more time: can you point at
the exact printed characters for it on THIS page, next to THAT field's own
label? If not, change it to null. Return ONLY the JSON object."""

_FIELD_GUIDANCE: dict[str, str] = {
    # ---------------- تكليف ----------------
    "رقم التكليف": """\
- "رقم التكليف" is the official assignment/tasking number, usually near the
  top of the document, often preceded by "رقم" or written in a reference box.""",
    "تاريخ التكليف": """\
- "تاريخ التكليف" is the date the assignment document itself was issued
  (not the start/end dates of the assignment period).""",
    "اسم المكلف": """\
- "اسم المكلف" is the full name of the person being assigned/tasked. It
  usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
    "تاريخ بداية التكليف": """\
- "تاريخ بداية التكليف" is the start date of the assignment period. Do not
  confuse it with the issue date of the document.""",
    "تاريخ نهاية التكليف": """\
- "تاريخ نهاية التكليف" is the end date of the assignment period.""",
    "الموضوع": """\
- "الموضوع" is the subject/topic stated in the document, usually appearing
  after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
    "صادر من": """\
- "صادر من" is the name/title of the person or authority who issued the
  document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
  near a signature block at the bottom.""",
    # ---------------- قرار ----------------
    "رقم القرار": """\
- "رقم القرار" is the official decision number, usually near the top or in a
  reference box, often preceded by "رقم القرار" or "القرار رقم".""",
    "تاريخ القرار": """\
- "تاريخ القرار" is the date the decision was issued/signed.""",
    "موضوع القرار": """\
- "موضوع القرار" is the short subject TITLE of the decision - one line, at
  most 20 words. It is normally printed after a subject label, or in the
  reference box near the decision number and date.
- It is NOT the body of the decision and NOT the preamble. A council decision
  opens with a long chain of recitals (each one starting with a phrase meaning
  "having reviewed" / "and having considered") that ends with a phrase meaning
  "hereby decides the following". That whole chain is the preamble: NEVER
  return any part of it as the subject.
- Never return a value longer than one line, never return a value containing
  a full stop followed by more sentences, and never return a value that
  begins with a recital opener.
- If the page has no short printed subject line, return null. A wrong long
  value is much worse than null here.""",
    "الجهة المصدرة": """\
- "الجهة المصدرة" is the entity/department/authority that issued the
  decision, often in letterhead at the top or near the signature at the
  bottom.""",
    # ---------------- تعميم ----------------
    "تاريخ صدور التعميم هجري": """\
- "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
  it exactly as written (day, month name or number, year), do not convert
  to Gregorian, do not reformat.""",
    "موضوع التعميم": """\
- "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
  for - it is NEVER just the generic document-type word "تعميم" written at
  the top of the page as a title. Ignore that title word completely.
- Look at the main body paragraph(s) of the circular (usually starting with
  something like "يهدي..." or "بالإشارة إلى..." or after an explicit
  "الموضوع:" label) and extract the actual subject being communicated.
- If there is an explicit "الموضوع:" label, prefer that exact text. If not,
  summarize the core subject using wording taken directly from the body
  text (do not invent new wording).
- Any reference number mentioned inside this subject text (e.g. a decision
  or letter number referenced in parentheses) must be copied digit-by-digit
  exactly as printed - re-check it carefully, these numbers are easy to
  misread.""",
    "جهة التعميم": """\
- "جهة التعميم" is the department/entity that issued the circular - usually
  in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
  or near the signature block at the bottom.""",
    "موجه الي": """\
- "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
  "مدراء الإدارات"), usually appears near the top after "إلى:" or
  "الموجه إلى:". Copy the full recipient phrase.""",
    "نسخة الي": """\
- "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
  near the bottom or right after the main addressee.""",
    # ---------------- فواتير عربي ----------------
    "رقم الفاتوره": """\
- "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
  number (typically 4-7 digits, e.g. "99911"), and it appears right after
  the word "رقم" (often written "رقم /" or "رقم:") near the top.
- Do NOT confuse it with the commercial registration number or tax/VAT
  number, which is a LONG number (usually 10+ digits) printed inside
  square brackets "[ ]" or near the company letterhead.
- If you see two different numbers near the top, pick the SHORT one that
  directly follows the label "رقم" - not the long registration/tax number.""",
    "رقم الفاتورة": """\
- "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
  number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
  near the top of the document.
- Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
    "الاسم": """\
- "الاسم" here means the customer/client name, usually appearing after
  "السادة", "السادة/", or "السادة:" near the top of the invoice.
- Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
  NOT part of the customer's name.""",
    "اسم المشتري": """\
- "اسم المشتري" means the customer/client name, usually after "السادة" or
  "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
    "المجموع": """\
- "المجموع" is the subtotal before VAT/discount - usually a line item near
  the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
  final grand total) and "القيمة المضافة" (the VAT amount).""",
    "الخصم": """\
- "الخصم" is the discount amount. If the document shows "0.00" or "-" next
  to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
    "القيمة المضافة": """\
- "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
  followed by a percentage like "15%"), found near the totals section.""",
    "اجمالي الفاتوره": """\
- "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
  after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
  or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
    "اجمالي قيمة الفاتوره": """\
- "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
  and after discount. Sanity check: should equal subtotal - discount + VAT.""",
    # ---------------- فواتير إنجليزي ----------------
    "Customer Name": """\
- "Customer Name" means the company or person receiving the invoice. It may
  appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
  Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
    "Supplier Name": """\
- "Supplier Name" means the company issuing the invoice. It may appear after:
  Vendor, Supplier, Seller, From, شركة, المورد.""",
    "Invoice Number": """\
- "Invoice Number" must be the official invoice identifier. Do not use PO
  Number, Order Number, Quote Number or Customer Number.""",
    "Total Amount with VAT": """\
- "Total Amount with VAT" must be the FINAL payable amount including VAT.
  Do not return the subtotal unless explicitly requested.""",
    "Items Count": """\
- "Items Count": count the total number of distinct line items/products
  listed. Return only the integer count.""",
    "Item List": """\
- "Item List": return an array containing only the product/service names in
  the same order they appear. Do NOT include quantities, prices, or codes.""",
    "اسم الشركة": """\
- "اسم الشركة": if the letterhead shows the company name in both Arabic and
  English, return the ARABIC name - not the English name.""",
}

# سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
_DOC_TYPE_CONTEXT: dict[str, str] = {
    "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
    "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
    "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
    "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
    "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
    "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
    "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
    "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
}


def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
    # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
    clean_fields = [_normalize_field_name(f) for f in fields]
    fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

    # FIX: إضافة سياق نوع المستند للـ prompt
    doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

    prompt = _GENERAL_RULES.format(
        fields_list=fields_list,
        doc_type_context=doc_type_context,
    )

    guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
    if guidance:
        prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

    missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
    if missing:
        logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

    return prompt


def build_raw_text_prompt() -> str:
    """
    برومبت النسخ الحرفي.

    قاعدة حديدية: ممنوع نهائيًا أي نص عربي أو أي مثال ملموس (اسم، تاريخ، رقم
    مرجعي، اسم مدينة) جوه البرومبت ده. الموديل vision صغير، ولما القصاصة تبقى
    شبه فاضية أو صعبة القراءة بيرجّع محتوى البرومبت نفسه كأنه نص المستند.
    كل سطر مهلوس ظهر في النتايج قبل كده كان متكتوب حرفيًا هنا (اسم مدينة،
    "المملكة"، أرقام مرجعية زي ١٣/أ، تاريخ ١٤٤٨/١/٢٦هـ، والاسم اللاتيني
    Salman bin Abdulaziz Al Saud). القاعدة اتحوّلت لاختبار في
    tests/test_prompt_has_no_arabic.py عشان متترجعش تاني بالغلط.
    """
    return textwrap.dedent("""\
        You are a verbatim OCR transcription engine. Transcribe ALL text visible
        in this image, exactly as printed, and output nothing else.

        SCRIPT AND FIDELITY
        1. Never translate and never transliterate. Text printed in Arabic script
           must be output in Arabic script. Text printed in Latin script must be
           output in Latin script. Never write an Arabic name using Latin letters,
           and never write a Latin name using Arabic letters.
        2. Copy every word exactly as printed, including misspellings, unusual
           wording, broken words and odd spacing. Never correct or normalize.
        3. Copy Arabic diacritics only where they are actually printed. Never add
           diacritics to a word that is printed without them.
        4. Copy digits exactly and keep the printed digit system (Arabic-Indic vs
           Western). Never convert calendars and never reformat dates.
        5. Write the digit groups of any date or compound number in the exact
           left-to-right order they appear in the image, even when a different
           order is the one you are used to seeing.
        6. Reference numbers often combine an Arabic letter and digits around a
           slash or a dash. Transcribe the letter as that letter: never turn it
           into a digit and never drop it.
        7. Each number belongs to the label physically next to it. Never move a
           number to a different label because it looks like a better fit.
        8. Arabic headings are often stretched with kashida/tatweel. Read the
           actual letters through the stretching and output the normal unstretched
           word, without dropping any repeated letter.
        9. If a word or region is genuinely unreadable, write [?] in its place.
           Never replace it with a guess.

        THIS IMAGE ONLY - the most important rule
        10. This image may be a small crop of a larger page: a header strip, one
            column, a band of a few lines, or a footer. Transcribe exactly what is
            inside THIS image and nothing else. Do not add lines you expect to be
            above or below the crop.
        11. You may recognize this as a familiar KIND of document. NEVER use that
            familiarity to output any word, name, city, authority, date, number,
            heading, clause or boilerplate line that you cannot actually SEE in
            THIS image.
        12. Never output any text taken from these instructions. These
            instructions are not part of the document.
        13. If this image contains no readable text at all (blank area, a rule,
            a decorative border, a faint background stamp), output nothing at all.
            An empty answer is the correct answer - never fill the silence.

        NO LOOPING
        14. Transcribe each printed line exactly ONCE, then move DOWN to the next
            line. When you reach the last printed line in this image, STOP.
        15. Formal pages repeat very similar lines on purpose, differing only by a
            number or a date. Track which line you are on by its POSITION in the
            image, not by its wording. After writing one, your next output must
            come from the line physically BELOW it. Never restart from an earlier
            line and never continue past the last printed one.
        16. Before finishing, check you have not written the same line twice and
            have not invented extra numbered items. A short transcription of a
            short crop is correct; padding it is not.

        READING ORDER
        17. Normally this is a single column. Read strictly top to bottom, one
            line after another, and transcribe every line you pass.
        18. Arabic lines read right-to-left: each line starts at its RIGHT edge.
        19. Only if the image really contains two side-by-side columns of text:
            transcribe ONE WHOLE COLUMN AT A TIME, the RIGHT-hand one first from
            its top to its bottom, then the one to its left. Never alternate
            between columns line by line and never merge a line from one column
            with a line from another.

        STRUCTURE
        20. Keep the printed line and paragraph breaks.
        21. Keep list markers and numbering exactly as printed, with their own
            characters. Never replace a printed marker with a generic dash, never
            drop it, and never renumber the items.
        22. Tables: one printed row per output line, cells separated by " | ",
            keeping the printed cell order.
        23. Include headers, footers, letterhead lines, reference numbers, dates
            and signature-line names.
        24. Label:value rows: output as "<label>: <value>" - label first, then the
            value. Never reverse the order.
        25. Skip repeated translucent diagonal background watermark overlays and
            faint repeated institution names printed across the page behind the
            text. Everything else in the image is real content.

        STAMPS AND SEALS - never transcribe
        26. Do NOT transcribe any text that belongs to a stamp or a seal: round
            or oval ink stamps, bordered rectangular stamps, embossed or dry
            seals, text that curves along the edge of a circle, and text
            printed at an angle across other text.
        27. Do NOT transcribe handwritten signatures, handwritten initials,
            QR codes or barcodes.
        28. A stamp usually sits on top of the printed text. Transcribe the
            printed text underneath it and ignore the stamp's own wording
            completely. Never merge a word from a stamp into a printed line.

        Output ONLY the transcription: no commentary, no explanations, no markdown.""")


# ─────────────────────────────────────────────────────────────────────────────
# حارس: أي حرف عربي جوه برومبت النسخ الحرفي = مصدر هلوسة محتمل.
# الموديل بيرجّع محتوى البرومبت لما القصاصة تبقى صعبة/فاضية، فأي مثال ملموس
# (اسم/تاريخ/رقم مرجعي/اسم مدينة) بيتحوّل لسطر مزيف في نص المستند.
# ─────────────────────────────────────────────────────────────────────────────
_ARABIC_RANGE_RE = re.compile(r"[\u0600-\u06FF]")


def assert_raw_prompt_is_ascii_only() -> None:
    """بيترمي AssertionError لو حد رجّع مثال عربي لبرومبت النسخ الحرفي."""
    offenders = sorted(set(_ARABIC_RANGE_RE.findall(build_raw_text_prompt())))
    assert not offenders, (
        "برومبت النسخ الحرفي فيه حروف عربية - ده بيرجع في النص كهلوسة: "
        + "".join(offenders)
    )


assert_raw_prompt_is_ascii_only()










# from __future__ import annotations

# import logging
# import re
# import textwrap

# logger = logging.getLogger(__name__)

# # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# def _normalize_field_name(name: str) -> str:
#     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
#     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# _GENERAL_RULES = """\
# You are an expert OCR and document information extraction system specialized in
# Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# commercial documents (invoices, receipts, quotations).
# {doc_type_context}
# Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# footers, stamps, logo areas) and extract ONLY these fields:
# {fields_list}

# OUTPUT FORMAT
# 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
#    fences, no comments, no explanations, no text before or after it.
# 2. Use EXACTLY the requested field names as JSON keys, character for
#    character, in the same order they were given.
# 3. Never invent extra fields. If a value is missing or unreadable with high
#    confidence, return null - never guess.

# TEXT FIDELITY
# 4. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
#    confuse. Verify each letter against the image instead of auto-completing
#    to the most common/expected name (e.g. do not turn "بريدة" into "بردة" or
#    vice versa just because one is more familiar).
   
# 5. Copy the original text exactly (Arabic stays Arabic, English stays
#    English - never translate, paraphrase, or "correct" wording). If a
#    printed word looks unusual or misspelled, copy it as printed anyway - do
#    not substitute it with a different, more "expected" word. Do NOT add
#    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
#    in the image, even for well-known phrases like country/ministry names -
#    if the source text has no diacritics, your output must have none either.
# 6. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
#    confuse. Verify each letter against the image instead of auto-completing
#    to the most common/expected name.
# 7. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
#    digit form as printed, keep commas/decimal separators/currency symbols as
#    printed. Any reference/tracking number written inside parentheses or
#    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
#    digit-by-digit against the image before being used - these are the
#    numbers most often misread.
# 8. Fields containing "تاريخ"/"Date": copy exactly as printed, including
#    هـ/م markers, in the original order/separators. Never convert calendars
#    or reformat.

# LAYOUT
# 9. Ignore watermarks, background stamps, or repeated translucent/diagonal
#    overlay text that is not real document content (e.g. "Demonstration
#    License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# 10. Bilingual headers/letterheads often print the SAME info twice - once in
#    English, once in Arabic (side by side or stacked, sometimes next to a
#    logo). Treat them as two separate text blocks and read both fully; small
#    Arabic text next to a logo is real text, not decoration.
# 11. When a requested field's NAME is written in Arabic and the document
#     shows that information in both Arabic and English, return the ARABIC
#     version by default (unless the field name is itself in English, in
#     which case return the English version).
# 12. Tables: first read the header row fully (both languages if bilingual)
#     to establish the real left-to-right column order as printed on THIS
#     document. Then map each number in a row to its column strictly by its
#     printed position - never assume a "typical" order.
# 13. If a field's value wraps across multiple printed lines, join it into
#     ONE continuous value with single spaces between words - no merged
#     words, no leftover line breaks, no double spaces.

# Before answering, double-check every value against the image (nothing
# guessed, nothing skipped because it was small/faint/next to a logo/stamp).
# Return ONLY the JSON object."""

# _FIELD_GUIDANCE: dict[str, str] = {
#     # ---------------- تكليف ----------------
#     "رقم التكليف": """\
# - "رقم التكليف" is the official assignment/tasking number, usually near the
#   top of the document, often preceded by "رقم" or written in a reference box.""",
#     "تاريخ التكليف": """\
# - "تاريخ التكليف" is the date the assignment document itself was issued
#   (not the start/end dates of the assignment period).""",
#     "اسم المكلف": """\
# - "اسم المكلف" is the full name of the person being assigned/tasked. It
#   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
#     "تاريخ بداية التكليف": """\
# - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
#   confuse it with the issue date of the document.""",
#     "تاريخ نهاية التكليف": """\
# - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
#     "الموضوع": """\
# - "الموضوع" is the subject/topic stated in the document, usually appearing
#   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
#     "صادر من": """\
# - "صادر من" is the name/title of the person or authority who issued the
#   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
#   near a signature block at the bottom.""",
#     # ---------------- قرار ----------------
#     "رقم القرار": """\
# - "رقم القرار" is the official decision number, usually near the top or in a
#   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
#     "تاريخ القرار": """\
# - "تاريخ القرار" is the date the decision was issued/signed.""",
#     "موضوع القرار": """\
# - "موضوع القرار" is the subject/title line summarizing what the decision is
#   about, usually right under the decision number/date or after "الموضوع:".""",
#     "الجهة المصدرة": """\
# - "الجهة المصدرة" is the entity/department/authority that issued the
#   decision, often in letterhead at the top or near the signature at the
#   bottom.""",
#     # ---------------- تعميم ----------------
#     "تاريخ صدور التعميم هجري": """\
# - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
#   it exactly as written (day, month name or number, year), do not convert
#   to Gregorian, do not reformat.""",
#     "موضوع التعميم": """\
# - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
#   for - it is NEVER just the generic document-type word "تعميم" written at
#   the top of the page as a title. Ignore that title word completely.
# - Look at the main body paragraph(s) of the circular (usually starting with
#   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
#   "الموضوع:" label) and extract the actual subject being communicated.
# - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
#   summarize the core subject using wording taken directly from the body
#   text (do not invent new wording).
# - Any reference number mentioned inside this subject text (e.g. a decision
#   or letter number referenced in parentheses) must be copied digit-by-digit
#   exactly as printed - re-check it carefully, these numbers are easy to
#   misread.""",
#     "جهة التعميم": """\
# - "جهة التعميم" is the department/entity that issued the circular - usually
#   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
#   or near the signature block at the bottom.""",
#     "موجه الي": """\
# - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
#   "مدراء الإدارات"), usually appears near the top after "إلى:" or
#   "الموجه إلى:". Copy the full recipient phrase.""",
#     "نسخة الي": """\
# - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
#   near the bottom or right after the main addressee.""",
#     # ---------------- فواتير عربي ----------------
#     "رقم الفاتوره": """\
# - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits, e.g. "99911"), and it appears right after
#   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# - Do NOT confuse it with the commercial registration number or tax/VAT
#   number, which is a LONG number (usually 10+ digits) printed inside
#   square brackets "[ ]" or near the company letterhead.
# - If you see two different numbers near the top, pick the SHORT one that
#   directly follows the label "رقم" - not the long registration/tax number.""",
#     "رقم الفاتورة": """\
# - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
#   near the top of the document.
# - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
#     "الاسم": """\
# - "الاسم" here means the customer/client name, usually appearing after
#   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
#   NOT part of the customer's name.""",
#     "اسم المشتري": """\
# - "اسم المشتري" means the customer/client name, usually after "السادة" or
#   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
#     "المجموع": """\
# - "المجموع" is the subtotal before VAT/discount - usually a line item near
#   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
#   final grand total) and "القيمة المضافة" (the VAT amount).""",
#     "الخصم": """\
# - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
#   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
#     "القيمة المضافة": """\
# - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
#   followed by a percentage like "15%"), found near the totals section.""",
#     "اجمالي الفاتوره": """\
# - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
#   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
#   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
#     "اجمالي قيمة الفاتوره": """\
# - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
#   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
#     # ---------------- فواتير إنجليزي ----------------
#     "Customer Name": """\
# - "Customer Name" means the company or person receiving the invoice. It may
#   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
#   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
#     "Supplier Name": """\
# - "Supplier Name" means the company issuing the invoice. It may appear after:
#   Vendor, Supplier, Seller, From, شركة, المورد.""",
#     "Invoice Number": """\
# - "Invoice Number" must be the official invoice identifier. Do not use PO
#   Number, Order Number, Quote Number or Customer Number.""",
#     "Total Amount with VAT": """\
# - "Total Amount with VAT" must be the FINAL payable amount including VAT.
#   Do not return the subtotal unless explicitly requested.""",
#     "Items Count": """\
# - "Items Count": count the total number of distinct line items/products
#   listed. Return only the integer count.""",
#     "Item List": """\
# - "Item List": return an array containing only the product/service names in
#   the same order they appear. Do NOT include quantities, prices, or codes.""",
#     "اسم الشركة": """\
# - "اسم الشركة": if the letterhead shows the company name in both Arabic and
#   English, return the ARABIC name - not the English name.""",
# }

# # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# _DOC_TYPE_CONTEXT: dict[str, str] = {
#     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
#     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
#     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
#     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
#     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
#     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
#     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
#     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# }


# def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
#     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
#     clean_fields = [_normalize_field_name(f) for f in fields]
#     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

#     # FIX: إضافة سياق نوع المستند للـ prompt
#     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

#     prompt = _GENERAL_RULES.format(
#         fields_list=fields_list,
#         doc_type_context=doc_type_context,
#     )

#     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
#     if guidance:
#         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

#     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
#     if missing:
#         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

#     return prompt


# def build_raw_text_prompt() -> str:
#     return textwrap.dedent("""\
#         You are an expert OCR system specialized in verbatim, lossless text
#         extraction from document images, including documents that mix Arabic and
#         English in the same header/letterhead, and documents with numeric tables.

#         Your ONLY task is to output ALL real document text exactly as printed,
#         nothing changed, nothing skipped.

#         CRITICAL - NO INVENTED CONTENT: You may recognize this as a type of
#         document you have seen many examples of before. NEVER use that prior
#         knowledge to add ANY word, name, phrase, sentence, or boilerplate line
#         that is not ACTUALLY visible in THIS specific image. Only output such
#         a greeting if you can actually see it printed at the top of THIS image.

#         STRICT RULES

#         1. Copy every word/character EXACTLY as printed. Do not fix spelling or
#            grammar. Do NOT add Arabic diacritics/tashkeel that are not actually
#            printed in the image.

#         2. Do NOT translate anything. Arabic stays Arabic, English stays English.

#         3. IGNORE watermarks, background stamps, and repeated translucent/diagonal
#            overlay text (e.g. "Demonstration License", "SAMPLE", "DRAFT", "COPY").
#            Also IGNORE handwritten marginal annotations.

#         4. Numbers: copy digits exactly (keep Arabic-Indic vs Western digit form as
#            printed). Any number inside parentheses/brackets, and every number inside
#            a table, must be re-verified digit-by-digit.

#         5. Tables: transcribe row by row, keeping every number in the SAME column
#            position as printed - separate cells with " | ".

#         6. Bilingual headers: transcribe the English block in full, then "---",
#            then the Arabic block in full.

#         7. Two-column label:value rows: output as "<label>: <value>" — label first,
#            then colon, then value. Never reverse the order.

#         8. Keep paragraphs complete. Include headers, footers, titles, stamps,
#            signature text, and footnotes.

#         9. Read the ENTIRE image before answering - skip nothing.

#         10. No comments, no explanations, no markdown - output only the transcribed text.

#         Return ONLY the raw extracted text.""")


# def build_number_focus_prompt() -> str:
#     return textwrap.dedent("""\
#         You are a meticulous OCR system with ONE job: find every number that is
#         written INSIDE parentheses "( )" or square brackets "[ ]" anywhere on this
#         page, and copy each one out digit-by-digit, exactly as printed.

#         RULES:
#         - Scan the ENTIRE page top to bottom, left to right.
#         - Copy ONLY the digits inside the parentheses/brackets.
#         - Keep the exact digit form as printed (Arabic-Indic or Western).
#         - Before writing each number down, read it twice and count the digits.
#         - Output ONLY one number per line, in the exact order they appear.
#         - If there are no such numbers on the page, output nothing.""")



# from __future__ import annotations

# import logging
# import re
# import textwrap

# logger = logging.getLogger(__name__)

# # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# def _normalize_field_name(name: str) -> str:
#     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
#     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# _GENERAL_RULES = """\
# You are an expert OCR and document information extraction system specialized in
# Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# commercial documents (invoices, receipts, quotations).
# {doc_type_context}
# Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# footers, stamps, logo areas) and extract ONLY these fields:
# {fields_list}

# OUTPUT FORMAT
# 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
#    fences, no comments, no explanations, no text before or after it.
# 2. Use EXACTLY the requested field names as JSON keys, character for
#    character, in the same order they were given.
# 3. Never invent extra fields.

# MISSING VALUES - read this before answering
# 4. This document may simply not contain some of the requested fields. That is
#    normal and expected. If a field's value is not printed on this page, return
#    null for it. Returning null is the CORRECT answer - it is never penalized.
# 5. Never fill a field by borrowing a different value from elsewhere on the
#    page. A date that is not the requested date, or a number that belongs to a
#    different label, is WRONG - more wrong than null. Do not reason about what
#    the value "should" or "would typically" be: if you cannot point at the exact
#    printed characters for that specific field, the answer is null.

# TEXT FIDELITY
# 6. Copy the original text exactly (Arabic stays Arabic, English stays
#    English - never translate, transliterate, paraphrase, or "correct" wording).
#    If a printed word looks unusual or misspelled, copy it as printed anyway -
#    do not substitute it with a different, more "expected" word. Do NOT add
#    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
#    in the image, even for well-known phrases like country/ministry names -
#    if the source text has no diacritics, your output must have none either.
# 7. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: several Arabic letters differ only by the number or position of
#    their dots, and are easy to confuse. Verify each letter against the image
#    instead of auto-completing to the most common or most familiar name.
#    Never replace a printed name with a better-known name that looks similar.
# 8. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
#    digit form as printed, keep commas/decimal separators/currency symbols as
#    printed. Any reference/tracking number written inside parentheses or
#    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
#    digit-by-digit against the image before being used - these are the
#    numbers most often misread.
# 9. Date fields: copy exactly as printed, including any Hijri/Gregorian era
#    marker, in the original order and with the original separators. Never
#    convert calendars and never reformat. Keep every digit group in the exact
#    left-to-right order shown in the image, even if another order is more
#    familiar to you. Reference numbers that mix an Arabic letter with digits
#    around a slash keep that letter as a letter - never turn it into a digit
#    and never drop it.

# LAYOUT
# 10. Arabic pages read RIGHT to LEFT. If the page is split into vertical
#     columns, read the entire RIGHT column top-to-bottom first, then the next
#     column to its left - never alternate between columns line by line.
# 11. Ignore watermarks, background stamps, or repeated translucent/diagonal
#     overlay text that is not real document content (e.g. "Demonstration
#     License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# 12. Bilingual headers/letterheads often print the SAME info twice - once in
#     English, once in Arabic (side by side or stacked, sometimes next to a
#     logo). Treat them as two separate text blocks and read both fully; small
#     Arabic text next to a logo is real text, not decoration.
# 13. When a requested field's NAME is written in Arabic and the document
#     shows that information in both Arabic and English, return the ARABIC
#     version by default (unless the field name is itself in English, in
#     which case return the English version).
# 14. Tables: first read the header row fully (both languages if bilingual)
#     to establish the real column order as printed on THIS document. Then map
#     each number in a row to its column strictly by its printed position -
#     never assume a "typical" order.
# 15. If a field's value wraps across multiple printed lines, join it into
#     ONE continuous value with single spaces between words - no merged
#     words, no leftover line breaks, no double spaces.

# Before answering, check every non-null value one more time: can you point at
# the exact printed characters for it on THIS page, next to THAT field's own
# label? If not, change it to null. Return ONLY the JSON object."""

# _FIELD_GUIDANCE: dict[str, str] = {
#     # ---------------- تكليف ----------------
#     "رقم التكليف": """\
# - "رقم التكليف" is the official assignment/tasking number, usually near the
#   top of the document, often preceded by "رقم" or written in a reference box.""",
#     "تاريخ التكليف": """\
# - "تاريخ التكليف" is the date the assignment document itself was issued
#   (not the start/end dates of the assignment period).""",
#     "اسم المكلف": """\
# - "اسم المكلف" is the full name of the person being assigned/tasked. It
#   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
#     "تاريخ بداية التكليف": """\
# - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
#   confuse it with the issue date of the document.""",
#     "تاريخ نهاية التكليف": """\
# - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
#     "الموضوع": """\
# - "الموضوع" is the subject/topic stated in the document, usually appearing
#   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
#     "صادر من": """\
# - "صادر من" is the name/title of the person or authority who issued the
#   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
#   near a signature block at the bottom.""",
#     # ---------------- قرار ----------------
#     "رقم القرار": """\
# - "رقم القرار" is the official decision number, usually near the top or in a
#   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
#     "تاريخ القرار": """\
# - "تاريخ القرار" is the date the decision was issued/signed.""",
#     "موضوع القرار": """\
# - "موضوع القرار" is the subject/title line summarizing what the decision is
#   about, usually right under the decision number/date or after "الموضوع:".""",
#     "الجهة المصدرة": """\
# - "الجهة المصدرة" is the entity/department/authority that issued the
#   decision, often in letterhead at the top or near the signature at the
#   bottom.""",
#     # ---------------- تعميم ----------------
#     "تاريخ صدور التعميم هجري": """\
# - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
#   it exactly as written (day, month name or number, year), do not convert
#   to Gregorian, do not reformat.""",
#     "موضوع التعميم": """\
# - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
#   for - it is NEVER just the generic document-type word "تعميم" written at
#   the top of the page as a title. Ignore that title word completely.
# - Look at the main body paragraph(s) of the circular (usually starting with
#   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
#   "الموضوع:" label) and extract the actual subject being communicated.
# - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
#   summarize the core subject using wording taken directly from the body
#   text (do not invent new wording).
# - Any reference number mentioned inside this subject text (e.g. a decision
#   or letter number referenced in parentheses) must be copied digit-by-digit
#   exactly as printed - re-check it carefully, these numbers are easy to
#   misread.""",
#     "جهة التعميم": """\
# - "جهة التعميم" is the department/entity that issued the circular - usually
#   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
#   or near the signature block at the bottom.""",
#     "موجه الي": """\
# - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
#   "مدراء الإدارات"), usually appears near the top after "إلى:" or
#   "الموجه إلى:". Copy the full recipient phrase.""",
#     "نسخة الي": """\
# - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
#   near the bottom or right after the main addressee.""",
#     # ---------------- فواتير عربي ----------------
#     "رقم الفاتوره": """\
# - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits, e.g. "99911"), and it appears right after
#   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# - Do NOT confuse it with the commercial registration number or tax/VAT
#   number, which is a LONG number (usually 10+ digits) printed inside
#   square brackets "[ ]" or near the company letterhead.
# - If you see two different numbers near the top, pick the SHORT one that
#   directly follows the label "رقم" - not the long registration/tax number.""",
#     "رقم الفاتورة": """\
# - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
#   near the top of the document.
# - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
#     "الاسم": """\
# - "الاسم" here means the customer/client name, usually appearing after
#   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
#   NOT part of the customer's name.""",
#     "اسم المشتري": """\
# - "اسم المشتري" means the customer/client name, usually after "السادة" or
#   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
#     "المجموع": """\
# - "المجموع" is the subtotal before VAT/discount - usually a line item near
#   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
#   final grand total) and "القيمة المضافة" (the VAT amount).""",
#     "الخصم": """\
# - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
#   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
#     "القيمة المضافة": """\
# - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
#   followed by a percentage like "15%"), found near the totals section.""",
#     "اجمالي الفاتوره": """\
# - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
#   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
#   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
#     "اجمالي قيمة الفاتوره": """\
# - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
#   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
#     # ---------------- فواتير إنجليزي ----------------
#     "Customer Name": """\
# - "Customer Name" means the company or person receiving the invoice. It may
#   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
#   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
#     "Supplier Name": """\
# - "Supplier Name" means the company issuing the invoice. It may appear after:
#   Vendor, Supplier, Seller, From, شركة, المورد.""",
#     "Invoice Number": """\
# - "Invoice Number" must be the official invoice identifier. Do not use PO
#   Number, Order Number, Quote Number or Customer Number.""",
#     "Total Amount with VAT": """\
# - "Total Amount with VAT" must be the FINAL payable amount including VAT.
#   Do not return the subtotal unless explicitly requested.""",
#     "Items Count": """\
# - "Items Count": count the total number of distinct line items/products
#   listed. Return only the integer count.""",
#     "Item List": """\
# - "Item List": return an array containing only the product/service names in
#   the same order they appear. Do NOT include quantities, prices, or codes.""",
#     "اسم الشركة": """\
# - "اسم الشركة": if the letterhead shows the company name in both Arabic and
#   English, return the ARABIC name - not the English name.""",
# }

# # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# _DOC_TYPE_CONTEXT: dict[str, str] = {
#     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
#     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
#     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
#     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
#     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
#     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
#     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
#     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# }


# def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
#     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
#     clean_fields = [_normalize_field_name(f) for f in fields]
#     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

#     # FIX: إضافة سياق نوع المستند للـ prompt
#     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

#     prompt = _GENERAL_RULES.format(
#         fields_list=fields_list,
#         doc_type_context=doc_type_context,
#     )

#     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
#     if guidance:
#         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

#     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
#     if missing:
#         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

#     return prompt


# def build_raw_text_prompt() -> str:
#     """
#     برومبت النسخ الحرفي.

#     قاعدة حديدية: ممنوع نهائيًا أي نص عربي أو أي مثال ملموس (اسم، تاريخ، رقم
#     مرجعي، اسم مدينة) جوه البرومبت ده. الموديل vision صغير، ولما القصاصة تبقى
#     شبه فاضية أو صعبة القراءة بيرجّع محتوى البرومبت نفسه كأنه نص المستند.
#     كل سطر مهلوس ظهر في النتايج قبل كده كان متكتوب حرفيًا هنا (اسم مدينة،
#     "المملكة"، أرقام مرجعية زي ١٣/أ، تاريخ ١٤٤٨/١/٢٦هـ، والاسم اللاتيني
#     Salman bin Abdulaziz Al Saud). القاعدة اتحوّلت لاختبار في
#     tests/test_prompt_has_no_arabic.py عشان متترجعش تاني بالغلط.
#     """
#     return textwrap.dedent("""\
#         You are a verbatim OCR transcription engine. Transcribe ALL text visible
#         in this image, exactly as printed, and output nothing else.

#         SCRIPT AND FIDELITY
#         1. Never translate and never transliterate. Text printed in Arabic script
#            must be output in Arabic script. Text printed in Latin script must be
#            output in Latin script. Never write an Arabic name using Latin letters,
#            and never write a Latin name using Arabic letters.
#         2. Copy every word exactly as printed, including misspellings, unusual
#            wording, broken words and odd spacing. Never correct or normalize.
#         3. Copy Arabic diacritics only where they are actually printed. Never add
#            diacritics to a word that is printed without them.
#         4. Copy digits exactly and keep the printed digit system (Arabic-Indic vs
#            Western). Never convert calendars and never reformat dates.
#         5. Write the digit groups of any date or compound number in the exact
#            left-to-right order they appear in the image, even when a different
#            order is the one you are used to seeing.
#         6. Reference numbers often combine an Arabic letter and digits around a
#            slash or a dash. Transcribe the letter as that letter: never turn it
#            into a digit and never drop it.
#         7. Each number belongs to the label physically next to it. Never move a
#            number to a different label because it looks like a better fit.
#         8. Arabic headings are often stretched with kashida/tatweel. Read the
#            actual letters through the stretching and output the normal unstretched
#            word, without dropping any repeated letter.
#         9. If a word or region is genuinely unreadable, write [?] in its place.
#            Never replace it with a guess.

#         THIS IMAGE ONLY - the most important rule
#         10. This image may be a small crop of a larger page: a header strip, one
#             column, a band of a few lines, or a footer. Transcribe exactly what is
#             inside THIS image and nothing else. Do not add lines you expect to be
#             above or below the crop.
#         11. You may recognize this as a familiar KIND of document. NEVER use that
#             familiarity to output any word, name, city, authority, date, number,
#             heading, clause or boilerplate line that you cannot actually SEE in
#             THIS image.
#         12. Never output any text taken from these instructions. These
#             instructions are not part of the document.
#         13. If this image contains no readable text at all (blank area, a rule,
#             a decorative border, a faint background stamp), output nothing at all.
#             An empty answer is the correct answer - never fill the silence.

#         NO LOOPING
#         14. Transcribe each printed line exactly ONCE, then move DOWN to the next
#             line. When you reach the last printed line in this image, STOP.
#         15. Formal pages repeat very similar lines on purpose, differing only by a
#             number or a date. Track which line you are on by its POSITION in the
#             image, not by its wording. After writing one, your next output must
#             come from the line physically BELOW it. Never restart from an earlier
#             line and never continue past the last printed one.
#         16. Before finishing, check you have not written the same line twice and
#             have not invented extra numbered items. A short transcription of a
#             short crop is correct; padding it is not.

#         READING ORDER
#         17. Normally this is a single column. Read strictly top to bottom, one
#             line after another, and transcribe every line you pass.
#         18. Arabic lines read right-to-left: each line starts at its RIGHT edge.
#         19. Only if the image really contains two side-by-side columns of text:
#             transcribe ONE WHOLE COLUMN AT A TIME, the RIGHT-hand one first from
#             its top to its bottom, then the one to its left. Never alternate
#             between columns line by line and never merge a line from one column
#             with a line from another.

#         STRUCTURE
#         20. Keep the printed line and paragraph breaks.
#         21. Keep list markers and numbering exactly as printed, with their own
#             characters. Never replace a printed marker with a generic dash, never
#             drop it, and never renumber the items.
#         22. Tables: one printed row per output line, cells separated by " | ",
#             keeping the printed cell order.
#         23. Include headers, footers, letterhead lines, reference numbers, dates
#             and signature-line names.
#         24. Label:value rows: output as "<label>: <value>" - label first, then the
#             value. Never reverse the order.
#         25. Skip repeated translucent diagonal background watermark overlays and
#             faint repeated institution names printed across the page behind the
#             text. Everything else in the image is real content.

#         STAMPS AND SEALS - never transcribe
#         26. Do NOT transcribe any text that belongs to a stamp or a seal: round
#             or oval ink stamps, bordered rectangular stamps, embossed or dry
#             seals, text that curves along the edge of a circle, and text
#             printed at an angle across other text.
#         27. Do NOT transcribe handwritten signatures, handwritten initials,
#             QR codes or barcodes.
#         28. A stamp usually sits on top of the printed text. Transcribe the
#             printed text underneath it and ignore the stamp's own wording
#             completely. Never merge a word from a stamp into a printed line.

#         Output ONLY the transcription: no commentary, no explanations, no markdown.""")


# # ─────────────────────────────────────────────────────────────────────────────
# # حارس: أي حرف عربي جوه برومبت النسخ الحرفي = مصدر هلوسة محتمل.
# # الموديل بيرجّع محتوى البرومبت لما القصاصة تبقى صعبة/فاضية، فأي مثال ملموس
# # (اسم/تاريخ/رقم مرجعي/اسم مدينة) بيتحوّل لسطر مزيف في نص المستند.
# # ─────────────────────────────────────────────────────────────────────────────
# _ARABIC_RANGE_RE = re.compile(r"[\u0600-\u06FF]")


# def assert_raw_prompt_is_ascii_only() -> None:
#     """بيترمي AssertionError لو حد رجّع مثال عربي لبرومبت النسخ الحرفي."""
#     offenders = sorted(set(_ARABIC_RANGE_RE.findall(build_raw_text_prompt())))
#     assert not offenders, (
#         "برومبت النسخ الحرفي فيه حروف عربية - ده بيرجع في النص كهلوسة: "
#         + "".join(offenders)
#     )


# assert_raw_prompt_is_ascii_only()










# # from __future__ import annotations

# # import logging
# # import re
# # import textwrap

# # logger = logging.getLogger(__name__)

# # # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# # _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# # def _normalize_field_name(name: str) -> str:
# #     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
# #     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# # _GENERAL_RULES = """\
# # You are an expert OCR and document information extraction system specialized in
# # Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# # commercial documents (invoices, receipts, quotations).
# # {doc_type_context}
# # Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# # footers, stamps, logo areas) and extract ONLY these fields:
# # {fields_list}

# # OUTPUT FORMAT
# # 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
# #    fences, no comments, no explanations, no text before or after it.
# # 2. Use EXACTLY the requested field names as JSON keys, character for
# #    character, in the same order they were given.
# # 3. Never invent extra fields. If a value is missing or unreadable with high
# #    confidence, return null - never guess.

# # TEXT FIDELITY
# # 4. Proper nouns (place names, personal names) need extra letter-by-letter
# #    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
# #    confuse. Verify each letter against the image instead of auto-completing
# #    to the most common/expected name (e.g. do not turn "بريدة" into "بردة" or
# #    vice versa just because one is more familiar).
   
# # 5. Copy the original text exactly (Arabic stays Arabic, English stays
# #    English - never translate, paraphrase, or "correct" wording). If a
# #    printed word looks unusual or misspelled, copy it as printed anyway - do
# #    not substitute it with a different, more "expected" word. Do NOT add
# #    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
# #    in the image, even for well-known phrases like country/ministry names -
# #    if the source text has no diacritics, your output must have none either.
# # 6. Proper nouns (place names, personal names) need extra letter-by-letter
# #    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
# #    confuse. Verify each letter against the image instead of auto-completing
# #    to the most common/expected name.
# # 7. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
# #    digit form as printed, keep commas/decimal separators/currency symbols as
# #    printed. Any reference/tracking number written inside parentheses or
# #    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
# #    digit-by-digit against the image before being used - these are the
# #    numbers most often misread.
# # 8. Fields containing "تاريخ"/"Date": copy exactly as printed, including
# #    هـ/م markers, in the original order/separators. Never convert calendars
# #    or reformat.

# # LAYOUT
# # 9. Ignore watermarks, background stamps, or repeated translucent/diagonal
# #    overlay text that is not real document content (e.g. "Demonstration
# #    License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# # 10. Bilingual headers/letterheads often print the SAME info twice - once in
# #    English, once in Arabic (side by side or stacked, sometimes next to a
# #    logo). Treat them as two separate text blocks and read both fully; small
# #    Arabic text next to a logo is real text, not decoration.
# # 11. When a requested field's NAME is written in Arabic and the document
# #     shows that information in both Arabic and English, return the ARABIC
# #     version by default (unless the field name is itself in English, in
# #     which case return the English version).
# # 12. Tables: first read the header row fully (both languages if bilingual)
# #     to establish the real left-to-right column order as printed on THIS
# #     document. Then map each number in a row to its column strictly by its
# #     printed position - never assume a "typical" order.
# # 13. If a field's value wraps across multiple printed lines, join it into
# #     ONE continuous value with single spaces between words - no merged
# #     words, no leftover line breaks, no double spaces.

# # Before answering, double-check every value against the image (nothing
# # guessed, nothing skipped because it was small/faint/next to a logo/stamp).
# # Return ONLY the JSON object."""

# # _FIELD_GUIDANCE: dict[str, str] = {
# #     # ---------------- تكليف ----------------
# #     "رقم التكليف": """\
# # - "رقم التكليف" is the official assignment/tasking number, usually near the
# #   top of the document, often preceded by "رقم" or written in a reference box.""",
# #     "تاريخ التكليف": """\
# # - "تاريخ التكليف" is the date the assignment document itself was issued
# #   (not the start/end dates of the assignment period).""",
# #     "اسم المكلف": """\
# # - "اسم المكلف" is the full name of the person being assigned/tasked. It
# #   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
# #     "تاريخ بداية التكليف": """\
# # - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
# #   confuse it with the issue date of the document.""",
# #     "تاريخ نهاية التكليف": """\
# # - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
# #     "الموضوع": """\
# # - "الموضوع" is the subject/topic stated in the document, usually appearing
# #   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
# #     "صادر من": """\
# # - "صادر من" is the name/title of the person or authority who issued the
# #   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
# #   near a signature block at the bottom.""",
# #     # ---------------- قرار ----------------
# #     "رقم القرار": """\
# # - "رقم القرار" is the official decision number, usually near the top or in a
# #   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
# #     "تاريخ القرار": """\
# # - "تاريخ القرار" is the date the decision was issued/signed.""",
# #     "موضوع القرار": """\
# # - "موضوع القرار" is the subject/title line summarizing what the decision is
# #   about, usually right under the decision number/date or after "الموضوع:".""",
# #     "الجهة المصدرة": """\
# # - "الجهة المصدرة" is the entity/department/authority that issued the
# #   decision, often in letterhead at the top or near the signature at the
# #   bottom.""",
# #     # ---------------- تعميم ----------------
# #     "تاريخ صدور التعميم هجري": """\
# # - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
# #   it exactly as written (day, month name or number, year), do not convert
# #   to Gregorian, do not reformat.""",
# #     "موضوع التعميم": """\
# # - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
# #   for - it is NEVER just the generic document-type word "تعميم" written at
# #   the top of the page as a title. Ignore that title word completely.
# # - Look at the main body paragraph(s) of the circular (usually starting with
# #   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
# #   "الموضوع:" label) and extract the actual subject being communicated.
# # - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
# #   summarize the core subject using wording taken directly from the body
# #   text (do not invent new wording).
# # - Any reference number mentioned inside this subject text (e.g. a decision
# #   or letter number referenced in parentheses) must be copied digit-by-digit
# #   exactly as printed - re-check it carefully, these numbers are easy to
# #   misread.""",
# #     "جهة التعميم": """\
# # - "جهة التعميم" is the department/entity that issued the circular - usually
# #   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
# #   or near the signature block at the bottom.""",
# #     "موجه الي": """\
# # - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
# #   "مدراء الإدارات"), usually appears near the top after "إلى:" or
# #   "الموجه إلى:". Copy the full recipient phrase.""",
# #     "نسخة الي": """\
# # - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
# #   near the bottom or right after the main addressee.""",
# #     # ---------------- فواتير عربي ----------------
# #     "رقم الفاتوره": """\
# # - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
# #   number (typically 4-7 digits, e.g. "99911"), and it appears right after
# #   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# # - Do NOT confuse it with the commercial registration number or tax/VAT
# #   number, which is a LONG number (usually 10+ digits) printed inside
# #   square brackets "[ ]" or near the company letterhead.
# # - If you see two different numbers near the top, pick the SHORT one that
# #   directly follows the label "رقم" - not the long registration/tax number.""",
# #     "رقم الفاتورة": """\
# # - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
# #   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
# #   near the top of the document.
# # - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
# #     "الاسم": """\
# # - "الاسم" here means the customer/client name, usually appearing after
# #   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# # - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
# #   NOT part of the customer's name.""",
# #     "اسم المشتري": """\
# # - "اسم المشتري" means the customer/client name, usually after "السادة" or
# #   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
# #     "المجموع": """\
# # - "المجموع" is the subtotal before VAT/discount - usually a line item near
# #   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
# #   final grand total) and "القيمة المضافة" (the VAT amount).""",
# #     "الخصم": """\
# # - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
# #   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
# #     "القيمة المضافة": """\
# # - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
# #   followed by a percentage like "15%"), found near the totals section.""",
# #     "اجمالي الفاتوره": """\
# # - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
# #   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
# #   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
# #     "اجمالي قيمة الفاتوره": """\
# # - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
# #   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
# #     # ---------------- فواتير إنجليزي ----------------
# #     "Customer Name": """\
# # - "Customer Name" means the company or person receiving the invoice. It may
# #   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
# #   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
# #     "Supplier Name": """\
# # - "Supplier Name" means the company issuing the invoice. It may appear after:
# #   Vendor, Supplier, Seller, From, شركة, المورد.""",
# #     "Invoice Number": """\
# # - "Invoice Number" must be the official invoice identifier. Do not use PO
# #   Number, Order Number, Quote Number or Customer Number.""",
# #     "Total Amount with VAT": """\
# # - "Total Amount with VAT" must be the FINAL payable amount including VAT.
# #   Do not return the subtotal unless explicitly requested.""",
# #     "Items Count": """\
# # - "Items Count": count the total number of distinct line items/products
# #   listed. Return only the integer count.""",
# #     "Item List": """\
# # - "Item List": return an array containing only the product/service names in
# #   the same order they appear. Do NOT include quantities, prices, or codes.""",
# #     "اسم الشركة": """\
# # - "اسم الشركة": if the letterhead shows the company name in both Arabic and
# #   English, return the ARABIC name - not the English name.""",
# # }

# # # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# # _DOC_TYPE_CONTEXT: dict[str, str] = {
# #     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
# #     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
# #     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
# #     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
# #     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
# #     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
# #     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
# #     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# # }


# # def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
# #     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
# #     clean_fields = [_normalize_field_name(f) for f in fields]
# #     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

# #     # FIX: إضافة سياق نوع المستند للـ prompt
# #     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

# #     prompt = _GENERAL_RULES.format(
# #         fields_list=fields_list,
# #         doc_type_context=doc_type_context,
# #     )

# #     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
# #     if guidance:
# #         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

# #     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
# #     if missing:
# #         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

# #     return prompt


# # def build_raw_text_prompt() -> str:
# #     return textwrap.dedent("""\
# #         You are an expert OCR system specialized in verbatim, lossless text
# #         extraction from document images, including documents that mix Arabic and
# #         English in the same header/letterhead, and documents with numeric tables.

# #         Your ONLY task is to output ALL real document text exactly as printed,
# #         nothing changed, nothing skipped.

# #         CRITICAL - NO INVENTED CONTENT: You may recognize this as a type of
# #         document you have seen many examples of before. NEVER use that prior
# #         knowledge to add ANY word, name, phrase, sentence, or boilerplate line
# #         that is not ACTUALLY visible in THIS specific image. Only output such
# #         a greeting if you can actually see it printed at the top of THIS image.

# #         STRICT RULES

# #         1. Copy every word/character EXACTLY as printed. Do not fix spelling or
# #            grammar. Do NOT add Arabic diacritics/tashkeel that are not actually
# #            printed in the image.

# #         2. Do NOT translate anything. Arabic stays Arabic, English stays English.

# #         3. IGNORE watermarks, background stamps, and repeated translucent/diagonal
# #            overlay text (e.g. "Demonstration License", "SAMPLE", "DRAFT", "COPY").
# #            Also IGNORE handwritten marginal annotations.

# #         4. Numbers: copy digits exactly (keep Arabic-Indic vs Western digit form as
# #            printed). Any number inside parentheses/brackets, and every number inside
# #            a table, must be re-verified digit-by-digit.

# #         5. Tables: transcribe row by row, keeping every number in the SAME column
# #            position as printed - separate cells with " | ".

# #         6. Bilingual headers: transcribe the English block in full, then "---",
# #            then the Arabic block in full.

# #         7. Two-column label:value rows: output as "<label>: <value>" — label first,
# #            then colon, then value. Never reverse the order.

# #         8. Keep paragraphs complete. Include headers, footers, titles, stamps,
# #            signature text, and footnotes.

# #         9. Read the ENTIRE image before answering - skip nothing.

# #         10. No comments, no explanations, no markdown - output only the transcribed text.

# #         Return ONLY the raw extracted text.""")


# # def build_number_focus_prompt() -> str:
# #     return textwrap.dedent("""\
# #         You are a meticulous OCR system with ONE job: find every number that is
# #         written INSIDE parentheses "( )" or square brackets "[ ]" anywhere on this
# #         page, and copy each one out digit-by-digit, exactly as printed.

# #         RULES:
# #         - Scan the ENTIRE page top to bottom, left to right.
# #         - Copy ONLY the digits inside the parentheses/brackets.
# #         - Keep the exact digit form as printed (Arabic-Indic or Western).
# #         - Before writing each number down, read it twice and count the digits.
# #         - Output ONLY one number per line, in the exact order they appear.
# #         - If there are no such numbers on the page, output nothing.""")






# from __future__ import annotations

# import logging
# import re
# import textwrap

# logger = logging.getLogger(__name__)

# # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# def _normalize_field_name(name: str) -> str:
#     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
#     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# _GENERAL_RULES = """\
# You are an expert OCR and document information extraction system specialized in
# Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# commercial documents (invoices, receipts, quotations).
# {doc_type_context}
# Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# footers, stamps, logo areas) and extract ONLY these fields:
# {fields_list}

# OUTPUT FORMAT
# 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
#    fences, no comments, no explanations, no text before or after it.
# 2. Use EXACTLY the requested field names as JSON keys, character for
#    character, in the same order they were given.
# 3. Never invent extra fields. If a value is missing or unreadable with high
#    confidence, return null - never guess.

# TEXT FIDELITY
# 4. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
#    confuse. Verify each letter against the image instead of auto-completing
#    to the most common/expected name (e.g. do not turn "بريدة" into "بردة" or
#    vice versa just because one is more familiar).
   
# 5. Copy the original text exactly (Arabic stays Arabic, English stays
#    English - never translate, paraphrase, or "correct" wording). If a
#    printed word looks unusual or misspelled, copy it as printed anyway - do
#    not substitute it with a different, more "expected" word. Do NOT add
#    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
#    in the image, even for well-known phrases like country/ministry names -
#    if the source text has no diacritics, your output must have none either.
# 6. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
#    confuse. Verify each letter against the image instead of auto-completing
#    to the most common/expected name.
# 7. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
#    digit form as printed, keep commas/decimal separators/currency symbols as
#    printed. Any reference/tracking number written inside parentheses or
#    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
#    digit-by-digit against the image before being used - these are the
#    numbers most often misread.
# 8. Fields containing "تاريخ"/"Date": copy exactly as printed, including
#    هـ/م markers, in the original order/separators. Never convert calendars
#    or reformat.

# LAYOUT
# 9. Ignore watermarks, background stamps, or repeated translucent/diagonal
#    overlay text that is not real document content (e.g. "Demonstration
#    License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# 10. Bilingual headers/letterheads often print the SAME info twice - once in
#    English, once in Arabic (side by side or stacked, sometimes next to a
#    logo). Treat them as two separate text blocks and read both fully; small
#    Arabic text next to a logo is real text, not decoration.
# 11. When a requested field's NAME is written in Arabic and the document
#     shows that information in both Arabic and English, return the ARABIC
#     version by default (unless the field name is itself in English, in
#     which case return the English version).
# 12. Tables: first read the header row fully (both languages if bilingual)
#     to establish the real left-to-right column order as printed on THIS
#     document. Then map each number in a row to its column strictly by its
#     printed position - never assume a "typical" order.
# 13. If a field's value wraps across multiple printed lines, join it into
#     ONE continuous value with single spaces between words - no merged
#     words, no leftover line breaks, no double spaces.

# Before answering, double-check every value against the image (nothing
# guessed, nothing skipped because it was small/faint/next to a logo/stamp).
# Return ONLY the JSON object."""

# _FIELD_GUIDANCE: dict[str, str] = {
#     # ---------------- تكليف ----------------
#     "رقم التكليف": """\
# - "رقم التكليف" is the official assignment/tasking number, usually near the
#   top of the document, often preceded by "رقم" or written in a reference box.""",
#     "تاريخ التكليف": """\
# - "تاريخ التكليف" is the date the assignment document itself was issued
#   (not the start/end dates of the assignment period).""",
#     "اسم المكلف": """\
# - "اسم المكلف" is the full name of the person being assigned/tasked. It
#   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
#     "تاريخ بداية التكليف": """\
# - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
#   confuse it with the issue date of the document.""",
#     "تاريخ نهاية التكليف": """\
# - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
#     "الموضوع": """\
# - "الموضوع" is the subject/topic stated in the document, usually appearing
#   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
#     "صادر من": """\
# - "صادر من" is the name/title of the person or authority who issued the
#   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
#   near a signature block at the bottom.""",
#     # ---------------- قرار ----------------
#     "رقم القرار": """\
# - "رقم القرار" is the official decision number, usually near the top or in a
#   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
#     "تاريخ القرار": """\
# - "تاريخ القرار" is the date the decision was issued/signed.""",
#     "موضوع القرار": """\
# - "موضوع القرار" is the subject/title line summarizing what the decision is
#   about, usually right under the decision number/date or after "الموضوع:".""",
#     "الجهة المصدرة": """\
# - "الجهة المصدرة" is the entity/department/authority that issued the
#   decision, often in letterhead at the top or near the signature at the
#   bottom.""",
#     # ---------------- تعميم ----------------
#     "تاريخ صدور التعميم هجري": """\
# - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
#   it exactly as written (day, month name or number, year), do not convert
#   to Gregorian, do not reformat.""",
#     "موضوع التعميم": """\
# - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
#   for - it is NEVER just the generic document-type word "تعميم" written at
#   the top of the page as a title. Ignore that title word completely.
# - Look at the main body paragraph(s) of the circular (usually starting with
#   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
#   "الموضوع:" label) and extract the actual subject being communicated.
# - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
#   summarize the core subject using wording taken directly from the body
#   text (do not invent new wording).
# - Any reference number mentioned inside this subject text (e.g. a decision
#   or letter number referenced in parentheses) must be copied digit-by-digit
#   exactly as printed - re-check it carefully, these numbers are easy to
#   misread.""",
#     "جهة التعميم": """\
# - "جهة التعميم" is the department/entity that issued the circular - usually
#   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
#   or near the signature block at the bottom.""",
#     "موجه الي": """\
# - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
#   "مدراء الإدارات"), usually appears near the top after "إلى:" or
#   "الموجه إلى:". Copy the full recipient phrase.""",
#     "نسخة الي": """\
# - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
#   near the bottom or right after the main addressee.""",
#     # ---------------- فواتير عربي ----------------
#     "رقم الفاتوره": """\
# - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits, e.g. "99911"), and it appears right after
#   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# - Do NOT confuse it with the commercial registration number or tax/VAT
#   number, which is a LONG number (usually 10+ digits) printed inside
#   square brackets "[ ]" or near the company letterhead.
# - If you see two different numbers near the top, pick the SHORT one that
#   directly follows the label "رقم" - not the long registration/tax number.""",
#     "رقم الفاتورة": """\
# - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
#   near the top of the document.
# - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
#     "الاسم": """\
# - "الاسم" here means the customer/client name, usually appearing after
#   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
#   NOT part of the customer's name.""",
#     "اسم المشتري": """\
# - "اسم المشتري" means the customer/client name, usually after "السادة" or
#   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
#     "المجموع": """\
# - "المجموع" is the subtotal before VAT/discount - usually a line item near
#   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
#   final grand total) and "القيمة المضافة" (the VAT amount).""",
#     "الخصم": """\
# - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
#   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
#     "القيمة المضافة": """\
# - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
#   followed by a percentage like "15%"), found near the totals section.""",
#     "اجمالي الفاتوره": """\
# - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
#   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
#   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
#     "اجمالي قيمة الفاتوره": """\
# - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
#   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
#     # ---------------- فواتير إنجليزي ----------------
#     "Customer Name": """\
# - "Customer Name" means the company or person receiving the invoice. It may
#   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
#   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
#     "Supplier Name": """\
# - "Supplier Name" means the company issuing the invoice. It may appear after:
#   Vendor, Supplier, Seller, From, شركة, المورد.""",
#     "Invoice Number": """\
# - "Invoice Number" must be the official invoice identifier. Do not use PO
#   Number, Order Number, Quote Number or Customer Number.""",
#     "Total Amount with VAT": """\
# - "Total Amount with VAT" must be the FINAL payable amount including VAT.
#   Do not return the subtotal unless explicitly requested.""",
#     "Items Count": """\
# - "Items Count": count the total number of distinct line items/products
#   listed. Return only the integer count.""",
#     "Item List": """\
# - "Item List": return an array containing only the product/service names in
#   the same order they appear. Do NOT include quantities, prices, or codes.""",
#     "اسم الشركة": """\
# - "اسم الشركة": if the letterhead shows the company name in both Arabic and
#   English, return the ARABIC name - not the English name.""",
# }

# # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# _DOC_TYPE_CONTEXT: dict[str, str] = {
#     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
#     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
#     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
#     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
#     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
#     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
#     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
#     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# }


# def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
#     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
#     clean_fields = [_normalize_field_name(f) for f in fields]
#     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

#     # FIX: إضافة سياق نوع المستند للـ prompt
#     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

#     prompt = _GENERAL_RULES.format(
#         fields_list=fields_list,
#         doc_type_context=doc_type_context,
#     )

#     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
#     if guidance:
#         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

#     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
#     if missing:
#         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

#     return prompt


# def build_raw_text_prompt() -> str:
#     return textwrap.dedent("""\
#         You are an expert OCR system specialized in verbatim, lossless text
#         extraction from document images, including documents that mix Arabic and
#         English in the same header/letterhead, and documents with numeric tables.

#         Your ONLY task is to output ALL real document text exactly as printed,
#         nothing changed, nothing skipped.

#         CRITICAL - NO INVENTED CONTENT: You may recognize this as a type of
#         document you have seen many examples of before. NEVER use that prior
#         knowledge to add ANY word, name, phrase, sentence, or boilerplate line
#         that is not ACTUALLY visible in THIS specific image. Only output such
#         a greeting if you can actually see it printed at the top of THIS image.

#         STRICT RULES

#         1. Copy every word/character EXACTLY as printed. Do not fix spelling or
#            grammar. Do NOT add Arabic diacritics/tashkeel that are not actually
#            printed in the image.

#         2. Do NOT translate anything. Arabic stays Arabic, English stays English.

#         3. IGNORE watermarks, background stamps, and repeated translucent/diagonal
#            overlay text (e.g. "Demonstration License", "SAMPLE", "DRAFT", "COPY").
#            Also IGNORE handwritten marginal annotations.

#         4. Numbers: copy digits exactly (keep Arabic-Indic vs Western digit form as
#            printed). Any number inside parentheses/brackets, and every number inside
#            a table, must be re-verified digit-by-digit.

#         5. Tables: transcribe row by row, keeping every number in the SAME column
#            position as printed - separate cells with " | ".

#         6. Bilingual headers: transcribe the English block in full, then "---",
#            then the Arabic block in full.

#         7. Two-column label:value rows: output as "<label>: <value>" — label first,
#            then colon, then value. Never reverse the order.

#         8. Keep paragraphs complete. Include headers, footers, titles, stamps,
#            signature text, and footnotes.

#         9. Read the ENTIRE image before answering - skip nothing.

#         10. No comments, no explanations, no markdown - output only the transcribed text.

#         Return ONLY the raw extracted text.""")


# def build_number_focus_prompt() -> str:
#     return textwrap.dedent("""\
#         You are a meticulous OCR system with ONE job: find every number that is
#         written INSIDE parentheses "( )" or square brackets "[ ]" anywhere on this
#         page, and copy each one out digit-by-digit, exactly as printed.

#         RULES:
#         - Scan the ENTIRE page top to bottom, left to right.
#         - Copy ONLY the digits inside the parentheses/brackets.
#         - Keep the exact digit form as printed (Arabic-Indic or Western).
#         - Before writing each number down, read it twice and count the digits.
#         - Output ONLY one number per line, in the exact order they appear.
#         - If there are no such numbers on the page, output nothing.""")



# from __future__ import annotations

# import logging
# import re
# import textwrap

# logger = logging.getLogger(__name__)

# # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# def _normalize_field_name(name: str) -> str:
#     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
#     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# _GENERAL_RULES = """\
# You are an expert OCR and document information extraction system specialized in
# Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# commercial documents (invoices, receipts, quotations).
# {doc_type_context}
# Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# footers, stamps, logo areas) and extract ONLY these fields:
# {fields_list}

# OUTPUT FORMAT
# 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
#    fences, no comments, no explanations, no text before or after it.
# 2. Use EXACTLY the requested field names as JSON keys, character for
#    character, in the same order they were given.
# 3. Never invent extra fields.

# MISSING VALUES - read this before answering
# 4. This document may simply not contain some of the requested fields. That is
#    normal and expected. If a field's value is not printed on this page, return
#    null for it. Returning null is the CORRECT answer - it is never penalized.
# 5. Never fill a field by borrowing a different value from elsewhere on the
#    page. A date that is not the requested date, or a number that belongs to a
#    different label, is WRONG - more wrong than null. Do not reason about what
#    the value "should" or "would typically" be: if you cannot point at the exact
#    printed characters for that specific field, the answer is null.

# TEXT FIDELITY
# 6. Copy the original text exactly (Arabic stays Arabic, English stays
#    English - never translate, transliterate, paraphrase, or "correct" wording).
#    If a printed word looks unusual or misspelled, copy it as printed anyway -
#    do not substitute it with a different, more "expected" word. Do NOT add
#    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
#    in the image, even for well-known phrases like country/ministry names -
#    if the source text has no diacritics, your output must have none either.
# 7. Proper nouns (place names, personal names) need extra letter-by-letter
#    care: several Arabic letters differ only by the number or position of
#    their dots, and are easy to confuse. Verify each letter against the image
#    instead of auto-completing to the most common or most familiar name.
#    Never replace a printed name with a better-known name that looks similar.
# 8. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
#    digit form as printed, keep commas/decimal separators/currency symbols as
#    printed. Any reference/tracking number written inside parentheses or
#    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
#    digit-by-digit against the image before being used - these are the
#    numbers most often misread.
# 9. Date fields: copy exactly as printed, including any Hijri/Gregorian era
#    marker, in the original order and with the original separators. Never
#    convert calendars and never reformat. Keep every digit group in the exact
#    left-to-right order shown in the image, even if another order is more
#    familiar to you. Reference numbers that mix an Arabic letter with digits
#    around a slash keep that letter as a letter - never turn it into a digit
#    and never drop it.

# LAYOUT
# 10. Arabic pages read RIGHT to LEFT. If the page is split into vertical
#     columns, read the entire RIGHT column top-to-bottom first, then the next
#     column to its left - never alternate between columns line by line.
# 11. Ignore watermarks, background stamps, or repeated translucent/diagonal
#     overlay text that is not real document content (e.g. "Demonstration
#     License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# 12. Bilingual headers/letterheads often print the SAME info twice - once in
#     English, once in Arabic (side by side or stacked, sometimes next to a
#     logo). Treat them as two separate text blocks and read both fully; small
#     Arabic text next to a logo is real text, not decoration.
# 13. When a requested field's NAME is written in Arabic and the document
#     shows that information in both Arabic and English, return the ARABIC
#     version by default (unless the field name is itself in English, in
#     which case return the English version).
# 14. Tables: first read the header row fully (both languages if bilingual)
#     to establish the real column order as printed on THIS document. Then map
#     each number in a row to its column strictly by its printed position -
#     never assume a "typical" order.
# 15. If a field's value wraps across multiple printed lines, join it into
#     ONE continuous value with single spaces between words - no merged
#     words, no leftover line breaks, no double spaces.

# Before answering, check every non-null value one more time: can you point at
# the exact printed characters for it on THIS page, next to THAT field's own
# label? If not, change it to null. Return ONLY the JSON object."""

# _FIELD_GUIDANCE: dict[str, str] = {
#     # ---------------- تكليف ----------------
#     "رقم التكليف": """\
# - "رقم التكليف" is the official assignment/tasking number, usually near the
#   top of the document, often preceded by "رقم" or written in a reference box.""",
#     "تاريخ التكليف": """\
# - "تاريخ التكليف" is the date the assignment document itself was issued
#   (not the start/end dates of the assignment period).""",
#     "اسم المكلف": """\
# - "اسم المكلف" is the full name of the person being assigned/tasked. It
#   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
#     "تاريخ بداية التكليف": """\
# - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
#   confuse it with the issue date of the document.""",
#     "تاريخ نهاية التكليف": """\
# - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
#     "الموضوع": """\
# - "الموضوع" is the subject/topic stated in the document, usually appearing
#   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
#     "صادر من": """\
# - "صادر من" is the name/title of the person or authority who issued the
#   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
#   near a signature block at the bottom.""",
#     # ---------------- قرار ----------------
#     "رقم القرار": """\
# - "رقم القرار" is the official decision number, usually near the top or in a
#   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
#     "تاريخ القرار": """\
# - "تاريخ القرار" is the date the decision was issued/signed.""",
#     "موضوع القرار": """\
# - "موضوع القرار" is the subject/title line summarizing what the decision is
#   about, usually right under the decision number/date or after "الموضوع:".""",
#     "الجهة المصدرة": """\
# - "الجهة المصدرة" is the entity/department/authority that issued the
#   decision, often in letterhead at the top or near the signature at the
#   bottom.""",
#     # ---------------- تعميم ----------------
#     "تاريخ صدور التعميم هجري": """\
# - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
#   it exactly as written (day, month name or number, year), do not convert
#   to Gregorian, do not reformat.""",
#     "موضوع التعميم": """\
# - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
#   for - it is NEVER just the generic document-type word "تعميم" written at
#   the top of the page as a title. Ignore that title word completely.
# - Look at the main body paragraph(s) of the circular (usually starting with
#   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
#   "الموضوع:" label) and extract the actual subject being communicated.
# - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
#   summarize the core subject using wording taken directly from the body
#   text (do not invent new wording).
# - Any reference number mentioned inside this subject text (e.g. a decision
#   or letter number referenced in parentheses) must be copied digit-by-digit
#   exactly as printed - re-check it carefully, these numbers are easy to
#   misread.""",
#     "جهة التعميم": """\
# - "جهة التعميم" is the department/entity that issued the circular - usually
#   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
#   or near the signature block at the bottom.""",
#     "موجه الي": """\
# - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
#   "مدراء الإدارات"), usually appears near the top after "إلى:" or
#   "الموجه إلى:". Copy the full recipient phrase.""",
#     "نسخة الي": """\
# - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
#   near the bottom or right after the main addressee.""",
#     # ---------------- فواتير عربي ----------------
#     "رقم الفاتوره": """\
# - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits, e.g. "99911"), and it appears right after
#   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# - Do NOT confuse it with the commercial registration number or tax/VAT
#   number, which is a LONG number (usually 10+ digits) printed inside
#   square brackets "[ ]" or near the company letterhead.
# - If you see two different numbers near the top, pick the SHORT one that
#   directly follows the label "رقم" - not the long registration/tax number.""",
#     "رقم الفاتورة": """\
# - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
#   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
#   near the top of the document.
# - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
#     "الاسم": """\
# - "الاسم" here means the customer/client name, usually appearing after
#   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
#   NOT part of the customer's name.""",
#     "اسم المشتري": """\
# - "اسم المشتري" means the customer/client name, usually after "السادة" or
#   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
#     "المجموع": """\
# - "المجموع" is the subtotal before VAT/discount - usually a line item near
#   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
#   final grand total) and "القيمة المضافة" (the VAT amount).""",
#     "الخصم": """\
# - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
#   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
#     "القيمة المضافة": """\
# - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
#   followed by a percentage like "15%"), found near the totals section.""",
#     "اجمالي الفاتوره": """\
# - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
#   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
#   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
#     "اجمالي قيمة الفاتوره": """\
# - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
#   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
#     # ---------------- فواتير إنجليزي ----------------
#     "Customer Name": """\
# - "Customer Name" means the company or person receiving the invoice. It may
#   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
#   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
#     "Supplier Name": """\
# - "Supplier Name" means the company issuing the invoice. It may appear after:
#   Vendor, Supplier, Seller, From, شركة, المورد.""",
#     "Invoice Number": """\
# - "Invoice Number" must be the official invoice identifier. Do not use PO
#   Number, Order Number, Quote Number or Customer Number.""",
#     "Total Amount with VAT": """\
# - "Total Amount with VAT" must be the FINAL payable amount including VAT.
#   Do not return the subtotal unless explicitly requested.""",
#     "Items Count": """\
# - "Items Count": count the total number of distinct line items/products
#   listed. Return only the integer count.""",
#     "Item List": """\
# - "Item List": return an array containing only the product/service names in
#   the same order they appear. Do NOT include quantities, prices, or codes.""",
#     "اسم الشركة": """\
# - "اسم الشركة": if the letterhead shows the company name in both Arabic and
#   English, return the ARABIC name - not the English name.""",
# }

# # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# _DOC_TYPE_CONTEXT: dict[str, str] = {
#     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
#     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
#     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
#     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
#     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
#     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
#     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
#     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# }


# def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
#     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
#     clean_fields = [_normalize_field_name(f) for f in fields]
#     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

#     # FIX: إضافة سياق نوع المستند للـ prompt
#     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

#     prompt = _GENERAL_RULES.format(
#         fields_list=fields_list,
#         doc_type_context=doc_type_context,
#     )

#     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
#     if guidance:
#         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

#     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
#     if missing:
#         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

#     return prompt


# def build_raw_text_prompt() -> str:
#     """
#     برومبت النسخ الحرفي.

#     قاعدة حديدية: ممنوع نهائيًا أي نص عربي أو أي مثال ملموس (اسم، تاريخ، رقم
#     مرجعي، اسم مدينة) جوه البرومبت ده. الموديل vision صغير، ولما القصاصة تبقى
#     شبه فاضية أو صعبة القراءة بيرجّع محتوى البرومبت نفسه كأنه نص المستند.
#     كل سطر مهلوس ظهر في النتايج قبل كده كان متكتوب حرفيًا هنا (اسم مدينة،
#     "المملكة"، أرقام مرجعية زي ١٣/أ، تاريخ ١٤٤٨/١/٢٦هـ، والاسم اللاتيني
#     Salman bin Abdulaziz Al Saud). القاعدة اتحوّلت لاختبار في
#     tests/test_prompt_has_no_arabic.py عشان متترجعش تاني بالغلط.
#     """
#     return textwrap.dedent("""\
#         You are a verbatim OCR transcription engine. Transcribe ALL text visible
#         in this image, exactly as printed, and output nothing else.

#         SCRIPT AND FIDELITY
#         1. Never translate and never transliterate. Text printed in Arabic script
#            must be output in Arabic script. Text printed in Latin script must be
#            output in Latin script. Never write an Arabic name using Latin letters,
#            and never write a Latin name using Arabic letters.
#         2. Copy every word exactly as printed, including misspellings, unusual
#            wording, broken words and odd spacing. Never correct or normalize.
#         3. Copy Arabic diacritics only where they are actually printed. Never add
#            diacritics to a word that is printed without them.
#         4. Copy digits exactly and keep the printed digit system (Arabic-Indic vs
#            Western). Never convert calendars and never reformat dates.
#         5. Write the digit groups of any date or compound number in the exact
#            left-to-right order they appear in the image, even when a different
#            order is the one you are used to seeing.
#         6. Reference numbers often combine an Arabic letter and digits around a
#            slash or a dash. Transcribe the letter as that letter: never turn it
#            into a digit and never drop it.
#         7. Each number belongs to the label physically next to it. Never move a
#            number to a different label because it looks like a better fit.
#         8. Arabic headings are often stretched with kashida/tatweel. Read the
#            actual letters through the stretching and output the normal unstretched
#            word, without dropping any repeated letter.
#         9. If a word or region is genuinely unreadable, write [?] in its place.
#            Never replace it with a guess.

#         THIS IMAGE ONLY - the most important rule
#         10. This image may be a small crop of a larger page: a header strip, one
#             column, a band of a few lines, or a footer. Transcribe exactly what is
#             inside THIS image and nothing else. Do not add lines you expect to be
#             above or below the crop.
#         11. You may recognize this as a familiar KIND of document. NEVER use that
#             familiarity to output any word, name, city, authority, date, number,
#             heading, clause or boilerplate line that you cannot actually SEE in
#             THIS image.
#         12. Never output any text taken from these instructions. These
#             instructions are not part of the document.
#         13. If this image contains no readable text at all (blank area, a rule,
#             a decorative border, a faint background stamp), output nothing at all.
#             An empty answer is the correct answer - never fill the silence.

#         NO LOOPING
#         14. Transcribe each printed line exactly ONCE, then move DOWN to the next
#             line. When you reach the last printed line in this image, STOP.
#         15. Formal pages repeat very similar lines on purpose, differing only by a
#             number or a date. Track which line you are on by its POSITION in the
#             image, not by its wording. After writing one, your next output must
#             come from the line physically BELOW it. Never restart from an earlier
#             line and never continue past the last printed one.
#         16. Before finishing, check you have not written the same line twice and
#             have not invented extra numbered items. A short transcription of a
#             short crop is correct; padding it is not.

#         READING ORDER
#         17. Normally this is a single column. Read strictly top to bottom, one
#             line after another, and transcribe every line you pass.
#         18. Arabic lines read right-to-left: each line starts at its RIGHT edge.
#         19. Only if the image really contains two side-by-side columns of text:
#             transcribe ONE WHOLE COLUMN AT A TIME, the RIGHT-hand one first from
#             its top to its bottom, then the one to its left. Never alternate
#             between columns line by line and never merge a line from one column
#             with a line from another.

#         STRUCTURE
#         20. Keep the printed line and paragraph breaks.
#         21. Keep list markers and numbering exactly as printed, with their own
#             characters. Never replace a printed marker with a generic dash, never
#             drop it, and never renumber the items.
#         22. Tables: one printed row per output line, cells separated by " | ",
#             keeping the printed cell order.
#         23. Include headers, footers, letterhead lines, reference numbers, dates
#             and signature-line names.
#         24. Label:value rows: output as "<label>: <value>" - label first, then the
#             value. Never reverse the order.
#         25. Skip repeated translucent diagonal background watermark overlays and
#             faint repeated institution names printed across the page behind the
#             text. Everything else in the image is real content.

#         STAMPS AND SEALS - never transcribe
#         26. Do NOT transcribe any text that belongs to a stamp or a seal: round
#             or oval ink stamps, bordered rectangular stamps, embossed or dry
#             seals, text that curves along the edge of a circle, and text
#             printed at an angle across other text.
#         27. Do NOT transcribe handwritten signatures, handwritten initials,
#             QR codes or barcodes.
#         28. A stamp usually sits on top of the printed text. Transcribe the
#             printed text underneath it and ignore the stamp's own wording
#             completely. Never merge a word from a stamp into a printed line.

#         Output ONLY the transcription: no commentary, no explanations, no markdown.""")


# # ─────────────────────────────────────────────────────────────────────────────
# # حارس: أي حرف عربي جوه برومبت النسخ الحرفي = مصدر هلوسة محتمل.
# # الموديل بيرجّع محتوى البرومبت لما القصاصة تبقى صعبة/فاضية، فأي مثال ملموس
# # (اسم/تاريخ/رقم مرجعي/اسم مدينة) بيتحوّل لسطر مزيف في نص المستند.
# # ─────────────────────────────────────────────────────────────────────────────
# _ARABIC_RANGE_RE = re.compile(r"[\u0600-\u06FF]")


# def assert_raw_prompt_is_ascii_only() -> None:
#     """بيترمي AssertionError لو حد رجّع مثال عربي لبرومبت النسخ الحرفي."""
#     offenders = sorted(set(_ARABIC_RANGE_RE.findall(build_raw_text_prompt())))
#     assert not offenders, (
#         "برومبت النسخ الحرفي فيه حروف عربية - ده بيرجع في النص كهلوسة: "
#         + "".join(offenders)
#     )


# assert_raw_prompt_is_ascii_only()










# # # from __future__ import annotations

# # # import logging
# # # import re
# # # import textwrap

# # # logger = logging.getLogger(__name__)

# # # # FIX: نمط تنظيف الأحرف غير المرئية (RTL mark, BOM, NBSP, إلخ) التي تأتي
# # # # من Laserfiche وتكسر المطابقة الحرفية مع مفاتيح _FIELD_GUIDANCE
# # # _INVISIBLE_CHARS_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0\u200e\u200f]")


# # # def _normalize_field_name(name: str) -> str:
# # #     """إزالة المسافات الزائدة والأحرف غير المرئية من اسم الحقل."""
# # #     return _INVISIBLE_CHARS_RE.sub("", name.strip())


# # # _GENERAL_RULES = """\
# # # You are an expert OCR and document information extraction system specialized in
# # # Arabic government/administrative documents (تكليف، قرار، تعميم) as well as
# # # commercial documents (invoices, receipts, quotations).
# # # {doc_type_context}
# # # Read the ENTIRE image (top, middle, bottom, left, right, tables, headers,
# # # footers, stamps, logo areas) and extract ONLY these fields:
# # # {fields_list}

# # # OUTPUT FORMAT
# # # 1. Return ONLY a single valid, minified JSON object - no markdown, no ```
# # #    fences, no comments, no explanations, no text before or after it.
# # # 2. Use EXACTLY the requested field names as JSON keys, character for
# # #    character, in the same order they were given.
# # # 3. Never invent extra fields. If a value is missing or unreadable with high
# # #    confidence, return null - never guess.

# # # TEXT FIDELITY
# # # 4. Proper nouns (place names, personal names) need extra letter-by-letter
# # #    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
# # #    confuse. Verify each letter against the image instead of auto-completing
# # #    to the most common/expected name (e.g. do not turn "بريدة" into "بردة" or
# # #    vice versa just because one is more familiar).
   
# # # 5. Copy the original text exactly (Arabic stays Arabic, English stays
# # #    English - never translate, paraphrase, or "correct" wording). If a
# # #    printed word looks unusual or misspelled, copy it as printed anyway - do
# # #    not substitute it with a different, more "expected" word. Do NOT add
# # #    Arabic diacritics/tashkeel (َ ً ُ ٌ ِ ٍ ْ ّ) that are not actually printed
# # #    in the image, even for well-known phrases like country/ministry names -
# # #    if the source text has no diacritics, your output must have none either.
# # # 6. Proper nouns (place names, personal names) need extra letter-by-letter
# # #    care: visually similar Arabic letters (ي/ب/ت/ث, د/ذ, ر/ز, س/ش) are easy to
# # #    confuse. Verify each letter against the image instead of auto-completing
# # #    to the most common/expected name.
# # # 7. Numbers: copy digits exactly, keep Arabic-Indic (٠١٢٣٤٥٦٧٨٩) vs Western
# # #    digit form as printed, keep commas/decimal separators/currency symbols as
# # #    printed. Any reference/tracking number written inside parentheses or
# # #    brackets in a body paragraph (e.g. "رقم (446842135)") must be re-verified
# # #    digit-by-digit against the image before being used - these are the
# # #    numbers most often misread.
# # # 8. Fields containing "تاريخ"/"Date": copy exactly as printed, including
# # #    هـ/م markers, in the original order/separators. Never convert calendars
# # #    or reformat.

# # # LAYOUT
# # # 9. Ignore watermarks, background stamps, or repeated translucent/diagonal
# # #    overlay text that is not real document content (e.g. "Demonstration
# # #    License", "SAMPLE", "DRAFT", "COPY"). Never put this text in any field.
# # # 10. Bilingual headers/letterheads often print the SAME info twice - once in
# # #    English, once in Arabic (side by side or stacked, sometimes next to a
# # #    logo). Treat them as two separate text blocks and read both fully; small
# # #    Arabic text next to a logo is real text, not decoration.
# # # 11. When a requested field's NAME is written in Arabic and the document
# # #     shows that information in both Arabic and English, return the ARABIC
# # #     version by default (unless the field name is itself in English, in
# # #     which case return the English version).
# # # 12. Tables: first read the header row fully (both languages if bilingual)
# # #     to establish the real left-to-right column order as printed on THIS
# # #     document. Then map each number in a row to its column strictly by its
# # #     printed position - never assume a "typical" order.
# # # 13. If a field's value wraps across multiple printed lines, join it into
# # #     ONE continuous value with single spaces between words - no merged
# # #     words, no leftover line breaks, no double spaces.

# # # Before answering, double-check every value against the image (nothing
# # # guessed, nothing skipped because it was small/faint/next to a logo/stamp).
# # # Return ONLY the JSON object."""

# # # _FIELD_GUIDANCE: dict[str, str] = {
# # #     # ---------------- تكليف ----------------
# # #     "رقم التكليف": """\
# # # - "رقم التكليف" is the official assignment/tasking number, usually near the
# # #   top of the document, often preceded by "رقم" or written in a reference box.""",
# # #     "تاريخ التكليف": """\
# # # - "تاريخ التكليف" is the date the assignment document itself was issued
# # #   (not the start/end dates of the assignment period).""",
# # #     "اسم المكلف": """\
# # # - "اسم المكلف" is the full name of the person being assigned/tasked. It
# # #   usually appears after labels like "السيد/", "الأستاذ/", "المكلف/", "اسم".""",
# # #     "تاريخ بداية التكليف": """\
# # # - "تاريخ بداية التكليف" is the start date of the assignment period. Do not
# # #   confuse it with the issue date of the document.""",
# # #     "تاريخ نهاية التكليف": """\
# # # - "تاريخ نهاية التكليف" is the end date of the assignment period.""",
# # #     "الموضوع": """\
# # # - "الموضوع" is the subject/topic stated in the document, usually appearing
# # #   after a label "الموضوع:" or "الموضوع /". Copy the full text after the label.""",
# # #     "صادر من": """\
# # # - "صادر من" is the name/title of the person or authority who issued the
# # #   document (e.g. "مدير التعليم", "مدير عام", "رئيس القسم"). It often appears
# # #   near a signature block at the bottom.""",
# # #     # ---------------- قرار ----------------
# # #     "رقم القرار": """\
# # # - "رقم القرار" is the official decision number, usually near the top or in a
# # #   reference box, often preceded by "رقم القرار" or "القرار رقم".""",
# # #     "تاريخ القرار": """\
# # # - "تاريخ القرار" is the date the decision was issued/signed.""",
# # #     "موضوع القرار": """\
# # # - "موضوع القرار" is the subject/title line summarizing what the decision is
# # #   about, usually right under the decision number/date or after "الموضوع:".""",
# # #     "الجهة المصدرة": """\
# # # - "الجهة المصدرة" is the entity/department/authority that issued the
# # #   decision, often in letterhead at the top or near the signature at the
# # #   bottom.""",
# # #     # ---------------- تعميم ----------------
# # #     "تاريخ صدور التعميم هجري": """\
# # # - "تاريخ صدور التعميم هجري" is the Hijri date the circular was issued. Copy
# # #   it exactly as written (day, month name or number, year), do not convert
# # #   to Gregorian, do not reformat.""",
# # #     "موضوع التعميم": """\
# # # - "موضوع التعميم" is a SUMMARY of what the circular is actually about/asking
# # #   for - it is NEVER just the generic document-type word "تعميم" written at
# # #   the top of the page as a title. Ignore that title word completely.
# # # - Look at the main body paragraph(s) of the circular (usually starting with
# # #   something like "يهدي..." or "بالإشارة إلى..." or after an explicit
# # #   "الموضوع:" label) and extract the actual subject being communicated.
# # # - If there is an explicit "الموضوع:" label, prefer that exact text. If not,
# # #   summarize the core subject using wording taken directly from the body
# # #   text (do not invent new wording).
# # # - Any reference number mentioned inside this subject text (e.g. a decision
# # #   or letter number referenced in parentheses) must be copied digit-by-digit
# # #   exactly as printed - re-check it carefully, these numbers are easy to
# # #   misread.""",
# # #     "جهة التعميم": """\
# # # - "جهة التعميم" is the department/entity that issued the circular - usually
# # #   in the letterhead at the top (e.g. "رئاسة الوزراء", "البنك المركزي السعودي")
# # #   or near the signature block at the bottom.""",
# # #     "موجه الي": """\
# # # - "موجه الي" is who the circular is addressed to (e.g. "جميع الأقسام",
# # #   "مدراء الإدارات"), usually appears near the top after "إلى:" or
# # #   "الموجه إلى:". Copy the full recipient phrase.""",
# # #     "نسخة الي": """\
# # # - "نسخة الي" ("cc") lists additional recipients who receive a copy, usually
# # #   near the bottom or right after the main addressee.""",
# # #     # ---------------- فواتير عربي ----------------
# # #     "رقم الفاتوره": """\
# # # - "رقم الفاتوره" is the invoice/reference number. It is usually a SHORT
# # #   number (typically 4-7 digits, e.g. "99911"), and it appears right after
# # #   the word "رقم" (often written "رقم /" or "رقم:") near the top.
# # # - Do NOT confuse it with the commercial registration number or tax/VAT
# # #   number, which is a LONG number (usually 10+ digits) printed inside
# # #   square brackets "[ ]" or near the company letterhead.
# # # - If you see two different numbers near the top, pick the SHORT one that
# # #   directly follows the label "رقم" - not the long registration/tax number.""",
# # #     "رقم الفاتورة": """\
# # # - "رقم الفاتورة" is the invoice/reference number. It is usually a SHORT
# # #   number (typically 4-7 digits), appearing right after "رقم" or "رقم /"
# # #   near the top of the document.
# # # - Do NOT use the long registration/tax number (usually 10+ digits inside brackets).""",
# # #     "الاسم": """\
# # # - "الاسم" here means the customer/client name, usually appearing after
# # #   "السادة", "السادة/", or "السادة:" near the top of the invoice.
# # # - Strip any trailing courtesy word like "المحترمين" or "المحترم" - it is
# # #   NOT part of the customer's name.""",
# # #     "اسم المشتري": """\
# # # - "اسم المشتري" means the customer/client name, usually after "السادة" or
# # #   "السادة/". Strip "المحترمين"/"المحترم" from the end - not part of the name.""",
# # #     "المجموع": """\
# # # - "المجموع" is the subtotal before VAT/discount - usually a line item near
# # #   the totals section at the bottom, distinct from "اجمالي الفاتوره" (the
# # #   final grand total) and "القيمة المضافة" (the VAT amount).""",
# # #     "الخصم": """\
# # # - "الخصم" is the discount amount. If the document shows "0.00" or "-" next
# # #   to a "الخصم"/"Discount" label, the discount is 0.00, not null.""",
# # #     "القيمة المضافة": """\
# # # - "القيمة المضافة" is the VAT amount (often labeled "ضريبة القيمة المضافة"
# # #   followed by a percentage like "15%"), found near the totals section.""",
# # #     "اجمالي الفاتوره": """\
# # # - "اجمالي الفاتوره" is the FINAL grand total payable, including VAT and
# # #   after discount. Do NOT confuse with subtotal (المجموع), discount (الخصم),
# # #   or VAT amount. Sanity check: this value should equal subtotal - discount + VAT.""",
# # #     "اجمالي قيمة الفاتوره": """\
# # # - "اجمالي قيمة الفاتوره" is the FINAL grand total payable, including VAT
# # #   and after discount. Sanity check: should equal subtotal - discount + VAT.""",
# # #     # ---------------- فواتير إنجليزي ----------------
# # #     "Customer Name": """\
# # # - "Customer Name" means the company or person receiving the invoice. It may
# # #   appear after labels such as: السادة، العميل، اسم العميل، المشتري، شركة,
# # #   Bill To, Buyer, Customer, Sold To. Strip "المحترمين"/"المحترم" if present.""",
# # #     "Supplier Name": """\
# # # - "Supplier Name" means the company issuing the invoice. It may appear after:
# # #   Vendor, Supplier, Seller, From, شركة, المورد.""",
# # #     "Invoice Number": """\
# # # - "Invoice Number" must be the official invoice identifier. Do not use PO
# # #   Number, Order Number, Quote Number or Customer Number.""",
# # #     "Total Amount with VAT": """\
# # # - "Total Amount with VAT" must be the FINAL payable amount including VAT.
# # #   Do not return the subtotal unless explicitly requested.""",
# # #     "Items Count": """\
# # # - "Items Count": count the total number of distinct line items/products
# # #   listed. Return only the integer count.""",
# # #     "Item List": """\
# # # - "Item List": return an array containing only the product/service names in
# # #   the same order they appear. Do NOT include quantities, prices, or codes.""",
# # #     "اسم الشركة": """\
# # # - "اسم الشركة": if the letterhead shows the company name in both Arabic and
# # #   English, return the ARABIC name - not the English name.""",
# # # }

# # # # سياق نوع المستند - يُضاف للـ prompt لمساعدة الموديل
# # # _DOC_TYPE_CONTEXT: dict[str, str] = {
# # #     "takleef": "\nThis is an Arabic ASSIGNMENT/TASKING document (تكليف). Focus on assignment details, assignee name, dates, and issuing authority.\n",
# # #     "qarar": "\nThis is an Arabic DECISION/DECREE document (قرار). Focus on decision number, date, subject, and issuing authority.\n",
# # #     "tamim": "\nThis is an Arabic CIRCULAR/MEMO document (تعميم). Focus on the circular date, subject matter, issuing entity, and recipients.\n",
# # #     "invoice": "\nThis is a COMMERCIAL INVOICE document. Focus on invoice number, date, customer name, and financial totals.\n",
# # #     "receipt": "\nThis is a RECEIPT document. Focus on receipt number, date, payer, and amount paid.\n",
# # #     "purchase_order": "\nThis is a PURCHASE ORDER document. Focus on PO number, supplier, dates, and total amount.\n",
# # #     "delivery_note": "\nThis is a DELIVERY NOTE document. Focus on delivery note number, date, receiver, and item count.\n",
# # #     "quotation": "\nThis is a PRICE QUOTATION document. Focus on company name, date, item list, and total amount.\n",
# # # }


# # # def build_fields_prompt(fields: list[str], doc_type: str = "") -> str:
# # #     # FIX: تنظيف أسماء الحقول من الأحرف غير المرئية قبل المطابقة مع _FIELD_GUIDANCE
# # #     clean_fields = [_normalize_field_name(f) for f in fields]
# # #     fields_list = "\n".join(f'- "{f}"' for f in clean_fields)

# # #     # FIX: إضافة سياق نوع المستند للـ prompt
# # #     doc_type_context = _DOC_TYPE_CONTEXT.get(doc_type, "")

# # #     prompt = _GENERAL_RULES.format(
# # #         fields_list=fields_list,
# # #         doc_type_context=doc_type_context,
# # #     )

# # #     guidance = [_FIELD_GUIDANCE[f] for f in clean_fields if f in _FIELD_GUIDANCE]
# # #     if guidance:
# # #         prompt += "\n\nFIELD-SPECIFIC GUIDANCE:\n" + "\n".join(guidance)

# # #     missing = [f for f in clean_fields if f not in _FIELD_GUIDANCE]
# # #     if missing:
# # #         logger.info("حقول مطلوبة بدون guidance مخصصة: %s", missing)

# # #     return prompt


# # # def build_raw_text_prompt() -> str:
# # #     return textwrap.dedent("""\
# # #         You are an expert OCR system specialized in verbatim, lossless text
# # #         extraction from document images, including documents that mix Arabic and
# # #         English in the same header/letterhead, and documents with numeric tables.

# # #         Your ONLY task is to output ALL real document text exactly as printed,
# # #         nothing changed, nothing skipped.

# # #         CRITICAL - NO INVENTED CONTENT: You may recognize this as a type of
# # #         document you have seen many examples of before. NEVER use that prior
# # #         knowledge to add ANY word, name, phrase, sentence, or boilerplate line
# # #         that is not ACTUALLY visible in THIS specific image. Only output such
# # #         a greeting if you can actually see it printed at the top of THIS image.

# # #         STRICT RULES

# # #         1. Copy every word/character EXACTLY as printed. Do not fix spelling or
# # #            grammar. Do NOT add Arabic diacritics/tashkeel that are not actually
# # #            printed in the image.

# # #         2. Do NOT translate anything. Arabic stays Arabic, English stays English.

# # #         3. IGNORE watermarks, background stamps, and repeated translucent/diagonal
# # #            overlay text (e.g. "Demonstration License", "SAMPLE", "DRAFT", "COPY").
# # #            Also IGNORE handwritten marginal annotations.

# # #         4. Numbers: copy digits exactly (keep Arabic-Indic vs Western digit form as
# # #            printed). Any number inside parentheses/brackets, and every number inside
# # #            a table, must be re-verified digit-by-digit.

# # #         5. Tables: transcribe row by row, keeping every number in the SAME column
# # #            position as printed - separate cells with " | ".

# # #         6. Bilingual headers: transcribe the English block in full, then "---",
# # #            then the Arabic block in full.

# # #         7. Two-column label:value rows: output as "<label>: <value>" — label first,
# # #            then colon, then value. Never reverse the order.

# # #         8. Keep paragraphs complete. Include headers, footers, titles, stamps,
# # #            signature text, and footnotes.

# # #         9. Read the ENTIRE image before answering - skip nothing.

# # #         10. No comments, no explanations, no markdown - output only the transcribed text.

# # #         Return ONLY the raw extracted text.""")


# # # def build_number_focus_prompt() -> str:
# # #     return textwrap.dedent("""\
# # #         You are a meticulous OCR system with ONE job: find every number that is
# # #         written INSIDE parentheses "( )" or square brackets "[ ]" anywhere on this
# # #         page, and copy each one out digit-by-digit, exactly as printed.

# # #         RULES:
# # #         - Scan the ENTIRE page top to bottom, left to right.
# # #         - Copy ONLY the digits inside the parentheses/brackets.
# # #         - Keep the exact digit form as printed (Arabic-Indic or Western).
# # #         - Before writing each number down, read it twice and count the digits.
# # #         - Output ONLY one number per line, in the exact order they appear.
# # #         - If there are no such numbers on the page, output nothing.""")
