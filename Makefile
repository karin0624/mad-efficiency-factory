PYTHON := .venv/bin/python
ORCH   := $(PYTHON) -m tools.orchestrator

.PHONY: impl mod spike

impl:
	$(ORCH) implement $(plan)

mod:
	$(ORCH) modify $(feature) $(change)

spike:
	$(ORCH) spike
