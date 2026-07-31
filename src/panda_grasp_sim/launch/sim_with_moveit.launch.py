import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description():
    panda_grasp_sim_share = get_package_share_directory('panda_grasp_sim')
    panda_moveit_config_share = get_package_share_directory('panda_moveit_config')

    # MoveIt 配置（URDF/SRDF/kinematics/controllers 从 panda_moveit_config 加载）
    moveit_config = (
        MoveItConfigsBuilder("panda", package_name="panda_moveit_config")
        .to_moveit_configs()
    )

    # 1. Gazebo 仿真（RSP + Bridge + Spawn + Controllers）
    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(panda_grasp_sim_share, 'launch', 'sim.launch.py')
        ])
    )

    # 2. MoveIt move_group 节点（运动规划引擎）
    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        parameters=[
            moveit_config.to_dict(),
            {'use_sim_time': True},
        ],
        output='screen',
    )

    # 3. RViz 节点（可视化 + Motion Planning 面板）
    rviz_config = os.path.join(panda_moveit_config_share, 'config', 'moveit.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        parameters=[
            moveit_config.to_dict(),
            {'use_sim_time': True},
        ],
        arguments=['-d', rviz_config],
        output='screen',
    )

    # T+0s:  Gazebo
    # T+6s:  等 controller 就绪 → move_group
    # T+8s:  等 move_group 就绪 → RViz
    delayed_move_group = TimerAction(period=6.0, actions=[move_group_node])
    delayed_rviz = TimerAction(period=8.0, actions=[rviz_node])

    return LaunchDescription([
        sim_launch,
        delayed_move_group,
        delayed_rviz,
    ])
