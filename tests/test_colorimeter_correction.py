"""Tests for the toolkit-neutral colorimeter-correction internals.

Covers the pure CCXX byte-injection lifted out of
``MainFrame.create_colorimeter_correction_handler``, plus the web-check /
upload / import helpers lifted out of the web-check dialog, the upload
handler and ``MainFrame.import_colorimeter_correction`` /
``import_colorimeter_corrections_producer`` (Stage 5+ import/upload/web-check
slice). No display or QApplication is needed.
"""

import os
from hashlib import md5
from unittest.mock import MagicMock

from DisplayCAL import colorimeter_correction as cc
from DisplayCAL import config

# A CCSS fixture whose DISPLAY field ("DELL UP2516D") matches a display's
# *generic* name, never a machine-specific model id - used to prove Auto
# resolution matches against the generic name, not the raw display name.
_CCSS_FIXTURE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "icc",
    "Dell, DELL UP2516D (i1 Pro 2) 08.2020.ccss",
)

# A minimal CCMX-shaped blob with the DISPLAY line the injector anchors on.
BASE = b'CCMX\n\nDESCRIPTOR "test"\nDISPLAY "LCD Monitor"\nCOLOR_REP "XYZ"\n'


class TestInjectCcxxMetadata:
    def test_no_values_is_noop(self):
        assert cc.inject_ccxx_metadata(BASE) == BASE

    def test_reference_inserted_above_display(self):
        out = cc.inject_ccxx_metadata(BASE, reference=b"i1 Pro")
        assert b'\nREFERENCE "i1 Pro"\nDISPLAY "LCD Monitor"\n' in out

    def test_str_value_is_utf8_encoded(self):
        out = cc.inject_ccxx_metadata(BASE, manufacturer="Dell")
        assert b'\nMANUFACTURER "Dell"\nDISPLAY "LCD Monitor"\n' in out

    def test_existing_keyword_not_duplicated(self):
        blob = b'CCMX\n\nREFERENCE "already"\nDISPLAY "LCD Monitor"\n'
        out = cc.inject_ccxx_metadata(blob, reference=b"i1 Pro")
        assert out == blob
        assert out.count(b"\nREFERENCE ") == 1

    def test_backslashes_escaped_as_literals(self):
        # A backslash in the value must survive re.sub as a literal backslash,
        # not be interpreted as a replacement backreference/escape.
        out = cc.inject_ccxx_metadata(BASE, manufacturer=b"a\\b")
        assert b'\nMANUFACTURER "a\\b"\nDISPLAY "LCD Monitor"\n' in out

    def test_all_fields_injected_in_fixed_order(self):
        out = cc.inject_ccxx_metadata(
            BASE,
            reference=b"ref",
            technology=b"LCD",
            manufacturer_id="ABC",
            manufacturer="Acme",
            observer=b"1931_2",
            reference_observer="1964_10",
        )
        block = (
            b'\nREFERENCE "ref"'
            b'\nTECHNOLOGY "LCD"'
            b'\nMANUFACTURER_ID "ABC"'
            b'\nMANUFACTURER "Acme"'
            b'\nOBSERVER "1931_2"'
            b'\nREFERENCE_OBSERVER "1964_10"'
            b'\nDISPLAY "LCD Monitor"\n'
        )
        assert block in out

    def test_partial_fields_only_inject_supplied(self):
        out = cc.inject_ccxx_metadata(BASE, technology=b"CRT", observer=b"1931_2")
        assert b'\nTECHNOLOGY "CRT"' in out
        assert b'\nOBSERVER "1931_2"' in out
        assert b"\nMANUFACTURER " not in out
        assert b"\nREFERENCE " not in out

    def test_falsy_values_skipped(self):
        out = cc.inject_ccxx_metadata(
            BASE, reference=b"", technology=None, manufacturer=""
        )
        assert out == BASE

    def test_missing_display_line_leaves_bytes_unchanged(self):
        blob = b'CCMX\n\nDESCRIPTOR "no display line"\n'
        out = cc.inject_ccxx_metadata(blob, reference=b"i1 Pro")
        assert out == blob


