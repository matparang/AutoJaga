import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import PolynomialFeatures
import warnings
warnings.filterwarnings('ignore')

# Given data
x = np.array([1, 2, 3, 4, 5]).reshape(-1, 1)
y = np.array([2, 4, 8, 16, 32])

print("Data analysis:")
print(f"x = {x.flatten()}")
print(f"y = {y}")
print()

# 1. Fit linear model
linear_model = LinearRegression()
linear_model.fit(x, y)
y_pred_linear = linear_model.predict(x)

# Calculate metrics for linear model
rmse_linear = np.sqrt(mean_squared_error(y, y_pred_linear))
r2_linear = r2_score(y, y_pred_linear)

print("Linear Model:")
print(f"Equation: y = {linear_model.coef_[0]:.3f}x + {linear_model.intercept_:.3f}")
print(f"RMSE: {rmse_linear:.4f}")
print(f"R²: {r2_linear:.4f}")
print()

# 2. Try exponential model: y = a * b^x
# Take log of y to linearize: log(y) = log(a) + x*log(b)
log_y = np.log(y)
exp_model = LinearRegression()
exp_model.fit(x, log_y)
log_y_pred = exp_model.predict(x)
y_pred_exp = np.exp(log_y_pred)

# Calculate metrics for exponential model
rmse_exp = np.sqrt(mean_squared_error(y, y_pred_exp))
r2_exp = r2_score(y, y_pred_exp)

print("Exponential Model (y = a * b^x):")
print(f"log(y) = {exp_model.intercept_:.3f} + {exp_model.coef_[0]:.3f} * x")
print(f"So y = {np.exp(exp_model.intercept_):.3f} * {np.exp(exp_model.coef_[0]):.3f}^x")
print(f"RMSE: {rmse_exp:.4f}")
print(f"R²: {r2_exp:.4f}")
print()

# 3. Try quadratic model
poly_features = PolynomialFeatures(degree=2)
x_poly = poly_features.fit_transform(x)
quad_model = LinearRegression()
quad_model.fit(x_poly, y)
y_pred_quad = quad_model.predict(x_poly)

rmse_quad = np.sqrt(mean_squared_error(y, y_pred_quad))
r2_quad = r2_score(y, y_pred_quad)

print("Quadratic Model:")
print(f"Coefficients: {quad_model.coef_}")
print(f"Intercept: {quad_model.intercept_:.3f}")
print(f"RMSE: {rmse_quad:.4f}")
print(f"R²: {r2_quad:.4f}")
print()

# 4. Try power model: y = a * x^b
# Take log of both sides: log(y) = log(a) + b*log(x)
log_x = np.log(x.flatten())
power_model = LinearRegression()
power_model.fit(log_x.reshape(-1, 1), log_y)
log_y_pred_power = power_model.predict(log_x.reshape(-1, 1))
y_pred_power = np.exp(log_y_pred_power)

rmse_power = np.sqrt(mean_squared_error(y, y_pred_power))
r2_power = r2_score(y, y_pred_power)

print("Power Model (y = a * x^b):")
print(f"log(y) = {power_model.intercept_:.3f} + {power_model.coef_[0]:.3f} * log(x)")
print(f"So y = {np.exp(power_model.intercept_):.3f} * x^{power_model.coef_[0]:.3f}")
print(f"RMSE: {rmse_power:.4f}")
print(f"R²: {r2_power:.4f}")
print()

# 5. Check if it's exactly y = 2^x
y_exact = 2**x.flatten()
rmse_exact = np.sqrt(mean_squared_error(y, y_exact))
r2_exact = r2_score(y, y_exact)

print("Exact exponential model y = 2^x:")
print(f"RMSE: {rmse_exact:.4f}")
print(f"R²: {r2_exact:.4f}")
print()

# Summary comparison
models = [
    ('Linear', rmse_linear, r2_linear),
    ('Exponential', rmse_exp, r2_exp),
    ('Quadratic', rmse_quad, r2_quad),
    ('Power', rmse_power, r2_power),
    ('Exact 2^x', rmse_exact, r2_exact)
]

print("Model Comparison:")
print("Model\t\tRMSE\t\tR²")
print("-" * 40)
for name, rmse, r2 in models:
    print(f"{name}\t\t{rmse:.6f}\t{r2:.6f}")

# Create visualization
plt.figure(figsize=(12, 8))

# Plot original data
plt.scatter(x, y, color='red', s=100, label='Original data', zorder=5)

# Plot predictions
x_plot = np.linspace(0.5, 5.5, 100).reshape(-1, 1)
y_plot_linear = linear_model.predict(x_plot)
y_plot_exp = np.exp(exp_model.predict(x_plot))
y_plot_quad = quad_model.predict(poly_features.transform(x_plot))
y_plot_power = np.exp(power_model.predict(np.log(x_plot).reshape(-1, 1)))
y_plot_exact = 2**x_plot.flatten()

plt.plot(x_plot, y_plot_linear, 'b--', label=f'Linear (R²={r2_linear:.4f})')
plt.plot(x_plot, y_plot_exp, 'g-.', label=f'Exp (R²={r2_exp:.4f})')
plt.plot(x_plot, y_plot_quad, 'm:', label=f'Quad (R²={r2_quad:.4f})')
plt.plot(x_plot, y_plot_power, 'c-', label=f'Power (R²={r2_power:.4f})')
plt.plot(x_plot, y_plot_exact, 'k-', label=f'Exact 2^x (R²={r2_exact:.4f})')

plt.xlabel('x')
plt.ylabel('y')
plt.title('Model Comparisons')
plt.legend()
plt.grid(True)
plt.savefig('model_comparison.png')
plt.show()

# Print detailed analysis
print("\nDiscovery Process Analysis:")
print("1. Initial observation: y values [2,4,8,16,32] are powers of 2: 2^1, 2^2, 2^3, 2^4, 2^5")
print("2. This suggests an exponential relationship y = 2^x")
print("3. Linear model will perform poorly because exponential growth cannot be captured by a straight line")
print("4. Exponential transformation (log(y) vs x) should give perfect linear relationship")
print("5. Verification: log2(y) = [1,2,3,4,5] which equals x exactly")
print("6. Therefore, the exact model is y = 2^x with R² = 1.0 and RMSE = 0")