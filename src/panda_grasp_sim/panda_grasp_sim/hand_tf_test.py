import time
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

def main():
    rclpy.init()
    node = Node("hand_tf_test", parameter_overrides=[Parameter("use_sim_time",value=True)])

    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=1.0)
        try:
            t = tf_buffer.lookup_transform("world", "fp3_hand_tcp",rclpy.time.Time())
            pos = t.transform.translation
            rot = t.transform.rotation
            node.get_logger().info(f"位置: ({pos.x:.3f}, {pos.y:.3f},{pos.z:.3f})")
            node.get_logger().info(f"姿态: ({rot.x:.3f}, {rot.y:.3f},{rot.z:.3f}, {rot.w:.3f})")
        except Exception:
            node.get_logger().warn("等待 TF...", throttle_duration_sec=5)
        
        time.sleep(1.0)
        


    rclpy.shutdown()

if __name__ == "__main__":
    main()