# A minimal but fully-parseable CCMX correction, matching the shape the online
# database's "cgats" JSON field contains (as text, since the web-check JSON is
# UTF-8, not raw bytes).
CCMX_TEXT = (
    "CCMX\n\n"
    'DESCRIPTOR "test"\n'
    'ORIGINATOR "Argyll dispcal"\n'
    'CREATED "Thu Apr 19 13:24:37 2012"\n'
    'DISPLAY "LCD Monitor"\n'
    'REFERENCE "i1 Pro"\n'
    'TECHNOLOGY "LCD"\n'
    'REFERENCE_OBSERVER "1931_2"\n'
    'FIT_METHOD "xy"\n'
    'FIT_AVG_DE00 "0.123"\n'
    'FIT_MAX_DE00 "0.456"\n'
    'COLOR_REP "XYZ"\n\n'
    "NUMBER_OF_FIELDS 4\n"
    "BEGIN_DATA_FORMAT\n"
    "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z\n"
    "END_DATA_FORMAT\n\n"
    "NUMBER_OF_SETS 1\n"
    "BEGIN_DATA\n"
    "1 1.0 1.0 1.0\n"
    "END_DATA\n"
)


class TestParseWebCheckEntries:
    def test_basic_ccmx_entry(self):
        entry = {
            "cgats": CCMX_TEXT,
            "type": "ccmx",
            "description": "i1 DisplayPro, ColorMunki Display",
            "display": "U2413",
            "manufacturer": "Dell",
            "reference": "i1 Pro",
            "created": "Thu Apr 19 13:24:37 2012",
        }
        rows = cc.parse_web_check_entries([entry], {"1931_2": "1931 2 Degree"})
        assert len(rows) == 1
        row = rows[0]
        assert row["cgats"] == CCMX_TEXT.encode("utf-8")
        assert row["display"] == "Dell U2413"
        assert row["observer"] == "1931 2 Degree"
        assert row["fit_method"] == "xy"
        assert row["fit_avg_de00"] == "0.123"
        assert row["fit_max_de00"] == "0.456"
        assert row["created"] == "2012-04-19 13:24:37"

    def test_ccss_entry_reports_not_applicable_fit_fields(self):
        entry = {
            "cgats": CCMX_TEXT.replace("CCMX", "CCSS", 1),
            "type": "ccss",
            "display": "Unknown",
        }
        row = cc.parse_web_check_entries([entry])[0]
        assert row["fit_method"] == "N/A" or row["fit_method"]
        # Not-applicable fields must not read the CCMX-only FIT_* keywords.
        from DisplayCAL import localization as lang

        assert row["fit_method"] == lang.getstr("not_applicable")
        assert row["fit_avg_de00"] == lang.getstr("not_applicable")
        assert row["fit_max_de00"] == lang.getstr("not_applicable")

    def test_display_not_reprefixed_when_already_prefixed(self):
        entry = {
            "cgats": CCMX_TEXT,
            "type": "ccmx",
            "display": "Dell U2413",
            "manufacturer": "Dell",
        }
        row = cc.parse_web_check_entries([entry])[0]
        assert row["display"] == "Dell U2413"

    def test_missing_cgats_key_yields_empty_bytes(self):
        entry = {"type": "ccmx"}
        row = cc.parse_web_check_entries([entry])[0]
        assert row["cgats"] == b""

    def test_missing_observer_label_falls_back_to_unknown(self):
        entry = {"cgats": CCMX_TEXT, "type": "ccmx"}
        row = cc.parse_web_check_entries([entry])[0]
        from DisplayCAL import localization as lang

        assert row["observer"] == lang.getstr("unknown")

    def test_spectral_resolution_computed_when_all_three_fields_present(self):
        entry = {
            "cgats": CCMX_TEXT,
            "type": "ccss",
            "spectral_bands": "36",
            "spectral_start_nm": "380",
            "spectral_end_nm": "730",
        }
        row = cc.parse_web_check_entries([entry])[0]
        assert "nm" in row["spectral_resolution"]
        assert "380-730" in row["spectral_resolution"]


class TestBuildWebCheckParams:
    def test_uses_worker_state(self):
        worker = MagicMock()
        worker.instrument_supports_ccss.return_value = True
        worker.get_display_edid.return_value = {"manufacturer_id": "DEL"}
        worker.get_display_generic_name.return_value = "Dell U2413"
        worker.get_display_name.return_value = "Dell U2413"
        worker.get_instrument_name.return_value = "i1 Pro"
        params = cc.build_web_check_params(worker)
        assert params == {
            "get": True,
            "type": "ccss,ccmx",
            "manufacturer_id": "DEL",
            "display": "Dell U2413",
            "instrument": "i1 Pro",
            "json": 1,
        }

    def test_falls_back_to_display_name_when_no_generic_name(self):
        worker = MagicMock()
        worker.instrument_supports_ccss.return_value = True
        worker.get_display_edid.return_value = {"manufacturer_id": "APP"}
        worker.get_display_generic_name.return_value = ""
        worker.get_display_name.return_value = "MacBookPro18,1"
        worker.get_instrument_name.return_value = "i1 DisplayPro"
        params = cc.build_web_check_params(worker)
        assert params["display"] == "MacBookPro18,1"

    def test_falls_back_to_ccmx_only_and_unknown(self):
        worker = MagicMock()
        worker.instrument_supports_ccss.return_value = False
        worker.get_display_edid.return_value = {}
        worker.get_display_generic_name.return_value = ""
        worker.get_display_name.return_value = None
        worker.get_instrument_name.return_value = None
        params = cc.build_web_check_params(worker)
        assert params["type"] == "ccmx"
        assert params["display"] == "Unknown"
        assert params["instrument"] == "Unknown"


