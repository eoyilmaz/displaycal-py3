rmdir /s /q dist
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m pip uninstall -y displaycal
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m build
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m pip install --upgrade dist\displaycal-3.9.16-py3-none-any.whl
%LOCALAPPDATA%\Programs\Python\Python311\python.exe DisplayCAL\freeze.py
%LOCALAPPDATA%\Programs\Python\Python311\python.exe setup.py inno
cd dist
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" DisplayCAL-Setup-py2exe.win-amd64-py3.11.iss
cd ..