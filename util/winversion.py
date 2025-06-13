import os
import sys
import tempfile

sys.path.insert(
    1,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DisplayCAL"
    ),
)


from DisplayCAL.meta import AUTHOR, DESCRIPTION, DOMAIN, NAME, VERSION_STRING, VERSION_TUPLE


def mktempver(
    version_template_path, name_=NAME, description_=DESCRIPTION, encoding="UTF-8"
):
    version_template = open(version_template_path, "rb")
    tempver_str = version_template.read().decode(encoding, "replace") % {
        "filevers": str(VERSION_TUPLE),
        "prodvers": str(VERSION_TUPLE),
        "CompanyName": DOMAIN,
        "FileDescription": description_,
        "FileVersion": f"{VERSION_STRING}",
        "InternalName": name_,
        "LegalCopyright": f"© {AUTHOR}",
        "OriginalFilename": f"{name_}.exe",
        "ProductName": name_,
        "ProductVersion": f"{VERSION_STRING}",
    }
    version_template.close()
    tempdir = tempfile.mkdtemp()
    tempver_path = os.path.join(tempdir, "winversion.txt")
    if not os.path.exists(tempdir):
        os.makedirs(tempdir)
    tempver = open(tempver_path, "wb")
    tempver.write(tempver_str.encode(encoding, "replace"))
    tempver.close()
    return tempver_path
