rmdir /s /q dist
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m pip uninstall -y displaycal
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m build
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m pip install --upgrade dist\displaycal-3.9.16-py3-none-any.whl
%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m DisplayCAL