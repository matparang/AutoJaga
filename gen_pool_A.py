import secrets
import sys

# Generate 50 cryptographically secure random integers in [-100, 100]
rand = secrets.SystemRandom()
pool = [rand.randint(-100, 100) for _ in range(50)]

# Write to pool_A.txt
with open('pool_A.txt', 'w') as f:
    for num in pool:
        f.write(str(num) + '\n')
