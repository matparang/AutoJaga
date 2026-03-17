import statistics

# Read and parse each pool
with open('pool_A.txt', 'r') as f:
    pool_a = [int(line.strip()) for line in f if line.strip()]
with open('pool_B.txt', 'r') as f:
    pool_b = [int(line.strip()) for line in f if line.strip()]
with open('pool_C.txt', 'r') as f:
    pool_c = [int(line.strip()) for line in f if line.strip()]

# Compute stats: mean (2 decimals), median (2 decimals), stdev (2 decimals)
def fmt(x):
    return f'{x:.2f}'

def compute_stats(pool):
    mean_val = statistics.mean(pool)
    median_val = statistics.median(pool)
    stdev_val = statistics.stdev(pool) if len(pool) > 1 else 0.0
    return fmt(mean_val), fmt(median_val), fmt(stdev_val)

a_mean, a_median, a_stdev = compute_stats(pool_a)
b_mean, b_median, b_stdev = compute_stats(pool_b)
c_mean, c_median, c_stdev = compute_stats(pool_c)

# Write stats_report.txt in exact plain-text format
with open('stats_report.txt', 'w') as f:
    f.write(f'Pool A:\nMean: {a_mean}\nMedian: {a_median}\nStdDev: {a_stdev}\n')
    f.write(f'Pool B:\nMean: {b_mean}\nMedian: {b_median}\nStdDev: {b_stdev}\n')
    f.write(f'Pool C:\nMean: {c_mean}\nMedian: {c_median}\nStdDev: {c_stdev}\n')
