import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import os
import sys

# Set random seed for reproducibility
np.random.seed(42)

# Generate synthetic regression dataset with n=10000
n_samples = 10000

# Generate 10 features
# 5 informative features
X_informative = np.random.normal(0, 1, (n_samples, 5))

# 3 redundant features (linear combinations of informative features)
X_redundant = np.zeros((n_samples, 3))
X_redundant[:, 0] = 0.5 * X_informative[:, 0] + 0.3 * X_informative[:, 1] + np.random.normal(0, 0.1, n_samples)
X_redundant[:, 1] = 0.4 * X_informative[:, 2] + 0.6 * X_informative[:, 3] + np.random.normal(0, 0.1, n_samples)
X_redundant[:, 2] = 0.7 * X_informative[:, 1] + 0.2 * X_informative[:, 4] + np.random.normal(0, 0.1, n_samples)

# 2 noise features
X_noise = np.random.normal(0, 1, (n_samples, 2))

# Combine all features
X = np.hstack([X_informative, X_redundant, X_noise])

# Create target variable with nonlinear interactions and heteroscedastic noise
# Base relationship with nonlinear terms
y_base = (
    2.0 * X_informative[:, 0] + 
    1.5 * X_informative[:, 1]**2 + 
    3.0 * np.sin(X_informative[:, 2]) + 
    2.5 * X_informative[:, 3] * X_informative[:, 4] + 
    1.0 * np.exp(-0.5 * X_informative[:, 0]**2)
)

# Heteroscedastic noise: variance depends on some features
# Higher variance when |X_informative[:, 0]| is large
noise_std = 0.5 + 1.0 * np.abs(X_informative[:, 0]) + 0.5 * X_informative[:, 1]**2
noise = np.random.normal(0, noise_std)

# Add the noise to create final target
y = y_base + noise

# Create variance-stratified sampling for train/test split
# First, compute variance of y in different bins
# For stratification, we'll use quantiles of y to ensure similar variance distribution
# Since heteroscedastic, we'll stratify by the magnitude of the heteroscedastic component
stratify_var = noise_std  # This captures the heteroscedastic pattern

# Create stratification bins
n_bins = 10
stratify_labels = np.digitize(stratify_var, np.quantile(stratify_var, np.linspace(0, 1, n_bins+1)))

# Split with stratification
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.2, 
    random_state=42,
    stratify=stratify_labels
)

# Save the dataset
np.savez('data/regression_data.npz', 
         X_train=X_train, X_test=X_test, 
         y_train=y_train, y_test=y_test,
         X_informative=X_informative, X_redundant=X_redundant, X_noise=X_noise)

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
feature_names = [f'feature_{i}' for i in range(X.shape[1])]

# Print results
print('=== REGRESSION DATASET GENERATION COMPLETE ===')
print(f'Dataset shape: {X.shape}')
print(f'Train set size: {X_train.shape[0]}')
print(f'Test set size: {X_test.shape[0]}')
print(f'Informative features: 5')
print(f'Redundant features: 3')
print(f'Noise features: 2')
print('\n=== BASELINE LINEAR REGRESSION RESULTS ===')
print(f'Train RMSE: {train_rmse:.4f}')
print(f'Test RMSE: {test_rmse:.4f}')
print(f'Train R²: {train_r2:.4f}')
print(f'Test R²: {test_r2:.4f}')
print('\n=== FEATURE IMPORTANCE (|coefficient|) ===')
for i, (name, imp) in enumerate(zip(feature_names, feature_importance)):
    print(f'{name}: {imp:.4f}')

# Save results to file
with open('regression_results.txt', 'w') as f:
    f.write('=== REGRESSION DATASET GENERATION COMPLETE ===\n')
    f.write(f'Dataset shape: {X.shape}\n')
    f.write(f'Train set size: {X_train.shape[0]}\n')
    f.write(f'Test set size: {X_test.shape[0]}\n')
    f.write(f'Informative features: 5\n')
    f.write(f'Redundant features: 3\n')
    f.write(f'Noise features: 2\n\n')
    f.write('=== BASELINE LINEAR REGRESSION RESULTS ===\n')
    f.write(f'Train RMSE: {train_rmse:.4f}\n')
    f.write(f'Test RMSE: {test_rmse:.4f}\n')
    f.write(f'Train R²: {train_r2:.4f}\n')
    f.write(f'Test R²: {test_r2:.4f}\n\n')
    f.write('=== FEATURE IMPORTANCE (|coefficient|) ===\n')
    for i, (name, imp) in enumerate(zip(feature_names, feature_importance)):
        f.write(f'{name}: {imp:.4f}\n')

print('\nResults saved to regression_results.txt')
print('Dataset saved to data/regression_data.npz')