class TestResolveColorimeterCorrectionSelectionAuto:
    """"Auto" must match local CCMX/CCSS files by generic display name.

    Regression test: local corrections are keyed by their own DISPLAY field
    (a generic monitor name, e.g. "DELL UP2516D"), never by a machine model
    id, so "Auto" resolution has to prefer ``get_display_generic_name()``
    the same way ``build_web_check_params`` does - otherwise, on a display
    where ``get_display_name()`` diverges from the generic name (e.g. an
    Apple built-in display, see ``get_display_generic_name``'s docstring),
    "Auto" can never find a matching correction even when one is present on
    disk.
    """

    def _worker(self):
        worker = MagicMock()
        worker.instrument_supports_ccss.return_value = True
        worker.instrument_can_use_ccxx.return_value = True
        worker.get_instrument_name.return_value = "i1 Pro 2"
        worker.get_instrument_measurement_modes.return_value = {"auto": None}
        # Deliberately wrong/overridden, mirroring get_display_name()'s
        # Apple model-id substitution - Auto must not use this value.
        worker.get_display_name.return_value = "MacBookPro18,1"
        worker.get_display_generic_name.return_value = "DELL UP2516D"
        return worker

    def _catalog(self):
        catalog = cc.ColorimeterCorrectionCatalog()
        catalog.cached_paths = [_CCSS_FIXTURE]
        return catalog

    def test_auto_resolves_using_generic_display_name(self):
        config.setcfg("measurement_mode", "auto")
        config.setcfg("colorimeter_correction_matrix_file", "AUTO:")
        result = cc.resolve_colorimeter_correction_selection(
            self._catalog(), self._worker()
        )
        assert result.use_ccmx
        assert result.ccmx[1] == _CCSS_FIXTURE
        assert result.items[1] != cc.lang.getstr("auto")

    def test_auto_stays_none_when_generic_name_does_not_match(self):
        config.setcfg("measurement_mode", "auto")
        config.setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = self._worker()
        worker.get_display_generic_name.return_value = "Some Other Display"
        result = cc.resolve_colorimeter_correction_selection(self._catalog(), worker)
        assert not result.use_ccmx
        assert result.ccmx[1] == ""


class TestValidateUploadOriginator:
    def test_argyll_originator_accepted(self):
        assert cc.validate_upload_originator(
            'foo\nORIGINATOR "Argyll dispcal"\nbar', "DisplayCAL"
        )

    def test_appname_originator_accepted(self):
        assert cc.validate_upload_originator(
            'foo\nORIGINATOR "DisplayCAL"\nbar', "DisplayCAL"
        )

    def test_other_originator_rejected(self):
        assert not cc.validate_upload_originator(
            'foo\nORIGINATOR "SomeOtherApp"\nbar', "DisplayCAL"
        )


class TestComputeUploadDedupHash:
    def test_strips_created_before_hashing(self):
        with_created = b'CCMX\n\nCREATED "Thu Apr 19 13:24:37 2012"\nDISPLAY "x"\n'
        without_created = b'CCMX\n\n\nDISPLAY "x"\n'
        assert (
            cc.compute_upload_dedup_hash(with_created)
            == md5(without_created.strip()).hexdigest()
        )

    def test_different_content_hashes_differently(self):
        a = b'CCMX\n\nDISPLAY "a"\n'
        b = b'CCMX\n\nDISPLAY "b"\n'
        assert cc.compute_upload_dedup_hash(a) != cc.compute_upload_dedup_hash(b)


