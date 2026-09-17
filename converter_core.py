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
        is_credit = tx["amount"] >= 0
        ref = tx.get("ref", "") or "000"
        name = tx.get("desc", "").strip()

        Ntry = SubElement(Stmt, "Ntry")
        SubElement(Ntry, "NtryRef").text = f"N{ref}"
        # Amt must always be non-negative per ISO 20022 — sign belongs only in CdtDbtInd.
        SubElement(Ntry, "Amt", Ccy=currency).text = f"{abs(tx['amount']):.2f}"
        SubElement(Ntry, "CdtDbtInd").text = "CRDT" if is_credit else "DBIT"
        SubElement(SubElement(Ntry, "BookgDt"), "Dt").text = tx["date"].isoformat()
        SubElement(SubElement(Ntry, "ValDt"), "Dt").text = tx["date"].isoformat()

        # BkTxCd is mandatory in the camt.053.001.02 schema; without it some
        # importers fail to map the rest of the entry's fields correctly.
        bk_tx_cd = SubElement(Ntry, "BkTxCd")
        prtry = SubElement(bk_tx_cd, "Prtry")
        SubElement(prtry, "Cd").text = "NTRF"
        SubElement(prtry, "Issr").text = "AKTIA"

        ntry_dtls = SubElement(Ntry, "NtryDtls")
        tx_dtls = SubElement(ntry_dtls, "TxDtls")

        refs = SubElement(tx_dtls, "Refs")
        SubElement(refs, "AcctSvcrRef").text = ref
        SubElement(refs, "EndToEndId").text = ref

        if name:
            rltd_pties = SubElement(tx_dtls, "RltdPties")
            # On a debit, the counterparty received the money -> creditor.
            # On a credit, the counterparty sent the money -> debtor.
            party_tag = "Cdtr" if not is_credit else "Dbtr"
            SubElement(SubElement(rltd_pties, party_tag), "Nm").text = name

        if name:
            rmt_inf = SubElement(tx_dtls, "RmtInf")
            SubElement(rmt_inf, "Ustrd").text = name

        payment_ref = tx.get("payment_ref")
        if payment_ref:
            rmt_inf_strd = tx_dtls.find("RmtInf")
            if rmt_inf_strd is None:
                rmt_inf_strd = SubElement(tx_dtls, "RmtInf")
            strd = SubElement(rmt_inf_strd, "Strd")
            cdtr_ref_inf = SubElement(strd, "CdtrRefInf")
            SubElement(cdtr_ref_inf, "Ref").text = payment_ref

        counterparty_iban = tx.get("counterparty_iban")
        counterparty_bic = tx.get("counterparty_bic")
        if counterparty_iban or counterparty_bic:
            rltd_agts = SubElement(tx_dtls, "RltdAgts")
            if counterparty_bic:
                agt_tag = "CdtrAgt" if not is_credit else "DbtrAgt"
                fin_instn_id = SubElement(SubElement(rltd_agts, agt_tag), "FinInstnId")
                SubElement(fin_instn_id, "BIC").text = counterparty_bic

        notes = tx.get("notes")
        if notes:
            SubElement(tx_dtls, "AddtlTxInf").text = notes

    xml = minidom.parseString(tostring(Document)).toprettyxml(indent="  ")
    return xml
