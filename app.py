from flask import Flask, request, render_template
import threading
import time
import uuid

app = Flask(__name__)

jobs = {}  # job_id -> dict


def worker(job_id, prompt, format):
    try:
        jobs[job_id]["status"] = "processing"

        time.sleep(3)  # имитация генерации

        images = [
            f"https://picsum.photos/seed/{uuid.uuid4().hex}/1024/1024"
            for _ in range(4)
        ]

        jobs[job_id]["status"] = "done"
        jobs[job_id]["images"] = images

    except Exception:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["images"] = []


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
            args=(job_id, prompt, format),
            daemon=True
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
        return {"status": "unknown", "images": []}

    return {
        "status": job["status"],
        "images": job.get("images", [])
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
