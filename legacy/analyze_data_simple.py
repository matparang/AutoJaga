import math
import sys

# Given data
x = [1, 2, 3, 4, 5]
y = [2, 4, 8, 16, 32]

print("Data analysis:")
print(f"x = {x}")
print(f"y = {y}")
print()

# Function to calculate RMSE
def calculate_rmse(y_true, y_pred):
    n = len(y_true)
    mse = sum((y_true[i] - y_pred[i])**2 for i in range(n)) / n
    return math.sqrt(mse)

# Function to calculate R²
def calculate_r2(y_true, y_pred):
    n = len(y_true)
    y_mean = sum(y_true) / n
    ss_res = sum((y_true[i] - y_pred[i])**2 for i in range(n))
    ss_tot = sum((y_true[i] - y_mean)**2 for i in range(n))
    if ss_tot == 0:
        return 1.0
    return 1 - (ss_res / ss_tot)

# 1. Linear model: y = mx + b
# Calculate coefficients using least squares formula
n = len(x)
sum_x = sum(x)
sum_y = sum(y)
sum_xy = sum(x[i] * y[i] for i in range(n))
sum_x2 = sum(x[i] * x[i] for i in range(n))

# m = (n*sum_xy - sum_x*sum_y) / (n*sum_x2 - sum_x^2)
# b = (sum_y - m*sum_x) / n
m = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
b = (sum_y - m * sum_x) / n

y_pred_linear = [m * xi + b for xi in x]
rmse_linear = calculate_rmse(y, y_pred_linear)
r2_linear = calculate_r2(y, y_pred_linear)

print("Linear Model:")
print(f"Equation: y = {m:.4f}x + {b:.4f}")
print(f"RMSE: {rmse_linear:.6f}")
print(f"R²: {r2_linear:.6f}")
print()

# 2. Exponential model: y = a * b^x
# Since y = [2,4,8,16,32] = [2^1, 2^2, 2^3, 2^4, 2^5], try y = 2^x
y_pred_exp = [2**xi for xi in x]
rmse_exp = calculate_rmse(y, y_pred_exp)
r2_exp = calculate_r2(y, y_pred_exp)

print("Exponential Model (y = 2^x):")
print(f"RMSE: {rmse_exp:.6f}")
print(f"R²: {r2_exp:.6f}")
print()

# 3. Check if perfect fit
print("Verification of y = 2^x:")
for i in range(len(x)):
    expected = 2**x[i]
    actual = y[i]
    print(f"x={x[i]}: 2^{x[i]} = {expected}, y={actual}, match={expected==actual}")

print()

# 4. Try other models briefly
# Quadratic: y = ax^2 + bx + c (simplified check)
# Using first three points to solve for coefficients
# For x=1,y=2: a + b + c = 2
# For x=2,y=4: 4a + 2b + c = 4
# For x=3,y=8: 9a + 3b + c = 8
# Solving: a=1, b=-1, c=2, so y = x^2 - x + 2
# Check: x=4: 16-4+2=14≠16, x=5:25-5+2=22≠32, so not quadratic

print("Quadratic check (y = x^2 - x + 2):")
y_pred_quad_check = [xi**2 - xi + 2 for xi in x]
print(f"Predictions: {y_pred_quad_check}")
print(f"Actual:      {y}")
rmse_quad_check = calculate_rmse(y, y_pred_quad_check)
r2_quad_check = calculate_r2(y, y_pred_quad_check)
print(f"RMSE: {rmse_quad_check:.6f}, R²: {r2_quad_check:.6f}")
print()

# 5. Power model: y = a*x^b
# Try y = 2*x: [2,4,6,8,10] - no
# Try y = x^2: [1,4,9,16,25] - close but not exact

print("Power model check (y = x^2):")
y_pred_power = [xi**2 for xi in x]
print(f"Predictions: {y_pred_power}")
print(f"Actual:      {y}")
rmse_power = calculate_rmse(y, y_pred_power)
r2_power = calculate_r2(y, y_pred_power)
print(f"RMSE: {rmse_power:.6f}, R²: {r2_power:.6f}")
print()

# Summary
print("Model Comparison:")
print("Model\t\tRMSE\t\tR²")
print("-" * 35)
print(f"Linear\t\t{rmse_linear:.6f}\t{r2_linear:.6f}")
print(f"Exponential (2^x)\t{rmse_exp:.6f}\t{r2_exp:.6f}")
print(f"Quadratic (x^2-x+2)\t{rmse_quad_check:.6f}\t{r2_quad_check:.6f}")
print(f"Power (x^2)\t{rmse_power:.6f}\t{r2_power:.6f}")

print("\nDiscovery Process:")
print("1. Initial observation: y values [2,4,8,16,32] are exactly 2^1, 2^2, 2^3, 2^4, 2^5")
print("2. This suggests the exact relationship is y = 2^x")
print("3. Verification shows perfect match for all 5 points")
print("4. Linear model has high error because exponential growth cannot be captured by a straight line")
print("5. The exponential model y = 2^x gives RMSE = 0 and R² = 1.0, indicating perfect fit")
print("6. Therefore, the best model is the exact exponential model y = 2^x")