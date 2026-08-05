.PHONY: clean clean-build clean-pyc clean-venv lint black test venv setup-dev run-dev help

SHELL := /bin/sh
.DEFAULT_GOAL := help

APP_DIR = src
RES_DIR = resources
APP_VERSION := 0.1
APP_NAME := dow2-texture-painter
PYTHON ?= python
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python

test: ## run the complete unittest suite
	$(PYTHON) -m unittest discover -s tests

venv: ## create the development virtual environment
	$(PYTHON) -m venv $(VENV_DIR)

setup-dev: venv ## install runtime, development, and editable project dependencies
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt
	$(VENV_PYTHON) -m pip install -e .

run-dev: ## launch the application from an already prepared environment
	$(VENV_PYTHON) -m src.frame_main

# On windows, use ";" separator instead of ":" for the --add-data args
# --icon option isn't working alongisde --name option
build-bin-folder-win: ## build binary folder for windows
	pyinstaller --name $(APP_NAME)-$(APP_VERSION) --windowed --noconfirm  \
	--add-data "$(APP_DIR)/$(RES_DIR);$(APP_DIR)/$(RES_DIR)" \
	--icon="$(APP_DIR)/$(RES_DIR)/icon_64x64.ico" \
	--add-data "readme.md;." --hidden-import='PIL._tkinter_finder' \
	$(APP_DIR)/frame_main.py

build-bin-file-win: ## build single-file binary for windows
	pyinstaller --name $(APP_NAME)-$(APP_VERSION) --onefile --windowed \
	--noconfirm --add-data "$(APP_DIR)/$(RES_DIR);$(APP_DIR)/$(RES_DIR)" \
	--icon="$(APP_DIR)/$(RES_DIR)/icon_64x64.ico" \
	--hidden-import='PIL._tkinter_finder' $(APP_DIR)/frame_main.py

build-bin-folder: ## build binary folder
	pyinstaller --name $(APP_NAME)-$(APP_VERSION) --windowed --noconfirm \
	--add-data "$(APP_DIR)/$(RES_DIR):$(APP_DIR)/$(RES_DIR)" \
	--icon="$(APP_DIR)/$(RES_DIR)/icon_64x64.ico" \
	--hidden-import='PIL._tkinter_finder' $(APP_DIR)/frame_main.py

build-bin-file: ## build binary
	pyinstaller --name $(APP_NAME)-$(APP_VERSION) --onefile --windowed \
	--noconfirm --add-data "$(APP_DIR)/$(RES_DIR):$(APP_DIR)/$(RES_DIR)" \
	--hidden-import='PIL._tkinter_finder' $(APP_DIR)/frame_main.py

# build-spec:
# 	docker run -v "$(pwd):/src/" cdrx/pyinstaller-linux "pyinstaller --onefile --windowed --noconfirm --add-data '$(APP_DIR)/data:data' --hidden-import='PIL._tkinter_finder' src/frame_main.py"

clean: clean-build clean-pyc ## remove all build, test, coverage and Python artifacts

clean-venv:
	rm -rf $(VENV_DIR)

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -fr {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

lint: ## check style with flake8
	flake8 $(APP_DIR)

black: ## Apply Black autoformatting style
	black $(APP_DIR) --line-length 79
