# 数字华容道 - 分布式求解系统

## 项目简介

这是一个分布式数字华容道(Sliding Puzzle)游戏系统，支持局域网内多节点协作求解。

系统由三个程序组成：
- **UI程序** (`ui_main.py`): 显示游戏界面，接收并展示移动步骤，统计步数
- **计算程序** (`solver_node.py`): 交替向UI发送下一步移动指令 (需要2个实例)

## 快速开始

### 安装依赖

```bash
# Python 3.7+ 即可，Tkinter为Python标准库已内置
# 如需运行测试：
sudo apt install python3-tk
```

### 本地测试

在**三个终端**中分别运行：

**终端1 - UI程序:**
```bash
python ui_main.py
```

**终端2 - Solver 1:**
```bash
python solver_node.py --id 1 --host 127.0.0.1
```

**终端3 - Solver 2:**
```bash
python solver_node.py --id 2 --host 127.0.0.1
```

然后在UI中点击"加载题目文件"。

### 局域网测试

**在机器A运行UI:**
```bash
python ui_main.py --port 9527
```

**在机器B运行Solver 1:**
```bash
python solver_node.py --id 1 --host <机器A的IP> --port 9527
```

**在机器C运行Solver 2:**
```bash
python solver_node.py --id 2 --host <机器A的IP> --port 9527
```

## 文件格式

题目文件为纯文本格式，逗号分隔，0表示空位：

```
1,2,3
4,0,6
7,5,8
```

## 项目结构

```
py-prt/
├── common.py          # 公共模块：状态、协议、可解性判断
├── solver.py          # IDA*求解算法
├── ui_main.py         # UI程序 (Tkinter)
├── solver_node.py     # 计算节点程序
├── README.md          # 本文件
└── tests/
    ├── test1.txt # 测试文件
    └── test2.txt # 测试文件
    ...
```


## 协作证明

系统设计了以下机制证明三个程序协作：

1. **网络日志**: UI实时显示来自不同IP的消息
2. **Solver标识**: 每条移动指令携带Solver ID (1或2)
3. **交替计算**: Solver 1处理奇数步，Solver 2处理偶数步
4. **通信时间戳**: 记录每条消息的发送/接收时间

## 技术选型

- **GUI**: Tkinter (Python标准库)
- **网络**: TCP Socket
- **算法**: IDA* (迭代加深A*)，支持曼哈顿距离和线性冲突启发函数
