from flask import Flask, request, render_template, jsonify
import base64
import json
import os
import threading
import uuid

from google import genai

app = Flask(__name__)

client = genai.Client()  # ключ берётся из переменной окружения GEMINI_API_KEY

jobs = {}  # job_id -> dict
history = []  # list of completed jobs


def call_gemini_api(prompt, aspect_ratio="1:1", references=None, count=4):
    contents = [prompt or ""]

    if references:
        for ref in references:
            data_url = ref.get("data_url") or ""
            if "," not in data_url:
                continue
            _, data = data_url.split(",", 1)
            contents.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": data,
                    }
                }
            )

    response = client.models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=contents,
    )

    images = []
    candidate = response.candidates[0].content.parts if response.candidates else []
    for part in candidate:
        if getattr(part, "inline_data", None):
            images.append(f"data:image/png;base64,{part.inline_data.data}")

    if not images:
        raise RuntimeError("No images returned from Gemini")

    return images[: max(1, min(count, 4))]


def worker(job_id, prompt, format, references, count):
    try:
        jobs[job_id]["status"] = "processing"

        images = call_gemini_api(
            prompt=prompt,
            aspect_ratio=format,
            references=references,
            count=count,
        )

        jobs[job_id]["status"] = "done"
        jobs[job_id]["images"] = images
        history.append(
            {
                "job_id": job_id,
                "prompt": prompt,
                "format": format,
                "images": images,
                "references": jobs[job_id].get("references", []),
                "status": jobs[job_id]["status"],
            }
        )

    except Exception:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["images"] = []


def create_job(prompt, format, references, count):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "queued",
        "images": [],
        "prompt": prompt or "",
        "format": format or "",
        "references": references,
        "count": count,
    }

    t = threading.Thread(
        target=worker,
        args=(job_id, prompt, format, references, count),
        daemon=True,
    )
    t.start()
    return job_id


@app.route("/", methods=["GET", "POST"])
def home():
    job_id = None
    status = None
    references = []
    error = None
    count = 4

    if request.method == "POST":
        prompt = request.form.get("prompt")
        format = request.form.get("format")
        files = request.files.getlist("references")
        count_raw = request.form.get("count") or "4"
        try:
            count = int(count_raw)
        except Exception:
            count = 4
        count = max(1, min(count, 4))
        stored_refs_raw = request.form.get("stored_refs") or "[]"

        try:
            references = json.loads(stored_refs_raw)
        except Exception:
            references = []

        for file in files:
            if not file:
                continue

            encoded = base64.b64encode(file.read()).decode("utf-8")
            mime = file.mimetype or "application/octet-stream"
            references.append(
                {
                    "name": file.filename or "reference",
                    "data_url": f"data:{mime};base64,{encoded}",
                }
            )

        if not prompt or len(prompt.strip()) < 10:
            error = "Промпт должен содержать минимум 10 символов"
            return render_template(
                "index.html",
                job_id=None,
                status=None,
                references=references,
                history=history,
                error=error,
                count=count,
            )

        job_id = create_job(prompt, format, references, count)

    if job_id:
        status = jobs[job_id]["status"]

    return render_template(
        "index.html",
        job_id=job_id,
        status=status,
        references=references,
        history=history,
        error=error,
        count=count,
    )


@app.route("/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)

    if not job:
        return {"status": "unknown", "images": []}

    return {
        "status": job["status"],
        "images": job.get("images", []),
        "prompt": job.get("prompt", ""),
        "format": job.get("format", ""),
        "references": job.get("references", []),
        "count": job.get("count", 4),
    }


@app.route("/history")
def job_history():
    return {"history": history}


@app.route("/api/generate", methods=["POST"])
def api_generate():
    prompt = request.form.get("prompt")
    format = request.form.get("format") or "1:1"
    files = request.files.getlist("references")
    count_raw = request.form.get("count") or "4"
    try:
        count = int(count_raw)
    except Exception:
        count = 4
    count = max(1, min(count, 4))
    stored_refs_raw = request.form.get("stored_refs") or "[]"

    try:
        references = json.loads(stored_refs_raw)
    except Exception:
        references = []

    for file in files:
        if not file:
            continue
        encoded = base64.b64encode(file.read()).decode("utf-8")
        mime = file.mimetype or "application/octet-stream"
        references.append(
            {
                "name": file.filename or "reference",
                "data_url": f"data:{mime};base64,{encoded}",
            }
        )

    if not prompt or len(prompt.strip()) < 10:
        return jsonify({"error": "Промпт должен содержать минмум 10 символов"}), 400

    job_id = create_job(prompt, format, references, count)
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/editor")
def editor():
    return render_template("editor.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
