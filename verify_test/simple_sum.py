# Simple sum calculation for the 50 numbers
numbers = [
123, 456, 789, 101, 112, 131, 415, 161, 718, 192,
21, 223, 242, 526, 272, 829, 303, 132, 334, 353,
637, 383, 940, 414, 243, 445, 464, 748, 494, 505,
152, 535, 654, 757, 585, 960, 616, 263, 646, 656,
766, 869, 696, 70, 727, 737, 476, 777, 878, 979
]

sum_val = sum(numbers)
count = len(numbers)
mean = sum_val / count

print(f"Sum: {sum_val}")
print(f"Count: {count}")
print(f"Mean: {mean:.2f}")