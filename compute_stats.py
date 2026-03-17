import sys
import numpy as np

def stats_from_file(filename):
    with open(filename, 'r') as f:
        data = [int(line.strip()) for line in f if line.strip()]
    arr = np.array(data)
    return {
        'filename': filename,
        'count': len(arr),
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std': float(np.std(arr, ddof=1))
    }

if __name__ == '__main__':
    files = ['pool_A.txt', 'pool_B.txt', 'pool_C.txt']
    results = [stats_from_file(f) for f in files]
    print('| Pool | Count | Mean | Median | Std Dev |')
    print('|------|-------|------|--------|---------|')
    for r in results:
        print(f'| {r["filename"]} | {r["count"]} | {r["mean"]:.2f} | {r["median"]:.0f} | {r["std"]:.2f} |')
