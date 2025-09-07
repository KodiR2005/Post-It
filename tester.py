import os
from flask import Flask, render_template
from livereload import Server
from threading import Thread
from pyngrok import ngrok
import webbrowser
from colorama import Fore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=BASE_DIR)

@app.route("/")
def index():
    return render_template("base.html")

def start_ngrok():
    tunnel = ngrok.connect(5000)
    print(Fore.BLUE + f"Ngrok URL: {tunnel.public_url}")
    webbrowser.open(tunnel.public_url)

if __name__ == "__main__":
    Thread(target=start_ngrok, daemon=True).start()

    server = Server(app.wsgi_app)
    server.watch(os.path.join(BASE_DIR, "base.html"))
    server.watch(os.path.join(BASE_DIR, "static/"))
    server.serve(host="0.0.0.0", port=5000, debug=True)  # ← removed liveport
