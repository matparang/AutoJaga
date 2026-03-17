import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import os

# Set random seed for reproducibility
np.random.seed(42)

# Generate 10,000 samples
n_samples = 10000

# Generate 5 informative features
X_informative = np.random.normal(0, 1, (n_samples, 5))

# Create nonlinear interactions for the target variable
# Base relationship: y = x1^2 + x2*x3 + sin(x4) + x5 + noise
y = (X_informative[:, 0] ** 2) + \
    (X_informative[:, 1] * X_informative[:, 2]) + \
    np.sin(X_informative[:, 3]) + \
    X_informative[:, 4] + \
    np.random.normal(0, 0.1, n_samples)

# Add heteroscedastic noise: variance increases with |x1|
noise_scale = 0.1 + 0.5 * np.abs(X_informative[:, 0])
heteroscedastic_noise = np.random.normal(0, noise_scale)
y += heteroscedastic_noise

# Generate 3 redundant features (linear combinations of informative features)
X_redundant = np.column_stack([
    X_informative[:, 0] + 0.1 * np.random.normal(0, 1, n_samples),
    X_informative[:, 1] + X_informative[:, 2] + 0.1 * np.random.normal(0, 1, n_samples),
    0.5 * X_informative[:, 0] + 0.5 * X_informative[:, 4] + 0.1 * np.random.normal(0, 1, n_samples)
])

# Generate 2 noise features
X_noise = np.random.normal(0, 1, (n_samples, 2))

# Combine all features
X = np.column_stack([X_informative, X_redundant, X_noise])

# Ensure we have exactly 10 features
assert X.shape[1] == 10, f'Expected 10 features, got {X.shape[1]}'

# Create variance-stratified sampling by binning y values
# Sort by y and create bins for stratification
n_bins = 20
y_bins = np.digitize(y, np.quantile(y, np.linspace(0, 1, n_bins + 1)))

# Split with stratification on y bins
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y_bins
)

# Save the dataset
np.savez('data/regression_data.npz', X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test)

# Train baseline LinearRegression model
model = LinearRegression()
model.fit(X_train, y_train)

# Make predictions
y_pred_train = model.predict(X_train)
y_pred_test = model.predict(X_test)

# Calculate metrics
train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
train_r2 = r2_score(y_train, y_pred_train)
test_r2 = r2_score(y_test, y_pred_test)

# Feature importance (coefficient magnitude)
feature_importance = np.abs(model.coef_)

# Save results
results = {
    'train_rmse': train_rmse,
    'test_rmse': test_rmse,
    'train_r2': train_r2,
    'test_r2': test_r2,
    'feature_importance': feature_importance
}

np.savez('data/regression_results.npz', **results)

# Print results
print(f'Train RMSE: {train_rmse:.4f}')
print(f'Test RMSE: {test_rmse:.4f}')
print(f'Train R²: {train_r2:.4f}')
print(f'Test R²: {test_r2:.4f}')
print(f'Feature importance (coeff magnitudes): {feature_importance}')
