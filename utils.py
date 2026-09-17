import json
import os
from datetime import datetime

CONFIG_PATH = "config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def generate_output_name(data, config):
    naming = config.get("output_naming", "iban_period")
    if naming == "iban_period":
        period = data.get("period_to")
        if hasattr(period, "isoformat"):
            period = period.isoformat()
        safe_iban = data.get("iban", "UNKNOWN").replace(" ", "")
        return f"{safe_iban}_{period}.xml"
    return "output.xml"


def ensure_log_folder(config):
    folder = config.get("log_folder", "logs")
    os.makedirs(folder, exist_ok=True)
    return folder


def get_log_path(config):
    folder = ensure_log_folder(config)
    filename = f"hosk_converter_{datetime.now().strftime('%Y%m%d')}.log"
    return os.path.join(folder, filename)


def append_log(message, config):
    path = get_log_path(config)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def get_output_folder(config):
    return config.get("default_output_folder", "output")
