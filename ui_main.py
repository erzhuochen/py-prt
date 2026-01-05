"""
数字华容道 - UI程序 (人机界面)
使用Tkinter显示游戏界面，作为TCP服务端接收计算程序的移动指令
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import socket
import threading
import time
import os
from datetime import datetime
from typing import Optional, Dict, List

from common import (
    PuzzleState, Direction, Message, MessageType,
    send_message, recv_message, is_solvable, load_puzzle_from_file,
    DEFAULT_PORT, DIRECTION_DELTA
)


class PuzzleUI:
    """数字华容道UI界面"""
    
    # 颜色配置
    COLORS = {
        'bg': '#1a1a2e',           # 深蓝色背景
        'tile': '#16213e',          # 方块背景
        'tile_text': '#eee',        # 方块文字
        'empty': '#0f0f23',         # 空位颜色
        'accent': '#e94560',        # 强调色
        'success': '#00d26a',       # 成功色
        'log_bg': '#0f3460',        # 日志背景
        'log_text': '#94bbe9',      # 日志文字
        'header': '#e94560',        # 标题色
        'solver1': '#00d4ff',       # Solver1颜色
        'solver2': '#ff6b6b',       # Solver2颜色
    }
    
    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.state: Optional[PuzzleState] = None
        self.step_count = 0
        self.solver_connections: Dict[int, socket.socket] = {}
        self.current_solver = 1  # 当前轮到的solver (1或2)
        self.game_running = False
        self.server_socket: Optional[socket.socket] = None
        self.solution_moves: List[Direction] = []
        
        # 初始化UI
        self._init_ui()
        
        # 启动服务器
        self._start_server()
        
        # 监控puzzle文件
        self._start_file_watcher()
    
    def _init_ui(self):
        """初始化UI界面"""
        self.root = tk.Tk()
        self.root.title("数字华容道 - 分布式求解系统")
        self.root.configure(bg=self.COLORS['bg'])
        self.root.geometry("900x650")
        self.root.resizable(False, False)
        
        # 主框架
        main_frame = tk.Frame(self.root, bg=self.COLORS['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题栏
        self._create_header(main_frame)
        
        # 内容区域
        content_frame = tk.Frame(main_frame, bg=self.COLORS['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # 左侧：棋盘
        self._create_board_area(content_frame)
        
        # 右侧：日志和状态
        self._create_info_area(content_frame)
        
        # 底部状态栏
        self._create_status_bar(main_frame)
    
    def _create_header(self, parent):
        """创建标题栏"""
        header_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        header_frame.pack(fill=tk.X)
        
        # 标题
        title_label = tk.Label(
            header_frame,
            text="🧩 数字华容道",
            font=('Microsoft YaHei', 24, 'bold'),
            fg=self.COLORS['header'],
            bg=self.COLORS['bg']
        )
        title_label.pack(side=tk.LEFT)
        
        # 步数显示
        self.step_frame = tk.Frame(header_frame, bg=self.COLORS['accent'], padx=15, pady=5)
        self.step_frame.pack(side=tk.RIGHT)
        
        self.step_label = tk.Label(
            self.step_frame,
            text="步数: 0",
            font=('Microsoft YaHei', 16, 'bold'),
            fg='white',
            bg=self.COLORS['accent']
        )
        self.step_label.pack()
    
    def _create_board_area(self, parent):
        """创建棋盘区域"""
        board_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        board_frame.pack(side=tk.LEFT, padx=20)
        
        # 棋盘容器
        self.board_container = tk.Frame(
            board_frame,
            bg=self.COLORS['empty'],
            padx=10,
            pady=10
        )
        self.board_container.pack()
        
        # 初始化空棋盘
        self.tile_labels: List[List[tk.Label]] = []
        self._create_empty_board(3)  # 默认3x3
        
        # 加载按钮
        btn_frame = tk.Frame(board_frame, bg=self.COLORS['bg'])
        btn_frame.pack(pady=20)
        
        load_btn = tk.Button(
            btn_frame,
            text="📁 加载题目文件",
            font=('Microsoft YaHei', 12),
            bg=self.COLORS['accent'],
            fg='white',
            activebackground='#ff6b8a',
            activeforeground='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            command=self._load_puzzle_file
        )
        load_btn.pack()
    
    def _create_empty_board(self, size: int):
        """创建空棋盘"""
        # 清除旧的标签
        for row in self.tile_labels:
            for label in row:
                label.destroy()
        self.tile_labels = []
        
        tile_size = 80 if size <= 4 else 60
        
        for i in range(size):
            row_labels = []
            for j in range(size):
                label = tk.Label(
                    self.board_container,
                    text="",
                    font=('Arial', 28, 'bold'),
                    width=3,
                    height=1,
                    bg=self.COLORS['empty'],
                    fg=self.COLORS['tile_text'],
                    relief=tk.FLAT
                )
                label.grid(row=i, column=j, padx=3, pady=3)
                row_labels.append(label)
            self.tile_labels.append(row_labels)
    
    def _create_info_area(self, parent):
        """创建信息区域"""
        info_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=20)
        
        # 连接状态
        conn_frame = tk.LabelFrame(
            info_frame,
            text=" 🔌 连接状态 ",
            font=('Microsoft YaHei', 12, 'bold'),
            fg=self.COLORS['log_text'],
            bg=self.COLORS['log_bg'],
            padx=10,
            pady=10
        )
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.solver1_status = tk.Label(
            conn_frame,
            text="● Solver 1: 等待连接...",
            font=('Microsoft YaHei', 11),
            fg='#888',
            bg=self.COLORS['log_bg'],
            anchor='w'
        )
        self.solver1_status.pack(fill=tk.X)
        
        self.solver2_status = tk.Label(
            conn_frame,
            text="● Solver 2: 等待连接...",
            font=('Microsoft YaHei', 11),
            fg='#888',
            bg=self.COLORS['log_bg'],
            anchor='w'
        )
        self.solver2_status.pack(fill=tk.X)
        
        # 通信日志
        log_frame = tk.LabelFrame(
            info_frame,
            text=" 📡 通信日志 ",
            font=('Microsoft YaHei', 12, 'bold'),
            fg=self.COLORS['log_text'],
            bg=self.COLORS['log_bg'],
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 日志文本框
        self.log_text = tk.Text(
            log_frame,
            font=('Consolas', 10),
            bg='#0a1628',
            fg=self.COLORS['log_text'],
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置日志标签颜色
        self.log_text.tag_configure('solver1', foreground=self.COLORS['solver1'])
        self.log_text.tag_configure('solver2', foreground=self.COLORS['solver2'])
        self.log_text.tag_configure('success', foreground=self.COLORS['success'])
        self.log_text.tag_configure('error', foreground='#ff4444')
        self.log_text.tag_configure('info', foreground='#888')
    
    def _create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = tk.Frame(parent, bg=self.COLORS['tile'])
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = tk.Label(
            status_frame,
            text="等待加载题目文件...",
            font=('Microsoft YaHei', 10),
            fg=self.COLORS['log_text'],
            bg=self.COLORS['tile'],
            anchor='w',
            padx=10,
            pady=5
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 显示IP地址
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except:
            ip = "127.0.0.1"
        
        ip_label = tk.Label(
            status_frame,
            text=f"IP: {ip}:{self.port}",
            font=('Consolas', 10),
            fg=self.COLORS['accent'],
            bg=self.COLORS['tile'],
            padx=10,
            pady=5
        )
        ip_label.pack(side=tk.RIGHT)
    
    def _log(self, message: str, tag: str = None):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.log_text.config(state=tk.NORMAL)
        
        if tag:
            self.log_text.insert(tk.END, f"[{timestamp}] ", 'info')
            self.log_text.insert(tk.END, f"{message}\n", tag)
        else:
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _update_board(self, highlight_success: bool = False):
        """更新棋盘显示"""
        if not self.state:
            return
        
        size = self.state.size
        
        # 如果大小变化，重新创建棋盘
        if len(self.tile_labels) != size:
            self._create_empty_board(size)
        
        for i in range(size):
            for j in range(size):
                val = self.state.board[i][j]
                label = self.tile_labels[i][j]
                
                if val == 0:
                    label.config(
                        text="",
                        bg=self.COLORS['empty']
                    )
                else:
                    # 成功时用绿色，否则用默认颜色
                    bg_color = self.COLORS['success'] if highlight_success else self.COLORS['tile']
                    label.config(
                        text=str(val),
                        bg=bg_color,
                        fg=self.COLORS['tile_text']
                    )
    
    def _update_step_count(self):
        """更新步数显示"""
        self.step_label.config(text=f"步数: {self.step_count}")
    
    def _set_status(self, text: str):
        """设置状态栏文字"""
        self.status_label.config(text=text)
    
    def _load_puzzle_file(self):
        """加载题目文件"""
        filepath = filedialog.askopenfilename(
            title="选择题目文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if filepath:
            self._load_puzzle(filepath)
    
    def _load_puzzle(self, filepath: str):
        """加载题目"""
        try:
            # 重置游戏状态
            self.game_running = False
            self.step_count = 0
            self.current_solver = 1
            
            self.state = load_puzzle_from_file(filepath)
            self._update_board()
            self._update_step_count()
            
            filename = os.path.basename(filepath)
            self._log(f"已加载题目: {filename}", 'info')
            
            # 检查可解性
            if is_solvable(self.state):
                self._log("题目可解 ✓", 'success')
                self._set_status(f"已加载 {filename} ({self.state.size}x{self.state.size}) - 等待计算程序连接...")
                
                # 检查是否两个solver都已连接
                if len(self.solver_connections) == 2:
                    self._start_game()
            else:
                self._log("题目无解 ✗", 'error')
                self._set_status("题目无解！")
                self._broadcast_no_solution()
        
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            self._log(f"加载失败: {str(e)}", 'error')
    
    def _start_server(self):
        """启动TCP服务器"""
        def server_thread():
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(2)
            
            self._log(f"服务器启动，监听端口 {self.port}", 'info')
            
            while True:
                try:
                    client_socket, addr = self.server_socket.accept()
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    ).start()
                except Exception as e:
                    if self.server_socket:
                        self._log(f"服务器错误: {str(e)}", 'error')
                    break
        
        threading.Thread(target=server_thread, daemon=True).start()
    
    def _handle_client(self, client_socket: socket.socket, addr):
        """处理客户端连接"""
        try:
            # 等待连接消息
            msg = recv_message(client_socket)
            
            if msg and msg.msg_type == MessageType.CONNECT:
                solver_id = msg.solver_id
                
                if solver_id in [1, 2]:
                    self.solver_connections[solver_id] = client_socket
                    
                    # 更新UI
                    self.root.after(0, lambda: self._update_solver_status(solver_id, True, addr[0]))
                    self.root.after(0, lambda: self._log(
                        f"Solver {solver_id} 已连接 ({addr[0]}:{addr[1]})",
                        f'solver{solver_id}'
                    ))
                    
                    # 发送欢迎消息
                    welcome = Message(msg_type=MessageType.WELCOME, solver_id=solver_id)
                    send_message(client_socket, welcome)
                    
                    # 检查是否可以开始游戏
                    if len(self.solver_connections) == 2 and self.state and is_solvable(self.state):
                        self.root.after(100, self._start_game)
                    
                    # 处理后续消息
                    self._handle_solver_messages(client_socket, solver_id)
                else:
                    self._log(f"无效的Solver ID: {solver_id}", 'error')
        
        except Exception as e:
            self._log(f"连接处理错误: {str(e)}", 'error')
        finally:
            # 清理连接
            for sid, sock in list(self.solver_connections.items()):
                if sock == client_socket:
                    del self.solver_connections[sid]
                    self.root.after(0, lambda s=sid: self._update_solver_status(s, False, None))
                    self.root.after(0, lambda s=sid: self._log(f"Solver {s} 已断开", 'error'))
                    break
            client_socket.close()
    
    def _handle_solver_messages(self, client_socket: socket.socket, solver_id: int):
        """处理Solver消息"""
        while True:
            try:
                msg = recv_message(client_socket)
                
                if not msg:
                    break
                
                if msg.msg_type == MessageType.MOVE:
                    self.root.after(0, lambda m=msg: self._process_move(m))
            
            except Exception as e:
                break
    
    def _process_move(self, msg: Message):
        """处理移动指令"""
        if not self.game_running:
            return
        
        solver_id = msg.solver_id
        direction = msg.direction
        
        # 验证是否轮到该solver
        if solver_id != self.current_solver:
            self._log(f"Solver {solver_id} 越权操作，当前轮到 Solver {self.current_solver}", 'error')
            return
        
        # 执行移动
        if self.state.move(direction):
            self.step_count += 1
            self._update_board()
            self._update_step_count()
            
            self._log(
                f"Solver {solver_id} 移动: {direction.value} (步骤 #{self.step_count})",
                f'solver{solver_id}'
            )
            
            # 检查是否完成
            if self.state.is_goal():
                self._game_complete()
            else:
                # 切换到下一个solver
                self.current_solver = 2 if self.current_solver == 1 else 1
                self._notify_next_solver()
        else:
            self._log(f"Solver {solver_id} 无效移动: {direction.value}", 'error')
    
    def _update_solver_status(self, solver_id: int, connected: bool, ip: Optional[str]):
        """更新Solver状态显示"""
        label = self.solver1_status if solver_id == 1 else self.solver2_status
        color = self.COLORS[f'solver{solver_id}'] if connected else '#888'
        
        if connected:
            text = f"● Solver {solver_id}: 已连接 ({ip})"
        else:
            text = f"● Solver {solver_id}: 等待连接..."
        
        label.config(text=text, fg=color)
    
    def _start_game(self):
        """开始游戏"""
        if self.game_running:
            return
        
        self.game_running = True
        self.current_solver = 1
        self._set_status("游戏进行中...")
        self._log("🎮 游戏开始！", 'success')
        
        # 通知第一个solver开始
        self._notify_next_solver()
    
    def _notify_next_solver(self):
        """通知下一个solver行动"""
        if self.current_solver not in self.solver_connections:
            self._log(f"Solver {self.current_solver} 未连接，游戏中止", 'error')
            self.game_running = False
            return
        
        sock = self.solver_connections[self.current_solver]
        
        # 发送状态和轮次通知
        state_msg = Message(
            msg_type=MessageType.STATE,
            step_num=self.step_count,
            board_data=self.state.board
        )
        send_message(sock, state_msg)
        
        turn_msg = Message(
            msg_type=MessageType.YOUR_TURN,
            solver_id=self.current_solver
        )
        send_message(sock, turn_msg)
    
    def _game_complete(self):
        """游戏完成"""
        self.game_running = False
        
        self._log(f"🎉 完成！共 {self.step_count} 步", 'success')
        self._set_status(f"游戏完成！总步数: {self.step_count} - 可加载新题目继续")
        
        # 更新棋盘样式显示成功
        self._update_board(highlight_success=True)
        
        # 广播完成消息（不断开连接）
        complete_msg = Message(
            msg_type=MessageType.SOLVED,
            total_steps=self.step_count
        )
        self._broadcast(complete_msg)
    
    def _broadcast_no_solution(self):
        """广播无解消息"""
        msg = Message(msg_type=MessageType.NOSOLUTION)
        self._broadcast(msg)
    
    def _broadcast(self, msg: Message):
        """广播消息给所有solver"""
        for solver_id, sock in self.solver_connections.items():
            try:
                send_message(sock, msg)
            except:
                pass
    
    def _start_file_watcher(self):
        """启动文件监控"""
        def watch():
            puzzle_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "puzzle.txt"
            )
            last_mtime = 0
            
            while True:
                try:
                    if os.path.exists(puzzle_file):
                        mtime = os.path.getmtime(puzzle_file)
                        if mtime > last_mtime:
                            last_mtime = mtime
                            # 等待文件写入完成
                            time.sleep(0.5)
                            self.root.after(0, lambda: self._load_puzzle(puzzle_file))
                except:
                    pass
                time.sleep(1)
        
        threading.Thread(target=watch, daemon=True).start()
    
    def run(self):
        """运行程序"""
        self.root.mainloop()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数字华容道 - UI程序')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'监听端口 (默认: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    app = PuzzleUI(port=args.port)
    app.run()


if __name__ == "__main__":
    main()
