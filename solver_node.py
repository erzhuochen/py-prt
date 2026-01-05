"""
数字华容道 - 计算节点程序 (Solver)
连接UI程序，接收棋盘状态，计算并发送下一步移动

这个程序作为"计算者"角色：
1. 连接到UI程序的TCP服务器
2. 等待UI发来的棋盘状态和"轮到你"的通知
3. 使用IDA*算法计算下一步，然后发送给UI
"""

# ==================== 导入模块 ====================
import socket                           # 网络通信库，用于连接UI服务器
import argparse                         # 命令行参数解析库
import time                             # 时间相关功能，用于计算耗时
from datetime import datetime           # 日期时间处理，用于日志时间戳
from typing import Optional             # 类型提示

# 从公共模块导入
from common import (
    PuzzleState,           # 棋盘状态类
    Direction,             # 移动方向枚举
    Message,               # 网络消息类
    MessageType,           # 消息类型枚举
    send_message,          # 发送消息的函数
    recv_message,          # 接收消息的函数
    is_solvable,           # 判断是否可解
    DEFAULT_PORT           # 默认端口号
)

# 从求解算法模块导入
from solver import solve_puzzle, get_next_move


# ==================== 计算节点类 ====================
class SolverNode:
    """
    计算节点类
    
    负责连接UI服务器，接收状态，计算并发送移动指令
    """
    
    def __init__(self, solver_id: int, host: str, port: int, use_linear_conflict: bool = True):
        """
        构造函数：初始化计算节点
        
        参数:
            solver_id: 节点ID，必须是1或2
            host: UI程序的IP地址
            port: UI程序的端口号
            use_linear_conflict: 是否使用线性冲突优化（更高效的启发函数）
        """
        # 验证ID是否有效
        if solver_id not in [1, 2]:
            raise ValueError("Solver ID 必须是 1 或 2")
        
        # 保存参数
        self.solver_id = solver_id
        self.host = host
        self.port = port
        self.use_linear_conflict = use_linear_conflict
        
        # socket连接对象，初始为None
        self.socket: Optional[socket.socket] = None
        
        # 运行状态标志
        self.running = False
        
        # 当前棋盘状态
        self.current_state: Optional[PuzzleState] = None
    
    def _log(self, message: str, level: str = "INFO"):
        """
        打印日志到控制台
        
        参数:
            message: 日志内容
            level: 日志级别（INFO, SEND, RECV, SUCCESS, ERROR, CALC）
        """
        # 获取当前时间
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据级别选择图标
        prefix = {
            "INFO": "ℹ️ ",      # 普通信息
            "SEND": "📤",       # 发送消息
            "RECV": "📥",       # 接收消息
            "SUCCESS": "✅",    # 成功
            "ERROR": "❌",      # 错误
            "CALC": "🧮"        # 计算中
        }.get(level, "")        # .get() 方法在键不存在时返回默认值""
        
        # 格式化输出
        # :^7 表示居中对齐，宽度为7
        print(f"[{timestamp}] [{level:^7}] {prefix} {message}")
    
    def connect(self) -> bool:
        """
        连接到UI程序
        
        返回值:
            True表示连接成功，False表示失败
        """
        try:
            # 创建TCP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 连接到服务器
            # connect()函数接受一个元组 (host, port)
            self.socket.connect((self.host, self.port))
            
            self._log(f"正在连接到 {self.host}:{self.port}...")
            
            # 创建并发送连接请求消息
            connect_msg = Message(
                msg_type=MessageType.CONNECT,
                solver_id=self.solver_id
            )
            send_message(self.socket, connect_msg)
            self._log(f"发送连接请求 (Solver {self.solver_id})", "SEND")
            
            # 等待服务器的欢迎响应
            response = recv_message(self.socket)
            
            # 检查是否收到WELCOME消息
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
        """
        运行主循环
        持续接收消息并处理
        """
        # 先尝试连接
        if not self.connect():
            return  # 连接失败则退出
        
        self.running = True
        self._log("等待游戏开始...")
        
        try:
            # 主循环：持续接收和处理消息
            while self.running:
                # 接收消息（会阻塞直到收到）
                msg = recv_message(self.socket)
                
                if not msg:
                    # 收到None说明连接断开
                    self._log("连接已断开", "ERROR")
                    break
                
                # 处理消息
                self._handle_message(msg)
        
        except KeyboardInterrupt:
            # 用户按Ctrl+C中断
            self._log("用户中断", "INFO")
        except Exception as e:
            self._log(f"运行错误: {str(e)}", "ERROR")
        finally:
            # 无论如何都要清理资源
            self._cleanup()
    
    def _handle_message(self, msg: Message):
        """
        处理接收到的消息
        
        参数:
            msg: 接收到的消息对象
        """
        
        if msg.msg_type == MessageType.STATE:
            # 收到棋盘状态更新
            # 从消息中的board_data创建PuzzleState对象
            self.current_state = PuzzleState(msg.board_data)
            step = msg.step_num
            self._log(f"收到棋盘状态 (当前步数: {step})", "RECV")
        
        elif msg.msg_type == MessageType.YOUR_TURN:
            # 轮到我行动了！
            self._log(f"轮到 Solver {self.solver_id} 行动", "RECV")
            # 计算并发送下一步
            self._make_move()
        
        elif msg.msg_type == MessageType.SOLVED:
            # 游戏完成
            self._log(f"🎉 游戏完成！总步数: {msg.total_steps}", "SUCCESS")
            self._log("等待新游戏...", "INFO")
            # 注意：不设置running=False，继续等待新游戏
        
        elif msg.msg_type == MessageType.NOSOLUTION:
            # 题目无解
            self._log("题目无解", "ERROR")
            self._log("等待新题目...", "INFO")
        
        elif msg.msg_type == MessageType.ERROR:
            # 收到错误消息
            self._log(f"收到错误: {msg.error_msg}", "ERROR")
    
    def _make_move(self):
        """
        计算并发送下一步移动
        
        这是核心逻辑：
        1. 使用IDA*算法计算完整解法
        2. 只发送第一步（下一步）
        """
        # 检查是否有棋盘状态
        if not self.current_state:
            self._log("无法移动：没有棋盘状态", "ERROR")
            return
        
        # 检查是否已经是目标状态
        if self.current_state.is_goal():
            self._log("棋盘已经是目标状态", "INFO")
            return
        
        # 使用IDA*算法计算解法
        # time.time()返回当前时间戳（秒）
        start_time = time.time()
        solution = solve_puzzle(self.current_state, self.use_linear_conflict)
        elapsed = time.time() - start_time
        
        # 检查是否找到解法
        if not solution or len(solution) == 0:
            self._log("无法找到解法", "ERROR")
            return
        
        # 记录计算结果
        self._log(f"计算完成！当前需 {len(solution)} 步，耗时 {elapsed:.3f}s", "CALC")
        
        # 只取第一步（solution[0]）
        direction = solution[0]
        
        # 创建移动消息
        move_msg = Message(
            msg_type=MessageType.MOVE,
            solver_id=self.solver_id,
            direction=direction
        )
        
        # 发送消息
        send_message(self.socket, move_msg)
        
        self._log(f"发送移动: {direction.value}", "SEND")
    
    def _cleanup(self):
        """
        清理资源
        关闭socket连接
        """
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass  # 忽略关闭时的错误
        
        self._log("程序退出", "INFO")


