# MCAP 交付规范（供应商版）

### **元数据（Metadata）**



```YAML
Metadata:
  # session 的 unix 起始时间
  #（mcap 内所有消息时间均相对于此时间）
  session-metadata.start-time-unix: int
  session-metadata.end-time-unix: int
```



### **数据通道（Topics）**



```YAML
topics:
  # --- 双目 RGB ---
  # 仅有单路 RGB 时，只指定 left
  - name: /top-left-camera/image-raw
    type: foxglove.CompressedVideo
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      format: string        # 编码，如 "av1"、"h265"
      fps: float64
      data: uint8[]

  - name: /top-right-camera/image-raw
    type: foxglove.CompressedVideo
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      format: string
      fps: float64
      data: uint8[]

  # --- 深度 ---
  # 配准（对齐）到左目 RGB 相机，因此 frame-id 须与 /top-left-camera 一致。
  # 像素数据：16-bit 单通道（16UC1）；1 单位 = 1 mm（绝对/公制深度）；
  # 无效或无回波 = 0；仅无损编码（每条消息承载 16-bit PNG）。
  - name: /top-left-camera/depth-raw
    type: foxglove.CompressedImage
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      frame-id: string      # 与 /top-left-camera 同一 frame
      format: string        # "png"
      data: uint8[]         # 16UC1，1 单位 = 1 mm，无效 = 0

  # --- 内参（所有相机必需）---
  - name: /top-left-camera/camera-info
    type: foxglove.CameraCalibration
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      width: int32
      height: int32
      distortion-model: string
      D: float64[]
      K: float64[]
      R: float64[]
      P: float64[]

  - name: /top-right-camera/camera-info
    type: foxglove.CameraCalibration
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      width: int32
      height: int32
      distortion-model: string
      D: float64[]
      K: float64[]
      R: float64[]
      P: float64[]

  # --- 外参 ---
  # 交付双目 + 深度时必需。frame 命名须与相机消息中的相机名称一致。
  # 不可用时，将 parent / child 置为 ""。
  - name: /tf-static
    type: foxglove.FrameTransforms
    fields:
      transforms:
        - timestamp:
            seconds: int32
            nanos: int32
          parent-frame-id: string
          child-frame-id: string
          translation: foxglove.Vector3
          rotation: foxglove.Quaternion

  # --- IMU ---
  # 头戴相机必需。采样率 > 200 Hz。参照 ROS sensor_msgs/Imu。
  - name: /head-imu
    fields:
      timestamp:
        seconds: int32
        nanos: int32
      frame-id: string                       # IMU frame（通过 /tf-static 关联到相机）
      orientation: foxglove.Quaternion       # 可选；未估计时填单位四元数
      angular-velocity: foxglove.Vector3     # rad/s
      linear-acceleration: foxglove.Vector3  # m/s^2（含重力）

# 注意事项：
# - 所有流必须共用同一时钟；时间相对于 start-time-unix。
# - 若包含腕部相机，topic 名称使用 "/wrist-left-camera" 与
#   "/wrist-right-camera"。
```



