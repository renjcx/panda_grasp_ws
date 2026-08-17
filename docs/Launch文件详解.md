# ROS2 Launch 文件详解
# 以 panda_grasp_sim/sim.launch.py 为例

================================================================
一、Launch 文件的结构
================================================================

最外层是一个 Python 函数：

    def generate_launch_description():
        # 所有逻辑写在这里
        return LaunchDescription([...])  # 返回要启动的东西的列表

ROS2 launch 系统调用 generate_launch_description()，
拿到它返回的列表，按顺序启动列表里的每一项。


================================================================
二、每一项都是"动作"（Action）
================================================================

LaunchDescription 里的每个元素，都是一个动作。最常见的几类：

┌──────────────────────────┬──────────────────────────────────┐
│ 动作                     │ 做什么                           │
├──────────────────────────┼──────────────────────────────────┤
│ Node                     │ 启动一个 ROS2 可执行文件（最常用）│
│ IncludeLaunchDescription │ 嵌套启动另一个 launch 文件       │
│ TimerAction              │ 延迟执行某个动作                 │
│ SetEnvironmentVariable   │ 设置环境变量                     │
└──────────────────────────┴──────────────────────────────────┘


================================================================
三、Node 为什么必须写 package + executable？
================================================================

ROS2 的打包方式是 "一个 package 里可以包含多个 executable"。
要启动一个程序，必须指定"哪个包" + "包里的哪个可执行文件"。

类比：就像说"在 /usr/bin 目录下运行 python3"
  → package = 目录
  → executable = 文件名

例 1：同名的情况
  Node(
      package='robot_state_publisher',      # 包名
      executable='robot_state_publisher',   # 可执行文件名（恰好同名）
      parameters=[{...}]                    # 传给这个节点的参数
  )

例 2：不同名的情况
  Node(
      package='ros_gz_sim',     # 包名叫 ros_gz_sim
      executable='create',      # 可执行文件叫 create（名字不同！）
      arguments=['-topic', 'robot_description', '-name', 'panda'],
  )


================================================================
四、我们的 launch 文件逐段解释
================================================================

整个文件做的事：启动 Gazebo 仿真 + Panda 机器人 + 控制器

--- ① SetEnvironmentVariable：设置环境变量 ---
set_gz_resource = SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', gz_resource_path)
# 让 Gazebo 能找到本地 workspace 中的 mesh 文件
# 不是"启动程序"，而是设置后续进程的环境变量

--- ② IncludeLaunchDescription：嵌套启动 Gazebo ---
gz_sim = IncludeLaunchDescription(...)
# ros_gz_sim 包自带 gz_sim.launch.py，我们直接复用
# 等价于命令行：ros2 launch ros_gz_sim gz_sim.launch.py

--- ③ Node：robot_state_publisher ---
Node(
    package='robot_state_publisher',
    executable='robot_state_publisher',
    parameters=[{'robot_description': ..., 'use_sim_time': True}]
)
# 功能：读取 URDF → 计算每个关节的 tf 变换 → 发布 /tf 话题
# 没有它，RViz 和 MoveIt 都不知道机械臂的各个连杆在哪里

--- ④ Node：ros_gz_bridge（时钟桥接）---
Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
)
# Gazebo 有自己的时钟，ROS2 有自己的时钟
# 这个 bridge 把 Gazebo 的时钟同步到 ROS2
# 否则 /tf 的时间戳会错乱，导致"TF 数据太旧"的警告

--- ⑤ Node：在 Gazebo 里生成机器人 ---
Node(
    package='ros_gz_sim',
    executable='create',
    arguments=['-topic', 'robot_description',
               '-name', 'panda',
               '-allow_renaming', 'true',
               '-z', '0.1'],
)
# -z 0.1：把 spawn 高度抬升 0.1m，让机器人正好落在桌面上
# 从 /robot_description 话题读取 URDF
# 转换成 SDF 格式发给 Gazebo
# Gazebo 创建 3D 实体（包括物理碰撞 + 视觉效果）

