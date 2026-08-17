Panda 机械臂 Pick & Place 仿真项目 — 进度总结
=====================================================
日期：2026-07-05
环境：Ubuntu 24.04 + ROS2 Jazzy + Gazebo Harmonic + MoveIt2 + Franka Panda (fp3)
工作空间：~/panda_grasp_ws

目录结构：
  src/
  ├── franka_description/          # Panda 模型库（URDF/mesh/YAML）
  ├── panda_grasp_sim/             # 仿真包（launch/URDF/config/worlds/脚本）
  │   ├── launch/
  │   │   ├── sim.launch.py         # Gazebo 单独启动
  │   │   └── sim_with_moveit.launch.py  # Gazebo + MoveIt + RViz 组合启动
  │   ├── config/
  │   │   └── panda_controllers.yaml    # ros2_control 控制器配置
  │   ├── urdf/
  │   │   └── panda.urdf.xacro          # 机器人 URDF（Xacro 宏展开）
  │   ├── worlds/
  │   │   └── grasp_world.sdf           # Gazebo 场景（地面+桌面+物体）
  │   └── panda_grasp_sim/
  │       └── pick_place.py             # Pick & Place 脚本（未完成）
  └── panda_moveit_config/          # MoveIt2 配置包（Setup Assistant 生成）
      ├── launch/
      │   ├── move_group.launch.py       # move_group 启动
      │   ├── moveit_rviz.launch.py      # RViz 可视化
      │   └── ...
      ├── config/
      │   ├── panda.srdf                 # 语义描述（规划组/碰撞矩阵/末端执行器）
      │   ├── panda.urdf.xacro           # MoveIt 用的 URDF（FakeSystem）
      │   ├── panda.urdf                 # 纯机器人模型（无 ros2_control/gazebo 标签）
      │   ├── kinematics.yaml            # KDL 运动学求解器配置
      │   ├── joint_limits.yaml          # 关节速度/加速度限制
      │   ├── moveit_controllers.yaml    # MoveIt 端控制器映射
      │   ├── ros2_controllers.yaml      # ros2_control 端控制器配置
      │   └── ompl_planning.yaml         # OMPL 规划管线配置（手动补的）
      └── ...
  ├── 踩坑总结_Panda_Gazebo.md       # Gazebo 踩坑文档
  ├── ROS2_Launch文件详解.md         # Launch 文件详解
  └── 仿真故障排查手册.md            # 6 级故障排查流程


一、已完成内容
═══════════════

1. URDF 模型修复
   - robot_type=fp3（Panda），ee_id=franka_hand（夹爪）
   - mimic 关节（fp3_finger_joint2 自动跟随 finger_joint1）
   - ros2_control 硬件接口配置（GazeboSimSystem 插件）
   - 关节初始位置设定 + Gazebo 插件加载控制器 YAML

2. Gazebo 资源路径修复
   - GZ_SIM_RESOURCE_PATH 加入本地 workspace 的 franka_description 路径
   - 解决 "Unable to find file model://franka_description/..." 错误

3. ros2_control 控制器配置
   - panda_controllers.yaml：3 个控制器
     · joint_state_broadcaster
     · fp3_arm_controller（7 轴关节轨迹控制）
     · fp3_gripper_controller（夹爪关节轨迹控制）
   - fp3_finger_joint2 不配置 command_interface（mimic 关节）

4. Launch 启动编排
   - sim.launch.py：
     T+0s  GZ_SIM_RESOURCE_PATH 设置
     T+0s  Gazebo 启动 + robot_state_publisher + gz_bridge（/clock 同步）
     T+3s  机器人 spawn（ros_gz_sim create）
     T+6s  控制器加载（controller_manager spawner）
   - sim_with_moveit.launch.py：
     复用 sim.launch.py + 延迟启动 move_group + RViz
     use_sim_time 显式传入节点

5. Gazebo 3D 模型正常显示 ✓

6. 控制器验证 ✓
   - ros2 control list_controllers → 3 个 active
   - ros2 control list_hardware_interfaces → 8 关节 claimed

7. 手动命令控制关节运动 ✓
   - ros2 action send_goal 控制夹爪开合
   - ros2 action send_goal 控制机械臂 7 轴运动

