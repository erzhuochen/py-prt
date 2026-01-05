"""
数字华容道 - UI程序 (人机界面)
使用Tkinter显示游戏界面，作为TCP服务端接收计算程序的移动指令

这是整个分布式系统的"中枢"：
1. 显示游戏界面和棋盘
2. 作为服务器等待两个Solver连接
3. 协调两个Solver交替计算
"""

# ==================== 导入模块 ====================
import tkinter as tk                    # Python标准的GUI库，用于创建图形界面
from tkinter import ttk, messagebox, filedialog  # ttk是主题化控件，messagebox用于弹窗，filedialog用于文件选择对话框
import socket                           # 网络通信库，用于创建TCP服务器
import threading                        # 多线程库，让网络通信在后台运行，不阻塞界面
import time                             # 时间相关功能
import os                               # 操作系统接口，用于文件路径处理
from datetime import datetime           # 日期时间处理，用于日志时间戳
from typing import Optional, Dict, List # 类型提示，让代码更易读（Python 3.5+特性）

# 从我们自己的common模块导入需要的类和函数
from common import (
    PuzzleState,           # 棋盘状态类
    Direction,             # 移动方向枚举
    Message,               # 网络消息类
    MessageType,           # 消息类型枚举
    send_message,          # 发送消息的函数
    recv_message,          # 接收消息的函数
    is_solvable,           # 判断棋盘是否可解
    load_puzzle_from_file, # 从文件加载棋盘
    DEFAULT_PORT,          # 默认端口号
    DIRECTION_DELTA        # 方向偏移量
)


