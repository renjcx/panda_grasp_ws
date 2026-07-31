#!/usr/bin/env python3

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from control_msgs.action import FollowJointTrajectory

from moveit.planning import MoveItPy, PlanRequestParameters
from moveit.core.robot_state import RobotState
from moveit_configs_utils import MoveItConfigsBuilder

HOME = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
ARM_JOINTS = ["fp3_joint1", "fp3_joint2", "fp3_joint3",
              "fp3_joint4", "fp3_joint5", "fp3_joint6", "fp3_joint7"]


def main():
    rclpy.init()
    node = Node("pick_place")

    # ---- 读取当前关节位置 ----
    current = None

    def on_joint_state(msg: JointState):
        nonlocal current
        idx = [msg.name.index(j) for j in ARM_JOINTS if j in msg.name]
        if len(idx) == 7:
            current = np.array([msg.position[i] for i in idx])

    sub = node.create_subscription(JointState, "/joint_states", on_joint_state, 10)
    while current is None:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_subscription(sub)

    # ---- 初始化 MoveIt ----
    config = MoveItConfigsBuilder("panda", package_name="panda_moveit_config").to_moveit_configs().to_dict()
    pipelines = config.pop("planning_pipelines")
    config["planning_pipelines.pipeline_names"] = pipelines
    config["planning_pipelines.namespace"] = ""

    moveit = MoveItPy(node_name="moveit_py", config_dict=config)
    arm = moveit.get_planning_component("arm")
    model = moveit.get_robot_model()

    # ---- 规划 ----
    params = PlanRequestParameters(moveit, "")
    params.planning_pipeline = "ompl"
    params.planner_id = "RRTConnect"

    start = RobotState(model)
    start.set_joint_group_positions("arm", current)
    arm.set_start_state(robot_state=start)

    goal = RobotState(model)
    goal.set_joint_group_positions("arm", HOME)
    arm.set_goal_state(robot_state=goal)

    plan_result = arm.plan(single_plan_parameters=params)
    if not plan_result:
        node.get_logger().error("规划失败"), rclpy.shutdown(); return

    jt = plan_result.trajectory.get_robot_trajectory_msg().joint_trajectory
    node.get_logger().info(f"规划成功: {np.round(jt.points[0].positions,2)} -> {np.round(HOME,2)}")

    # ---- 执行 ----
    client = ActionClient(node, FollowJointTrajectory, "/fp3_arm_controller/follow_joint_trajectory")
    if not client.wait_for_server(5.0):
        node.get_logger().error("控制器未就绪"); rclpy.shutdown(); return

    send_future = client.send_goal_async(FollowJointTrajectory.Goal(trajectory=jt))
    rclpy.spin_until_future_complete(node, send_future)
    goal_handle = send_future.result()
    if not goal_handle or not goal_handle.accepted:
        node.get_logger().error("控制器拒绝"); rclpy.shutdown(); return

    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result()
    if result.result.error_code == result.result.SUCCESSFUL:
        node.get_logger().info("完成!")
    else:
        node.get_logger().error(result.result.error_string)

    rclpy.shutdown()


if __name__ == "__main__":
    main()
