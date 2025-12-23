from flask import Flask, request, render_template
import threading
import time
import uuid

app = Flask(__name__)

# Хранилище задач
# job_id -> { status: "...", images?: [...] }
jobs = {}


def worker(job_id, prompt):
    # Задача ушла в обработку
    jobs[job_id] = {"status": "processing"}

    # Имитируем долгую AI-генерацию
    time.sleep(3)

    # Фейковые картинки (как будто Higgsfield)
    fake_images = [
        "https://picsum.photos/seed/food1/1024/1024",
        "https://picsum.photos/seed/food2/1024/1024",
        "https://picsum.photos/seed/food3/1024/1024",
        "https://picsum.photos/seed/food4/1024/1024",
    ]

    # Задача завершена
    jobs[job_id] = {
        "status": "done",
        "images": fake_images
    }


@app.route("/", methods=["GET", "POST"])
def home():
    job_id = None
    status = None

    if request.method == "POST":
        prompt = request.form.get("prompt")

        # создаём задачу
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"status": "queued"}

        # запускаем фоновую обработку
        t = threading.Thread(target=worker, args=(job_id, prompt))
        t.start()

    if job_id:
        status = jobs.get(job_id, {}).get("status")

    return render_template(
        "index.html",
        job_id=job_id,
        status=status,
    )


@app.route("/status/<job_id>")
def job_status(job_id):
    # Возвращаем ВСЮ задачу (status + images)
    return jobs.get(job_id, {"status": "unknown"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
