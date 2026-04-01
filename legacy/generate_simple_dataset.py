import numpy as np

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
    X_informative[:, 4]

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

# Simple train/test split (80/20) - since stratification requires sklearn
# We'll use simple random split as fallback
indices = np.random.permutation(n_samples)
train_indices = indices[:int(0.8 * n_samples)]
test_indices = indices[int(0.8 * n_samples):]

X_train = X[train_indices]
X_test = X[test_indices]
y_train = y[train_indices]
y_test = y[test_indices]

# Save the dataset
np.savez('data/regression_data.npz', X_train=X_train, X_test=X_test, y_train=y_train, y_test=y_test)

# Simple linear regression using normal equations
# X_train @ beta = y_train => beta = (X_train.T @ X_train)^(-1) @ X_train.T @ y_train
X_train_centered = X_train - np.mean(X_train, axis=0)
y_train_centered = y_train - np.mean(y_train)

# Calculate coefficients using normal equations
try:
    beta = np.linalg.solve(X_train_centered.T @ X_train_centered, X_train_centered.T @ y_train_centered)
    # Add intercept
    intercept = np.mean(y_train) - np.mean(X_train, axis=0) @ beta
    
    # Make predictions
    y_pred_train = X_train @ beta + intercept
    y_pred_test = X_test @ beta + intercept
    
    # Calculate metrics
    train_rmse = np.sqrt(np.mean((y_train - y_pred_train) ** 2))
    test_rmse = np.sqrt(np.mean((y_test - y_pred_test) ** 2))
    train_r2 = 1 - np.sum((y_train - y_pred_train) ** 2) / np.sum((y_train - np.mean(y_train)) ** 2)
    test_r2 = 1 - np.sum((y_test - y_pred_test) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2)
    
    # Feature importance (coefficient magnitude)
    feature_importance = np.abs(beta)
    
    # Save results
    results = {
        'train_rmse': train_rmse,
        'test_rmse': test_rmse,
        'train_r2': train_r2,
        'test_r2': test_r2,
        'feature_importance': feature_importance,
        'intercept': intercept
    }
    
    np.savez('data/regression_results.npz', **results)
    
    # Print results
    print(f'Train RMSE: {train_rmse:.4f}')
    print(f'Test RMSE: {test_rmse:.4f}')
    print(f'Train R²: {train_r2:.4f}')
    print(f'Test R²: {test_r2:.4f}')
    print(f'Feature importance (coeff magnitudes): {feature_importance}')
    
except np.linalg.LinAlgError:
    print('Matrix inversion failed, using pseudo-inverse')
    beta = np.linalg.pinv(X_train_centered) @ y_train_centered
    intercept = np.mean(y_train) - np.mean(X_train, axis=0) @ beta
    
    y_pred_train = X_train @ beta + intercept
    y_pred_test = X_test @ beta + intercept
    
    train_rmse = np.sqrt(np.mean((y_train - y_pred_train) ** 2))
    test_rmse = np.sqrt(np.mean((y_test - y_pred_test) ** 2))
    train_r2 = 1 - np.sum((y_train - y_pred_train) ** 2) / np.sum((y_train - np.mean(y_train)) ** 2)
    test_r2 = 1 - np.sum((y_test - y_pred_test) ** 2) / np.sum((y_test - np.mean(y_test)) ** 2)
    
    feature_importance = np.abs(beta)
    
    results = {
        'train_rmse': train_rmse,
        'test_rmse': test_rmse,
        'train_r2': train_r2,
        'test_r2': test_r2,
        'feature_importance': feature_importance,
        'intercept': intercept
    }
    
    np.savez('data/regression_results.npz', **results)
    
    print(f'Train RMSE: {train_rmse:.4f}')
    print(f'Test RMSE: {test_rmse:.4f}')
    print(f'Train R²: {train_r2:.4f}')
    print(f'Test R²: {test_r2:.4f}')
    print(f'Feature importance (coeff magnitudes): {feature_importance}')
