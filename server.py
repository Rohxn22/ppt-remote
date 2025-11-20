from flask import Flask,request,render_template
import queue, os
app=Flask(__name__,template_folder="templates")
q=queue.Queue()
TOKEN=os.environ.get("PPT_REMOTE_TOKEN","qwerty66*")

@app.route("/")
def home(): return render_template("index.html",token=TOKEN)

@app.route("/press/<key>",methods=["POST"])
def press(key):
    if request.args.get("token")!=TOKEN: return "bad",403
    q.put(key); return "ok"

from threading import Thread
from pynput.keyboard import Controller,Key
def worker():
    kb=Controller()
    while True:
        k=q.get()
        if k=="left": kb.press(Key.left); kb.release(Key.left)
        if k=="right": kb.press(Key.right); kb.release(Key.right)

Thread(target=worker,daemon=True).start()
