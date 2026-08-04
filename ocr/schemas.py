"""نماذج الطلب/الرد المستخدمة في الـ API، لتوثيق أوضح في OpenAPI ولضمان شكل الرد."""

from __future__ import annotations

from pydantic import BaseModel


class PageText(BaseModel):
    """نص صفحة واحدة. الترقيم بيبدأ من 1 عشان يطابق ترقيم Laserfiche."""

    page: int
    text: str


class ExtractAllTextResponse(BaseModel):
    text: str
    file_name: str
    download_url: str
    # عدد الصفحات اللي اتعالجت فعلًا. لو الرقم ده = 1 والمستند أكتر من صفحة،
    # يبقى العميل (Laserfiche JS) بعت صفحة واحدة بس مش الملف كله.
    page_count: int = 1
    # نص كل صفحة لوحده. Laserfiche بيخزّن النص لكل صفحة على حدة عن طريق
    # SetTextByDocIdAndPageId، فالـ JS محتاج التقسيمة دي مش النص الملزوق.
    pages: list[PageText] = []
