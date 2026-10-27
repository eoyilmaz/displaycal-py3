SHELL:=bash
NUM_CPUS = $(shell nproc ||  grep -c '^processor' /proc/cpuinfo)
SETUP_PY_FLAGS = --use-distutils
VERSION_FILE=$(CURDIR)/DisplayCAL/VERSION
VERSION := $(shell cat $(VERSION_FILE))
VIRTUALENV_DIR:=.venv
SYSTEM_PYTHON?=python3
TARGET_ARCH?=`arch`

all: build FORCE

.PHONY: help
help:
	@echo ""
	@echo "Available targets:"
	@make -qp | grep -o '^[a-z0-9-]\+' | sort

.PHONY: venv
venv:
	@printf "\n\033[36m--- $@: Creating Local virtualenv '$(VIRTUALENV_DIR)' using '`which python`' ---\033[0m\n"
	$(SYSTEM_PYTHON) -m venv $(VIRTUALENV_DIR)

.PHONY: build
build:
	@printf "\n\033[36m--- $@: Building ---\033[0m"
	@printf "\n\033[36m--- $@: Local install into virtualenv '$(VIRTUALENV_DIR)' ---\033[0m";
	@source ./$(VIRTUALENV_DIR)/bin/activate; \
	printf "\n\033[36m--- $@: Using python interpreter '`which python`' ---\033[0m\n"; \
	pip install uv; \
	uv pip install -r requirements.txt -r requirements-dev.txt; \
	uv build;

install:
	@printf "\n\033[36m--- $@: Installing displaycal to virtualenv at '$(VIRTUALENV_DIR)' using '`which python`' ---\033[0m\n"
	source ./$(VIRTUALENV_DIR)/bin/activate; \
	uv pip install ./dist/displaycal-$(VERSION)-*.whl --force-reinstall;

launch:
	@printf "\n\033[36m--- $@: Launching DisplayCAL ---\033[0m\n"
	@source ./$(VIRTUALENV_DIR)/bin/activate; \
	displaycal

clean: FORCE
	@printf "\n\033[36m--- $@: Clean ---\033[0m\n"
	-rm -rf .pytest_cache
	-rm -rf .coverage
	-rm -rf .ruff_cache
	-rm -rf .tox
	-rm -rf $(VIRTUALENV_DIR)
	-rm -rf dist
	-rm -rf build

clean-all: clean
	@printf "\n\033[36m--- $@: Clean All---\033[0m\n"
	-rm -f INSTALLED_FILES
	-rm -f setuptools-*.egg
	-rm -f use-distutils
	-rm -f main.py
	-rm -Rf htmlcov
	-rm .coverage.*
	-rm MANIFEST.in
	-rm -Rf displaycal.egg-info
	-rm -Rf $(VIRTUALENV_DIR)

html:
	./native_build.py readme

py2app:
	@printf "\n\033[36m--- $@: Generating macOS APP ---\033[0m\n"
	@source ./$(VIRTUALENV_DIR)/bin/activate; \
	ACOSX_DEPLOYMENT_TARGE=11.0 ARCHFLAGS="-arch $(TARGET_ARCH)" python native_build.py py2app --arch=$(TARGET_ARCH); \
	for APP_PATH in dist/*/DisplayCAL-*/*.app; do \
		echo "Signing $$APP_PATH..."; \
		find "$$APP_PATH" -type f -name "*.dylib" -exec codesign --remove-signature {} +; \
		find "$$APP_PATH" -type f -name "*.so" -exec codesign --remove-signature {} +; \
		find "$$APP_PATH/Contents" -type f \( -name "*.dylib" -o -name "*.so" \) -exec codesign -s - -f -o linker-signed {} +; \
		codesign --force --deep --options runtime --entitlements misc/entitlements.plist --sign - "$$APP_PATH"; \
	done; \
	build_folder=$(ls dist | grep -i py2app.macosx); \
	xattr -cr "dist/${build_folder}/DisplayCAL-${VERSION}/DisplayCAL.app";

new-release:
	@printf "\n\033[36m--- $@: Generating New Release ---\033[0m\n"
	@if [ ! -d "$(VIRTUALENV_DIR)" ]; then \
		printf "\n\033[31m--- $@: Virtualenv '$(VIRTUALENV_DIR)' not found, run 'make venv' first ---\033[0m\n"; \
		exit 1; \
	fi
	@if [[ ! "$(VERSION)" =~ ^[0-9]+(\.[0-9]+)*$$ ]]; then \
		printf "\n\033[31m--- $@: '$(VERSION)' is a pre-release, use 'make new-prerelease' ---\033[0m\n"; \
		exit 1; \
	fi
	git add $(VERSION_FILE)
	git commit -m "Version $(VERSION)"
	git push
	git checkout main
	git pull
	git merge develop
	git tag $(VERSION)
	git push origin main --tags
	git tag -f nightly
	git push --force origin nightly
	@source ./$(VIRTUALENV_DIR)/bin/activate; \
	printf "\n\033[36m--- $@: Using python interpreter '`which python`' ---\033[0m\n"; \
	uv pip install -r requirements.txt -r requirements-dev.txt; \
	uv build; \
	twine check dist/displaycal-$(VERSION).tar.gz; \
	twine upload dist/displaycal-$(VERSION).tar.gz;

# Tags a release candidate (e.g. 3.10.0rc1) on the current branch, without
# merging into main or moving the nightly tag. The tag triggers the release
# builds, which publish it as a GitHub pre-release.
new-prerelease:
	@printf "\n\033[36m--- $@: Generating New Pre-Release ---\033[0m\n"
	@if [ ! -d "$(VIRTUALENV_DIR)" ]; then \
		printf "\n\033[31m--- $@: Virtualenv '$(VIRTUALENV_DIR)' not found, run 'make venv' first ---\033[0m\n"; \
		exit 1; \
	fi
	@if [[ ! "$(VERSION)" =~ ^[0-9]+(\.[0-9]+)*(a|b|rc)[0-9]+$$ ]]; then \
		printf "\n\033[31m--- $@: '$(VERSION)' is not an alpha, beta or release candidate version (e.g. 3.10.0rc1) ---\033[0m\n"; \
		exit 1; \
	fi
	git add $(VERSION_FILE)
	git commit -m "Version $(VERSION)"
	git push
	git tag $(VERSION)
	git push origin $(VERSION)
	@source ./$(VIRTUALENV_DIR)/bin/activate; \
	printf "\n\033[36m--- $@: Using python interpreter '`which python`' ---\033[0m\n"; \
	uv pip install -r requirements.txt -r requirements-dev.txt; \
	uv build; \
	twine check dist/displaycal-$(VERSION).tar.gz; \
	twine upload dist/displaycal-$(VERSION).tar.gz;

.PHONY: tests
tests:
	@printf "\n\033[36m--- $@: Run Tests ---\033[0m"
	@printf "\n\033[36m--- $@: Using virtualenv at '$(VIRTUALENV_DIR)' ---\033[0m"; \
	source ./$(VIRTUALENV_DIR)/bin/activate; \
	printf "\n\033[36m--- $@: Using python interpreter '`which python`' ---\033[0m\n"; \
	pytest -n auto -W ignore --color=yes --cov-report term --cov-report html --cov=DisplayCAL --durations=50;

# https://www.gnu.org/software/make/manual/html_node/Force-Targets.html
FORCE:
