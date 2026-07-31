import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from moveit_configs_utils import MoveItConfigsBuilder
from moveit.planning import MoveItPy, PlanRequestParameters
from moveit.core.robot_state import RobotState
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from geometry_msgs.msg import Pose
from sensor_msgs.msg import JointState
from rclpy.parameter import Parameter
from moveit.planning import PlanningSceneMonitor #规划碰撞避让

ARM_JOINTS = ["fp3_joint1", "fp3_joint2", "fp3_joint3",
                "fp3_joint4", "fp3_joint5", "fp3_joint6", "fp3_joint7"]

def main():
    rclpy.init()
    node = Node("cartesian_test", parameter_overrides=[Parameter("use_sim_time", value=True)])

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
    config = MoveItConfigsBuilder("panda", package_name="panda_moveit_config").to_moveit_configs().to_dict()#读取panda_moveit_config包里面的文件
    pipelines = config.pop("planning_pipelines")
    config["planning_pipelines.pipeline_names"] = pipelines
    config["planning_pipelines.namespace"] = ""

    moveit = MoveItPy(node_name="moveit_py", config_dict=config)
    arm = moveit.get_planning_component("arm")
    scene_monitor = moveit.get_planning_scene_monitor()
    from moveit_msgs.msg import CollisionObject
    from shape_msgs.msg import SolidPrimitive

    def make_box(name, x, y, z, sx, sy, sz):
        obj = CollisionObject()
        obj.id = name
        obj.header.frame_id = "world"
        obj.operation = CollisionObject.ADD
        box = SolidPrimitive()
        box.type = SolidPrimitive.BOX
        box.dimensions = [sx, sy, sz]
        obj.primitives = [box]
        p = Pose()
        p.position.x, p.position.y, p.position.z = x, y, z
        p.orientation.w = 1.0
        obj.primitive_poses = [p]
        return obj

    with scene_monitor.read_write() as scene:
        scene.apply_collision_object(make_box("table", 0.5, 0.0, 0.05, 2.0, 2.0, 0.1))
        scene.apply_collision_object(make_box("grasp_object", 0.6, 0.0, 0.115, 0.03, 0.03, 0.03))

    model = moveit.get_robot_model()

# ---- 查当末端执行器当前位姿作为起点 ----
    start = RobotState(model)
    start.set_joint_group_positions("arm", current)
    arm.set_start_state(robot_state=start)

    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)
    while rclpy.ok():
      rclpy.spin_once(node, timeout_sec=0.1)
      try:
        t = tf_buffer.lookup_transform("world", "fp3_hand_tcp", rclpy.time.Time())
        break
      except Exception:
        pass
    
    t = tf_buffer.lookup_transform("world", "fp3_hand_tcp", rclpy.time.Time())

    start_pose = Pose()
    start_pose.position.x = t.transform.translation.x
    start_pose.position.y = t.transform.translation.y
    start_pose.position.z = t.transform.translation.z
    start_pose.orientation = t.transform.rotation

    #目标位姿
    target_pose = Pose()
    target_pose.position.x = start_pose.position.x
    target_pose.position.y = start_pose.position.y
    target_pose.position.z = start_pose.position.z + 0.05   # 上升 5cm
    target_pose.orientation = start_pose.orientation

    # 用 IK 求解目标位姿对应的关节角
    goal = RobotState(model)
    try:
        goal.set_from_ik("arm", target_pose, "fp3_hand_tcp")
    except Exception as e:
        node.get_logger().error(f"IK 无解: {e}"); return

    arm.set_goal_state(robot_state=goal)

    # 用 Pilz LIN 做直线规划
    params = PlanRequestParameters(moveit, "")
    params.planning_pipeline = "pilz_industrial_motion_planner"
    params.planner_id = "LIN"
    params.max_velocity_scaling_factor = 0.1
    params.max_acceleration_scaling_factor = 0.1

    plan_result = arm.plan(single_plan_parameters=params)

    if not plan_result:
        node.get_logger().error("规划失败")
    else:
        jt = plan_result.trajectory.get_robot_trajectory_msg().joint_trajectory
        client = ActionClient(node, FollowJointTrajectory, "/fp3_arm_controller/follow_joint_trajectory")
        if not client.wait_for_server(5.0):
            node.get_logger().error("控制器未就绪"); return

        send_future = client.send_goal_async(FollowJointTrajectory.Goal(trajectory=jt))
        rclpy.spin_until_future_complete(node, send_future)
        goal_handle = send_future.result()
        if not goal_handle or not goal_handle.accepted:
            node.get_logger().error("控制器拒绝"); return

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


