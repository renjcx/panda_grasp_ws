# panda_moveit_config 生成指南

> 从已有的 `panda_grasp_sim` 包，用 MoveIt Setup Assistant 从零生成 `panda_moveit_config` 包的完整流程。

---

## 背景：这个包是什么

- `panda_moveit_config` 是 MoveIt 2 的配置包，用来回答 MoveIt 的一系列问题（关节怎么分组、IK 用什么求解器、规划出的轨迹发给哪个控制器……）。
- 它由图形化向导 **MoveIt Setup Assistant (MISA)** 自动生成，生成骨架 = URDF 快照 + `panda.srdf` + 各种 yaml + 8 个 launch 模板 + CMakeLists。
- 生成后日常只需"改参数回答问题"：数值类修改直接编辑 yaml，SRDF 语义类修改（mimic、碰撞矩阵）直接编辑 `panda.srdf`，**只有机器人结构变了才需要重新生成**。

> 项目整体架构与各文件职责见 [`project_overview.md`](project_overview.md)。

### 两个启动命令，别搞混（鸡生蛋问题）

| 命令 | 使用时机 |
|------|---------|
| `ros2 run moveit_setup_assistant moveit_setup_assistant` | **第一次创建**包（包还不存在时只能用这个） |
| `ros2 launch panda_moveit_config setup_assistant.launch.py` | 包**已存在**后，重新打开向导做增量修改 |

> 方式 2 的 launch 文件本身活在 `panda_moveit_config` 包里面，包不存在时根本跑不了——第一次创建必须用方式 1。

---

## 第 0 步：前置条件

```bash
cd ~/panda_grasp_ws
colcon build --symlink-install
source install/setup.bash   # 必须！向导解析 xacro 里的 $(find franka_description) 靠它
```

---

## 第 1 步：从 xacro 导出一份"干净 URDF"

Setup Assistant 可以直接吃 `.xacro`，但 `panda.urdf.xacro` 里有两段**仿真专用**内容（`<gazebo>` 插件段 + `gz_ros2_control` 硬件块），MoveIt 用不上，最好先剥掉：

```bash
xacro src/panda_grasp_sim/urdf/panda.urdf.xacro > /tmp/panda_clean.urdf
```

然后用编辑器删掉 `/tmp/panda_clean.urdf` 里的 `<gazebo>...</gazebo>` 段和 `<ros2_control>...</ros2_control>` 段。

> 删不删都能走完向导（向导会忽略 gazebo 标签），但删了更干净——现有包里的 `config/panda.urdf` 就是没有这两段的。

---

## 第 2 步：打开向导，走完左边栏

```bash
ros2 run moveit_setup_assistant moveit_setup_assistant
```

菜单 **File → New MoveIt Configuration Package**，每一步对应"回答一个问题"：

| 向导步骤 | 你要做的事 | 答案从哪来 | 生成哪个文件 |
|---------|-----------|-----------|-------------|
| ① Start | 浏览选择 `/tmp/panda_clean.urdf` | `panda_grasp_sim` 里的图纸 | `config/panda.urdf` |
| ② Self-Collisions | 点 **Generate Collision Matrix** | 自动采样计算 | `panda.srdf` 里的 `<disable_collisions>` 段 |
| ③ Virtual Joints | 加一个：`world → base`，type=fixed | 你的 xacro 里已有 `world_fixed` 关节 | `panda.srdf` 的 `<virtual_joint>` |
| ④ Planning Groups | 建两组：`arm`（勾 fp3_joint1~7，**选 KDL** 求解器）、`gripper`（勾 fp3_finger_joint1） | 你自己定义（README 里的规划组表） | `panda.srdf` 的 `<group>` + `kinematics.yaml` |
| ⑤ Robot Poses | 跳过 | — | — |
| ⑥ End Effectors | 建 `hand`：parent_link=**fp3_hand**，组选 gripper | 夹爪手掌 link 名 | `panda.srdf` 的 `<end_effector>` |
| ⑦ Passive Joints | 跳过 | — | — |
| ⑧ ros2_control | 添加 3 个控制器：JointStateBroadcaster（全部 9 关节）+ 两个 JointTrajectoryController（`fp3_arm_controller` 管 7 关节、`fp3_gripper_controller` 管手指） | **名字必须和 `panda_controllers.yaml` 完全一致** | `ros2_controllers.yaml` + `panda.ros2_control.xacro`（mock 假硬件） |
| ⑨ Author | 填邮箱 | — | `package.xml` |
| ⑩ Generate | 输出目录选 **`src/panda_moveit_config`**，点 Generate | — | 全部文件 + launch 模板 + CMakeLists |

---

## 第 3 步：生成后必须手改的 2 处

向导生成的是"标准答案"，但本项目有两处特殊：

1. **`panda.srdf` 加 `<mimic_joint>`**：sim 侧的 xacro 现在**没有** URDF 级 mimic（因为 Gazebo 不执行它，已删掉），所以向导不会知道双指是从动关系，必须手动补上：

   ```xml
   <mimic_joint joint="fp3_finger_joint2" mimic_joint="fp3_finger_joint1" multiplier="1.0" offset="0.0"/>
   ```

2. **检查 `moveit_controllers.yaml`**：确认控制器名 / action 名与 Gazebo 里实际跑的一致（`fp3_arm_controller`、`fp3_gripper_controller`）。

---

## 第 4 步：编译收工

```bash
cd ~/panda_grasp_ws
colcon build --symlink-install
source install/setup.bash
```

之后 `ros2 launch panda_grasp_sim sim_with_moveit.launch.py` 就能通过 `MoveItConfigsBuilder("panda", package_name="panda_moveit_config")` 找到这个包了。**以后**想再改规划组、重算碰撞矩阵，就用方式 2 的 launch 命令（会载入已有配置做增量修改）。

---

## 生成后日常修改的分界线

| 你改了什么 | 怎么办 |
|-----------|--------|
| 限位数值、默认速度缩放、IK 超时等**参数值** | 直接编辑对应 yaml，不用重新生成 |
| SRDF 层：`<mimic_joint>`、`<disable_collisions>` | 直接编辑 `panda.srdf` |
| 控制器映射、action 名字 | 直接编辑 `moveit_controllers.yaml` |
| **机器人结构变了**：加/删关节、改 link 名、改夹爪结构 | 必须重新跑 Setup Assistant（或手动同步 URDF 快照） |

> ⚠️ **最大的坑**：`config/panda.urdf` 是生成那一刻的**快照**，不会跟着 `panda_grasp_sim/urdf/panda.urdf.xacro` 自动更新。MoveIt 侧加载快照、Gazebo 侧加载 xacro，**两边必须保持同一份结构**。改完 sim 包的 xacro 后，要么重新生成，要么手动把新 URDF 拷过去替换。
>
> 另外，重新生成会**覆盖**手改内容（如 mimic 声明），重新生成前记得备份手改部分。

---

## 一句话总结

向导问你的问题（关节怎么分组、末端执行器是谁、IK 用什么、控制器叫什么），答案全都来自 `panda_grasp_sim` 里已经写好的内容——你的工作就是把这些"已经知道的事"在图形界面里点一遍，剩下的事（URDF 快照、SRDF、yaml、launch 模板）它自动写。
