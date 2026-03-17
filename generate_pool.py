import secrets
import sys

def main(pool_name):
    # Generate 50 cryptographically secure random integers in [-100, 100]
    rng = secrets.SystemRandom()
    numbers = [rng.randint(-100, 100) for _ in range(50)]
    
    # Write to corresponding file
    filename = f'pool_{pool_name}.txt'
    with open(filename, 'w') as f:
        for num in numbers:
            f.write(f'{num}\n')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python generate_pool.py <A|B|C>')
        sys.exit(1)
    main(sys.argv[1])
