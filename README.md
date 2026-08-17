# Panda 机械臂抓取仿真项目

基于 **ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2** 的 Franka Panda (fp3) 机械臂 Pick & Place 仿真系统。
支持笛卡尔空间运动规划、完整抓取流水线和 RViz 交互式运动规划面板。

---

## 目录

- [效果演示](#效果演示)
- [环境要求](#环境要求)
- [新电脑从零搭建流程](#新电脑从零搭建流程)
- [日常快速启动](#日常快速启动)
- [项目结构](#项目结构)
- [系统架构](#系统架构)
- [抓取流水线](#抓取流水线)
- [已实现功能](#已实现功能)
- [已知问题](#已知问题)
- [Jazzy 兼容性修复](#jazzy-兼容性修复)
- [故障速查](#故障速查)
- [相关文档](#相关文档)
- [未来规划](#未来规划)
- [许可](#许可)

---

## 效果演示

<!-- TODO: 录制仿真运行的 screen capture / GIF -->

| Gazebo 仿真 | RViz 运动规划 |
|------------|--------------|
| <!-- 截图 --> | <!-- 截图 --> |

---

## 环境要求

| 组件 | 版本 |
|------|------|
| 操作系统 | Ubuntu 24.04 |
| ROS 2 | Jazzy |
| Gazebo | Harmonic |
| MoveIt 2 | Jazzy 适配版 |
| Python | 3.12+ |
| 物理引擎 | Bullet-featherstone |

---

## 新电脑从零搭建流程

在一台全新安装的 Ubuntu 24.04 上，按以下步骤操作。

### 第一步 — 安装 ROS 2 Jazzy

```bash
# 启用 universe 仓库并添加 ROS 2 apt key
sudo apt update && sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-jazzy-desktop
```

### 第二步 — 安装 Gazebo Harmonic + ros_gz 桥接

```bash
sudo apt install -y ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge
```

### 第三步 — 安装 MoveIt 2

```bash
sudo apt install -y ros-jazzy-moveit
```

### 第四步 — 安装 ros2_control + 控制器

```bash
sudo apt install -y ros-jazzy-ros2-control ros-jazzy-ros2-controllers
sudo apt install -y ros-jazzy-joint-state-broadcaster ros-jazzy-joint-trajectory-controller
```

### 第五步 — 安装 xacro 与工具

```bash
sudo apt install -y ros-jazzy-xacro ros-jazzy-robot-state-publisher
```

### 第六步 — 克隆本仓库

```bash
git clone git@github.com:<你的用户名>/panda_grasp_ws.git ~/panda_grasp_ws
```

> 将 `<你的用户名>` 替换为你的 GitHub 用户名。

### 第七步 — 编译工作空间

```bash
cd ~/panda_grasp_ws
colcon build --symlink-install
```

### 第八步 — 加载工作空间环境

```bash
source ~/panda_grasp_ws/install/setup.bash
```

> 💡 **建议**：将环境加载命令写入 `~/.bashrc`，省去每次手动 source：
> ```bash
> echo "source ~/panda_grasp_ws/install/setup.bash" >> ~/.bashrc
> ```

### 第九步 — 验证编译结果

```bash
ros2 pkg list | grep panda
```

正常情况下应看到：
```
franka_description
panda_grasp_sim
panda_moveit_config
```

### 第十步 — 启动仿真

```bash
# 仅 Gazebo 仿真（不含 MoveIt / RViz）
ros2 launch panda_grasp_sim sim.launch.py
```

> Gazebo 窗口将出现地面、桌子、绿色方块和 Panda 机械臂。

如果一切正常，就可以运行抓取脚本了。参见下方的[日常快速启动](#日常快速启动)。

---

## 日常快速启动

编译并加载环境后，日常使用流程如下：

### 1. 编译（修改代码后）

```bash
cd ~/panda_grasp_ws
colcon build --symlink-install
source install/setup.bash
```

### 2. 启动仿真（仅 Gazebo）

```bash
ros2 launch panda_grasp_sim sim.launch.py
```

Gazebo 窗口将出现桌子、绿色物块（3cm）和 Panda 机械臂。

### 3. 启动完整系统（Gazebo + MoveIt 2 + RViz）

```bash
ros2 launch panda_grasp_sim sim_with_moveit.launch.py
```

**启动时序：**

| 时间  | 动作 |
|-------|------|
| T+0s  | Gazebo 仿真世界 + `robot_state_publisher` + `ros_gz_bridge`（`/clock` 同步） |
| T+3s  | 在 Gazebo 中生成机器人实体 |
| T+6s  | 加载 ros2_control 控制器 + 启动 `move_group` |
| T+8s  | 启动 RViz |

### 4. 运行抓取脚本

打开**新终端**，加载环境后执行：

```bash
# 基础测试：运动到 HOME 位姿（关节空间规划）
ros2 run panda_grasp_sim pick_place

# 完整抓取流水线（笛卡尔空间规划）
ros2 run panda_grasp_sim pick_place_full

# 笛卡尔运动测试：垂直上升 5cm
ros2 run panda_grasp_sim cartesian_test

# 夹爪开合测试
ros2 run panda_grasp_sim hand_grasp_test

# TF 诊断：持续打印末端位姿
ros2 run panda_grasp_sim hand_tf_test
```

### 5. 手动控制测试（无需 Python 脚本）

```bash
# 查看控制器状态（3 个都应显示 active）
ros2 control list_controllers

# 手臂运动到 HOME 位姿
ros2 action send_goal /fp3_arm_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{ trajectory: { joint_names: ['fp3_joint1','fp3_joint2','fp3_joint3',
    'fp3_joint4','fp3_joint5','fp3_joint6','fp3_joint7'],
    points: [ { positions: [0.0, -0.785, 0.0, -2.356, 0.0, 1.57, 0.785],
      time_from_start: { sec: 3, nanosec: 0 } } ] } }"

# 夹爪闭合（0.0m）/ 张开（0.04m）—— 两个手指都要写
ros2 action send_goal /fp3_gripper_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  "{ trajectory: { joint_names: ['fp3_finger_joint1', 'fp3_finger_joint2'],
    points: [ { positions: [0.0, 0.0], time_from_start: { sec: 1, nanosec: 0 } } ] } }"
```

---

## 项目结构

```
panda_grasp_ws/
├── src/
│   ├── franka_description/         # 上游库（已并入本仓库）：Franka 机器人 URDF / 模型 / 参数
│   │   ├── robots/fp3/             # Panda fp3 配置（关节限位 / 运动学 / 惯量）
│   │   ├── robots/common/          # 公共 xacro 宏
│   │   ├── end_effectors/          # 末端执行器（Franka Hand / Cobot Pump）
│   │   └── meshes/                 # 碰撞（STL）和视觉（DAE）网格
│   │
│   ├── panda_grasp_sim/            # 核心：Gazebo 仿真 + Python 抓取脚本
│   │   ├── launch/
│   │   │   ├── sim.launch.py              # Gazebo 单独启动
│   │   │   └── sim_with_moveit.launch.py  # Gazebo + MoveIt 2 + RViz
│   │   ├── urdf/
│   │   │   └── panda.urdf.xacro           # 机器人 URDF（含 ros2_control 硬件插件）
│   │   ├── config/
│   │   │   └── panda_controllers.yaml     # ros2_control 控制器配置
│   │   ├── worlds/
│   │   │   └── grasp_world.sdf            # Gazebo 仿真世界（桌子 + 抓取物块）
│   │   └── panda_grasp_sim/
│   │       ├── pick_place.py              # 关节空间 HOME 运动测试
│   │       ├── pick_place_full.py         # 完整抓取流水线
│   │       ├── cartesian_test.py          # 笛卡尔空间运动测试
│   │       ├── hand_grasp_test.py         # 夹爪开合测试
│   │       └── hand_tf_test.py            # TF 诊断（末端位姿监控）
│   │
│   └── panda_moveit_config/        # MoveIt 2 配置包（Setup Assistant 自动生成）
│       ├── config/
│       │   ├── panda.srdf                   # 语义描述（规划组 / 碰撞矩阵 / 末端执行器）
│       │   ├── kinematics.yaml              # KDL 运动学求解器配置
│       │   ├── joint_limits.yaml            # 安全关节限位（缩放到 10%）
│       │   ├── ompl_planning.yaml           # OMPL 规划管线
│       │   ├── pilz_industrial_motion_planner_planning.yaml
│       │   ├── moveit_controllers.yaml      # MoveIt → 控制器映射
│       │   └── moveit.rviz                  # RViz 配置
│       └── launch/
│
├── docs/
│   ├── launch_file_guide.md         # Launch 文件架构详解
│   ├── gazebo_troubleshooting.md    # Gazebo 仿真踩坑记录
│   ├── debugging_handbook.md        # 6 级故障排查手册
│   ├── moveitpy_bug_fixes.md        # MoveItPy Bug 修复总结
│   └── project_log.md               # 项目开发日志
│
├── README.md
└── .gitignore
```

---

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
  （/tf 发布）                       （Gazebo 实体生成）
          │                                 │
     TF 树                          Gazebo Harmonic
  （所有关节变换）                   + gz_ros2_control 插件
          │                          + panda_controllers.yaml
          │                                 │
          └───────┬───────    controller_manager
                  │                    │
             MoveIt 2             ├── joint_state_broadcaster
             （move_group）         │     → /joint_states
                  │               ├── fp3_arm_controller
                  │               │     → /fp3_arm_controller/follow_joint_trajectory
     MoveItPy Python 脚本          └── fp3_gripper_controller
     ├── MoveItConfigsBuilder           → /fp3_gripper_controller/follow_joint_trajectory
     ├── 规划：OMPL（关节空间）/ Pilz LIN（笛卡尔空间）
     └── 执行：ActionClient → FollowJointTrajectory
```

### 规划组

| 规划组 | 关节 | 运动学求解器 | 用途 |
|--------|------|-------------|------|
| `arm` | fp3_joint1 ~ fp3_joint7（7-DOF） | KDL | 手臂运动规划 |
| `gripper` | fp3_finger_joint1（1-DOF） | 无 IK | 夹爪控制 |

### 控制器

| 控制器 | 类型 | 关节 | 用途 |
|--------|------|------|------|
| `joint_state_broadcaster` | JointStateBroadcaster | 全部 8 关节 | 发布 `/joint_states` |
| `fp3_arm_controller` | JointTrajectoryController | fp3_joint1–7 | 手臂轨迹跟踪 |
| `fp3_gripper_controller` | JointTrajectoryController | fp3_finger_joint1 | 夹爪轨迹跟踪 |

### 仿真世界

Gazebo 世界（`grasp_world.sdf`）包含：

| 元素 | 参数 |
|------|------|
| 地面 | 10 × 10 m |
| 桌子 | 2 × 2 × 0.1 m，中心 x = 0.5 |
| 抓取物块 | 3 cm 绿色方块，x = 0.6，z = 0.115，质量 20 g |
| 物理引擎 | Bullet-featherstone |

---

## 抓取流水线

`pick_place_full.py` 实现的完整抓取流程：

```
1. 初始化
   ├── 读取 /joint_states 获取当前关节角度
   ├── MoveItPy 初始化（含 planning_pipelines 修复）
   └── PlanningSceneMonitor 加载碰撞物体

2. 预备阶段
   ├── TF 查询末端 TCP 6-DOF 位姿
   └── 定义目标：预抓取点（z = 0.215）/ 抓取点（z = 0.118）

3. 抓取执行
   ├── 移动到预抓取点   （Pilz LIN，笛卡尔直线）
   ├── 夹爪张开          （ActionClient → fp3_gripper_controller，0.04 m）
   ├── 下降到抓取点     （Pilz LIN，笛卡尔直线）
   ├── 夹爪闭合          （ActionClient → fp3_gripper_controller，0.0 m）
   └── 抬起返回         （Pilz LIN，笛卡尔直线）

所有运动速度 / 加速度按 0.1 倍缩放（安全模式）。
```

---

## 已实现功能

- ✅ Franka Panda（fp3）7-DOF 手臂 + 平行夹爪在 Gazebo Harmonic 中完整仿真
- ✅ ros2_control 三控制器架构（关节状态广播 + 手臂轨迹 + 夹爪轨迹）
- ✅ MoveIt 2 集成（OMPL 关节空间规划 + Pilz LIN 笛卡尔空间规划）
- ✅ 笛卡尔直线运动规划（Pilz 工业运动规划器）
- ✅ 完整 Pick & Place 流水线：预抓取 → 张开 → 下降 → 闭合 → 抬起
- ✅ TF 末端位姿实时监控
- ✅ RViz 交互式运动规划面板
- ✅ 定时启动编排（Gazebo → spawn → 控制器 → MoveIt → RViz）
- ✅ 碰撞感知规划（PlanningSceneMonitor）

---

## 已知问题

> 📌 2026-08-17 更新：查明物体滑落的主因是 **Gazebo 不执行 URDF mimic 约束，夹爪只有一个手指在动**，物块根本夹不住。已改为控制器双指同步驱动（见 [`docs/夹爪单指运动问题修复记录.md`](docs/夹爪单指运动问题修复记录.md)），
> **端到端实测：`pick_place_full` 成功将 3cm 物块从桌面 (z=0.115) 夹起并悬停空中 (z=0.212)**。

| 问题 | 疑似原因 | 状态 |
|------|---------|------|
| 物体从夹爪滑落 | 夹爪只动一边（mimic 失效）→ 已改为双指同步驱动并实测抓取成功 | ✅ 已修复 |
| 绿色方块消失 | 过轻物体（20g）在 Bullet-featherstone 物理引擎下不稳定 | 🔴 待修复 |

---

## Jazzy 兼容性修复

本项目在搭建过程中发现并解决了 ROS 2 Jazzy 与 MoveIt 2 之间的 **5 个关键兼容性问题**，
详见 [`docs/moveitpy_bug_fixes.md`](docs/moveitpy_bug_fixes.md)。简要汇总：

| # | 问题 | 修复方式 |
|---|------|---------|
| 1 | `MoveItPy` 构造函数不接受 `parameter_namespace` | 改用 `config_dict` 从 `MoveItConfigsBuilder` 传入完整配置 |
| 2 | `planning_pipelines` 参数名不匹配（Jazzy Bug） | 重命名为 `planning_pipelines.pipeline_names` + 补 `namespace` |
| 3 | `use_sim_time` 下 `set_start_state_to_current_state()` 失效 | 手动订阅 `/joint_states` 并构造 `RobotState` |
| 4 | `moveit.execute()` 在仿真时间下返回 ABORTED | 绕过 `TrajectoryExecutionManager`，用 `ActionClient` 直接发轨迹 |
| 5 | Gazebo 找不到 workspace 中的 mesh 文件 | launch 文件中设置 `GZ_SIM_RESOURCE_PATH` 包含本地 `install/` 路径 |

---

## 故障速查

| 现象 | 原因 | 参考 |
|------|------|------|
| Gazebo 白屏 | GPU / 显卡驱动问题 | [排查手册](docs/debugging_handbook.md) 第 0 级 |
| `move_group` 报错退出 | 参数或依赖缺失 | 查看终端红色 ERROR 行 |
| RViz Plan 失败 | `joint_states` 未发布或时钟同步问题 | [排查手册](docs/debugging_handbook.md) 第 5 级 |
| Plan 成功但机械臂不动 | 轨迹未送到控制器 | [排查手册](docs/debugging_handbook.md) 第 6 级 |
| 夹爪命令无效 | 控制器未加载，或轨迹缺少 `fp3_finger_joint2` | [排查手册](docs/debugging_handbook.md) 第 2/4 级 |

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

---

## 相关文档

- [`docs/launch_file_guide.md`](docs/launch_file_guide.md) — Launch 文件架构详解（启动时序、数据流）
- [`docs/gazebo_troubleshooting.md`](docs/gazebo_troubleshooting.md) — Gazebo 仿真常见踩坑与解决方案
- [`docs/debugging_handbook.md`](docs/debugging_handbook.md) — 6 级逐级排查手册
- [`docs/moveitpy_bug_fixes.md`](docs/moveitpy_bug_fixes.md) — MoveItPy 三个核心 Bug 及修复
- [`docs/project_log.md`](docs/project_log.md) — 项目开发进度日志

---

## 未来规划

- [ ] **视觉引导抓取** — 在 Gazebo 中添加 RGB-D 相机 + 物体位姿估计
- [ ] **多物体流水线** — 检测、抓取、分拣多个物体
- [ ] **力控抓取** — 建模夹爪力控，修复物体滑落问题
- [ ] **抓取质量评估** — 评估抓取稳定性，失败时重规划
- [ ] **自动化测试** — ROS 2 包 CI 流水线
- [ ] **Docker 支持** — 可复现的演示和开发环境

---

## 许可

`franka_description` 包来源于 [Franka Robotics](https://github.com/frankaemika/franka_description)，
遵循其原始许可（Apache 2.0）。

本项目其余代码由 **renjcx** 开发，采用 Apache License 2.0 许可。
