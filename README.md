# Panda 机械臂抓取仿真项目

基于 ROS2 Jazzy + Gazebo Harmonic + MoveIt2 的 Franka Panda (fp3) 机械臂仿真与抓取控制系统。

## 环境要求

| 组件 | 版本 |
|------|------|
| 操作系统 | Ubuntu 24.04 |
| ROS2 | Jazzy |
| Gazebo | Harmonic |
| MoveIt2 | Jazzy 适配版 |
| Python | 3.12+ |
| 物理引擎 | Bullet-featherstone |

### 依赖安装

```bash
# ROS2 Jazzy (完整桌面版)
sudo apt install ros-jazzy-desktop

# Gazebo Harmonic + ros_gz 桥接
sudo apt install ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge

# MoveIt2
sudo apt install ros-jazzy-moveit

# ros2_control + 控制器
sudo apt install ros-jazzy-ros2-control ros-jazzy-ros2-controllers
sudo apt install ros-jazzy-joint-state-broadcaster ros-jazzy-joint-trajectory-controller

# xacro & 工具
sudo apt install ros-jazzy-xacro ros-jazzy-robot-state-publisher
```

## 项目结构

```
panda_grasp_ws/
├── src/
│   ├── franka_description/      # 上游库：Franka 机器人 URDF/模型/参数
│   │   ├── robots/fp3/          # Panda fp3 模型配置 (关节限位/运动学/惯量)
│   │   ├── robots/common/       # 公共 xacro 宏
│   │   ├── end_effectors/       # 末端执行器 (Franka Hand / Cobot Pump)
│   │   └── meshes/              # 碰撞 (STL) 和视觉 (DAE) 网格
│   │
│   ├── panda_grasp_sim/         # 核心：Gazebo 仿真 + Python 抓取脚本
│   │   ├── launch/
│   │   │   ├── sim.launch.py          # 启动 Gazebo 仿真 (仅仿真)
│   │   │   └── sim_with_moveit.launch.py  # 仿真 + MoveIt2 + RViz
│   │   ├── urdf/
│   │   │   └── panda.urdf.xacro       # 机器人 URDF (含 ros2_control 硬件插件)
│   │   ├── config/
│   │   │   └── panda_controllers.yaml # ros2_control 控制器配置
│   │   ├── worlds/
│   │   │   └── grasp_world.sdf        # Gazebo 仿真世界 (桌子+抓取物块)
│   │   └── panda_grasp_sim/
│   │       ├── pick_place.py          # ⭐ 基础抓取：MoveItPy 规划 + 执行
│   │       ├── pick_place_full.py     # 完整抓取流水线 (预抓取→下降→闭合→抬起)
│   │       ├── cartesian_test.py      # 笛卡尔空间运动测试 (Pilz LIN 规划器)
│   │       ├── hand_grasp_test.py     # 夹爪开合测试
│   │       └── hand_tf_test.py        # TF 诊断工具 (末端位姿监控)
│   │
│   └── panda_moveit_config/     # MoveIt2 配置包 (Setup Assistant 自动生成)
│       ├── config/
│       │   ├── panda.srdf              # 语义描述 (规划组/碰撞矩阵/末端执行器)
│       │   ├── panda.urdf.xacro        # MoveIt 用 URDF (FakeSystem 硬件)
│       │   ├── kinematics.yaml         # KDL 运动学求解器配置
│       │   ├── joint_limits.yaml       # 安全关节限位 (缩放到 10%)
│       │   ├── ompl_planning.yaml      # OMPL 规划管线
│       │   ├── pilz_industrial_motion_planner_planning.yaml  # Pilz 工业规划器
│       │   ├── moveit_controllers.yaml # MoveIt → 控制器映射
│       │   └── moveit.rviz             # RViz 配置
│       └── launch/                     # MoveIt 启动文件 (demo/move_group/rviz/...)
│
├── panda.urdf                  # 预展开的 URDF (方便直接查看)
├── sim.launch.py文件详解.md     # Launch 文件架构详解
├── 踩坑总结_Panda_Gazebo.md     # Gazebo 仿真踩坑记录
├── 仿真故障排查手册.md           # 6 级故障排查手册
├── pick_place报错总结以及movitpy的bug.txt  # MoveItPy Bug 修复总结
└── 项目进度总结.txt             # 项目进度
```

## 快速开始

### 1. 编译

```bash
cd ~/panda_grasp_ws
colcon build --symlink-install
source install/setup.bash
```

### 2. 启动 Gazebo 仿真 (仅模拟)

