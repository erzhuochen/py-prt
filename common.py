import json
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
DEFAULT_PORT = 9527
BUFFER_SIZE = 4096

class Direction(Enum):
    UP = 'UP'
    DOWN = 'DOWN'
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'
DIRECTION_DELTA = {Direction.UP: (-1, 0), Direction.DOWN: (1, 0), Direction.LEFT: (0, -1), Direction.RIGHT: (0, 1)}
OPPOSITE_DIRECTION = {Direction.UP: Direction.DOWN, Direction.DOWN: Direction.UP, Direction.LEFT: Direction.RIGHT, Direction.RIGHT: Direction.LEFT}

@dataclass
class PuzzleState:
    board: List[List[int]]
    size: int = field(init=False)
    blank_pos: Tuple[int, int] = field(init=False)

    def __post_init__(self):
        self.size = len(self.board)
        self.blank_pos = self._find_blank()

    def _find_blank(self) -> Tuple[int, int]:
        for i in range(self.size):
            for j in range(self.size):
                if self.board[i][j] == 0:
                    return (i, j)
        raise ValueError('棋盘中没有空位(0)')

    def copy(self) -> 'PuzzleState':
        new_board = [row[:] for row in self.board]
        return PuzzleState(new_board)

    def get_valid_moves(self) -> List[Direction]:
        moves = []
        r, c = self.blank_pos
        if r > 0:
            moves.append(Direction.UP)
        if r < self.size - 1:
            moves.append(Direction.DOWN)
        if c > 0:
            moves.append(Direction.LEFT)
        if c < self.size - 1:
            moves.append(Direction.RIGHT)
        return moves

    def move(self, direction: Direction) -> bool:
        if direction not in self.get_valid_moves():
            return False
        r, c = self.blank_pos
        dr, dc = DIRECTION_DELTA[direction]
        new_r, new_c = (r + dr, c + dc)
        self.board[r][c] = self.board[new_r][new_c]
        self.board[new_r][new_c] = 0
        self.blank_pos = (new_r, new_c)
        return True

    def is_goal(self) -> bool:
        expected = 1
        for i in range(self.size):
            for j in range(self.size):
                if i == self.size - 1 and j == self.size - 1:
                    if self.board[i][j] != 0:
                        return False
                else:
                    if self.board[i][j] != expected:
                        return False
                    expected += 1
        return True

    def to_tuple(self) -> Tuple[int, ...]:
        return tuple((cell for row in self.board for cell in row))

    def __hash__(self):
        return hash(self.to_tuple())

    def __eq__(self, other):
        if not isinstance(other, PuzzleState):
            return False
        return self.board == other.board

    def __str__(self):
        lines = []
        cell_width = len(str(self.size * self.size - 1))
        for row in self.board:
            line = ' '.join((str(cell).rjust(cell_width) if cell != 0 else ' ' * cell_width for cell in row))
            lines.append(line)
        return '\n'.join(lines)

def count_inversions(board: List[List[int]]) -> int:
    flat = [cell for row in board for cell in row if cell != 0]
    inversions = 0
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i] > flat[j]:
                inversions += 1
    return inversions

def is_solvable(state: PuzzleState) -> bool:
    inversions = count_inversions(state.board)
    size = state.size
    if size % 2 == 1:
        return inversions % 2 == 0
    else:
        blank_row_from_bottom = size - state.blank_pos[0]
        return (inversions + blank_row_from_bottom) % 2 == 1

def load_puzzle_from_file(filepath: str) -> PuzzleState:
    board = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                row = [int(x.strip()) for x in line.split(',')]
                board.append(row)
    if not board:
        raise ValueError('文件为空')
    size = len(board)
    for row in board:
        if len(row) != size:
            raise ValueError(f'棋盘必须是正方形，期望{size}列，得到{len(row)}列')
    return PuzzleState(board)

class MessageType(Enum):
    CONNECT = 'CONNECT'
    WELCOME = 'WELCOME'
    STATE = 'STATE'
    YOUR_TURN = 'YOUR_TURN'
    MOVE = 'MOVE'
    SOLVED = 'SOLVED'
    NOSOLUTION = 'NOSOLUTION'
    ERROR = 'ERROR'

@dataclass
class Message:
    msg_type: MessageType
    solver_id: Optional[int] = None
    step_num: Optional[int] = None
    direction: Optional[Direction] = None
    board_data: Optional[List[List[int]]] = None
    total_steps: Optional[int] = None
    error_msg: Optional[str] = None

    def to_json(self) -> str:
        data = {'type': self.msg_type.value}
        if self.solver_id is not None:
            data['solver_id'] = self.solver_id
        if self.step_num is not None:
            data['step_num'] = self.step_num
        if self.direction is not None:
            data['direction'] = self.direction.value
        if self.board_data is not None:
            data['board'] = self.board_data
        if self.total_steps is not None:
            data['total_steps'] = self.total_steps
        if self.error_msg is not None:
            data['error'] = self.error_msg
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        msg_type = MessageType(data['type'])
        solver_id = data.get('solver_id')
        step_num = data.get('step_num')
        direction = Direction(data['direction']) if 'direction' in data else None
        board_data = data.get('board')
        total_steps = data.get('total_steps')
        error_msg = data.get('error')
        return cls(msg_type=msg_type, solver_id=solver_id, step_num=step_num, direction=direction, board_data=board_data, total_steps=total_steps, error_msg=error_msg)

def send_message(sock, message: Message):
    data = message.to_json().encode('utf-8')
    length = len(data)
    sock.sendall(length.to_bytes(4, 'big') + data)

def recv_message(sock) -> Optional[Message]:
    length_data = sock.recv(4)
    if not length_data:
        return None
    length = int.from_bytes(length_data, 'big')
    data = b''
    while len(data) < length:
        chunk = sock.recv(min(length - len(data), BUFFER_SIZE))
        if not chunk:
            return None
        data += chunk
    return Message.from_json(data.decode('utf-8'))

def get_goal_state(size: int) -> PuzzleState:
    board = []
    num = 1
    for i in range(size):
        row = []
        for j in range(size):
            if i == size - 1 and j == size - 1:
                row.append(0)
            else:
                row.append(num)
                num += 1
        board.append(row)
    return PuzzleState(board)
if __name__ == '__main__':
    test_board = [[1, 2, 3], [4, 0, 6], [7, 5, 8]]
    state = PuzzleState(test_board)
    print('初始状态:')
    print(state)
    print(f'\n空位位置: {state.blank_pos}')
    print(f'有效移动: {[d.value for d in state.get_valid_moves()]}')
    print(f'是否有解: {is_solvable(state)}')
    print(f'是否为目标: {state.is_goal()}')