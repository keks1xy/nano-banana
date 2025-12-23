from flask import Flask, request, render_template
import time

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    prompt = None
    status = None

    if request.method == "POST":
        prompt = request.form.get("prompt")
        status = "processing"
        time.sleep(2)  # имитация работы
        status = "done"

    return render_template("index.html", prompt=prompt, status=status)