--- ⑥ Node：加载控制器 ---
Node(
    package='controller_manager',
    executable='spawner',
    arguments=['joint_state_broadcaster', 'fp3_arm_controller', 'fp3_gripper_controller',
               '--controller-manager-timeout', '120',
               '--activate-as-group'],
)
# --controller-manager-timeout 120：controller_manager 是 Gazebo 插件内部启动的，
#   机器人 spawn 前它还不存在，超时要给足
# --activate-as-group：3 个控制器作为一个组同时激活，避免部分激活的不一致
# 等 controller_manager 服务就绪后，加载 3 个控制器：
#   joint_state_broadcaster  → 读取并发布所有关节状态到 /joint_states
#   fp3_arm_controller       → 接收轨迹命令，控制 7 个机械臂关节
#   fp3_gripper_controller   → 接收轨迹命令，控制夹爪开关

--- ⑦ TimerAction：延迟执行（时序控制）---
delayed_spawn = TimerAction(period=3.0, actions=[gz_spawn_entity])
delayed_controller_spawner = TimerAction(period=6.0, actions=[controller_spawner])
# 不能全部同时启动！原因：
#   T+0s:  Gazebo 刚启动，还没初始化完
#   T+3s:  Gazebo 就绪了，才能 spawn 机器人
#   T+6s:  机器人 spawn 后 controller_manager 才存在，才能加载控制器

> 这个时序问题的踩坑记录见 [`gazebo_troubleshooting.md`](gazebo_troubleshooting.md) 坑 6。


================================================================
五、数据流全景图
================================================================

Launch 启动
  │
  ├─ set_gz_resource ──→ 设置 GZ_SIM_RESOURCE_PATH
  │                          ↓
  ├─ gz_sim ──→ 启动 Gazebo 服务器（空世界）
  │                 ↓ (等 3 秒)
  ├─ robot_state_publisher ──→ 读取 xacro → 发布 /tf
  │
  ├─ gz_bridge ──→ 把 Gazebo 时钟同步到 ROS2 /clock
  │
  ├─ [T+3s] create ──→ 读 /robot_description → 发给 Gazebo 生成 Panda
  │                        ↓ (Gazebo 加载 gz_ros2_control 插件)
  │                        ↓ (插件内部启动 controller_manager 节点)
  │
  └─ [T+6s] controller_spawner ──→ 等 /controller_manager 服务就绪
                                       → 加载 joint_state_broadcaster
                                       → 加载 fp3_arm_controller
                                       → 加载 fp3_gripper_controller


================================================================
六、完整数据流（URDF → 关节运动）
================================================================

[1] panda.urdf.xacro (源文件)
     │  xacro.process_file() 展开宏
     ▼
[2] robot_description (URDF XML 字符串)
     │
     ├──→ robot_state_publisher 发布 /tf（各连杆位姿）
     │
     └──→ ros_gz_sim create 发给 Gazebo
              │
              ▼
         [3] Gazebo 内：sdformat_urdf 转成 SDF
              │  加载 gz_ros2_control-system 插件
              │  加载 mesh 文件 → 3D 渲染
              ▼
         [4] controller_manager 节点启动
              │  加载 fp3_arm_controller
              │  加载 fp3_gripper_controller
              │
         [5] 用户发轨迹命令
              │  ros2 action send_goal /fp3_arm_controller/follow_joint_trajectory ...
              ▼
         [6] 关节运动 → Gazebo 物理引擎计算 → 3D 画面更新


================================================================
七、常见问题
================================================================

Q: 为什么不把所有东西写在一个大文件里？
A: 模块化设计。launch 可以嵌套、可以复用。比如 Gazebo 的启动逻辑
   ros_gz_sim 包已经写好了，我们直接 IncludeLaunchDescription 就行，
   不用重复造轮子。

Q: package 和 executable 的值从哪来的？
A: 查看包的 setup.py / CMakeLists.txt 里注册的 entry_points，
   或者用命令：ros2 pkg executables <包名>
   例如：ros2 pkg executables ros_gz_sim
        → create
        → gz_sim

Q: arguments 和 parameters 有什么区别？
A: arguments  = 命令行参数（像 ./program --flag value）
   parameters = ROS2 参数系统（YAML / dict 格式，可在运行时修改）
