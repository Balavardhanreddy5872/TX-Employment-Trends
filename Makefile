PY := .venv/bin/python

.PHONY: setup data clean db analyze viz report all test
setup:      ## create venv and install pinned dependencies
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
data:       ## download LODES8 + TIGER files (~450 MB)
	$(PY) -m src.download_data
clean:      ## clean/validate raw files -> data/interim/*.parquet + data-quality report
	$(PY) -m src.clean
db:         ## build the SQLite star schema
	$(PY) -m src.build_db
analyze:    ## run sql/*.sql and export outputs/tables/*.csv
	$(PY) -m src.run_sql
viz:        ## charts, choropleths and the interactive map
	$(PY) -m src.visualize
notebooks:  ## execute the notebooks in place
	$(PY) -m src.make_notebooks
test:
	$(PY) -m pytest -q
all: data clean db analyze viz test
