import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from utils import save_config


class AdminPanel:
    def __init__(self, root, config, app=None):
        self.root = root
        self.config = config
        self.app = app
        self.window = tk.Toplevel(root)
        self.window.title("HoSK r.f. Admin Console")
        self.window.geometry("560x520")
        self.window.resizable(False, False)
        self.security_unlocked = False

        self._build_login_screen()

    def _build_login_screen(self):
        self.login_frame = ttk.Frame(self.window, padding=20)
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.login_frame, text="Admin password:", font=("Segoe UI", 11)).pack(pady=(0, 10))
        self.password_entry = ttk.Entry(self.login_frame, show="*")
        self.password_entry.pack(fill=tk.X, pady=6)

        ttk.Button(self.login_frame, text="Login", command=self.check_password).pack(pady=12)

    def check_password(self):
        if self.password_entry.get() == self.config.get("admin_password", ""):
            self.login_frame.destroy()
            self._build_settings_panel()
        else:
            messagebox.showerror("Access Denied", "Incorrect admin password.")

    def _build_settings_panel(self):
        tab_control = ttk.Notebook(self.window)
        tab_control.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_general_tab(tab_control)
        self._build_security_tab(tab_control)
        self._build_maintenance_tab(tab_control)

        save_button = ttk.Button(self.window, text="Save Settings", command=self.save_config)
        save_button.pack(pady=10)

    def _build_general_tab(self, parent):
        general_tab = ttk.Frame(parent)
        parent.add(general_tab, text="General")

        ttk.Label(general_tab, text="Currency:", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(12, 2))
        self.currency_entry = ttk.Entry(general_tab)
        self.currency_entry.insert(0, self.config.get("currency", "EUR"))
        self.currency_entry.pack(fill=tk.X, padx=12)

        ttk.Label(general_tab, text="Output folder:", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(12, 2))
        self.output_entry = ttk.Entry(general_tab)
        self.output_entry.insert(0, self.config.get("default_output_folder", "output"))
        self.output_entry.pack(fill=tk.X, padx=12)

        ttk.Button(general_tab, text="Browse...", command=self.choose_output_folder).pack(anchor=tk.E, padx=12, pady=8)

        self.strict_validation_var = tk.BooleanVar(value=self.config.get("strict_validation", True))
        ttk.Checkbutton(general_tab, text="Enable strict validation", variable=self.strict_validation_var).pack(anchor=tk.W, padx=12, pady=8)

        self.auto_backup_var = tk.BooleanVar(value=self.config.get("auto_backup", True))
        ttk.Checkbutton(general_tab, text="Keep automatic backup copies", variable=self.auto_backup_var).pack(anchor=tk.W, padx=12, pady=8)

    def _build_security_tab(self, parent):
        security_tab = ttk.Frame(parent)
        parent.add(security_tab, text="Security")

        self.security_frame = ttk.Frame(security_tab, padding=12)
        self.security_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.security_frame, text="This tab requires additional verification.", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(12, 6))
        ttk.Button(self.security_frame, text="Unlock Security Settings", command=self._verify_security_access).pack(fill=tk.X, pady=12)

        self.security_content = ttk.Frame(self.security_frame)
        self.security_content.pack(fill=tk.BOTH, expand=True, pady=12)

        ttk.Label(self.security_content, text="Admin password:", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(12, 2))
        self.password_new = ttk.Entry(self.security_content, show="*", state=tk.DISABLED)
        self.password_new.pack(fill=tk.X, pady=6)

        ttk.Label(self.security_content, text="Confirm password:", font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(12, 2))
        self.password_confirm = ttk.Entry(self.security_content, show="*", state=tk.DISABLED)
        self.password_confirm.pack(fill=tk.X, pady=6)

    def _verify_security_access(self):
        if self.security_unlocked:
            messagebox.showinfo("Already Unlocked", "Security settings are already unlocked.")
            return

        verify_window = tk.Toplevel(self.window)
        verify_window.title("Security Verification")
        verify_window.geometry("300x120")
        verify_window.resizable(False, False)

        ttk.Label(verify_window, text="Enter admin password:", font=("Segoe UI", 10)).pack(pady=(12, 6), padx=12)
        password_field = ttk.Entry(verify_window, show="*")
        password_field.pack(fill=tk.X, padx=12, pady=6)

        def verify():
            if password_field.get() == self.config.get("admin_password", ""):
                self.security_unlocked = True
                self.password_new.configure(state=tk.NORMAL)
                self.password_confirm.configure(state=tk.NORMAL)
                verify_window.destroy()
                messagebox.showinfo("Unlocked", "Security settings are now accessible. You can modify the admin password.")
            else:
                messagebox.showerror("Access Denied", "Incorrect admin password.")
                password_field.delete(0, tk.END)
                password_field.focus()

        ttk.Button(verify_window, text="Verify", command=verify).pack(pady=12)
        password_field.focus()

    def _build_maintenance_tab(self, parent):
        maintenance_tab = ttk.Frame(parent)
        parent.add(maintenance_tab, text="Maintenance")

        ttk.Button(maintenance_tab, text="Clear log folder", command=self.clear_logs).pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Button(maintenance_tab, text="Open output folder", command=self.open_output_folder).pack(fill=tk.X, padx=12, pady=6)
        ttk.Button(maintenance_tab, text="Export config JSON", command=self.export_config).pack(fill=tk.X, padx=12, pady=6)

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Choose default output folder")
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)

    def save_config(self):
        if self.security_unlocked and self.password_new.get() and self.password_new.get() != self.password_confirm.get():
            messagebox.showerror("Password mismatch", "The new passwords do not match.")
            return

        self.config["currency"] = self.currency_entry.get().strip() or self.config.get("currency", "EUR")
        self.config["default_output_folder"] = self.output_entry.get().strip() or self.config.get("default_output_folder", "output")
        self.config["strict_validation"] = self.strict_validation_var.get()
        self.config["auto_backup"] = self.auto_backup_var.get()

        if self.security_unlocked and self.password_new.get():
            self.config["admin_password"] = self.password_new.get()

        save_config(self.config)
        messagebox.showinfo("Saved", "Admin settings saved.")
        if self.app:
            self.app.refresh_settings()

    def clear_logs(self):
        log_folder = self.config.get("log_folder", "logs")
        if not os.path.isdir(log_folder):
            messagebox.showinfo("Clear logs", "No log folder found to clear.")
            return
        for name in os.listdir(log_folder):
            file_path = os.path.join(log_folder, name)
            if os.path.isfile(file_path):
                os.remove(file_path)
        messagebox.showinfo("Logs cleared", "All log files have been removed.")

    def open_output_folder(self):
        folder = self.config.get("default_output_folder", "output")
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def export_config(self):
        destination = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not destination:
            return
        with open(destination, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(self.config, indent=4))
        messagebox.showinfo("Exported", f"Configuration exported to {destination}")

