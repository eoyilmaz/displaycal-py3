SHELL:=bash
NUM_CPUS = $(shell nproc ||  grep -c '^processor' /proc/cpuinfo)
SETUP_PY_FLAGS = --use-distutils
VERSION := $(shell cat VERSION_BASE)
VERSION_FILE=$(CURDIR)/VERSION_BASE
VIRTUALENV_DIR:=.venv
SYSTEM_PYTHON:=python3

all: build FORCE

.PHONY: help
help:
	@echo ""
	@echo "Available targets:"
	@make -qp | grep -o '^[a-z0-9-]\+' | sort

.PHONY: venv
venv:
	$(SYSTEM_PYTHON) -m venv $(VIRTUALENV_DIR); \
	source ./$(VIRTUALENV_DIR)/bin/activate; \
	pip install -r requirements.txt; \
	pip install -r requirements-dev.txt;

build: venv FORCE
	source ./$(VIRTUALENV_DIR)/bin/activate; \
	python3 -m build;

install:
	source ./$(VIRTUALENV_DIR)/bin/activate; \
	pip install ./dist/DisplayCAL-$(VERSION)-*.whl --force-reinstall;

launch:
	source ./.venv/bin/activate; \
	displaycal

clean: FORCE
	-rm -rf .pytest_cache
	-rm -rf .venv
	-rm -rf dist
	-rm -rf build

clean-all: clean
	-rm -f INSTALLED_FILES
	-rm -f setuptools-*.egg
	-rm -f use-distutils
	-rm -rf dist
	-rm MANIFEST.in
	-rm VERSION
	-rm -Rf DisplayCAL.egg-info
	-rm DisplayCAL/__version__.py
	-rm -Rf $(VIRTUALENV_DIR)

html:
	./setup.py readme

new-release:
	git add $(VERSION_FILE)
	git commit -m "Version $(VERSION)"
	git push
	git checkout main
	git pull
	git merge develop
	git tag $(VERSION)
	git push origin main --tags
	python3 -m build
# 	twine check dist/DisplayCAL-$(VERSION).whl
	twine check dist/DisplayCAL-$(VERSION).tar.gz
# 	twine upload dist/DisplayCAL-$(VERSION).whl
	twine upload dist/DisplayCAL-$(VERSION).tar.gz

tests: venv build install
	source $(VIRTUALENV_DIR)/bin/activate; \
	pytest -v -n auto -W ignore --color=yes --cov-report term;

# https://www.gnu.org/software/make/manual/html_node/Force-Targets.html
FORCE:
