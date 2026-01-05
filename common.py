"""
数字华容道 - 公共模块
包含棋盘状态、网络协议、可解性判断等公共功能

这个模块被UI程序和Solver程序共同使用，包含：
1. 棋盘状态类（PuzzleState）
2. 可解性判断算法
3. 网络通信协议
"""

# ==================== 导入模块 ====================
import json                             # JSON序列化，用于网络消息
from typing import List, Tuple, Optional # 类型提示
from dataclasses import dataclass, field # 数据类装饰器，简化类定义
from enum import Enum                    # 枚举类型


# ==================== 常量定义 ====================

# 默认端口号
DEFAULT_PORT = 9527

# 网络缓冲区大小（字节）
BUFFER_SIZE = 4096


# ==================== 方向枚举 ====================

class Direction(Enum):
    """
    移动方向枚举
    
    表示空位可以移动的四个方向
    值是字符串，便于在网络上传输
    """
    UP = "UP"       # 空位向上移动（数字向下移动到空位）
    DOWN = "DOWN"   # 空位向下移动
    LEFT = "LEFT"   # 空位向左移动
    RIGHT = "RIGHT" # 空位向右移动


# 方向到坐标偏移的映射
# (行偏移, 列偏移)
DIRECTION_DELTA = {
    Direction.UP: (-1, 0),    # 向上：行减1，列不变
    Direction.DOWN: (1, 0),   # 向下：行加1，列不变
    Direction.LEFT: (0, -1),  # 向左：行不变，列减1
    Direction.RIGHT: (0, 1),  # 向右：行不变，列加1
}

# 反方向映射（用于剪枝，避免走回头路）
OPPOSITE_DIRECTION = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}


# ==================== 棋盘状态类 ====================

@dataclass
class PuzzleState:
    """
    数字华容道棋盘状态类
    
    使用@dataclass装饰器可以自动生成__init__、__repr__等方法
    
    属性:
        board: 二维列表，存储棋盘数字，0表示空位
        size: 棋盘大小（自动计算）
        blank_pos: 空位位置（自动计算）
    """
    # 棋盘二维数组，0表示空位
    # 例如 3x3 棋盘: [[1,2,3], [4,5,6], [7,8,0]]
    board: List[List[int]]
    
    # 以下字段使用field(init=False)，表示不在__init__中初始化
    # 它们会在__post_init__中自动计算
    size: int = field(init=False)
    blank_pos: Tuple[int, int] = field(init=False)
    
    def __post_init__(self):
        """
        后初始化方法
        在__init__执行完毕后自动调用
        用于计算size和blank_pos
        """
        self.size = len(self.board)  # 棋盘大小等于行数
        self.blank_pos = self._find_blank()  # 找到空位位置
    
    def _find_blank(self) -> Tuple[int, int]:
        """
        找到空位(0)的位置
        
        返回值:
            (行号, 列号) 元组
        """
        for i in range(self.size):
            for j in range(self.size):
                if self.board[i][j] == 0:
                    return (i, j)
        # 如果没找到，抛出异常
        raise ValueError("棋盘中没有空位(0)")
    
    def copy(self) -> 'PuzzleState':
        """
        深拷贝
        创建一个新的PuzzleState对象，内容相同
        
        返回值:
            新的PuzzleState对象
        """
        # 列表推导式创建二维数组的深拷贝
        # row[:] 创建row的浅拷贝
        new_board = [row[:] for row in self.board]
        return PuzzleState(new_board)
    
    def get_valid_moves(self) -> List[Direction]:
        """
        获取当前状态下所有有效的移动方向
        
        返回值:
            可以移动的方向列表
        """
        moves = []
        r, c = self.blank_pos  # 获取空位的行和列
        
        # 检查每个方向是否可行
        if r > 0:  # 不在第一行，可以向上
            moves.append(Direction.UP)
        if r < self.size - 1:  # 不在最后一行，可以向下
            moves.append(Direction.DOWN)
        if c > 0:  # 不在第一列，可以向左
            moves.append(Direction.LEFT)
        if c < self.size - 1:  # 不在最后一列，可以向右
            moves.append(Direction.RIGHT)
        
        return moves
    
    def move(self, direction: Direction) -> bool:
        """
        执行移动操作（移动空位）
        
        参数:
            direction: 移动方向
        
        返回值:
            True表示移动成功，False表示无效移动
        """
        # 检查方向是否有效
        if direction not in self.get_valid_moves():
            return False
        
        # 获取当前空位位置
        r, c = self.blank_pos
        
        # 获取方向对应的偏移量
        dr, dc = DIRECTION_DELTA[direction]
        
        # 计算新位置
        new_r, new_c = r + dr, c + dc
        
        # 交换空位和目标位置的值
        self.board[r][c] = self.board[new_r][new_c]  # 数字移到空位
        self.board[new_r][new_c] = 0                  # 新位置变成空位
        
        # 更新空位位置
        self.blank_pos = (new_r, new_c)
        
        return True
    
    def is_goal(self) -> bool:
        """
        检查是否达到目标状态
        
        目标状态：数字1到n²-1按顺序排列，最后一个位置是空位
        例如3x3的目标状态：
        1 2 3
        4 5 6
        7 8 0
        
        返回值:
            True表示已达到目标状态
        """
        expected = 1  # 期望的数字，从1开始
        
        for i in range(self.size):
            for j in range(self.size):
                # 最后一个位置应该是空位(0)
                if i == self.size - 1 and j == self.size - 1:
                    if self.board[i][j] != 0:
                        return False
                else:
                    # 其他位置应该按顺序是1,2,3,...
                    if self.board[i][j] != expected:
                        return False
                    expected += 1
        
        return True
    
    def to_tuple(self) -> Tuple[int, ...]:
        """
        将棋盘转换为元组（用于哈希）
        
        元组是不可变的，可以作为字典的键或集合的元素
        """
        # 生成器表达式 + tuple() 将二维数组扁平化为一维元组
        return tuple(cell for row in self.board for cell in row)
    
    def __hash__(self):
        """
        计算哈希值
        使棋盘状态可以作为字典的键
        """
        return hash(self.to_tuple())
    
    def __eq__(self, other):
        """
        判断两个棋盘状态是否相等
        """
        if not isinstance(other, PuzzleState):
            return False
        return self.board == other.board
    
    def __str__(self):
        """
        将棋盘转换为字符串（用于打印）
        """
        lines = []
        # 计算最宽数字的宽度（用于对齐）
        cell_width = len(str(self.size * self.size - 1))
        
        for row in self.board:
            line = " ".join(
                str(cell).rjust(cell_width) if cell != 0 else " " * cell_width
                for cell in row
            )
            lines.append(line)
        
        return "\n".join(lines)


# ==================== 可解性判断 ====================

def count_inversions(board: List[List[int]]) -> int:
    """
    计算逆序数
    
    逆序数是指在一维序列中，大数在小数前面出现的次数
    例如 [2,1,3] 的逆序数是1（2在1前面）
    
    参数:
        board: 二维棋盘数组
    
    返回值:
        逆序数
    """
    # 将二维数组扁平化为一维，同时过滤掉0
    flat = [cell for row in board for cell in row if cell != 0]
    
    inversions = 0
    
    # 双重循环计算逆序数
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i] > flat[j]:  # 如果前面的数比后面的大
                inversions += 1
    
    return inversions


def is_solvable(state: PuzzleState) -> bool:
    """
    判断数字华容道是否有解
    
    规则（基于数学证明）：
    - 对于奇数阶(3x3)：逆序数为偶数时有解
    - 对于偶数阶(4x4)：
      - 空位在从底部数的奇数行，逆序数为偶数时有解
      - 空位在从底部数的偶数行，逆序数为奇数时有解
      - 即：(inversions + blank_row_from_bottom) 为奇数时有解
    
    参数:
        state: 棋盘状态
    
    返回值:
        True表示有解，False表示无解
    """
    inversions = count_inversions(state.board)
    size = state.size
    
    if size % 2 == 1:  # 奇数阶（如3x3）
        return inversions % 2 == 0
    else:  # 偶数阶（如4x4）
        # 计算空位距离底部的行数（从1开始）
        blank_row_from_bottom = size - state.blank_pos[0]
        return (inversions + blank_row_from_bottom) % 2 == 1


# ==================== 文件加载 ====================

def load_puzzle_from_file(filepath: str) -> PuzzleState:
    """
    从文件加载棋盘状态
    
    文件格式：每行用逗号分隔的数字，0表示空位
    例如：
    1,2,3
    4,0,6
    7,5,8
    
    参数:
        filepath: 文件路径
    
    返回值:
        PuzzleState对象
    """
    board = []
    
    # 打开并读取文件
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()  # 去除首尾空白
            if line:
                # 将一行按逗号分割，转换为整数列表
                row = [int(x.strip()) for x in line.split(',')]
                board.append(row)
    
    # 检查是否为空
    if not board:
        raise ValueError("文件为空")
    
    # 检查是否为正方形
    size = len(board)
    for row in board:
        if len(row) != size:
            raise ValueError(f"棋盘必须是正方形，期望{size}列，得到{len(row)}列")
    
    return PuzzleState(board)


# ==================== 网络协议 ====================

class MessageType(Enum):
    """
    消息类型枚举
    
    定义了UI和Solver之间通信的所有消息类型
    """
    CONNECT = "CONNECT"        # Solver -> UI: 连接请求
    WELCOME = "WELCOME"        # UI -> Solver: 欢迎消息（连接成功）
    STATE = "STATE"            # UI -> Solver: 同步棋盘状态
    YOUR_TURN = "YOUR_TURN"    # UI -> Solver: 轮到你了
    MOVE = "MOVE"              # Solver -> UI: 移动指令
    SOLVED = "SOLVED"          # UI -> All: 游戏完成
    NOSOLUTION = "NOSOLUTION"  # UI -> All: 题目无解
    ERROR = "ERROR"            # 错误消息