class TestBuildUploadParams:
    def test_accepts_str_input_without_crashing(self):
        # Regression: the wx handler decodes the file to str before calling
        # in, but the byte-stripping regex requires bytes; this must not
        # raise TypeError.
        text = 'CCMX\n\nREFERENCE_FILENAME "/tmp/x.ti3"\nDISPLAY "LCD Monitor"\n'
        params = cc.build_upload_params(text)
        assert b"REFERENCE_FILENAME" not in params["cgats"]
        assert isinstance(params["cgats"], bytes)

    def test_strips_filename_fields(self):
        cgats = (
            b'CCMX\n\nREFERENCE_FILENAME "/tmp/secret/path.ti3"\n'
            b'DISPLAY "LCD Monitor"\n'
        )
        params = cc.build_upload_params(cgats)
        assert b"REFERENCE_FILENAME" not in params["cgats"]
        assert b"DISPLAY" in params["cgats"]

    def test_attaches_reference_cgats_when_hash_matches(self, tmp_path):
        from DisplayCAL.cgats import CGATS

        measurement = b'CTI3\n\nDESCRIPTOR "ref"\n'
        ref_path = tmp_path / "reference.ti3"
        ref_path.write_bytes(measurement)
        # The hash is computed over the *re-serialized* CGATS (matching the wx
        # handler byte-for-byte: ``bytes(CGATS(filename)).strip()``), which may
        # differ from the file's raw bytes (whitespace/formatting).
        reserialized = bytes(CGATS(str(ref_path))).strip()
        digest = md5(reserialized).hexdigest()  # noqa: S324
        cgats = (
            f'CCMX\n\nREFERENCE_FILENAME "{ref_path}"\n'
            f'REFERENCE_HASH "md5:{digest}"\n'
            'DISPLAY "LCD Monitor"\n'
        ).encode()
        params = cc.build_upload_params(cgats)
        assert params["reference_cgats"] == reserialized

    def test_skips_reference_cgats_when_hash_mismatches(self, tmp_path):
        measurement = b'CTI3\n\nDESCRIPTOR "ref"\n'
        ref_path = tmp_path / "reference.ti3"
        ref_path.write_bytes(measurement)
        cgats = (
            f'CCMX\n\nREFERENCE_FILENAME "{ref_path}"\n'
            'REFERENCE_HASH "md5:deadbeef"\n'
            'DISPLAY "LCD Monitor"\n'
        ).encode()
        params = cc.build_upload_params(cgats)
        assert "reference_cgats" not in params

    def test_no_provenance_fields_is_just_cgats(self):
        cgats = b'CCMX\n\nDISPLAY "LCD Monitor"\n'
        params = cc.build_upload_params(cgats)
        assert params == {"cgats": cgats}


class TestGetArgyllDataFiles:
    def test_returns_list_without_worker_state_for_empty_scope(self, monkeypatch):
        worker = MagicMock()
        worker.argyll_version = [1, 2]
        result = cc.get_argyll_data_files(worker, "", "*.ccmx")
        assert result == []

    def test_include_lastmod_pairs_path_with_mtime(self, tmp_path, monkeypatch):
        from DisplayCAL import config as cfg

        # Put the file under both branches' "u"-scope lookup dirs so the test
        # doesn't depend on which platform it runs under.
        color_dir = tmp_path / "color"
        color_dir.mkdir()
        ccmx_file = color_dir / "test.ccmx"
        ccmx_file.write_text("CCMX\n")
        monkeypatch.setattr(cfg, "APPDATA", str(tmp_path))
        # LIBRARY_HOME is only ever imported into `config` on macOS (see
        # config.py's platform-gated defaultpaths import), so it doesn't
        # exist as an attribute to override on other platforms unless we
        # tell monkeypatch not to require that.
        monkeypatch.setattr(cfg, "LIBRARY_HOME", str(tmp_path), raising=False)
        worker = MagicMock()
        worker.argyll_version = [1, 2]
        result = cc.get_argyll_data_files(worker, "u", "*.ccmx", include_lastmod=True)
        assert len(result) == 1
        path, lastmod = result[0]
        assert path == str(ccmx_file)
        assert isinstance(lastmod, float)


class TestDiscoverAutoImportPaths:
    def test_no_importers_selected_returns_empty(self):
        assert cc.discover_auto_import_paths({}, False, False, False, False, None) == {}

    def test_i1d3_skipped_when_no_utility_available(self):
        # Neither oeminst nor i1d3ccss present -> the i1D3 lookup is skipped
        # even if requested, matching the wx gating.
        result = cc.discover_auto_import_paths(
            {"i1d3": True}, False, False, False, False, None
        )
        assert "i1d3" not in result

    def test_i1d3_skipped_when_already_imported(self):
        result = cc.discover_auto_import_paths(
            {"i1d3": True}, True, True, False, False, "oeminst"
        )
        assert "i1d3" not in result


