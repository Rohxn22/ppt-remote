# app_gui.py
"""
NO-TRAY GUI for remote_ppt — polished:
- Dark phone UI served from templates/index.html
- Server status shows a green dot when running (no IP displayed)
- Show QR in a popup (QR image + Copy URL + Open)
- No tray implementation
"""

import threading
import os
import logging
import webbrowser
import socket
import time
import sys
import urllib.request

import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("remote_ppt_gui")

# Config - ensure server binds to 0.0.0.0 in server.py for phone reachability
HOST = os.environ.get("PPT_REMOTE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PPT_REMOTE_PORT", "5000"))

POLL_TIMEOUT = 0.5
POLL_MAX_SECONDS = 10.0

# ---------------- helper funcs ----------------
def get_local_ip():
    """Used only internally when needed; GUI will not display it."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def is_server_up(host="127.0.0.1", port=5000, timeout=1.0):
    url = f"http://{host}:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False

# ---------------- QR helpers ----------------
def _make_qr_image(url, size=360):
    try:
        import qrcode
    except Exception:
        raise RuntimeError("Install QR package: pip install qrcode[pil]")
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img = img.resize((size, size))
    return img

def show_qr_popup(parent, url):
    """
    Show a popup containing only the QR, a Copy button and an Open button.
    The popup intentionally does NOT display the IP text.
    """
    try:
        img = _make_qr_image(url, size=360)
    except Exception as e:
        messagebox.showerror("QR Error", f"Could not generate QR: {e}")
        return

    popup = tk.Toplevel(parent)
    popup.title("Scan QR to open Remote")
    popup.resizable(False, False)

    tkimg = ImageTk.PhotoImage(img)
    lbl = tk.Label(popup, image=tkimg)
    lbl.image = tkimg
    lbl.pack(padx=12, pady=(12, 8))

    # Buttons row
    btn_frame = tk.Frame(popup)
    btn_frame.pack(pady=(0, 12))

    def copy_url():
        try:
            parent.clipboard_clear()
            parent.clipboard_append(url)
            parent.update()  # keep clipboard content
            messagebox.showinfo("Copied", "URL copied to clipboard")
        except Exception:
            messagebox.showwarning("Copy failed", "Could not copy URL to clipboard")

    def open_url():
        webbrowser.open(url)

    copy_btn = tk.Button(btn_frame, text="Copy URL", width=12, command=copy_url)
    copy_btn.pack(side="left", padx=8)
    open_btn = tk.Button(btn_frame, text="Open in browser", width=14, command=open_url)
    open_btn.pack(side="left", padx=8)

    # center popup over parent
    parent.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    sw = popup.winfo_reqwidth()
    sh = popup.winfo_reqheight()
    x = px + max(10, (pw - sw) // 2)
    y = py + max(10, (ph - sh) // 2)
    popup.geometry(f"+{x}+{y}")

    popup.grab_set()
    popup.focus_force()

# ---------------- server thread ----------------
def start_server():
    """
    Import server.py and serve using waitress. Run in daemon thread.
    """
    try:
        import server
    except Exception as e:
        logger.exception("Failed to import server.py: %s", e)
        return

    try:
        from waitress import serve
    except Exception as e:
        logger.exception("waitress not installed: %s", e)
        return

    logger.info("Starting waitress on %s:%s", HOST, PORT)
    try:
        serve(server.app, host=HOST, port=PORT, threads=4)
    except Exception:
        logger.exception("waitress serve failed")

server_thread = threading.Thread(target=start_server, daemon=True)

# ---------------- GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("remote_ppt")
        root.geometry("420x200")
        root.minsize(380, 180)

        try:
            root.eval('tk::PlaceWindow . center')
        except Exception:
            pass

        # Frame
        frame = tk.Frame(root, padx=14, pady=10)
        frame.pack(fill="both", expand=True)

        # Title
        title = tk.Label(frame, text="remote_ppt", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0,8))

        # Server status area: a small colored dot + text ("Running")
        self.status_canvas = tk.Canvas(frame, width=18, height=18, highlightthickness=0, bg=root.cget("bg"))
        self.status_canvas.grid(row=0, column=1, sticky="e", padx=(0,0))
        # initial: orange dot (starting)
        self._status_dot = self.status_canvas.create_oval(2,2,16,16, fill="#f39c12", outline="")

        # hidden label next to dot (no IP)
        self.status_var = tk.StringVar(value="Starting...")
        self.status_label = tk.Label(frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0,10))

        # Buttons
        btn_opts = {"width":16, "padx":6, "pady":6}
        self.open_btn = tk.Button(frame, text="Open UI", command=self.open_ui, **btn_opts)
        self.qr_btn = tk.Button(frame, text="Show QR", command=self.show_qr, **btn_opts)
        self.quit_btn = tk.Button(frame, text="Quit", command=self.quit, fg="white", bg="#c0392b", **btn_opts)

        self.open_btn.grid(row=2, column=0, sticky="w", padx=8, pady=8)
        self.qr_btn.grid(row=2, column=1, sticky="e", padx=8, pady=8)
        self.quit_btn.grid(row=3, column=0, columnspan=2, pady=(8,0))

        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        root.protocol("WM_DELETE_WINDOW", self.quit)

    def set_status_running(self):
        # turn dot green and change text (no ip shown)
        def _upd():
            self.status_canvas.itemconfig(self._status_dot, fill="#2ecc71")  # green
            self.status_var.set("Server running")
            self.status_label.config(fg="#2ecc71")
        self.root.after(0, _upd)

    def set_status_failed(self):
        def _upd():
            self.status_canvas.itemconfig(self._status_dot, fill="#e74c3c")
            self.status_var.set("Server failed")
            self.status_label.config(fg="#e74c3c")
        self.root.after(0, _upd)

    def open_ui(self):
        # open UI using LAN IP under the hood, but we don't display it
        ip = get_local_ip()
        url = f"http://{ip}:{PORT}/"
        webbrowser.open(url)

    def show_qr(self):
        ip = get_local_ip()
        url = f"http://{ip}:{PORT}/"
        show_qr_popup(self.root, url)

    def quit(self):
        if messagebox.askyesno("Quit remote_ppt", "Close this app and stop server?"):
            os._exit(0)

# ---------------- poller ----------------
def wait_for_server(app_obj):
    app_obj.status_var.set("Starting...")
    start = time.time()
    while True:
        if is_server_up("127.0.0.1", PORT, timeout=1.0):
            app_obj.set_status_running()
            logger.info("Server reachable locally")
            return
        if time.time() - start > POLL_MAX_SECONDS:
            app_obj.set_status_failed()
            logger.warning("Server not reachable after timeout")
            return
        time.sleep(POLL_TIMEOUT)

def main():
    logger.info("Starting GUI + server")
    server_thread.start()
    time.sleep(0.12)

    root = tk.Tk()
    app = App(root)

    # start background poller thread to update status (dot + label)
    poller = threading.Thread(target=wait_for_server, args=(app,), daemon=True)
    poller.start()

    root.mainloop()

if __name__ == "__main__":
    main()
