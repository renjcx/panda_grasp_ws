# Panda Grasp 仿真 — 故障排查手册

> 适用环境：ROS2 Jazzy + Gazebo Harmonic + MoveIt2 + Franka Panda (fp3)
> 
> 使用方法：从第1级开始逐级排查，某级不过就停在该级修，不要跳到下一级。

---

## 第 0 级：仿真启动是否成功

### 检查点：Gazebo 窗口弹出、机械臂模型 3D 正常显示

```bash
# 看各个节点是否都在运行
ros2 node list
```

| 期望看到的节点 | 说明 |
|---|---|
| `robot_state_publisher` | 发布 TF 变换 |
| `parameter_bridge` | Gazebo ↔ ROS2 时钟同步 |
| `controller_manager` | 管理控制器 |
| `move_group` | MoveIt 规划引擎 |

```bash
# 看有没有崩溃的进程
ros2 topic list | wc -l
```
topic 数量应该 > 15，如果只有个位数，说明仿真没起来。

### 常见故障

| 现象 | 原因 | 查什么 |
|------|------|--------|
| Gazebo 窗口空白没有模型 | 模型没 spawn 或 URDF 路径错误 | `cat ~/.gz/sim/log/*/server_console.log \| tail -20` |
| 模型出现但关节全塌 | 惯性参数异常 | 检查 URDF 惯量配置 |
| move_group 没起来 | CMake 编译错误或 use_sim_time 没设 | 看终端红色 ERROR |

---

## 第 1 级：硬件接口是否正常

> 这一步验证 Gazebo 内部的 ros2_control 插件是否成功初始化了所有关节。

### 检查命令

```bash
ros2 control list_hardware_interfaces
```

### 期望输出（共 8 个关节 × 多接口）

```
command interfaces
    fp3_joint1/position       [available] [claimed]
    fp3_joint2/position       [available] [claimed]
    ...
    fp3_finger_joint1/position [available] [claimed]

state interfaces
    fp3_joint1/position  (有)   fp3_joint1/velocity  (有)   fp3_joint1/effort  (有)
    ...
```

### 关键判断

| 状态 | 含义 | 处理 |
|------|------|------|
| `[available] [claimed]` | 正常，被控制器占用 | ✅ |
| `[available] [unclaimed]` | 硬件接口在线但没控制器使用它 | ⚠️ 检查 step 2 |
| `fp3_finger_joint2` 不在 command_interface 里 | 配置错误！两个手指都必须有 command（Gazebo 不执行 URDF mimic） | 检查 URDF 和 YAML |
| 关节数量不对 | URDF ros2_control 段有问题 | 检查 xacro 展开结果 |

---

## 第 2 级：控制器是否加载

### 检查命令

```bash
ros2 control list_controllers
```

### 期望输出

```
joint_state_broadcaster  joint_state_broadcaster/JointStateBroadcaster  active
fp3_arm_controller       joint_trajectory_controller/JointTrajectoryController  active
fp3_gripper_controller   joint_trajectory_controller/JointTrajectoryController  active
```

### 关键判断

| 状态 | 含义 | 处理 |
|------|------|------|
| `active` | 正常 | ✅ |
| `inactive` | 控制器加载了但没激活 | `ros2 control set_controller_state <name> activate` |
| `unconfigured` | yaml 配置没被读入 | 检查 URDF 的 `<plugin>` 指向的 yaml 路径 |
| 列表为空 | controller_manager 没启动 | Gazebo 可能还没 ready，等几秒再试 |
| 缺少某个控制器 | spawner 失败了 | 看 Gazebo 终端日志，关节名拼写是否匹配 |

---

## 第 3 级：action server 和 topic 是否在线

### 检查命令

```bash
# 无头模式的 action，move_group 内部用
ros2 action list

# 核心：控制器的 action，MoveIt 通过这个发轨迹
ros2 action list | grep follow_joint_trajectory
```

### 期望输出

```
/fp3_arm_controller/follow_joint_trajectory
/fp3_gripper_controller/follow_joint_trajectory
```

如果这两条不在，MoveIt Planning 能过但 Execute 不会动。

### 补充：检查 TF 树

```bash
# 确认坐标系发布正常
ros2 run tf2_tools view_frames
# 或直接看
ros2 topic echo /tf --once | grep -oP 'child_frame_id: "\K[^"]+'
```

期望能看到 `fp3_link0` ～ `fp3_link7`、`fp3_hand` 等所有 link。

---

## 第 4 级：手动控制关节验证

> 这一步跳过 MoveIt，直接用命令行发轨迹，确认底层控制链路完全通。

### 测试机械臂 (7 轴)

```bash
ros2 action send_goal /fp3_arm_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{ trajectory: { joint_names: ['fp3_joint1','fp3_joint2','fp3_joint3','fp3_joint4','fp3_joint5','fp3_joint6','fp3_joint7'], points: [ { positions: [0.0, -0.785, 0.0, -2.356, 0.0, 1.57, 0.785], time_from_start: { sec: 0, nanosec: 0 } }, { positions: [0.5, -0.3, 0.2, -2.0, 0.3, 1.2, 0.5], time_from_start: { sec: 3, nanosec: 0 } } ] } }"
```

### 测试夹爪