class TestDetectImportKind:
    def test_missing_path_leaves_result_unchanged(self):
        # A nonexistent path never resolves to a "kind", so the function is a
        # no-op and hands the caller's ``result`` back untouched.
        worker = MagicMock()
        result, i1d3, spyd4, icd = cc.detect_import_kind(
            worker,
            None,
            False,
            False,
            False,
            False,
            False,
            None,
            "/no/such/file",
            False,
        )
        assert result is None
        assert (i1d3, spyd4, icd) == (False, False, False)

    def test_unrecognized_extension_returns_error(self, tmp_path):
        path = tmp_path / "correction.xyz"
        path.write_text("dummy")
        worker = MagicMock()
        result, _i1d3, _spyd4, _icd = cc.detect_import_kind(
            worker, None, False, False, False, False, False, None, str(path), False
        )
        from DisplayCAL.debughelpers import Error

        assert isinstance(result, Error)

    def test_txt_path_is_treated_as_icolordisplay_export(self, tmp_path):
        path = tmp_path / "DeviceCorrections.txt"
        path.write_text("dummy")
        worker = MagicMock()
        worker.wrapup.return_value = None
        from DisplayCAL import ccmx as ccmx_module

        original = ccmx_module.convert_devicecorrections_to_ccmx
        ccmx_module.convert_devicecorrections_to_ccmx = lambda p, d: (1, 0)
        try:
            result, i1d3, spyd4, icd = cc.detect_import_kind(
                worker, None, False, False, False, False, False, None, str(path), False
            )
        finally:
            ccmx_module.convert_devicecorrections_to_ccmx = original
        assert icd is True
        assert result is True

    def test_txt_path_converts_real_devicecorrections_file(self, tmp_path, monkeypatch):
        path = tmp_path / "DeviceCorrections.txt"
        path.write_text(
            '"i1 Display 2 / Monitor Y" =\n'
            "{\n"
            '  Name = "i1 Display 2 / Monitor Y"\n'
            '  Device = "i1 Display 2"\n'
            '  Display = "Monitor Y"\n'
            '  ReferenceDevice = "eye-one Pro Rev.D"\n'
            '  MatrixXYZ = "3 3 1 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0"\n'
            "}\n",
            encoding="utf-8",
        )
        ccmx_dir = tmp_path / "argyll"
        ccmx_dir.mkdir()
        monkeypatch.setattr(config, "get_argyll_data_dir", lambda: str(ccmx_dir))
        worker = MagicMock()
        result, _i1d3, _spyd4, icd = cc.detect_import_kind(
            worker, None, False, False, False, False, False, None, str(path), False
        )
        assert (result, icd) == (True, True)
        assert os.listdir(ccmx_dir) == ["i1 Display 2 _ Monitor Y.ccmx"]

    def test_txt_parse_error_is_reported_as_file_invalid(self, tmp_path, monkeypatch):
        from DisplayCAL import ccmx as ccmx_module
        from DisplayCAL import localization as lang
        from DisplayCAL.debughelpers import Error

        path = tmp_path / "DeviceCorrections.txt"
        path.write_text("not a DeviceCorrections file\n", encoding="utf-8")
        monkeypatch.setattr(config, "get_argyll_data_dir", lambda: str(tmp_path))
        result, _i1d3, _spyd4, icd = cc.detect_import_kind(
            MagicMock(), None, False, False, False, False, False, None, str(path), False
        )
        assert isinstance(result, Error)
        assert str(result).startswith(lang.getstr("file.invalid"))
        assert icd is False
        assert issubclass(ccmx_module.DeviceCorrectionsError, Exception)

    def test_txt_internal_value_error_is_not_reported_as_file_invalid(
        self, tmp_path, monkeypatch
    ):
        from DisplayCAL import ccmx as ccmx_module
        from DisplayCAL.debughelpers import Error

        path = tmp_path / "DeviceCorrections.txt"
        path.write_text("dummy", encoding="utf-8")
        monkeypatch.setattr(config, "get_argyll_data_dir", lambda: str(tmp_path))
        bug = ValueError("invalid mode: 'utf8'")

        def raise_bug(_path, _target_dir):
            raise bug

        monkeypatch.setattr(
            ccmx_module, "convert_devicecorrections_to_ccmx", raise_bug
        )
        result, _i1d3, _spyd4, _icd = cc.detect_import_kind(
            MagicMock(), None, False, False, False, False, False, None, str(path), False
        )
        assert result is bug
        assert not isinstance(result, Error)
