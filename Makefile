PYTHON := .venv/bin/python
ORCH   := $(PYTHON) -m tools.orchestrator

.PHONY: impl modify modify-plan spike

impl:
	$(ORCH) implement $(plan)

modify:
ifdef plan
	$(ORCH) modify --plan $(plan)
else
	$(ORCH) modify $(feature) $(change)
endif

modify-plan:
	$(ORCH) modify-plan $(change)

spike:
	$(ORCH) spike
