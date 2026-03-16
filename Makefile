PYTHON := .venv/bin/python
ORCH   := $(PYTHON) -m tools.orchestrator

.PHONY: impl modify modify-plan spike

impl:
	$(ORCH) implement $(plan)

modify:
	$(ORCH) modify $(feature) $(change)

modify-plan:
	$(ORCH) modify-plan $(change)

spike:
	$(ORCH) spike
