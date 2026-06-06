"""IP-XACT (IEEE 1685) export.

IP-XACT is the XML standard for *describing* an IP component: its VLNV identity,
its source filesets, and a model of build views. Many EDA tools (Vivado in
particular) ingest IP-XACT, so exporting one lets a core authored with this
packager be consumed by the wider tool ecosystem. We borrow IP-XACT's VLNV scheme
already (see ``vlnv.py``); here we emit a component document from a manifest.

:func:`to_ipxact` is **pure**: it maps a :class:`~hdl_ip_packager.manifest.Manifest`
to a deterministic XML string (no I/O), so the CLI ``export-ipxact`` command is a
thin write wrapper. The output targets the **1685-2014** schema and is well-formed
and structurally conventional (VLNV, then a ``model`` of one view +
componentInstantiation per ``[targets.*]``, then the ``fileSets``); validating it
against the official XSD is tracked as a follow-up. Conveniently, the manifest
fileset ``type`` vocabulary (``systemVerilogSource``/``verilogSource``/
``vhdlSource``) is already the IP-XACT ``fileType`` vocabulary, so it passes
straight through.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .manifest import Manifest

__all__ = ["IPXACT_NAMESPACE", "to_ipxact"]

IPXACT_NAMESPACE = "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    """Append a namespaced ``ipxact:<tag>`` child, optionally with text."""
    element = ET.SubElement(parent, f"{{{IPXACT_NAMESPACE}}}{tag}")
    if text is not None:
        element.text = text
    return element


def to_ipxact(manifest: Manifest) -> str:
    """Render *manifest* as an IEEE 1685-2014 IP-XACT component XML document."""
    ET.register_namespace("ipxact", IPXACT_NAMESPACE)
    ET.register_namespace("xsi", _XSI_NAMESPACE)

    component = ET.Element(f"{{{IPXACT_NAMESPACE}}}component")
    component.set(
        f"{{{_XSI_NAMESPACE}}}schemaLocation",
        f"{IPXACT_NAMESPACE} {IPXACT_NAMESPACE}/index.xsd",
    )

    vlnv = manifest.vlnv
    _sub(component, "vendor", vlnv.vendor)
    _sub(component, "library", vlnv.library)
    _sub(component, "name", vlnv.name)
    _sub(component, "version", str(vlnv.version))

    # model: one view + componentInstantiation per build target.
    if manifest.targets:
        model = _sub(component, "model")
        views = _sub(model, "views")
        for target_name in manifest.targets:
            view = _sub(views, "view")
            _sub(view, "name", target_name)
            _sub(view, "componentInstantiationRef", target_name)
        instantiations = _sub(model, "instantiations")
        for target_name, target in manifest.targets.items():
            inst = _sub(instantiations, "componentInstantiation")
            _sub(inst, "name", target_name)
            module = target.top or manifest.top
            if module is not None:
                _sub(inst, "moduleName", module)
            for fileset_name in target.filesets:
                ref = _sub(inst, "fileSetRef")
                _sub(ref, "localName", fileset_name)

    # fileSets: the source files, grouped, with their IP-XACT fileType.
    if manifest.filesets:
        filesets = _sub(component, "fileSets")
        for name, fileset in manifest.filesets.items():
            fs_element = _sub(filesets, "fileSet")
            _sub(fs_element, "name", name)
            for path in fileset.files:
                file_element = _sub(fs_element, "file")
                _sub(file_element, "name", path)
                _sub(file_element, "fileType", fileset.type)

    if manifest.description:
        _sub(component, "description", manifest.description)

    ET.indent(component, space="  ")
    body = ET.tostring(component, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