@dataclass
class Message:
    """
    网络消息类
    
    使用@dataclass简化定义
    所有字段都有默认值，可以灵活创建不同类型的消息
    """
    msg_type: MessageType                           # 消息类型（必需）
    solver_id: Optional[int] = None                 # Solver的ID
    step_num: Optional[int] = None                  # 当前步数
    direction: Optional[Direction] = None           # 移动方向
    board_data: Optional[List[List[int]]] = None   # 棋盘数据
    total_steps: Optional[int] = None               # 总步数（游戏完成时）
    error_msg: Optional[str] = None                 # 错误信息
    
    def to_json(self) -> str:
        """
        将消息序列化为JSON字符串
        
        返回值:
            JSON格式的字符串
        """
        # 构建数据字典
        data = {"type": self.msg_type.value}
        
        # 只添加非None的字段
        if self.solver_id is not None:
            data["solver_id"] = self.solver_id
        if self.step_num is not None:
            data["step_num"] = self.step_num
        if self.direction is not None:
            data["direction"] = self.direction.value
        if self.board_data is not None:
            data["board"] = self.board_data
        if self.total_steps is not None:
            data["total_steps"] = self.total_steps
        if self.error_msg is not None:
            data["error"] = self.error_msg
        
        # 使用json.dumps()转换为JSON字符串
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """
        从JSON字符串反序列化为Message对象
        
        参数:
            json_str: JSON字符串
        
        返回值:
            Message对象
        
        注意：@classmethod使这个方法可以通过类调用：Message.from_json(...)
        """
        # 解析JSON
        data = json.loads(json_str)
        
        # 提取各字段
        msg_type = MessageType(data["type"])
        solver_id = data.get("solver_id")          # .get()在键不存在时返回None
        step_num = data.get("step_num")
        direction = Direction(data["direction"]) if "direction" in data else None
        board_data = data.get("board")
        total_steps = data.get("total_steps")
        error_msg = data.get("error")
        
        # 创建并返回Message对象
        return cls(
            msg_type=msg_type,
            solver_id=solver_id,
            step_num=step_num,
            direction=direction,
            board_data=board_data,
            total_steps=total_steps,
            error_msg=error_msg,
        )


# ==================== 网络通信函数 ====================

def send_message(sock, message: Message):
    """
    发送消息
    
    协议：先发送4字节的消息长度，再发送消息内容
    这样接收方就知道要读取多少字节
    
    参数:
        sock: socket对象
        message: 要发送的消息
    """
    # 将消息转换为JSON，再编码为UTF-8字节串
    data = message.to_json().encode('utf-8')
    
    # 获取数据长度
    length = len(data)
    
    # 将长度转换为4字节的大端序字节串，拼接上数据一起发送
    # to_bytes(4, 'big') 将整数转换为4字节，使用大端序
    sock.sendall(length.to_bytes(4, 'big') + data)


def recv_message(sock) -> Optional[Message]:
    """
    接收消息
    
    参数:
        sock: socket对象
    
    返回值:
        Message对象，如果连接断开则返回None
    """
    # 先接收4字节的长度
    length_data = sock.recv(4)
    if not length_data:
        return None  # 连接已断开
    
    # 将4字节转换为整数
    length = int.from_bytes(length_data, 'big')
    
    # 接收完整的数据
    data = b''  # 空字节串
    while len(data) < length:
        # 每次最多接收BUFFER_SIZE字节
        chunk = sock.recv(min(length - len(data), BUFFER_SIZE))
        if not chunk:
            return None  # 连接断开
        data += chunk  # 拼接
    
    # 解码并反序列化为Message对象
    return Message.from_json(data.decode('utf-8'))


# ==================== 目标状态生成 ====================

def get_goal_state(size: int) -> PuzzleState:
    """
    生成指定大小的目标状态
    
    参数:
        size: 棋盘大小
    
    返回值:
        目标状态的PuzzleState对象
    """
    board = []
    num = 1
    
    for i in range(size):
        row = []
        for j in range(size):
            if i == size - 1 and j == size - 1:
                row.append(0)  # 最后一个位置是空位
            else:
                row.append(num)
                num += 1
        board.append(row)
    
    return PuzzleState(board)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 当直接运行这个文件时执行测试
    test_board = [
        [1, 2, 3],
        [4, 0, 6],
        [7, 5, 8]
    ]
    state = PuzzleState(test_board)
    
    print("初始状态:")
    print(state)
    print(f"\n空位位置: {state.blank_pos}")
    print(f"有效移动: {[d.value for d in state.get_valid_moves()]}")
    print(f"是否有解: {is_solvable(state)}")
    print(f"是否为目标: {state.is_goal()}")
