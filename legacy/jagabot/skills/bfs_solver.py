from collections import deque
import json

def solve_8_puzzle(initial_state, goal_state):
    """
    Solve 8-puzzle using BFS
    State is represented as a tuple of 9 integers (0-8), where 0 is empty space
    """
    if initial_state == goal_state:
        return []
    
    # Convert to string for dictionary keys
    def state_to_str(state):
        return ''.join(map(str, state))
    
    def str_to_state(s):
        return tuple(int(c) for c in s)
    
    # Get possible moves
    def get_neighbors(state):
        neighbors = []
        state_list = list(state)
        zero_idx = state_list.index(0)
        
        # Possible moves: up, down, left, right
        moves = []
        if zero_idx >= 3:  # can move up
            moves.append(zero_idx - 3)
        if zero_idx < 6:   # can move down
            moves.append(zero_idx + 3)
        if zero_idx % 3 != 0:  # can move left
            moves.append(zero_idx - 1)
        if zero_idx % 3 != 2:  # can move right
            moves.append(zero_idx + 1)
        
        for new_idx in moves:
            new_state = state_list[:]
            new_state[zero_idx], new_state[new_idx] = new_state[new_idx], new_state[zero_idx]
            neighbors.append(tuple(new_state))
        
        return neighbors
    
    # BFS
    queue = deque([(initial_state, [])])
    visited = {state_to_str(initial_state)}
    
    while queue:
        current_state, path = queue.popleft()
        
        for neighbor in get_neighbors(current_state):
            neighbor_str = state_to_str(neighbor)
            if neighbor_str not in visited:
                new_path = path + [neighbor]
                if neighbor == goal_state:
                    return new_path
                visited.add(neighbor_str)
                queue.append((neighbor, new_path))
    
    return None  # No solution

# Test function
def test_bfs():
    # Simple test case
    initial = (1, 2, 3, 4, 0, 5, 6, 7, 8)
    goal = (1, 2, 3, 4, 5, 6, 7, 8, 0)
    solution = solve_8_puzzle(initial, goal)
    print(f"Solution length: {len(solution) if solution else 'No solution'}")
    return solution

if __name__ == "__main__":
    test_bfs()
