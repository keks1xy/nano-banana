from flask import Flask, request, render_template, jsonify
import base64
import json
import os
import threading
import time
import uuid

from google import genai

app = Flask(__name__)

# Берёт ключ из переменной окружения GEMINI_API_KEY
# Railway: Variables -> GEMINI_API_KEY
client = None


def _client():
    global client
    if client is None:
        if not os.environ.get("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is не задан")
        client = genai.Client()
    return client

# In-memory storage (после рестарта Railway история обнуляется — это нормально без БД)
jobs = {}      # job_id -> dict(status, images, prompt, format, count, error)
history = []   # list of completed jobs
lock = threading.Lock()


def _parse_data_url(data_url: str):
    """
    data:image/png;base64,AAAA...
    -> (mime, base64data)
    """
    if not data_url or "," not in data_url:
        return None, None
    head, b64 = data_url.split(",", 1)
    mime = "image/png"
    if head.startswith("data:") and ";base64" in head:
        mime = head[5:].split(";base64", 1)[0] or "image/png"
    return mime, b64


def call_gemini_image(prompt: str, references=None, count: int = 4):
    """
    Возвращает список data:image/...;base64,... (до 4 шт)
    """
    # Собираем contents: текст + inline images
    contents = [{"text": (prompt or "").strip()}]

    if references:
        for ref in references[:10]:
            data_url = ref.get("data_url", "")
            mime, b64 = _parse_data_url(data_url)
            if not mime or not b64:
                continue
            contents.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": b64
                }
            })

    # Модель для image preview (если у тебя другая — поменяй здесь)
    response = _client().models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=contents,
    )

    images = []
    candidates = getattr(response, "candidates", []) or []
    if not candidates:
        raise RuntimeError("Gemini: empty candidates")

    parts = getattr(candidates[0].content, "parts", []) or []
    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            # inline.data обычно уже base64-строка
            data = inline.data
            if isinstance(data, (bytes, bytearray)):
                data = base64.b64encode(data).decode("utf-8")
            mime = getattr(inline, "mime_type", None) or "image/png"
            images.append(f"data:{mime};base64,{data}")

    if not images:
        raise RuntimeError("Gemini: no images in response")

    count = max(1, min(int(count or 4), 4))
    return images[:count]


def worker(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if not job:
            return
        job["status"] = "processing"
        job["error"] = None

    try:
        images = call_gemini_image(
            prompt=job.get("prompt", ""),
            references=job.get("references", []),
            count=job.get("count", 4),
        )

        with lock:
            job["status"] = "done"
            job["images"] = images

            history.append({
                "job_id": job_id,
                "time": time.strftime("%d.%m.%Y, %H:%М:%S"),
                "prompt": job.get("prompt", ""),
                "format": job.get("format", "1:1"),   # формат сейчас как метка UI
                "count": job.get("count", 4),
                "images": images,
            })

            # чуть ограничим историю, чтобы не раздувалась
            if len(history) > 50:
                history[:] = history[-50:]

    except Exception as e:
        with lock:
            job["status"] = "error"
            job["images"] = []
            job["error"] = str(e)


@app.route("/", methods=["GET", "POST"])
def home():
    job_id = None
    status = None
    error = None

    if request.method == "POST":
        prompt = (request.form.get("prompt") or "").strip()
        fmt = (request.form.get("format") or "1:1").strip()
        count_raw = request.form.get("count") or "4"

        try:
            count = int(count_raw)
        except Exception:
            count = 4
        count = max(1, min(count, 4))

        # stored_refs — приходит из JS, там base64 data_url
        stored_refs_raw = request.form.get("stored_refs") or "[]"
        try:
            refs = json.loads(stored_refs_raw)
            if not isinstance(refs, list):
                refs = []
        except Exception:
            refs = []

        # ограничение на 10
        refs = refs[:10]

        if len(prompt) < 10:
            error = "Промпт должен содержать минимум 10 символов"
            return render_template(
                "index.html",
                job_id=None,
                status=None,
                error=error,
                count=count,
                history=history
            )

        job_id = str(uuid.uuid4())
        with lock:
            jobs[job_id] = {
                "status": "queued",
                "images": [],
                "prompt": prompt,
                "format": fmt,
                "count": count,
                "references": refs,
                "error": None
            }

        t = threading.Thread(target=worker, args=(job_id,), daemon=True)
        t.start()

        status = "queued"

    return render_template(
        "index.html",
        job_id=job_id,
        status=status,
        error=error,
        count=4,
        history=history
    )


@app.route("/status/<job_id>")
def job_status(job_id):
    with lock:
        job = jobs.get(job_id)

        if not job:
            return jsonify({"status": "unknown", "images": [], "error": "job not found"})

        return jsonify({
            "status": job.get("status"),
            "images": job.get("images", []),
            "error": job.get("error"),
            "prompt": job.get("prompt", ""),
            "format": job.get("format", "1:1"),
            "count": job.get("count", 4),
        })


@app.route("/history")
def job_history():
    with lock:
        return jsonify({"history": history})


@app.route("/api/generate_flow", methods=["POST"])
def api_generate_flow():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    references = data.get("references", []) or []
    count = data.get("count") or 1

    if len(prompt) < 3:
        return jsonify({"error": "Промпт должен содержать минимум 3 символа"}), 400

    if not isinstance(references, list):
        references = []
    references = references[:10]

    try:
        images = call_gemini_image(prompt=prompt, references=references, count=count)
        return jsonify({"status": "ok", "images": images})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/modules")
def modules():
    return render_template("modules.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