8. MoveIt2 集成 ✓
   - Setup Assistant 生成 panda_moveit_config 配置包
   - 创建两个规划组：arm（7 轴 KDL IK）、gripper（无 IK）
   - 末端执行器 hand，父 link 为 fp3_hand
   - 修复加速度限制（joint_limits.yaml 补 max_acceleration）
   - 修复时钟同步（move_group + RViz 加 use_sim_time: true）
   - RViz Motion Planning 面板可正常 Plan & Execute

9. 场景搭建 ✓
   - grasp_world.sdf：地面 + 2m×2m×0.1m 桌面 + 3cm 绿色方块
   - 机械臂 spawn 在桌面 z=0.10m 处
   - bullet-featherstone 物理引擎（当时把 mimic 报错当噪音忽略了，2026-08-17 查明这正是夹爪只动一边的根因，见文末补充日志）

10. 文档沉淀 ✓
    - 踩坑总结_Panda_Gazebo.md（Gazebo 搭建全流程踩坑）
    - ROS2_Launch文件详解.md
    - 仿真故障排查手册.md（0~6 级排查 + 一键检查脚本）


二、待完成内容
═══════════════

1. Python Pick & Place 脚本（核心）
   当前状态：panda_grasp_sim/pick_place.py 有多版尝试代码但均未成功
   需要实现：
   ┌──────────────────────────────────────────┐
   │ 步1  张开夹爪 (0.04m)                     │
   │ 步2  移动到物体上方（预抓取位姿）           │
   │ 步3  下降至抓取位姿（手掌朝下）             │
   │ 步4  闭合夹爪 (0.0m)                      │
   │ 步5  抬起物体                             │
   │ 步6  移动至放置位置                        │
   │ 步7  张开夹爪释放                          │
   └──────────────────────────────────────────┘

   技术路线选择：
   A. 硬编码关节角（最简单）：
      在 RViz 里手动拖出预抓取/抓取姿态 → 读取关节值
      → 写入 Python 脚本 → 用 FollowJointTrajectory action 发送
      优点：不需要 MoveIt，纯 controller action 已验证可用
      缺点：物体位置变了就要重新找关节值

   B. 修复 MoveItPy 高级 API：
      补齐 MoveItPy 初始化配置，直接调用 plan()/execute()
      优点：自动 IK，适用任何位姿
      缺点：配置链路复杂

   C. 用经典 moveit_commander：
      pip install 或 apt install 经典 Python API
      优点：文档多、成熟
      缺点：可能需要适配 ROS2 Jazzy

   推荐：优先用方案 A（硬编码关节角），快速跑通全流程
   再用方案 B/C 升级为通用版

2. MoveGroup Action 接口调试（未解决）
   /move_action 可连接，但 MotionPlanRequest 构造复杂：
   - PositionConstraint 的 BoundingVolume 需要精确配置
   - OrientationConstraint 的手掌朝向需要根据 URDF 坐标系调整
   - 规划场景碰撞物体需要提前发布 CollisionObject 到 /planning_scene

3. 视觉/相机（可选）
   - 在 Gazebo 场景中加 RGBD 相机
   - 物体检测与位姿估计
   - 视觉伺服抓取

4. 多物体/连续抓取（可选）
   - 多个物体 + 流水线抓取
   - 物体掉落/碰撞处理


三、Python 脚本开发参考
═══════════════════

3.1 已验证可用的 Python 模板（纯 joint trajectory）：

import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint


class PickPlaceNode(Node):
    def __init__(self):
        super().__init__('pick_place_node')
        self.arm = ActionClient(
            self, FollowJointTrajectory,
            '/fp3_arm_controller/follow_joint_trajectory'
        )
        self.gripper = ActionClient(
            self, FollowJointTrajectory,
            '/fp3_gripper_controller/follow_joint_trajectory'
        )
        self.arm.wait_for_server(timeout_sec=5.0)
        self.gripper.wait_for_server(timeout_sec=5.0)
        self._goals = []  # 保持 goal handle 引用，防止被 GC 取消

    def _send(self, client, joints, positions, duration):
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = joints
        p = JointTrajectoryPoint()
        p.positions = positions
        p.time_from_start.sec = int(duration)
        goal.trajectory.points.append(p)

        f = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, f, timeout_sec=3.0)
        gh = f.result() if f.done() else None
        if gh and gh.accepted:
            self._goals.append(gh)
            self.get_logger().info(f'已接受: {positions}')
        else:
            self.get_logger().error('被拒')

    def move_arm(self, joints, duration=3.0):
        names = [f'fp3_joint{i}' for i in range(1, 8)]
        self._send(self.arm, names, joints, duration)

    def set_gripper(self, opening, duration=1.0):
        self._send(self.gripper, ['fp3_finger_joint1'], [opening], duration)

    def run(self):
        self.set_gripper(0.04);  time.sleep(1.5)    # 张开
        self.move_arm([0.0, -0.3, 0.0, -1.5, 0.0, 1.2, 0.5]); time.sleep(4.0)  # 预抓取
        self.move_arm([...]);    time.sleep(4.0)    # 抓取关节值（需从 RViz 获取）
        self.set_gripper(0.0);   time.sleep(1.5)    # 闭合
        self.move_arm([...]);    time.sleep(4.0)    # 抬起
        self.move_arm([...]);    time.sleep(4.0)    # 放置
        self.set_gripper(0.04)                       # 释放
        self.get_logger().info('完成！')


