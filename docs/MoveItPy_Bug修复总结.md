pick_place.py 修复总结
====================

目标：用 MoveItPy 控制 Gazebo 仿真中的 Franka Panda 机械臂运动到 HOME 位置。

遇到的问题及修复：

┌──────────────────────────────────────────────────────────────────┐
│ 问题 1: MoveItPy 构造函数参数名错误                                │
├──────────────────────────────────────────────────────────────────┤
│ 错误信息: TypeError: __init__(): incompatible constructor         │
│          arguments... parameter_namespace 不是合法参数              │
│                                                                   │
│ 原因: 代码中使用了 parameter_namespace='/move_group'，但          │
│       MoveItPy 的构造函数没有这个参数。                             │
│                                                                   │
│ 修复: 改用 config_dict= 参数，从 MoveItConfigsBuilder 加载        │          │
│       完整的 MoveIt 配置字典传入。                                  │
│                                                                   │
│       from moveit_configs_utils import MoveItConfigsBuilder       │
│       config = MoveItConfigsBuilder(                              │
│           "panda", package_name="panda_moveit_config"             │
│       ).to_moveit_configs().to_dict()                             │
│       moveit = MoveItPy(node_name="moveit_py", config_dict=config) │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ 问题 2: Failed to load any planning pipelines                     │
├──────────────────────────────────────────────────────────────────┤
│ 错误信息: [ERROR] Failed to load any planning pipelines.          │
│          [FATAL] Failed to load planning pipelines from           │
│          parameter server                                         │
│                                                                   │
│ 原因: MoveItConfigsBuilder 生成的参数字段名是 planning_pipelines   │
│      （扁平时列表），但 MoveItCpp（MoveItPy 底层 C++ 类）读取       │
│      的参数是 planning_pipelines.pipeline_names。                  │
│      Jazzy 版本中两者命名约定不一致，导致 MoveItCpp 找不到规划      │
│      管线配置，所有 planner (OMPL/CHOMP/STOMP/Pilz) 加载失败。     │
│                                                                   │
│ 修复: 在传给 MoveItPy 之前，把 planning_pipelines 重命名为         │
│      planning_pipelines.pipeline_names，并补充 namespace 字段：    │
│                                                                   │
│      pipelines = config.pop("planning_pipelines")                 │
│      config["planning_pipelines.pipeline_names"] = pipelines      │
│      config["planning_pipelines.namespace"] = ""                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ 问题 3: plan() 返回成功但机器人不动                                │
├──────────────────────────────────────────────────────────────────┤
│ 现象: Planning succeeded 但 Execution result: ABORTED              │
│                                                                   │
│ 原因1: set_start_state_to_current_state() 不生效。                │
│        MoveItPy 内部的 CurrentStateMonitor 因为 use_sim_time      │
│        和 /clock 同步问题，无法获取当前关节状态。                   │
│        导致轨迹起点为全零，与实际机器人位置不匹配。                  │
│                                                                   │
│ 原因2: moveit.execute() 调用 TrajectoryExecutionManager，          │
│        其内部轨迹校验也需要 CurrentStateMonitor 提供当前状态，       │
│        因上述原因校验失败，直接返回 ABORTED。                       │
│                                                                   │
│ 修复:                                                             │
│   a) 用 rclpy 直接从 /joint_states 话题读取当前关节位置，          │
│      构造 RobotState 作为规划起点（替代 set_start_state_to_current_state）│
│   b) 用 rclpy ActionClient 直接发轨迹到控制器                      │
│      （替代 moveit.execute()），绕过 TrajectoryExecutionManager    │
│                                                                   │
│      from control_msgs.action import FollowJointTrajectory        │
│      client = ActionClient(node, FollowJointTrajectory,           │
│          "/fp3_arm_controller/follow_joint_trajectory")           │
└──────────────────────────────────────────────────────────────────┘

最终代码结构（4 步骤）：
  1. 读取当前关节位置 → 从 /joint_states 获取 arm 的 7 个关节角
  2. MoveIt 初始化  → MoveItConfigsBuilder + MoveItPy(planning_pipelines 修正)
  3. 规划           → RobotState(start) → RobotState(goal) → plan()
  4. 执行           → ActionClient 发送 FollowJointTrajectory 到控制器
