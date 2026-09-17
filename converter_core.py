from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from datetime import datetime


def build_camt053(data, config=None):
    ns = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"
    currency = config.get("currency", "EUR") if config else "EUR"

    Document = Element("Document", xmlns=ns)
    stmt_root = SubElement(Document, "BkToCstmrStmt")
    Stmt = SubElement(stmt_root, "Stmt")

    SubElement(Stmt, "Id").text = f"STATEMENT-{data['period_to']}"
    SubElement(Stmt, "CreDtTm").text = datetime.now().isoformat()

    acct = SubElement(Stmt, "Acct")
    SubElement(SubElement(acct, "Id"), "IBAN").text = data["iban"]
    SubElement(acct, "Ccy").text = currency

    def add_balance(code, amount):
        bal = SubElement(Stmt, "Bal")
        tp = SubElement(bal, "Tp")
        cd_or_prtry = SubElement(tp, "CdOrPrtry")
        SubElement(cd_or_prtry, "Cd").text = code
        SubElement(bal, "Amt", Ccy=currency).text = f"{abs(amount):.2f}"
        SubElement(bal, "CdtDbtInd").text = "CRDT" if amount >= 0 else "DBIT"

    add_balance("OPBD", data["opening"])
    add_balance("CLBD", data["closing"])

    for tx in data.get("transactions", []):
        Ntry = SubElement(Stmt, "Ntry")
        SubElement(Ntry, "NtryRef").text = f"N{tx.get('ref', '000')}"
        SubElement(Ntry, "Amt", Ccy=currency).text = f"{tx['amount']:.2f}"
        SubElement(Ntry, "CdtDbtInd").text = "CRDT" if tx["amount"] >= 0 else "DBIT"
        SubElement(SubElement(Ntry, "BookgDt"), "Dt").text = tx["date"].isoformat()

        ntry_dtls = SubElement(Ntry, "NtryDtls")
        tx_dtls = SubElement(ntry_dtls, "TxDtls")
        refs = SubElement(tx_dtls, "Refs")
        SubElement(refs, "MsgId").text = tx.get("ref", "")
        SubElement(tx_dtls, "RmtInf").text = tx.get("desc", "")

    xml = minidom.parseString(tostring(Document)).toprettyxml(indent="  ")
    return xml
