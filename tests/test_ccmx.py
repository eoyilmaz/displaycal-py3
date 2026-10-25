"""Tests for the iColorDisplay DeviceCorrections.txt to CCMX converter."""

import os

import pytest

from DisplayCAL import ccmx
from DisplayCAL.cgats import CGATS

IDENTITY = "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0 "
SAMPLE_MATRIX = (
    "3 3 1482250784 0.9612 0.0213 -0.0154 0.0105 0.9921 0.0031 -0.0042 0.0117 1.0563 "
)


def make_entry(name, device="i1 Display 2", display="Monitor Y", matrix=IDENTITY):
    """Return one DeviceCorrections.txt entry block."""
    return (
        f'"{name}" =\n'
        "{\n"
        f'  Name = "{name}"\n'
        f'  Device = "{device}"\n'
        f'  Display = "{display}"\n'
        '  ReferenceDevice = "eye-one Pro Rev.D"\n'
        f'  MatrixXYZ = "{matrix}"\n'
        "}\n"
    )


def write_devicecorrections(tmp_path, text, encoding="utf-8"):
    """Write DeviceCorrections.txt into a source dir, return (path, target)."""
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    path = source / "DeviceCorrections.txt"
    path.write_bytes(text.encode(encoding))
    return str(path), target


def ccmx_files(target):
    """Return the sorted CCMX filenames in target."""
    return sorted(os.listdir(target))


