"""نقطة دخول تطبيق FastAPI."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import fitz  # PyMuPDF — pip install pymupdf --break-system-packages
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.document_types import DEFAULT_DOC_TYPE, DOCUMENT_TYPES, DocumentTypeConfig, get_fields_for_doc_type
from app.ocr_service import extract_all_text, extract_fields, merge_page_fields
from app.schemas import ExtractAllTextResponse, PageText

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Arabic Document Field & Text Extractor", root_path="/ocr")

# CORS — يسمح للـ React frontend بالاتصال
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    بيحوّل أي استثناء غير متوقع لـ JSONResponse بدل ما يعدّي كـ raw 500.

    السبب: ServerErrorMiddleware بتاعة Starlette بتقف *بره* الـ CORSMiddleware،
    فالـ 500 الناتج عن استثناء مبيتحطش عليه CORS headers. المتصفح بيحجب قراءة
    الرد فالـ fetch بيفشل على مستوى الشبكة، والـ JS بيقول "تعذر الاتصال بخدمة
    الـ OCR" بدل ما يقول سبب الخطأ الحقيقي - وde كان بيخفي الـ AttributeError
    ورا رسالة اتصال مضللة تمامًا.

    كده الـ handler ده بيرجّع JSON عادي، فالـ CORSMiddleware بتشوفه وبتحط
    الهيدرز، والرسالة بتوصل للمستخدم في الـ overlay.
    """
    logger.exception("استثناء غير متوقع في %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


_IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"BM", b"II*\x00", b"MM\x00*")


def _is_pdf(data: bytes) -> bool:
    """
    الاعتماد على الـ magic bytes مش على content_type.

    Laserfiche (وعملاء تانيين كتير) بيبعتوا الـ PDF بـ content_type
    "application/octet-stream" أو "application/pdf; charset=binary". المقارنة
    الحرفية القديمة كانت بتفشل في الحالتين، فالبايتس بتاعة الـ PDF كانت
    بتتبعت للموديل كأنها صورة - الموديل مبيشوفش حاجة ويرجّع نتيجة فاضية.
    """
    return data[:5] == b"%PDF-"


def _require_supported_file(data: bytes) -> None:
    if _is_pdf(data) or data.startswith(_IMAGE_MAGIC):
        return
    raise HTTPException(status_code=400, detail="من فضلك ارفع ملف صورة (PNG/JPG) أو PDF")


