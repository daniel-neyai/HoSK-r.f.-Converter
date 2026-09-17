import os
import json
import threading
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from admin import AdminPanel
from converter_core import build_camt053
from parser_aktia import parse_input_file
from validator import validate_statement
from utils import append_log, ensure_log_folder, generate_output_name, get_output_folder, save_config

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None


class ConverterApp:
    SUPPORTED_EXTENSIONS = [".zip", ".pdf", ".xml"]

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.file_queue = []
        self.processing = False
        self.spinner_angle = 0
        self.root.title("HoSK r.f. Smart Bank Statement Converter")
        self.root.geometry("1080x720")
        self.root.minsize(980, 680)

        self._build_style()
        self._build_toolbar()
        self._build_list_area()
        self._build_drop_zone()
        self._build_progress_area()
        self._build_log_area()
        self._build_status_bar()

        ensure_log_folder(self.config)
        self.append_log("Application started.")

    def _build_style(self):
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use(self.config.get("theme_style", "clam"))
        except Exception:
            self.style.theme_use("clam")

        theme = self.config.get("theme", "dark")
        self.bg_color = "#1E1E2F" if theme == "dark" else "#F4F4F6"
        self.text_color = "white" if theme == "dark" else "#202020"
        self.root.configure(bg=self.bg_color)

        self.style.configure("Header.TFrame", background=self.bg_color)
        self.style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), foreground="white")
        self.style.configure("Status.TLabel", background=self.bg_color, foreground=self.text_color)
        self.style.configure("Treeview", rowheight=28, fieldbackground="#2B2B3B" if theme == "dark" else "white", background="#2B2B3B" if theme == "dark" else "white", foreground=self.text_color)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, style="Header.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=12, pady=8)

        self.add_button = ttk.Button(toolbar, text="Add File", style="Action.TButton", command=self.add_file)
        self.add_button.pack(side=tk.LEFT, padx=6)

        self.add_folder_button = ttk.Button(toolbar, text="Add Folder", style="Action.TButton", command=self.add_folder)
        self.add_folder_button.pack(side=tk.LEFT, padx=6)

        self.clear_button = ttk.Button(toolbar, text="Clear List", style="Action.TButton", command=self.clear_queue)
        self.clear_button.pack(side=tk.LEFT, padx=6)

        self.convert_button = ttk.Button(toolbar, text="Convert Batch", style="Action.TButton", command=self.convert_files)
        self.convert_button.pack(side=tk.LEFT, padx=6)

        self.admin_button = ttk.Button(toolbar, text="Admin Panel", style="Action.TButton", command=self.open_admin_panel)
        self.admin_button.pack(side=tk.LEFT, padx=6)

        self.theme_button = ttk.Button(toolbar, text="Toggle Theme", style="Action.TButton", command=self.toggle_theme)
        self.theme_button.pack(side=tk.RIGHT, padx=6)

    def _build_list_area(self):
        list_frame = ttk.LabelFrame(self.root, text="Input Files and Conversion Queue", padding=(12, 10))
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=12, pady=(0, 10))

        columns = ("path", "type", "status", "output")
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=6)
        self.file_tree.heading("path", text="Path")
        self.file_tree.heading("type", text="Type")
        self.file_tree.heading("status", text="Status")
        self.file_tree.heading("output", text="Output")
        self.file_tree.column("path", width=520)
        self.file_tree.column("type", width=90, anchor="center")
        self.file_tree.column("status", width=120, anchor="center")
        self.file_tree.column("output", width=220)
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Warning label at the bottom
        self.warning_label = tk.Label(self.root, text="", fg="red", font=("Helvetica", 12), bg="#f5f5f5")
        self.warning_label.pack(side="bottom", fill="x", padx=10, pady=5)

    def _build_drop_zone(self):
        drop_frame = ttk.Frame(self.root, padding=(12, 10), style="Header.TFrame")
        drop_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 10))

        self.drop_label = ttk.Label(drop_frame, text="Drag and drop ZIP, PDF, or XML files here to add them to the queue.", style="Status.TLabel")
        self.drop_label.pack(fill=tk.X, pady=4)

        if DND_FILES and hasattr(self.root, "drop_target_register"):
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind("<<Drop>>", self.handle_drop)
                self.append_log("Drag-and-drop interface enabled.")
            except Exception:
                self.drop_label.config(text="Drag and drop is not supported in this environment. Use Add File or Add Folder.")
        else:
            self.drop_label.config(text="Drag and drop unavailable. Install tkinterdnd2 or use Add File/Add Folder.")

    def _build_progress_area(self):
        progress_frame = ttk.Frame(self.root, style="Header.TFrame")
        progress_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        self.spinner_canvas = tk.Canvas(progress_frame, width=52, height=52, highlightthickness=0, bg=self.bg_color)
        self.spinner_canvas.pack(side=tk.LEFT)

    def _build_log_area(self):
        log_frame = ttk.LabelFrame(self.root, text="Detailed Conversion Log", padding=(12, 10))
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        self.log_area = ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 11), background="#151521", foreground="#E5E5E5", height=12)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def _build_status_bar(self):
        status_frame = ttk.Frame(self.root, style="Header.TFrame")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 10))

        self.status_label = ttk.Label(status_frame, text="Ready to convert PDF/XML/ZIP statements into camt.053.001.02.", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT)

    def add_file(self):
        file_paths = filedialog.askopenfilenames(
            title="Select PDF, ZIP or XML files",
            filetypes=[("Supported files", "*.zip *.pdf *.xml"), ("All files", "*")],
        )
        self.add_files(file_paths)

    def add_folder(self):
        folder_path = filedialog.askdirectory(title="Select folder containing statements")
        if not folder_path:
            return

        found = []
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if os.path.splitext(filename)[1].lower() in self.SUPPORTED_EXTENSIONS:
                    found.append(os.path.join(root, filename))

        if not found:
            messagebox.showinfo("No supported files", "No ZIP, PDF, or XML files were found in the selected folder.")
            return

        self.add_files(found)

    def handle_drop(self, event):
        raw = self.root.tk.splitlist(event.data)
        paths = [path.strip('{}') for path in raw if os.path.isfile(path.strip('{}'))]
        self.add_files(paths)

    def add_files(self, paths):
        if not paths:
            return

        for path in paths:
            extension = os.path.splitext(path)[1].lower()
            if extension not in self.SUPPORTED_EXTENSIONS:
                self.append_log(f"Skipped unsupported file: {path}")
                continue
            if path in [item["path"] for item in self.file_queue]:
                self.append_log(f"Already added: {path}")
                continue

            self.file_queue.append({
                "path": path,
                "type": extension.replace(".", "").upper(),
                "status": "Ready",
                "output": "",
            })
            self.append_log(f"Queued file: {path}")

        self.refresh_file_list()
        self.status_label.config(text=f"{len(self.file_queue)} files queued.")

    def refresh_file_list(self):
        for row in self.file_tree.get_children():
            self.file_tree.delete(row)

        for item in self.file_queue:
            self.file_tree.insert("", tk.END, values=(item["path"], item["type"], item["status"], item["output"]))

    def clear_queue(self):
        self.file_queue.clear()
        self.refresh_file_list()
        self.append_log("Queue cleared.")
        self.status_label.config(text="Ready to load files.")

    def convert_files(self):
        if self.processing:
            messagebox.showinfo("Conversion in progress", "Conversion is already running.")
            return

        if not self.file_queue:
            messagebox.showwarning("No files", "Please add at least one supported file before conversion.")
            return

        self.processing = True
        self.progress_bar.start(14)
        self.status_label.config(text="Converting files... this can take a moment.")
        self.append_log("Starting batch conversion.")
        self.animate_spinner()

        thread = threading.Thread(target=self._run_conversion, daemon=True)
        thread.start()

    def _run_conversion(self):
        for item in self.file_queue:
            try:
                self._set_file_status(item, "Processing")
                output_path = self.process_file(item["path"])
                item["status"] = "Success"
                item["output"] = output_path
                self.append_log(f"Converted {item['path']} -> {output_path}")
            except Exception as err:
                item["status"] = "Failed"
                item["output"] = ""
                error_text = traceback.format_exc()
                self.append_log(f"Conversion failed for {item['path']}: {err}")
                self.append_log(error_text)
                self._show_error(item["path"], err, error_text)
            finally:
                self.root.after(100, self.refresh_file_list)

        self.root.after(0, self._conversion_complete)

    def _set_file_status(self, item, status):
        item["status"] = status
        self.root.after(0, self.refresh_file_list)

    def _show_error(self, path, error, traceback_text):
        message = f"Failed to convert:\n{path}\n\nError: {error}"
        self.append_log(message)
        self.root.after(0, lambda: messagebox.showerror("Conversion Error", message))

    def process_file(self, path):
        self.append_log(f"Reading input file: {path}")
        data = parse_input_file(path)
        self.append_log(f"Parsed data: {data['iban']} from {path}")
        
        # Log opening and closing balances for debugging
        self.append_log(f"Opening Balance: {data['opening']}, Closing Balance: {data['closing']}")
        self.append_log(f"Transactions: {data['transactions']}")

        if self.config.get("strict_validation", True):
            self.append_log("Validating statement data.")
            validate_statement(data, self.config, self)  # Pass 'self' (app object)

        # Generate XML output
        xml_output = build_camt053(data, self.config)
        self.append_log(f"Generated XML Output: {xml_output[:300]}...")  # Log first 300 characters for quick check

        output_folder = get_output_folder(self.config)
        os.makedirs(output_folder, exist_ok=True)

        output_name = generate_output_name(data, self.config)
        output_path = self._unique_output_path(output_folder, output_name)

        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(xml_output)

        if self.config.get("auto_backup", True):
            self._backup_output(output_path)
            return output_path

    def _unique_output_path(self, folder, name):
        output_path = os.path.join(folder, name)
        candidate = output_path
        index = 1
        while os.path.exists(candidate):
            candidate = os.path.join(folder, f"{os.path.splitext(name)[0]}_{index}{os.path.splitext(name)[1]}")
            index += 1
        return candidate

    def _backup_output(self, path):
        backup_folder = os.path.join(os.path.dirname(path), "backup")
        os.makedirs(backup_folder, exist_ok=True)
        backup_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(path)}"
        backup_path = os.path.join(backup_folder, backup_name)
        with open(path, "rb") as original, open(backup_path, "wb") as backup:
            backup.write(original.read())
        self.append_log(f"Backup created: {backup_path}")

    def _conversion_complete(self):
        self.processing = False
        self.progress_bar.stop()
        self.status_label.config(text="Conversion complete. Review logs for details.")
        self.append_log("Batch conversion completed.")

    def animate_spinner(self):
        if not self.processing:
            self.spinner_canvas.delete("spinner")
            return

        self.spinner_canvas.delete("spinner")
        self.spinner_angle = (self.spinner_angle + 20) % 360
        self.spinner_canvas.create_arc(
            8,
            8,
            44,
            44,
            start=self.spinner_angle,
            extent=140,
            style=tk.ARC,
            outline="#5AB1FF",
            width=4,
            tag="spinner",
        )
        self.root.after(80, self.animate_spinner)

    def open_admin_panel(self):
        AdminPanel(self.root, self.config, self)

    def toggle_theme(self):
        self.config["theme"] = "light" if self.config.get("theme", "dark") == "dark" else "dark"
        self.config["theme_style"] = "clam"
        save_config(self.config)
        messagebox.showinfo("Theme", "Restart the app to apply the new theme.")
        self.append_log(f"Theme updated to {self.config['theme']}. Restart required.")

    def append_log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        append_log(line, self.config)

        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, line + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def update_status(self, message):
        self.status_label.config(text=message)

    def refresh_settings(self):
        save_config(self.config)
        self.append_log("Settings saved from admin panel.")
        self.status_label.config(text="Settings updated.")