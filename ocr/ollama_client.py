"""
عميل Ollama غير متزامن (async) بـ semaphore بيسمح بطلب واحد في نفس اللحظة.

- httpx.AsyncClient بدل requests: انتظار رد Ollama non-blocking فعليًا، فالسيرفر
  بيقدر يستقبل طلبات تانية بدل ما الـ event loop يقف 900 ثانية.
- Semaphore(1): Ollama على CPU بيتخنق لو جاله طلبين مع بعض، والطلبات المتوازية
  بتخلي الموديل يتعمله swap. الطابور أسرع فعليًا من التوازي هنا.
- top_k=1 / top_p=1.0 / seed=0 / temperature=0: greedy decoding كامل - نفس
  الصورة لازم تدّي نفس النص كل مرة.
"""

import asyncio
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# module-level — instance واحدة تتشارك بين كل الريكوستات اللي بتيجي للسيرفر
_ollama_lock = asyncio.Semaphore(1)  # 1 = طلب واحد بس في نفس اللحظة


async def generate(
    *,
    prompt: str,
    image_b64: str,
    num_predict: int,
    temperature: float = 0,
    response_format_json: bool = False,
) -> str:
    payload: dict[str, Any] = {
        "model": settings.default_model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "num_ctx": settings.ollama_num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            # لازم تتبعت صريحة: default Ollama = 1.1 وده بيخلي الموديل يتفادى
            # تكرار الجمل المتكررة فعليًا في النصوص النظامية فيغيّر كلماتها.
            "repeat_penalty": settings.ollama_repeat_penalty,
            # greedy decoding كامل - نفس الصورة لازم تدّي نفس النص كل مرة.
            "top_k": 1,
            "top_p": 1.0,
            "seed": 0,
        },
    }
    if response_format_json:
        payload["format"] = "json"

    async with _ollama_lock:  # هنا السحر — أي طلب تاني هيستنى لحد ما ده يخلص
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.post(settings.ollama_url, json=payload)
        except httpx.ConnectError as exc:
            logger.error("فشل الاتصال بـ Ollama على %s: %s", settings.ollama_url, exc)
            raise HTTPException(status_code=503, detail="Ollama غير شغال. شغّل: ollama serve") from exc
        except httpx.ReadTimeout as exc:
            logger.error(
                "انتهت مهلة الانتظار (%.0f ثانية) بدون رد من الموديل '%s'.",
                settings.request_timeout_seconds, settings.default_model,
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    f"الموديل أخد وقت أطول من {settings.request_timeout_seconds:.0f} ثانية ولم يرد. "
                    "جرب موديل أصغر (مثل qwen2.5vl:3b) أو صورة أصغر حجماً."
                ),
            ) from exc

    if response.status_code != 200:
        logger.error(
            "Ollama رجّع status code %s. الرد: %s",
            response.status_code, response.text[:500],
        )
        raise HTTPException(status_code=502, detail=f"Ollama خطأ {response.status_code}: {response.text}")

    data = response.json()

    # done_reason بيقول الموديل وقف ليه: "stop" يعني قرر إنه خلص لوحده،
    # و"length" يعني اصطدم بسقف num_predict. الفرق ده مهم جدًا في التشخيص:
    # نص ناقص + "stop" = الموديل فاكر إنه خلص (مشكلة قراءة)، بينما نص ناقص +
    # "length" = السقف صغير أو الموديل دخل في لوب أكل الـtokens.
    logger.info(
        "رد الموديل: done_reason=%s | tokens=%s | مدة التوليد=%.1f ث",
        data.get("done_reason"),
        data.get("eval_count"),
        data.get("eval_duration", 0) / 1e9,
    )

    return data.get("response", "")
