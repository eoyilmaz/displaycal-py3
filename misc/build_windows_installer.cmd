rmdir /s /q dist
C:\Users\eoyil\AppData\Local\Programs\Python\Python311\python.exe -m pip uninstall -y displaycal
C:\Users\eoyil\AppData\Local\Programs\Python\Python311\python.exe -m build
C:\Users\eoyil\AppData\Local\Programs\Python\Python311\python.exe -m pip install --upgrade dist\displaycal-3.9.14-py3-none-any.whl
C:\Users\eoyil\AppData\Local\Programs\Python\Python311\python.exe DisplayCAL\freeze.py
C:\Users\eoyil\AppData\Local\Programs\Python\Python311\python.exe setup.py inno
cd dist
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" DisplayCAL-Setup-py2exe.win-amd64-py3.11.iss
cd ..