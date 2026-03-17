import statistics
import json


def get_stats(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    data = [int(line.strip()) for line in lines if line.strip()]
    return {
        "pool": filename.split('_')[1].split('.')[0].upper(),
        "mean": round(statistics.mean(data), 2),
        "median": round(statistics.median(data), 2),
        "std": round(statistics.stdev(data), 2)
    }


# Compute for all three pools
stats = [
    get_stats('pool_A.txt'),
    get_stats('pool_B.txt'),
    get_stats('pool_C.txt')
]

# Write valid JSON array to report
with open('statistics_report.txt', 'w') as f:
    json.dump(stats, f)

print('✅ statistics_report.txt regenerated successfully.')
