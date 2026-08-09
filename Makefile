.PHONY: clean clean-build clean-pyc clean-venv lint black typecheck test venv setup-dev run-dev build build-onefile build-clean help

SHELL := /bin/sh
.DEFAULT_GOAL := help

APP_DIR = src
RES_DIR = resources
APP_VERSION := 0.1
APP_NAME := dow2-texture-painter
PYTHON ?= python
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
BUILD_SPEC := texture-painter.spec

test: ## run the complete unittest suite
	$(PYTHON) -m unittest discover -s tests

typecheck: ## type-check the initial core module set
	$(PYTHON) -m mypy src/texture_set.py src/texture_renderer.py src/texture_naming.py src/render_settings.py src/constant.py src/action_state.py src/texture_loading_service.py src/image_process.py src/preview_controller.py src/batch_processing_service.py src/pattern_controller.py src/pattern_exchange.py src/color_pattern_handler.py

venv: ## create the development virtual environment
	$(PYTHON) -m venv $(VENV_DIR)

setup-dev: venv ## install runtime, development, and editable project dependencies
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	$(VENV_PYTHON) -m pip install -r requirements-dev.txt
	$(VENV_PYTHON) -m pip install -e .

run-dev: ## launch the application from an already prepared environment
	$(VENV_PYTHON) -m src.frame_main

build: ## build the one-folder application bundle
	$(VENV_PYTHON) -m PyInstaller --clean --noconfirm $(BUILD_SPEC)

build-onefile: ## build the single-file application executable
	TEXTURE_PAINTER_ONEFILE=1 $(VENV_PYTHON) -m PyInstaller --clean --noconfirm $(BUILD_SPEC)

build-clean: clean-build ## remove all PyInstaller output

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
