"""This module provides utilities for working with XML data, including
functions to convert dictionaries to XML, escape XML special characters, and
classes to parse XML into dictionary-like structures.
"""
import contextlib

with contextlib.suppress(ImportError):
    from defusedxml import ElementTree


def dict2xml(d, elementname="element", pretty=True, allow_attributes=True, level=0):
    indent = (pretty and "\t" * level) or ""
    xml = []
    attributes = []
    children = []

    if isinstance(d, (dict, list)):
        start_tag = []
        start_tag.append(indent + "<" + elementname)

        if isinstance(d, dict):
            for key in d:
                value = d[key]
                if isinstance(value, (dict, list)) or not allow_attributes:
                    children.append(
                        dict2xml(value, key, pretty, allow_attributes, level + 1)
                    )
                else:
                    if pretty:
                        attributes.append("\n" + indent)
                    attributes.append(f' {key}="{escape(str(value))}"')
        else:
            for value in d:
                children.append(
                    dict2xml(value, "item", pretty, allow_attributes, level + 1)
                )

        start_tag.extend(attributes)
        start_tag.append((children and ">") or "/>")
        xml.append("".join(start_tag))

        if children:
            xml += children
            xml.append(f"{indent}</{elementname}>")
    else:
        xml.append(f"{indent}<{elementname}>{escape(str(d))}</{elementname}>")

    return ((pretty and "\n") or "").join(xml)


def escape(xml):
    return (
        xml.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class ETreeDict(dict):
    # Roughly follow "Converting Between XML and JSON"
    # https://www.xml.com/pub/a/2006/05/31/converting-between-xml-and-json.html

    def __init__(self, etree):
        super().__init__()
        children = len(etree)
        if etree.attrib or etree.text or children:
            self[etree.tag] = {f"@{k}": v for k, v in etree.attrib.items()}
            if etree.text:
                text = etree.text.strip()
                if etree.attrib or children:
                    if text:
                        self[etree.tag]["#text"] = text
                else:
                    self[etree.tag] = text
            if children:
                d = self[etree.tag]
                for child in etree:
                    for k, v in ETreeDict(child).items():
                        if k in d:
                            if not isinstance(d[k], list):
                                d[k] = [d[k]]
                            d[k].append(v)
                        else:
                            d[k] = v
        else:
            self[etree.tag] = None

    def __repr__(self):
        """od.__repr__() <==> repr(od)"""
        l = []
        for k in self:
            v = self[k]
            l.append(f"{k!r}: {v!r}")
        return "{{{}}}".format(", ".join(l))

    @property
    def json(self):
        import json

        return json.dumps(self)


class XMLDict(ETreeDict):
    def __init__(self, xml):
        etree = ElementTree.fromstring(xml)
        ETreeDict.__init__(self, etree)
