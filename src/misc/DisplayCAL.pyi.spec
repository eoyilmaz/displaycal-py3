# -*- mode: python -*-

from ConfigParser import ConfigParser
from distutils.util import get_platform
from py_compile import compile
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, '')
from meta import name as appname, version, script2pywname
from DisplayCAL.setup import (config, create_app_symlinks, get_data,
                              get_scripts, plist_dict)

sys.path.insert(1, 'util')
import winversion

library_zip = True

build_dir = os.path.join(os.getcwd(), 'build', 'pyi.%s-%s' % (get_platform(), sys.version[:3]),
                         appname + '.pyi')
dist_dir = os.path.join(os.getcwd(), 'dist', 'pyi.%s-py%s' % (get_platform(), sys.version[:3]),
                        '%s-%s' % (appname, version))

if sys.platform == 'win32':
    exe_ext = '.exe'
else:
    exe_ext = ''
    
if sys.platform == 'darwin':
    coll_name = appname
    data = os.path.join(dist_dir, '..', appname + '.app', 'Contents', 'Resources')
else:
    coll_name = dist_dir
    data = dist_dir

# Scripts
if sys.platform == 'darwin':
    scripts = get_scripts(excludes=[appname + '-apply-profiles'])
else:
    scripts = get_scripts()

# Analyze ALL scripts at once
excludes = config['excludes']['all'] + config['excludes'][sys.platform]
a = Analysis([os.path.join('scripts', script) for script, desc in scripts],
             pathex=['.'],
             hiddenimports=[],
             hookspath=None,
             excludes=excludes)

# We need a dummy PYZ for our executables otherwise FrozenImporter will fail
dummy = os.path.join(build_dir, 'dummy')
open(dummy, 'wb').close()
compile(dummy, dummy + '.pyc', dfile='dummy')
pyz = PYZ(TOC([('dummy', dummy + '.pyc', 'PYMODULE')]))

if library_zip:
    # Don't use PYZ, instead a regular zipfile
    # will contain all our pure python modules
    lib = 'library.zip'
    libzip = ZipFile(os.path.join(build_dir, lib), 'w', ZIP_DEFLATED)
    for name, py_path, dtype in a.pure:
        py_name, py_ext = os.path.splitext(os.path.basename(py_path))
        if not name.endswith(py_name):
            name += '.' + py_name
        libzip.write(py_path, name.replace('.', '/') + py_ext)
    # We need to add PyInstaller's fake site.py
    libzip.write(os.path.join(HOMEPATH, 'PyInstaller', 'fake', 'fake-site' + py_ext),
                 'site' + py_ext)
    libzip.close()

    # Remove default PYZ dependencies (pyi_ modules are already part of library)
    pyz.dependencies = []
else:
    # Use PYZ
    lib = 'library.pyz'
    PYZ(a.pure, name=os.path.join(build_dir, lib))

    # Remove analyzed scripts from scripts TOC
    # Also remove win32comgenpy runtime hook as we don't use genpy
    global scripts  # Use global otherwise the below filter will result in a
                    # NameError: global name 'scripts' is not defined -- but WHY???
    a.scripts = list(filter(lambda (name, script, dtype):
                       name not in ['pyi_rth_win32comgenpy'] +
                                   [script for script, desc in scripts], a.scripts))

# Bootstrap code which inserts library into sys.path
lib_bootstrap = os.path.join(build_dir, 'lib_bootstrap')
with open(lib_bootstrap, 'wb') as py_file:
    py_file.write('\n'.join(['import sys',
                             'sys.path[:0] = [sys.exec_prefix + "/%s"]' % lib]))

