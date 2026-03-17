import random


def generate_pool(filename, count=50):
    with open(filename, 'w') as f:
        for _ in range(count):
            f.write(str(random.randrange(0, 100)) + '\n')


def validate_pool(filename, count=50, min_val=0, max_val=99):
    with open(filename, 'r') as f:
        lines = f.readlines()
    if len(lines) != count:
        raise ValueError(f'{filename} has {len(lines)} lines, expected {count}')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line.isdigit():
            raise ValueError(f'{filename}:{i+1} contains non-digit: {repr(line)}')
        val = int(line)
        if not (min_val <= val <= max_val):
            raise ValueError(f'{filename}:{i+1} value {val} outside [{min_val}, {max_val}]')


# Generate
generate_pool('pool_A.txt')
generate_pool('pool_B.txt')
generate_pool('pool_C.txt')

# Validate
validate_pool('pool_A.txt')
validate_pool('pool_B.txt')
validate_pool('pool_C.txt')

print('All pools generated and validated successfully.')
