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


IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
IDENTIFICATION_MARKER_RE = re.compile(r"TRANSAKTIONENS\s+IDENTIFIKATION", re.IGNORECASE)
PURE_DIGITS_RE = re.compile(r"^\d{5,}$")

# Lines that mark the end of one transaction's detail block (summary/footer/
# header lines that are never part of a transaction's own detail lines).
DETAIL_STOP_RE = re.compile(
    r"^(SALDO|INS[ÄA]TTNINGAR|UTTAG|REGISTR\.?DAG|TRANSP$|AKTIA BANK|"
    r"AVS[ÄA]NDARE|SAMMANDR|BET\.DAG|KONTOUTDRAG|MOTTAGARE|BIC-KOD|"
    r"DISPONIBELT|FR[ÅA]N (B[ÖO]RJAN|PERIODENS))",
    re.IGNORECASE,
)


def _extract_transaction_extras(detail_lines):
    """Pull IBAN, BIC, and the actual payment reference number (viite) out of
    a transaction's detail block, plus keep the raw lines as free-text notes.
    """
    iban = None
    bic = None
    payment_ref = None
    in_identification_block = False

    for line in detail_lines:
        if IDENTIFICATION_MARKER_RE.search(line):
            in_identification_block = True
            continue

        if iban is None:
            iban_match = IBAN_RE.search(line)
            if iban_match:
                iban = iban_match.group(0)

        if bic is None and line.upper() != "NOTPROVIDED" and BIC_RE.match(line):
            bic = line

        if in_identification_block and payment_ref is None:
            if PURE_DIGITS_RE.match(line) and line.upper() != "NOTPROVIDED":
                payment_ref = line

    notes = "; ".join(
        line for line in detail_lines
        if line.upper() != "NOTPROVIDED" and not BIC_RE.match(line) and not IBAN_RE.fullmatch(line)
    )

    return {"iban": iban, "bic": bic, "payment_ref": payment_ref, "notes": notes}


def parse_transactions(lines):
    transactions = []
    current_date = None
    i = 0

    while i < len(lines):
        line = lines[i]

        registr_match = REGISTR_DAG_RE.search(line)
        if registr_match:
            current_date = datetime.strptime(registr_match.group(1), "%d.%m.%Y").date()
            i += 1
            continue

        tx_match = TRANSACTION_RE.match(line)
        if tx_match:
            amount = float(tx_match.group("amount").replace(",", "."))
            if tx_match.group("sign") == "-":
                amount = -amount

            # Collect this transaction's detail lines (everything until the
            # next transaction, a REGISTR.DAG marker, or a summary/footer line).
            detail_lines = []
            j = i + 1
            while j < len(lines) and not TRANSACTION_RE.match(lines[j]) and not DETAIL_STOP_RE.match(lines[j]):
                detail_lines.append(lines[j])
                j += 1

            extras = _extract_transaction_extras(detail_lines)

            transactions.append({
                "date": current_date or datetime.today().date(),
                "amount": amount,
                "ref": tx_match.group("ref"),
                "desc": tx_match.group("desc").strip(),
                "payment_ref": extras["payment_ref"],
                "counterparty_iban": extras["iban"],
                "counterparty_bic": extras["bic"],
                "notes": extras["notes"],
            })

            i = j
            continue

        i += 1

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
