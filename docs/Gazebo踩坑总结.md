# Panda 机械臂 Gazebo 仿真踩坑总结

## 一、为什么不是"导入模型就好了"？

"导入模型"在 Gazebo 里确实只是一条命令（`ros_gz_sim create -topic robot_description`），但要让这个模型**有物理、能被控制、能渲染**，背后需要 5 层对接全部正确：

```
[URDF/Xacro 模型定义]
    ↓
[Gazebo SDF 转换] → [Mesh 文件加载] → [3D 渲染]
    ↓
[ros2_control 硬件接口]
    ↓
[Controller Manager + 控制器]
    ↓
[Launch 启动编排]
```

任何一层出错，结果要么崩溃、要么白屏、要么关节动不了。


## 二、踩坑清单（按发现顺序）

### 坑 1：robot_type 选错 — fr3 ≠ Panda

**现象**：机械臂关节名和运动学参数全部错误，Gazebo 加载后立即崩溃。

**原因**：
- `franka_description` 包里 fr3 和 fp3 是两个不同的机器人：
  - `fr3`  = Franka Research 3（新一代，7轴研究平台）
  - `fp3`  = Franka Panda 3（经典 Panda）
- 我最初写了 `robot_type="fr3"`，但你要的是 Panda。
- 这导致所有关节名变成 `fr3_joint1`、`fr3_joint2`...，与 Panda 的 `fp3_joint1` 不匹配。

**教训**：
```xml
<!-- 错误 -->
<xacro:franka_robot robot_type="fr3" ... />
<!-- 正确 -->
<xacro:franka_robot robot_type="fp3" ... />
```
同时 YAML 路径、关节名都要对应改动。**先确认你用的到底是哪个机器人型号。**

### 坑 2：ee_id 默认值是 "none" — 夹爪悄无声息地消失了

**现象**：Entity Tree 里有 Panda，但看不见手指。

**原因**：
```xml
<!-- franka_robot.xacro 宏的条件判断 -->
<xacro:if value="${hand and ee_id == 'franka_hand'}">
    <!-- 这里才生成夹爪 -->
</xacro:if>
```
`franka_robot` 宏签名：`ee_id:=none`（默认值）
我只传了 `hand="true"`，没传 `ee_id="franka_hand"`，条件不满足，夹爪被跳过。

**教训**：**Xacro 宏的默认参数值会"静默"地关闭功能。** 必需参数要显式全部写出：
```xml
<xacro:franka_robot
    robot_type="fp3"
    hand="true"
    ee_id="franka_hand"   <!-- 必须显式指定！ -->
    ... />
```

### 坑 3：Gazebo 资源路径 ≠ ROS2 包路径

**现象**：Gazebo 不崩溃了，Entity Tree 有 Panda 但 3D 窗口一片空白。日志全是：
```
[Err] Unable to find file [model://franka_description/meshes/robots/fp3/collision/link0.stl]
```

**原因**：
- URDF 用 `package://franka_description/meshes/...` （ROS 包路径）
- `ros_gz_sim` 把它转成 `model://franka_description/meshes/...` （Gazebo 资源路径）
- Gazebo 只在 `GZ_SIM_RESOURCE_PATH` 里搜索资源
- 默认值：`GZ_SIM_RESOURCE_PATH=/opt/ros/jazzy/share`（只有系统包！）
- 你的 `franka_description` 是本地 workspace 编译的，不在系统路径里

**教训**：**本地编译的包，Gazebo 找不到它的 mesh 文件。** 必须在 launch 里加：
```python
franka_share = get_package_share_directory('franka_description')
ws_resource_path = os.path.dirname(franka_share)
gz_resource_path = ws_resource_path + ':' + os.environ.get('GZ_SIM_RESOURCE_PATH', '')
set_gz_resource = SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', gz_resource_path)
```

### 坑 4：package.xml 依赖缺失

**现象**：运行时可能找不到节点、topic、service。

**原因**：`package.xml` 只声明了 `rclpy`，但 launch 文件实际依赖 ros_gz_sim、robot_state_publisher、controller_manager 等 8 个包。ROS2 构建系统不做运行时检查，所以编译能过但运行会出各种奇怪错误。

**教训**：`package.xml` 的 `<depend>` 要写全。以下是我用到的所有包：
```
ros_gz_sim, ros_gz_bridge, robot_state_publisher,
controller_manager, joint_state_broadcaster,
joint_trajectory_controller, xacro, franka_description
```

### 坑 5：Gazebo Harmonic 不执行 URDF mimic 约束（夹爪只动一边）

**现象**：只命令 `fp3_finger_joint1` 时，Gazebo 里只有一个手指动；服务器日志报错：

```
[Err] [Physics.cc:1808] Attempting to create a mimic constraint for joint
[fp3_finger_joint2] but the chosen physics engine does not support mimic
constraints, so no constraint will be created.
```

