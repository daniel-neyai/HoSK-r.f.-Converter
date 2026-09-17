import tkinter as tk
import threading
import os
from gui import ConverterApp
from utils import load_config
from splash_screen import SplashScreen

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None


def load_app(root, splash):
    try:
        config = load_config()
        app = ConverterApp(root, config)
        root.deiconify()
    except Exception as e:
        print(f"Error loading app: {e}")
    finally:
        splash.close()


if __name__ == "__main__":
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    root.withdraw()
    
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    splash = SplashScreen(root, logo_path)
    root.update()

    # Keep only the splash visible for a short demo (1s), then initialize the app.
    def start_after_delay():
        # close splash and then load app on background thread
        splash.close()
        thread = threading.Thread(target=load_app, args=(root, splash), daemon=True)
        thread.start()

    root.after(1000, start_after_delay)
    
    root.mainloop()