```bash
# 闭合
ros2 action send_goal /fp3_gripper_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{ trajectory: { joint_names: ['fp3_finger_joint1'], points: [ { positions: [0.0], time_from_start: { sec: 1, nanosec: 0 } } ] } }"

# 张开
ros2 action send_goal /fp3_gripper_controller/follow_joint_trajectory control_msgs/action/FollowJointTrajectory "{ trajectory: { joint_names: ['fp3_finger_joint1'], points: [ { positions: [0.04], time_from_start: { sec: 1, nanosec: 0 } } ] } }"
```

### 期望结果
- 终端返回 `Goal reached, success!`
- Gazebo 里机械臂和夹爪**真的动了**
- Gazebo 日志有 `Received new action goal` → `Accepted` → `Goal reached`

### 常见故障

| 现象 | 原因 | 处理 |
|------|------|------|
| 命令格式错误 | 换行复制导致空格/编码问题 | 贴到文件再 cat 发送（见第4级脚本版） |
| `Incoming joint X doesn't match` | 关节名拼写、顺序不对 | 对比 YAML 里 joints 列表 |
| command 不报错但关节不动 | 物理引擎问题或 mimic 冲突 | 看 Gazebo 日志 ERR 行 |

---

## 第 5 级：MoveIt 规划是否正常

### 检查项

1. RViz 左侧 **Motion Planning** 面板有 `arm` 和 `gripper` 两个规划组
2. 在 **Planning Group** 选 `arm`，拖一个随机目标，点 **Plan**
3. 日志应出现 `Motion plan was computed successfully`，RViz 里显示绿色轨迹线

### 如果 Plan 失败，查：

```bash
# 查看 joint_states 是否在发布
ros2 topic echo /joint_states --once
```

期望 7 个关节 + 1 个 finger 的 position 值都在更新。

```
# 看 move_group 有没有报错
# 终端里翻 move_group-* 的红色行，常见错误：

"No acceleration limit was defined for joint XXX"
  → joint_limits.yaml 里 has_acceleration_limits 改 true，补上 max_acceleration

"Didn't receive robot state with recent timestamp"
  → use_sim_time 没设对，节点参数里加 {'use_sim_time': True}

"Planner configuration 'arm' will use planner..."
  → 这条不是错误，只是 INFO
```

---

## 第 6 级：MoveIt Execute 是否成功

> Plan 成功但 Execute 不动 = MoveIt 轨迹没有送到控制器。

### 检查命令

```bash
ros2 action list | grep follow_joint_trajectory
```

必须有 `/fp3_arm_controller/follow_joint_trajectory`。

如果不在 → 回到第 2 级查控制器。

```bash
# 看 move_group 连接控制器的日志
ros2 node info /move_group 2>/dev/null | grep -A 20 "Action Clients"
```

### 检查 moveit_controllers.yaml

```bash
cat ~/panda_grasp_ws/src/panda_moveit_config/config/moveit_controllers.yaml
```

确保：
- `action_ns: follow_joint_trajectory`
- `joints:` 列表的关节名与 YAML 控制器配置一致
- `type: FollowJointTrajectory`

---

## 快速一键全检脚本

```bash
#!/bin/bash
# 保存为 ~/panda_grasp_ws/check.sh
echo "=== 1. 节点列表 ==="
ros2 node list 2>&1 | head -10

echo ""
echo "=== 2. 控制器状态 ==="
ros2 control list_controllers 2>&1

echo ""
echo "=== 3. Action Server ==="
ros2 action list 2>&1 | grep follow_joint_trajectory || echo "⚠ 没有找到 follow_joint_trajectory action!"

echo ""
echo "=== 4. Joint States ==="
ros2 topic echo /joint_states --once 2>&1 | grep -E "name:|position:"

echo ""
echo "=== 5. TF Frames ==="
ros2 topic echo /tf --once 2>&1 | grep -oP 'child_frame_id: "\K[^"]+' || echo "⚠ TF 无输出"
```

运行方式：
```bash
source ~/panda_grasp_ws/install/setup.bash
bash ~/panda_grasp_ws/check.sh
```

---

## 故障速查表

| 你在做什么 | 失败现象 | 先查这一级 |
|-----------|---------|-----------|
| 启动仿真 | Gazebo 白屏 | 第 0 级 |
| 启动仿真 | move_group 报错退出 | 第 0 级 → 看终端 ERROR |
| RViz 里点 Plan | 规划失败 | 第 5 级 |
| RViz 里点 Execute | 机械臂不动 | 第 3 级 → 第 6 级 |
| 手动命令 | 夹爪不动 | 第 2 级 → 第 4 级 |
| 一切正常但关节位置不对 | RViz 模型与实际不一致 | 第 5 级 check joint_states |

---

## 备份常用命令（随时查阅）

```bash
ros2 node list                             # 有哪些节点
ros2 topic list                            # 有哪些 topic
ros2 action list                           # 有哪些 action
ros2 control list_controllers              # 控制器状态
ros2 control list_hardware_interfaces      # 硬件接口状态
ros2 topic echo /joint_states --once       # 当前关节角度
ros2 topic echo /tf --once                 # TF 树快照
ros2 run rqt_reconfigure rqt_reconfigure   # 动态调参（GUI）
```
