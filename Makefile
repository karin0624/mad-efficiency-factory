PYTHON := .venv/bin/python
ORCH   := $(PYTHON) -m tools.orchestrator

.PHONY: impl modify spike

impl:
	$(ORCH) implement $(plan)

modify:
	$(ORCH) modify $(feature) $(change)

spike:
	$(ORCH) spike
