import sys

# Read numbers from data.txt
try:
    with open('verify_test/data.txt', 'r') as f:
        numbers = [float(line.strip()) for line in f if line.strip()]
    
    # Calculate mean
    if numbers:
        mean = sum(numbers) / len(numbers)
        print(f'Mean = {mean:.2f}')
        # Also write to file
        with open('verify_test/real_mean.txt', 'w') as f:
            f.write(f'{mean:.2f}')
    else:
        print('Mean = 0.00')
        with open('verify_test/real_mean.txt', 'w') as f:
            f.write('0.00')
except Exception as e:
    print(f'Error: {e}')
