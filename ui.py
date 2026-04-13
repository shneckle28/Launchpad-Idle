import threading
import time
import tkinter as tk

import customtkinter as ctk

from animations import ANIMATIONS, PRESETS, GRID_SIZE, CORNERS
from launchpad import LaunchpadDevice, list_output_devices

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PLAY_FG    = "#1F6AA5"
PLAY_HOVER = "#144870"
STOP_FG    = "#B22222"
STOP_HOVER = "#8B0000"

BG         = "#12121e"
PANEL_BG   = "#1a1a2e"
PAD_OFF    = "#0d0d1a"
PAD_CORNER = "#08081a"


class MidiControllerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Launchpad Controller")
        self.geometry("980x660")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        try:
            import sys, os
            base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            self.iconbitmap(os.path.join(base, "icon.ico"))
        except Exception:
            pass

        self.launchpad        = LaunchpadDevice()
        self.anim_thread      = None
        self.stop_event       = threading.Event()
        self.current_anim     = None
        self.fps              = 30
        self.is_playing       = False
        self._preview_pending = False
        self._device_map      = {}

        self._build_ui()
        self.after(200, self._scan_devices)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="LAUNCHPAD CONTROLLER",
            font=ctk.CTkFont(family="Consolas", size=17, weight="bold"),
            text_color="#6699ff",
        ).pack(pady=(18, 10))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15)
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=0)
        content.rowconfigure(0, weight=1)

        self._build_anim_panel(content)
        self._build_preset_panel(content)
        self._build_preview_panel(content)
        self._build_bottom_bar()

    def _build_anim_panel(self, parent):
        frame = ctk.CTkFrame(parent, width=200, corner_radius=14, fg_color=PANEL_BG)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        frame.grid_propagate(False)

        ctk.CTkLabel(
            frame, text="ANIMATIONS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#667799",
        ).pack(pady=(16, 6))

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))

        self.anim_var = ctk.StringVar(value=ANIMATIONS[0].name)
        for anim_cls in ANIMATIONS:
            ctk.CTkRadioButton(
                scroll,
                text=anim_cls.name,
                variable=self.anim_var,
                value=anim_cls.name,
                command=self._on_anim_change,
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", padx=16, pady=5)

    def _build_preset_panel(self, parent):
        frame = ctk.CTkFrame(parent, corner_radius=14, fg_color=PANEL_BG)
        frame.grid(row=0, column=1, sticky="nsew", padx=8)

        ctk.CTkLabel(
            frame, text="COLOR PRESETS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#667799",
        ).pack(pady=(16, 6))

        self.preset_var = ctk.StringVar(value="Ocean")
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        for name, colors in PRESETS.items():
            row_f = ctk.CTkFrame(scroll, fg_color="transparent")
            row_f.pack(fill="x", pady=5)

            ctk.CTkRadioButton(
                row_f, text=name,
                variable=self.preset_var, value=name,
                command=self._on_preset_change,
                font=ctk.CTkFont(size=13), width=125,
            ).pack(side="left")

            swatch_row = ctk.CTkFrame(row_f, fg_color="transparent")
            swatch_row.pack(side="left", padx=(10, 0))
            for r, g, b in colors:
                ctk.CTkFrame(
                    swatch_row, width=20, height=20, corner_radius=5,
                    fg_color=f"#{r:02x}{g:02x}{b:02x}",
                ).pack(side="left", padx=2)

    _PAD    = 22
    _GAP    = 2
    _MARGIN = 8

    def _build_preview_panel(self, parent):
        panel_w = GRID_SIZE * (self._PAD + self._GAP) - self._GAP + self._MARGIN * 2 + 24
        frame = ctk.CTkFrame(parent, width=panel_w, corner_radius=14, fg_color=PANEL_BG)
        frame.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        frame.grid_propagate(False)

        ctk.CTkLabel(
            frame, text="PREVIEW",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#667799",
        ).pack(pady=(14, 6))

        canvas_size = GRID_SIZE * (self._PAD + self._GAP) - self._GAP + self._MARGIN * 2
        self._canvas = tk.Canvas(
            frame, width=canvas_size, height=canvas_size,
            bg="#08081a", highlightthickness=0, bd=0,
        )
        self._canvas.pack(padx=12, pady=4)

        self._pad_rects = []
        for row in range(GRID_SIZE):
            row_rects = []
            for col in range(GRID_SIZE):
                x0   = self._MARGIN + col * (self._PAD + self._GAP)
                y0   = self._MARGIN + row * (self._PAD + self._GAP)
                fill = PAD_CORNER if (row, col) in CORNERS else PAD_OFF
                rid  = self._canvas.create_rectangle(
                    x0, y0, x0 + self._PAD, y0 + self._PAD,
                    fill=fill, outline="",
                )
                row_rects.append(rid)
            self._pad_rects.append(row_rects)

    def _build_bottom_bar(self):
        bar = ctk.CTkFrame(self, height=120, corner_radius=14, fg_color=PANEL_BG)
        bar.pack(fill="x", padx=15, pady=(10, 14))
        bar.pack_propagate(False)

        self.play_btn = ctk.CTkButton(
            bar, text="▶  PLAY",
            width=125, height=46,
            command=self._toggle_play,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=10,
            fg_color=PLAY_FG, hover_color=PLAY_HOVER,
        )
        self.play_btn.pack(side="left", padx=22, pady=18)

        speed_f = ctk.CTkFrame(bar, fg_color="transparent")
        speed_f.pack(side="left", padx=12, pady=16)

        top_row = ctk.CTkFrame(speed_f, fg_color="transparent")
        top_row.pack(fill="x")
        ctk.CTkLabel(
            top_row, text="SPEED",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#667799",
        ).pack(side="left")
        self.fps_label = ctk.CTkLabel(
            top_row, text="30 fps",
            font=ctk.CTkFont(size=10), text_color="#6699ff",
        )
        self.fps_label.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            speed_f, from_=5, to=60, number_of_steps=55,
            command=self._on_speed_change, width=170,
        )
        self.speed_slider.set(30)
        self.speed_slider.pack(pady=(4, 0))

        status_f = ctk.CTkFrame(bar, fg_color="transparent")
        status_f.pack(side="right", padx=22, pady=8)

        self.status_label = ctk.CTkLabel(
            status_f, text="● Not Connected",
            font=ctk.CTkFont(size=12), text_color="#445566",
        )
        self.status_label.pack()

        self.device_menu = ctk.CTkOptionMenu(
            status_f, values=["-- scan for devices --"],
            width=210, height=26,
            font=ctk.CTkFont(size=11), dynamic_resizing=False,
        )
        self.device_menu.pack(pady=(5, 4))

        btn_row = ctk.CTkFrame(status_f, fg_color="transparent")
        btn_row.pack()

        ctk.CTkButton(
            btn_row, text="Scan", width=60, height=26,
            command=self._scan_devices,
            fg_color="transparent", border_width=1,
            border_color="#334455", font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="Connect", width=80, height=26,
            command=self._try_connect,
            fg_color=PLAY_FG, hover_color=PLAY_HOVER,
            font=ctk.CTkFont(size=11),
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def _scan_devices(self):
        self.status_label.configure(text="● Scanning...", text_color="#aaaaaa")

        def _do_scan():
            devices = list_output_devices()
            def _finish():
                if not devices:
                    self.device_menu.configure(values=["No MIDI outputs found"])
                    self.device_menu.set("No MIDI outputs found")
                    self._device_map = {}
                    self.status_label.configure(text="● No outputs found", text_color="#dd4444")
                    return
                self._device_map = {name: did for did, name in devices}
                names = list(self._device_map.keys())
                self.device_menu.configure(values=names)
                auto = next((n for n in names if "MIDIOUT2" in n), None)
                if auto is None:
                    auto = next((n for n in names if "Launchpad" in n), names[0])
                self.device_menu.set(auto)
                self.status_label.configure(
                    text=f"● {len(names)} device(s) found", text_color="#6699ff"
                )
            self.after(0, _finish)

        threading.Thread(target=_do_scan, daemon=True).start()

    def _try_connect(self):
        selected  = self.device_menu.get()
        device_id = self._device_map.get(selected)

        if device_id is None:
            self._scan_devices()
            selected  = self.device_menu.get()
            device_id = self._device_map.get(selected)

        if device_id is None:
            self.status_label.configure(text="● No device selected", text_color="#dd4444")
            return

        self.status_label.configure(text="● Connecting...", text_color="#aaaaaa")
        self.device_menu.configure(state="disabled")

        def _do_connect():
            ok, msg = self.launchpad.connect(device_id, selected)
            def _finish():
                self.device_menu.configure(state="normal")
                if ok:
                    self.status_label.configure(text="● Connected", text_color="#44dd88")
                else:
                    self.status_label.configure(text=f"● {msg}", text_color="#dd4444")
            self.after(0, _finish)

        threading.Thread(target=_do_connect, daemon=True).start()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_anim_change(self):
        if self.is_playing:
            self._restart()

    def _on_preset_change(self):
        if self.is_playing:
            self._restart()

    def _on_speed_change(self, value):
        self.fps = int(value)
        self.fps_label.configure(text=f"{self.fps} fps")

    def _toggle_play(self):
        if self.is_playing:
            self._stop()
        else:
            self._play()

    # ------------------------------------------------------------------
    # Animation control
    # ------------------------------------------------------------------

    def _play(self):
        anim_name = self.anim_var.get()
        anim_cls  = next((a for a in ANIMATIONS if a.name == anim_name), ANIMATIONS[0])
        palette   = PRESETS[self.preset_var.get()]

        self.current_anim = anim_cls(palette)
        self.stop_event.clear()
        self.is_playing = True
        self.play_btn.configure(text="■  STOP", fg_color=STOP_FG, hover_color=STOP_HOVER)

        self.anim_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.anim_thread.start()

    def _stop(self):
        self.stop_event.set()
        self.is_playing = False
        self.play_btn.configure(text="▶  PLAY", fg_color=PLAY_FG, hover_color=PLAY_HOVER)
        self.launchpad.clear()
        self.after(60, self._clear_preview)

    def _restart(self):
        self.stop_event.set()
        if self.anim_thread and self.anim_thread.is_alive():
            self.anim_thread.join(timeout=0.4)
        self._play()

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        while not self.stop_event.is_set():
            t0   = time.perf_counter()
            grid = self.current_anim.next_frame()

            if self.launchpad.connected:
                self.launchpad.set_grid(grid)

            self._queue_preview(grid)

            elapsed = time.perf_counter() - t0
            wait    = max(0.0, 1.0 / max(1, self.fps) - elapsed)
            time.sleep(wait)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _queue_preview(self, grid):
        if self._preview_pending:
            return
        snapshot = [row[:] for row in grid]
        self._preview_pending = True

        def _apply():
            self._preview_pending = False
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE):
                    if (r, c) in CORNERS:
                        continue
                    px = snapshot[r][c]
                    self._canvas.itemconfig(
                        self._pad_rects[r][c],
                        fill=f"#{px[0]:02x}{px[1]:02x}{px[2]:02x}",
                    )

        try:
            self.after(0, _apply)
        except Exception:
            self._preview_pending = False

    def _clear_preview(self):
        self._preview_pending = False
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                fill = PAD_CORNER if (r, c) in CORNERS else PAD_OFF
                self._canvas.itemconfig(self._pad_rects[r][c], fill=fill)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_close(self):
        self._stop()
        self.launchpad.disconnect()
        self.destroy()