def _pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    """
    يحوّل كل صفحات الـ PDF لصور JPEG، صفحة صفحة.

    الإصدار القديم كان بياخد أول صفحة بس (load_page(0)) - يعني أي PDF أكتر من
    صفحة كان بيرجّع نص الصفحة الأولى وخلاص والباقي بيضيع.

    الرسم بيتم على الـ DPI اللي يوصّل الصفحة لأكبر بُعد مطلوب مرة واحدة، بدل
    الرسم على DPI ثابت وبعدين تصغير - كل resample زيادة بيهرّي حواف الخط
    العربي الصغير وبيزوّد أخطاء الحروف المتشابهة.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    logger.info("الـ PDF المستلم فيه %d صفحة.", doc.page_count)
    if doc.page_count == 1:
        logger.warning(
            "الـ PDF المستلم صفحة واحدة بس. لو المستند في Laserfiche أكتر من "
            "صفحة، يبقى الـ export رجّع الصفحة الحالية بس - راجع الباراميتر "
            "EXPORT_PAGES_PARAM في ArabicOCR.js. المشكلة مش في خدمة الـ OCR."
        )
    page_count = min(doc.page_count, settings.max_pdf_pages)
    if doc.page_count > settings.max_pdf_pages:
        logger.warning(
            "الـ PDF فيه %d صفحة، هيتعالج أول %d بس (max_pdf_pages).",
            doc.page_count, settings.max_pdf_pages,
        )

    images: list[bytes] = []
    for index in range(page_count):
        page = doc.load_page(index)
        longest_point = max(page.rect.width, page.rect.height)
        dpi = min(settings.pdf_render_dpi, int(settings.max_image_dimension_text / longest_point * 72))
        pix = page.get_pixmap(dpi=max(dpi, 150))
        images.append(pix.tobytes("jpeg"))
    return images


async def _read_pages(image: UploadFile) -> list[bytes]:
    """يقرا الملف المرفوع ويرجّعه كقائمة صور صفحات (صورة واحدة = صفحة واحدة)."""
    data = await image.read()
    _require_supported_file(data)
    if _is_pdf(data):
        pages = _pdf_to_page_images(data)
        logger.info("الملف المرفوع PDF فيه %d صفحة هتتعالج.", len(pages))
        return pages
    # صورة واحدة = صفحة واحدة. لو المستند في Laserfiche أكتر من صفحة وشوفت
    # السطر ده، يبقى العميل بعت الصفحة الحالية بس - المشكلة مش هنا.
    logger.info(
        "الملف المرفوع صورة واحدة (%s) - صفحة واحدة هتتعالج. "
        "لو المستند متعدد الصفحات لازم العميل يبعت الـ PDF كامل.",
        image.filename,
    )
    return [data]


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "model": settings.default_model}


@app.get("/document-types", response_model=dict[str, DocumentTypeConfig])
def get_document_types() -> dict[str, DocumentTypeConfig]:
    """يرجّع كل أنواع المستندات المدعومة وحقولها."""
    return DOCUMENT_TYPES


@app.post("/extract")
async def extract(
    image: UploadFile = File(...),
    fields: str | None = Form(None, description="أسماء حقول مفصولة بفاصلة"),
    doc_type: str = Form(DEFAULT_DOC_TYPE),
) -> JSONResponse:
    """استخراج حقول محددة من المستند وإرجاعها كـ JSON."""
    field_list = (
        [f.strip() for f in fields.split(",") if f.strip()]
        if fields
        else get_fields_for_doc_type(doc_type)
    )

    pages = await _read_pages(image)

    # الحقول عادة كلها في الصفحة الأولى. بنكمل على الصفحات اللي بعدها بس لو
    # فضل حقل فاضي (زي التوقيع/التاريخ في آخر صفحة من مرسوم متعدد الصفحات)،
    # وبنوقف أول ما يتملّى كل حاجة - مفيش نداء زيادة على الموديل من غير داعي.
    page_results: list[dict] = []
    for index, page_bytes in enumerate(pages):
        page_results.append(await extract_fields(page_bytes, field_list, doc_type=doc_type))
        merged = merge_page_fields(page_results, field_list)
        if all(v not in (None, "", [], {}) for v in merged.values()):
            break
        if index + 1 < len(pages):
            logger.info("فيه حقول لسه فاضية بعد صفحة %d، هنكمل للصفحة اللي بعدها.", index + 1)

    return JSONResponse(content=merge_page_fields(page_results, field_list))


@app.post("/extract-all-text", response_model=ExtractAllTextResponse)
async def extract_all_text_route(image: UploadFile = File(...)) -> ExtractAllTextResponse:
    """استخراج النص الكامل من المستند (كل صفحاته لو PDF)."""
    pages = await _read_pages(image)

    page_texts: list[str] = []
    for index, page_bytes in enumerate(pages, start=1):
        logger.info("استخراج النص من صفحة %d من %d", index, len(pages))
        page_texts.append(await extract_all_text(page_bytes))

    if len(page_texts) == 1:
        text = page_texts[0]
    else:
        text = "".join(
            settings.page_separator.format(page=i) + page_text
            for i, page_text in enumerate(page_texts, start=1)
        ).strip()

    original_name = Path(image.filename or "document").stem
    file_name = f"{original_name}_{uuid.uuid4().hex[:8]}.txt"
    file_path = settings.resolved_output_dir / file_name
    file_path.write_text(text, encoding="utf-8")

    logger.info("خلص استخراج النص: %d صفحة، %d حرف.", len(page_texts), len(text))

    return ExtractAllTextResponse(
        text=text,
        file_name=file_name,
        download_url=f"/ocr/download-text/{file_name}",
        page_count=len(page_texts),
        pages=[PageText(page=i, text=t) for i, t in enumerate(page_texts, start=1)],
    )


@app.get("/download-text/{file_name}")
def download_text(file_name: str) -> FileResponse:
    """تحميل ملف الـ txt الناتج من /extract-all-text."""
    safe_name = Path(file_name).name
    file_path = settings.resolved_output_dir / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="الملف غير موجود")

    return FileResponse(path=file_path, media_type="text/plain; charset=utf-8", filename=safe_name)