# Regenerate and verify the extracted SolarWinds schema data.
#
#   make data           fetch the OrionSDK docs and rebuild everything under data/
#   make docs-reference regenerate the enumerated tables in docs/reference/
#   make docs-index     regenerate docs/TOC.md and llms-full.txt, and check llms.txt
#   make schema-diff    report what changed between two published versions
#   make validate       check every sample query and every ```sql block in the docs
#   make check          validate plus a consistency check of the generated data
#   make clean          remove the fetched OrionSDK checkout
#
# VERSION selects the platform release to document:
#   make data VERSION=2025.4

VERSION ?= 2026.2
SDK_DIR ?= .orionsdk
WORKBOOK ?= reference/SWQL_Examples.xlsx
PYTHON ?= python3

# schema-diff compares FROM against TO. The older version is extracted into a scratch
# directory rather than checked in, since only the report is worth keeping.
FROM ?= 2026.1
TO ?= $(VERSION)
DIFF_SCRATCH ?= .schema-versions

.PHONY: all data docs-reference docs-index schema-diff test validate check clean sdk help grafana-plugin

help:
	@echo "make data            rebuild data/ from the OrionSDK docs (VERSION=$(VERSION))"
	@echo "make docs-reference  regenerate the generated tables in docs/reference/"
	@echo "make docs-index      regenerate docs/TOC.md and llms-full.txt, and check llms.txt"
	@echo "make test            run the toolchain unit tests"
	@echo "make validate        check sample queries, the Grafana plugin's queries, and docs code blocks"
	@echo "make grafana-plugin  build and test the Grafana data source plugin (needs Go and Node)"
	@echo "make check           tests + queries + data + names + counts + verbs + links"
	@echo "make schema-diff     compare two versions (FROM=2025.4 TO=2026.2)"
	@echo "make clean           remove $(SDK_DIR)"

# The published schema lives on the gh-pages branch of the OrionSDK repository, which
# is what serves https://solarwinds.github.io/OrionSDK/. A blobless partial clone keeps
# the download to what we actually read.
sdk: $(SDK_DIR)/.fetched

$(SDK_DIR)/.fetched:
	@echo "fetching OrionSDK gh-pages (schema + docs)..."
	@rm -rf $(SDK_DIR) $(DIFF_SCRATCH)
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
	@$(PYTHON) tools/build_unverified_index.py
	@$(PYTHON) tools/build_llms_index.py

# The AI-facing indexes: a heading-level table of contents and the whole guide in one
# file, both derived from docs/. llms.txt is written by hand and checked for coverage.
docs-index:
	@$(PYTHON) tools/build_llms_index.py

# Upgrade impact: what changed between two published versions, and which of those changes
# can break code that already works.
#
#   make schema-diff FROM=2025.4 TO=2026.2
schema-diff: sdk
	@echo "extracting $(FROM) for comparison..."
	@cd $(SDK_DIR) && git sparse-checkout set docs $(FROM) $(TO) && git checkout gh-pages
	@$(PYTHON) tools/build_schema_data.py --source $(SDK_DIR) --version $(FROM) --out $(DIFF_SCRATCH) >/dev/null
	@$(PYTHON) tools/diff_schema.py --from $(FROM) --to $(TO) --old-root $(DIFF_SCRATCH) \
		--markdown > docs/reference/schema-changes-$(FROM)-to-$(TO).md
	@$(PYTHON) tools/diff_schema.py --from $(FROM) --to $(TO) --old-root $(DIFF_SCRATCH)
	@echo "wrote docs/reference/schema-changes-$(FROM)-to-$(TO).md"

validate:
	@$(PYTHON) tools/validate_swql.py scripts/ --quiet
	@$(PYTHON) tools/validate_swql.py apps/grafana-swis-datasource/src apps/grafana-swis-datasource/dashboards --quiet
	@$(PYTHON) tools/validate_swql.py --docs docs --quiet

test:
	@$(PYTHON) tools/test_tools.py
	@$(PYTHON) -m unittest discover -s apps/disa-stig-conversion-tool -p "test_*.py"

check: test validate
	@$(PYTHON) tools/check_data.py --version $(VERSION)
	@$(PYTHON) tools/check_entity_references.py --version $(VERSION) --strict
	@$(PYTHON) tools/check_counts.py --version $(VERSION)
	@$(PYTHON) tools/check_signatures.py --version $(VERSION)
	@$(PYTHON) tools/check_examples.py
	@$(PYTHON) tools/check_dashboards.py
	@$(PYTHON) tools/check_api_poller_templates.py
	@$(PYTHON) tools/check_links.py --orphans --check-anchors
	@$(PYTHON) tools/build_llms_index.py --check
	@$(PYTHON) tools/check_gate.py

# The Grafana data source plugin under apps/. Its SWQL is validated by `make validate`
# without either toolchain; this target is the full build the plugin's own README describes.
grafana-plugin:
	@cd apps/grafana-swis-datasource && go vet ./pkg/... && go test ./pkg/...
	@cd apps/grafana-swis-datasource && npm ci --no-audit --no-fund && npm run typecheck && npm run lint && npm run test:ci && npm run build
	@cd apps/grafana-swis-datasource && CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o dist/gpx_swis_linux_amd64 ./pkg
	@echo "plugin built into apps/grafana-swis-datasource/dist/"

clean:
	@rm -rf $(SDK_DIR) $(DIFF_SCRATCH)
