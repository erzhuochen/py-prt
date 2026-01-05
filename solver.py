"""
数字华容道 - IDA* 求解算法模块
使用迭代加深A*算法求解数字华容道
"""

from typing import List, Optional, Tuple
from common import PuzzleState, Direction, DIRECTION_DELTA, OPPOSITE_DIRECTION, get_goal_state


# ==================== 启发函数 ====================

def manhattan_distance(state: PuzzleState) -> int:
    """
    曼哈顿距离启发函数
    计算每个数字到其目标位置的曼哈顿距离之和
    """
    size = state.size
    distance = 0
    
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            if val != 0:
                # 目标位置
                goal_i = (val - 1) // size
                goal_j = (val - 1) % size
                distance += abs(i - goal_i) + abs(j - goal_j)
    
    return distance


def linear_conflict(state: PuzzleState) -> int:
    """
    线性冲突启发函数
    在曼哈顿距离基础上，加上线性冲突的代价
    当一行/列中，两个数字都在正确的行/列，但相对顺序错误时，需要额外的2步
    """
    size = state.size
    conflict = 0
    
    # 检查行冲突
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            goal_i = (val - 1) // size
            if goal_i != i:
                continue  # 不在正确的行
            
            # 检查同一行右边的数字
            for k in range(j + 1, size):
                other = state.board[i][k]
                if other == 0:
                    continue
                other_goal_i = (other - 1) // size
                if other_goal_i != i:
                    continue  # 不在正确的行
                
                # 两者都在正确的行，检查相对顺序
                goal_j = (val - 1) % size
                other_goal_j = (other - 1) % size
                if goal_j > other_goal_j:  # 顺序错误
                    conflict += 2
    
    # 检查列冲突
    for j in range(size):
        for i in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            goal_j = (val - 1) % size
            if goal_j != j:
                continue  # 不在正确的列
            
            # 检查同一列下面的数字
            for k in range(i + 1, size):
                other = state.board[k][j]
                if other == 0:
                    continue
                other_goal_j = (other - 1) % size
                if other_goal_j != j:
                    continue  # 不在正确的列
                
                # 两者都在正确的列，检查相对顺序
                goal_i = (val - 1) // size
                other_goal_i = (other - 1) // size
                if goal_i > other_goal_i:  # 顺序错误
                    conflict += 2
    
    return manhattan_distance(state) + conflict


# ==================== IDA* 算法 ====================

class IDAStar:
    """IDA* 求解器"""
    
    def __init__(self, use_linear_conflict: bool = True):
        """
        初始化求解器
        
        Args:
            use_linear_conflict: 是否使用线性冲突启发函数
        """
        self.heuristic = linear_conflict if use_linear_conflict else manhattan_distance
        self.nodes_expanded = 0
    
    def solve(self, initial_state: PuzzleState, max_depth: int = 80) -> Optional[List[Direction]]:
        """
        求解数字华容道
        
        Args:
            initial_state: 初始状态
            max_depth: 最大搜索深度
        
        Returns:
            移动序列，如果无解返回None
        """
        if initial_state.is_goal():
            return []
        
        self.nodes_expanded = 0
        threshold = self.heuristic(initial_state)
        path = []
        
        while threshold <= max_depth:
            result = self._search(initial_state, 0, threshold, path, None)
            
            if isinstance(result, list):
                return result  # 找到解
            
            if result == float('inf'):
                return None  # 无解
            
            threshold = result  # 更新阈值
        
        return None  # 超出最大深度
    
    def _search(
        self,
        state: PuzzleState,
        g: int,
        threshold: int,
        path: List[Direction],
        last_move: Optional[Direction]
    ) -> any:
        """
        IDA* 搜索核心
        
        Returns:
            - 解的路径列表（如果找到解）
            - 新的阈值（如果需要增加阈值）
            - float('inf')（如果需要无解）
        """
        self.nodes_expanded += 1
        
        f = g + self.heuristic(state)
        
        if f > threshold:
            return f
        
        if state.is_goal():
            return path[:]
        
        min_threshold = float('inf')
        
        for direction in state.get_valid_moves():
            # 剪枝：不走回头路
            if last_move is not None and direction == OPPOSITE_DIRECTION[last_move]:
                continue
            
            # 执行移动
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


# ==================== 简化接口 ====================

def solve_puzzle(state: PuzzleState, use_linear_conflict: bool = True) -> Optional[List[Direction]]:
    """
    求解数字华容道
    
    Args:
        state: 初始状态
        use_linear_conflict: 是否使用线性冲突优化
    
    Returns:
        移动序列，如果无解返回None
    """
    solver = IDAStar(use_linear_conflict=use_linear_conflict)
    return solver.solve(state)


def get_next_move(
    state: PuzzleState,
    use_linear_conflict: bool = True
) -> Optional[Direction]:
    """
    获取下一步移动
    
    Args:
        state: 当前状态
        use_linear_conflict: 是否使用线性冲突优化
    
    Returns:
        下一步移动方向，如果已完成或无解返回None
    """
    if state.is_goal():
        return None
    
    solution = solve_puzzle(state, use_linear_conflict)
    
    if solution and len(solution) > 0:
        return solution[0]
    
    return None


if __name__ == "__main__":
    # 测试代码
    from common import is_solvable
    
    # 简单的3x3测试
    test_board = [
        [1, 2, 3],
        [4, 0, 6],
        [7, 5, 8]
    ]
    state = PuzzleState(test_board)
    
    print("初始状态:")
    print(state)
    print(f"\n是否有解: {is_solvable(state)}")
    
    solution = solve_puzzle(state)
    if solution:
        print(f"\n找到解，共{len(solution)}步:")
        print(" -> ".join(d.value for d in solution))
        
        # 验证解
        test_state = state.copy()
        for move in solution:
            test_state.move(move)
        print(f"\n最终状态是否为目标: {test_state.is_goal()}")
    else:
        print("\n未找到解")
