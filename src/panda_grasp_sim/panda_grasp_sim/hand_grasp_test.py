import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
import builtin_interfaces.msg
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


def build_gripper_trajectory(open_or_close:str):
    #"构造夹爪轨迹"
    jt = JointTrajectory()
    jt.joint_names = ["fp3_finger_joint1"]

    point = JointTrajectoryPoint()
    point.positions = [0.04 if open_or_close == "open" else 0.0]
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

def main():
    rclpy.init()
    node = Node("hand_grasp_test")

    send_gripper_command(node, "open")    # 张开
    time.sleep(2)
    send_gripper_command(node, "close")   # 闭合
    time.sleep(2)
    send_gripper_command(node, "open")    # 再张开

    rclpy.shutdown()

if __name__ == "__main__":
    main()