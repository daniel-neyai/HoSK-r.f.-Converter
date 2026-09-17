import os
import tkinter as tk
from PIL import Image, ImageTk
import threading


class SplashScreen:
    def __init__(self, root, logo_path="logo.png"):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)
        
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        try:
            if os.path.exists(logo_path):
                image = Image.open(logo_path)
                image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                label = tk.Label(self.window, image=photo, bg="black")
                label.image = photo
                label.pack()
            else:
                label = tk.Label(
                    self.window,
                    text="HoSK r.f.\nBank Statement Converter\n\nLoading...",
                    font=("Segoe UI", 16, "bold"),
                    bg="black",
                    fg="white",
                    pady=40,
                    padx=40
                )
                label.pack()
        except Exception as e:
            label = tk.Label(
                self.window,
                text="HoSK r.f.\nBank Statement Converter\n\nLoading...",
                font=("Segoe UI", 16, "bold"),
                bg="black",
                fg="white",
                pady=40,
                padx=40
            )
            label.pack()
        
        status = tk.Label(
            self.window,
            text="Starting application...",
            font=("Segoe UI", 10),
            bg="black",
            fg="#888888"
        )
        status.pack(pady=(0, 20))
        
        self.window.update_idletasks()
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.window.geometry(f"+{x}+{y}")

    def close(self):
        self.window.destroy()
