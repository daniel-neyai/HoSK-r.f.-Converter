import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None


def parse_input_file(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".zip":
        return parse_aktia_zip(path)
    if extension == ".pdf":
        return parse_aktia_pdf(path)
    if extension == ".xml":
        return parse_aktia_xml(path)
    raise ValueError(f"Unsupported input type: {extension}")


def parse_aktia_zip(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        html_files = [name for name in zf.namelist() if name.lower().endswith(".html")]
        if not html_files:
            raise Exception("No HTML file found in ZIP archive.")
        html = zf.read(html_files[0]).decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    return parse_text_body(text)


def parse_aktia_pdf(pdf_path):
    if PdfReader is None:
        raise ImportError("PyPDF2 is required for PDF parsing. Install it with 'pip install PyPDF2'.")

    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)

    text = "\n".join(pages)
    return parse_text_body(text)


def parse_aktia_xml(xml_path):
    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(xml_path, parser=parser)
    root = tree.getroot()

    xml_text = ET.tostring(root, encoding="utf-8", method="text").decode("utf-8", errors="replace")
    return parse_text_body(xml_text)


# Matches lines like:
#   FT26091Y5GWD A 0401 TALLINK SILJA OY 1 900.00 -
#   FT261134DXBK A 0423 18 19.22 -                (no merchant description)
# ref  = alphanumeric Aktia transaction reference (letters mixed into the digits,
#        so \bFT\d+\b never matched — this was the main bug)
# dir  = A (outgoing) or K (incoming) — informational only, the actual +/- sign is authoritative
# mmdd = duplicate of the REGISTR.DAG date in MM DD order, not used (we already track current_date)
# desc = optional free-text description (may be empty)
# seq  = running transaction sequence number printed by the bank
# amount / sign = the actual booked amount
TRANSACTION_RE = re.compile(
    r"^(?P<ref>FT[A-Z0-9]+)\s+(?P<dir>[AK])\s+\d{4}\s+"
    r"(?P<desc>.*?)\s*(?P<seq>\d+)\s+(?P<amount>\d+[.,]\d{2})\s+(?P<sign>[+-])$"
)

REGISTR_DAG_RE = re.compile(r"REGISTR\.?DAG\s+(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)

BALANCE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4}).*?(\d+[.,]\d{2})\s*([+-])")


def parse_balance_line(line):
    match = BALANCE_RE.search(line)
    if not match:
        return None
    date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
    amount = float(match.group(2).replace(",", "."))
    if match.group(3) == "-":
        amount = -amount
    return date, amount


def parse_named_value(text, labels):
    for label in labels:
        pattern = rf"{re.escape(label)}[:\s]+(\d+[.,]\d{{2}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def parse_transactions(lines):
    transactions = []
    current_date = None

    for line in lines:
        registr_match = REGISTR_DAG_RE.search(line)
        if registr_match:
            current_date = datetime.strptime(registr_match.group(1), "%d.%m.%Y").date()
            continue

        tx_match = TRANSACTION_RE.match(line)
        if tx_match:
            amount = float(tx_match.group("amount").replace(",", "."))
            if tx_match.group("sign") == "-":
                amount = -amount

            transactions.append({
                "date": current_date or datetime.today().date(),
                "amount": amount,
                "ref": tx_match.group("ref"),
                "desc": tx_match.group("desc").strip(),
            })

    return transactions


def parse_text_body(text):
    iban_match = re.search(r"\bFI\d{16}\b", text)
    if not iban_match:
        raise ValueError("IBAN not found in statement text.")
    iban = iban_match.group(0)

    # Find the period (start and end dates of the statement)
    period_match = re.search(r"Period\s*\n\s*(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})", text, re.I)
    if not period_match:
        period_match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})", text)
    if not period_match:
        raise ValueError("Statement period not found.")

    period_from = datetime.strptime(period_match.group(1), "%d.%m.%Y").date()
    period_to = datetime.strptime(period_match.group(2), "%d.%m.%Y").date()

    opening = None
    closing = None
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Opening balance: the first SALDO line dated the 1st of the statement's start month.
    for line in lines:
        if "SALDO" in line.upper() and "01." in line:
            opening = parse_balance_line(line)
            if opening:
                break

    # Closing balance: the last SALDO line dated the last day of the statement's end month.
    closing_candidates = []
    for line in lines:
        if "SALDO" in line.upper() and ("30." in line or "31." in line):
            balance = parse_balance_line(line)
            if balance:
                closing_candidates.append(balance)

    if closing_candidates:
        closing_candidates.sort(key=lambda x: x[0], reverse=True)
        closing = closing_candidates[0]

    if opening is None or closing is None:
        opening_amount = parse_named_value(text, ["Opening balance", "Open balance", "Avattava saldo"])
        closing_amount = parse_named_value(text, ["Closing balance", "Close balance", "Suljettu saldo"])
        opening = opening or (period_from, opening_amount or 0)
        closing = closing or (period_to, closing_amount or 0)

    if opening and closing and opening[0] > closing[0]:
        opening, closing = closing, opening

    transactions = parse_transactions(lines)

    return {
        "iban": iban,
        "period_from": period_from,
        "period_to": period_to,
        "opening": round(opening[1] if opening else 0.0, 2),
        "closing": round(closing[1] if closing else 0.0, 2),
        "transactions": transactions,
    }
