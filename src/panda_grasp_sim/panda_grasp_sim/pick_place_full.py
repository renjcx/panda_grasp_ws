import numpy as np
import time
import rclpy
import builtin_interfaces.msg
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
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from moveit.planning import PlanningSceneMonitor #规划碰撞避让

ARM_JOINTS = ["fp3_joint1", "fp3_joint2", "fp3_joint3",
                "fp3_joint4", "fp3_joint5", "fp3_joint6", "fp3_joint7"]


def build_gripper_trajectory(open_or_close:str):
    #"构造夹爪轨迹"
    jt = JointTrajectory()
    # 两个手指由控制器同步驱动（Gazebo 不执行 URDF mimic 约束）
    jt.joint_names = ["fp3_finger_joint1", "fp3_finger_joint2"]

    point = JointTrajectoryPoint()
    pos = 0.04 if open_or_close == "open" else 0.0
    point.positions = [pos, pos]
    point.time_from_start = builtin_interfaces.msg.Duration(sec=1, nanosec=0)#1秒完成闭合
    jt.points = [point]
    return jt

def send_gripper_command(node, open_or_close):
    jt = build_gripper_trajectory(open_or_close)#每次调用完重新构造轨迹
    client = ActionClient(node, FollowJointTrajectory, "/fp3_gripper_controller/follow_joint_trajectory")
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

def plan_and_execute_arm(node, moveit, arm, model, current, target_pose, planner_id):

    # 设起始状态
    start = RobotState(model)
    start.set_joint_group_positions("arm", current)
    arm.set_start_state(robot_state=start)

    # IK
    goal = RobotState(model)
    goal.set_from_ik("arm", target_pose, "fp3_hand_tcp")
    arm.set_goal_state(robot_state=goal)

    # 用 Pilz LIN 做直线规划
    params = PlanRequestParameters(moveit, "")
    params.planning_pipeline = "pilz_industrial_motion_planner"
    params.planner_id = planner_id #"ptp" or "lin"
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
            new_current = None
            def on_js(msg):
                nonlocal new_current
                idx = [msg.name.index(j) for j in ARM_JOINTS if j in msg.name]
                if len(idx) == 7:
                    new_current = np.array([msg.position[i] for i in idx])
            sub = node.create_subscription(JointState, "/joint_states", on_js, 10)
            while new_current is None:
                rclpy.spin_once(node, timeout_sec=0.1)
            node.destroy_subscription(sub)
            return new_current
        else:
            node.get_logger().error(result.result.error_string)

def main():
    rclpy.init()
    node = Node("pick_place_full", parameter_overrides=[Parameter("use_sim_time", value=True)])

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
    # ---- 碰撞物体识别 ----
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

    #with scene_monitor.read_write() as scene:
        #scene.apply_collision_object(make_box("table", 0.5, 0.0, 0.05, 2.0, 2.0, 0.1))
        #scene.apply_collision_object(make_box("grasp_object", 0.6, 0.0, 0.115, 0.03, 0.03, 0.03))
    # ---- 碰撞物体识别 ----

    model = moveit.get_robot_model()

# ---- 查当末端执行器当前位姿作为起点 ----
    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
        try:
            t = tf_buffer.lookup_transform("world", "fp3_hand_tcp", rclpy.time.Time())
            break
        except Exception:
            pass

    ori = t.transform.rotation   # 用当前的朝向

    pre_grasp = Pose()
    pre_grasp.position.x = 0.58
    pre_grasp.position.y = 0.0
    pre_grasp.position.z = 0.215
    pre_grasp.orientation.x = 0.5
    pre_grasp.orientation.y = 0.5
    pre_grasp.orientation.z = 0.0
    pre_grasp.orientation.w = 0.0

    grasp = Pose()
    grasp.position.x = 0.58
    grasp.position.y = 0.0
    grasp.position.z = 0.118
    grasp.orientation.x = 0.5
    grasp.orientation.y = 0.5
    grasp.orientation.z = 0.0
    grasp.orientation.w = 0.0

    # ---- Pick 流程 ----
    node.get_logger().info("① 去 pre-grasp")
    current = plan_and_execute_arm(node, moveit, arm, model, current, pre_grasp, "LIN")
    time.sleep(0.5)

    node.get_logger().info("② 张开")
    send_gripper_command(node, "open")
    time.sleep(2.0)

    node.get_logger().info("③ 下降")
    current = plan_and_execute_arm(node, moveit, arm, model, current, grasp, "LIN")
    time.sleep(0.5)

    node.get_logger().info("④ 闭合")
    send_gripper_command(node, "close")
    time.sleep(5.0)

    node.get_logger().info("⑤ 抬起")
    current = plan_and_execute_arm(node, moveit, arm, model, current, pre_grasp, "LIN")

    node.get_logger().info("=== Pick 完成 ===")

    rclpy.shutdown()

if __name__ == "__main__":
   main()
