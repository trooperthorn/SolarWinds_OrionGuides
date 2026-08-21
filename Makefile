# Regenerate and verify the extracted SolarWinds schema data.
#
#   make data        fetch the OrionSDK docs and rebuild everything under data/
#   make validate    check every sample query and every ```sql block in the docs
#   make check       validate plus a consistency check of the generated data
#   make clean       remove the fetched OrionSDK checkout
#
# VERSION selects the platform release to document:
#   make data VERSION=2025.4

VERSION ?= 2026.2
SDK_DIR ?= .orionsdk
WORKBOOK ?= reference/SWQL_Examples.xlsx
PYTHON ?= python3

.PHONY: all data docs-reference validate check clean sdk help

help:
	@echo "make data            rebuild data/ from the OrionSDK docs (VERSION=$(VERSION))"
	@echo "make docs-reference  regenerate the generated tables in docs/reference/"
	@echo "make validate        check sample queries and docs code blocks against the schema"
	@echo "make check           validate + verify generated data is internally consistent"
	@echo "make clean           remove $(SDK_DIR)"

# The published schema lives on the gh-pages branch of the OrionSDK repository, which
# is what serves https://solarwinds.github.io/OrionSDK/. A blobless partial clone keeps
# the download to what we actually read.
sdk: $(SDK_DIR)/.fetched

$(SDK_DIR)/.fetched:
	@echo "fetching OrionSDK gh-pages (schema + docs)..."
	@rm -rf $(SDK_DIR)
	@git clone --filter=blob:none --no-checkout --branch gh-pages --depth 1 \
		https://github.com/solarwinds/OrionSDK.git $(SDK_DIR)
	@cd $(SDK_DIR) && git sparse-checkout init --cone \
		&& git sparse-checkout set docs $(VERSION) \
		&& git checkout gh-pages
	@touch $@

data: sdk
	@echo "building schema data for $(VERSION)..."
	@$(PYTHON) tools/build_schema_data.py --source $(SDK_DIR) --version $(VERSION)
	@echo "building reference data..."
	@if [ -f "$(WORKBOOK)" ]; then \
		$(PYTHON) tools/build_reference_data.py \
			--functions-md $(SDK_DIR)/docs/swql-functions/index.md \
			--workbook "$(WORKBOOK)" \
			--schema-index data/schema/$(VERSION)/index.json ; \
	else \
		echo "note: $(WORKBOOK) not present; skipping reference data." ; \
		echo "      Schema data was still rebuilt." ; \
	fi

# The large reference tables are enumerations of the extracted data. Generating them
# keeps a 2067-row entity table from drifting out of step with the schema.
docs-reference:
	@$(PYTHON) tools/build_reference_docs.py --version $(VERSION)

validate:
	@$(PYTHON) tools/validate_swql.py scripts/swql/ --quiet
	@$(PYTHON) tools/validate_swql.py --docs docs --quiet

check: validate
	@$(PYTHON) tools/check_data.py --version $(VERSION)

clean:
	@rm -rf $(SDK_DIR)