# Generate executables for each of our scripts
# If using library.zip, do NOT use a.scripts except for PYI bootstrap
exes = []
for script, desc in scripts:
    if sys.platform == 'darwin':
        # For Mac OS X we need to add the icon to the bundle
        icon = None
    elif sys.platform == 'win32':
        icon = script2pywname(script) + '.ico'
    else:
        icon = os.path.join('256x256', '%s.png' % script)
    tempver_path = winversion.mktempver(os.path.join('misc', 'winversion.txt'),
                                        script2pywname(script), desc)
    exes += [EXE(pyz,  # Dummy PYZ
                 [('lib_bootstrap', lib_bootstrap, 'PYSOURCE')],  # library bootstrap
                 filter(lambda (name, script, dtype):
                        name == '_pyi_bootstrap', a.scripts) if not pyz.dependencies else a.scripts,  # PYI bootstrap
                 [(script, os.path.join('scripts', script), 'PYSOURCE')],
                 exclude_binaries=1,
                 name=script2pywname(script) + exe_ext,
                 debug=False,
                 strip=sys.platform != 'win32',
                 upx=True,
                 console=False,
                 icon=icon and os.path.join(appname, 'theme', 'icons', icon),
                 version=tempver_path)]
    os.remove(tempver_path)
    os.rmdir(os.path.dirname(tempver_path))

if sys.platform == 'win32':
    # Substitute for python.exe
    # This has very limited functionality - basically just the -c parameter is
    # supported, which is exactly what we need for wexpect.Wtty.startChild
    python = os.path.join(build_dir, 'python')
    with open(python, 'wb') as py:
        py.write('\n'.join(['if __name__ == "__main__":',
                            f'    import {appname}.wexpect',
                            f'    sys.modules["wexpect"] = sys.modules["{appname}.wexpect"]',
                            '    for i, arg in enumerate(sys.argv[1:]):',
                            '        if arg == "-c":',
                            '            exec("".join(sys.argv[i + 2]))']))
    exes += [EXE(pyz,  # Dummy PYZ
                 [('lib_bootstrap', lib_bootstrap, 'PYSOURCE')],  # library bootstrap
                 filter(lambda (name, script, dtype):
                        name == '_pyi_bootstrap', a.scripts) if not pyz.dependencies else a.scripts,  # PYI bootstrap
                 [('python', python, 'PYSOURCE')],
                 exclude_binaries=1,
                 name='python' + exe_ext,
                 debug=False,
                 strip=sys.platform != 'win32',
                 upx=True,
                 console=True,
                 icon=sys.executable)]
    
# Collect executables + dependencies
coll = COLLECT(*exes +
               [a.binaries, a.zipfiles, a.datas,
                [(lib, os.path.join(build_dir, lib), 'DATA')]],
               strip=sys.platform != 'win32',
               upx=True,
               name=coll_name)

# Mac OS X: Create app bundle
if sys.platform == 'darwin':
    iconpth = os.path.join(appname, 'theme', 'icons', appname + '.icns')
    app = BUNDLE(coll,
                 icon=iconpth,
                 info_plist=dict((k, v.encode('UTF-8')) for k, v in plist_dict.items()),
                 name=appname + '.app')

# Collect data
data_files = (get_data('', 'data') + get_data('', 'doc') +
              get_data('', 'package_data', appname) +
              get_data('', 'xtra_package_data', appname, sys.platform))
for dirname, files in data_files:
    for filename in files:
        tgt = os.path.join(data, dirname, os.path.basename(filename))
        if os.path.exists(tgt):
            print 'NOTICE: Skipping already existing', tgt
            continue
        if not os.path.isdir(os.path.dirname(tgt)):
            os.makedirs(os.path.dirname(tgt))
        print 'Copying', filename, '->', tgt
        shutil.copy(filename, tgt)

# Mac OS X: Move app to dist directory
if sys.platform == 'darwin':
    for src, dst in [(os.path.join(dist_dir, '..', appname + '.app'),
                      os.path.join(dist_dir, appname + '.app'))]:
        if os.path.isdir(dst):
            _rmtree(dst)
        os.renames(src, dst)
    create_app_symlinks(dist_dir, scripts)
