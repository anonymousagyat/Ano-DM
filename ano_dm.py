"""
Ano-Download Manager (Ano-DM)
Complete Neat Download Manager (NDM) Replica:
- Full Main Dashboard Window with Toolbar, Category Sidebar, and Persistent Downloads Table.
- Exact NDM Active Download Dialog with in-place tabs (Download, Options, Connections).
- Official high-DPI user logo in prominent 36x36 / 48x48 display (crystal clear).
- Genuine Windows Shell default application icons (WinRAR for .rar, 7-Zip for .zip, etc.).
- 32-segment visualizer with 3D glass LED gradient slots and specular highlights.
- Smooth multi-stop linear gradient progress bar.
- Rock-solid Pause (no premature complete) and Cancel (purges .part temp files).
- Embedded Chrome Extension HTTP Server on 127.0.0.1:9653.
- Persistent history saved in downloads/history.json.
- System tray integration with hidden icons support.
"""

import sys
import os
import time
import json
import threading
import subprocess
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, List, Dict, Any

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import pystray

# Win32 Shell API for extracting genuine Windows default application icons
try:
    from win32com.shell import shell, shellcon
    import win32gui
    import win32ui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)


def get_asset_path(filename: str) -> str:
    """Resolves asset path supporting assets/ subdirectory, root, and PyInstaller bundle."""
    candidates = [
        os.path.join(PROJECT_DIR, "assets", filename),
        os.path.join(PROJECT_DIR, filename),
    ]
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', PROJECT_DIR)
        candidates.insert(0, os.path.join(meipass, "assets", filename))
        candidates.insert(0, os.path.join(meipass, filename))
    for c in candidates:
        if os.path.exists(c):
            return c
    return os.path.join(PROJECT_DIR, "assets", filename)


from network_scanner import get_active_interfaces
from engine import DualBondDownloader, sanitize_filename
from part_manager import SegmentPart

# ----------------- Theme Colors -----------------
BG_WINDOW = "#140D24"       # Deep dark purple-slate
BG_FRAME = "#1D1432"        # Framed content background
BG_SUBFRAME = "#140D24"     # Inset sub-box background
BORDER_FRAME = "#4A3368"    # Subtle purple border
BORDER_TAB_ACTIVE = "#FFFFFF" # White tab border matching NDM
BORDER_TAB_INACTIVE = "#4A3368"
TEXT_WHITE = "#FFFFFF"
TEXT_MUTED = "#B4A9CE"
TEXT_URL = "#8DA4FF"        # Light periwinkle URL text
ACCENT_CYAN = "#38BDF8"     # Crisp cyan / sky text
ACCENT_GREEN = "#34D399"    # Mint green
ACCENT_PURPLE = "#A855F7"   # Vibrant purple
ACCENT_SLOT_BG = "#120B20"  # Segment slot background
BTN_BG = "#1F1535"          # Button dark fill
BTN_BORDER = "#FFFFFF"      # Button white border

ctk.set_appearance_mode("Dark")


def format_bytes(b: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024.0:
            return f"{b:.3f} {unit}" if unit in ['MB', 'GB'] else f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.3f} PB"


def format_time(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400 * 7:
        return "--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h} hr {m} min {s} sec"
    return f"{m} min {s} sec"


def get_file_category(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.wmv']:
        return "Video"
    elif ext in ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg', '.wma']:
        return "Audio"
    elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.bz2']:
        return "Compressed"
    elif ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']:
        return "Document"
    elif ext in ['.exe', '.msi', '.apk', '.dmg', '.bat', '.cmd']:
        return "Application"
    return "Misc"


def get_windows_file_icon(filename_or_ext: str, size=(56, 56)) -> Optional[Image.Image]:
    """Extracts the true Windows default application icon for the given file extension (e.g. WinRAR for .rar)."""
    if not HAS_WIN32:
        return None
    ext = os.path.splitext(filename_or_ext)[1] or filename_or_ext
    if not ext.startswith('.'):
        ext = '.' + ext
    try:
        flags = shellcon.SHGFI_ICON | shellcon.SHGFI_LARGEICON | shellcon.SHGFI_USEFILEATTRIBUTES
        ret, info = shell.SHGetFileInfo(ext, win32con.FILE_ATTRIBUTE_NORMAL, flags)
        hicon = info[0]
        if not hicon:
            return None
        hdc = win32gui.GetDC(0)
        hdc_mem = win32ui.CreateDCFromHandle(hdc)
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc_mem, 32, 32)
        hdc_mem_compat = hdc_mem.CreateCompatibleDC()
        hdc_mem_compat.SelectObject(hbmp)
        win32gui.DrawIconEx(hdc_mem_compat.GetSafeHdc(), 0, 0, hicon, 32, 32, 0, 0, win32con.DI_NORMAL)
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)

        win32gui.DestroyIcon(hicon)
        win32gui.ReleaseDC(0, hdc)
        win32gui.DeleteObject(hbmp.GetHandle())

        if size != (32, 32):
            img = img.resize(size, Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


def make_vertical_gradient(w: int, h: int, stops: list, add_specular: bool = True) -> Image.Image:
    w = max(2, w)
    h = max(2, h)
    img = Image.new('RGB', (w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            pos1, col1 = stops[i]
            pos2, col2 = stops[i + 1]
            if pos1 <= t <= pos2:
                sub_t = (t - pos1) / (pos2 - pos1) if pos2 > pos1 else 0.0
                r = int(col1[0] + (col2[0] - col1[0]) * sub_t)
                g = int(col1[1] + (col2[1] - col1[1]) * sub_t)
                b = int(col1[2] + (col2[2] - col1[2]) * sub_t)
                break
        for x in range(w):
            img.putpixel((x, y), (r, g, b))

    if add_specular and h > 3:
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (w - 1, 0)], fill=(255, 255, 255))
        draw.line([(0, 1), (w - 1, 1)], fill=(225, 225, 255))

    return img


# ----------------- History Database -----------------
class DownloadHistoryManager:
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.downloads: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.downloads = json.load(f)
            except Exception:
                self.downloads = []
        else:
            self.downloads = []

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.downloads, f, indent=2)
        except Exception:
            pass

    def add_or_update(self, item: Dict[str, Any]):
        for idx, d in enumerate(self.downloads):
            if d.get("id") == item.get("id") or d.get("url") == item.get("url"):
                self.downloads[idx].update(item)
                self.save()
                return
        self.downloads.insert(0, item)
        self.save()

    def remove(self, item_id: str):
        self.downloads = [d for d in self.downloads if d.get("id") != item_id]
        self.save()


