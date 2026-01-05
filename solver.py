"""
数字华容道 - IDA* 求解算法模块
使用迭代加深A*算法求解数字华容道

IDA* (Iterative Deepening A*) 算法的特点：
1. 结合了A*的最优性和迭代加深的低内存消耗
2. 通过启发函数估计距离目标的距离
3. 特别适合像4x4华容道这样状态空间巨大的问题
"""

# ==================== 导入模块 ====================
from typing import List, Optional, Tuple
from common import PuzzleState, Direction, DIRECTION_DELTA, OPPOSITE_DIRECTION, get_goal_state


# ==================== 启发函数 ====================
# 启发函数用于估计从当前状态到目标状态的最小步数
# 好的启发函数可以大幅减少搜索的节点数

def manhattan_distance(state: PuzzleState) -> int:
    """
    曼哈顿距离启发函数
    
    计算每个数字到其目标位置的曼哈顿距离(横向距离+纵向距离)之和
    这是一个"可采纳"的启发函数，永远不会高估真实距离
    
    参数:
        state: 当前棋盘状态
    
    返回值:
        曼哈顿距离之和
    """
    size = state.size
    distance = 0
    
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            
            if val != 0:  # 跳过空位
                # 计算这个数字的目标位置
                # 例如数字5在3x3棋盘中应该在第1行第1列 (5-1)//3=1, (5-1)%3=1
                goal_i = (val - 1) // size  # 目标行
                goal_j = (val - 1) % size   # 目标列
                
                # 累加曼哈顿距离
                distance += abs(i - goal_i) + abs(j - goal_j)
    
    return distance


def linear_conflict(state: PuzzleState) -> int:
    """
    线性冲突启发函数
    
    这是曼哈顿距离的增强版。当一行或一列中，有两个数字都在正确的行/列，
    但它们的相对顺序错误时，需要额外移动至少2步。
    
    例如在某一行中 [3, 2, 1]，如果这一行的目标是 [1, 2, 3]，
    那么1和3都在正确的行，但顺序反了，需要额外2步。
    
    参数:
        state: 当前棋盘状态
    
    返回值:
        曼哈顿距离 + 线性冲突惩罚
    """
    size = state.size
    conflict = 0
    
    # 检查行冲突
    for i in range(size):
        for j in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            
            # 计算这个数字的目标行
            goal_i = (val - 1) // size
            if goal_i != i:
                continue  # 不在正确的行，跳过
            
            # 检查同一行右边的数字
            for k in range(j + 1, size):
                other = state.board[i][k]
                if other == 0:
                    continue
                
                # 计算另一个数字的目标行
                other_goal_i = (other - 1) // size
                if other_goal_i != i:
                    continue  # 不在正确的行，跳过
                
                # 两个数字都在正确的行，检查相对顺序
                goal_j = (val - 1) % size
                other_goal_j = (other - 1) % size
                
                if goal_j > other_goal_j:  # 顺序错误（当前val应该在other右边，但实际在左边）
                    conflict += 2
    
    # 检查列冲突（逻辑类似）
    for j in range(size):
        for i in range(size):
            val = state.board[i][j]
            if val == 0:
                continue
            
            goal_j = (val - 1) % size
            if goal_j != j:
                continue  # 不在正确的列，跳过
            
            for k in range(i + 1, size):
                other = state.board[k][j]
                if other == 0:
                    continue
                
                other_goal_j = (other - 1) % size
                if other_goal_j != j:
                    continue
                
                goal_i = (val - 1) // size
                other_goal_i = (other - 1) // size
                
                if goal_i > other_goal_i:  # 顺序错误
                    conflict += 2
    
    # 返回曼哈顿距离 + 冲突惩罚
    return manhattan_distance(state) + conflict


# ==================== IDA* 算法 ====================

