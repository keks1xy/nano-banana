from flask import Flask, request, render_template, jsonify
import threading
import time
import uuid

app = Flask(__name__)

jobs = {}  # job_id -> {status, images}


def worker(job_id, prompt, format):
    jobs[job_id]["status"] = "processing"

    time.sleep(3)  # имитация генерации

    # ФЕЙКОВЫЕ КАРТИНКИ (пока без Banana)
    images = [
        "https://picsum.photos/seed/a/1024/1024",
        "https://picsum.photos/seed/b/1024/1024",
        "https://picsum.photos/seed/c/1024/1024",
        "https://picsum.photos/seed/d/1024/1024",
    ]

    jobs[job_id]["status"] = "done"
    jobs[job_id]["images"] = images


@app.route("/", methods=["GET", "POST"])
def home():
    job_id = None
    status = None

    if request.method == "POST":
        prompt = request.form.get("prompt")
        format = request.form.get("format")

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "queued",
            "images": []
        }

        t = threading.Thread(
            target=worker,
            args=(job_id, prompt, format)
        )
        t.start()

    if job_id:
        status = jobs[job_id]["status"]

    return render_template(
        "index.html",
        job_id=job_id,
        status=status
    )


@app.route("/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)

    if not job:
        return jsonify({"status": "unknown"})

    return jsonify({
        "status": job["status"],
        "images": job.get("images", [])
    })
