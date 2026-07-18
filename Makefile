.PHONY: pipeline test evaluate api dashboard
pipeline:
	python -m insightops.pipeline --output data/demo
test:
	pytest
evaluate:
	python -m insightops.evaluation
api:
	uvicorn api.main:app --reload
dashboard:
	streamlit run app/streamlit_app.py

