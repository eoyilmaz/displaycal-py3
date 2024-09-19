from DisplayCAL.config import standard_profiles
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home
from DisplayCAL.get_data_path import get_data_path


import os
import re


def get_standard_profiles(paths_only=False):
    if not standard_profiles:
        from DisplayCAL import ICCProfile as ICCP

        # Reference profiles (Argyll + DisplayCAL)                                      # noqa: SC100
        ref_icc = get_data_path("ref", r"\.ic[cm]$") or []
        # Other profiles installed on the system
        other_icc = []
        rex = re.compile(r"\.ic[cm]$", re.IGNORECASE)
        for icc_dir in set(iccprofiles + iccprofiles_home):
            for dirpath, _dirnames, basenames in os.walk(icc_dir):
                for basename in filter(rex.search, basenames):
                    filename, ext = os.path.splitext(basename.lower())
                    if (
                        filename.endswith("_bas")
                        or filename.endswith("_eci")
                        or filename.endswith("adobergb1998")
                        or filename.startswith("eci-rgb")
                        or filename.startswith("ecirgb")
                        or filename.startswith("ekta space")
                        or filename.startswith("ektaspace")
                        or filename.startswith("fogra")
                        or filename.startswith("gracol")
                        or filename.startswith("iso")
                        or filename.startswith("lstar-")
                        or filename.startswith("pso")
                        or filename.startswith("prophoto")
                        or filename.startswith("psr_")
                        or filename.startswith("psrgravure")
                        or filename.startswith("snap")
                        or filename.startswith("srgb")
                        or filename.startswith("swop")
                        or filename
                        in (
                            "applergb",
                            "bestrgb",
                            "betargb",
                            "brucergb",
                            "ciergb",
                            "cie-rgb",
                            "colormatchrgb",
                            "donrgb",
                            "widegamutrgb",
                        )
                    ):
                        other_icc.append(os.path.join(dirpath, basename))

        # Ensure ref_icc is a list
        if isinstance(ref_icc, str):
            ref_icc = [ref_icc]

        for path in ref_icc + other_icc:
            try:
                profile = ICCP.ICCProfile(path, load=False, use_cache=True)
            except EnvironmentError:
                pass
            except Exception as exception:
                print(exception)
            else:
                if (
                    profile.version < 4
                    and profile.profileClass != b"nmcl"
                    and profile.colorSpace != b"GRAY"
                    and profile.connectionColorSpace in (b"Lab", b"XYZ")
                ):
                    standard_profiles.append(profile)
    if paths_only:
        return [profile.fileName for profile in standard_profiles]
    return standard_profiles