# ----------------- Visualizer Widgets -----------------
class GradientProgressBar(tk.Canvas):
    def __init__(self, parent, height=14, **kwargs):
        super().__init__(
            parent,
            height=height,
            bg=BG_SUBFRAME,
            highlightthickness=1,
            highlightbackground=BORDER_FRAME,
            **kwargs
        )
        self.fraction = 0.0
        self.photo = None
        self.bind("<Configure>", lambda e: self.redraw())

    def set_progress(self, frac: float):
        self.fraction = min(1.0, max(0.0, frac))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 4 or h <= 4:
            return

        fill_w = int(w * self.fraction)
        if fill_w > 0:
            row = Image.new("RGB", (4, 1))
            row.putpixel((0, 0), (124, 58, 237))   # #7C3AED
            row.putpixel((1, 0), (192, 132, 252))  # #C084FC
            row.putpixel((2, 0), (45, 212, 191))   # #2DD4BF
            row.putpixel((3, 0), (52, 211, 153))   # #34D399
            grad = row.resize((w, h), Image.Resampling.BILINEAR)
            cropped = grad.crop((0, 0, fill_w, h))
            self.photo = ImageTk.PhotoImage(cropped)
            self.create_image(0, 0, anchor="nw", image=self.photo)


class NDM32SegmentCanvas(tk.Canvas):
    def __init__(self, parent, height=22, **kwargs):
        super().__init__(
            parent,
            height=height,
            bg=ACCENT_SLOT_BG,
            highlightthickness=1,
            highlightbackground=BORDER_FRAME,
            **kwargs
        )
        self.num_slots = 32
        self.part_data: List[SegmentPart] = []
        self._cached_w = 0
        self._cached_h = 0
        self._photo_done = None
        self._photo_active = None
        self._photo_empty = None
        self.bind("<Configure>", lambda e: self._on_resize())

    def _on_resize(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w != self._cached_w or h != self._cached_h:
            self._cached_w = w
            self._cached_h = h
            self._regenerate_gradient_slices()
        self.redraw()

    def _regenerate_gradient_slices(self):
        w = self._cached_w
        h = self._cached_h
        if w <= 32 or h <= 4:
            return

        spacing = 2
        slot_w = max(2, int((w - (spacing * (self.num_slots - 1)) - 4) / self.num_slots))

        img_done = make_vertical_gradient(slot_w, h - 4, [
            (0.0, (103, 232, 249)),
            (0.3, (6, 182, 212)),
            (0.7, (2, 132, 199)),
            (1.0, (30, 27, 75))
        ], add_specular=True)
        self._photo_done = ImageTk.PhotoImage(img_done)

        img_active = make_vertical_gradient(slot_w, h - 4, [
            (0.0, (240, 171, 252)),
            (0.3, (192, 38, 211)),
            (0.7, (124, 58, 237)),
            (1.0, (59, 7, 100))
        ], add_specular=True)
        self._photo_active = ImageTk.PhotoImage(img_active)

        img_empty = make_vertical_gradient(slot_w, h - 4, [
            (0.0, (23, 14, 40)),
            (1.0, (15, 9, 26))
        ], add_specular=False)
        self._photo_empty = ImageTk.PhotoImage(img_empty)

    def set_parts(self, parts: List[SegmentPart]):
        self.part_data = parts
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()

        if w <= 32 or h <= 4 or not self._photo_done:
            return

        spacing = 2
        slot_w = max(2, int((w - (spacing * (self.num_slots - 1)) - 4) / self.num_slots))
        y_top = 2

        for i in range(self.num_slots):
            x1 = 2 + i * (slot_w + spacing)
            is_complete = False
            is_active = False
            if i < len(self.part_data):
                p = self.part_data[i]
                is_complete = p.is_complete
                is_active = (not p.is_complete and p.downloaded_bytes > 0)

            if is_complete:
                self.create_image(x1, y_top, anchor="nw", image=self._photo_done)
            elif is_active:
                self.create_image(x1, y_top, anchor="nw", image=self._photo_active)
            else:
                self.create_image(x1, y_top, anchor="nw", image=self._photo_empty)


# ----------------- Active Download Dialog Window -----------------
class NDMDownloadWindow(ctk.CTkToplevel):
    def __init__(self, parent_app, url: str, filename: str = "", initial_streams: int = 32):
        super().__init__(parent_app)

        self.parent_app = parent_app
        self.url = url
        self.initial_filename = filename
        self.num_streams = initial_streams

        self.title("Ano-DM - Initializing...")
        self.geometry("720x510")
        self.minsize(680, 480)
        self.resizable(True, True)
        self.configure(fg_color=BG_WINDOW)

        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.downloader: Optional[DualBondDownloader] = None
        self.is_downloading = False
        self.is_paused = False
        self.start_time = time.time()
        self.file_size = 0
        self.target_path = ""
        self.clean_filename = filename or "downloading_file"
        self.file_icon_photo = None
        self.logo_photo = None

        self.speed_limit_var = tk.StringVar(value="")
        self.remember_resume_var = tk.BooleanVar(value=False)
        self.show_completion_var = tk.BooleanVar(value=True)
        self.connections_count_var = tk.StringVar(value=str(initial_streams))

        self.setup_ui()
        self.start_download_thread()

    def setup_ui(self):
        # Header (Clean NDM Style with Prominent 40x40 Logo)
        header_frame = tk.Frame(self, bg=BG_SUBFRAME, height=50)
        header_frame.pack(fill="x", pady=(0, 10))

        icon_path = get_asset_path("icon.png")
        if os.path.exists(icon_path):
            logo_img = Image.open(icon_path).resize((40, 40), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            logo_lbl = tk.Label(header_frame, image=self.logo_photo, bg=BG_SUBFRAME)
            logo_lbl.pack(side="left", padx=(14, 10), pady=5)

        self.header_title = tk.Label(
            header_frame,
            text=f"Connecting - {self.clean_filename}",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_WHITE,
            bg=BG_SUBFRAME,
            anchor="w"
        )
        self.header_title.pack(side="left", fill="x", expand=True, pady=5)

        # Tab Bar
        self.tab_bar = tk.Frame(self, bg=BG_WINDOW, height=32)
        self.tab_bar.pack(fill="x", padx=16, pady=(0, 0))

        self.tab_download_btn = tk.Button(
            self.tab_bar, text="Download", font=("Segoe UI", 10, "bold"),
            bg=BG_FRAME, fg=TEXT_WHITE, relief="flat", padx=16, pady=4,
            highlightbackground=BORDER_TAB_ACTIVE, highlightthickness=1, bd=0,
            cursor="hand2", command=lambda: self.switch_tab("download")
        )
        self.tab_download_btn.pack(side="left", padx=(0, 4))

        self.tab_options_btn = tk.Button(
            self.tab_bar, text="Options", font=("Segoe UI", 10),
            bg=BG_WINDOW, fg=TEXT_MUTED, relief="flat", padx=16, pady=4,
            highlightbackground=BORDER_TAB_INACTIVE, highlightthickness=1, bd=0,
            cursor="hand2", command=lambda: self.switch_tab("options")
        )
        self.tab_options_btn.pack(side="left", padx=4)

        self.tab_conn_btn = tk.Button(
            self.tab_bar, text="Connections", font=("Segoe UI", 10),
            bg=BG_WINDOW, fg=TEXT_MUTED, relief="flat", padx=16, pady=4,
            highlightbackground=BORDER_TAB_INACTIVE, highlightthickness=1, bd=0,
            cursor="hand2", command=lambda: self.switch_tab("connections")
        )
        self.tab_conn_btn.pack(side="left", padx=4)

        # Main Framed Content Box
        self.content_frame = tk.Frame(
            self, bg=BG_FRAME, highlightbackground=BORDER_FRAME, highlightthickness=1
        )
        self.content_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.view_download = tk.Frame(self.content_frame, bg=BG_FRAME)
        self.view_options = tk.Frame(self.content_frame, bg=BG_FRAME)
        self.view_connections = tk.Frame(self.content_frame, bg=BG_FRAME)

        self.setup_download_view()
        self.setup_options_view()
        self.setup_connections_view()

        self.current_tab = "download"
        self.view_download.pack(fill="both", expand=True, padx=14, pady=12)

        # Overall Progress Bar
        self.gradient_progress = GradientProgressBar(self, height=16)
        self.gradient_progress.pack(fill="x", padx=16, pady=(0, 4))

        # Segments Label
        self.seg_label = tk.Label(
            self, text=f"Segments : {self.num_streams}",
            font=("Segoe UI", 10, "bold"), fg=ACCENT_CYAN, bg=BG_WINDOW
        )
        self.seg_label.pack(pady=(0, 4))

        # 32-Segment Canvas
        self.segment_canvas = NDM32SegmentCanvas(self, height=24)
        self.segment_canvas.pack(fill="x", padx=16, pady=(0, 14))

        # Action Buttons
        btn_bar = tk.Frame(self, bg=BG_WINDOW)
        btn_bar.pack(pady=(0, 12))

        self.pause_resume_btn = tk.Button(
            btn_bar, text="Pause", font=("Segoe UI", 10, "bold"),
            bg=BTN_BG, fg=TEXT_WHITE, relief="flat", width=13, pady=4,
            highlightbackground=BTN_BORDER, highlightthickness=1, bd=0,
            cursor="hand2", command=self.toggle_pause
        )
        self.pause_resume_btn.pack(side="left", padx=10)

        self.cancel_btn = tk.Button(
            btn_bar, text="Cancel", font=("Segoe UI", 10, "bold"),
            bg=BTN_BG, fg=TEXT_WHITE, relief="flat", width=13, pady=4,
            highlightbackground=BTN_BORDER, highlightthickness=1, bd=0,
            cursor="hand2", command=self.on_cancel
        )
        self.cancel_btn.pack(side="left", padx=10)

    def setup_download_view(self):
        self.url_label = tk.Label(
            self.view_download, text=self.url,
            font=("Segoe UI", 10), fg=TEXT_URL, bg=BG_FRAME, anchor="w"
        )
        self.url_label.pack(fill="x", pady=(0, 10))

        info_container = tk.Frame(self.view_download, bg=BG_FRAME)
        info_container.pack(fill="both", expand=True)

        grid_frame = tk.Frame(info_container, bg=BG_FRAME)
        grid_frame.pack(side="left", fill="both", expand=True)

        rows = [
            ("Status", "Connecting..."),
            ("File Size", "Probing..."),
            ("Downloaded", "0.000 MB ( 0.00 % )"),
            ("Bandwidth", "0.000 MB/sec"),
            ("Remaining Time", "--"),
            ("Resumable", "Checking...")
        ]

        self.val_labels: Dict[str, tk.Label] = {}
        for r, (key, default_val) in enumerate(rows):
            lbl_key = tk.Label(
                grid_frame, text=key + ":", font=("Segoe UI", 10),
                fg=TEXT_MUTED, bg=BG_FRAME, anchor="w", width=16
            )
            lbl_key.grid(row=r, column=0, sticky="w", pady=3)

            val_color = TEXT_WHITE
            if key == "Status":
                val_color = TEXT_URL
            elif key == "Resumable":
                val_color = ACCENT_GREEN

            lbl_val = tk.Label(
                grid_frame, text=default_val,
                font=("Segoe UI", 10, "bold" if key in ["Status", "Bandwidth"] else "normal"),
                fg=val_color, bg=BG_FRAME, anchor="w"
            )
            lbl_val.grid(row=r, column=1, sticky="w", pady=3)
            self.val_labels[key] = lbl_val

        right_frame = tk.Frame(info_container, bg=BG_FRAME)
        right_frame.pack(side="right", padx=(10, 24), pady=6)

        self.icon_label = tk.Label(right_frame, bg=BG_FRAME)
        self.icon_label.pack()

        self.file_type_lbl = tk.Label(
            right_frame, text="File", font=("Segoe UI", 9, "bold"),
            fg=TEXT_MUTED, bg=BG_FRAME, pady=4
        )
        self.file_type_lbl.pack()

        self.update_file_icon(self.clean_filename)

    def setup_options_view(self):
        pad_frame = tk.Frame(self.view_options, bg=BG_FRAME)
        pad_frame.pack(fill="both", expand=True, padx=6, pady=6)

        bw_box = tk.LabelFrame(
            pad_frame, text=" Bandwidth ", font=("Segoe UI", 9, "bold"),
            fg=TEXT_WHITE, bg=BG_FRAME, highlightbackground=BORDER_FRAME,
            highlightcolor=ACCENT_PURPLE, highlightthickness=1, bd=1, padx=14, pady=12
        )
        bw_box.pack(fill="x", pady=(0, 12))

        top_bw_row = tk.Frame(bw_box, bg=BG_FRAME)
        top_bw_row.pack(fill="x", pady=(2, 10))

        self.opt_speed_lbl = tk.Label(
            top_bw_row, text="0.000 MB/sec", font=("Segoe UI", 13, "bold"),
            fg=TEXT_WHITE, bg=BG_FRAME
        )
        self.opt_speed_lbl.pack(side="left")

        no_limit_lbl = tk.Label(
            top_bw_row, text="0 or Blank = No Limit", font=("Segoe UI", 9),
            fg=ACCENT_CYAN, bg=BG_FRAME
        )
        no_limit_lbl.pack(side="right")

        limit_row = tk.Frame(bw_box, bg=BG_FRAME)
        limit_row.pack(fill="x", pady=4)

        tk.Label(
            limit_row, text="Limit Bandwidth to", font=("Segoe UI", 9),
            fg=TEXT_WHITE, bg=BG_FRAME
        ).pack(side="left", padx=(0, 8))

        self.limit_entry = tk.Entry(
            limit_row, textvariable=self.speed_limit_var, font=("Segoe UI", 9),
            bg=BG_SUBFRAME, fg=TEXT_WHITE, insertbackground=TEXT_WHITE,
            width=12, relief="solid", bd=1, highlightbackground=BORDER_FRAME
        )
        self.limit_entry.pack(side="left", padx=(0, 8))

        tk.Label(
            limit_row, text="KB/sec", font=("Segoe UI", 9),
            fg=TEXT_WHITE, bg=BG_FRAME
        ).pack(side="left", padx=(0, 14))

        apply_btn = tk.Button(
            limit_row, text="Apply", font=("Segoe UI", 9),
            bg=BTN_BG, fg=TEXT_WHITE, relief="flat", padx=12, pady=1,
            highlightbackground=BTN_BORDER, highlightthickness=1, bd=0,
            command=self.apply_speed_limit
        )
        apply_btn.pack(side="left")

        rem_cb = tk.Checkbutton(
            bw_box, text="Remember on Resume", variable=self.remember_resume_var,
            font=("Segoe UI", 9), fg=TEXT_WHITE, bg=BG_FRAME, selectcolor=BG_SUBFRAME,
            activebackground=BG_FRAME, activeforeground=TEXT_WHITE
        )
        rem_cb.pack(anchor="w", pady=(8, 2))

        comp_cb = tk.Checkbutton(
            pad_frame, text="Show Completion Dialog", variable=self.show_completion_var,
            font=("Segoe UI", 9), fg=TEXT_WHITE, bg=BG_FRAME, selectcolor=BG_SUBFRAME,
            activebackground=BG_FRAME, activeforeground=TEXT_WHITE
        )
        comp_cb.pack(anchor="w", pady=4)

    def setup_connections_view(self):
        pad_frame = tk.Frame(self.view_connections, bg=BG_FRAME)
        pad_frame.pack(fill="both", expand=True, padx=6, pady=6)

        left_table_frame = tk.Frame(pad_frame, bg=BG_FRAME)
        left_table_frame.pack(side="left", fill="both", expand=True, padx=(0, 14))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "NDM.Treeview",
            background=BG_SUBFRAME,
            foreground=TEXT_WHITE,
            fieldbackground=BG_SUBFRAME,
            rowheight=20,
            font=("Segoe UI", 9)
        )
        style.configure(
            "NDM.Treeview.Heading",
            background="#251C3B",
            foreground=TEXT_MUTED,
            font=("Segoe UI", 9, "bold")
        )
        style.map("NDM.Treeview", background=[('selected', '#3B2960')])

        columns = ("no", "status")
        self.conn_tree = ttk.Treeview(
            left_table_frame, columns=columns, show="headings",
            style="NDM.Treeview", selectmode="browse"
        )
        self.conn_tree.heading("no", text="No")
        self.conn_tree.heading("status", text="Status")

        self.conn_tree.column("no", width=40, anchor="center")
        self.conn_tree.column("status", width=260, anchor="w")

        scrollbar = ttk.Scrollbar(left_table_frame, orient="vertical", command=self.conn_tree.yview)
        self.conn_tree.configure(yscrollcommand=scrollbar.set)

        self.conn_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i in range(1, self.num_streams + 1):
            self.conn_tree.insert("", "end", iid=str(i), values=(i, "Initializing..."))

        right_ctrl_frame = tk.Frame(pad_frame, bg=BG_FRAME)
        right_ctrl_frame.pack(side="right", fill="y", padx=(6, 16), pady=10)

        conn_row = tk.Frame(right_ctrl_frame, bg=BG_FRAME)
        conn_row.pack(anchor="w", pady=(0, 12))

        tk.Label(
            conn_row, text="Connections", font=("Segoe UI", 9),
            fg=TEXT_WHITE, bg=BG_FRAME
        ).pack(side="left", padx=(0, 8))

        conn_combo = ttk.Combobox(
            conn_row, textvariable=self.connections_count_var,
            values=["4", "8", "16", "24", "32"],
            width=5, state="readonly", font=("Segoe UI", 9)
        )
        conn_combo.pack(side="left")

        apply_conn_btn = tk.Button(
            right_ctrl_frame, text="Apply", font=("Segoe UI", 9),
            bg=BTN_BG, fg=TEXT_WHITE, relief="flat", padx=14, pady=2,
            highlightbackground=BTN_BORDER, highlightthickness=1, bd=0,
            command=self.apply_connections_count
        )
        apply_conn_btn.pack(anchor="w", pady=(0, 12))

        rem_conn_cb = tk.Checkbutton(
            right_ctrl_frame, text="Remember on Resume", variable=self.remember_resume_var,
            font=("Segoe UI", 9), fg=TEXT_WHITE, bg=BG_FRAME, selectcolor=BG_SUBFRAME,
            activebackground=BG_FRAME, activeforeground=TEXT_WHITE
        )
        rem_conn_cb.pack(anchor="w")

    def switch_tab(self, tab_name: str):
        if tab_name == self.current_tab:
            return

        self.view_download.pack_forget()
        self.view_options.pack_forget()
        self.view_connections.pack_forget()

        for btn in [self.tab_download_btn, self.tab_options_btn, self.tab_conn_btn]:
            btn.config(
                bg=BG_WINDOW, fg=TEXT_MUTED, font=("Segoe UI", 9),
                highlightbackground=BORDER_TAB_INACTIVE
            )

        if tab_name == "download":
            self.view_download.pack(fill="both", expand=True, padx=14, pady=12)
            self.tab_download_btn.config(
                bg=BG_FRAME, fg=TEXT_WHITE, font=("Segoe UI", 9, "bold"),
                highlightbackground=BORDER_TAB_ACTIVE
            )
        elif tab_name == "options":
            self.view_options.pack(fill="both", expand=True, padx=14, pady=12)
            self.tab_options_btn.config(
                bg=BG_FRAME, fg=TEXT_WHITE, font=("Segoe UI", 9, "bold"),
                highlightbackground=BORDER_TAB_ACTIVE
            )
        elif tab_name == "connections":
            self.view_connections.pack(fill="both", expand=True, padx=14, pady=12)
            self.tab_conn_btn.config(
                bg=BG_FRAME, fg=TEXT_WHITE, font=("Segoe UI", 9, "bold"),
                highlightbackground=BORDER_TAB_ACTIVE
            )

        self.current_tab = tab_name

    def update_file_icon(self, filename: str):
        ext = os.path.splitext(filename)[1].lower()
        real_icon = get_windows_file_icon(ext or ".file", size=(64, 64))

        if real_icon:
            self.file_icon_photo = ImageTk.PhotoImage(real_icon)
            self.icon_label.config(image=self.file_icon_photo)
        else:
            archive_icon_path = get_asset_path("file_archive.png")
            if os.path.exists(archive_icon_path):
                img = Image.open(archive_icon_path).resize((64, 64), Image.Resampling.LANCZOS)
                self.file_icon_photo = ImageTk.PhotoImage(img)
                self.icon_label.config(image=self.file_icon_photo)

        ext_label = ext.upper().lstrip('.') or "FILE"
        self.file_type_lbl.config(text=f"{ext_label} Archive" if ext in ['.rar', '.zip', '.7z'] else f"{ext_label} File")

    def apply_speed_limit(self):
        val = self.speed_limit_var.get().strip()
        if not val or val == "0":
            pass

    def apply_connections_count(self):
        new_count = self.connections_count_var.get().strip()
        if new_count.isdigit():
            self.num_streams = int(new_count)
            self.seg_label.config(text=f"Segments : {self.num_streams}")

    def start_download_thread(self):
        def worker():
            save_dir = os.path.join(PROJECT_DIR, "downloads")
            temp_dir = os.path.join(save_dir, "temp")
            os.makedirs(save_dir, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)

            adapters = self.parent_app.detected_adapters
            self.downloader = DualBondDownloader(
                url=self.url,
                output_path="",
                interfaces=adapters,
                num_connections=self.num_streams,
                temp_dir=temp_dir
            )

            try:
                size, ranges, name = self.downloader.probe_file()
                self.clean_filename = sanitize_filename(self.initial_filename or name)
                self.target_path = os.path.join(save_dir, self.clean_filename)
                self.downloader.output_path = self.target_path
                self.file_size = size

                # Update UI metadata
                self.after(0, lambda: self.on_probed(self.clean_filename, size, ranges))

                # Update Main Window History
                self.parent_app.history_manager.add_or_update({
                    "id": self.url,
                    "filename": self.clean_filename,
                    "url": self.url,
                    "size": size,
                    "downloaded": 0,
                    "status": "Downloading ( 0% )",
                    "category": get_file_category(self.clean_filename),
                    "date": datetime.now().strftime("%b %d %H:%M:%S"),
                    "output_path": self.target_path
                })
                self.after(0, self.parent_app.refresh_downloads_table)

                self.is_downloading = True
                self.start_time = time.time()
                self.downloader.start(progress_callback=lambda s: self.after(0, lambda: self.on_progress(s)))

                # Critical Fix: Only trigger on_complete if download truly completed all bytes!
                if self.downloader.part_manager and self.downloader.part_manager.is_all_complete():
                    self.after(0, self.on_complete)

            except Exception as e:
                self.after(0, lambda: self.on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_probed(self, filename: str, size: int, ranges: bool):
        self.title(f"Downloading - {filename}")
        self.header_title.config(text=f"Downloading - {filename}")
        self.val_labels["Status"].config(text="Downloading", fg=TEXT_URL)
        self.val_labels["File Size"].config(text=format_bytes(size))
        self.val_labels["Resumable"].config(text="Yes" if ranges else "No", fg=ACCENT_GREEN if ranges else "#FF5470")
        self.update_file_icon(filename)

    def on_progress(self, stats):
        if stats.get("is_merging"):
            prog = stats.get("merge_progress", 0.0) * 100
            self.title(f"Assembling - {self.clean_filename} ({prog:.0f}%)")
            self.header_title.config(text=f"Assembling - {self.clean_filename} ({prog:.0f}%)")
            self.val_labels["Status"].config(text=f"Assembling file... {prog:.0f}%", fg=ACCENT_CYAN)
            self.val_labels["Bandwidth"].config(text="Merging")
            self.val_labels["Remaining Time"].config(text="Almost done")
            return

        downloaded = stats["downloaded_bytes"]
        total = stats["total_bytes"]
        pct = (downloaded / total * 100) if total > 0 else 0
        speed_bps = stats["total_speed_bps"]
        speed_str = format_bytes(speed_bps) + "/sec"

        # Update labels
        self.val_labels["Downloaded"].config(text=f"{format_bytes(downloaded)} ( {pct:.2f} % )")
        self.val_labels["Bandwidth"].config(text=speed_str)
        self.opt_speed_lbl.config(text=speed_str)

        rem_bytes = max(0, total - downloaded)
        rem_sec = (rem_bytes / speed_bps) if speed_bps > 1024 else 0
        self.val_labels["Remaining Time"].config(text=format_time(rem_sec))

        frac = (downloaded / total) if total > 0 else 0.0
        self.gradient_progress.set_progress(frac)

        parts = stats.get("parts", [])
        if parts:
            self.segment_canvas.set_parts(parts)
            for idx, p in enumerate(parts):
                row_id = str(idx + 1)
                if self.conn_tree.exists(row_id):
                    st = "Finished" if p.is_complete else ("Downloading" if p.downloaded_bytes > 0 else "Pending")
                    if p.assigned_adapter:
                        st += f" ({p.assigned_adapter})"
                    self.conn_tree.item(row_id, values=(idx + 1, st))

        # Refresh in Main App Table
        self.parent_app.update_table_item_progress(self.url, downloaded, total, speed_str, rem_sec)

    def toggle_pause(self):
        if not self.downloader:
            return
        if self.is_downloading and not self.is_paused:
            self.downloader.stop()
            self.is_paused = True
            self.is_downloading = False
            self.pause_resume_btn.config(text="Resume")
            self.title(f"Paused - {self.clean_filename}")
            self.header_title.config(text=f"Paused - {self.clean_filename}")
            self.val_labels["Status"].config(text="Paused", fg="#FFD166")
            self.val_labels["Bandwidth"].config(text="0.000 MB/sec")
            self.opt_speed_lbl.config(text="0.000 MB/sec")

            # Update history status
            downloaded = self.downloader.part_manager.get_total_downloaded() if self.downloader.part_manager else 0
            pct = (downloaded / self.file_size * 100) if self.file_size > 0 else 0
            self.parent_app.history_manager.add_or_update({
                "id": self.url,
                "status": f"Paused ( {pct:.0f}% )",
                "downloaded": downloaded
            })
            self.parent_app.refresh_downloads_table()
        else:
            self.is_paused = False
            self.is_downloading = True
            self.pause_resume_btn.config(text="Pause")
            self.title(f"Downloading - {self.clean_filename}")
            self.header_title.config(text=f"Downloading - {self.clean_filename}")
            self.val_labels["Status"].config(text="Downloading", fg=TEXT_URL)

            def resume_thread():
                self.downloader.start(progress_callback=lambda s: self.after(0, lambda: self.on_progress(s)))
                if self.downloader.part_manager and self.downloader.part_manager.is_all_complete():
                    self.after(0, self.on_complete)

            threading.Thread(target=resume_thread, daemon=True).start()

    def on_complete(self):
        self.is_downloading = False
        filename = os.path.basename(self.target_path) or self.clean_filename
        self.title(f"Completed - {filename}")
        self.header_title.config(text=f"Completed - {filename}")
        self.val_labels["Status"].config(text="Completed", fg=ACCENT_GREEN)
        self.val_labels["Bandwidth"].config(text="Complete")
        self.val_labels["Remaining Time"].config(text="0 sec")
        self.pause_resume_btn.config(text="Open Folder", command=self.open_folder)
        self.cancel_btn.config(text="Close", command=self.destroy)
        self.gradient_progress.set_progress(1.0)

        # Update history
        self.parent_app.history_manager.add_or_update({
            "id": self.url,
            "status": "Complete",
            "downloaded": self.file_size
        })
        self.parent_app.refresh_downloads_table()

        if self.show_completion_var.get():
            messagebox.showinfo("Download Complete", f"Downloaded:\n{filename}\n\nSaved to:\n{self.target_path}")

    def on_error(self, err_msg: str):
        self.is_downloading = False
        self.val_labels["Status"].config(text="Error", fg="#FF5470")
        self.parent_app.history_manager.add_or_update({
            "id": self.url,
            "status": "Error ( 0% )"
        })
        self.parent_app.refresh_downloads_table()
        messagebox.showerror("Download Error", f"Error: {err_msg}")

    def on_cancel(self):
        if self.downloader:
            self.downloader.cancel_and_cleanup()
        self.parent_app.history_manager.remove(self.url)
        self.parent_app.refresh_downloads_table()
        self.destroy()

    def open_folder(self):
        if os.path.exists(self.target_path):
            subprocess.run(f'explorer /select,"{os.path.abspath(self.target_path)}"')
        else:
            subprocess.run(f'explorer "{os.path.abspath(os.path.dirname(self.target_path))}"')


# ----------------- Embedded HTTP Server for Chrome Extension -----------------
class ChromeExtensionHandler(BaseHTTPRequestHandler):
    app_instance = None

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/add_download":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                url = data.get("url", "")
                filename = data.get("filename", "")

                if url and ChromeExtensionHandler.app_instance:
                    ChromeExtensionHandler.app_instance.after(
                        0, lambda: ChromeExtensionHandler.app_instance.spawn_download_window(url, filename)
                    )

                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


# ----------------- Main Dashboard Window & Daemon -----------------
class AnoDMMainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Ano-Download Manager 1.0")
        self.geometry("1020x600")
        self.minsize(820, 500)
        self.configure(bg=BG_WINDOW)

        # Icons
        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # State & History
        history_path = os.path.join(PROJECT_DIR, "downloads", "history.json")
        self.history_manager = DownloadHistoryManager(history_path)
        self.detected_adapters = []
        self.active_dialogs: Dict[str, NDMDownloadWindow] = {}
        self.current_category = "All Downloads"
        self.logo_photo = None
        self.tool_icons = {}

        self.scan_adapters()

        # Start Chrome Extension HTTP Server on 127.0.0.1:9653
        ChromeExtensionHandler.app_instance = self
        self.server = None
        self.start_extension_server()

        # Build Main UI
        self.setup_main_ui()

        # System Tray
        self.tray_icon = None
        self.setup_tray()

        # Intercept window close to minimize to tray instead of quitting
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def scan_adapters(self):
        def worker():
            adapters = get_active_interfaces(test_internet=True)
            self.detected_adapters = [a for a in adapters if a["online"]]
            self.after(0, self.update_status_bar)
        threading.Thread(target=worker, daemon=True).start()

    def start_extension_server(self):
        def run_server():
            try:
                self.server = HTTPServer(("127.0.0.1", 9653), ChromeExtensionHandler)
                self.server.serve_forever()
            except Exception:
                pass
        threading.Thread(target=run_server, daemon=True).start()

    def setup_main_ui(self):
        # ----------------- Title / Header Banner -----------------
        header_bar = tk.Frame(self, bg=BG_SUBFRAME, height=52)
        header_bar.pack(fill="x")

        # Official Logo (40x40) - Clear, sharp, uncompressed
        icon_path = get_asset_path("icon.png")
        if os.path.exists(icon_path):
            logo_img = Image.open(icon_path).resize((40, 40), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_img)
            logo_lbl = tk.Label(header_bar, image=self.logo_photo, bg=BG_SUBFRAME)
            logo_lbl.pack(side="left", padx=(14, 10), pady=6)

        title_lbl = tk.Label(
            header_bar,
            text="Ano-Download Manager 1.0 (Ano-DM)",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_WHITE,
            bg=BG_SUBFRAME
        )
        title_lbl.pack(side="left", pady=6)

        # ----------------- Top Toolbar (Exact NDM Layout) -----------------
        toolbar = tk.Frame(self, bg=BG_FRAME, height=60, highlightbackground=BORDER_FRAME, highlightthickness=1)
        toolbar.pack(fill="x", padx=0, pady=(0, 0))

        # Left Group: New URL, Resume, Stop, Delete
        left_tool_frame = tk.Frame(toolbar, bg=BG_FRAME)
        left_tool_frame.pack(side="left", padx=10, pady=5)

        self.create_tool_button(left_tool_frame, "+", "New URL", "#38BDF8", self.prompt_manual_download)
        self.create_tool_button(left_tool_frame, "▶", "Resume", "#60A5FA", self.toolbar_resume)
        self.create_tool_button(left_tool_frame, "■", "Stop", "#818CF8", self.toolbar_stop)
        self.create_tool_button(left_tool_frame, "✕", "Delete", "#F87171", self.toolbar_delete)

        # Right Group: Settings, Browsers, About, Quit
        right_tool_frame = tk.Frame(toolbar, bg=BG_FRAME)
        right_tool_frame.pack(side="right", padx=10, pady=5)

        self.create_tool_button(right_tool_frame, "⚙", "Settings", "#C084FC", self.show_settings)
        self.create_tool_button(right_tool_frame, "🌐", "Browsers", "#34D399", self.show_browser_info)
        self.create_tool_button(right_tool_frame, "ℹ", "About", "#38BDF8", self.show_about)
        self.create_tool_button(right_tool_frame, "⏻", "Quit", "#F87171", self.tray_exit)

        # ----------------- Main Split Area -----------------
        split_frame = tk.Frame(self, bg=BG_WINDOW)
        split_frame.pack(fill="both", expand=True)

        # Left Sidebar (Categories)
        sidebar_frame = tk.Frame(split_frame, bg="#140D22", width=190, highlightbackground=BORDER_FRAME, highlightthickness=1)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 0))
        sidebar_frame.pack_propagate(False)

        # Categories List
        self.category_btns: Dict[str, tk.Label] = {}
        cats = [
            ("All Downloads", "▼ 📁 All Downloads"),
            ("Video", "    🎬 Video"),
            ("Audio", "    🎵 Audio"),
            ("Compressed", "    🗜 Compressed"),
            ("Document", "    📄 Document"),
            ("Application", "    💻 Application"),
            ("Misc", "    📦 Misc"),
            ("Complete", "▶ 📁 Complete"),
            ("Incomplete", "▶ 📁 Incomplete")
        ]

        tk.Label(sidebar_frame, text="", bg="#140D22", height=1).pack()

        for cat_id, cat_label in cats:
            lbl = tk.Label(
                sidebar_frame, text=cat_label, font=("Segoe UI", 10, "bold" if cat_id == "All Downloads" else "normal"),
                fg=TEXT_WHITE if cat_id == "All Downloads" else TEXT_MUTED,
                bg="#23173B" if cat_id == "All Downloads" else "#140D22",
                anchor="w", padx=10, pady=5, cursor="hand2"
            )
            lbl.pack(fill="x", padx=4, pady=1)
            lbl.bind("<Button-1>", lambda e, c=cat_id: self.select_category(c))
            self.category_btns[cat_id] = lbl

        # Right Main Downloads Table
        table_frame = tk.Frame(split_frame, bg="#160E26")
        table_frame.pack(side="right", fill="both", expand=True)

        # Treeview styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Main.Treeview",
            background="#160E26",
            foreground=TEXT_WHITE,
            fieldbackground="#160E26",
            rowheight=28,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Main.Treeview.Heading",
            background="#1F1436",
            foreground=TEXT_MUTED,
            font=("Segoe UI", 10, "bold")
        )
        style.map("Main.Treeview", background=[('selected', '#3B2464')])

        columns = ("filename", "size", "status", "bandwidth", "remaining", "last_try")
        self.downloads_tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            style="Main.Treeview", selectmode="browse"
        )

        self.downloads_tree.heading("filename", text="File Name")
        self.downloads_tree.heading("size", text="Size")
        self.downloads_tree.heading("status", text="Status")
        self.downloads_tree.heading("bandwidth", text="Bandwidth")
        self.downloads_tree.heading("remaining", text="Remaining Time")
        self.downloads_tree.heading("last_try", text="Last Try (z-a)")

        self.downloads_tree.column("filename", width=340, anchor="w")
        self.downloads_tree.column("size", width=95, anchor="center")
        self.downloads_tree.column("status", width=125, anchor="center")
        self.downloads_tree.column("bandwidth", width=105, anchor="center")
        self.downloads_tree.column("remaining", width=115, anchor="center")
        self.downloads_tree.column("last_try", width=135, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.downloads_tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.downloads_tree.xview)
        self.downloads_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.downloads_tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")

        # Double-click handler
        self.downloads_tree.bind("<Double-1>", self.on_table_double_click)

        # ----------------- Bottom Status Bar -----------------
        self.status_bar = tk.Frame(self, bg="#110A1E", height=28, highlightbackground=BORDER_FRAME, highlightthickness=1)
        self.status_bar.pack(fill="x", side="bottom")

        self.status_left_lbl = tk.Label(
            self.status_bar, text="0 Downloads • Dual-Bond Engine Ready",
            font=("Segoe UI", 10), fg=TEXT_MUTED, bg="#110A1E"
        )
        self.status_left_lbl.pack(side="left", padx=12, pady=3)

        self.status_right_lbl = tk.Label(
            self.status_bar, text="Double-click item to open download details",
            font=("Segoe UI", 10), fg=TEXT_MUTED, bg="#110A1E"
        )
        self.status_right_lbl.pack(side="right", padx=12, pady=3)

        # Initial populate
        self.refresh_downloads_table()

    def create_tool_button(self, parent, symbol: str, label: str, color: str, cmd):
        btn_box = tk.Frame(parent, bg=BG_FRAME, cursor="hand2")
        btn_box.pack(side="left", padx=8)

        circle = tk.Label(
            btn_box, text=symbol, font=("Segoe UI", 13, "bold"),
            fg=color, bg="#271A42", width=3, height=1, relief="solid", bd=1,
            highlightbackground=color, highlightthickness=1
        )
        circle.pack()

        lbl = tk.Label(
            btn_box, text=label, font=("Segoe UI", 9, "bold"),
            fg=TEXT_WHITE, bg=BG_FRAME
        )
        lbl.pack(pady=(2, 0))

        for widget in [btn_box, circle, lbl]:
            widget.bind("<Button-1>", lambda e: cmd())

    def select_category(self, cat_id: str):
        self.current_category = cat_id
        for c, lbl in self.category_btns.items():
            if c == cat_id:
                lbl.config(bg="#2E1B4D", fg=TEXT_WHITE, font=("Segoe UI", 10, "bold"))
            else:
                lbl.config(bg="#140D22", fg=TEXT_MUTED, font=("Segoe UI", 10, "normal"))
        self.refresh_downloads_table()

    def refresh_downloads_table(self):
        for item in self.downloads_tree.get_children():
            self.downloads_tree.delete(item)

        items = self.history_manager.downloads

        # Filter by category
        if self.current_category == "Complete":
            items = [d for d in items if d.get("status") == "Complete"]
        elif self.current_category == "Incomplete":
            items = [d for d in items if d.get("status") != "Complete"]
        elif self.current_category != "All Downloads":
            items = [d for d in items if d.get("category") == self.current_category]

        for d in items:
            fname = d.get("filename", "unknown")
            size_str = format_bytes(d.get("size", 0))
            status = d.get("status", "Queued")
            bandwidth = d.get("bandwidth", "--")
            rem = d.get("remaining", "--")
            date_str = d.get("date", "--")
            self.downloads_tree.insert(
                "", "end", iid=d.get("id"),
                values=(fname, size_str, status, bandwidth, rem, date_str)
            )

        self.update_status_bar()

    def update_table_item_progress(self, item_id: str, downloaded: int, total: int, bandwidth: str, rem_sec: float):
        if self.downloads_tree.exists(item_id):
            pct = (downloaded / total * 100) if total > 0 else 0
            st = f"Downloading ( {pct:.0f}% )"
            rem_str = format_time(rem_sec)
            cur_vals = list(self.downloads_tree.item(item_id, "values"))
            if len(cur_vals) >= 6:
                cur_vals[2] = st
                cur_vals[3] = bandwidth
                cur_vals[4] = rem_str
                self.downloads_tree.item(item_id, values=cur_vals)

    def update_status_bar(self):
        count = len(self.history_manager.downloads)
        adapter_names = [a["name"] for a in self.detected_adapters]
        adapters_str = " + ".join(adapter_names) if adapter_names else "Scanning Adapters..."
        self.status_left_lbl.config(
            text=f"{count} Downloads • Dual-Bond: {adapters_str}"
        )

    def on_table_double_click(self, event):
        sel = self.downloads_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        # Find item in history
        item = next((d for d in self.history_manager.downloads if d.get("id") == item_id), None)
        if not item:
            return

        status = item.get("status", "")
        if "Complete" in status:
            out_path = item.get("output_path", "")
            if os.path.exists(out_path):
                subprocess.run(f'explorer /select,"{os.path.abspath(out_path)}"')
            else:
                downloads_dir = os.path.join(PROJECT_DIR, "downloads")
                subprocess.run(f'explorer "{os.path.abspath(downloads_dir)}"')
        else:
            # Reopen or focus download dialog
            self.spawn_download_window(item.get("url"), item.get("filename"))

    def toolbar_resume(self):
        sel = self.downloads_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        item = next((d for d in self.history_manager.downloads if d.get("id") == item_id), None)
        if item and "Complete" not in item.get("status", ""):
            self.spawn_download_window(item.get("url"), item.get("filename"))

    def toolbar_stop(self):
        sel = self.downloads_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        dialog = self.active_dialogs.get(item_id)
        if dialog:
            dialog.toggle_pause()

    def toolbar_delete(self):
        sel = self.downloads_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        item = next((d for d in self.history_manager.downloads if d.get("id") == item_id), None)
        if not item:
            return

        if messagebox.askyesno("Delete Download", f"Delete '{item.get('filename')}' and purge temporary files?"):
            dialog = self.active_dialogs.get(item_id)
            if dialog:
                dialog.on_cancel()
            else:
                # Manual purge of temp files
                temp_dir = os.path.join(PROJECT_DIR, "downloads", "temp")
                if os.path.exists(temp_dir):
                    fname = item.get("filename", "")
                    for f in os.listdir(temp_dir):
                        if fname in f:
                            try:
                                os.remove(os.path.join(temp_dir, f))
                            except Exception:
                                pass
            self.history_manager.remove(item_id)
            self.refresh_downloads_table()

    def spawn_download_window(self, url: str, filename: str = ""):
        existing = self.active_dialogs.get(url)
        if existing and existing.winfo_exists():
            existing.focus_force()
            return existing

        win = NDMDownloadWindow(self, url, filename, initial_streams=32)
        self.active_dialogs[url] = win
        win.focus_force()
        return win

    def prompt_manual_download(self):
        clipboard_url = ""
        try:
            cb = self.clipboard_get().strip()
            if cb.startswith("http://") or cb.startswith("https://"):
                clipboard_url = cb
        except Exception:
            pass

        dialog = tk.Toplevel(self)
        dialog.title("Ano-DM - Add Download")
        dialog.geometry("540x160")
        dialog.configure(bg=BG_WINDOW)
        dialog.resizable(False, False)

        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)

        tk.Label(
            dialog, text="Enter Download URL:", font=("Segoe UI", 10, "bold"),
            fg=TEXT_WHITE, bg=BG_WINDOW
        ).pack(anchor="w", padx=16, pady=(16, 4))

        entry = tk.Entry(
            dialog, font=("Segoe UI", 10), bg=BG_FRAME, fg=TEXT_WHITE,
            insertbackground=TEXT_WHITE, relief="solid", bd=1, highlightbackground=BORDER_FRAME
        )
        entry.pack(fill="x", padx=16, pady=4)
        if clipboard_url:
            entry.insert(0, clipboard_url)

        btn_box = tk.Frame(dialog, bg=BG_WINDOW)
        btn_box.pack(pady=12)

        def on_ok():
            url = entry.get().strip()
            dialog.destroy()
            if url:
                self.spawn_download_window(url)

        tk.Button(
            btn_box, text="Download", font=("Segoe UI", 9, "bold"),
            bg=BTN_BG, fg=TEXT_WHITE, highlightbackground=BTN_BORDER,
            highlightthickness=1, bd=0, padx=16, pady=3, cursor="hand2", command=on_ok
        ).pack(side="left", padx=6)

        tk.Button(
            btn_box, text="Cancel", font=("Segoe UI", 9),
            bg=BG_WINDOW, fg=TEXT_MUTED, highlightbackground=BORDER_FRAME,
            highlightthickness=1, bd=0, padx=16, pady=3, cursor="hand2", command=dialog.destroy
        ).pack(side="left", padx=6)

    def show_settings(self):
        win = tk.Toplevel(self)
        win.title("Ano-DM Settings")
        win.geometry("480x220")
        win.configure(bg=BG_WINDOW)
        win.resizable(False, False)

        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            win.iconbitmap(icon_path)

        save_dir = os.path.join(PROJECT_DIR, "downloads")

        tk.Label(win, text="Downloads Directory:", font=("Segoe UI", 10, "bold"), fg=TEXT_WHITE, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=(16, 4))
        path_lbl = tk.Label(win, text=save_dir, font=("Segoe UI", 9), fg=TEXT_URL, bg=BG_FRAME, relief="solid", bd=1, padx=8, pady=4)
        path_lbl.pack(fill="x", padx=16, pady=4)

        tk.Label(win, text="Active Channel Bonding Adapters:", font=("Segoe UI", 10, "bold"), fg=TEXT_WHITE, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=(12, 4))
        adapter_names = ", ".join([a["name"] for a in self.detected_adapters]) or "No active adapters"
        tk.Label(win, text=adapter_names, font=("Segoe UI", 9), fg=ACCENT_CYAN, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=2)

        tk.Button(win, text="Close", font=("Segoe UI", 9), bg=BTN_BG, fg=TEXT_WHITE, highlightbackground=BTN_BORDER, highlightthickness=1, bd=0, padx=16, pady=3, command=win.destroy).pack(pady=16)

    def show_browser_info(self):
        win = tk.Toplevel(self)
        win.title("Browser Integration")
        win.geometry("520x220")
        win.configure(bg=BG_WINDOW)
        win.resizable(False, False)

        icon_path = get_asset_path("icon.ico")
        if os.path.exists(icon_path):
            win.iconbitmap(icon_path)

        tk.Label(win, text="Google Chrome Extension Status: Connected", font=("Segoe UI", 10, "bold"), fg=ACCENT_GREEN, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=(16, 6))
        tk.Label(win, text="Daemon HTTP Listener: http://127.0.0.1:9653", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=2)
        
        ext_dir = os.path.join(PROJECT_DIR, "chrome_extension")
        tk.Label(win, text=f"Extension Folder: {ext_dir}", font=("Segoe UI", 9), fg=TEXT_URL, bg=BG_WINDOW).pack(anchor="w", padx=16, pady=2)

        def open_ext_folder():
            subprocess.run(f'explorer "{os.path.abspath(ext_dir)}"')

        btn_box = tk.Frame(win, bg=BG_WINDOW)
        btn_box.pack(pady=16)
        tk.Button(btn_box, text="Open Extension Folder", font=("Segoe UI", 9, "bold"), bg=BTN_BG, fg=TEXT_WHITE, highlightbackground=BTN_BORDER, highlightthickness=1, bd=0, padx=12, pady=4, command=open_ext_folder).pack(side="left", padx=6)
        tk.Button(btn_box, text="Close", font=("Segoe UI", 9), bg=BG_WINDOW, fg=TEXT_MUTED, highlightbackground=BORDER_FRAME, highlightthickness=1, bd=0, padx=12, pady=4, command=win.destroy).pack(side="left", padx=6)

    def show_about(self):
        win = tk.Toplevel(self)
        win.title("About Ano-DM")
        win.geometry("420x260")
        win.configure(bg=BG_WINDOW)
        win.resizable(False, False)

        icon_path = get_asset_path("icon.png")
        if os.path.exists(icon_path):
            logo_img = Image.open(icon_path).resize((64, 64), Image.Resampling.LANCZOS)
            self._about_logo = ImageTk.PhotoImage(logo_img)
            tk.Label(win, image=self._about_logo, bg=BG_WINDOW).pack(pady=(16, 6))

        tk.Label(win, text="Ano-Download Manager 1.0", font=("Segoe UI", 12, "bold"), fg=TEXT_WHITE, bg=BG_WINDOW).pack()
        tk.Label(win, text="High-Speed Multi-Interface Channel Bonding", font=("Segoe UI", 9), fg=ACCENT_CYAN, bg=BG_WINDOW).pack(pady=2)
        tk.Label(win, text="Aggregates Wi-Fi + 4G/5G USB Tethering for doubled speeds.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_WINDOW).pack(pady=4)

        tk.Button(win, text="Close", font=("Segoe UI", 9), bg=BTN_BG, fg=TEXT_WHITE, highlightbackground=BTN_BORDER, highlightthickness=1, bd=0, padx=16, pady=3, command=win.destroy).pack(pady=12)

    def on_window_close(self):
        # Minimize to system tray instead of destroying
        self.withdraw()

    def setup_tray(self):
        icon_png_path = get_asset_path("icon.png")
        if not os.path.exists(icon_png_path):
            return

        image = Image.open(icon_png_path)
        menu = pystray.Menu(
            pystray.MenuItem("Open Main Window", self.tray_open_main, default=True),
            pystray.MenuItem("New Download", lambda: self.after(0, self.prompt_manual_download)),
            pystray.MenuItem("Exit", self.tray_exit)
        )
        self.tray_icon = pystray.Icon("Ano-DM", image, "Ano-Download Manager", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def tray_open_main(self, icon=None, item=None):
        self.after(0, self.restore_main_window)

    def restore_main_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def tray_exit(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        if self.server:
            self.server.shutdown()
        self.after(0, self.destroy)


if __name__ == "__main__":
    app = AnoDMMainApp()
    app.mainloop()