# ==================== 主类定义 ====================
class PuzzleUI:
    """
    数字华容道UI界面类
    
    这个类包含了整个程序的所有功能：
    - 界面显示（棋盘、日志、状态栏）
    - 网络服务器（接收Solver连接）
    - 游戏逻辑（交替调度、状态更新）
    """
    
    # 类变量：颜色配置（使用深色主题让界面更美观）
    COLORS = {
        'bg': '#1a1a2e',           # 深蓝色背景
        'tile': '#16213e',          # 数字方块的背景色
        'tile_text': '#eee',        # 数字方块的文字颜色
        'empty': '#0f0f23',         # 空位的颜色
        'accent': '#e94560',        # 强调色（按钮、标题等）
        'success': '#00d26a',       # 成功时的绿色
        'log_bg': '#0f3460',        # 日志区域的背景色
        'log_text': '#94bbe9',      # 日志文字颜色
        'header': '#e94560',        # 标题颜色
        'solver1': '#00d4ff',       # Solver 1 的专属颜色（蓝色）
        'solver2': '#ff6b6b',       # Solver 2 的专属颜色（红色）
    }
    
    def __init__(self, port: int = DEFAULT_PORT):
        """
        构造函数：初始化UI程序
        
        参数:
            port: TCP服务器监听的端口号，默认9527
        """
        # 保存端口号
        self.port = port
        
        # 当前棋盘状态，初始为None（还没加载题目）
        self.state: Optional[PuzzleState] = None
        
        # 当前步数计数器
        self.step_count = 0
        
        # 已连接的Solver字典，键是Solver ID(1或2)，值是socket连接
        # 例如: {1: <socket对象>, 2: <socket对象>}
        self.solver_connections: Dict[int, socket.socket] = {}
        
        # 当前轮到哪个Solver（1或2），初始为1
        self.current_solver = 1
        
        # 游戏是否正在进行的标志
        self.game_running = False
        
        # 服务器socket对象
        self.server_socket: Optional[socket.socket] = None
        
        # 解法步骤列表（预留字段，当前未使用）
        self.solution_moves: List[Direction] = []
        
        # 初始化UI界面（创建窗口和所有控件）
        self._init_ui()
        
        # 启动TCP服务器（在后台线程）
        self._start_server()
        
        # 启动文件监控（自动检测puzzle.txt的变化）
        self._start_file_watcher()
    
    # ==================== UI初始化方法 ====================
    
    def _init_ui(self):
        """
        初始化Tkinter界面
        创建主窗口和所有子组件
        """
        # 创建主窗口（Tk()返回一个窗口对象）
        self.root = tk.Tk()
        
        # 设置窗口标题（显示在标题栏）
        self.root.title("数字华容道 - 分布式求解系统")
        
        # 设置窗口背景颜色
        self.root.configure(bg=self.COLORS['bg'])
        
        # 设置窗口初始大小（宽度x高度）
        self.root.geometry("900x650")
        
        # 禁止调整窗口大小（False, False表示宽度和高度都不可调）
        self.root.resizable(False, False)
        
        # 创建主框架（Frame是一个容器，用于组织其他控件）
        # fill=tk.BOTH表示填充父容器的宽度和高度
        # expand=True表示随窗口扩展
        # padx/pady是外边距
        main_frame = tk.Frame(self.root, bg=self.COLORS['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 创建标题栏区域
        self._create_header(main_frame)
        
        # 【重要】先创建底部状态栏，使用 side=tk.BOTTOM
        # pack 是按顺序分配空间的，如果最后才 pack 状态栏，
        # 前面的 content_frame 设置了 expand=True 会占满所有剩余空间
        self._create_status_bar(main_frame)
        
        # 创建内容区域的框架
        content_frame = tk.Frame(main_frame, bg=self.COLORS['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # 创建左侧区域：棋盘
        self._create_board_area(content_frame)
        
        # 创建右侧区域：连接状态和通信日志
        self._create_info_area(content_frame)
    
    def _create_header(self, parent):
        """
        创建标题栏
        包含游戏标题和步数显示
        
        参数:
            parent: 父容器（这个组件将放在哪个容器里）
        """
        # 创建标题栏容器
        header_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        header_frame.pack(fill=tk.X)  # fill=tk.X表示水平方向填满父容器
        
        # 创建标题文字（Label是文本标签控件）
        title_label = tk.Label(
            header_frame,                              # 父容器
            text="🧩 数字华容道",                       # 显示的文字
            font=('Microsoft YaHei', 24, 'bold'),     # 字体、大小、粗体
            fg=self.COLORS['header'],                  # 前景色（文字颜色）
            bg=self.COLORS['bg']                       # 背景色
        )
        title_label.pack(side=tk.LEFT)  # 放在左边
        
        # 创建步数显示区域的框架（带背景色的小方块）
        self.step_frame = tk.Frame(
            header_frame, 
            bg=self.COLORS['accent'],  # 红色背景
            padx=15,                   # 内边距
            pady=5
        )
        self.step_frame.pack(side=tk.RIGHT)  # 放在右边
        
        # 创建步数数字标签
        self.step_label = tk.Label(
            self.step_frame,
            text="步数: 0",
            font=('Microsoft YaHei', 16, 'bold'),
            fg='white',
            bg=self.COLORS['accent']
        )
        self.step_label.pack()
    
    def _create_board_area(self, parent):
        """
        创建棋盘区域
        包含棋盘网格和加载按钮
        """
        # 棋盘区域的容器
        board_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        board_frame.pack(side=tk.LEFT, padx=20)
        
        # 棋盘的外框容器（深色背景，包裹住所有数字格子）
        self.board_container = tk.Frame(
            board_frame,
            bg=self.COLORS['empty'],
            padx=10,
            pady=10
        )
        self.board_container.pack()
        
        # 保存所有数字格子的二维数组
        # 例如: [[Label00, Label01, Label02], [Label10, Label11, Label12], ...]
        self.tile_labels: List[List[tk.Label]] = []
        
        # 创建一个默认的3x3空棋盘
        self._create_empty_board(3)
        
        # 创建按钮区域
        btn_frame = tk.Frame(board_frame, bg=self.COLORS['bg'])
        btn_frame.pack(pady=20)
        
        # 创建"加载题目"按钮
        load_btn = tk.Button(
            btn_frame,
            text="📁 加载题目文件",
            font=('Microsoft YaHei', 12),
            bg=self.COLORS['accent'],           # 背景色
            fg='white',                          # 文字颜色
            activebackground='#ff6b8a',         # 按下时的背景色
            activeforeground='white',           # 按下时的文字颜色
            relief=tk.FLAT,                     # 扁平样式（无边框）
            padx=20,
            pady=10,
            command=self._load_puzzle_file      # 点击时调用的函数
        )
        load_btn.pack()
    
    def _create_empty_board(self, size: int):
        """
        创建空棋盘（或重新创建）
        
        参数:
            size: 棋盘大小（3表示3x3，4表示4x4）
        """
        # 先销毁旧的格子（如果有的话）
        for row in self.tile_labels:
            for label in row:
                label.destroy()  # 销毁控件，释放资源
        self.tile_labels = []  # 清空列表
        
        # 根据棋盘大小决定格子尺寸
        tile_size = 80 if size <= 4 else 60
        
        # 嵌套循环创建size x size个格子
        for i in range(size):       # 行
            row_labels = []
            for j in range(size):   # 列
                # 每个格子是一个Label控件
                label = tk.Label(
                    self.board_container,              # 父容器
                    text="",                           # 初始文字为空
                    font=('Arial', 28, 'bold'),
                    width=3,                           # 宽度（字符数）
                    height=1,                          # 高度（行数）
                    bg=self.COLORS['empty'],
                    fg=self.COLORS['tile_text'],
                    relief=tk.FLAT
                )
                # 使用grid布局，按行列放置
                label.grid(row=i, column=j, padx=3, pady=3)
                row_labels.append(label)
            self.tile_labels.append(row_labels)
    
    def _create_info_area(self, parent):
        """
        创建信息区域（右侧）
        包含连接状态和通信日志
        """
        # 信息区域容器
        info_frame = tk.Frame(parent, bg=self.COLORS['bg'])
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=20)
        
        # ===== 连接状态区域 =====
        # LabelFrame是带标题的框架
        conn_frame = tk.LabelFrame(
            info_frame,
            text=" 🔌 连接状态 ",                   # 框架标题
            font=('Microsoft YaHei', 12, 'bold'),
            fg=self.COLORS['log_text'],
            bg=self.COLORS['log_bg'],
            padx=10,
            pady=10
        )
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Solver 1 状态标签
        self.solver1_status = tk.Label(
            conn_frame,
            text="● Solver 1: 等待连接...",
            font=('Microsoft YaHei', 11),
            fg='#888',                             # 灰色表示未连接
            bg=self.COLORS['log_bg'],
            anchor='w'                             # 文字左对齐
        )
        self.solver1_status.pack(fill=tk.X)
        
        # Solver 2 状态标签
        self.solver2_status = tk.Label(
            conn_frame,
            text="● Solver 2: 等待连接...",
            font=('Microsoft YaHei', 11),
            fg='#888',
            bg=self.COLORS['log_bg'],
            anchor='w'
        )
        self.solver2_status.pack(fill=tk.X)
        
        # ===== 通信日志区域 =====
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
        
        # 日志文本框（Text控件支持多行文本和格式化）
        self.log_text = tk.Text(
            log_frame,
            font=('Consolas', 10),                 # 等宽字体，适合日志
            bg='#0a1628',                          # 深色背景
            fg=self.COLORS['log_text'],
            relief=tk.FLAT,
            wrap=tk.WORD,                          # 按单词换行
            state=tk.DISABLED                      # 初始禁用编辑
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 配置文本标签（tag）的颜色
        # 标签可以让同一个Text控件显示不同颜色的文字
        self.log_text.tag_configure('solver1', foreground=self.COLORS['solver1'])  # Solver1用蓝色
        self.log_text.tag_configure('solver2', foreground=self.COLORS['solver2'])  # Solver2用红色
        self.log_text.tag_configure('success', foreground=self.COLORS['success'])  # 成功用绿色
        self.log_text.tag_configure('error', foreground='#ff4444')                 # 错误用红色
        self.log_text.tag_configure('info', foreground='#888')                     # 信息用灰色
    
    def _create_status_bar(self, parent):
        """
        创建底部状态栏
        显示当前状态和服务器IP地址
        """
        status_frame = tk.Frame(parent, bg=self.COLORS['tile'])
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 状态文字（左边）
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
        
        # 获取本机IP地址
        try:
            hostname = socket.gethostname()            # 获取计算机名
            ip = socket.gethostbyname(hostname)        # 根据计算机名获取IP
        except:
            ip = "127.0.0.1"                           # 获取失败则显示本地回环地址
        
        # IP地址标签（右边）
        ip_label = tk.Label(
            status_frame,
            text=f"IP: {ip}:{self.port}",              # f-string格式化
            font=('Consolas', 10),
            fg=self.COLORS['accent'],
            bg=self.COLORS['tile'],
            padx=10,
            pady=5
        )
        ip_label.pack(side=tk.RIGHT)
    
    # ==================== 工具方法 ====================
    
    def _log(self, message: str, tag: str = None):
        """
        添加一条日志到日志区域
        
        参数:
            message: 日志内容
            tag: 文本标签（决定颜色），如'solver1', 'error', 'success'
        """
        # 获取当前时间，格式化为 时:分:秒
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Text控件默认是DISABLED状态（只读），需要先启用才能写入
        self.log_text.config(state=tk.NORMAL)
        
        if tag:
            # 有标签时，时间戳用灰色，内容用标签指定的颜色
            self.log_text.insert(tk.END, f"[{timestamp}] ", 'info')
            self.log_text.insert(tk.END, f"{message}\n", tag)
        else:
            # 没有标签时，全部用默认颜色
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # 自动滚动到最新内容
        self.log_text.see(tk.END)
        
        # 写入完成后重新禁用编辑
        self.log_text.config(state=tk.DISABLED)
    
    def _update_board(self, highlight_success: bool = False):
        """
        更新棋盘显示
        根据self.state的内容刷新所有格子
        
        参数:
            highlight_success: 是否用绿色高亮显示（游戏完成时）
        """
        if not self.state:
            return  # 还没加载题目，不更新
        
        size = self.state.size
        
        # 如果棋盘大小变化了（比如从3x3变成4x4），重新创建格子
        if len(self.tile_labels) != size:
            self._create_empty_board(size)
        
        # 遍历棋盘的每个位置
        for i in range(size):
            for j in range(size):
                val = self.state.board[i][j]       # 获取这个位置的数字
                label = self.tile_labels[i][j]     # 获取对应的Label控件
                
                if val == 0:
                    # 空位：不显示文字，用深色背景
                    label.config(
                        text="",
                        bg=self.COLORS['empty']
                    )
                else:
                    # 有数字：显示数字，根据参数决定背景色
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
        """设置底部状态栏的文字"""
        self.status_label.config(text=text)
    
    # ==================== 文件加载 ====================
    
    def _load_puzzle_file(self):
        """
        弹出文件选择对话框，让用户选择题目文件
        """
        # filedialog.askopenfilename() 会弹出一个文件选择窗口
        filepath = filedialog.askopenfilename(
            title="选择题目文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__))  # 初始目录为程序所在目录
        )
        
        # 如果用户选择了文件（没有点取消）
        if filepath:
            self._load_puzzle(filepath)
    
    def _load_puzzle(self, filepath: str):
        """
        加载题目文件并开始游戏
        
        参数:
            filepath: 题目文件的完整路径
        """
        try:
            # 重置游戏状态
            self.game_running = False
            self.step_count = 0
            self.current_solver = 1
            
            # 从文件加载棋盘状态（调用common模块的函数）
            self.state = load_puzzle_from_file(filepath)
            
            # 更新UI
            self._update_board()
            self._update_step_count()
            
            # 获取文件名（不含路径）
            filename = os.path.basename(filepath)
            self._log(f"已加载题目: {filename}", 'info')
            
            # 检查题目是否可解
            if is_solvable(self.state):
                self._log("题目可解 ✓", 'success')
                self._set_status(f"已加载 {filename} ({self.state.size}x{self.state.size})")
                
                # 如果两个Solver都已经连接了，立即开始游戏
                if len(self.solver_connections) == 2:
                    self._start_game()
            else:
                # 题目无解
                self._log("题目无解 ✗", 'error')
                self._set_status("题目无解！")
                self._broadcast_no_solution()  # 通知所有Solver
        
        except Exception as e:
            # 加载失败，弹出错误提示框
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            self._log(f"加载失败: {str(e)}", 'error')
    
    # ==================== 网络服务器 ====================
    
    def _start_server(self):
        """
        启动TCP服务器
        在后台线程中运行，避免阻塞UI
        """
        def server_thread():
            """服务器线程的主函数"""
            # 创建TCP socket
            # AF_INET表示使用IPv4
            # SOCK_STREAM表示使用TCP协议
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 设置socket选项：允许地址重用
            # 这样程序重启后可以立即绑定同一端口，不用等待超时
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 绑定到所有网络接口('0.0.0.0')的指定端口
            self.server_socket.bind(('0.0.0.0', self.port))
            
            # 开始监听，参数2表示最多允许2个等待连接
            self.server_socket.listen(2)
            
            # 记录日志（注意：这是在后台线程，但_log方法内部会处理线程安全）
            self._log(f"服务器启动，监听端口 {self.port}", 'info')
            
            # 无限循环等待连接
            while True:
                try:
                    # accept()会阻塞，直到有客户端连接
                    # 返回值：(客户端socket, 客户端地址)
                    client_socket, addr = self.server_socket.accept()
                    
                    # 为每个客户端连接创建一个新的线程处理
                    # daemon=True表示这是守护线程，主程序退出时会自动结束
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    ).start()
                except Exception as e:
                    if self.server_socket:
                        self._log(f"服务器错误: {str(e)}", 'error')
                    break
        
        # 创建并启动服务器线程
        threading.Thread(target=server_thread, daemon=True).start()
    
    def _handle_client(self, client_socket: socket.socket, addr):
        """
        处理一个客户端（Solver）的连接
        
        参数:
            client_socket: 客户端的socket对象
            addr: 客户端的地址 (IP, 端口)
        """
        try:
            # 等待客户端发送连接请求消息
            msg = recv_message(client_socket)
            
            # 检查是否是CONNECT类型的消息
            if msg and msg.msg_type == MessageType.CONNECT:
                solver_id = msg.solver_id  # 获取Solver的ID（1或2）
                
                # 验证ID是否有效
                if solver_id in [1, 2]:
                    # 保存这个连接
                    self.solver_connections[solver_id] = client_socket
                    
                    # 更新UI（必须通过root.after()在主线程执行）
                    # lambda是匿名函数，用于捕获当前的变量值
                    self.root.after(0, lambda: self._update_solver_status(solver_id, True, addr[0]))
                    self.root.after(0, lambda: self._log(
                        f"Solver {solver_id} 已连接 ({addr[0]}:{addr[1]})",
                        f'solver{solver_id}'
                    ))
                    
                    # 发送欢迎消息给客户端
                    welcome = Message(msg_type=MessageType.WELCOME, solver_id=solver_id)
                    send_message(client_socket, welcome)
                    
                    # 检查是否两个Solver都连接了，且题目已加载且可解
                    if len(self.solver_connections) == 2 and self.state and is_solvable(self.state):
                        # 延迟100毫秒后开始游戏
                        self.root.after(100, self._start_game)
                    
                    # 进入消息处理循环
                    self._handle_solver_messages(client_socket, solver_id)
                else:
                    self._log(f"无效的Solver ID: {solver_id}", 'error')
        
        except Exception as e:
            self._log(f"连接处理错误: {str(e)}", 'error')
        
        finally:
            # 无论如何，最后都要清理连接
            # 从连接字典中移除
            for sid, sock in list(self.solver_connections.items()):
                if sock == client_socket:
                    del self.solver_connections[sid]
                    # 更新UI显示为断开状态
                    self.root.after(0, lambda s=sid: self._update_solver_status(s, False, None))
                    self.root.after(0, lambda s=sid: self._log(f"Solver {s} 已断开", 'error'))
                    break
            # 关闭socket
            client_socket.close()
    
    def _handle_solver_messages(self, client_socket: socket.socket, solver_id: int):
        """
        持续接收Solver发来的消息
        
        参数:
            client_socket: 客户端socket
            solver_id: Solver的ID
        """
        while True:
            try:
                # 接收消息（会阻塞直到收到消息）
                msg = recv_message(client_socket)
                
                if not msg:
                    break  # 连接已断开
                
                # 如果是移动指令
                if msg.msg_type == MessageType.MOVE:
                    # 通过root.after()在主线程处理
                    # lambda m=msg 是为了"捕获"当前的msg值
                    self.root.after(0, lambda m=msg: self._process_move(m))
            
            except Exception as e:
                break  # 出错则退出循环
    
    # ==================== 游戏逻辑 ====================
    
    def _process_move(self, msg: Message):
        """
        处理Solver发来的移动指令
        
        参数:
            msg: 包含移动信息的消息对象
        """
        # 游戏没在进行中则忽略
        if not self.game_running:
            return
        
        solver_id = msg.solver_id      # 发送方的ID
        direction = msg.direction       # 移动方向
        
        # 验证是否轮到这个Solver
        if solver_id != self.current_solver:
            self._log(f"Solver {solver_id} 越权操作，当前轮到 Solver {self.current_solver}", 'error')
            return
        
        # 尝试执行移动
        if self.state.move(direction):
            # 移动成功
            self.step_count += 1
            self._update_board()
            self._update_step_count()
            
            # 记录日志
            self._log(
                f"Solver {solver_id} 移动: {direction.value} (步骤 #{self.step_count})",
                f'solver{solver_id}'
            )
            
            # 检查是否已经完成（达到目标状态）
            if self.state.is_goal():
                self._game_complete()
            else:
                # 没完成，切换到下一个Solver
                # 三元表达式：如果当前是1则变成2，否则变成1
                self.current_solver = 2 if self.current_solver == 1 else 1
                self._notify_next_solver()
        else:
            # 移动失败（无效移动）
            self._log(f"Solver {solver_id} 无效移动: {direction.value}", 'error')
    
    def _update_solver_status(self, solver_id: int, connected: bool, ip: Optional[str]):
        """
        更新Solver连接状态的显示
        
        参数:
            solver_id: Solver的ID
            connected: 是否已连接
            ip: 连接的IP地址
        """
        # 根据ID选择对应的标签
        label = self.solver1_status if solver_id == 1 else self.solver2_status
        
        # 根据连接状态选择颜色
        color = self.COLORS[f'solver{solver_id}'] if connected else '#888'
        
        # 根据连接状态设置文字
        if connected:
            text = f"● Solver {solver_id}: 已连接 ({ip})"
        else:
            text = f"● Solver {solver_id}: 等待连接..."
        
        # 更新标签
        label.config(text=text, fg=color)
    
    def _start_game(self):
        """开始游戏"""
        # 防止重复开始
        if self.game_running:
            return
        
        self.game_running = True
        self.current_solver = 1  # 从Solver 1开始
        self._set_status("游戏进行中...")
        self._log("🎮 游戏开始！", 'success')
        
        # 通知Solver 1开始第一步
        self._notify_next_solver()
    
    def _notify_next_solver(self):
        """
        通知下一个Solver该它行动了
        发送当前棋盘状态和YOUR_TURN消息
        """
        # 检查该Solver是否还在线
        if self.current_solver not in self.solver_connections:
            self._log(f"Solver {self.current_solver} 未连接，游戏中止", 'error')
            self.game_running = False
            return
        
        # 获取对应的socket
        sock = self.solver_connections[self.current_solver]
        
        # 发送当前棋盘状态
        state_msg = Message(
            msg_type=MessageType.STATE,
            step_num=self.step_count,
            board_data=self.state.board  # 发送二维数组
        )
        send_message(sock, state_msg)
        
        # 发送"轮到你了"的通知
        turn_msg = Message(
            msg_type=MessageType.YOUR_TURN,
            solver_id=self.current_solver
        )
        send_message(sock, turn_msg)
    
    def _game_complete(self):
        """游戏完成的处理"""
        self.game_running = False
        
        # 记录日志和更新状态
        self._log(f"🎉 完成！共 {self.step_count} 步", 'success')
        self._set_status(f"游戏完成！总步数: {self.step_count} - 可加载新题目继续")
        
        # 用绿色高亮显示棋盘
        self._update_board(highlight_success=True)
        
        # 广播完成消息给所有Solver
        complete_msg = Message(
            msg_type=MessageType.SOLVED,
            total_steps=self.step_count
        )
        self._broadcast(complete_msg)
    
    def _broadcast_no_solution(self):
        """广播"题目无解"消息给所有Solver"""
        msg = Message(msg_type=MessageType.NOSOLUTION)
        self._broadcast(msg)
    
    def _broadcast(self, msg: Message):
        """
        广播消息给所有已连接的Solver
        
        参数:
            msg: 要发送的消息
        """
        for solver_id, sock in self.solver_connections.items():
            try:
                send_message(sock, msg)
            except:
                pass  # 发送失败就忽略
    
    # ==================== 文件监控 ====================
    
    def _start_file_watcher(self):
        """
        启动文件监控线程
        自动检测puzzle.txt文件的变化并加载
        """
        def watch():
            """监控线程的主函数"""
            # 构建要监控的文件路径
            puzzle_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "puzzle.txt"
            )
            last_mtime = 0  # 上次的修改时间
            
            while True:
                try:
                    # 检查文件是否存在
                    if os.path.exists(puzzle_file):
                        # 获取文件的修改时间
                        mtime = os.path.getmtime(puzzle_file)
                        
                        # 如果修改时间变了，说明文件被更新了
                        if mtime > last_mtime:
                            last_mtime = mtime
                            # 等待0.5秒，确保文件写入完成
                            time.sleep(0.5)
                            # 在主线程加载文件
                            self.root.after(0, lambda: self._load_puzzle(puzzle_file))
                except:
                    pass  # 忽略任何错误
                
                # 每秒检查一次
                time.sleep(1)
        
        # 启动监控线程
        threading.Thread(target=watch, daemon=True).start()
    
    # ==================== 主循环 ====================
    
    def run(self):
        """
        运行程序
        进入Tkinter的主事件循环
        """
        # mainloop()会阻塞在这里，直到窗口关闭
        # 它持续处理用户输入、刷新界面等
        self.root.mainloop()


# ==================== 程序入口 ====================

def main():
    """
    主函数：程序的入口点
    """
    # 导入命令行参数解析库
    import argparse
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='数字华容道 - UI程序')
    
    # 添加--port参数，用于指定监听端口
    parser.add_argument(
        '--port', 
        type=int, 
        default=DEFAULT_PORT, 
        help=f'监听端口 (默认: {DEFAULT_PORT})'
    )
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 创建UI实例并运行
    app = PuzzleUI(port=args.port)
    app.run()


# 当直接运行这个文件时执行main()
# 如果这个文件被其他文件import，则不会执行
if __name__ == "__main__":
    main()