```bash
ros2 launch panda_grasp_sim sim.launch.py
```

Gazebo 窗口将出现一张桌子、一个绿色物块和 Panda 机械臂。

### 3. 启动完整系统 (Gazebo + MoveIt2 + RViz)

```bash
ros2 launch panda_grasp_sim sim_with_moveit.launch.py
```

启动时序：
- T+0s: Gazebo 仿真世界 + robot_state_publisher + ros_gz_bridge
- T+3s: 在 Gazebo 中生成 Panda 机器人
- T+6s: 加载 ros2_control 控制器 + 启动 move_group
- T+8s: 启动 RViz

### 4. 运行抓取脚本

```bash
# 基础测试：运动到 HOME 位置 (关节空间规划)
ros2 run panda_grasp_sim pick_place

# 完整抓取流水线 (笛卡尔空间规划)
ros2 run panda_grasp_sim pick_place_full

# 笛卡尔运动测试
ros2 run panda_grasp_sim cartesian_test

# 夹爪测试
ros2 run panda_grasp_sim hand_grasp_test

# TF 诊断 (打印末端位姿)
ros2 run panda_grasp_sim hand_tf_test
```

### 5. 手动控制测试

```bash
# 查看控制器状态 (三个都应该显示 active)
ros2 control list_controllers

# 手臂运动：发送关节轨迹到 HOME 位置
ros2 action send_goal /fp3_arm_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{ trajectory: { joint_names: ['fp3_joint1','fp3_joint2','fp3_joint3',
    'fp3_joint4','fp3_joint5','fp3_joint6','fp3_joint7'],
    points: [ { positions: [0.0, -0.785, 0.0, -2.356, 0.0, 1.57, 0.785],
      time_from_start: { sec: 3, nanosec: 0 } } ] } }"

# 夹爪闭合 (0.0m) / 张开 (0.04m)
ros2 action send_goal /fp3_gripper_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{ trajectory: { joint_names: ['fp3_finger_joint1'],
    points: [ { positions: [0.0], time_from_start: { sec: 1, nanosec: 0 } } ] } }"
```

## 系统架构

```
                     panda.urdf.xacro
                           │
                   xacro.process_file()
                           │
                  /robot_description
                           │
          ┌────────────────┼────────────────┐
          │                                 │
  robot_state_publisher              ros_gz_sim create
  (/tf 发布)                         (Gazebo 实体生成)
          │                                 │
     TF 树                           Gazebo Harmonic
  (所有关节变换)                     + gz_ros2_control 插件
          │                          + panda_controllers.yaml
          │                                 │
          └───────┬───────    controller_manager
                  │                    │
             MoveIt2              ├── joint_state_broadcaster
             (move_group)         │     → /joint_states
                  │               ├── fp3_arm_controller
                  │               │     → /fp3_arm_controller/follow_joint_trajectory
     MoveItPy Python Scripts      └── fp3_gripper_controller
     ├── MoveItConfigsBuilder           → /fp3_gripper_controller/follow_joint_trajectory
     ├── 规划: OMPL (关节空间) / Pilz LIN (笛卡尔空间)
     └── 执行: ActionClient → FollowJointTrajectory
```

### 规划组

| 规划组 | 关节 | 运动学求解器 | 用途 |
|--------|------|-------------|------|
| `arm` | fp3_joint1 ~ fp3_joint7 (7DOF) | KDL | 手臂运动规划 |
| `gripper` | fp3_finger_joint1 (1DOF) | 无 IK | 夹爪控制 |

### 控制器

| 控制器 | 类型 | 关节 | 用途 |
|--------|------|------|------|
| `joint_state_broadcaster` | JointStateBroadcaster | 全部 8 关节 | 发布 /joint_states |
| `fp3_arm_controller` | JointTrajectoryController | fp3_joint1-7 | 手臂轨迹跟踪 |
| `fp3_gripper_controller` | JointTrajectoryController | fp3_finger_joint1 | 夹爪轨迹跟踪 |

### 仿真世界

Gazebo 世界 (`grasp_world.sdf`) 包含：
- 地面平面 (10×10m)
- 桌子 (2×2×0.1m, 位置 x=0.5)
- 抓取物块 (3cm 绿色方块, 位置 x=0.6, z=0.115, 质量 20g)
- 物理引擎: Bullet-featherstone (mimic 关节需要)

## 抓取流水线

`pick_place_full.py` 实现的完整抓取流程：

