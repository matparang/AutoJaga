import random
import sys
import math

def mean(nums):
    return sum(nums) / len(nums)

def median(nums):
    s = sorted(nums)
    n = len(s)
    if n % 2 == 0:
        return (s[n//2 - 1] + s[n//2]) / 2
    else:
        return s[n//2]

def std_dev(nums):
    m = mean(nums)
    variance = sum((x - m) ** 2 for x in nums) / len(nums)
    return math.sqrt(variance)

def generate_pool(seed, count=50, low=1, high=1000):
    random.seed(seed)
    return [random.randint(low, high) for _ in range(count)]

def format_stats(pool_name, nums):
    m = mean(nums)
    med = median(nums)
    sd = std_dev(nums)
    return f"Pool {pool_name}:\nMean: {m:.2f}\nMedian: {med:.2f}\nStd Dev: {sd:.2f}"

# Generate pools with distinct seeds
pool_A = generate_pool(42)
pool_B = generate_pool(123)
pool_C = generate_pool(789)

# Write pool files
with open('pool_A.txt', 'w') as f:
    f.write(' '.join(map(str, pool_A)))

with open('pool_B.txt', 'w') as f:
    f.write(' '.join(map(str, pool_B)))

with open('pool_C.txt', 'w') as f:
    f.write(' '.join(map(str, pool_C)))

# Compute and write stats report
stats_lines = [
    format_stats('A', pool_A),
    format_stats('B', pool_B),
    format_stats('C', pool_C)
]

with open('stats_report.txt', 'w') as f:
    f.write('\n\n'.join(stats_lines))

print('All files generated successfully.')
