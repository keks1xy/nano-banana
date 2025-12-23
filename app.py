from flask import Flask, request, render_template_string

app = Flask(__name__)

HTML = """
<!doctype html>
<html>
<head>
  <title>Nano Banana</title>
</head>
<body>
  <h1>Nano Banana 🍌</h1>

  <form method="post">
    <input name="prompt" placeholder="Введите текст" style="width:300px">
    <button type="submit">Отправить</button>
  </form>

  {% if prompt %}
    <p><b>Вы ввели:</b> {{ prompt }}</p>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    prompt = None
    if request.method == "POST":
        prompt = request.form.get("prompt")
    return render_template_string(HTML, prompt=prompt)