class IDAStar:
    """
    IDA* (Iterative Deepening A*) 求解器
    
    核心思想：
    1. 从启发函数的估计值作为初始阈值开始
    2. 进行深度优先搜索，只探索f值(g+h)不超过阈值的节点
    3. 如果没找到解，将阈值提高到本次搜索遇到的最小超出值
    4. 重复直到找到解或证明无解
    """
    
    def __init__(self, use_linear_conflict: bool = True):
        """
        初始化求解器
        
        参数:
            use_linear_conflict: 是否使用线性冲突启发函数
        """
        # 选择启发函数
        self.heuristic = linear_conflict if use_linear_conflict else manhattan_distance
        
        # 统计扩展的节点数（用于调试）
        self.nodes_expanded = 0
    
    def solve(self, initial_state: PuzzleState, max_depth: int = 80) -> Optional[List[Direction]]:
        """
        求解数字华容道
        
        参数:
            initial_state: 初始状态
            max_depth: 最大搜索深度（防止无限循环）
        
        返回值:
            移动序列（Direction列表），如果无解返回None
        """
        # 如果已经是目标状态，返回空列表
        if initial_state.is_goal():
            return []
        
        self.nodes_expanded = 0
        
        # 初始阈值设为启发函数的估计值
        threshold = self.heuristic(initial_state)
        
        # 用于记录路径的列表
        path = []
        
        # 迭代加深
        while threshold <= max_depth:
            # 进行一次深度优先搜索
            result = self._search(initial_state, 0, threshold, path, None)
            
            if isinstance(result, list):
                return result  # 找到解！
            
            if result == float('inf'):
                return None  # 无解
            
            # 更新阈值为本次搜索遇到的最小超出值
            threshold = result
        
        return None  # 超出最大深度
    
    def _search(
        self,
        state: PuzzleState,
        g: int,              # 从起点到当前状态的实际步数
        threshold: int,      # 当前阈值
        path: List[Direction],  # 当前路径
        last_move: Optional[Direction]  # 上一步的移动方向（用于剪枝）
    ) -> any:
        """
        IDA* 搜索的核心递归函数
        
        返回值:
            - 如果找到解：返回路径列表
            - 如果超出阈值：返回遇到的最小f值（用于更新阈值）
            - 如果无解：返回 float('inf')
        """
        self.nodes_expanded += 1
        
        # 计算f值 = g (已走步数) + h (估计剩余步数)
        f = g + self.heuristic(state)
        
        # 如果f值超过阈值，返回f值（用于更新阈值）
        if f > threshold:
            return f
        
        # 如果达到目标状态，返回当前路径
        if state.is_goal():
            return path[:]  # 返回路径的副本
        
        # 记录本次搜索遇到的最小超出值
        min_threshold = float('inf')
        
        # 尝试所有有效的移动方向
        for direction in state.get_valid_moves():
            # 剪枝：不走回头路
            # 如果上一步向上走，这一步就不要向下走（会回到原来的状态）
            if last_move is not None and direction == OPPOSITE_DIRECTION[last_move]:
                continue
            
            # 创建新状态（深拷贝，不修改原状态）
            new_state = state.copy()
            new_state.move(direction)
            
            # 将这一步加入路径
            path.append(direction)
            
            # 递归搜索
            result = self._search(new_state, g + 1, threshold, path, direction)
            
            # 回溯：移除这一步
            path.pop()
            
            # 如果找到解，直接返回
            if isinstance(result, list):
                return result
            
            # 更新最小超出值
            if result < min_threshold:
                min_threshold = result
        
        return min_threshold


# ==================== 简化接口 ====================

def solve_puzzle(state: PuzzleState, use_linear_conflict: bool = True) -> Optional[List[Direction]]:
    """
    求解数字华容道（简化接口）
    
    参数:
        state: 初始状态
        use_linear_conflict: 是否使用线性冲突优化
    
    返回值:
        移动序列，如果无解返回None
    """
    solver = IDAStar(use_linear_conflict=use_linear_conflict)
    return solver.solve(state)


def get_next_move(
    state: PuzzleState,
    use_linear_conflict: bool = True
) -> Optional[Direction]:
    """
    获取下一步移动（只返回第一步）
    
    参数:
        state: 当前状态
        use_linear_conflict: 是否使用线性冲突优化
    
    返回值:
        下一步移动方向，如果已完成或无解返回None
    """
    if state.is_goal():
        return None
    
    solution = solve_puzzle(state, use_linear_conflict)
    
    if solution and len(solution) > 0:
        return solution[0]
    
    return None


# ==================== 测试代码 ====================

if __name__ == "__main__":
    from common import is_solvable
    
    # 创建一个简单的测试棋盘
    test_board = [
        [1, 2, 3],
        [4, 0, 6],
        [7, 5, 8]
    ]
    state = PuzzleState(test_board)
    
    print("初始状态:")
    print(state)
    print(f"\n是否有解: {is_solvable(state)}")
    
    # 求解
    solution = solve_puzzle(state)
    
    if solution:
        print(f"\n找到解，共{len(solution)}步:")
        print(" -> ".join(d.value for d in solution))
        
        # 验证解是否正确
        test_state = state.copy()
        for move in solution:
            test_state.move(move)
        print(f"\n最终状态是否为目标: {test_state.is_goal()}")
    else:
        print("\n未找到解")
