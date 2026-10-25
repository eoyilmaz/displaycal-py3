"""Toolkit-neutral internals of the colorimeter-correction (CCMX/CCSS) pipeline.

The pure, window-agnostic pieces of ``MainFrame.create_colorimeter_correction_handler``
(``display_cal.py``): the Argyll / CGATS work that carries no wx (or Qt)
dependency, so both the shipping wx path and the future Qt window can call into
them. A plain ``DisplayCAL`` module (like ``main_settings.py`` /
``measurement_report.py``) so importing it never pulls in Qt.

The dialogs (create wizard, details prompt, the reference-vs-corrected preview
grid), the ``worker.Worker`` execution (``spec2cie`` / ``ccxxmake`` /
``create_ccxx``), and the file-save flow stay in their respective UI layers.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from hashlib import md5
from time import strftime, strptime, struct_time
from typing import TYPE_CHECKING

from DisplayCAL import ccmx, colord, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll import make_argyll_compatible_path
from DisplayCAL.argyll_instruments import get_canonical_instrument_name
from DisplayCAL.cgats import CGATS, CGATSError, CGATSInvalidError
from DisplayCAL.config import EXE_EXT
from DisplayCAL.debughelpers import Error, Info, Warn
from DisplayCAL.util_dict import swap_dict_keys_values
from DisplayCAL.util_os import get_program_file, getenvu, safe_glob, which
from DisplayCAL.util_str import ellipsis_

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

#: Hash algorithms accepted for the upload dedup/verification hash. Matches
#: the wx handler's ``globals()[algo_hash[0]]`` lookup, which in practice only
#: ever resolved ``"md5"`` (the only hash function imported at module scope).
_HASH_ALGORITHMS = {"md5": md5}

# The keyword injection order, top-to-bottom, must match the wx handler so the
# emitted CCXX bytes are identical (each field is inserted immediately above the
# DISPLAY line, so insertion order == line order).
_CCXX_METADATA_ORDER = (
    "reference",
    "technology",
    "manufacturer_id",
    "manufacturer",
    "observer",
    "reference_observer",
)
_CCXX_KEYWORDS = {
    "reference": b"REFERENCE",
    "technology": b"TECHNOLOGY",
    "manufacturer_id": b"MANUFACTURER_ID",
    "manufacturer": b"MANUFACTURER",
    "observer": b"OBSERVER",
    "reference_observer": b"REFERENCE_OBSERVER",
}


def _to_bytes(value: str | bytes) -> bytes:
    """Return ``value`` as UTF-8 bytes (passing bytes through unchanged)."""
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def _insert_ccxx_field(cgats: bytes, keyword: bytes, value: bytes) -> bytes:
    """Insert ``keyword "value"`` immediately above the ``DISPLAY`` line.

    A no-op if the keyword is already present. Backslashes in ``value`` are
    escaped so they survive the ``re.sub`` replacement as literals (matching the
    wx handler).
    """
    if re.search(rb"\n" + keyword + rb'\s+".+?"\n', cgats):
        return cgats
    escaped = value.replace(b"\\", b"\\\\")
    return re.sub(
        rb'(\nDISPLAY\s+"[^"]*"\n)',
        b"\n" + keyword + b' "' + escaped + b'"\\1',
        cgats,
    )


def inject_ccxx_metadata(
    cgats: bytes,
    *,
    reference: str | bytes | None = None,
    technology: str | bytes | None = None,
    manufacturer_id: str | bytes | None = None,
    manufacturer: str | bytes | None = None,
    observer: str | bytes | None = None,
    reference_observer: str | bytes | None = None,
) -> bytes:
    """Inject the optional CCMX/CCSS metadata fields Argyll omits by default.

    Ports the ``REFERENCE`` / ``TECHNOLOGY`` / ``MANUFACTURER_ID`` /
    ``MANUFACTURER`` / ``OBSERVER`` / ``REFERENCE_OBSERVER`` byte rewrites in
    ``create_colorimeter_correction_handler``. Each field is added only when a
    truthy value is supplied and the keyword is not already present, inserted
    above the ``DISPLAY`` line in the fixed order above. ``str`` values are
    UTF-8 encoded (the wx path emitted a mix of already-bytes and UTF-8 encoded
    values; normalising here is byte-identical for real-world inputs, which
    never contain backslashes).

    Args:
        cgats: The raw CCXX file bytes as emitted by ``ccxxmake`` /
            ``create_ccxx`` (must not be re-parsed CGATS, whose keyword order
            may differ, changing the MD5).
        reference: Reference instrument (``TARGET_INSTRUMENT``).
        technology: Display technology string.
        manufacturer_id: PnP manufacturer id.
        manufacturer: Manufacturer name.
        observer: Colorimeter observer.
        reference_observer: Reference observer.

    Returns:
        The (possibly) modified CCXX bytes.
    """
    values = {
        "reference": reference,
        "technology": technology,
        "manufacturer_id": manufacturer_id,
        "manufacturer": manufacturer,
        "observer": observer,
        "reference_observer": reference_observer,
    }
    for field in _CCXX_METADATA_ORDER:
        value = values[field]
        if value:
            cgats = _insert_ccxx_field(cgats, _CCXX_KEYWORDS[field], _to_bytes(value))
    return cgats


def get_cgats_path(cgats: bytes) -> str:
    """Return the default save path for a CCMX/CCSS file's raw bytes.

    Ports ``display_cal.get_cgats_path``: the file is named after the
    ``DESCRIPTOR`` field (falling back to "unnamed"), sanitised for the
    filesystem and Argyll, with the extension taken from the CGATS type
    keyword on the first line (``CCMX`` / ``CCSS``), saved under the Argyll
    data dir.

    Args:
        cgats: The raw CCXX file bytes.

    Returns:
        The full path to save the file to.
    """
    descriptor = re.search(rb'\nDESCRIPTOR\s+"(.+?)"\n', cgats)
    descriptor = descriptor.groups()[0] if descriptor else b""
    description = descriptor.decode("utf-8") or lang.getstr("unnamed")
    name = make_argyll_compatible_path(description, is_name=True)[:255]
    extension = cgats.split()[0].lower().decode("utf-8")
    return os.path.join(config.get_argyll_data_dir(), f"{name}.{extension}")


# -- Web check ----------------------------------------------------------------

#: Localized-label lookup for the "type" column, keyed by the CGATS type
#: keyword (matches ``colorimeter_correction_web_check_choose``).
_WEB_CHECK_TYPE_LABELS = {
    "CCSS": lambda: lang.getstr("spectral").replace(":", ""),
    "CCMX": lambda: lang.getstr("matrix").replace(":", ""),
}

_MONTH_ABBREVIATIONS = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


def build_web_check_params(worker: Worker) -> dict:
    """Build the GET params for the online colorimeter-correction lookup.

    Toolkit-neutral port of the param-building half of
    ``MainFrame.colorimeter_correction_web_handler`` (the ``http_request``
    call itself, and its progress reporting, stay with the caller).

    Uses ``worker.get_display_generic_name()`` (falling back to
    ``get_display_name()``) for the ``display`` param: the online database is
    keyed by generic monitor names ("Color LCD"), and for Apple built-in
    displays ``get_display_name()`` substitutes the machine model id
    ("MacBookPro18,1"), which the database has no entries for.

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker`, used to derive
            the current display/instrument.

    Returns:
        dict: The request params (``get``, ``type``, ``manufacturer_id``,
            ``display``, ``instrument``, ``json``).
    """
    filetype = "ccss,ccmx" if worker.instrument_supports_ccss() else "ccmx"
    return {
        "get": True,
        "type": filetype,
        "manufacturer_id": worker.get_display_edid().get("manufacturer_id", ""),
        "display": worker.get_display_generic_name()
        or worker.get_display_name(False, True)
        or "Unknown",
        "instrument": worker.get_instrument_name() or "Unknown",
        "json": 1,
    }


def _web_check_spectral_resolution(item: dict) -> str:
    spectral = {}
    for key in ("bands", "start_nm", "end_nm"):
        try:
            v = float(item.get(f"spectral_{key}", 0))
        except (TypeError, ValueError):
            continue
        if v:
            spectral[key] = v
    if not spectral or len(spectral) < 3:
        return lang.getstr("unknown")
    return "{:.1f}nm, {:.0f}-{:.0f}nm".format(
        (spectral["end_nm"] - spectral["start_nm"]) / (spectral["bands"] - 1),
        spectral["start_nm"],
        spectral["end_nm"],
    )


def _web_check_created(item: dict) -> str:
    created = item.get("created")
    if not created:
        return lang.getstr("unknown")
    try:
        created = strptime(created)
    except ValueError:
        datetmp = re.search(
            r"\w+ (\w{3}) (\d{2}) (\d{2}(?::[0-5][0-9]){2}) (\d{4})", created
        )
        if not datetmp:
            return created
        year, month_abbr, day, time_part = (
            datetmp.groups()[3],
            datetmp.groups()[0],
            datetmp.groups()[1],
            datetmp.groups()[2],
        )
        datetmp = f"{year}-{_MONTH_ABBREVIATIONS.get(month_abbr)}-{day} {time_part}"
        try:
            created = strptime(datetmp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return item["created"]
    if isinstance(created, struct_time):
        return strftime("%Y-%m-%d %H:%M:%S", created)
    return created


def parse_web_check_entries(
    entries: list[dict], observer_labels: None | dict[str, str] = None
) -> list[dict]:
    """Turn JSON correction entries from the online DB into display-ready rows.

    Toolkit-neutral port of the per-entry loop in
    ``colorimeter_correction_web_check_choose`` (everything except building
    and driving the wx list-control dialog): CGATS parsing, the
    manufacturer/display quirking, the spectral-resolution summary, the
    created-date normalisation and the fit-method label. Fixes a latent bug
    in the wx handler: it looked ``REFERENCE_OBSERVER`` (``queryv1`` returns
    ``bytes``) up directly in the str-keyed ``observers_ab`` map, so the
    lookup never matched and the "observer" column always showed "unknown".
    This port decodes the key first, so a supplied ``observer_labels`` map
    actually resolves.

    Args:
        entries: The parsed JSON list from the web-check response (a list of
            ``dict``, each describing one correction).
        observer_labels: Optional ``observer value -> localized label`` map
            (see :func:`DisplayCAL.ui.measurement_flow.observer_items`), used
            for the ``REFERENCE_OBSERVER`` column. Defaults to no lookup
            (raw observer key, or "unknown"/"not_applicable").

    Returns:
        list[dict]: One row per entry, each with ``cgats`` (raw bytes,
            required to save byte-identically) plus the display fields
            ``type``, ``description``, ``display``, ``reference``,
            ``spectral_resolution``, ``observer``, ``fit_method``,
            ``fit_avg_de00``, ``fit_max_de00``, ``created``.
    """
    observer_labels = observer_labels or {}
    rows = []
    for item in entries:
        # CGATS is byte string based, make sure to encode Unicode back to
        # UTF-8 for parsing. CGATS accepts ``bytes`` data only.
        cgats_bytes = item.get("cgats", "").encode("utf-8")
        try:
            ccxx = CGATS(cgats_bytes)
        except CGATSError:
            cgats_bytes = b""
            ccxx = CGATS()
        ccxx = ccxx.get(0, ccxx)
        ccxx_type = item.get("type", "").upper()
        manufacturer = colord.quirk_manufacturer(
            item.get("manufacturer") or lang.getstr("unknown")
        )
        display = item.get("display") or lang.getstr("unknown")
        if config.is_virtual_display(display):
            display = manufacturer
        if not display.lower().startswith(manufacturer.lower()):
            display = f"{manufacturer} {display}"
        fit_method = ccxx.queryv1("FIT_METHOD")
        if fit_method and fit_method != b"xy":
            fit_method = lang.getstr("perceptual")
        elif isinstance(fit_method, bytes):
            # Same bytes/str inconsistency as REFERENCE_OBSERVER above: only
            # the "perceptual" branch localized to str, leaving the raw "xy"
            # case as bytes.
            fit_method = fit_method.decode("utf-8")
        is_ccmx = ccxx_type == "CCMX"
        reference_observer = ccxx.queryv1("REFERENCE_OBSERVER")
        if isinstance(reference_observer, bytes):
            # The wx handler looked this bytes value up in a str-keyed dict
            # directly, so it never matched (always fell through to
            # "unknown"/"not_applicable"); decode so the lookup actually
            # works.
            reference_observer = reference_observer.decode("utf-8")
        rows.append(
            {
                "cgats": cgats_bytes,
                "type": _WEB_CHECK_TYPE_LABELS.get(ccxx_type, lambda t=ccxx_type: t)(),
                "description": get_canonical_instrument_name(
                    item.get("description") or lang.getstr("unknown")
                ),
                "display": display,
                "reference": get_canonical_instrument_name(
                    item.get("reference") or lang.getstr("unknown")
                ),
                "spectral_resolution": _web_check_spectral_resolution(item),
                "observer": observer_labels.get(
                    reference_observer,
                    lang.getstr("unknown" if is_ccmx else "not_applicable"),
                ),
                "fit_method": (
                    (fit_method or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "fit_avg_de00": (
                    str(ccxx.queryv1("FIT_AVG_DE00") or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "fit_max_de00": (
                    str(ccxx.queryv1("FIT_MAX_DE00") or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "created": _web_check_created(item),
            }
        )
    return rows


# -- Upload ---------------------------------------------------------------


def validate_upload_originator(cgats_text: str, appname: str) -> bool:
    """Return whether ``cgats_text`` claims an Argyll/``appname`` origin.

    Port of the ``ORIGINATOR`` check in
    ``MainFrame.upload_colorimeter_correction_handler``, which refuses to
    offer upload for files this application didn't (help) create.
    """
    return bool(
        re.search(r'\nORIGINATOR\s+"Argyll', cgats_text)
        or re.search(r'\nORIGINATOR\s+"' + re.escape(appname), cgats_text)
    )


def compute_upload_dedup_hash(cgats: bytes) -> str:
    """Return the MD5 hash used to detect an already-uploaded correction.

    Port of the hash in ``upload_colorimeter_correction`` (module-level,
    ``display_cal.py``): the ``CREATED`` date is stripped first so re-runs of
    the same correction hash identically regardless of when it was made.
    """
    return md5(  # noqa: S324
        re.sub(rb'\nCREATED\s+".+?"\n', rb"\n\n", cgats).strip()
    ).hexdigest()


def build_upload_params(cgats: bytes | str) -> dict:
    """Build the upload params for a CCMX/CCSS correction, with provenance.

    Toolkit-neutral port of the param-building in
    ``MainFrame.upload_colorimeter_correction`` (the confirm dialog and the
    actual HTTP round-trip stay with the caller): strips the platform-specific
    ``REFERENCE``/``TARGET_FILENAME`` fields, then adds the referenced
    reference/target CGATS measurement files verbatim if they still exist on
    disk and match the hash recorded in the correction file.

    Fixes a latent crash in the wx handler: ``upload_colorimeter_correction_
    handler`` reads the file as ``str`` (``.decode()``) and passes it straight
    through, but the byte-stripping regex below uses a ``bytes`` pattern,
    which raises ``TypeError`` against a ``str`` subject. Only the create-
    correction call site (which already holds ``bytes``) avoided it. This
    port normalises to ``bytes`` upfront so both call shapes work.

    Args:
        cgats: The raw correction file bytes or text (not re-parsed CGATS,
            whose keyword order may differ and change the MD5 the server
            sees).

    Returns:
        dict: ``{"cgats": <bytes>}`` plus optional ``reference_cgats`` /
            ``target_cgats`` entries.
    """
    if isinstance(cgats, str):
        cgats = cgats.encode("utf-8")
    ccxx = CGATS(cgats)
    cgats = re.sub(rb'\n(?:REFERENCE|TARGET)_FILENAME\s+"[^"]+"\n', b"\n", cgats)
    params = {"cgats": cgats}
    for label in ("REFERENCE", "TARGET"):
        filename = (ccxx.queryv1(f"{label}_FILENAME") or b"").decode("utf-8")
        algo_hash = ((ccxx.queryv1(f"{label}_HASH") or b"").decode("utf-8")).split(
            ":", 1
        )
        algo = _HASH_ALGORITHMS.get(algo_hash[0])
        if filename and algo and os.path.isfile(filename):
            meas = bytes(CGATS(filename)).strip()
            if algo(meas).hexdigest() == algo_hash[-1]:
                params[label.lower() + "_cgats"] = meas
    return params


# -- Import -----------------------------------------------------------------


def get_argyll_data_files(
    worker: Worker,
    scope: str,
    wildcard: str,
    include_lastmod: bool = False,
) -> list[str | tuple[str, float]]:
    """Get paths of Argyll data files.

    Toolkit-neutral port of ``MainFrame.get_argyll_data_files`` (``self`` ->
    ``worker``, the only instance state it reads).

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker` (only its
            ``argyll_version`` is consulted, for a macOS Argyll 1.9.x quirk).
        scope: A string containing "l" for local system and/or "u" for user.
        wildcard: A wildcard pattern to match files.
        include_lastmod: If True, include the last modification time of the
            files.

    Returns:
        list[str | tuple[str, float]]: A list of file paths, or (path,
            last-modified) tuples if ``include_lastmod``.
    """
    data_files = []
    if sys.platform != "darwin":
        if "l" in scope:
            for commonappdata in config.COMMONAPPDATA:
                data_files += safe_glob(os.path.join(commonappdata, "color", wildcard))
                data_files += safe_glob(
                    os.path.join(commonappdata, "ArgyllCMS", wildcard)
                )
        if "u" in scope:
            data_files += safe_glob(os.path.join(config.APPDATA, "color", wildcard))
    else:
        if "l" in scope:
            data_files += safe_glob(os.path.join(config.LIBRARY, "color", wildcard))
            data_files += safe_glob(os.path.join(config.LIBRARY, "ArgyllCMS", wildcard))
            if [1, 9] <= worker.argyll_version <= [1, 9, 1]:
                # Argyll CMS 1.9 and 1.9.1 use *nix locations due to a
                # configuration problem
                data_files += safe_glob(
                    os.path.join("/usr/local/share", "ArgyllCMS", wildcard)
                )
        if "u" in scope:
            data_files += safe_glob(
                os.path.join(config.LIBRARY_HOME, "color", wildcard)
            )
            if [1, 9] <= worker.argyll_version <= [1, 9, 1]:
                # Argyll CMS 1.9 and 1.9.1 use *nix locations due to a
                # configuration problem
                data_files += safe_glob(
                    os.path.join(config.HOME, ".local", "share", "ArgyllCMS", wildcard)
                )
    if "u" in scope:
        data_files += safe_glob(os.path.join(config.APPDATA, "ArgyllCMS", wildcard))

    # Prefer files with the same basename in the "ArgyllCMS" folder over the
    # "color" folder.
    mapping: dict[str, str] = {}
    for filename in data_files:
        basename = os.path.basename(filename)
        if (
            basename not in mapping
            or os.path.basename(os.path.dirname(filename)) == "ArgyllCMS"
        ):
            mapping[basename] = filename

    if include_lastmod:
        result = []
        for filename in mapping.values():
            try:
                lastmod = os.stat(filename).st_mtime
            except OSError:
                lastmod = -1
            result.append((filename, lastmod))
        return result
    return list(mapping.values())


def discover_auto_import_paths(
    importers: dict,
    i1d3: bool,
    i1d3ccss: bool,
    spyd4: bool,
    spyd4en: bool,
    oeminst: str,
) -> dict[str, list[str]]:
    """Locate on-disk OEM installer files for the "auto" import mode.

    Toolkit-neutral port of the file-discovery half of
    ``MainFrame.import_colorimeter_corrections_producer`` (the trailing
    web-download fallback, which needs ``worker.download``, stays with the
    caller). Pure ``os``/``sys.platform`` globbing, no worker/wx dependency.

    Args:
        importers: Which importers the user selected, as returned by the
            import dialog (keys among ``"icd"``, ``"i1d3"``, ``"spyd4"``).
        i1d3: Whether an i1D3 correction was already imported this run
            (skips the i1D3 lookup).
        i1d3ccss: Whether the ``i1d3ccss`` Argyll utility is available.
        spyd4: Whether a Spyder4/5 correction was already imported this run
            (skips the Spyder4/5 lookup).
        spyd4en: Whether the ``spyd4en`` Argyll utility is available.
        oeminst: Path to the ``oeminst`` Argyll utility, or falsy.

    Returns:
        dict[str, list[str]]: ``{"icd": [...], "i1d3": [...], "spyd4": [...]}``
            for each requested, not-yet-imported importer (only keys with at
            least one discovered path are present).
    """
    found: dict[str, list[str]] = {}
    if importers.get("icd"):
        if sys.platform == "win32":
            icdfn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""),
                    "Quato",
                    "iColorDisplay",
                    "DeviceCorrections.txt",
                )
            )
        elif sys.platform == "darwin":
            icdfn = safe_glob(
                os.path.join(
                    os.path.sep,
                    "Applications",
                    "iColorDisplay*.app",
                    "DeviceCorrections.txt",
                )
            )
            if not icdfn:
                icdfn = safe_glob(
                    os.path.join(
                        os.path.sep,
                        "Volumes",
                        "iColorDisplay*",
                        "iColorDisplay*.app",
                        "DeviceCorrections.txt",
                    )
                )
        else:
            icdfn = []
        if icdfn:
            found["icd"] = icdfn
    if importers.get("i1d3") and (oeminst or i1d3ccss) and not i1d3:
        if sys.platform == "win32":
            i1d3fn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""),
                    "X-Rite",
                    "Devices",
                    "i1d3",
                    "Calibrations",
                    "*.edr",
                )
            )
        elif sys.platform == "darwin":
            i1d3fn = safe_glob(
                os.path.join(
                    os.path.sep,
                    "Library",
                    "Application Support",
                    "X-Rite",
                    "Devices",
                    "i1d3xrdevice",
                    "Contents",
                    "Resources",
                    "Calibrations",
                    "*.edr",
                )
            )
            if not i1d3fn:
                i1d3fn = safe_glob(
                    os.path.join(os.path.sep, "Volumes", "i1Profiler", "*Setup.exe")
                )
            if not i1d3fn:
                i1d3fn = safe_glob(
                    os.path.join(
                        os.path.sep, "Volumes", "ColorMunki Display", "*Setup.exe"
                    )
                )
        else:
            i1d3fn = []
        if i1d3fn:
            found["i1d3"] = i1d3fn
    if importers.get("spyd4") and (oeminst or spyd4en) and not spyd4:
        if sys.platform == "win32":
            spydfn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""), "Datacolor", "Spyder5*", "dccmtr.dll"
                )
            )
            if not spydfn:
                spydfn = safe_glob(
                    os.path.join(
                        getenvu("PROGRAMFILES", ""),
                        "Datacolor",
                        "Spyder4*",
                        "dccmtr.dll",
                    )
                )
        elif sys.platform == "darwin":
            spydfn = safe_glob(
                os.path.join(os.path.sep, "Volumes", "Datacolor", "Data", "Setup.exe")
            )
            if not spydfn:
                spydfn = safe_glob(
                    os.path.join(
                        os.path.sep, "Volumes", "Datacolor_ISO", "Data", "Setup.exe"
                    )
                )
        else:
            spydfn = []
        if spydfn:
            found["spyd4"] = spydfn
    return found


def detect_import_kind(
    worker: Worker,
    result: bool | Exception,
    i1d3: bool,
    i1d3ccss: bool,
    spyd4: bool,
    spyd4en: bool,
    icd: bool,
    oeminst: str,
    path: str | list,
    asroot: bool,
) -> tuple[bool | Exception, bool, bool, bool]:
    """Import colorimeter correction(s) from ``path``.

    Toolkit-neutral port of ``MainFrame.import_colorimeter_correction``
    (``self`` -> ``worker``, ``self.get_argyll_data_files`` ->
    :func:`get_argyll_data_files`): detects what kind of OEM export ``path``
    is (iColor Display's ``DeviceCorrections.txt``, possibly packaged in a
    ``.dmg``/``.cab``/``.exe``; an X-Rite ``.edr``; a Spyder4/5 install; or an
    Argyll ``oeminst``-supported package) and runs the matching
    ``worker.Worker`` import method.

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker`.
        result: Result of the import operation so far.
        i1d3: Whether i1D3 corrections were imported.
        i1d3ccss: Whether the ``i1d3ccss`` Argyll utility is available.
        spyd4: Whether Spyder4/5 corrections were imported.
        spyd4en: Whether the ``spyd4en`` Argyll utility is available.
        icd: Whether iColor Display corrections were imported.
        oeminst: Path to the ``oeminst`` Argyll utility, or falsy.
        path: Path(s) to the correction file(s)/installer to import from.
        asroot: Whether to install as root (system-wide).

    Returns:
        tuple: ``(result, i1d3, spyd4, icd)``, each possibly updated.
    """
    kind = None
    icolordisplay = False
    if isinstance(path, list):
        kind = "xrite"
    elif path and os.path.exists(path):
        ext = os.path.splitext(path)[1]
        kind = "unknown"
        if ext.lower() == ".txt":
            kind = "icd"
            result = True
        else:
            icolordisplay = "icolordisplay" in os.path.basename(path).lower()
            if ext.lower() == ".dmg":
                if icolordisplay:
                    kind = "icd"
                    result = worker.exec_cmd(
                        which("hdiutil"),
                        ["attach", path],
                        capture_output=True,
                        skip_scripts=True,
                    )
                    if result and not isinstance(result, Exception):
                        for _path in safe_glob(
                            os.path.join(
                                os.path.sep,
                                "Volumes",
                                "iColorDisplay*",
                                "iColorDisplay*.app",
                                "Contents",
                                "Resources",
                                "DeviceCorrections.txt",
                            )
                        ):
                            break
                        else:
                            result = Error(
                                lang.getstr("file.missing", "DeviceCorrections.txt")
                            )
            elif i1d3ccss and ext.lower() == ".edr":
                kind = "xrite"
            elif ext.lower() in (".cab", ".exe"):
                if icolordisplay:
                    kind = "icd"
                    sevenzip = get_program_file("7z", "7-zip")
                    if sevenzip:
                        if not config.getcfg("dry_run"):
                            # Extract from NSIS installer
                            temp = worker.create_tempdir()
                            if isinstance(temp, Exception):
                                result = temp
                            else:
                                result = worker.exec_cmd(
                                    sevenzip,
                                    ["e", "-y", path, "DeviceCorrections.txt"],
                                    capture_output=True,
                                    skip_scripts=True,
                                    working_dir=temp,
                                )
                                if result and not isinstance(result, Exception):
                                    path = os.path.join(temp, "DeviceCorrections.txt")
                                else:
                                    worker.wrapup(False)
                    else:
                        result = Error(lang.getstr("file.missing", "7z" + EXE_EXT))
                elif i1d3ccss and (
                    "colormunki" in os.path.basename(path).lower()
                    or "i1profiler" in os.path.basename(path).lower()
                    or os.path.basename(path).lower() == "i1d3"
                ):
                    # Assume X-Rite installer
                    kind = "xrite"
                elif spyd4en and (
                    "spyder4" in os.path.basename(path).lower()
                    or os.path.basename(path).lower() == "spyd4"
                ):
                    # Assume Spyder4/5
                    kind = "spyder4"
    if kind:
        if kind == "icd":
            if (
                not config.getcfg("dry_run")
                and result
                and not isinstance(result, Exception)
            ):
                # Assume iColorDisplay DeviceCorrections.txt
                ccmx_dir = config.get_argyll_data_dir()
                if not os.path.exists(ccmx_dir):
                    from DisplayCAL.worker import check_create_dir

                    result = check_create_dir(ccmx_dir)
                    if isinstance(result, Exception):
                        return result, i1d3, spyd4, icd
                print(lang.getstr("colorimeter_correction.import"))
                print(path)
                try:
                    imported, skipped = ccmx.convert_devicecorrections_to_ccmx(
                        path, ccmx_dir
                    )
                    if imported == 0:
                        raise Info
                except ccmx.DeviceCorrectionsError as exception:
                    result = Error(lang.getstr("file.invalid") + "\n" + str(exception))
                except Info:
                    result = False
                except Exception as exception:  # noqa: BLE001
                    result = exception
                else:
                    result = icd = True
                    if skipped > 0:
                        result = Warn(
                            lang.getstr(
                                "colorimeter_correction.import.partial_warning",
                                ("iColor Display", skipped, imported + skipped),
                            )
                        )
                worker.wrapup(False)
        elif kind == "xrite":
            # Import .edr
            if asroot and sys.platform == "win32":
                ccss = get_argyll_data_files(worker, "l", "*.ccss", True)
            args = path if isinstance(path, list) else [path]
            result = i1d3 = worker.import_edr(args, asroot=asroot)
            if asroot and sys.platform == "win32":
                # Hacky but the only way to know if we were successful
                result = i1d3 = (
                    get_argyll_data_files(worker, "l", "*.ccss", True) != ccss
                )
        elif kind == "spyder4":
            # Import spyd4cal.bin
            result = spyd4 = worker.import_spyd4cal([path], asroot=asroot)
            if asroot and sys.platform == "win32":
                result = spyd4 = get_argyll_data_files(worker, "l", "spyd4cal.bin")
        elif oeminst and not icolordisplay:
            if asroot and sys.platform == "win32":
                ccss = get_argyll_data_files(worker, "l", "*.ccss", True)
            result = worker.import_colorimeter_corrections(oeminst, [path], asroot)
            if ".ccss" in "".join(worker.output) or (
                asroot
                and sys.platform == "win32"
                and get_argyll_data_files(worker, "l", "*.ccss", True) != ccss
            ):
                i1d3 = result
            if "spyd4cal.bin" in "".join(worker.output) or (
                asroot
                and sys.platform == "win32"
                and get_argyll_data_files(worker, "l", "spyd4cal.bin")
            ):
                spyd4 = result
        else:
            result = Error(lang.getstr("error.file_type_unsupported") + "\n" + path)
    return result, i1d3, spyd4, icd


# -- Measurement modes ---------------------------------------------------


def get_instrument_type(worker: Worker) -> str:
    """Return the instrument type, "color" (colorimeter) or "spect" (spectrometer).

    Toolkit-neutral port of ``MainFrame.get_instrument_type`` (``self`` ->
    ``worker``, the only instance state it reads).
    """
    spect = worker.get_instrument_features().get("spectral", False)
    return "spect" if spect else "color"


def get_cgats_measurement_mode(cgats: CGATS, instrument: str) -> str | None:
    """Get the measurement mode implied by a CCMX/CCSS's CGATS metadata.

    Toolkit-neutral port of ``display_cal.get_cgats_measurement_mode`` (moved
    here since it never depended on wx; ``display_cal`` now delegates to this).

    Args:
        cgats: The parsed CGATS data.
        instrument (str): The instrument name.

    Returns:
        str | None: The measurement mode, or None if it can't be determined.
    """
    base_id = cgats.queryv1("DISPLAY_TYPE_BASE_ID")
    refresh = cgats.queryv1("DISPLAY_TYPE_REFRESH")
    mode = None
    if base_id:
        # IMPORTANT: Make changes aswell in the following locations:
        # - DisplayCAL.MainFrame.create_colorimeter_correction_handler
        # - DisplayCAL.MainFrame.get_ccxx_measurement_modes
        # - DisplayCAL.MainFrame.set_ccxx_measurement_mode
        # - worker.Worker.check_add_display_type_base_id
        # - worker.Worker.instrument_can_use_ccxx
        if instrument in ("ColorHug", "ColorHug2"):
            mode = {1: "F", 2: "R"}.get(base_id)
        elif instrument == "ColorMunki Smile":
            mode = {1: "f"}.get(base_id)
        elif instrument == "Colorimtre HCFR":
            mode = {1: "R"}.get(base_id)
        elif instrument == "K-10":
            mode = {1: "F"}.get(base_id)
        else:
            mode = {1: "l", 2: "c", 3: "g"}.get(base_id)
    elif refresh == b"NO":
        mode = "l"
    elif refresh == b"YES":
        mode = "c"
    return mode


def get_ccxx_measurement_modes(instrument_name: str, swap: bool = False) -> dict:
    """Return the measurement modes suitable for colorimeter-correction creation.

    Toolkit-neutral port of ``MainFrame.get_ccxx_measurement_modes``: a pure
    per-instrument-name lookup (unlike :func:`compute_measurement_modes`, it
    needs no live ``worker``/``argyll_version`` state, and never adds the
    adaptive/high-res/projector variants that helper does), used for the
    colorimeter side of a CCMX/CCSS creation dialog.

    Args:
        instrument_name: The instrument's display name.
        swap: If True, swap the keys and values of the returned dict.
    """
    # IMPORTANT: Make changes aswell in the following locations:
    # - DisplayCAL.MainFrame.create_colorimeter_correction_handler
    # - DisplayCAL.MainFrame.set_ccxx_measurement_mode
    # - DisplayCAL.MainFrame.update_colorimeter_correction_matrix_ctrl_items
    # - worker.Worker.check_add_display_type_base_id
    # - worker.Worker.instrument_can_use_ccxx
    modes = {
        "ColorHug": {
            "F": lang.getstr("measurement_mode.factory"),
            "R": lang.getstr("measurement_mode.raw"),
        },
        "ColorHug2": {
            "F": lang.getstr("measurement_mode.factory"),
            "R": lang.getstr("measurement_mode.raw"),
        },
        "ColorMunki Smile": {"f": lang.getstr("measurement_mode.lcd.ccfl")},
        "Colorimtre HCFR": {"R": lang.getstr("measurement_mode.raw")},
        "K-10": {"F": lang.getstr("measurement_mode.factory")},
        "SpyderX": {
            "l": lang.getstr("measurement_mode.lcd"),
            "e": lang.getstr("measurement_mode.lcd.white_led"),
            "b": lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            "i": lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
        },
        "SpyderX2": {
            "l": lang.getstr("measurement_mode.lcd"),
            "e": lang.getstr("measurement_mode.lcd.white_led"),
            "b": lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            "i": lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
            "h": lang.getstr("measurement_mode.lcd.high_brightness", "High brightness"),
        },
        "Spyder 2024": {
            "l": lang.getstr("measurement_mode.lcd"),
            "e": lang.getstr("measurement_mode.lcd.white_led"),
            "b": lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            "i": lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
            "h": lang.getstr("measurement_mode.lcd.high_brightness", "High brightness"),
            "o": lang.getstr("measurement_mode.lcd.oled", "OLED"),
            "m": lang.getstr("measurement_mode.lcd.mini_led", "Mini-LED"),
        },
    }.get(
        instrument_name,
        {
            "c": lang.getstr("measurement_mode.refresh"),
            "l": lang.getstr("measurement_mode.lcd"),
        },
    )
    if swap:
        modes = swap_dict_keys_values(modes)
    return modes


@dataclass
class MeasurementModes:
    """Result of :func:`compute_measurement_modes`."""

    #: The (possibly-corrected) measurement mode abbreviation to store.
    measurement_mode: str
    #: instrument type -> localized mode names, in combo order.
    measurement_modes: dict[str, list[str]]
    #: instrument type -> {combo index: mode abbreviation}.
    measurement_modes_ab: dict[str, dict[int, str]]
    #: instrument type -> {mode abbreviation: combo index}.
    measurement_modes_ba: dict[str, dict[str, int]]


def compute_measurement_modes(
    worker: Worker,
    instrument_name: str,
    instrument_type: str,
    cfgname: str = "measurement_mode",
) -> MeasurementModes:
    """Compute the measurement modes available for the given instrument.

    Toolkit-neutral port of ``MainFrame.get_measurement_modes`` (``self`` ->
    ``worker``; no other instance state was read).

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker`.
        instrument_name (str): Name of the instrument.
        instrument_type (str): Type of the instrument (e.g., "spect",
            "color"), as returned by :func:`get_instrument_type`.
        cfgname (str, optional): Configuration name for the measurement mode.

    Returns:
        MeasurementModes: The current mode plus the combo's items/index maps.
    """
    measurement_mode = config.getcfg(cfgname)
    if instrument_name != "DTP92":
        measurement_modes = {
            instrument_type: [
                lang.getstr("measurement_mode.refresh"),
                lang.getstr("measurement_mode.lcd"),
            ]
        }
        measurement_modes_ab = {instrument_type: ["c", "l"]}
    else:
        measurement_modes = {instrument_type: [lang.getstr("measurement_mode.refresh")]}
        measurement_modes_ab = {instrument_type: ["c"]}
    instrument_features = worker.get_instrument_features(instrument_name)
    if instrument_name in ("Spyder4", "Spyder5") and worker.spyder4_cal_exists():
        # Spyder4 Argyll CMS >= 1.3.6
        # Spyder5 Argyll CMS >= 1.7.0
        # See http://www.argyllcms.com/doc/instruments.html#spyd4
        # for description of supported modes
        measurement_modes[instrument_type].extend(
            [
                lang.getstr("measurement_mode.lcd.ccfl"),
                lang.getstr("measurement_mode.lcd.wide_gamut.ccfl"),
                lang.getstr("measurement_mode.lcd.white_led"),
                lang.getstr("measurement_mode.lcd.wide_gamut.rgb_led"),
                lang.getstr("measurement_mode.lcd.ccfl.2"),
            ]
        )
        if worker.argyll_version >= [1, 5, 0]:
            measurement_modes_ab[instrument_type].extend(["f", "L", "e", "B", "x"])
        else:
            measurement_modes_ab[instrument_type].extend(["3", "4", "5", "6", "7"])
    elif instrument_name == "SpyderX":
        # Argyll SpyderX modes:
        # l General [Default,CB1] (LCD/CCFL)
        # e Standard LED (LCD/white LED)
        # b Wide Gamut LED (LCD/RGB LED)
        # i GB LED (LCD/GB-R Phosphor LED)
        measurement_modes[instrument_type] = [
            lang.getstr("measurement_mode.generic"),
            lang.getstr("measurement_mode.lcd.white_led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
        ]
        measurement_modes_ab[instrument_type] = ["l", "e", "b", "i"]
    elif instrument_name == "SpyderX2":
        # Argyll SpyderX2 modes: SpyderX plus high brightness
        measurement_modes[instrument_type] = [
            lang.getstr("measurement_mode.generic"),
            lang.getstr("measurement_mode.lcd.white_led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
            lang.getstr("measurement_mode.lcd.high_brightness", "High brightness"),
        ]
        measurement_modes_ab[instrument_type] = ["l", "e", "b", "i", "h"]
    elif instrument_name == "Spyder 2024":
        # Argyll Spyder/SpyderPro 2024 modes: SpyderX2 plus OLED and Mini-LED
        measurement_modes[instrument_type] = [
            lang.getstr("measurement_mode.generic"),
            lang.getstr("measurement_mode.lcd.white_led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.led"),
            lang.getstr("measurement_mode.lcd.wide_gamut.gb_led"),
            lang.getstr("measurement_mode.lcd.high_brightness", "High brightness"),
            lang.getstr("measurement_mode.lcd.oled", "OLED"),
            lang.getstr("measurement_mode.lcd.mini_led", "Mini-LED"),
        ]
        measurement_modes_ab[instrument_type] = ["l", "e", "b", "i", "h", "o", "m"]
    elif instrument_name in ("ColorHug", "ColorHug2"):
        # Argyll CMS 1.3.6, spectro/colorhug.c, colorhug_disptypesel
        # Note: projector mode (-yp) is not the same as ColorMunki
        # projector mode! (-p)
        # ColorHug2 needs Argyll CMS 1.7
        measurement_modes[instrument_type].extend(
            [
                lang.getstr("projector"),
                lang.getstr("measurement_mode.lcd.white_led"),
                lang.getstr("measurement_mode.factory"),
                lang.getstr("measurement_mode.raw"),
                lang.getstr("auto"),
            ]
        )
        measurement_modes_ab[instrument_type].extend(["p", "e", "F", "R", "auto"])
    elif instrument_name == "DTP94" and worker.argyll_version >= [1, 5, 0]:
        # Argyll CMS 1.5.x introduces new measurement mode
        measurement_modes[instrument_type].extend(
            [lang.getstr("measurement_mode.generic")]
        )
        measurement_modes_ab[instrument_type].append("g")
    elif instrument_name == "ColorMunki Smile":
        # Only supported in Argyll CMS 1.5.x and newer
        measurement_modes[instrument_type] = [
            lang.getstr("measurement_mode.lcd.ccfl"),
            lang.getstr("measurement_mode.lcd.white_led"),
        ]
        measurement_modes_ab[instrument_type] = ["f", "e"]
    elif instrument_name == "Colorimtre HCFR" and worker.argyll_version >= [
        1,
        5,
        0,
    ]:
        # Argyll CMS 1.5.x introduces new measurement mode
        measurement_modes[instrument_type].extend([lang.getstr("measurement_mode.raw")])
        measurement_modes_ab[instrument_type].append("R")
    elif instrument_name == "K-10" or not instrument_features:
        # K-10 and 'unknown' instruments
        measurement_modes[instrument_type] = []
        measurement_modes_ab[instrument_type] = []
        for mode, desc in worker.get_instrument_measurement_modes().items():
            measurement_modes[instrument_type].append(lang.getstr(desc))
            measurement_modes_ab[instrument_type].append(mode)
    if (
        instrument_name == "K-10"
        and measurement_mode not in measurement_modes_ab[instrument_type]
    ):
        measurement_mode = "F"
    if instrument_features.get("projector_mode") and worker.argyll_version >= [
        1,
        1,
        0,
    ]:
        # Projector mode introduced in Argyll 1.1.0 Beta
        measurement_modes[instrument_type].append(lang.getstr("projector"))
        measurement_modes_ab[instrument_type].append("p")
    if measurement_mode not in measurement_modes_ab[instrument_type]:
        if measurement_modes_ab[instrument_type]:
            measurement_mode = measurement_modes_ab[instrument_type][0]
        else:
            measurement_mode = config.DEFAULTS["measurement_mode"]
    if instrument_features.get("adaptive_mode") and (
        worker.argyll_version[0:3] > [1, 1, 0]
        or (
            worker.argyll_version[0:3] == [1, 1, 0]
            and "Beta" not in worker.argyll_version_string
            and "RC1" not in worker.argyll_version_string
            and "RC2" not in worker.argyll_version_string
        )
    ):
        # Adaptive mode introduced in Argyll 1.1.0 RC3
        for key in iter(measurement_modes):
            instrument_modes = list(measurement_modes[key])
            for i, mode in reversed(
                list(zip(list(range(len(instrument_modes))), instrument_modes))
            ):
                if mode == lang.getstr("default"):
                    mode = lang.getstr("measurement_mode.adaptive")
                else:
                    mode = "{} {}".format(
                        mode, lang.getstr("measurement_mode.adaptive")
                    )
                measurement_modes[key].insert(i + 1, mode)
                modesig = measurement_modes_ab[key][i]
                measurement_modes_ab[key].insert(i + 1, (modesig or "") + "V")
        if config.getcfg(f"{cfgname}.adaptive"):
            measurement_mode += "V"
    if instrument_features.get("highres_mode"):
        for key in iter(measurement_modes):
            instrument_modes = list(measurement_modes[key])
            for i, mode in reversed(
                list(zip(list(range(len(instrument_modes))), instrument_modes))
            ):
                if mode == lang.getstr("default"):
                    mode = lang.getstr("measurement_mode.highres")
                else:
                    mode = "{} {}".format(mode, lang.getstr("measurement_mode.highres"))
                measurement_modes[key].insert(i + 1, mode)
                modesig = measurement_modes_ab[key][i]
                measurement_modes_ab[key].insert(i + 1, (modesig or "") + "H")
        if config.getcfg(f"{cfgname}.highres"):
            measurement_mode += "H"
    measurement_modes_ab = dict(
        list(
            zip(
                list(measurement_modes_ab.keys()),
                [
                    dict(
                        list(
                            zip(
                                list(range(len(measurement_modes_ab[key]))),
                                measurement_modes_ab[key],
                            )
                        )
                    )
                    for key in measurement_modes_ab
                ],
            )
        )
    )
    measurement_modes_ba = dict(
        list(
            zip(
                list(measurement_modes_ab.keys()),
                [
                    swap_dict_keys_values(measurement_modes_ab[key])
                    for key in measurement_modes_ab
                ],
            )
        )
    )
    return MeasurementModes(
        measurement_mode=measurement_mode,
        measurement_modes=measurement_modes,
        measurement_modes_ab=measurement_modes_ab,
        measurement_modes_ba=measurement_modes_ba,
    )


# -- Colorimeter-correction-matrix combo ---------------------------------


class ColorimeterCorrectionCatalog:
    """Persistent CCMX/CCSS disk-scan cache.

    Toolkit-neutral port of the ``MainFrame.ccmx_cached_paths`` /
    ``ccmx_cached_descriptors`` / ``ccmx_instruments`` / ``ccmx_mapping`` /
    ``ccmx_item_paths`` instance attributes, which
    ``update_colorimeter_correction_matrix_ctrl_items`` populates once and
    reuses across calls (``force=True`` re-scans). A caller keeps one
    instance alive for the lifetime of its correction-matrix combo.
    """

    def __init__(self) -> None:
        self.cached_paths: list[str] | None = None
        self.cached_descriptors: dict[str, str] = {}
        self.instruments: dict[str, str] = {}
        self.mapping: dict[str, str] = {}
        self.item_paths: list[str] = []

    def forget(self, path: str) -> None:
        """Drop a deleted CCMX/CCSS file from the cache.

        Toolkit-neutral port of
        ``MainFrame.delete_colorimeter_correction_matrix_ctrl_item``.
        """
        if self.cached_paths and path in self.cached_paths:
            self.cached_paths.remove(path)
        self.cached_descriptors.pop(path, None)
        self.instruments.pop(path, None)
        key = next((key for key, value in self.mapping.items() if value == path), None)
        if key is not None:
            del self.mapping[key]


@dataclass
class ColorimeterCorrectionSelection:
    """Result of :func:`resolve_colorimeter_correction_selection`.

    Carries everything ``update_colorimeter_correction_matrix_ctrl_items``
    used to push straight into wx widgets, as plain data instead: the caller
    (wx or Qt) applies it to its own combo/tooltip/observer control and
    decides how (or whether) to surface ``mismatch_warning``,
    ``malformed_paths`` and ``parse_errors`` to the user.
    """

    #: Combo items, in order ("None", "Auto", then the matching CCMX/CCSS).
    items: list[str]
    #: Paths for ``items[2:]``, i.e. ``item_paths[i]`` backs ``items[i + 2]``.
    item_paths: list[str]
    #: Index into ``items`` that should be selected.
    index: int
    #: The resolved ``colorimeter_correction_matrix_file`` cfg value, split
    #: on ``":"`` (already written back via ``setcfg``).
    ccmx: list[str]
    #: Whether a CCMX/CCSS correction is actually in effect.
    use_ccmx: bool
    #: Tooltip text for the combo (the resolved path, or "").
    tooltip: str
    #: Display technology implied by the resolved mode/correction, if any.
    tech: str | None
    #: Observer implied by the CCSS metadata, if any.
    observer: str | None
    #: True if ``observer`` is one DisplayCAL recognizes (already written to
    #: cfg); the caller should lock its observer control in that case, and
    #: (re-)enable it otherwise.
    observer_recognized: bool
    #: New measurement mode implied by the correction, if it changed
    #: (already written to cfg); the caller should re-sync its own control.
    measurement_mode: str | None
    #: Set (only when the caller passed ``warn_on_mismatch=True``) when the
    #: configured CCMX/CCSS doesn't match the current instrument.
    mismatch_warning: str | None
    #: CCMX/CCSS files that failed to parse as CGATS at all (candidates for
    #: deletion, as the wx handler does after warning the user; not
    #: reproduced here).
    malformed_paths: list[str] = dataclass_field(default_factory=list)
    #: ``(path, exception)`` pairs for files that failed to parse where wx
    #: would have shown ``show_ccxx_error_dialog``.
    parse_errors: list[tuple[str, Exception]] = dataclass_field(default_factory=list)


def resolve_colorimeter_correction_selection(
    catalog: ColorimeterCorrectionCatalog,
    worker: Worker,
    current_selection_index: int = -1,
    force: bool = False,
    warn_on_mismatch: bool = False,
    update_measurement_mode: bool = True,
) -> ColorimeterCorrectionSelection:
    """Resolve the CCMX/CCSS combo's items and selection.

    Toolkit-neutral port of
    ``MainFrame.update_colorimeter_correction_matrix_ctrl_items``. Scans the
    Argyll data dirs for ``.ccmx``/``.ccss`` files matching the current
    instrument, resolves "Auto" against the instrument+display mapping, and
    validates the configured selection, exactly as the wx handler does -
    except it never touches a widget or shows a dialog directly; see
    :class:`ColorimeterCorrectionSelection` for what's returned instead.

    Deliberately not reproduced (caller's responsibility, or deferred):
    trashing malformed files, the observer-control visibility toggle
    (``show_observer_ctrl``), and re-running ``measurement_mode_ctrl_handler``
    when the resolved mode changes calibration defaults (matches the wx
    handler's ``update_main_controls`` / ``update_estimated_measurement_times``
    refresh, out of scope here).

    Args:
        catalog: Persistent scan cache, reused across calls.
        worker: The running :class:`DisplayCAL.worker.Worker`.
        current_selection_index: The combo's currently-selected index before
            this call (mirrors ``self.colorimeter_correction_matrix_ctrl
            .Selection``); only used for the "keep whatever is currently
            selected" fallback. Pass -1 if there is no live selection yet.
        force: Re-scan the Argyll data dirs even if a cache already exists.
        warn_on_mismatch: If True, populate ``mismatch_warning`` when the
            configured CCMX doesn't match the current instrument (matches
            the wx handler's dialog-vs-print choice).
        update_measurement_mode: If True, a CCMX/CCSS-implied measurement
            mode always overrides the current one; if False, a mismatched
            implied mode instead discards the CCMX/CCSS selection.

    Returns:
        ColorimeterCorrectionSelection: The resolved items/selection/etc.
    """
    items = [lang.getstr("colorimeter_correction.file.none"), lang.getstr("auto")]
    catalog.item_paths = []
    index = 0
    ccxx_path = None
    ccmx_cfg = config.getcfg("colorimeter_correction_matrix_file").split(":", 1)

    if len(ccmx_cfg) > 1 and not os.path.isfile(ccmx_cfg[1]):
        ccmx_cfg = ccmx_cfg[:1]

    if force or not catalog.cached_paths:
        ccmx_paths = get_argyll_data_files(worker, "lu", "*.ccmx")
        ccss_paths = get_argyll_data_files(worker, "lu", "*.ccss")
        # Filter out files with known identical spectra. Key is the
        # preferred CCSS, value is the one to be ignored. If key is same as
        # value, remove from paths completely.
        dupe_mapping = {
            "Dell_U2413_25Jul12.ccss": "GBrLED_25Jul12.ccss",  # HCFR
            "necpa242w_full.ccss": "necpa242w_full.ccss",  # HCFR
            # necpa242w_full.ccss is bad - not done with native primaries
            "Panasonic VVX17P051J00.ccss": "PanasonicVVX17P051J00.ccss",
        }
        imapping = {}
        for path in ccss_paths:
            basename = os.path.basename(path)
            if basename in dupe_mapping:
                imapping[dupe_mapping[basename]] = path
        if imapping:
            discard_paths = []
            for path in ccss_paths:
                basename = os.path.basename(path)
                if basename in imapping:
                    if basename in dupe_mapping:
                        print("Ignoring", path)
                    else:
                        print("Ignoring", path, "in favor of", imapping[basename])
                    discard_paths.append(path)
            if discard_paths:
                ccss_paths = [p for p in ccss_paths if p not in discard_paths]
        ccmx_paths.sort(key=os.path.basename)
        ccss_paths.sort(key=os.path.basename)
        catalog.cached_paths = ccmx_paths + ccss_paths
        catalog.cached_descriptors = {}
        catalog.instruments = {}
        catalog.mapping = {}

    types = {
        "ccss": lang.getstr("spectral").replace(":", ""),
        "ccmx": lang.getstr("matrix").replace(":", ""),
    }
    add_basename_to_desc_on_mismatch = False
    malformed_ccxx: list[str] = []
    parse_errors: list[tuple[str, Exception]] = []

    for path in catalog.cached_paths:
        filename, ext = os.path.splitext(path)
        lstr = ext[1:] + "." + os.path.basename(filename)
        desc = lang.getstr(lstr)
        if catalog.cached_descriptors.get(path):
            if desc == lstr:
                desc = catalog.cached_descriptors[path]
        elif os.path.isfile(path):
            try:
                cgats = CGATS(path, strict=True)
            except (OSError, CGATSError) as exception:
                print(exception)
                if isinstance(exception, CGATSInvalidError):
                    malformed_ccxx.append(path)
                continue
            if desc == lstr:
                desc = cgats.get_descriptor()  # this is bytes
                desc = desc.decode("utf-8", "replace")
            # If the description is not the same as the 'sane' filename, add
            # the filename after the description (max 31 chars). See also
            # colorimeter_correction_check_overwrite, the way the filename
            # is processed must be the same.
            if (
                add_basename_to_desc_on_mismatch
                and make_argyll_compatible_path(desc, is_name=True)
                != os.path.splitext(os.path.basename(path))[0]
            ):
                desc = "{} <{}>".format(
                    ellipsis_(desc, 66, "m"), ellipsis_(os.path.basename(path), 31, "m")
                )
            else:
                desc = ellipsis_(desc, 100, "m")
            catalog.cached_descriptors[path] = desc
            # get_canonical_instrument_name: returns bytes
            catalog.instruments[path] = get_canonical_instrument_name(
                cgats.queryv1("INSTRUMENT") or b"",
                {
                    "DTP94-LCD mode": "DTP94",
                    "eye-one display": "i1 Display",
                    "Spyder 2 LCD": "Spyder2",
                    "Spyder 3": "Spyder3",
                },
            ).decode("utf-8")
            key = "{}\0{}".format(
                catalog.instruments[path],
                (cgats.queryv1("DISPLAY") or b"").decode("utf-8"),
            )
            if not catalog.mapping.get(key) or (
                len(ccmx_cfg) > 1 and path == ccmx_cfg[1]
            ):
                # Prefer the selected CCMX
                catalog.mapping[key] = path
        else:
            continue

        instrument_name = worker.get_instrument_name()
        if instrument_name.lower().replace(" ", "") in catalog.instruments.get(
            path, ""
        ).lower().replace(" ", "") or (
            path.lower().endswith(".ccss") and worker.instrument_supports_ccss()
        ):
            # Only add the correction to the list if it matches the
            # currently selected instrument or if it is a CCSS
            if len(ccmx_cfg) > 1 and ccmx_cfg[0] != "AUTO" and ccmx_cfg[1] == path:
                ccxx_path = path

            item_text = "{}: {}".format(
                types.get(os.path.splitext(path)[1].lower()[1:]),
                desc if isinstance(desc, str) else desc.decode("utf-8", "replace"),
            )
            items.append(item_text)
            catalog.item_paths.append(path)
    items_paths = []
    for i, item in enumerate(items[2:]):
        items_paths.append({"item": item, "path": catalog.item_paths[i]})
    items_paths.sort(key=lambda item_path: item_path["item"].lower())
    for i, item_path in enumerate(items_paths):
        items[i + 2] = item_path["item"]
        catalog.item_paths[i] = item_path["path"]
    if ccxx_path:
        index = catalog.item_paths.index(ccxx_path) + 2
    add_cfg_ccxx = False
    cgats = None
    if (
        len(ccmx_cfg) > 1
        and ccmx_cfg[1]
        and ccmx_cfg[1] not in catalog.cached_paths
        and (
            not ccmx_cfg[1].lower().endswith(".ccss")
            or worker.instrument_supports_ccss()
        )
    ):
        # Add currently configured CCXX to list? Check if same file in list
        add_cfg_ccxx = True
        for i, path in enumerate(catalog.item_paths):
            if os.path.basename(path) == os.path.basename(ccmx_cfg[1]):
                try:
                    existing_cgats = CGATS(path)
                    existing_cgats[0].DATA.vmaxlen = 5  # Allow margin of error
                except Exception as exception:  # noqa: BLE001
                    print(exception)
                    break
                try:
                    cgats = CGATS(ccmx_cfg[1], strict=True)
                    vmaxlen = cgats[0].DATA.vmaxlen
                    cgats[0].DATA.vmaxlen = 5  # Allow margin of error
                except Exception as exception:  # noqa: BLE001
                    parse_errors.append((ccmx_cfg[1], exception))
                    add_cfg_ccxx = False
                    ccmx_cfg = [""]
                else:
                    if str(cgats) == str(existing_cgats):
                        # Same, use existing entry
                        print(ccmx_cfg[1], "matches", path, "- using the latter")
                        add_cfg_ccxx = False
                        ccmx_cfg[1] = path
                        index = i + 2
                    else:
                        print(ccmx_cfg[1], "does not match", path, "- using the former")
                    cgats[0].DATA.vmaxlen = vmaxlen
                break
    if add_cfg_ccxx:
        desc = catalog.cached_descriptors.get(ccmx_cfg[1])
        if not desc and os.path.isfile(ccmx_cfg[1]):
            try:
                if not cgats:
                    cgats = CGATS(ccmx_cfg[1], strict=True)
            except (OSError, CGATSError) as exception:
                if isinstance(exception, CGATSInvalidError) and ccmx_cfg[
                    1
                ] in get_argyll_data_files(
                    worker, "lu", "*" + os.path.splitext(ccmx_cfg[1])[1]
                ):
                    malformed_ccxx.append(ccmx_cfg[1])
                parse_errors.append((ccmx_cfg[1], exception))
                ccmx_cfg = [""]
            else:
                catalog.cached_paths.insert(0, ccmx_cfg[1])
                desc = cgats.get_descriptor()
                # If the description is not the same as the 'sane' filename,
                # add the filename after the description (max 31 chars). See
                # also colorimeter_correction_check_overwite, the way the
                # filename is processed must be the same.
                if (
                    add_basename_to_desc_on_mismatch
                    and make_argyll_compatible_path(desc, is_name=True)
                    != os.path.splitext(os.path.basename(ccmx_cfg[1]))[0]
                ):
                    desc = "{} <{}>".format(
                        ellipsis_(desc, 66, "m"),
                        ellipsis_(os.path.basename(ccmx_cfg[1]), 31, "m"),
                    )
                else:
                    desc = ellipsis_(desc, 100, "m")
                catalog.cached_descriptors[ccmx_cfg[1]] = desc
                catalog.instruments[ccmx_cfg[1]] = get_canonical_instrument_name(
                    cgats.queryv1("INSTRUMENT") or b"",
                    {
                        "DTP94-LCD mode": "DTP94",
                        "eye-one display": "i1 Display",
                        "Spyder 2 LCD": "Spyder2",
                        "Spyder 3": "Spyder3",
                    },
                ).decode("utf-8")
                key = "{}\0{}".format(
                    catalog.instruments[ccmx_cfg[1]],
                    (cgats.queryv1("DISPLAY") or b"").decode("utf-8"),
                )
                catalog.mapping[key] = ccmx_cfg[1]
        if desc and (
            worker.get_instrument_name().lower().replace(" ", "")
            in catalog.instruments.get(ccmx_cfg[1], "").lower().replace(" ", "")
            or ccmx_cfg[1].lower().endswith(".ccss")
        ):
            # Only add the correction to the list if it matches the
            # currently selected instrument or if it is a CCSS
            items.insert(
                2,
                "{}: {}".format(
                    types.get(os.path.splitext(ccmx_cfg[1])[1].lower()[1:]),
                    desc if isinstance(desc, str) else desc.decode("utf-8", "replace"),
                ),
            )
            catalog.item_paths.insert(0, ccmx_cfg[1])
            if ccmx_cfg[0] != "AUTO":
                index = 2
    if ccmx_cfg[0] == "AUTO":
        if len(ccmx_cfg) < 2:
            ccmx_cfg.append("")
        # Local CCMX/CCSS files are keyed by their own generic DISPLAY field
        # ("Color LCD"), never by an Apple machine model id, so matching
        # must use the generic name too (see get_display_generic_name()'s
        # docstring / build_web_check_params, which need the same fix for
        # the same reason).
        display_name = worker.get_display_generic_name() or worker.get_display_name(
            False, True, False
        )
        if worker.instrument_supports_ccss():
            # Prefer CCSS
            ccmx_cfg[1] = catalog.mapping.get(f"\0{display_name}", "")
        if not worker.instrument_supports_ccss() or not ccmx_cfg[1]:
            instrument_name = worker.get_instrument_name()
            ccmx_cfg[1] = catalog.mapping.get(f"{instrument_name}\0{display_name}", "")
        cgats = None
    elif not ccmx_cfg[0] and len(ccmx_cfg) < 2:
        if -1 < current_selection_index - 2 < len(catalog.item_paths):
            index = current_selection_index
            ccmx_cfg.append(catalog.item_paths[current_selection_index - 2])

    mismatch_warning = None
    if (
        worker.instrument_can_use_ccxx()
        and len(ccmx_cfg) > 1
        and ccmx_cfg[1]
        and ccmx_cfg[1] not in catalog.item_paths
    ):
        # CCMX does not match the currently selected instrument, don't use
        msg = lang.getstr("colorimeter_correction.instrument_mismatch")
        if warn_on_mismatch:
            mismatch_warning = msg
        else:
            print(msg, ccmx_cfg[1])
        ccmx_cfg = [""]
    elif ccmx_cfg[0] == "AUTO":
        index = 1
        if ccmx_cfg[1]:
            ccmx_desc = catalog.cached_descriptors[ccmx_cfg[1]]
            items[1] += " ({}: {})".format(
                types.get(os.path.splitext(ccmx_cfg[1])[1].lower()[1:]),
                (
                    ccmx_desc
                    if isinstance(ccmx_desc, str)
                    else ccmx_desc.decode("utf-8", "replace")
                ),
            )
        else:
            items[1] += " ({})".format(lang.getstr("colorimeter_correction.file.none"))

    use_ccmx = bool(
        worker.instrument_can_use_ccxx(False) and len(ccmx_cfg) > 1 and ccmx_cfg[1]
    )
    tech = None
    observer = None
    measurement_mode = None
    if use_ccmx:
        mode = None
        try:
            if not cgats:
                cgats = CGATS(ccmx_cfg[1], strict=True)
        except (OSError, CGATSError) as exception:
            parse_errors.append((ccmx_cfg[1], exception))
            ccmx_cfg = ["", ""]
            index = 0
        else:
            if config.getcfg("measurement_mode") != "auto":
                tech = cgats.queryv1("TECHNOLOGY")
                # Set appropriate measurement mode
                # IMPORTANT: Make changes aswell in the following locations:
                # - DisplayCAL.get_cgats_measurement_mode
                mode = get_cgats_measurement_mode(cgats, worker.get_instrument_name())
            observer = cgats.queryv1("OBSERVER")
            if observer in config.VALID_VALUES["observer"]:
                config.setcfg("observer", observer)
        if mode or (
            config.getcfg("measurement_mode") != "auto"
            and not worker.instrument_can_use_ccxx()
        ):
            if update_measurement_mode or mode == config.getcfg("measurement_mode"):
                config.setcfg("measurement_mode", mode)
                measurement_mode = mode
            else:
                ccmx_cfg = ["", ""]
                index = 0
                tech = None
    if tech is None:
        tech = worker.get_instrument_measurement_modes().get(
            config.getcfg("measurement_mode")
        )
    config.setcfg("display.technology", tech)
    config.setcfg("colorimeter_correction_matrix_file", ":".join(ccmx_cfg))

    return ColorimeterCorrectionSelection(
        items=items,
        item_paths=list(catalog.item_paths),
        index=index,
        ccmx=ccmx_cfg,
        use_ccmx=use_ccmx,
        tooltip=ccmx_cfg[1] if use_ccmx and len(ccmx_cfg) > 1 else "",
        tech=tech,
        observer=observer,
        observer_recognized=(
            bool(observer) and observer in config.VALID_VALUES["observer"]
        ),
        measurement_mode=measurement_mode,
        mismatch_warning=mismatch_warning,
        malformed_paths=malformed_ccxx,
        parse_errors=parse_errors,
    )