**原因**：URDF 的 `<mimic>` 声明转换进 SDF 后，gz-sim 尝试创建物理约束，但当前软件栈（Jazzy + Gazebo Harmonic vendor 包）下没有物理引擎能通过该检查——这是已知上游问题 [`gazebosim/gz-sim#1684`](https://github.com/gazebosim/gz-sim/issues/1684)，gz_ros2_control 的 workaround PR（[ros-controls/gz_ros2_control#86](https://github.com/ros-controls/gz_ros2_control/pull/86)）从未合并。所以 `finger_joint2` 是一个没有任何约束和命令的自由关节。

**教训 / 解决方案**：不要依赖物理层 mimic，让控制器同步驱动两个手指：

1. URDF 删除 `finger_joint2` 的 `<mimic>` 标签（`franka_hand.xacro`）
2. `panda.urdf.xacro` 给 `fp3_finger_joint2` 也配置 `command_interface`
3. `panda_controllers.yaml`：broadcaster 和 `fp3_gripper_controller` 都加入 `fp3_finger_joint2`
4. `panda.srdf` 声明 `<mimic_joint joint="fp3_finger_joint2" mimic_joint="fp3_finger_joint1"/>`，MoveIt 保持 1-DOF 规划并自动展开轨迹
5. 抓取脚本的轨迹同时包含两个手指关节（相同目标值）

> 完整排查过程与实测数据见 [`夹爪单指运动问题修复记录.md`](夹爪单指运动问题修复记录.md)。

### 坑 6：Launch 启动时序

**现象**：Controller spawner 找不到 `/controller_manager` 服务。

**原因**：`controller_manager` 是 `gz_ros2_control` 插件在 Gazebo 内部启动的，要等机器人 spawn 之后才存在。Spawner 如果同时启动就会超时失败。

**教训**：用 `TimerAction` 分步延迟：
```
T+0s:  启动 Gazebo + RSP + Bridge
T+3s:  等待 Gazebo 就绪 → spawn 机器人
T+6s:  等待 controller_manager 就绪 → 加载控制器
```

> launch 时序的逐段讲解见 [`Launch文件详解.md`](Launch文件详解.md)。

## 三、架构速览 — 关键概念

```
┌─────────────────────────────────────────────────────┐
│ Launch File (sim.launch.py)                         │
│  ├─ gz_sim          ← 启动 Gazebo 物理引擎+渲染      │
│  ├─ robot_state_publisher ← 把 URDF 广播到 /tf       │
│  ├─ gz_bridge       ← /clock 时间同步                │
│  ├─ create          ← 把 URDF 发到 Gazebo 生成实体    │
│  └─ controller_spawner ← 加载 joint_trajectory 等控制器│
└─────────────────────────────────────────────────────┘

URDF/Xacro 的生命周期:
  panda.urdf.xacro
    → xacro.process_file() 展开宏
    → robot_description (XML string)
    → robot_state_publisher 发布 /tf
    → ros_gz_sim create 发给 Gazebo → SDF 转换 → 物理+渲染

控制链路:
  用户代码 → /fp3_arm_controller/joint_trajectory action
    → joint_trajectory_controller
    → /controller_manager
    → gz_ros2_control (GazeboSimSystem)
    → Gazebo 物理引擎 → 关节运动
```

### 核心术语

| 术语 | 作用 |
|------|------|
| Xacro | XML 宏语言，用 `${变量}` 和 `<xacro:macro>` 减少重复 |
| URDF | 机器人描述格式（连杆、关节、惯量、mesh） |
| SDF | Gazebo 原生的仿真描述格式（比 URDF 多了物理/传感器/插件） |
| ros2_control | ROS2 的硬件抽象层，统一了仿真和真机的控制接口 |
| gz_ros2_control | ros2_control 和 Gazebo 之间的桥接插件 |
| controller_manager | 管理多个控制器的生命周期（加载/卸载/切换） |
| JointTrajectoryController | 最常用的机械臂控制器，接收轨迹点并插值执行 |
| mimic joint | 从动关节，值由另一个关节计算得出（如夹爪的两个手指） |


## 四、快速排查清单

Gazebo 出问题时，按这个顺序查：

1. **Gazebo 直接崩溃** → `cat ~/.gz/sim/log/<latest>/server_console.log` 看最后几行错误
2. **模型不显示（白屏/透明）** → 看 log 里有没有 `Unable to find file [model://...]`
3. **关节不动** → 检查 `/controller_manager/list_controllers` 是否返回了控制器
4. **夹爪同步问题** → 两个手指由 `fp3_gripper_controller` 用相同命令同步驱动，与物理引擎无关；确认 URDF 已删除 `<mimic>` 标签且两个手指都有 command_interface（见坑 5）
5. **xacro 报错** → 单独跑 `xacro panda.urdf.xacro` 检查语法