class TestConvertDeviceCorrectionsToCcmx:
    def test_converts_sample_file(self, tmp_path):
        text = make_entry(
            "i1 Display 2 for Dell U2410",
            display="Dell U2410",
            matrix=SAMPLE_MATRIX,
        ) + make_entry("i1 Display 2 for Eizo CG", display="Eizo CG")
        path, target = write_devicecorrections(tmp_path, text)

        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (2, 0)
        assert ccmx_files(target) == [
            "i1 Display 2 for Dell U2410.ccmx",
            "i1 Display 2 for Eizo CG.ccmx",
        ]
        cgats = CGATS(str(target / "i1 Display 2 for Dell U2410.ccmx"))
        assert cgats[0].type == b"CCMX"
        data = cgats[0]
        assert data.DESCRIPTOR == b"i1 Display 2 & Dell U2410"
        assert data.INSTRUMENT == b"i1 Display 2"
        assert data.DISPLAY == b"Dell U2410"
        assert data.REFERENCE == b"eye-one Pro Rev.D"
        assert data.ORIGINATOR == b"Quato iColorDisplay"
        rows = [
            [data.DATA[i]["XYZ_X"], data.DATA[i]["XYZ_Y"], data.DATA[i]["XYZ_Z"]]
            for i in range(3)
        ]
        assert rows == [
            [0.9612, 0.0213, -0.0154],
            [0.0105, 0.9921, 0.0031],
            [-0.0042, 0.0117, 1.0563],
        ]

    def test_crlf_line_endings(self, tmp_path):
        text = make_entry("A").replace("\n", "\r\n")
        path, target = write_devicecorrections(tmp_path, text)
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["A.ccmx"]

    def test_empty_file_imports_nothing(self, tmp_path):
        path, target = write_devicecorrections(tmp_path, "\n\n")
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (0, 0)
        assert ccmx_files(target) == []

    def test_name_and_brace_on_same_line(self, tmp_path):
        text = make_entry("A").replace('"A" =\n{\n', '"A" = {\n')
        path, target = write_devicecorrections(tmp_path, text)
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["A.ccmx"]

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("i1 Display Pro / Dell U2410", "i1 Display Pro _ Dell U2410.ccmx"),
            ("../../evil", "_.._evil.ccmx"),
            ("..", "iColorDisplay.ccmx"),
            ('A:B?C*D"E<F>G|H\\I', "A_B_C_D_E_F_G_H_I.ccmx"),
            ("Trailing dot. ", "Trailing dot.ccmx"),
            ("CON", "_CON.ccmx"),
            ("tab\there", "tab_here.ccmx"),
        ],
    )
    def test_entry_names_are_sanitized(self, tmp_path, name, expected):
        path, target = write_devicecorrections(tmp_path, make_entry(name))
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == [expected]
        # Nothing was written outside the target directory
        assert sorted(os.listdir(tmp_path)) == ["source", "target"]

    def test_utf8_bom(self, tmp_path):
        path, target = write_devicecorrections(
            tmp_path, make_entry("Bom", display="Écran"), encoding="utf-8-sig"
        )
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["Bom.ccmx"]
        assert CGATS(str(target / "Bom.ccmx"))[0].DISPLAY == "Écran".encode()

    def test_legacy_codepage(self, tmp_path):
        path, target = write_devicecorrections(
            tmp_path, make_entry("Écran", display="Écran"), encoding="cp1252"
        )
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["Écran.ccmx"]
        assert CGATS(str(target / "Écran.ccmx"))[0].DISPLAY == "Écran".encode()

    def test_values_with_equals_quotes_and_backslashes(self, tmp_path):
        display = 'Dell 24" U2410 A=B C:\\D'
        path, target = write_devicecorrections(
            tmp_path, make_entry("A=B", display=display)
        )
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["A=B.ccmx"]
        data = CGATS(str(target / "A=B.ccmx"))[0]
        assert data.DISPLAY == display.encode()
        assert data.DESCRIPTOR == f"i1 Display 2 & {display}".encode()

    @pytest.mark.parametrize(
        "matrix",
        [
            "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0",
            "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0 2.0",
            "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 x",
            "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 nan",
            "",
        ],
    )
    def test_invalid_matrix_is_skipped(self, tmp_path, matrix):
        text = make_entry("Bad", matrix=matrix) + make_entry("Good")
        path, target = write_devicecorrections(tmp_path, text)
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 1)
        assert ccmx_files(target) == ["Good.ccmx"]

    def test_missing_field_is_skipped(self, tmp_path):
        text = make_entry("Bad").replace('  Display = "Monitor Y"\n', "")
        path, target = write_devicecorrections(tmp_path, text + make_entry("Good"))
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 1)
        assert ccmx_files(target) == ["Good.ccmx"]

    def test_duplicate_entry_names_are_all_written(self, tmp_path):
        text = make_entry("Same", display="One") + make_entry("Same", display="Two")
        path, target = write_devicecorrections(tmp_path, text)
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (2, 0)
        assert ccmx_files(target) == ["Same (2).ccmx", "Same.ccmx"]
        assert CGATS(str(target / "Same.ccmx"))[0].DISPLAY == b"One"
        assert CGATS(str(target / "Same (2).ccmx"))[0].DISPLAY == b"Two"

    def test_reimport_does_not_duplicate(self, tmp_path):
        path, target = write_devicecorrections(tmp_path, make_entry("A"))
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["A.ccmx"]

    def test_existing_different_file_is_not_overwritten(self, tmp_path):
        path, target = write_devicecorrections(tmp_path, make_entry("A"))
        (target / "A.ccmx").write_text("user edited", encoding="utf-8")
        assert ccmx.convert_devicecorrections_to_ccmx(path, str(target)) == (1, 0)
        assert ccmx_files(target) == ["A (2).ccmx", "A.ccmx"]
        assert (target / "A.ccmx").read_text(encoding="utf-8") == "user edited"

    @pytest.mark.parametrize(
        "text",
        [
            "this is not a DeviceCorrections file\n",
            '"A" =\n{\n  Name = "A"\n',
            '{\n  Name = "A"\n}\n',
            '"A" =\n{\n  no separator here\n}\n',
            "}\n",
        ],
    )
    def test_malformed_file_raises_parse_error(self, tmp_path, text):
        path, target = write_devicecorrections(tmp_path, text)
        with pytest.raises(ccmx.DeviceCorrectionsError):
            ccmx.convert_devicecorrections_to_ccmx(path, str(target))
        assert ccmx_files(target) == []