# ==================== 程序入口 ====================

def main():
    """
    主函数：程序入口点
    解析命令行参数并启动Solver
    """
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='数字华容道 - 计算节点程序')
    
    # 添加 --id 参数（必需），只能是1或2
    parser.add_argument(
        '--id', 
        type=int, 
        required=True,            # 必须提供
        choices=[1, 2],           # 只能选1或2
        help='Solver ID (1 或 2)'
    )
    
    # 添加 --host 参数（可选），UI程序的IP地址
    parser.add_argument(
        '--host', 
        type=str, 
        default='127.0.0.1',      # 默认连接本机
        help='UI程序的IP地址 (默认: 127.0.0.1)'
    )
    
    # 添加 --port 参数（可选），UI程序的端口
    parser.add_argument(
        '--port', 
        type=int, 
        default=DEFAULT_PORT,
        help=f'UI程序的端口 (默认: {DEFAULT_PORT})'
    )
    
    # 添加 --no-linear-conflict 参数（可选），禁用线性冲突优化
    parser.add_argument(
        '--no-linear-conflict', 
        action='store_true',       # 存在则为True，不存在则为False
        help='不使用线性冲突优化 (用于区分两个Solver的算法)'
    )
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 打印启动信息
    print("=" * 50)
    print(f"  数字华容道 - Solver {args.id}")
    print(f"  目标: {args.host}:{args.port}")
    print(f"  算法: {'曼哈顿距离' if args.no_linear_conflict else '线性冲突'}")
    print("=" * 50)
    print()
    
    # 创建Solver实例
    solver = SolverNode(
        solver_id=args.id,
        host=args.host,
        port=args.port,
        use_linear_conflict=not args.no_linear_conflict  # 注意取反
    )
    
    # 运行
    solver.run()


# 当直接运行这个文件时执行main()
if __name__ == "__main__":
    main()
