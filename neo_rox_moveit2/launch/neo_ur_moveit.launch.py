# Copyright (c) 2024 Neobotix GmbH.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#    * Neither the name of the {copyright_holder} nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

#
# Author: Pradheep Padmanabhan
# Contributor: Adarsh Karan K P

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
from launch_ros.descriptions import ParameterValue, ParameterFile
from moveit_configs_utils import MoveItConfigsBuilder
from pathlib import Path
from neo_rox_moveit2.launch_common import load_yaml
from launch.event_handlers import OnProcessExit
from launch.actions import RegisterEventHandler

def launch_setup(context, *args, **kwargs):

    # Initialize Arguments
    arm_type = LaunchConfiguration("arm_type")
    # General arguments
    moveit_config_package = LaunchConfiguration("moveit_config_package")
    prefix = LaunchConfiguration("prefix")
    use_sim_time = LaunchConfiguration("use_sim_time")
    launch_rviz = LaunchConfiguration("launch_rviz")
    ur_dc = LaunchConfiguration("use_ur_dc")
    use_gz = LaunchConfiguration("use_gz")
    
    urdf = os.path.join(get_package_share_directory('rox_description'),
        'urdf',
        'rox.urdf.xacro')
    
    # MoveIt Configuration
    srdf = os.path.join(get_package_share_directory('neo_rox_moveit2'),
        'srdf',
        'rox.srdf.xacro')

    # Controllers Configuration
    controllers_yaml = os.path.join(
        get_package_share_directory(str(moveit_config_package.perform(context))),
        "config",
        "controllers.yaml",
    )
    controllers_yaml_with_substitutions = ParameterFile(controllers_yaml, allow_substs=True)
    # Evaluate the parameter file to apply dynamic substitutions
    controllers_yaml_with_substitutions.evaluate(context)
    controllers_yaml = os.path.join(
        get_package_share_directory('neo_rox_moveit2'),
        "config",
        str(controllers_yaml_with_substitutions.param_file)
    )
    
    # Joint Limits Configuration
    joint_limits_yaml = os.path.join(
        get_package_share_directory(str(moveit_config_package.perform(context))),
        "config",
        "joint_limits.yaml",
    )
    joint_limits_yaml_with_substitutions = ParameterFile(joint_limits_yaml, allow_substs=True)
    # Evaluate the parameter file to apply dynamic substitutions
    joint_limits_yaml_with_substitutions.evaluate(context)
    joint_limits_yaml = os.path.join(
        get_package_share_directory('neo_rox_moveit2'),
        "config",
        str(joint_limits_yaml_with_substitutions.param_file)
    )

    moveit_config = (
        MoveItConfigsBuilder(robot_name="rox_ur", package_name="neo_rox_moveit2")
        .robot_description_semantic(file_path=srdf, mappings={"prefix": prefix})
        .robot_description(file_path=urdf, mappings={"arm_type": arm_type, "use_gz": use_gz, "use_ur_dc": ur_dc, "force_abs_paths": "true"})
        .trajectory_execution(file_path=controllers_yaml)
        .joint_limits(file_path=joint_limits_yaml)
        .to_moveit_configs()
    )

    # Start the actual move_group node/action server
    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[
            moveit_config.to_dict(),
            {"use_sim_time": use_sim_time},
        ],
    )

    # rviz with moveit configuration
    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare(moveit_config_package), "rviz", "view_robot.rviz"]
    )
    rviz_node = Node(
        package="rviz2",
        condition=IfCondition(launch_rviz),
        executable="rviz2",
        name="rviz2_moveit",
        output="log",
        arguments=["-d", rviz_config_file],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.robot_description_kinematics,
            moveit_config.planning_pipelines,
            moveit_config.joint_limits,
            {
                "use_sim_time": use_sim_time,
            },
        ],
    )

    wait_robot_description = Node(
        package="ur_robot_driver",
        executable="wait_for_robot_description",
        output="screen",
    )

    handler = RegisterEventHandler(
        OnProcessExit(
            target_action=wait_robot_description,
            on_exit=[move_group_node, rviz_node],
        )
    )

    nodes_to_start = [wait_robot_description, handler]

    return nodes_to_start

def generate_launch_description():

    declared_arguments = []
    # UR specific arguments

    declared_arguments.append(
        DeclareLaunchArgument(
            'arm_type', 
            default_value='',
            description='Arm Types:\n'
                        '\t Elite Arms: ec66, cs66\n'
                        '\t Universal Robotics (UR): ur5, ur10, ur5e, ur10e' 
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "moveit_config_package",
            default_value="neo_rox_moveit2",
            description="MoveIt config package with robot SRDF/XACRO files. Usually the argument \
        is not set, it enables use of a custom moveit config.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="false",
            description="Make MoveIt to use simulation time. This is needed for the trajectory planing in simulation.",
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            "prefix",
            default_value='""',
            description="Prefix of the joint names, useful for \
        multi-robot setup. If changed than also joint names in the controllers' configuration \
        have to be updated.",
        )
    )
    
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_ur_dc",
            default_value="false",
            description="Uses a shorter cabin box. Check with Neobotix, before selecting.",
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument(
            "use_gz",
            default_value="false",
            description="Whether to enable Gazebo simulation.",
        )
    )

    declared_arguments.append(
        DeclareLaunchArgument("launch_rviz", default_value="true", description="Launch RViz?")
    )

    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
