import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro


def generate_launch_description():
    pkg_name = 'panda_grasp_sim'
    pkg_share = get_package_share_directory(pkg_name)

    # 1. 处理 Xacro 生成 Robot Description
    xacro_file = os.path.join(pkg_share, 'urdf', 'panda.urdf.xacro')
    robot_description_config = xacro.process_file(xacro_file).toxml()

    # ---- 关键修复：让 Gazebo 能找到 workspace 中的 mesh 文件 ----
    # GZ_SIM_RESOURCE_PATH 默认只有 /opt/ros/jazzy/share，
    # 需要把本地 workspace 的 franka_description 资源路径也加上
    franka_share = get_package_share_directory('franka_description')
    ws_resource_path = os.path.dirname(franka_share)  # .../install/franka_description/share
    gz_resource_path = ws_resource_path + ':' + os.environ.get('GZ_SIM_RESOURCE_PATH', '/opt/ros/jazzy/share')

    set_gz_resource = SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', gz_resource_path)

    # 2. 启动 Gazebo Harmonic
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')]),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
    )

    # 3. Robot State Publisher
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description_config,
            'use_sim_time': True,
        }]
    )

    # 4. 桥接 Gazebo → ROS 时钟
    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )

    # 5. 在 Gazebo 中生成机器人
    gz_spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-topic', 'robot_description',
                   '-name', 'panda',
                   '-allow_renaming', 'true',
                   '-z', '0.0'],
    )

    # 6. Controller spawner — 等待 controller_manager 就绪后加载所有控制器
    controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            'fp3_arm_controller',
            'fp3_gripper_controller',
            '--controller-manager-timeout', '120',
            '--activate-as-group',
        ],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    # 启动顺序：Gazebo → RSP + Bridge → 延迟 spawn → 再延迟 spawn controller
    delayed_spawn = TimerAction(
        period=3.0,
        actions=[gz_spawn_entity],
    )

    delayed_controller_spawner = TimerAction(
        period=6.0,
        actions=[controller_spawner],
    )

    return LaunchDescription([
        set_gz_resource,
        gz_sim,
        node_robot_state_publisher,
        gz_bridge,
        delayed_spawn,
        delayed_controller_spawner,
    ])
