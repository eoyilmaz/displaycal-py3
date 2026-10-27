# Changelog

All notable changes to DisplayCAL since the Python 3 port (3.9.x) are listed here, newest first. The same notes are published with each release on the [GitHub releases page](https://github.com/eoyilmaz/displaycal-py3/releases).

The changelog of the original Python 2 DisplayCAL by Florian Höch (3.8.9.3 and earlier) is kept in [CHANGELOG-legacy.html](CHANGELOG-legacy.html).

## 3.10.0 - Unreleased

DisplayCAL 3.10.0 is the first release that ships a second user interface built on Qt (PySide6), next to the existing wxPython one. Almost every window has been ported, and we'd like you to start using it. This release also drops Python 3.9 and 3.10, and fixes a long list of crashes and accuracy issues reported since 3.9.19.

### ✨ Highlights

- **New Qt user interface (opt-in).** Every main window, tool and dialog has a Qt (PySide6) counterpart: the main window, measurement and adjustment windows, profile info viewer, curve viewer, 3D LUT maker, testchart editor, synthetic ICC creator, visual whitepoint editor, measurement reports, untethered measurement, display uniformity, the scripting client and the profile loader tray icon. ([#836](https://github.com/eoyilmaz/displaycal-py3/pull/836) and follow-ups by @eoyilmaz)
  - To try it, accept the offer DisplayCAL shows on startup, or enable **Options > Advanced > Use Qt user interface (experimental)** and restart DisplayCAL. You can switch back the same way from the Qt UI. The `--qt` / `--wx` command line flags and the `DISPLAYCAL_UI=qt` / `DISPLAYCAL_UI=wx` environment variable override the setting for a single launch.
  - **Roadmap:** in 3.10.x wx stays the default and Qt is opt-in. In 3.11.x Qt becomes the default and wx is still available. DisplayCAL 4.0 will be Qt only.
  - Please [report](https://github.com/eoyilmaz/displaycal-py3/issues/new?template=bug_report.yml) anything that looks or behaves differently from the wx UI, and choose "Qt" as the user interface in the bug report.
- **Python 3.11 is now the minimum.** Python 3.9 and 3.10 are no longer supported. ([#1001](https://github.com/eoyilmaz/displaycal-py3/pull/1001) by @eoyilmaz)
- **The DEB and RPM packages install offline.** All Python dependencies are bundled as wheels, so installing no longer downloads or compiles anything. ([#1012](https://github.com/eoyilmaz/displaycal-py3/pull/1012) by @eoyilmaz)

### 🚀 Improvements

- Verification reports now show whether the calibration was applied during the measurement, and warn when a device link profile is verified without a 3D LUT. ([#1004](https://github.com/eoyilmaz/displaycal-py3/pull/1004) by @eoyilmaz)
- Profile creation fails with a clear error instead of hanging forever when one of the worker processes dies. ([#1013](https://github.com/eoyilmaz/displaycal-py3/pull/1013) by @eoyilmaz)
- Creating a profile from a session whose `.cal` file has no calibration settings now offers to load the settings from the session's profile instead. ([#1015](https://github.com/eoyilmaz/displaycal-py3/pull/1015) by @eoyilmaz)
- The colorimeter correction web-check dialog columns can be sorted. ([#959](https://github.com/eoyilmaz/displaycal-py3/pull/959) by @eoyilmaz)
- Hardened the import of iColorDisplay `DeviceCorrections.txt` files. ([#1002](https://github.com/eoyilmaz/displaycal-py3/pull/1002) by @eoyilmaz)
- The Spyder 2024 OLED and Mini-LED measurement modes are refused with an explanation on ArgyllCMS 3.5.0 and older, which can't handle them. ([#1008](https://github.com/eoyilmaz/displaycal-py3/pull/1008) by @eoyilmaz)

### 🐛 Bug Fixes

#### 🧩 General

- Fixed the shaper curves mapping white to `(1, 1, 1)` instead of the display's white point, which could tint highlights. ([#1010](https://github.com/eoyilmaz/displaycal-py3/pull/1010) by @eoyilmaz)
- Fixed every measurement failing when frame insertion was enabled. ([#1011](https://github.com/eoyilmaz/displaycal-py3/pull/1011) by @eoyilmaz)
- Fixed "can't concat int to bytes" when creating a profile from an existing profile. ([#1015](https://github.com/eoyilmaz/displaycal-py3/pull/1015) by @eoyilmaz)
- Fixed the ArgyllCMS download prompt not appearing at startup when ArgyllCMS is missing. ([#957](https://github.com/eoyilmaz/displaycal-py3/pull/957) by @eoyilmaz)
- Fixed the ArgyllCMS update dialog showing an outdated changelog. ([#950](https://github.com/eoyilmaz/displaycal-py3/pull/950) by @eoyilmaz)
- Fixed ArgyllCMS versions being compared as text instead of numbers in the gamut mapping window. ([#876](https://github.com/eoyilmaz/displaycal-py3/pull/876) by @eoyilmaz)
- Fixed the Verification tab's testchart edit button opening the wrong chart. ([#872](https://github.com/eoyilmaz/displaycal-py3/pull/872) by @eoyilmaz)
- Fixed the madVR test pattern generator setup failing, and fragmented network packets from madTPG being parsed incorrectly. ([#988](https://github.com/eoyilmaz/displaycal-py3/pull/988) by @voidvideo)
- Fixed the scripting host crashing when a client disconnects in the middle of a response. ([#982](https://github.com/eoyilmaz/displaycal-py3/pull/982) by @mkiera)
- Fixed the settings file path getting mangled on systems whose locale isn't UTF-8. ([#832](https://github.com/eoyilmaz/displaycal-py3/pull/832) by @eoyilmaz)
- Fixed a series of Python 2 to 3 bytes/str bugs found in a code audit. ([#933](https://github.com/eoyilmaz/displaycal-py3/pull/933), [#945](https://github.com/eoyilmaz/displaycal-py3/pull/945) by @eoyilmaz)
- Fixed reading colorimeter correction (`.ccmx`) files with a non-default system encoding. ([#973](https://github.com/eoyilmaz/displaycal-py3/pull/973) by @ahjulstad)
- `print()` output is written to the log file again in the packaged builds, which makes bug reports much more useful. ([#1009](https://github.com/eoyilmaz/displaycal-py3/pull/1009) by @eoyilmaz)
- Fixed a crash closing the Visual Whitepoint Editor, and an error when floating its control panel. ([#905](https://github.com/eoyilmaz/displaycal-py3/pull/905), [#907](https://github.com/eoyilmaz/displaycal-py3/pull/907) by @eoyilmaz)
- Fixed the display uniformity measurement hanging. ([#948](https://github.com/eoyilmaz/displaycal-py3/pull/948) by @eoyilmaz)

#### 🪟 Windows

- Fixed HDR detection, and the profile loader now applies the profile that matches the display's current HDR or SDR mode. ([#1007](https://github.com/eoyilmaz/displaycal-py3/pull/1007) by @eoyilmaz)
- Fixed measurements failing with a cryptic CGATS error when ArgyllCMS reports an invalid reading as `-nan(ind)`. ([#1014](https://github.com/eoyilmaz/displaycal-py3/pull/1014) by @eoyilmaz)
- Fixed ArgyllCMS tools failing to start on some Windows 11 systems because attaching the console was aborted instead of retried. ([#994](https://github.com/eoyilmaz/displaycal-py3/pull/994) by @antoniohqueiroz)
- The profile loader retries reading the ICC profile after a failure instead of giving up. ([#977](https://github.com/eoyilmaz/displaycal-py3/pull/977) by @Xare123)

#### 🍎 macOS

- Fixed displays with the same resolution being mixed up, by identifying them by their CoreGraphics display ID. ([#1005](https://github.com/eoyilmaz/displaycal-py3/pull/1005) by @eoyilmaz)
- Fixed the colorimeter correction web-check finding nothing for Apple built-in displays. ([#961](https://github.com/eoyilmaz/displaycal-py3/pull/961) by @eoyilmaz)

#### 🐧 Linux

- Fixed installing profiles through colord on Wayland. ([#974](https://github.com/eoyilmaz/displaycal-py3/pull/974) by @ahjulstad)
- Fixed the profile creation worker processes aborting on Linux, by starting them with `spawn` instead of `fork`. ([#1013](https://github.com/eoyilmaz/displaycal-py3/pull/1013) by @eoyilmaz)
- Fixed the AppImage and Flatpak builds. ([#963](https://github.com/eoyilmaz/displaycal-py3/pull/963), [#1000](https://github.com/eoyilmaz/displaycal-py3/pull/1000) by @eoyilmaz)
- Fixed the Debian package shipping a stray `debian` Python module. ([#1003](https://github.com/eoyilmaz/displaycal-py3/pull/1003) by @eoyilmaz)

### 🛠️ Packaging and Development

- Modernized the build: `setup.py` no longer runs packaging logic on every PEP 517 build or rewrites `MANIFEST.in`, duplicated metadata and dead freeze back ends were removed, and `native_build.py` was split up. ([#919](https://github.com/eoyilmaz/displaycal-py3/pull/919), [#920](https://github.com/eoyilmaz/displaycal-py3/pull/920), [#921](https://github.com/eoyilmaz/displaycal-py3/pull/921), [#922](https://github.com/eoyilmaz/displaycal-py3/pull/922), [#923](https://github.com/eoyilmaz/displaycal-py3/pull/923), [#926](https://github.com/eoyilmaz/displaycal-py3/pull/926), [#929](https://github.com/eoyilmaz/displaycal-py3/pull/929), [#931](https://github.com/eoyilmaz/displaycal-py3/pull/931) by @eoyilmaz)
- Split `icc_profile.py` into a package, made `CGATS` a `MutableMapping` instead of a `dict` subclass, and removed leftover Python 2 compatibility code. ([#935](https://github.com/eoyilmaz/displaycal-py3/pull/935), [#937](https://github.com/eoyilmaz/displaycal-py3/pull/937), [#939](https://github.com/eoyilmaz/displaycal-py3/pull/939), [#941](https://github.com/eoyilmaz/displaycal-py3/pull/941), [#943](https://github.com/eoyilmaz/displaycal-py3/pull/943) by @eoyilmaz)
- Fixed the `pip` console-script entry points pointing at functions that didn't exist. ([#833](https://github.com/eoyilmaz/displaycal-py3/pull/833) by @eoyilmaz)
- The changelog is now this Markdown file; the pre-3.9 history moved to `CHANGELOG-legacy.html`. ([#1017](https://github.com/eoyilmaz/displaycal-py3/issues/1017) by @eoyilmaz)
- Release downloads come with a signed build provenance attestation, so you can check that a file was built by the release workflow from the tagged source with `gh attestation verify <file> -R eoyilmaz/displaycal-py3`. ([#1017](https://github.com/eoyilmaz/displaycal-py3/issues/1017) by @eoyilmaz)

### 🙏 Thanks

Thanks to everyone who contributed to this release, including @ahjulstad, @Xare123, @mkiera, @voidvideo and @antoniohqueiroz for their first contributions.

## [3.9.19](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.19) - 2026-07-13

A quick follow-up to 3.9.18, this release adds Linux AppImage/Flatpak packages and fixes 20 issues, mostly stability and crash fixes surfaced by users right after the last release, plus several latent Python 3 bytes/str bugs found during a code audit.

### ✨ Highlights

- **AppImage and Flatpak packages** are now built and published alongside the existing DEB/RPM installers. ([#232](https://github.com/eoyilmaz/displaycal-py3/pull/796) by @eoyilmaz)

### 🚀 Improvements

- DEB/RPM postinstall now prints progress instead of running silently, installs prebuilt wxPython wheels from the wxPython extras index, and pulls in the `dbus-python` build dependencies, fixing installation on Ubuntu 24.04/26.04. ([#805](https://github.com/eoyilmaz/displaycal-py3/pull/807) by @eoyilmaz)

### 🐛 Bug Fixes

#### 🧩 General
- Fixed `displaycal.ini` becoming mangled and ballooning to gigabytes in size, eventually crashing the app from memory exhaustion. Config writes are now atomic and lock-protected, oversized config files are quarantined instead of parsed, and the config is explicitly read as UTF-8 so mismatched locale codepages can no longer corrupt it further. ([#828](https://github.com/eoyilmaz/displaycal-py3/pull/829), [#828](https://github.com/eoyilmaz/displaycal-py3/pull/832) by @eoyilmaz)
- Fixed several `pip`-installed console scripts (`displaycal-vrml-to-x3d-converter`, `displaycal-scripting-client`, `displaycal-eecolor-to-madvr-converter` and their console variants) crashing with `AttributeError` because their entry-point functions didn't exist. ([#797](https://github.com/eoyilmaz/displaycal-py3/pull/833) by @eoyilmaz)
- Fixed invalid filename characters from surviving into color profile names. ([#819](https://github.com/eoyilmaz/displaycal-py3/pull/831) by @eoyilmaz)
- Fixed `unsupported format string passed to tuple.__format__` error when generating a cube 3D LUT. ([#827](https://github.com/eoyilmaz/displaycal-py3/pull/830) by @eoyilmaz)
- Fixed a `TypeError` crash and incorrect `CTI3` file-type comparisons in measurement/profile handling caused by leftover Python 2-to-3 bytes/str bugs. ([#811](https://github.com/eoyilmaz/displaycal-py3/pull/812) by @eoyilmaz)
- Fixed the `profile.unsupported` dialog showing a raw bytes value (e.g. `b'mntr'`) instead of the decoded text, across 12 sites. ([#815](https://github.com/eoyilmaz/displaycal-py3/pull/816) by @eoyilmaz)
- Fixed three latent bytes/str Python 3 port bugs in `load_cal_handler`/`import_session_archive_producer`. ([#817](https://github.com/eoyilmaz/displaycal-py3/pull/818) by @eoyilmaz)
- Fixed four more bytes/str bugs that made `load_cal_handler`'s 3D LUT/profile B2A metadata-restore block unreachable dead code. ([#820](https://github.com/eoyilmaz/displaycal-py3/pull/821) by @eoyilmaz)
- Fixed a `TypeError` from `str` regex patterns matched against `bytes` content in the ReShade/MasterEffect 3D LUT install patchers. ([#808](https://github.com/eoyilmaz/displaycal-py3/pull/809) by @eoyilmaz)
- Fixed an `Event is undefined` error when the number of worker threads is 1. ([#799](https://github.com/eoyilmaz/displaycal-py3/pull/800) by @lexxxel)

#### 🍎 macOS
- Fixed a crash when the first measurement taken after launch is a Measurement Report or Colorimeter Correction. ([#822](https://github.com/eoyilmaz/displaycal-py3/pull/823) by @ethanbrookins)
- Fixed an infinite black-screen ping-pong across multiple displays during VideoLUT recovery, by reloading the clobbered LUTs via CoreGraphics from a single persistent process instead of spawning `dispwin`. ([#824](https://github.com/eoyilmaz/displaycal-py3/pull/826) by @eoyilmaz)

#### 🪟 Windows
- Fixed `DisplayCAL.mscms.manager`'s logger writing to `sys.stderr`, which made the frozen windowed `.exe` falsely show an "Errors in..." dialog on every close even though nothing had actually failed. ([#804](https://github.com/eoyilmaz/displaycal-py3/pull/806) by @eoyilmaz)

### 🙏 Thanks

Thanks to everyone who contributed to this release, including @lexxxel for their first contribution, and @ethanbrookins.

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.18...3.9.19

## [3.9.18](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.18) - 2026-07-05

It's been almost 10 months since 3.9.17, and this release reflects that: 72 merged pull requests, 524 commits, and 104 closed issues worth of work, adding support for a new colorimeter, ArgyllCMS 3.5.0 compatibility, and a large batch of accumulated stability and accuracy fixes across Windows, macOS, and Linux.

### ✨ Highlights

- **New instrument support:** Datacolor Spyder2024 (SpyderX2). ([#620](https://github.com/eoyilmaz/displaycal-py3/pull/620) by @g4bri3lDev)
- **ArgyllCMS 3.5.0 support**, including the new spectral plot (`specplot`) option. ([#645](https://github.com/eoyilmaz/displaycal-py3/pull/645) by @jaminmc)
- The simplified splash screen (previously macOS-only) is now available on **all platforms**, fully translated. ([#787](https://github.com/eoyilmaz/displaycal-py3/pull/787) by @ethanbrookins, [#791](https://github.com/eoyilmaz/displaycal-py3/pull/791) by @eoyilmaz)
- **Windows ARM64** builds ([#741](https://github.com/eoyilmaz/displaycal-py3/pull/741), [#747](https://github.com/eoyilmaz/displaycal-py3/pull/747) by @eoyilmaz) and **Linux DEB/RPM** installer packages ([#739](https://github.com/eoyilmaz/displaycal-py3/pull/739) by @eoyilmaz) are now available.

### 🚀 Improvements

- Improved Web @ localhost remote calibration: fixed freezing/retry issues, corrected color accuracy shown in the browser, and improved handling when multiple devices are connected. ([#647](https://github.com/eoyilmaz/displaycal-py3/pull/647) by @jaminmc)
- Automatic retry when a spectrophotometer's ambient light diffuser interrupts a measurement. ([#733](https://github.com/eoyilmaz/displaycal-py3/pull/733) by @eoyilmaz)
- Added a warning in the measurement report when the display's actual white point drifts noticeably from the profile's target. ([#761](https://github.com/eoyilmaz/displaycal-py3/pull/761) by @eoyilmaz)
- You can now sort the colorimeter corrections table by clicking its column headers. ([#752](https://github.com/eoyilmaz/displaycal-py3/pull/752) by @eoyilmaz)
- Sped up 3D LUT (B2A) table generation. ([#781](https://github.com/eoyilmaz/displaycal-py3/pull/781) by @eoyilmaz)
- Your saved "2012" observer settings are now migrated automatically to the "2015" naming used by ArgyllCMS 3.4+, no action needed. ([#760](https://github.com/eoyilmaz/displaycal-py3/pull/760) by @eoyilmaz)
- ArgyllCMS downloads and version checks now use a new, more reliable GitHub-hosted source. ([#750](https://github.com/eoyilmaz/displaycal-py3/pull/750) by @eoyilmaz)

### 🐛 Bug Fixes

#### 🧩 General
- Fixed profiles sometimes crushing near-black shadow detail together. ([#724](https://github.com/eoyilmaz/displaycal-py3/pull/724) by @eoyilmaz)
- Fixed a startup crash some users hit right after launching the app. ([#726](https://github.com/eoyilmaz/displaycal-py3/pull/726) by @eoyilmaz)
- Fixed a spurious warning and a crash in the 3D VRML view/export. ([#725](https://github.com/eoyilmaz/displaycal-py3/pull/725), [#783](https://github.com/eoyilmaz/displaycal-py3/pull/783) by @eoyilmaz)
- Fixed profile creation failing on machines with more than 60 CPU cores/threads. ([#717](https://github.com/eoyilmaz/displaycal-py3/pull/717) by @eoyilmaz)
- Fixed corruption and an overly strict white point check that could affect XYZ LUT-based profiles. ([#721](https://github.com/eoyilmaz/displaycal-py3/pull/721) by @Youfffeng)
- Fixed duplicate "please calibrate your instrument" prompts. ([#765](https://github.com/eoyilmaz/displaycal-py3/pull/765) by @eoyilmaz)
- Fixed the app losing track of colorimeter correction measurement progress after a crash. ([#767](https://github.com/eoyilmaz/displaycal-py3/pull/767) by @eoyilmaz)
- Fixed saving the log file so it no longer gets corrupted. ([#744](https://github.com/eoyilmaz/displaycal-py3/pull/744) by @eoyilmaz)
- Fixed an error that could occur when applying calibration/profile associations. ([#754](https://github.com/eoyilmaz/displaycal-py3/pull/754) by @eoyilmaz)
- Fixed a crash when a profile's filename included the `%crc32` placeholder. ([#777](https://github.com/eoyilmaz/displaycal-py3/pull/777) by @eoyilmaz)
- Fixed uploading/checking colorimeter corrections online. ([#789](https://github.com/eoyilmaz/displaycal-py3/pull/789) by @eoyilmaz)
- Fixed 3D LUT settings being unexpectedly reset when creating a new profile. ([#655](https://github.com/eoyilmaz/displaycal-py3/pull/655) by @Adam-Color)
- Fixed profiles not reloading correctly after changing certain settings. ([#678](https://github.com/eoyilmaz/displaycal-py3/pull/678) by @jaminmc)
- Fixed the testchart editor grid on newer Python versions (3.10+). ([#677](https://github.com/eoyilmaz/displaycal-py3/pull/677) by @jaminmc)
- Removed excessive debug output that could slow things down. ([#699](https://github.com/eoyilmaz/displaycal-py3/pull/699) by @Adam-Color)

#### 🪟 Windows
- Fixed build/compatibility issues on Python 3.13+, including Windows color management integration. ([#646](https://github.com/eoyilmaz/displaycal-py3/pull/646) by @jaminmc)
- Fixed the ARM64 installer refusing to install on ARM64 systems. ([#747](https://github.com/eoyilmaz/displaycal-py3/pull/747), [#748](https://github.com/eoyilmaz/displaycal-py3/pull/748) by @eoyilmaz)
- Fixed the monitor name showing as a generic "Plug and Play" device instead of its real model name. ([#740](https://github.com/eoyilmaz/displaycal-py3/pull/740) by @eoyilmaz)
- Fixed the on-screen color patch being positioned incorrectly at display scaling above 100%. ([#743](https://github.com/eoyilmaz/displaycal-py3/pull/743) by @eoyilmaz)
- Fixed gamut coverage not being displayed, caused by a file path bug. ([#746](https://github.com/eoyilmaz/displaycal-py3/pull/746) by @eoyilmaz)
- Fixed oversized "fancy" text rendering at certain scaling levels. ([#755](https://github.com/eoyilmaz/displaycal-py3/pull/755) by @DamoyY)
- Fixed a Profile Loader crash when monitors are reconnected or rearranged. ([#763](https://github.com/eoyilmaz/displaycal-py3/pull/763) by @eoyilmaz)
- HDR calibration profiles are no longer incorrectly forced while the display is in SDR mode; HDR detection is now more reliable on Windows 11 22H2+. ([#766](https://github.com/eoyilmaz/displaycal-py3/pull/766), [#771](https://github.com/eoyilmaz/displaycal-py3/pull/771) by @eoyilmaz)
- Fixed saving a profile with SMPTE 2084 (HDR PQ) roll-off causing an error. ([#716](https://github.com/eoyilmaz/displaycal-py3/pull/716) by @eoyilmaz)

#### 🍎 macOS
- Fixed a black screen appearing during calibration on some Macs. ([#723](https://github.com/eoyilmaz/displaycal-py3/pull/723) by @eoyilmaz)
- Fixed a crash on quit on macOS Sonoma 14.6. ([#681](https://github.com/eoyilmaz/displaycal-py3/pull/681) by @eoyilmaz)
- Fixed bundled tool apps (e.g. the 3D LUT viewer) sometimes launching the wrong app. ([#722](https://github.com/eoyilmaz/displaycal-py3/pull/722) by @eoyilmaz)
- Fixed app signing so all bundled tool apps are properly signed. ([#684](https://github.com/eoyilmaz/displaycal-py3/pull/684) by @eoyilmaz)
- Fixed a crash when creating a colorimeter correction. ([#732](https://github.com/eoyilmaz/displaycal-py3/pull/732) by @eoyilmaz)
- Fixed a crash when saving the log window on certain macOS versions. ([#759](https://github.com/eoyilmaz/displaycal-py3/pull/759) by @eoyilmaz)
- Fixed display names showing as generic instead of the real monitor model on Apple Silicon Macs and macOS Tahoe. ([#774](https://github.com/eoyilmaz/displaycal-py3/pull/774) by @eoyilmaz)

#### 🐧 Linux
- Fixed display names showing as generic "Monitor" instead of the real model name. ([#762](https://github.com/eoyilmaz/displaycal-py3/pull/762) by @eoyilmaz)
- Fixed the interactive display adjustment step hanging under Wayland. ([#768](https://github.com/eoyilmaz/displaycal-py3/pull/768) by @eoyilmaz)
- Added a clearer error message when a required wxPython system library is missing. ([#745](https://github.com/eoyilmaz/displaycal-py3/pull/745) by @eoyilmaz)

### 🙏 Thanks

Thanks to everyone who contributed to this release, including first-time contributors @g4bri3lDev, @jaminmc, @Youfffeng, and @DamoyY.

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.17...3.9.18

## [3.9.17](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.17) - 2025-09-11

* **[ALL]** Added support for ArgyllCMS 3.4.0+ in regards of the update on the observer names of CIE 2012 2° and CIE 2012 10° being CIE 2015 2° and CIE 2015 10°. Depending on the ArgyllCMS version the old names are still going to be accessible through the UI.
* **[ALL]** Fixed an issue related to the black point correction being applied even if it is disabled introduced in DisplayCAL 3.9.15.
* **[ALL]** Fixed `dispread` arguments not being added to argument list by @Anulap
* **[ALL]** Fixed unnecessary argument quoting in `DisplayCAL.wexpect.spawn_windows.__init__()` by @eoyilmaz
* **[ALL]** Fixed `IndexError` in a string formatting in `DisplayCAL.worker` by @vastunghia
* **[Windows]** Fixed the issues related with displays with scaling value more than 150%, where DisplayCAL errors out on startup by @eoyilmaz
* **[Windows]** Fixed Profile Loader "Identify Monitor" and "Exceptions" dialog crash by @Anulap
* **[Windows]** Fexed output level reporting for and some other issues related to madVR by @eoyilmaz

### What's Changed
* 556 update osx install instructions by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/558
* 553 anybutton error by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/559
* Windows specific fixes for various feature by @Anulap in https://github.com/eoyilmaz/displaycal-py3/pull/579
* 580 a bytes like object is required not int when trying to verify with colormunki by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/582
* Fix issue [#577](https://github.com/eoyilmaz/displaycal-py3/issues/577) by @vastunghia in https://github.com/eoyilmaz/displaycal-py3/pull/589
* 585 displaycal can not start after first install by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/598
* [#583] Added support for the new names given for the CIE 2012 2° and … by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/599
* [#570] Fix for [#570](https://github.com/eoyilmaz/displaycal-py3/issues/570). Removed the skipping of the `-b` parameter in `D… by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/600

### New Contributors
* @Anulap made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/579
* @vastunghia made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/589

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.16...3.9.17

## [3.9.16](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.16) - 2025-05-04

* **[Windows]** Fixed the `WPARAM` error message on the Profile Loader.
* **[Windows]** Fixed the `wxAnyButton::doSetBitmap()` related error message that occured on startup.
* **[Windows]** Fixed ArgyllCMS USB device driver installation procedure.
* **[Windows]** Fixed `RecursionError: maximum recursion depth exceeded` error which originated to `DisplayCAL.taskscheduler.Task.__str__()` method.
* **[macOS]** Fixed the shifted gamma of the screen captured background of the splash screen or made it a better than before.
* **[Linux]** Made it clear that the logged exception is for a handled exception in `DisplayCAL.worker.Worker.exec_cmd()` related to DBus.
* **[Linux]** Fixed tests running on linux + arm64.
* **[ALL]** Dropped Python 3.8 support as it has reached end-of-life on October 2024.
* **[ALL]** Removed residual code and dependencies required for Python 2 support (`six`,  `enum34` etc.).
* **[ALL]** Added tests for `wxPython=4.2.3` on all platforms.
* **[ALL]** Update recommended `wxPython` version to `4.2.0` to get rig of the messages saying `4.2.1` is not supported anymore, which is not true.
* **[ALL]** Fixed many string formatting issues introduced with 3.9.15.
* **[ALL]** Fixed `DisplayCAL.icc_profile.ICCProfile.load()`when all the data has already been read.
* **[ALL]** Fixed `AttributeError: NoneType object has no attribute 'listening'` error originated to `DisplayCAL.wxwindows.BaseApp.query_and_session()` method.
* **[ALL]** Fixed `DisplayCAL.icc_profileICCProfile.get_info()` to correctly identify the white point illuminant tag for the key `wtpt`.
* **[ALL]** Added the `PVA` term in any tech names that mentions `VPA` in `display.tech` section for all language files to match ArgyllCMS tech names output.
* **[ALL]** Replaced the `locale.getdefaultlocale()` call in `DisplayCAL.config` with `locale.getlocale()` as the original function is getting deprecated in Python 3.9.15.
* **[ALL]** Moved most of the ArgyllCMS related utility functions from `DisplayCAL.worker` to `DisplayCAL.argyll`.
* **[ALL]** Updated `DisplayCAL.argyll.get_argyll_version_string()` to first try to get the ArgyllCMS version from the `log.txt` instead of running any utility functions to make it run faster, especially under macOS. It will fallback to the normal method if it can't retrieve the version from the `log.txt`.
* **[ALL]** Renamed a couple of the modules to comply with PEP8 rules:
  * `DisplayCAL.ICCProfile` is now `DisplayCAL.icc_profile`.
  * `DisplayCAL.CATS` is now `DisplayCAL.cats`.
* **[ALL]** Capitalized the enum variables in `DisplayCAL.icc_profile module.
* **[ALL]** Fixed the generation and display of the `meta.prefix` tag of the `ICCProfile`.
* **[ALL]** Fixed `DisplayCAL.worker_base.Xicclu.close()` to properly handle error output as `bytes`.
* **[ALL]** Added `tox` as a development requirement.
* **[ALL]** Updated the `build` target in make workflow to use `uv`.
* **[ALL]** Fix `update_menus()` and `install_argyll_instrument_conf()` method of `DisplayCAL.display_cal.MainFrame` class.
* **[ALL]** Rename package from `DisplayCAL` to `displaycal` in `pyproject.toml` to comply with PyPI naming conventions.

### What's Changed
* [#501] Fixed [#501](https://github.com/eoyilmaz/displaycal-py3/issues/501) by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/504
* [#506] Fixed gamma of the background of the splash screen under macOS… by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/508
* 502 ccss creation with i1pro3 does not seem to work by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/505
* 509 error when extracting usb drivers from argyll archive by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/517
* [#515] Fixed [#515](https://github.com/eoyilmaz/displaycal-py3/issues/515). by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/518
* [#512] Fixed [#512](https://github.com/eoyilmaz/displaycal-py3/issues/512). by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/519
* Update install_instructions_macos.md by @amkdev in https://github.com/eoyilmaz/displaycal-py3/pull/523
* Fix typo by @bradyjoh in https://github.com/eoyilmaz/displaycal-py3/pull/529
* [#528] Fixed [#528](https://github.com/eoyilmaz/displaycal-py3/issues/528). by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/531
* [#484] Made it clear that the logged exception is for a handled excep… by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/532
* 455 displaycal 3914 for windows error when poweroff or restart compoter by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/534
* 514 profile loader 3915   minor errors wparam audio driver restart by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/533
* [#542] Fixed [#542](https://github.com/eoyilmaz/displaycal-py3/issues/542). by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/543
* [#546] Dropped Python 3.8 support. by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/547
* drop references to old "six" and "enum34" compat libraries by @a-detiste in https://github.com/eoyilmaz/displaycal-py3/pull/549
* trim leftover Python2 compatibility by @a-detiste in https://github.com/eoyilmaz/displaycal-py3/pull/550
* 536 collinkexe error   write file 782 technology signature dcpj is unknown by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/544

### New Contributors
* @amkdev made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/523
* @bradyjoh made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/529
* @a-detiste made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/549

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.15...3.9.16

## [3.9.15](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.15) - 2025-04-02

**Big Items**:
* Windows version should now work without a major issue. So, the previous problems about not being able to run ArgyllCMS executables has been resolved, and paths containing empty spaces are handled correctly.
* The dependency to the `RealDisplaySizeMM` has been removed. So DisplayCAL doesn't require any C-Extensions to be compiled and this makes it easier to install on different OSes.
* Added CI GitHub workflow for Windows.
* Lots of code refactoring and cleanup many thanks to @oldgithubman for their hard work.
* As it was getting harder to test for wxPython 4.1.1, the minimum wxPython version that we test DisplayCAL with has been upgraded to 4.2.0.
* CI GitHub tests run much faster under Linux (45-50 minutes vs 6-7 minutes) now as the tests are now using the pre-compiled wheels from wxPython website.
* Updated `DisplayCAL.lib.agw` from `0.9.1` to `0.9.7` from `wx.lib.agw` and introduced a lot of code refactoring and TypeHints on top of the original source.
* DisplayCAL development is now using the Rust tools for package management and linting. So, `uv` is the main package manager instead of `pip` and `ruff` replaces `black` and `flake8`.
* Removed `setup.cfg`, DisplayCAL is now fully using `pyproject.toml` for configuration. Unfortunately, we are still depending on the `setup.py`.

**Auto Generated Notes**
* Resolve broken reference to `wxenhancedplot._Numeric` by @Wedge009 in https://github.com/eoyilmaz/displaycal-py3/pull/430
* Update install instructions by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/433
* Fixed [#67](https://github.com/eoyilmaz/displaycal-py3/issues/67). by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/434
* Fix for [#251](https://github.com/eoyilmaz/displaycal-py3/issues/251) by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/439
* Update Readme to fix grammar, add new requirements to requirements-de… by @Adam-Color in https://github.com/eoyilmaz/displaycal-py3/pull/445
* Get rid of the realdisplaysizemm C-Extension by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/444
* General Refactoring and more TypeHints by @oldgithubman in https://github.com/eoyilmaz/displaycal-py3/pull/414
* Update install_instructions_linux.md by @aaronwi in https://github.com/eoyilmaz/displaycal-py3/pull/487
* Update install_instructions_linux.md by @MahmoudAdelbghany in https://github.com/eoyilmaz/displaycal-py3/pull/482
* A quick fix in the test chart editor by @ethanbrookins in https://github.com/eoyilmaz/displaycal-py3/pull/471
* Corrected a couple of misspellings. by @wadetregaskis in https://github.com/eoyilmaz/displaycal-py3/pull/497
* Additional fixes for [#67](https://github.com/eoyilmaz/displaycal-py3/issues/67) and [#31](https://github.com/eoyilmaz/displaycal-py3/issues/31) by @ethanbrookins in https://github.com/eoyilmaz/displaycal-py3/pull/470
* Further improvement and bugfixes for the colorimeter correction workflow by @ethanbrookins in https://github.com/eoyilmaz/displaycal-py3/pull/469
* Windows version can't start "dispread.exe" by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/499

### New Contributors
* @Wedge009 made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/430
* @Adam-Color made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/445
* @oldgithubman made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/414
* @aaronwi made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/487
* @MahmoudAdelbghany made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/482
* @wadetregaskis made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/497

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.14...3.9.15

## [3.9.14](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.14) - 2024-10-16

**Big Items**:
* Added MacOS package along with the updated Windows Installer (see the Warning above).
* Added Python 3.13 support for Linux/MacOS. Windows will support Python 3.8-3.11 for now.
* Fixed Ubuntu installation errors complaining about missing files.
* Fixed fail to open calibrate window under Debian.
* Updated default ArgyllCMS to 3.3.0 and latest version of ArgyllCMS will be parsed through www.argyllcms.com.
* Improved/added numPy 2.0 compatibility.
* Under MacOS it is now possible to install the profile system-wide (fixing lock/unlock profile shifts on XDR displays, logout/login is still problematic).

**Auto Generated Notes**
* [#421] Added support for Python 3.13. by @eoyilmaz in [#423](https://github.com/eoyilmaz/displaycal-py3/issues/423)
* Updated ArgyllCMS to 3.3.0 - by @parkatoast in [#405](https://github.com/eoyilmaz/displaycal-py3/issues/405)
* The latest version number of ArgyllCMS will now be automatically updated by @ethanbrookins in [#412](https://github.com/eoyilmaz/displaycal-py3/issues/412)
* Fixed encoding problems in wexpect for non cp1252 or utf-8 - by @eoyilmaz in [#409](https://github.com/eoyilmaz/displaycal-py3/issues/409)
* Added NumPy 2.0 compatibility - by @nschloe in [#408](https://github.com/eoyilmaz/displaycal-py3/issues/408)
* [#296] Fixed [#296](https://github.com/eoyilmaz/displaycal-py3/issues/296) - Can't install the profile after calibration ("sudo timeout") error - by @eoyilmaz in https://github.com/eoyilmaz/displaycal-py3/pull/429
* [#415] Fixed fail to open calibrate window under Debian - by @eoyilmaz in [#419](https://github.com/eoyilmaz/displaycal-py3/issues/419)
* [#400] Disabled universal bdist whell creation - by @eoyilmaz in [#420](https://github.com/eoyilmaz/displaycal-py3/issues/420)
* [#384] Fixed [#384](https://github.com/eoyilmaz/displaycal-py3/issues/384), added warning dialog for the user to know the ICC profile doesn't have a `targ` tag - by @eoyilmaz in [#425](https://github.com/eoyilmaz/displaycal-py3/issues/425)
* Improve Simplified Chinese translation - by @Headcrabed in [#426](https://github.com/eoyilmaz/displaycal-py3/issues/426)
* [#345] Fixed bug in Source Profile selection in Advanced Gamut Options dialog - by @eoyilmaz in [#428](https://github.com/eoyilmaz/displaycal-py3/issues/428)

### New Contributors
* @parkatoast made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/405
* @nschloe made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/408
* @Headcrabed made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/426

**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.13...3.9.14

## [3.9.13](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.13) - 2024-10-10

This release introduces lots of fixes, especially for Windows. The big items are:

* We now have a [Windows Installer](https://github.com/eoyilmaz/displaycal-py3/releases/download/3.9.13/DisplayCAL-3.9.13-Setup.exe). It might not fully work out of the box as we had very limited testing with both the installer and the frozen executables.
* Updated installation instructions with a cleaner and more understandable format for all OSes.
* Python 3.12 should now work fine under Linux and MacOS with wxPython 4.2.2. But, Windows is still problematic.
* Updated default config so that the default profile name doesn't contain any empty spaces.
* Updated Argyll CMS from V3.1.0 to V3.2.0 (v3.3.0 is already released, so it is left to the users to download).
* And lots of fixes here and there, check the [full changelog](https://github.com/eoyilmaz/displaycal-py3/compare/3.9.12...3.9.13) for details.

### New Contributors
* @ethanbrookins made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/328
* @lunochod made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/337
* @jelly made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/360
* @rickdoesdev made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/351
* @xz-dev made their first contribution in https://github.com/eoyilmaz/displaycal-py3/pull/380

**PyPI:** https://pypi.org/project/DisplayCAL/3.9.13/
**Full Changelog**: https://github.com/eoyilmaz/displaycal-py3/compare/3.9.12...3.9.13

## [3.9.12](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.12) - 2024-03-19

This release introduces lots of old and new, small and big bug fixes. Some notable changes are:

- Made improvements to Windows and MacOS builds.
- Fixed Resolve patch generator.
- Fixed ArgyllCMS download function.
- Fixed MacOS menu disappearing after measurement window is shown.
- Pipx should now be able locate lang files.
- Fixed setup tools fail on upgrade for nixpkgs.
- Fix Windows build and runtime on Python 3.11.4.
- Fixed lock file mishandling on Windows.
- Allow py2app to build a MacOS app
- Implemented a stable sort_by_L which falls back to a then b sort if L is equal.

**PyPI:** https://pypi.org/project/DisplayCAL/3.9.12/

### Contributions

This release's contributers are: Erkan Ozgur Yilmaz, Radosław Szkodziński, Vladislav Sharapov, Matt Khan, Patrick Zwerschke

Changes per contributor are as follows:

**Erkan Ozgur Yilmaz**
- Fixed [#282](https://github.com/eoyilmaz/displaycal-py3/issues/282) (not a real fix but an improvement).
- Fixed [#283](https://github.com/eoyilmaz/displaycal-py3/issues/283)
- Fixed [#61](https://github.com/eoyilmaz/displaycal-py3/issues/61)
- Fixed [#302](https://github.com/eoyilmaz/displaycal-py3/issues/302)
- Fixed a regular expression in `DisplayCAL.worker` module that might be the root cause of [#302](https://github.com/eoyilmaz/displaycal-py3/issues/302).
- Updated `utils.patch_consumer` so it stays on top.
- Optimized the `utils.patch_consumer` so that it uses 16bit colors (but the style sheet uses 8bit).
- Added `utils.patch_consumer` to test Resolve patch generator.
- Added `help` make target that displays all available targets.
- Fix for `DisplayCAL.worker_base.parse_argyll_version_string()` when the input is a `bytes` object.
- Fixed `BorderGradientButton` style for MacOS, which is used as the main button ("Calibrate & Profile" etc.).
- Updated the term "Authentification" to a more common one of "Authentication".
- Fixed [#291](https://github.com/eoyilmaz/displaycal-py3/issues/291)
- Fixed [#303](https://github.com/eoyilmaz/displaycal-py3/issues/303)
- Fixed [#137](https://github.com/eoyilmaz/displaycal-py3/issues/137)
- Fixed [#310](https://github.com/eoyilmaz/displaycal-py3/issues/310)
- [#318] Fixed a bug that is causing one empty line getting printed after each command output. The output is now better matching vanilla Argyll outputs.
- [#318] Fixed `display_cal.MeasurementFileCheckSanityDialog` for python 3.11+.
- [#318] Fixed `StartupFrame` test for MacOS.
- [#318] Introduced some quality of life improvements.
- [#318] Added `{pydir}/share` to data dirs.
- [#320] Did some unnecessary formatting updates while searching for a possible bug.
- Fixed [#271](https://github.com/eoyilmaz/displaycal-py3/issues/271)
- [#261](https://github.com/eoyilmaz/displaycal-py3/issues/261) setuptools build fails on upgrade for nixpkgs ([#272](https://github.com/eoyilmaz/displaycal-py3/issues/272))
- Updated Makefile workflow, it should now be easier to build/install/run DisplayCAL.
- Fixed "Manually Setup" section link.
- Update Makefile
- Updated Makefile new-release target to use the VERSION variable for the twine command.

**Radosław Szkodziński**
- Fix Windows build and runtime on Python 3.11.4 ([#312](https://github.com/eoyilmaz/displaycal-py3/issues/312))
- Fixes:
  - Runtime on Python 3.11
  - Setuptools, tested with 3.11.4
  - Missing pywin32 dependency
  - Lock file mishandling on Windows
  - Fix a mistake in version handling code

**Vladislav Sharapov**
- allow py2app to build a MacOS app ([#277](https://github.com/eoyilmaz/displaycal-py3/issues/277))
- Remove commented out block

**Matt Khan**
- untethered mode should take multiple white point measurements at the start and should only update the specific sample not all samples with the same RGB
- fix for [#276](https://github.com/eoyilmaz/displaycal-py3/issues/276) ([#278](https://github.com/eoyilmaz/displaycal-py3/issues/278))
  - correct bad string/bytes comparison which was preventing correction of gamma applied to a measurement report
  - workaround apparent wx regression with honouring hidden when set in xrc document [#276](https://github.com/eoyilmaz/displaycal-py3/issues/276)
- reformat using black
- Make maximise lightness diff sort stable
- minor code cleanup following pr comments
- implement a stable sort_by_L which falls back to a then b sort if L is equal
- demonstration of sort problem
- fix python3 (str/bytes) compatibility errors in untethered mode
- fix py3 compatibility problems in madtpg net
- csvwriter requires w mode in python3
- make sure measurement data is copied to the joined output, fixes [#224](https://github.com/eoyilmaz/displaycal-py3/issues/224)
- further py2-3 migration fixes around byte handling when handling madvr 3dlut
- fix python3 (str/bytes) compatibility errors in untethered mode

**Patrick Zwerschke**
- updated test workflow
- removed manual install of attrdict3 from workflow
- removed libreadline-gplv2-dev from packages.list
- updated test workflow to wxpython-4.2.1
- removed unnecessary wxpython-4.2.0 requirement (attrdict3)
- updated workflow to accommodate new branch restrictions

## [3.9.11](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.11) - 2023-06-05

The release notes will updated properly in the future. You can use the commit messages to deduce the information.

### Contributions

**Erkan Ozgur Yilmaz**
- Fixed new-release target in Makefile to do a pull before merging the develop branch.
- Fixed main branch name in Makefile.
- Updated Makefile to introduce new targets.
- Updated string formatting on several places in `wxProfileInfo`.
- Fixed `colorimeter_correction_web_check_choose()` to work properly for fractional scale.

**Patrick Zwerschke**
- Revert "fix eoyilmaz/displaycal-py3#231 ([#237](https://github.com/eoyilmaz/displaycal-py3/issues/237))" ([#239](https://github.com/eoyilmaz/displaycal-py3/issues/239))
- This reverts commit 59c456c5c73bc23e7a587f0fc48cf95556bcb204 that accidentally was pushed to main branch
- Updated actions to use Node.js 16 ([#220](https://github.com/eoyilmaz/displaycal-py3/issues/220))
- updated restrictions for max python version to run with python 3.11 ([#217](https://github.com/eoyilmaz/displaycal-py3/issues/217))
- Update test workflow for python 3.11 ([#215](https://github.com/eoyilmaz/displaycal-py3/issues/215))
- added python 3.11 to test workflow
- catch FileNotFoundError in module defaultpaths

**Matt Khan**
- allow untethered window to open

**Hubert Figuière**
- Fix appdata to validate for flathub ([#253](https://github.com/eoyilmaz/displaycal-py3/issues/253))
- Fix appdata to validate for flathub

**filmmakerto**
- fix eoyilmaz/displaycal-py3#231 ([#240](https://github.com/eoyilmaz/displaycal-py3/issues/240))
- Fixes [#231](https://github.com/eoyilmaz/displaycal-py3/issues/231)
- fix eoyilmaz/displaycal-py3#231 ([#237](https://github.com/eoyilmaz/displaycal-py3/issues/237))

**James Addison**
- Cleanup: remove no-longer-referenced get_known_folder_path, UserDirs class ([#227](https://github.com/eoyilmaz/displaycal-py3/issues/227))
- Cleanup: remove no-longer-referenced defaultpaths.get_known_folder_path method, and associated UserDirs class

**sdy623**
- Add feature: Add a gamut coverage information in Profile Information page

**stativ**
- Fix incorect bytes and string comparison when reading a .ti3 file ([#221](https://github.com/eoyilmaz/displaycal-py3/issues/221))

## [3.9.10](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.10) - 2022-11-21

There was an error with ``setup.py`` preventing DisplayCAL to be installed on Linux systems (macOS was working fine), thus released a new version 3.9.10.

## [3.9.9](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.9) - 2022-11-20

After waiting for more than 2 months since the last one (sorry about that), we now have a new release. Hopefuly the next release will not be that long away.

We have quite a bit of contribution, so I'll list changes grouped by the contributers.

Erkan Ozgur Yilmaz:

  - Fixed [#146](https://github.com/eoyilmaz/displaycal-py3/issues/146).
  - Fixed [#162](https://github.com/eoyilmaz/displaycal-py3/issues/162).
  - Updated ``requirement.txt`` and ``setup.cfg`` to only install ``dbus-python`` on Linux systems.
  - Updated README file as the MacOS instruction was not correct.
  - Fixed a small ``bytes`` getting concatenated with a ``str`` error in ``DisplayCAL.wxCCXXPlot.CCXXPlot`` class.
  - Fixed [#185](https://github.com/eoyilmaz/displaycal-py3/issues/185).
  - Fixes [#194](https://github.com/eoyilmaz/displaycal-py3/issues/194).
  - Updated ``util_http.encode_multipart_formdata()`` to generate ``bytes`` data instead of ``str``.
  - Fixed ``util_http.get_content_type()`` to handle ``bytes`` input.
  - Fixed ``DisplayCAL.ICCProfile.DictType.to_json()`` to use a proper ``JSONEncoder`` and fixed the ``bad escape \u at position 0`` error thrown by the ``re`` module.
  - Possible bug fix in ``DisplayCAL.wxSynthICCFrame.SynthICCFrame.icc_drop_handler()`` for checking the given ``profile.colorSpace`` against ``bytes`` values.
  - Fixed [#179](https://github.com/eoyilmaz/displaycal-py3/issues/179).
  - Updated ``.gitignore`` file to ignore any compiled library under the ``DisplayCAL/lib64/pythonXXX`` folders.

Patrick Zwerschke:

  - Reverted a change and fixed bug mentioned in [#154](https://github.com/eoyilmaz/displaycal-py3/issues/154).
  - Fixed drawing of tabs.

Krul Ceter:

  - RealDisplaySizeMM.c: fix error handling
  - fix setuptools module in DisplayCAL/setup.py (This one is reverted!)
  - fix deprecated "codeset" in gettext.translation() for python 3.11

François-Xavier Thomas:

  - Fix 3DLUT generation (ICCProfile class expected bytes, but got str in some cases).
  - Add exception tracebacks inside workers when displaycal is run with -d1.

ledoge:

  - More ICC parsing fixes.
  - Clip parametricCurveType values
  - Fix error on parsing ICC profiles
  - Fix typos in observer names

## [3.9.8](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.8) - 2022-09-15

The release change list is a combination of commit messages, and it is as follows:

- Fixed [#153](https://github.com/eoyilmaz/displaycal-py3/issues/153)
- Fixed [#171](https://github.com/eoyilmaz/displaycal-py3/issues/171)
- fix_device_values_scaling now initiates query with byte-str
- Fixes for [#169](https://github.com/eoyilmaz/displaycal-py3/issues/169) added
- Additional tests added
- Fixes [#171](https://github.com/eoyilmaz/displaycal-py3/issues/171)
  - switched from byte-str to str
  - setcgf does not set a list for "whitepoint.x" and "3dlut.whitepoint.x" anymore
- fix_device_values_scaling now initiates query with byte-str
- fixed positioning of newColourPanel
- Fixes for [#169](https://github.com/eoyilmaz/displaycal-py3/issues/169) added
  - changed comparison values for display_name to str in function visual_whitepoint_editor_handler
  - added uncritical integer conversion wherever needed in module wxVisualWhitepointEditor
- Fixed typo and removed comment
- Fixed implicit conversion to integers in MeasurementFileCheckSanityDialog
- Skip both failing tests atm:
  - test_check_file_isfile
  - test_colorimeter_correction_check_overwrite
- Workflow updated
- README updated
- Added wx4.2.0 to automated tests
- size of wx.Dialog initializer has been converted to integer
- Workflow updated to choose filepath for c-extension according to used python version
- Updated job string
- env variable corrected
- updated requirements to successfully install wxpython 4.2.0
- typo corrected
- updated workflow to test against wx 4.1.1 and wx 4.2.0
- size of wx.Dialog initializer has been converted to integer
- changed test to str comparison
- tests added for worker module
- ColumnSize converted to int before function call
- test if all classes of display_cal initialize properly
- test removed because of remote error
- test options removed because of remote error
- Fixed [#151](https://github.com/eoyilmaz/displaycal-py3/issues/151) and removed all the remaining ``__unicode__`` methods.
- Version bump.
- test_donation_message corrected
- tests for additional functions added
- additional tests for functions in display_cal added:
  - test_incrementing_int
  - test_webbrowser_open
  - test_install_scope_handler
  - test_get_cgats_path
  - test_get_cgats_measurement_mode

## [3.9.7](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.7) - 2022-08-08

- Fixed the display of ``colorimeter_correction_matrix_ctrl`` item name when ``Auto`` is selected on the main window.
- Convert ``float`` to ``int`` for calling wxPython's ``Scroll(self, int, int)`` correctly in ``DisplayCAL.wxfixes``.
- Fixed an issue related to the colorimeter check web check window not appearing correctly.
- Fixed [#148](https://github.com/eoyilmaz/displaycal-py3/issues/148).
- Fixed [#142](https://github.com/eoyilmaz/displaycal-py3/issues/142).
- Fixed ``gtk_box_gadget_distribute: assertion 'size >= 0' failed in GtkSpinButton`` messages on the ``Verification`` page.
- Fixed [#136](https://github.com/eoyilmaz/displaycal-py3/issues/136).
- Updated ``conftest.argyll()`` to use the ``v2.3.1`` of ``Argyll``.
- Updated ``conftest.argyll()`` to use the ``v2.3.1`` of ``Argyll`` also for local paths.
- Fixed ``worker.Worker._create_matrix_profile()`` to correctly concatenate the ``ti3`` data. This fixed profiling through the web browser.
- Fixed [#150](https://github.com/eoyilmaz/displaycal-py3/issues/150) related bugs:
  - Fixed fallback date in ``DisplayCAL.meta``.
  - Corrected build_time str in ``setup.py``.
  - Set ``lastmod`` to a valid date str in ``DisplayCAL.meta``.
  - Fixed build and/or last modification fallback date in ``DisplayCAL.setup``.

## [3.9.6](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.6) - 2022-06-11

- Some more fix for [#129](https://github.com/eoyilmaz/displaycal-py3/issues/129).
- Fixed [#132](https://github.com/eoyilmaz/displaycal-py3/issues/132) and many other things related to ``wxCCXXPlot``.
- Fixed [#130](https://github.com/eoyilmaz/displaycal-py3/issues/130). But this is probably not a good solution and [#124](https://github.com/eoyilmaz/displaycal-py3/issues/124) may need to be reverted and solved in a different way.
- Fixed [#124](https://github.com/eoyilmaz/displaycal-py3/issues/124)
- Possible fix for [#129](https://github.com/eoyilmaz/displaycal-py3/issues/129)
- Updated ``DisplayCAL.worker.Worker.prepare_dispread()`` to use ``BytesIO`` instead of ``StringIO``.
- Fixed ``DisplayCAL.worker.Worker.ti3_lookup_to_ti1()`` to properly generate ``ti1`` and ``t3v`` values.
- Fixed [#118](https://github.com/eoyilmaz/displaycal-py3/issues/118)
- Fixed the handling of EDID that contains ``b"\xc3"`` characters. Now, this fix is elegant and correctly addresses the issue.
- Possible fix for [#128](https://github.com/eoyilmaz/displaycal-py3/issues/128)
- Fixed [#126](https://github.com/eoyilmaz/displaycal-py3/issues/126)
- Add test case for a 384 byte EDID.
- Fixed ``DisplayCAL.RealDisplaySizeMM.get_wayland_display()`` to return the EDID data properly. With this change the fix in the ``DisplayCAL.edid.parse_edid()`` is not very necessary, but it has kept in case the given EDID has the wrong character coding.
- Fixed [#119](https://github.com/eoyilmaz/displaycal-py3/issues/119).
- Added test for [#119](https://github.com/eoyilmaz/displaycal-py3/issues/119).

## [3.9.5](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.5) - 2022-05-29

- Updated ``README`` file with instructions to switch to the ``develop`` branch if required.
- Re-enabled and also updated the ``findall`` function under ``setup.py``.
- Instrument configuration files are not going to get installed unless ``setup.py`` instructed to build the ``RPM`` package.
- ``build`` package has been moved from ``requirements.txt`` to ``requirements-dev.txt``.
- Updated ``45-Argyll.rules`` and ``55-Argyll.rules`` files from ArgyllCMS 2.3.0.
- Fixed [#111](https://github.com/eoyilmaz/displaycal-py3/issues/111)
- Fixed [#112](https://github.com/eoyilmaz/displaycal-py3/issues/112)
- Fixed [#113](https://github.com/eoyilmaz/displaycal-py3/issues/113)
- Fixes [#114](https://github.com/eoyilmaz/displaycal-py3/issues/114)
- Allow 384 byte EDID
- Misc py3 porting fixes
- Added a new item to the list of things to focus the future development effort.
- Reverted bytestr change.
- Moved test in ``argyll_RGB2XYZ``.
- Added tests for ``argyll_cgats``.
- Refactored ``argyll_cgats``.
- Updated ``README.md``, paraphrased some first person talk, updated with the latest development news.
- Updated ``AboutDialog`` size to accommodate all author names.
- Updated ``CHANGES.html`` with some information.
- Little update to the installation instructions.
- Possible fix for [#86](https://github.com/eoyilmaz/displaycal-py3/issues/86)
- Updated ``DisplayCAL.worker.Worker._install_profile_loader_xdg()`` to write the desktop file at once.
- Removed/replaced deprecated ``wxWidgets`` widgets with new ones. This will make DisplayCAL work only with ``wxWidgets>=4.1.1`` (or possibly with an earlier but more recent version), but it is okay.
- Fixed ``_SizeWindows`` and ``AdjustLayout`` methods of ``DisplayCAL.lib.agw.fourwaysplitter.FourWaySplitter`` for Python 3.10.
- Fixed ``_SizeWindows``, ``OnLeftUp`` and ``OnMotion`` methods of ``DisplayCAL.wxwindows.TwoWaySplitter`` for Python 3.10.
- The splitter in the Profile Info window is now properly working.
- Updated ``requirements.txt`` and made ``wxPython`` version ``4.1.1`` the minimum required version.

## [3.9.4](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.4) - 2022-05-16

- Fixed [#104](https://github.com/eoyilmaz/displaycal-py3/issues/104)
- Updated ``wxLUTViewer.py`` for [#86](https://github.com/eoyilmaz/displaycal-py3/issues/86).
- Fixed ``DisplayCAL.CGATS.CGATS.convert_XYZ_to_Lab()`` and test added.
- Added additional tests for ``CGATS`` and corrected ``DisplayCAL.CGATS.CGATS.get_cie_data_format()``.
- Replaced all string concatenations with format commands on possible code paths to fix the [#86](https://github.com/eoyilmaz/displaycal-py3/issues/86).

## [3.9.3](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.3) - 2022-05-04

- Fixed [#97](https://github.com/eoyilmaz/displaycal-py3/issues/97)
- Fixed ``gtk_box_gadget_distribute: assertion 'size >= 0' failed in GtkSpinButton`` errors in ``synthicc.xrc``.
- Removed ``libgtkd-3-dev`` dependency, which should be a typo and not necessary for DisplayCAL.
- Fixed ``gtk_box_gadget_distribute: assertion 'size >= 0' failed in GtkSpinButton`` errors in ``3dlut.xrc``.
- Replaced all string concatenations with format commands on possible code paths to fix the [#86](https://github.com/eoyilmaz/displaycal-py3/issues/86).
- Manually applied changes of [#99](https://github.com/eoyilmaz/displaycal-py3/issues/99) of @gavtroy.

## [3.9.2](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.2) - 2022-04-30

- Fixed LUTViewer to properly draw profiles under Python 3.10.

## [3.9.1](https://github.com/eoyilmaz/displaycal-py3/releases/tag/3.9.1) - 2022-04-30

For now we only have source distributions. The other packages will be added later on. Follow the instructions on the README (the project home page) to install.


## 3.9.x - 2022-04-01

The Python 3 port of DisplayCAL, continuing from the last Python 2 release (3.8.9.3).

- Added Python 3 support. DisplayCAL now works with Python 3.8+.
- Dropped Python 2.x support. DisplayCAL will not work with Python 2.x anymore.
- Dropped 32-bit support. DisplayCAL now works only on 64-bit operating systems.
