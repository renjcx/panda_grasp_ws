from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'panda_grasp_sim'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        #让编译时候同时打包，配置文件
        (os.path.join('share', package_name, 'launch'),glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'),glob('config/*.yaml')),
        (os.path.join('share', package_name, 'urdf'),glob('urdf/*.xacro')),
        (os.path.join('share', package_name, 'worlds'),glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='renjcx',
    maintainer_email='renjcx3128@gmail.com',
    description='Franka Panda (fp3) pick-and-place simulation with Gazebo Harmonic + MoveIt2',
    license='Apache License 2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'pick_place = panda_grasp_sim.pick_place:main',
            'hand_grasp_test = panda_grasp_sim.hand_grasp_test:main',
            'hand_tf_test = panda_grasp_sim.hand_tf_test:main',
            'cartesian_test = panda_grasp_sim.cartesian_test:main',
            'pick_place_full = panda_grasp_sim.pick_place_full:main',
        ],
    },
)
