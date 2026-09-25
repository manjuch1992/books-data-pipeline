# Titanic Analytics Module

This folder contains the Module 2 work for the Titanic dataset and is intentionally kept separate from the Module 1 book-data pipeline.

## Files

- `01_eda.ipynb` — exploratory data analysis and chart generation
- `02_modeling.ipynb` — preprocessing, model training, comparison, and saving the fitted pipeline
- `titanic.csv` — committed offline dataset used as the project fallback
- `charts/` — generated visual diagnostics and model plots
- `outputs/` — aggregated CSV summaries from the analysis
- `models/` — final trained pipeline artifact
- `scripts/run_titanic_analysis.py` — generates EDA reports, plots, and model outputs

## Offline fallback

The repository includes the committed Titanic CSV in this folder so the analysis remains reproducible even without a networked data source.

## Key findings

- Survival is strongly associated with sex and passenger class.
- Age and fare distributions show clear differences between survivors and non-survivors.
- The classifier comparison reports validation metrics for logistic regression and a shallow decision tree.

## Artifact summary

Run `python scripts/run_titanic_analysis.py` from this folder to generate the charts, CSV summaries, and `models/best_titanic_pipeline.joblib`.
