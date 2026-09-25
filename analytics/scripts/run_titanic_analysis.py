from pathlib import Path

import joblib
import pandas as pd
from PIL import Image, ImageDraw
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).absolute().parent.parent
DATA = ROOT / 'titanic.csv'
OUTPUT = ROOT / 'outputs'
CHARTS = ROOT / 'charts'
MODELS = ROOT / 'models'


def save_chart(path, title, values):
    image = Image.new('RGB', (640, 360), 'white')
    draw = ImageDraw.Draw(image)
    margin, bottom = 30, 330
    max_value = max(values, default=1) or 1
    step = (640 - 2 * margin) / max(len(values), 1)
    draw.text((margin, 10), title, fill='black')
    for index, value in enumerate(values):
        x0 = margin + index * step + 5
        x1 = margin + (index + 1) * step - 5
        y1 = bottom - float(value) / max_value * 270
        draw.rectangle((x0, y1, x1, bottom), fill=(44, 118, 170))
    image.save(path)


def save_boxplot(path, title, groups):
    image = Image.new('RGB', (640, 360), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((30, 10), title, fill='black')
    low, high = min(min(values) for values in groups), max(max(values) for values in groups)
    spread = high - low or 1
    for index, values in enumerate(groups):
        values = sorted(values)
        quantile = lambda fraction: values[int((len(values) - 1) * fraction)]
        x = 190 + index * 250
        y = lambda value: 320 - (value - low) / spread * 270
        draw.line((x, y(values[0]), x, y(values[-1])), fill=(30, 30, 30), width=2)
        draw.rectangle((x - 45, y(quantile(0.75)), x + 45, y(quantile(0.25))), outline=(44, 118, 170), width=3)
        draw.line((x - 45, y(quantile(0.5)), x + 45, y(quantile(0.5))), fill=(190, 65, 45), width=3)
        draw.text((x - 10, 330), str(index), fill='black')
    image.save(path)


def save_heatmap(path, matrix):
    size = 560
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    cell = size / len(matrix)
    for row in range(len(matrix)):
        for column in range(len(matrix)):
            value = max(-1.0, min(1.0, float(matrix.iloc[row, column])))
            if value < 0:
                color = (int(255 * (1 + value)), int(255 * (1 + value)), 255)
            else:
                color = (255, int(255 * (1 - value)), int(255 * (1 - value)))
            draw.rectangle((column * cell, row * cell, (column + 1) * cell, (row + 1) * cell), fill=color)
    image.save(path)


def save_roc_chart(path, curves):
    image = Image.new('RGB', (640, 360), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((30, 10), 'ROC Curves', fill='black')
    draw.line((40, 320, 600, 40), fill=(170, 170, 170), width=2)
    for color, (false_positive, true_positive) in zip(((44, 118, 170), (190, 65, 45)), curves):
        points = [(40 + x * 560, 320 - y * 280) for x, y in zip(false_positive, true_positive)]
        if len(points) > 1:
            draw.line(points, fill=color, width=3)
    image.save(path)


def main():
    for folder in (OUTPUT, CHARTS, MODELS):
        folder.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(DATA)
    data.isna().sum().rename_axis('column').reset_index(name='missing_values').to_csv(OUTPUT / 'missing_values.csv', index=False)
    survival_by_sex = data.groupby('sex')['survived'].mean()
    survival_by_sex.rename('survival_rate').reset_index().to_csv(OUTPUT / 'survival_rates.csv', index=False)
    correlation = data.select_dtypes(include='number').corr()
    correlation.to_csv(OUTPUT / 'correlation_matrix.csv')

    age_bins = pd.cut(data['age'].dropna(), bins=10).value_counts().sort_index().tolist()
    fare_bins = pd.cut(data['fare'].dropna(), bins=10).value_counts().sort_index().tolist()
    save_chart(CHARTS / 'age_histogram.png', 'Age Distribution', age_bins)
    save_chart(CHARTS / 'fare_histogram.png', 'Fare Distribution', fare_bins)
    save_chart(CHARTS / 'survival_by_sex.png', 'Survival Rate by Sex', survival_by_sex.tolist())
    save_chart(CHARTS / 'survival_by_pclass.png', 'Survival Rate by Class', data.groupby('pclass')['survived'].mean().tolist())
    save_heatmap(CHARTS / 'correlation_heatmap.png', correlation.fillna(0))
    save_chart(CHARTS / 'survival_by_sex_pclass.png', 'Survival by Sex and Class', data.groupby(['sex', 'pclass'])['survived'].mean().tolist())
    save_boxplot(CHARTS / 'age_boxplot.png', 'Age by Survival', [data.loc[data['survived'] == label, 'age'].dropna().tolist() for label in (0, 1)])
    save_boxplot(CHARTS / 'fare_boxplot.png', 'Fare by Survival', [data.loc[data['survived'] == label, 'fare'].dropna().tolist() for label in (0, 1)])

    X = data.drop(columns=['survived', 'alive'])
    y = data['survived']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    categorical = X.select_dtypes(include='object').columns.tolist()
    numeric = X.select_dtypes(exclude='object').columns.tolist()
    preprocessing = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), numeric),
        ('categorical', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), categorical),
    ])
    candidates = {
        'logistic_regression': LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42),
        'decision_tree': DecisionTreeClassifier(max_depth=4, random_state=42),
    }
    rows, fitted, curves = [], {}, []
    for name, estimator in candidates.items():
        pipeline = Pipeline([('preprocess', preprocessing), ('model', estimator)])
        pipeline.fit(X_train, y_train)
        fitted[name] = pipeline
        predicted = pipeline.predict(X_test)
        probabilities = pipeline.predict_proba(X_test)[:, 1]
        rows.append({
            'model': name,
            'accuracy': accuracy_score(y_test, predicted),
            'precision': precision_score(y_test, predicted, zero_division=0),
            'recall': recall_score(y_test, predicted, zero_division=0),
            'f1': f1_score(y_test, predicted, zero_division=0),
            'roc_auc': roc_auc_score(y_test, probabilities),
        })
        curves.append(roc_curve(y_test, probabilities)[:2])

    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUTPUT / 'classification_metrics.csv', index=False)
    best_name = metrics.sort_values('f1', ascending=False).iloc[0]['model']
    metrics.assign(selected=metrics['model'] == best_name).to_csv(OUTPUT / 'model_comparison.csv', index=False)
    joblib.dump(fitted[best_name], MODELS / 'best_titanic_pipeline.joblib')
    pd.DataFrame({'actual': y_train.value_counts().sort_index(), 'proportion': y_train.value_counts(normalize=True).sort_index()}).to_csv(OUTPUT / 'imbalance_comparison.csv')
    save_roc_chart(CHARTS / 'roc_curves.png', curves)
    tree = fitted['decision_tree'].named_steps['model']
    feature_names = fitted['decision_tree'].named_steps['preprocess'].get_feature_names_out()
    important = sorted(zip(feature_names, tree.feature_importances_), key=lambda item: item[1], reverse=True)[:10]
    save_chart(CHARTS / 'decision_tree.png', 'Decision Tree Feature Importance', [value for _, value in important])

    regression_data = data[['age', 'fare', 'pclass', 'sex']].dropna().copy()
    regression_data['sex'] = (regression_data['sex'] == 'female').astype(int)
    regression_X = regression_data[['age', 'pclass', 'sex']]
    regression_y = regression_data['fare']
    regression = LinearRegression().fit(regression_X, regression_y)
    residuals = regression_y - regression.predict(regression_X)
    pd.DataFrame([{'model': 'linear_regression', 'mse': (residuals ** 2).mean(), 'r2': regression.score(regression_X, regression_y)}]).to_csv(OUTPUT / 'regression_metrics.csv', index=False)
    save_chart(CHARTS / 'regression_residuals.png', 'Regression Residuals', residuals.abs().round().value_counts().sort_index().iloc[:10].tolist())
    print(metrics.to_string(index=False))
    print(f'Artifacts saved under {ROOT}')


if __name__ == '__main__':
    main()
