"""
数字华容道 - 计算节点程序 (Solver)
连接UI程序，接收棋盘状态，计算并发送下一步移动
"""

import socket
import argparse
import time
from datetime import datetime
from typing import Optional

from common import (
    PuzzleState, Direction, Message, MessageType,
    send_message, recv_message, is_solvable,
    DEFAULT_PORT
)
from solver import solve_puzzle, get_next_move


class SolverNode:
    """计算节点"""
    
    def __init__(self, solver_id: int, host: str, port: int, use_linear_conflict: bool = True):
        """
        初始化计算节点
        
        Args:
            solver_id: 节点ID (1 或 2)
            host: UI程序的IP地址
            port: UI程序的端口
            use_linear_conflict: 是否使用线性冲突优化
        """
        if solver_id not in [1, 2]:
            raise ValueError("Solver ID 必须是 1 或 2")
        
        self.solver_id = solver_id
        self.host = host
        self.port = port
        self.use_linear_conflict = use_linear_conflict
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.current_state: Optional[PuzzleState] = None
        
        # 缓存完整解法
        self.cached_solution: list = []
        self.solution_index = 0
    
    def _log(self, message: str, level: str = "INFO"):
        """打印日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "SEND": "📤",
            "RECV": "📥",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "CALC": "🧮"
        }.get(level, "")
        
        print(f"[{timestamp}] [{level:^7}] {prefix} {message}")
    
    def connect(self) -> bool:
        """连接到UI程序"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            
            self._log(f"正在连接到 {self.host}:{self.port}...")
            
            # 发送连接请求
            connect_msg = Message(
                msg_type=MessageType.CONNECT,
                solver_id=self.solver_id
            )
            send_message(self.socket, connect_msg)
            self._log(f"发送连接请求 (Solver {self.solver_id})", "SEND")
            
            # 等待欢迎消息
            response = recv_message(self.socket)
            
            if response and response.msg_type == MessageType.WELCOME:
                self._log(f"连接成功！已被接受为 Solver {self.solver_id}", "SUCCESS")
                return True
            else:
                self._log("连接被拒绝", "ERROR")
                return False
        
        except Exception as e:
            self._log(f"连接失败: {str(e)}", "ERROR")
            return False
    
    def run(self):
        """运行主循环"""
        if not self.connect():
            return
        
        self.running = True
        self._log("等待游戏开始...")
        
        try:
            while self.running:
                msg = recv_message(self.socket)
                
                if not msg:
                    self._log("连接已断开", "ERROR")
                    break
                
                self._handle_message(msg)
        
        except KeyboardInterrupt:
            self._log("用户中断", "INFO")
        except Exception as e:
            self._log(f"运行错误: {str(e)}", "ERROR")
        finally:
            self._cleanup()
    
    def _handle_message(self, msg: Message):
        """处理接收到的消息"""
        
        if msg.msg_type == MessageType.STATE:
            # 收到状态更新 - 保存最新状态
            self.current_state = PuzzleState(msg.board_data)
            step = msg.step_num
            self._log(f"收到棋盘状态 (当前步数: {step})", "RECV")
        
        elif msg.msg_type == MessageType.YOUR_TURN:
            # 轮到我了 - 基于当前状态计算下一步
            self._log(f"轮到 Solver {self.solver_id} 行动", "RECV")
            self._make_move()
        
        elif msg.msg_type == MessageType.SOLVED:
            # 游戏完成 - 继续等待新游戏
            self._log(f"🎉 游戏完成！总步数: {msg.total_steps}", "SUCCESS")
            self._log("等待新游戏...", "INFO")
        
        elif msg.msg_type == MessageType.NOSOLUTION:
            # 无解 - 继续等待新题目
            self._log("题目无解", "ERROR")
            self._log("等待新题目...", "INFO")
        
        elif msg.msg_type == MessageType.ERROR:
            # 错误
            self._log(f"收到错误: {msg.error_msg}", "ERROR")
    
    def _make_move(self):
        """执行移动 - 每次都基于当前状态重新计算"""
        if not self.current_state:
            self._log("无法移动：没有棋盘状态", "ERROR")
            return
        
        if self.current_state.is_goal():
            self._log("棋盘已经是目标状态", "INFO")
            return
        
        # 基于当前状态计算解法
        start_time = time.time()
        solution = solve_puzzle(self.current_state, self.use_linear_conflict)
        elapsed = time.time() - start_time
        
        if not solution or len(solution) == 0:
            self._log("无法找到解法", "ERROR")
            return
        
        self._log(f"计算完成！当前需 {len(solution)} 步，耗时 {elapsed:.3f}s", "CALC")
        
        # 只发送第一步（下一步移动）
        direction = solution[0]
        
        # 发送移动指令
        move_msg = Message(
            msg_type=MessageType.MOVE,
            solver_id=self.solver_id,
            direction=direction
        )
        send_message(self.socket, move_msg)
        
        self._log(f"发送移动: {direction.value}", "SEND")
    
    def _cleanup(self):
        """清理资源"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self._log("程序退出", "INFO")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数字华容道 - 计算节点程序')
    parser.add_argument('--id', type=int, required=True, choices=[1, 2],
                        help='Solver ID (1 或 2)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='UI程序的IP地址 (默认: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'UI程序的端口 (默认: {DEFAULT_PORT})')
    parser.add_argument('--no-linear-conflict', action='store_true',
                        help='不使用线性冲突优化 (用于区分两个Solver)')
    
    args = parser.parse_args()
    
    print("=" * 50)
    print(f"  数字华容道 - Solver {args.id}")
    print(f"  目标: {args.host}:{args.port}")
    print(f"  算法: {'曼哈顿距离' if args.no_linear_conflict else '线性冲突'}")
    print("=" * 50)
    print()
    
    solver = SolverNode(
        solver_id=args.id,
        host=args.host,
        port=args.port,
        use_linear_conflict=not args.no_linear_conflict
    )
    solver.run()


if __name__ == "__main__":
    main()