```
1. 初始化
   ├── 读取 /joint_states 获取当前关节角度
   ├── MoveItPy 初始化 (含 planning_pipelines 修复)
   └── PlanningSceneMonitor 加载碰撞物体

2. 预备阶段
   ├── TF 查询末端 TCP 6D 位姿
   └── 定义目标: 预抓取点 (z=0.215) / 抓取点 (z=0.118)

3. 抓取执行
   ├── 移动到预抓取点   (Pilz LIN, 笛卡尔直线)
   ├── 夹爪张开          (ActionClient → fp3_gripper_controller, 0.04m)
   ├── 下降到抓取点     (Pilz LIN, 笛卡尔直线)
   ├── 夹爪闭合          (ActionClient → fp3_gripper_controller, 0.0m)
   └── 抬起返回         (Pilz LIN, 笛卡尔直线)

所有运动速度/加速度按 0.1 倍缩放 (安全模式)
```

## 已知问题与修复

本项目在搭建过程中解决了 ROS2 Jazzy + MoveIt2 组合的几个关键兼容性问题：

### 1. MoveItPy 构造函数参数

MoveItPy 不接受 `parameter_namespace` 参数，需要使用 `config_dict` 从 `MoveItConfigsBuilder` 传入完整配置。

```python
from moveit_configs_utils import MoveItConfigsBuilder
config = MoveItConfigsBuilder("panda", package_name="panda_moveit_config").to_moveit_configs().to_dict()
moveit = MoveItPy(node_name="moveit_py", config_dict=config)
```

### 2. planning_pipelines 参数名不匹配 (Jazzy Bug)

`MoveItConfigsBuilder` 生成 `planning_pipelines`，但 MoveItCpp 读取的是 `planning_pipelines.pipeline_names`，两者不一致导致所有规划器加载失败。

```python
pipelines = config.pop("planning_pipelines")
config["planning_pipelines.pipeline_names"] = pipelines
config["planning_pipelines.namespace"] = ""
```

### 3. use_sim_time 导致 MoveItPy 无法获取当前状态

`set_start_state_to_current_state()` 在仿真时间下因为 CurrentStateMonitor 的 /clock 同步问题而失效。修复：手动订阅 `/joint_states` 获取当前关节值，直接构造 `RobotState`。

### 4. moveit.execute() 返回 ABORTED

TrajectoryExecutionManager 的状态校验在仿真时间下失败。修复：绕过 `moveit.execute()`，直接用 `ActionClient` 向 `/fp3_arm_controller/follow_joint_trajectory` 发送轨迹。

### 5. Gazebo 找不到 Mesh 文件

Gazebo 默认不搜索本地 workspace 路径。修复：launch 文件在启动 Gazebo 前把 `franka_description` 安装路径加入 `GZ_SIM_RESOURCE_PATH`。

## 故障速查

| 现象 | 原因 | 参考文档 |
|------|------|---------|
| Gazebo 白屏 | GPU/显卡驱动问题 | [仿真故障排查手册](./仿真故障排查手册.md) 第 0 级 |
| move_group 报错退出 | 参数或依赖缺失 | 终端红色 ERROR 行 |
| RViz Plan 失败 | joint_states 未发布或时间同步 | [排查手册](./仿真故障排查手册.md) 第 5 级 |
| Plan 成功但机械臂不动 | 轨迹未送到控制器 | [排查手册](./仿真故障排查手册.md) 第 6 级 |
| 夹爪命令无效 | 控制器未加载或 mimic 冲突 | [排查手册](./仿真故障排查手册.md) 第 2/4 级 |

### 常用诊断命令

```bash
ros2 node list                          # 节点列表
ros2 topic list                         # Topic 列表
ros2 action list                        # Action 列表
ros2 control list_controllers           # 控制器状态
ros2 control list_hardware_interfaces   # 硬件接口状态
ros2 topic echo /joint_states --once    # 当前关节角度
ros2 topic echo /tf --once              # TF 树快照
```

## 其他文档

- [sim.launch.py 文件详解](./sim.launch.py文件详解.md) — Launch 文件架构与启动时序
- [踩坑总结 Panda Gazebo](./踩坑总结_Panda_Gazebo.md) — Gazebo 仿真环境搭建踩坑
- [仿真故障排查手册](./仿真故障排查手册.md) — 6 级逐级排查方法
- [pick_place 报错总结与 MoveItPy Bug](./pick_place报错总结以及movitpy的bug.txt) — MoveItPy 三个核心 Bug 的修复

## 许可

`franka_description` 来自 [Franka Robotics](https://github.com/frankaemika/franka_description)，遵循其原始许可。

本项目其余部分由 renjcx 开发。
