from typing import List, Optional, Tuple
from common import PuzzleState, Direction, DIRECTION_DELTA, OPPOSITE_DIRECTION, get_goal_state

def manhattan_distance(state: PuzzleState) -> int:
    size = state.size
    distance = 0
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            if val != 0:
                goal_i = (val - 1) // size
                goal_j = (val - 1) % size
                distance += abs(i - goal_i) + abs(j - goal_j)
    return distance

def linear_conflict(state: PuzzleState) -> int:
    size = state.size
    conflict = 0
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            goal_i = (val - 1) // size
            if goal_i != i:
                continue
            for k in range(j + 1, size):
                other = state.board[i][k]
                if other == 0:
                    continue
                other_goal_i = (other - 1) // size
                if other_goal_i != i:
                    continue
                goal_j = (val - 1) % size
                other_goal_j = (other - 1) % size
                if goal_j > other_goal_j:
                    conflict += 2
    for j in range(size):
        for i in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            goal_j = (val - 1) % size
            if goal_j != j:
                continue
            for k in range(i + 1, size):
                other = state.board[k][j]
                if other == 0:
                    continue
                other_goal_j = (other - 1) % size
                if other_goal_j != j:
                    continue
                goal_i = (val - 1) // size
                other_goal_i = (other - 1) // size
                if goal_i > other_goal_i:
                    conflict += 2
    return manhattan_distance(state) + conflict

class IDAStar:

    def __init__(self, use_linear_conflict: bool=True):
        self.heuristic = linear_conflict if use_linear_conflict else manhattan_distance
        self.nodes_expanded = 0

    def solve(self, initial_state: PuzzleState, max_depth: int=80) -> Optional[List[Direction]]:
        if initial_state.is_goal():
            return []
        self.nodes_expanded = 0
        threshold = self.heuristic(initial_state)
        path = []
        while threshold <= max_depth:
            result = self._search(initial_state, 0, threshold, path, None)
            if isinstance(result, list):
                return result
            if result == float('inf'):
                return None
            threshold = result
        return None

    def _search(self, state: PuzzleState, g: int, threshold: int, path: List[Direction], last_move: Optional[Direction]) -> any:
        self.nodes_expanded += 1
        f = g + self.heuristic(state)
        if f > threshold:
            return f
        if state.is_goal():
            return path[:]
        min_threshold = float('inf')
        for direction in state.get_valid_moves():
            if last_move is not None and direction == OPPOSITE_DIRECTION[last_move]:
                continue
            new_state = state.copy()
            new_state.move(direction)
            path.append(direction)
            result = self._search(new_state, g + 1, threshold, path, direction)
            path.pop()
            if isinstance(result, list):
                return result
            if result < min_threshold:
                min_threshold = result
        return min_threshold

def solve_puzzle(state: PuzzleState, use_linear_conflict: bool=True) -> Optional[List[Direction]]:
    solver = IDAStar(use_linear_conflict=use_linear_conflict)
    return solver.solve(state)

def get_next_move(state: PuzzleState, use_linear_conflict: bool=True) -> Optional[Direction]:
    if state.is_goal():
        return None
    solution = solve_puzzle(state, use_linear_conflict)
    if solution and len(solution) > 0:
        return solution[0]
    return None
if __name__ == '__main__':
    from common import is_solvable
    test_board = [[1, 2, 3], [4, 0, 6], [7, 5, 8]]
    state = PuzzleState(test_board)
    print('初始状态:')
    print(state)
    print(f'\n是否有解: {is_solvable(state)}')
    solution = solve_puzzle(state)
    if solution:
        print(f'\n找到解，共{len(solution)}步:')
        print(' -> '.join((d.value for d in solution)))
        test_state = state.copy()
        for move in solution:
            test_state.move(move)
        print(f'\n最终状态是否为目标: {test_state.is_goal()}')
    else:
        print('\n未找到解')