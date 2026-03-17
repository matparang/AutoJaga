import sys

# Read numbers from data.txt
with open('verify_test/data.txt', 'r') as f:
    numbers = [float(line.strip()) for line in f if line.strip()]

# Calculate mean
mean = sum(numbers) / len(numbers) if numbers else 0
print(f'Mean = {mean:.2f}')
