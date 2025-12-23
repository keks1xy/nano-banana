from flask import Flask, request, render_template

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    prompt = None
    if request.method == "POST":
        prompt = request.form.get("prompt")
    return render_template("index.html", prompt=prompt)