def main():
    rclpy.init()
    PickPlaceNode().run()
    rclpy.shutdown()


3.2 关键注意事项：
    - goal handle 必须保存在列表/成员变量中，函数返回后析构会取消 goal
    - time_from_start.sec 必须是 Python int，不能传 float
    - 两个连续的 goal 之间 sleep 时间要 ≥ duration + 1s，否则新 goal 覆盖旧 goal
    - 夹爪最大开口 0.04m（4cm），物体边长应 ≤ 3cm

3.3 获取抓取关节值的方法：
    (1) 启动仿真：ros2 launch panda_grasp_sim sim_with_moveit.launch.py
    (2) 在 RViz Motion Planning 面板中选 Planning Group: arm
    (3) 拖动末端交互标记到物体上方
    (4) 点 Plan → 如果成功，在终端 move_group 日志中找 planned trajectory
    (5) 或者用 ros2 topic echo /display_planned_path 看关节值
    (6) 把关节值填入脚本的 move_arm([...]) 中


四、常用命令速查
═══════════════

启动仿真：
  source /opt/ros/jazzy/setup.bash
  source ~/panda_grasp_ws/install/setup.bash
  ros2 launch panda_grasp_sim sim_with_moveit.launch.py

编译：
  cd ~/panda_grasp_ws
  colcon build --packages-select panda_grasp_sim --symlink-install
  source install/setup.bash

运行脚本：
  ros2 run panda_grasp_sim pick_place

一键检查脚本：
  ros2 node list
  ros2 control list_controllers
  ros2 action list | grep follow_joint_trajectory
  ros2 topic echo /joint_states --once

查看 TF：
  ros2 run tf2_ros tf2_echo world base
  ros2 run tf2_tools view_frames

---

## 2026-08-17 补充：夹爪单指运动问题修复

**问题**：`hand_grasp_test` 只动一边手指。排查确认 Gazebo Harmonic（Jazzy vendor 包）
**不执行 URDF mimic 约束**（服务器日志：[Err] [Physics.cc:1808] ... does not support mimic
constraints），`fp3_finger_joint2` 是无约束自由关节。之前日志里"mimic 警告可忽略"的判断是错的，
那个警告正是根因。

**修复**：物理层放弃 mimic，由 `fp3_gripper_controller` 双指同步驱动；MoveIt 层用 SRDF
`<mimic_joint>` 保持 1-DOF 规划语义。涉及文件：
- `franka_description/end_effectors/common/franka_hand.xacro`（删 `<mimic>`）
- `panda_grasp_sim/urdf/panda.urdf.xacro`（finger_joint2 加 command/state 接口）
- `panda_grasp_sim/config/panda_controllers.yaml`（双指 + gains + allow_partial_joints_goal）
- `panda_moveit_config/config/panda.srdf`（声明 mimic_joint）
- `hand_grasp_test.py` / `pick_place_full.py`（轨迹含双指）

另：物体滑落问题的主因就是夹爪只有一边在动。详见
[`docs/夹爪单指运动问题修复记录.md`](夹爪单指运动问题修复记录.md)。

**验证结果（2026-08-17 晚）**：
- `hand_grasp_test` 全程双指同步（close: 0.04→0.0 双指一致；open: 0.0→0.04 双指一致）✓
- `pick_place_full` 端到端抓取成功：物块从桌面 (z=0.115) 被双指夹起悬空 (z=0.212) ✓
- 排查中曾遇到一次 finger2 完全卡死（JTC 输出正常但物理层不响应），重启仿真后
  消失且无法复现，判定为旧仿真进程残留导致的一次性事件（见修复记录第五节）。
