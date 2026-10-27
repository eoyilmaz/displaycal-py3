import glob
import shutil
import sys
import time
from pathlib import Path

from _native_build import appdata as appdata_mod
from _native_build import inno as inno_mod
from _native_build import meta, version
from _native_build.templates import replace_placeholders

pydir = Path(__file__).resolve().parent.parent


def setup():
    bdist_cmd = None

    if sys.platform == "darwin":
        bdist_cmd = "py2app"
    elif sys.platform == "win32":
        bdist_cmd = "py2exe"

    if "bdist_standalone" in sys.argv[1:]:
        i = sys.argv.index("bdist_standalone")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

        if bdist_cmd and bdist_cmd not in sys.argv[1:i]:
            sys.argv.insert(i, bdist_cmd)
    elif "py2app" in sys.argv[1:]:
        bdist_cmd = "py2app"
    elif "py2exe" in sys.argv[1:]:
        bdist_cmd = "py2exe"

    appdata = "appdata" in sys.argv[1:]
    arch = None
    setup_cfg = None
    dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
    help = False
    inno = "inno" in sys.argv[1:]
    purge = "purge" in sys.argv[1:]
    purge_dist = "purge_dist" in sys.argv[1:]
    use_setuptools = "--use-setuptools" in sys.argv[1:]
    stability = "testing"

    argv = list(sys.argv[1:])

    for i, arg in enumerate(reversed(argv)):
        n = len(sys.argv) - i - 1
        arg = arg.split("=")

        if len(arg) == 2:
            if arg[0] == "--force-arch":
                arch = arg[1]
            elif arg[0] in ("--cfg", "--stability"):
                if arg[0] == "--cfg":
                    setup_cfg = arg[1]
                else:
                    stability = arg[1]

                sys.argv = sys.argv[:n] + sys.argv[n + 1 :]
        elif arg[0] == "-h" or arg[0].startswith("--help"):
            help = True

    lastmod_time = 0
    non_build_args = list(
        filter(
            lambda x: x in sys.argv[1:],
            [
                "clean",
                "purge",
                "purge_dist",
                "uninstall",
                "-h",
                "--help",
                "--help-commands",
                "--all",
                "--name",
                "--fullname",
                "--author",
                "--author-email",
                "--maintainer",
                "--maintainer-email",
                "--contact",
                "--contact-email",
                "--url",
                "--license",
                "--licence",
                "--description",
                "--long-description",
                "--platforms",
                "--classifiers",
                "--keywords",
                "--provides",
                "--requires",
                "--obsoletes",
                "--quiet",
                "-q",
                "register",
                "--list-classifiers",
                "upload",
                "--use-distutils",
                "--use-setuptools",
                "--verbose",
                "-v",
            ],
        )
    )

    version.generate_version_file(pydir)

    if not sys.argv[1:]:
        return

    meta.load()

    if not lastmod_time:
        lastmod_time = int(time.time())

    if purge or purge_dist:
        # remove the "build" and "DisplayCAL.egg-info" directories and their
        # contents recursively

        if dry_run:
            print("dry run - nothing will be removed")

        paths = []

        if purge:
            paths += glob.glob(str(Path(pydir, "build"))) + glob.glob(
                str(Path(pydir, meta.NAME + ".egg-info"))
            )
            sys.argv.remove("purge")

        if purge_dist:
            paths += glob.glob(str(Path(pydir, "dist")))
            sys.argv.remove("purge_dist")

        for path in paths:
            path = Path(path)

            if path.exists():
                if dry_run:
                    print(path)
                    continue

                try:
                    shutil.rmtree(path)
                except Exception as e:
                    print(e)
                else:
                    print(f"Removed: {path}")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if "readme" in sys.argv[1:]:
        if not dry_run:
            for tmpl_name in ("README", "README-fr"):
                replace_placeholders(
                    Path(pydir, "misc", f"{tmpl_name}.template.html"),
                    Path(pydir, f"{tmpl_name}.html"),
                    lastmod_time,
                    {"STABILITY": "Beta" if stability != "stable" else ""},
                )
        sys.argv.remove("readme")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if "manifest" in sys.argv[1:]:
        # MANIFEST.in's contents depend on the `attrs` dict DisplayCAL/_setup.py's
        # main() assembles (data_files, packages, ...), so the regeneration
        # itself has to run there, not here.
        from DisplayCAL._setup import main

        real_argv = sys.argv
        sys.argv = [real_argv[0], "generate_manifest_in"] + (
            ["--dry-run"] if dry_run else []
        )
        try:
            main()
        finally:
            sys.argv = real_argv
        sys.argv.remove("manifest")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    create_appdata = (
        (appdata or "install" in sys.argv[1:] or "sdist" in sys.argv[1:])
        and not help
        and not dry_run
    )

    if create_appdata:
        appdata_mod.generate(pydir, lastmod_time)

    if appdata:
        sys.argv.remove("appdata")

    if inno and sys.platform == "win32":
        inno_mod.generate(pydir, bdist_cmd, arch, dry_run)
        sys.argv.remove("inno")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if not appdata or sys.argv[1:]:
        print(sys.argv[1:])
        from DisplayCAL._setup import main

        main()

    if dry_run or help:
        return

    if setup_cfg or ("bdist_msi" in sys.argv[1:] and use_setuptools):
        shutil.copy2(Path(pydir, "setup.cfg.backup"), Path(pydir, "setup.cfg"))
