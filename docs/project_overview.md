# 项目全流程概览

> 从零到实现抓取的完整阶段划分。先讲主干，细节可结合其他文档深入。

---

## 项目一句话概括

在电脑上搭一个**虚拟的 Franka Panda 机械臂**，让它自动完成：**移动到绿色方块上方 → 下降 → 闭合夹爪 → 抬起**。全程是仿真（Gazebo），不碰真实硬件。

---

## 六大阶段

### ① 装环境

安装 ROS 2 Jazzy（机器人软件框架，负责各程序之间通信）、Gazebo Harmonic（物理仿真引擎）、MoveIt 2（运动规划库）、ros2_control（关节控制框架）。

**作用**：这是地基，后面所有东西都跑在这上面。

### ② 建机器人模型（franka_description 包）
用 URDF/Xacro 格式写机械臂的"图纸"：7 个手臂关节 + 夹爪的尺寸、连接关系、质量、关节限位。这个包是 Franka 官方开源的，直接拿来用。

官方包自带 `robots/fp3/fp3.urdf.xacro`（纯模型图纸，能显示外形但动不了）。导入后做的事：
1. **复用官方宏** — 在项目自己的 `panda.urdf.xacro` 里 include 官方宏文件，加载 fp3 的 4 个参数文件（关节限位 / 运动学 / 惯量 / 动力学）
2. **调用宏生成整条臂** — 传 `robot_type=fp3`、`hand=franka_hand`、`ros2_control=false`（关掉官方的真实硬件接口，仿真不用）
3. **补仿真专属内容**：
   - `world` 固定关节 —— 把机器人锚定到世界坐标系
   - ros2_control 块 —— `GazeboSimSystem` 插件 + 8 个关节的 command/state 接口 + 初始角度
   - gazebo 插件标签 —— 指向控制器配置 `panda_controllers.yaml`
4. **launch 时展开** — `xacro.process_file()` 展开成纯 URDF → 发布为 `/robot_description` → robot_state_publisher 据此发 TF，Gazebo 据此生成实体

> **为什么夹爪只有一个自由度？** 真实 Franka Hand 只有一个电机、两指机械耦合，物理上就是 1 个自由度，规划时不应有两个独立自由度。
> **但为什么 URDF 里两个手指是独立关节？** 因为 Gazebo Harmonic 的物理引擎**不执行 URDF mimic 约束**（已知上游 bug，`gazebosim/gz-sim#1684`，服务器日志会报 "does not support mimic constraints"），只声明 mimic 会导致 `finger_joint2` 完全不受控——只有一个手指会动。
> **实际架构**：物理层两个手指都是普通关节，由 `fp3_gripper_controller` 用相同的位置命令**同步驱动**；规划层在 `panda.srdf` 里声明 `<mimic_joint>`，让 MoveIt 仍把它当作 1 个自由度，且生成的轨迹自动展开两个手指关节。

### ③ 让机器人在 Gazebo 里"活"起来（panda_grasp_sim 包）
两件事：**把图纸装进物理世界**（有重力、有碰撞、有摩擦），**给机器人接上肌肉**（能接收命令、驱动关节）。
| 文件 | 管什么 | 一句话 |
|------|--------|--------|
| `worlds/grasp_world.sdf` | 仿真世界 | 搭场景：地面 + 桌子 + 绿色方块 |
| `urdf/panda.urdf.xacro` | 图纸 + 硬件接口 | 给图纸补上"接物理引擎的插头" |
| `config/panda_controllers.yaml` | 控制器配置 | 定义 3 个控制器：报状态、动胳膊、开夹爪 |
| `launch/sim.launch.py` | 启动编排 | 按正确顺序拉起所有进程 |

      ####  launch 编排 `sim.launch.py` —— 顺序启动，缺一不可
```
T+0s   设 GZ_SIM_RESOURCE_PATH（否则 Gazebo 找不到 mesh → 白屏）
       ├─ 启动 Gazebo（加载 grasp_world.sdf）
       ├─ 启动 robot_state_publisher（xacro → URDF → 发 /tf）
       └─ 启动时钟桥（Gazebo 时钟 ↔ ROS 时钟，不桥接 /tf 时间戳会错乱）
T+3s   等 Gazebo 就绪 → 把 /robot_description 发给 Gazebo 生成实体
T+6s   等机器人出生 → 加载 3 个控制器
```

为什么要排队：**controller_manager 不是独立进程**，它是 gz_ros2_control 插件在 Gazebo 内部启动的——机器人还没生成，它就不存在，spawner 会直接超时。

**作用**：一条命令 `ros2 launch panda_grasp_sim sim.launch.py` 拉起整条链。验证方式：`ros2 run panda_grasp_sim hand_grasp_test`（夹爪张开 → 闭合 → 再张开）。

####  至此的控制链路
```
你的命令
  → /fp3_arm_controller/follow_joint_trajectory（action）
  → 控制器插值（100Hz）
  → controller_manager → gz_ros2_control 插件
  → Gazebo 物理引擎（算重力/碰撞/摩擦）
  → 关节转动 → 3D 画面更新
```
**作用**：到这一步，机械臂在物理世界里"活"了——能报状态、能动、能夹。阶段④的 MoveIt 和阶段⑤的抓取脚本，最后都是走这条链路来驱动它的。

> 深入阅读：[`launch_file_guide.md`](launch_file_guide.md)（逐段讲 launch 文件）、[`gazebo_troubleshooting.md`](gazebo_troubleshooting.md)（本阶段踩过的 6 个坑）


### ④ 接入 MoveIt 2（panda_moveit_config 包）

**作用**：给机器人装"大脑"。你只说"末端去桌子上的某点、掌心朝下"，MoveIt 通过**逆运动学（IK）**自动算出 7 个关节各转多少度，并用 OMPL 算法规划出一条**避障的关节轨迹**。RViz 面板让你能手动拖拽目标点、点 Plan 看规划结果。

### ⑤ 写抓取脚本（pick_place_full.py）

用 MoveItPy 编程实现完整流程：

```
移动到预抓取点（方块上方）→ 张开夹爪 → 直线下降到抓取点 → 闭合夹爪 → 直线抬起
```

所有速度缩放到 0.1 倍（安全模式）。

**作用**：把阶段③④的能力串成一条自动流水线。

### ⑥ 调试与修复（贯穿全程）

过程中解决了 5 个 ROS 2 Jazzy 与 MoveIt 2 的兼容性 bug（MoveItPy 参数名不匹配、仿真时间下轨迹执行失败等，详见 [`moveitpy_bug_fixes.md`](moveitpy_bug_fixes.md)），还沉淀了故障排查手册。

---

## 当前状态

- ✅ 规划 + 控制全链路已跑通：机械臂能规划出轨迹、执行到抓取位姿、闭合夹爪
- 🔴 遗留问题在**物理层面**：夹爪夹不住 20g 的轻物体（会滑落/方块有时消失），需要调摩擦参数或做夹爪力控

---

## 一句话总结

整体就是 **"图纸 → 物理世界 → 肌肉 → 大脑 → 编排成流水线"** 这样一条线。
