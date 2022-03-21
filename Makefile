NUM_CPUS = $(shell nproc ||  grep -c '^processor' /proc/cpuinfo)

all: build FORCE

build: FORCE
	python setup.py build -j${NUM_CPUS} --use-distutils

clean: FORCE
	-rm -rf build

dist:
	util/sdist.sh

distclean: clean FORCE
	-rm -f INSTALLED_FILES
	-rm -f setuptools-*.egg
	-rm -f use-distutils

html:
	./setup.py readme

install: build FORCE
	python setup.py install --use-distutils

requirements: requirements.txt requirements-dev.txt
	MAKEFLAGS="-j$(NUM_CORES)" pip install  -r requirements.txt
	MAKEFLAGS="-j$(NUM_CORES)" pip install  -r requirements-dev.txt

uninstall:
	./setup.py uninstall --use-distutils

# https://www.gnu.org/software/make/manual/html_node/Force-Targets.html
FORCE:
