from flask import Flask, request, render_template
import threading
import time
import uuid

app = Flask(__name__)

jobs = {}  # id -> status


def worker(job_id, prompt):
    jobs[job_id] = "processing"
    time.sleep(3)  # имитация долгой работы
    jobs[job_id] = "done"


@app.route("/", methods=["GET", "POST"])
def home():
    job_id = None
    status = None

    if request.method == "POST":
        prompt = request.form.get("prompt")
        job_id = str(uuid.uuid4())
        jobs[job_id] = "queued"

        t = threading.Thread(target=worker, args=(job_id, prompt))
        t.start()

    if job_id:
        status = jobs.get(job_id)

    return render_template(
        "index.html",
        job_id=job_id,
        status=status,
    )
