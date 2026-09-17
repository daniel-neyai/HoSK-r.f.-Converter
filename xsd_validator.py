# xsd_validator.py
#
# HoSK r.f. Bank Statement Converter
# CAMT.053.001.02 XSD validation
#
# © 2026 Daniel Lucas Neyai. All rights reserved.

import os
from lxml import etree


CAMT_NAMESPACE = (
    "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"
)


class XSDValidationError(Exception):
    """Raised when CAMT XML fails XSD validation."""


def get_xsd_path():
    """
    Locate the bundled CAMT XSD.

    Works both when running from Python and when packaged
    with PyInstaller.
    """

    possible_paths = []

    # Normal development environment
    possible_paths.append(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "camt.053.001.02.xsd",
        )
    )

    # PyInstaller one-file / one-folder environment
    if hasattr(__import__("sys"), "_MEIPASS"):
        possible_paths.append(
            os.path.join(
                __import__("sys")._MEIPASS,
                "assets",
                "camt.053.001.02.xsd",
            )
        )

    for path in possible_paths:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "CAMT.053.001.02 XSD schema was not found.\n\n"
        "Expected location:\n"
        "assets\\camt.053.001.02.xsd"
    )


def load_schema(xsd_path=None):
    """
    Load the CAMT.053.001.02 XSD schema.
    """

    if xsd_path is None:
        xsd_path = get_xsd_path()

    try:
        with open(
            xsd_path,
            "rb",
        ) as f:
            xsd_data = f.read()

        schema_doc = etree.XML(
            xsd_data
        )

        return etree.XMLSchema(
            schema_doc
        )

    except etree.XMLSyntaxError as exc:
        raise XSDValidationError(
            "The CAMT XSD schema itself is invalid:\n\n"
            f"{exc}"
        )


def validate_xml_tree(xml_tree, xsd_path=None):
    """
    Validate an lxml XML tree against CAMT.053.001.02.

    Returns:
        True

    Raises:
        XSDValidationError
    """

    schema = load_schema(
        xsd_path
    )

    if not schema.validate(xml_tree):
        errors = []

        for error in schema.error_log:
            errors.append(
                f"Line {error.line}: "
                f"{error.message}"
            )

        message = (
            "CAMT.053.001.02 XSD VALIDATION FAILED\n\n"
            + "\n".join(errors)
        )

        raise XSDValidationError(
            message
        )

    return True


def validate_xml_file(xml_path, xsd_path=None):
    """
    Validate an XML file directly.
    """

    try:
        parser = etree.XMLParser(
            remove_blank_text=False
        )

        tree = etree.parse(
            xml_path,
            parser,
        )

    except (etree.XMLSyntaxError, OSError) as exc:
        raise XSDValidationError(
            "Could not read XML file:\n\n"
            f"{exc}"
        )

    return validate_xml_tree(
        tree,
        xsd_path,
    )


def validate_xml_bytes(xml_bytes, xsd_path=None):
    """
    Validate XML supplied as bytes.
    """

    try:
        root = etree.fromstring(
            xml_bytes
        )

        tree = root.getroottree()

    except etree.XMLSyntaxError as exc:
        raise XSDValidationError(
            "Generated XML is not well-formed:\n\n"
            f"{exc}"
        )

    return validate_xml_tree(
        tree,
        xsd_path,
    )


def get_validation_errors(xml_path, xsd_path=None):
    """
    Return validation errors without raising an exception.

    Useful for GUI preview/diagnostics.
    """

    try:
        parser = etree.XMLParser(
            remove_blank_text=False
        )

        tree = etree.parse(
            xml_path,
            parser,
        )

        schema = load_schema(
            xsd_path
        )

        if schema.validate(tree):
            return []

        return [
            {
                "line": error.line,
                "column": error.column,
                "message": error.message,
                "type": error.type_name,
            }
            for error in schema.error_log
        ]

    except Exception as exc:
        return [
            {
                "line": None,
                "column": None,
                "message": str(exc),
                "type": "VALIDATION_ERROR",
            }
        ]
