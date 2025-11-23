import tkinter as tk
from tkinter import ttk
import threading
import os
import sys


class LoadingScreen:
    """A modern loading screen widget that displays initialization progress."""

    def __init__(self, version="v1.0.0"):
        self.version_string = version
        self.root = tk.Tk()
        self.finished_callback = None
        self.progress = 0
        self.steps = []
        self.current_step = 0
        self.animation_angle = 0
        self.is_destroyed = False
        self.ui_lock = threading.RLock()
        self.init_ui()

    def get_resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def init_ui(self):
        """Initialize the loading screen UI."""
        self.root.title("SignSynth")

        try:
            icon_path = self.get_resource_path("SignSynth.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                print(f"Warning: Icon file not found at {icon_path}")
        except Exception as e:
            print(f"Warning: Could not set icon. Error: {e}")

        window_width = 600
        window_height = 450
        self.root.geometry(f"{window_width}x{window_height}")

        self.root.resizable(False, False)
        self.main_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.main_frame,
            bg="#1a1a2e",
            highlightthickness=0,
            width=window_width,
            height=window_height
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_gradient()
        self.canvas.create_text(
            300, 80,
            text="SignSynth",
            font=("Segoe UI", 48, "bold"),
            fill="#00d4ff",
            tags="title"
        )
        self.canvas.create_text(
            300, 140,
            text="YouTube Sign Language Integrator",
            font=("Segoe UI", 16),
            fill="#a0a0a0",
            tags="subtitle"
        )
        self.circle_id = self._create_loading_circle(300, 220, 30)
        self.progress_frame = tk.Frame(self.main_frame, bg="#0f3460", height=30)
        self.progress_frame.place(x=100, y=280, width=400, height=30)
        self.progress_canvas = tk.Canvas(
            self.progress_frame,
            bg="#0f3460",
            highlightthickness=0,
            height=30
        )
        self.progress_canvas.pack(fill=tk.BOTH, expand=True)
        self.progress_canvas.create_rectangle(
            0, 0, 400, 30,
            outline="#00d4ff",
            width=2,
            tags="border"
        )
        self.progress_fill = self.progress_canvas.create_rectangle(
            0, 0, 0, 30,
            fill="#00d4ff",
            outline="",
            tags="fill"
        )
        self.progress_text = self.progress_canvas.create_text(
            200, 15,
            text="0%",
            font=("Segoe UI", 12, "bold"),
            fill="white",
            tags="percent"
        )
        self.status_text = self.canvas.create_text(
            300, 330,
            text="Initializing...",
            font=("Segoe UI", 14),
            fill="white",
            tags="status"
        )
        self.detail_text = self.canvas.create_text(
            300, 360,
            text="",
            font=("Segoe UI", 11),
            fill="#808080",
            tags="detail"
        )
        self.button_frame = tk.Frame(self.main_frame, bg="#1a1a2e")
        self.update_button = tk.Button(
            self.button_frame,
            text="Update and Restart",
            font=("Segoe UI", 12, "bold"),
            bg="#00d4ff",
            fg="#1a1a2e",
            activebackground="#00b8e0",
            activeforeground="#1a1a2e",
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=10
        )
        self.update_button.pack(side=tk.RIGHT, padx=10)
        self.later_button = tk.Button(
            self.button_frame,
            text="Later",
            font=("Segoe UI", 12),
            bg="#2a2a3e",
            fg="#a0a0a0",
            activebackground="#3a3a4e",
            activeforeground="white",
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=10
        )
        self.later_button.pack(side=tk.RIGHT, padx=10)
        self.button_frame.place_forget()
        self.canvas.create_text(
            300, 420,
            text=self.version_string,
            font=("Segoe UI", 9),
            fill="#606060",
            tags="version"
        )

        self.root.bind("<Escape>", self.on_escape)
        self.root.protocol("WM_DELETE_WINDOW", self.on_escape)
        self._animate_circle()

    def on_escape(self, event=None):
        """Handle Escape key press or close button click."""
        print("Loading cancelled by user.")
        self.close_and_finish()

    def _draw_gradient(self):
        """Draw a gradient-like background effect."""

        for i in range(20):
            y = i * 22.5
            color_val = int(0x1a + (0x16 - 0x1a) * (i / 20))
            color = f"#{color_val:02x}{color_val:02x}{min(0x2e + i, 0x3e):02x}"
            self.canvas.create_rectangle(
                0, y, 600, y + 23,
                fill=color,
                outline=""
            )

    def _create_loading_circle(self, x, y, radius):
        """Create an animated loading circle."""
        return self.canvas.create_arc(
            x - radius, y - radius, x + radius, y + radius,
            start=0, extent=120,
            outline="#00d4ff",
            width=4,
            style=tk.ARC,
            tags="spinner"
        )

    def _animate_circle(self):
        """Animate the loading circle."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.animation_angle = (self.animation_angle + 10) % 360
                self.canvas.itemconfig(self.circle_id, start=self.animation_angle)
                self.root.after(50, self._animate_circle)
            except (tk.TclError, RuntimeError):

                pass

    def set_steps(self, steps):
        """Set the initialization steps to display."""

        self.steps = steps
        self.current_step = 0

    def show_update_prompt(self, text, yes_callback, no_callback):
        """Shows the update buttons and text, hides progress."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.canvas.itemconfig(self.status_text, text=text)
                self.canvas.itemconfig(self.detail_text, text="")
                self.progress_frame.place_forget()
                self.canvas.itemconfig("spinner", state="hidden")
                self.button_frame.place(x=150, y=280, width=300, height=60)
                self.update_button.config(command=yes_callback)
                self.later_button.config(command=no_callback)
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def hide_update_prompt(self):
        """Hides the update buttons, shows progress."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.button_frame.place_forget()
                self.progress_frame.place(x=100, y=280, width=400, height=30)
                self.canvas.itemconfig("spinner", state="normal")
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def update_progress(self, step_name, detail=""):
        """Update the progress bar and status."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:

                self.hide_update_prompt()

                if self.steps:
                    self.current_step += 1
                    progress_value = int((self.current_step / len(self.steps)) * 100)
                    self.set_progress(progress_value)

                self.canvas.itemconfig(self.status_text, text=step_name)
                self.canvas.itemconfig(self.detail_text, text=detail)
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def set_progress(self, value):
        """Set progress bar value (0-100)."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.progress = max(0, min(100, value))
                fill_width = (self.progress / 100) * 400
                self.progress_canvas.coords(self.progress_fill, 0, 0, fill_width, 30)
                self.progress_canvas.itemconfig(self.progress_text, text=f"{self.progress}%")
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def update_status_text(self, step_name, detail=""):
        """
        Updates *only* the status text and detail text labels.
        Does NOT modify the progress bar.
        """
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.canvas.itemconfig(self.status_text, text=step_name)
                self.canvas.itemconfig(self.detail_text, text=detail)
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def complete(self):
        """Mark loading as complete and close after a brief delay."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.hide_update_prompt()
                self.set_progress(100)
                self.canvas.itemconfig(self.status_text, text="Ready!")
                self.canvas.itemconfig(self.detail_text, text="Starting application...")
                self.root.update()
            except (tk.TclError, RuntimeError):
                return

        self.root.after(500, self.close_and_finish)

    def close_and_finish(self):
        """Close the loading screen and call finished callback."""

        with self.ui_lock:
            if self.is_destroyed:
                return
            self.is_destroyed = True

        try:
            self.root.quit()
            self.root.destroy()
        except (tk.TclError, RuntimeError):
            pass

        if self.finished_callback:
            self.finished_callback()

    def finished_connect(self, callback):
        """Connect a callback to be called when loading finishes."""
        self.finished_callback = callback

    def center(self):
        """Center the window on the screen."""
        try:
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except (tk.TclError, RuntimeError):
            pass

    def show(self):
        """Show the loading screen."""
        try:
            self.root.deiconify()
            self.root.update()
        except (tk.TclError, RuntimeError):
            pass

    def mainloop(self):
        """Run the tkinter event loop."""
        try:
            self.root.mainloop()
        except (tk.TclError, RuntimeError):
            pass

    def update(self):
        """Process pending events."""
        with self.ui_lock:
            if self.is_destroyed:
                return
            try:
                self.root.update()
            except (tk.TclError, RuntimeError):
                pass

    def quit(self):
        """Quit the event loop."""
        self.close_and_finish()

    def close(self):
        """Close the window."""
        self.close_and_finish()
