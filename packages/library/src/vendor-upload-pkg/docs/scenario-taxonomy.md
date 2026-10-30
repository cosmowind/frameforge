# Scenario Taxonomy — v2 参考

本文档对应 publish.example.com/vendors task-box 创建时 `--scenario` 参数的合法取值列表。

总计 **647** 个叶子 task(对应 10 个 domain × 37 个 sector × 106 个 category)。

> 数据来源:`F:\sys\o\frameforge\frameforge\frameforge\src\lib\scene-taxonomy-v2.ts` (upstream `origin/master`)
> 中文翻译为人工整理;**不存在的翻译会回退为英文**,请补全后再发布给前端。

## 翻译覆盖率

- task:已翻译 647/647, 待补 0 个(完整列表见末尾"待翻译 task"小节)
- sector:已翻译 72/37, 待补 0 个
- category:已翻译 337/104, 待补 0 个

## 用法

```bash
python3 upload_pkg.py \
    --cookie-file ./cookie.txt \
    --scenario D01-S01-C01-T01 \
    --task-description "Plasma cutting" \
    --environment-description "..." \
    --operator-name "..." \
    --capture-mode stereo \
    --session-dir ./captures/session_000001
```

## D01 Industrial Manufacturing / 工业制造

### D01-S01 Metalworking / 金属加工

#### D01-S01-C01 Cutting / 切割

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S01-C01-T01` | 1 | Plasma cutting | 等离子切割 | `plasma_cutting` |
| `D01-S01-C01-T02` | 2 | Laser cutting | 激光切割 | `laser_cutting` |
| `D01-S01-C01-T03` | 3 | Oxy-acetylene flame cutting | 氧乙炔火焰切割 | `oxy-acetylene_flame_cutting` |
| `D01-S01-C01-T04` | 4 | Waterjet cutting | 水刀切割 | `waterjet_cutting` |
| `D01-S01-C01-T05` | 5 | Bandsaw stock cutting | 带锯下料切割 | `bandsaw_stock_cutting` |
| `D01-S01-C01-T06` | 6 | Shear plate cutting | 剪板切割 | `shear_plate_cutting` |

#### D01-S01-C02 Welding / 焊接

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S01-C02-T01` | 7 | Manual arc welding (SMAW) | 手工电弧焊 | `manual_arc_welding_smaw` |
| `D01-S01-C02-T02` | 8 | MIG/MAG gas-shielded welding | MIG/MAG 气体保护焊 | `mig_mag_gas-shielded_welding` |
| `D01-S01-C02-T03` | 9 | TIG argon welding | TIG 氩弧焊 | `tig_argon_welding` |
| `D01-S01-C02-T04` | 10 | Spot welding | 点焊 | `spot_welding` |
| `D01-S01-C02-T05` | 11 | Laser welding | 激光焊 | `laser_welding` |
| `D01-S01-C02-T06` | 12 | Brazing | 钎焊 | `brazing` |
| `D01-S01-C02-T07` | 13 | Weld bead grinding & cleaning | 焊缝打磨与清理 | `weld_bead_grinding_cleaning` |
| `D01-S01-C02-T08` | 14 | Weld NDT inspection | 焊缝无损检测 | `weld_ndt_inspection` |

#### D01-S01-C03 Machining / 机加工

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S01-C03-T01` | 15 | Lathe turning | 车床车削 | `lathe_turning` |
| `D01-S01-C03-T02` | 16 | Milling | 铣削 | `milling` |
| `D01-S01-C03-T03` | 17 | Drilling and tapping | 钻孔与攻丝 | `drilling_and_tapping` |
| `D01-S01-C03-T04` | 18 | Surface grinding | 平面磨削 | `surface_grinding` |
| `D01-S01-C03-T05` | 19 | CNC programming & operation | CNC 编程与操作 | `cnc_programming_operation` |
| `D01-S01-C03-T06` | 20 | Wire EDM machining | 线切割加工 | `wire_edm_machining` |
| `D01-S01-C03-T07` | 21 | Deburring | 去毛刺 | `deburring` |

#### D01-S01-C04 Forming / 成型

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S01-C04-T01` | 22 | Stamping | 冲压 | `stamping` |
| `D01-S01-C04-T02` | 23 | Press brake bending | 折弯机弯板 | `press_brake_bending` |
| `D01-S01-C04-T03` | 24 | Forging | 锻造 | `forging` |
| `D01-S01-C04-T04` | 25 | Casting pouring | 浇注 | `casting_pouring` |
| `D01-S01-C04-T05` | 26 | Drawing/stretch forming | 拉延/拉伸成型 | `drawing_stretch_forming` |
| `D01-S01-C04-T06` | 27 | Roll forming | 辊压成型 | `roll_forming` |

#### D01-S01-C05 Surface Treatment / 表面处理

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S01-C05-T01` | 28 | Sandblasting | 喷砂 | `sandblasting` |
| `D01-S01-C05-T02` | 29 | Electroplating | 电镀 | `electroplating` |
| `D01-S01-C05-T03` | 30 | Anodizing | 阳极氧化 | `anodizing` |
| `D01-S01-C05-T04` | 31 | Spray painting | 喷漆 | `spray_painting` |
| `D01-S01-C05-T05` | 32 | Heat treatment / quenching | 热处理/淬火 | `heat_treatment_quenching` |
| `D01-S01-C05-T06` | 33 | Polishing & buffing | 抛光与打磨 | `polishing_buffing` |

### D01-S02 Assembly Line / 流水线装配

#### D01-S02-C01 Electronics Assembly / 电子装配

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S02-C01-T01` | 34 | SMT feeder loading | SMT 上料 | `smt_feeder_loading` |
| `D01-S02-C01-T02` | 35 | Through-hole soldering | 通孔焊接 | `through-hole_soldering` |
| `D01-S02-C01-T03` | 36 | PCB inspection | PCB 检验 | `pcb_inspection` |
| `D01-S02-C01-T04` | 37 | Wire harness assembly | 线束组装 | `wire_harness_assembly` |
| `D01-S02-C01-T05` | 38 | Connector crimping | 连接器压接 | `connector_crimping` |
| `D01-S02-C01-T06` | 39 | Display module assembly | 显示模组组装 | `display_module_assembly` |

#### D01-S02-C02 Mechanical Assembly / 机械装配

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S02-C02-T01` | 40 | Bolt fastening assembly | 螺栓紧固装配 | `bolt_fastening_assembly` |
| `D01-S02-C02-T02` | 41 | Gearbox assembly | 齿轮箱装配 | `gearbox_assembly` |
| `D01-S02-C02-T03` | 42 | Bearing press-fit | 轴承压装 | `bearing_press-fit` |
| `D01-S02-C02-T04` | 43 | Hydraulic component assembly | 液压元件装配 | `hydraulic_component_assembly` |
| `D01-S02-C02-T05` | 44 | Final unit assembly | 总机装配 | `final_unit_assembly` |
| `D01-S02-C02-T06` | 45 | Torque verification | 扭矩校验 | `torque_verification` |

#### D01-S02-C03 Automotive Assembly / 汽车总装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S02-C03-T01` | 46 | Engine hoisting & install | 发动机吊装 | `engine_hoisting_install` |
| `D01-S02-C03-T02` | 47 | Chassis marriage | 底盘合装 | `chassis_marriage` |
| `D01-S02-C03-T03` | 48 | Interior trim installation | 内饰安装 | `interior_trim_installation` |
| `D01-S02-C03-T04` | 49 | Door assembly | 车门装配 | `door_assembly` |
| `D01-S02-C03-T05` | 50 | Glass installation | 玻璃安装 | `glass_installation` |
| `D01-S02-C03-T06` | 51 | Tire mounting on line | 线内轮胎装配 | `tire_mounting_on_line` |

#### D01-S02-C04 Packaging / 包装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S02-C04-T01` | 52 | Product boxing | 产品装箱 | `product_boxing` |
| `D01-S02-C04-T02` | 53 | Carton sealing | 纸箱封口 | `carton_sealing` |
| `D01-S02-C04-T03` | 54 | Label application | 贴标 | `label_application` |
| `D01-S02-C04-T04` | 55 | Stretch wrapping | 缠绕膜包装 | `stretch_wrapping` |
| `D01-S02-C04-T05` | 56 | Palletizing | 码垛 | `palletizing` |
| `D01-S02-C04-T06` | 57 | Filling and capping | 灌装与封盖 | `filling_and_capping` |

### D01-S03 Process Industry / 流程工业

#### D01-S03-C01 Chemical Operations / 化工操作

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S03-C01-T01` | 58 | Reactor charging | 反应釜投料 | `reactor_charging` |
| `D01-S03-C01-T02` | 59 | Pipeline valve switching | 管线阀门切换 | `pipeline_valve_switching` |
| `D01-S03-C01-T03` | 60 | Sampling for lab analysis | 取样送检 | `sampling_for_lab_analysis` |
| `D01-S03-C01-T04` | 61 | In-reactor reaction monitoring | 反应过程监控 | `in-reactor_reaction_monitoring` |
| `D01-S03-C01-T05` | 62 | Filtration / separation | 过滤/分离 | `filtration_separation` |
| `D01-S03-C01-T06` | 63 | Drying and granulation | 干燥与造粒 | `drying_and_granulation` |

#### D01-S03-C02 Refining & Petrochem / 炼油与石化

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S03-C02-T01` | 64 | Distillation column patrol | 精馏塔巡检 | `distillation_column_patrol` |
| `D01-S03-C02-T02` | 65 | Pump changeover | 泵切换 | `pump_changeover` |
| `D01-S03-C02-T03` | 66 | Heat exchanger cleaning | 换热器清洗 | `heat_exchanger_cleaning` |
| `D01-S03-C02-T04` | 67 | Tank farm receiving/dispatch | 罐区收/发油 | `tank_farm_receiving_dispatch` |
| `D01-S03-C02-T05` | 68 | Flare system operation | 火炬系统操作 | `flare_system_operation` |
| `D01-S03-C02-T06` | 69 | Catalyst replacement | 催化剂更换 | `catalyst_replacement` |

#### D01-S03-C03 Pharmaceutical Production / 药品生产

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S03-C03-T01` | 70 | Raw material weighing & batching | 原料称量配料 | `raw_material_weighing_batching` |
| `D01-S03-C03-T02` | 71 | Sterilization | 灭菌 | `sterilization` |
| `D01-S03-C03-T03` | 72 | Tableting & coating | 压片与包衣 | `tableting_coating` |
| `D01-S03-C03-T04` | 73 | Aseptic filling | 无菌灌装 | `aseptic_filling` |
| `D01-S03-C03-T05` | 74 | Lyophilization (freeze-drying) | 冻干 | `lyophilization_freeze-drying` |
| `D01-S03-C03-T06` | 75 | Clean-in-place (CIP) | 原位清洗(CIP) | `clean-in-place_cip` |

#### D01-S03-C04 Food Processing / 食品加工

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S03-C04-T01` | 76 | Raw material sorting & washing | 原料分拣与清洗 | `raw_material_sorting_washing` |
| `D01-S03-C04-T02` | 77 | Cutting & prepping | 切配 | `cutting_prepping` |
| `D01-S03-C04-T03` | 78 | Cooking & sterilization | 蒸煮与灭菌 | `cooking_sterilization` |
| `D01-S03-C04-T04` | 79 | Fermentation control | 发酵控制 | `fermentation_control` |
| `D01-S03-C04-T05` | 80 | Filling and canning | 灌装与罐装 | `filling_and_canning` |
| `D01-S03-C04-T06` | 81 | Quick freezing & cold storage | 速冻与冷藏 | `quick_freezing_cold_storage` |

### D01-S04 QC & Metrology / 质量与计量

#### D01-S04-C01 Dimensional Inspection / 尺寸检验(通用)

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S04-C01-T01` | 82 | Vernier caliper measurement | 游标卡尺测量 | `vernier_caliper_measurement` |
| `D01-S04-C01-T02` | 83 | Micrometer measurement | 千分尺测量 | `micrometer_measurement` |
| `D01-S04-C01-T03` | 84 | CMM coordinate measurement | 三坐标测量 | `cmm_coordinate_measurement` |
| `D01-S04-C01-T04` | 85 | Go/no-go gauge inspection | 过/不过规检验 | `go_no-go_gauge_inspection` |
| `D01-S04-C01-T05` | 86 | Optical projector inspection | 光学投影仪检测 | `optical_projector_inspection` |
| `D01-S04-C01-T06` | 87 | Laser scan measurement | 激光扫描测量 | `laser_scan_measurement` |

#### D01-S04-C02 Non-Destructive Testing / 无损检测

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S04-C02-T01` | 88 | Ultrasonic testing (UT) | 超声波检测(UT) | `ultrasonic_testing_ut` |
| `D01-S04-C02-T02` | 89 | Radiographic testing (RT) | 射线检测(RT) | `radiographic_testing_rt` |
| `D01-S04-C02-T03` | 90 | Magnetic particle testing (MT) | 磁粉检测(MT) | `magnetic_particle_testing_mt` |
| `D01-S04-C02-T04` | 91 | Penetrant testing (PT) | 渗透检测(PT) | `penetrant_testing_pt` |
| `D01-S04-C02-T05` | 92 | Eddy current testing | 涡流检测 | `eddy_current_testing` |
| `D01-S04-C02-T06` | 93 | Visual inspection | 外观检验 | `visual_inspection` |

#### D01-S04-C03 Functional Testing / 功能测试

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S04-C03-T01` | 94 | Leak / air-tightness test | 气密性检测 | `leak_air-tightness_test` |
| `D01-S04-C03-T02` | 95 | Hydrostatic pressure test | 水压试验 | `hydrostatic_pressure_test` |
| `D01-S04-C03-T03` | 96 | Electrical performance test | 电气性能测试 | `electrical_performance_test` |
| `D01-S04-C03-T04` | 97 | Burn-in / aging test | 老化测试 | `burn-in_aging_test` |
| `D01-S04-C03-T05` | 98 | Vibration test | 振动测试 | `vibration_test` |
| `D01-S04-C03-T06` | 99 | Weighing & metrology | 称重与计量 | `weighing_metrology` |

### D01-S05 Warehousing & Logistics / 仓储物流

#### D01-S05-C01 Inbound / Outbound / 入库/出库

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S05-C01-T01` | 100 | Goods receiving | 收货 | `goods_receiving` |
| `D01-S05-C01-T02` | 101 | Barcode scan-in | 扫码入库 | `barcode_scan-in` |
| `D01-S05-C01-T03` | 102 | Order picking | 订单拣货 | `order_picking` |
| `D01-S05-C01-T04` | 103 | Pick verification & packing | 拣货复核与打包 | `pick_verification_packing` |
| `D01-S05-C01-T05` | 104 | Outbound loading | 出库装车 | `outbound_loading` |
| `D01-S05-C01-T06` | 105 | Returns processing | 退货处理 | `returns_processing` |

#### D01-S05-C02 Material Handling / 物料搬运

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S05-C02-T01` | 106 | Forklift handling | 叉车作业 | `forklift_handling` |
| `D01-S05-C02-T02` | 107 | Pallet jack handling | 地牛作业 | `pallet_jack_handling` |
| `D01-S05-C02-T03` | 108 | Shelf put-away | 上架 | `shelf_put-away` |
| `D01-S05-C02-T04` | 109 | Pallet stacking | 托盘堆码 | `pallet_stacking` |
| `D01-S05-C02-T05` | 110 | AGV dispatch monitoring | AGV 调度监控 | `agv_dispatch_monitoring` |
| `D01-S05-C02-T06` | 111 | Crane lifting | 起重机吊装 | `crane_lifting` |

#### D01-S05-C03 Inventory Management / 库存管理

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S05-C03-T01` | 112 | Cycle counting | 盘点 | `cycle_counting` |
| `D01-S05-C03-T02` | 113 | Bin location adjustment | 库位调整 | `bin_location_adjustment` |
| `D01-S05-C03-T03` | 114 | Label replacement | 标签更换 | `label_replacement` |
| `D01-S05-C03-T04` | 115 | Cold storage temperature patrol | 冷库温度巡检 | `cold_storage_temperature_patrol` |
| `D01-S05-C03-T05` | 116 | Hazmat storage management | 危化品仓储管理 | `hazmat_storage_management` |
| `D01-S05-C03-T06` | 117 | WMS data entry | WMS 数据录入 | `wms_data_entry` |

### D01-S06 Equipment Maintenance / 设备保养

#### D01-S06-C01 Mechanical Repair / 机械维修

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S06-C01-T01` | 118 | Bearing replacement | 轴承更换 | `bearing_replacement` |
| `D01-S06-C01-T02` | 119 | Belt replacement & tensioning | 皮带更换与张紧 | `belt_replacement_tensioning` |
| `D01-S06-C01-T03` | 120 | Coupling alignment | 联轴器对中 | `coupling_alignment` |
| `D01-S06-C01-T04` | 121 | Gearbox overhaul | 齿轮箱大修 | `gearbox_overhaul` |
| `D01-S06-C01-T05` | 122 | Seal replacement | 密封件更换 | `seal_replacement` |
| `D01-S06-C01-T06` | 123 | Lubrication & greasing | 润滑与加注 | `lubrication_greasing` |

#### D01-S06-C02 Hydraulic & Pneumatic / 液压与气动

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S06-C02-T01` | 124 | Hydraulic oil change | 液压油更换 | `hydraulic_oil_change` |
| `D01-S06-C02-T02` | 125 | Hydraulic line repair | 液压管路维修 | `hydraulic_line_repair` |
| `D01-S06-C02-T03` | 126 | Cylinder replacement | 油缸更换 | `cylinder_replacement` |
| `D01-S06-C02-T04` | 127 | Solenoid valve replacement | 电磁阀更换 | `solenoid_valve_replacement` |
| `D01-S06-C02-T05` | 128 | Pressure adjustment | 压力调整 | `pressure_adjustment` |
| `D01-S06-C02-T06` | 129 | Leak troubleshooting | 泄漏排查 | `leak_troubleshooting` |

#### D01-S06-C03 Electrical Repair / 电气维修

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S06-C03-T01` | 130 | Motor replacement | 电机更换 | `motor_replacement` |
| `D01-S06-C03-T02` | 131 | Contactor replacement | 接触器更换 | `contactor_replacement` |
| `D01-S06-C03-T03` | 132 | Wiring repair | 电气线路维修 | `wiring_repair` |
| `D01-S06-C03-T04` | 133 | VFD commissioning | 变频器调试 | `vfd_commissioning` |
| `D01-S06-C03-T05` | 134 | PLC program troubleshooting | PLC 程序故障排查 | `plc_program_troubleshooting` |
| `D01-S06-C03-T06` | 135 | Switchgear repair | 配电柜维修 | `switchgear_repair` |

#### D01-S06-C04 Inspection Patrol / 巡检

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S06-C04-T01` | 136 | Daily equipment checks | 设备日检 | `daily_equipment_checks` |
| `D01-S06-C04-T02` | 137 | Vibration & temperature patrol | 振动与温度巡检 | `vibration_temperature_patrol` |
| `D01-S06-C04-T03` | 138 | Lubrication point inspection | 润滑点检查 | `lubrication_point_inspection` |
| `D01-S06-C04-T04` | 139 | Instrument reading log | 仪表读数记录 | `instrument_reading_log` |
| `D01-S06-C04-T05` | 140 | Fault shutdown diagnosis | 故障停机诊断 | `fault_shutdown_diagnosis` |
| `D01-S06-C04-T06` | 141 | Preventive maintenance | 预防性保养 | `preventive_maintenance` |

### D01-S07 Industrial Control / 工业控制

#### D01-S07-C01 Automation Commissioning / 自动化调试

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S07-C01-T01` | 142 | Sensor calibration | 传感器标定 | `sensor_calibration` |
| `D01-S07-C01-T02` | 143 | Actuator commissioning | 执行器调试 | `actuator_commissioning` |
| `D01-S07-C01-T03` | 144 | PLC programming & debug | PLC 编程与调试 | `plc_programming_debug` |
| `D01-S07-C01-T04` | 145 | HMI configuration | 触摸屏组态 | `hmi_configuration` |
| `D01-S07-C01-T05` | 146 | Servo tuning | 伺服调试 | `servo_tuning` |
| `D01-S07-C01-T06` | 147 | Network communication setup | 网络通信配置 | `network_communication_setup` |

#### D01-S07-C02 Robotics Operation / 机器人操作

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S07-C02-T01` | 148 | Teach-pendant programming | 示教编程 | `teach-pendant_programming` |
| `D01-S07-C02-T02` | 149 | Trajectory tuning | 轨迹调试 | `trajectory_tuning` |
| `D01-S07-C02-T03` | 150 | Fixture adjustment | 夹具调整 | `fixture_adjustment` |
| `D01-S07-C02-T04` | 151 | Robot body maintenance | 机器人本体保养 | `robot_body_maintenance` |
| `D01-S07-C02-T05` | 152 | End-effector tool change | 末端工具更换 | `end-effector_tool_change` |
| `D01-S07-C02-T06` | 153 | Cobot configuration | 协作机器人配置 | `cobot_configuration` |

#### D01-S07-C03 Central Control Room / 中央控制室

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D01-S07-C03-T01` | 154 | DCS monitoring | DCS 监控 | `dcs_monitoring` |
| `D01-S07-C03-T02` | 155 | Alarm handling | 报警处理 | `alarm_handling` |
| `D01-S07-C03-T03` | 156 | Process parameter adjustment | 工艺参数调整 | `process_parameter_adjustment` |
| `D01-S07-C03-T04` | 157 | Trend analysis & logging | 趋势分析与记录 | `trend_analysis_logging` |
| `D01-S07-C03-T05` | 158 | Interlock testing | 联锁测试 | `interlock_testing` |
| `D01-S07-C03-T06` | 159 | Emergency switchover | 应急切换 | `emergency_switchover` |

## D02 Construction / Construction

### D02-S01 Structural Civil Work / 结构土建

#### D02-S01-C01 Rebar Work / 钢筋作业

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S01-C01-T01` | 160 | Rebar cutting | 钢筋切断 | `rebar_cutting` |
| `D02-S01-C01-T02` | 161 | Rebar bending | 钢筋弯曲 | `rebar_bending` |
| `D02-S01-C01-T03` | 162 | Rebar tying | 钢筋绑扎 | `rebar_tying` |
| `D02-S01-C01-T04` | 163 | Rebar welded splicing | 钢筋焊接接头 | `rebar_welded_splicing` |
| `D02-S01-C01-T05` | 164 | Mechanical coupler splicing | 机械连接接头 | `mechanical_coupler_splicing` |
| `D02-S01-C01-T06` | 165 | Cover block placement | 保护层垫块放置 | `cover_block_placement` |

#### D02-S01-C02 Concrete / 混凝土

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S01-C02-T01` | 166 | Formwork setup | 模板支立 | `formwork_setup` |
| `D02-S01-C02-T02` | 167 | Concrete pouring | 混凝土浇筑 | `concrete_pouring` |
| `D02-S01-C02-T03` | 168 | Vibration compaction | 振捣密实 | `vibration_compaction` |
| `D02-S01-C02-T04` | 169 | Screeding & finishing | 找平与收面 | `screeding_finishing` |
| `D02-S01-C02-T05` | 170 | Curing & water spraying | 养护与洒水 | `curing_water_spraying` |
| `D02-S01-C02-T06` | 171 | Formwork stripping | 拆模 | `formwork_stripping` |

#### D02-S01-C03 Masonry / 砌筑

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S01-C03-T01` | 172 | Brick wall laying | 砌砖墙 | `brick_wall_laying` |
| `D02-S01-C03-T02` | 173 | Block wall laying | 砌块墙 | `block_wall_laying` |
| `D02-S01-C03-T03` | 174 | Mortar pointing | 砂浆勾缝 | `mortar_pointing` |
| `D02-S01-C03-T04` | 175 | Tie-column construction | 构造柱施工 | `tie-column_construction` |
| `D02-S01-C03-T05` | 176 | Lintel installation | 过梁安装 | `lintel_installation` |
| `D02-S01-C03-T06` | 177 | Wall layout marking | 墙体放线 | `wall_layout_marking` |

#### D02-S01-C04 Steel Structure / 钢结构

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S01-C04-T01` | 178 | Steel beam hoisting | 钢梁吊装 | `steel_beam_hoisting` |
| `D02-S01-C04-T02` | 179 | High-strength bolt tightening | 高强螺栓紧固 | `high-strength_bolt_tightening` |
| `D02-S01-C04-T03` | 180 | On-site welding | 现场焊接 | `on-site_welding` |
| `D02-S01-C04-T04` | 181 | Member alignment | 构件校正 | `member_alignment` |
| `D02-S01-C04-T05` | 182 | Profiled steel decking | 压型钢板铺设 | `profiled_steel_decking` |
| `D02-S01-C04-T06` | 183 | Fireproof coating spray | 防火涂料喷涂 | `fireproof_coating_spray` |

### D02-S02 Interior Finishing / 室内装修

#### D02-S02-C01 Plastering & Painting / 抹灰与涂装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S02-C01-T01` | 184 | Wall plastering | 墙面抹灰 | `wall_plastering` |
| `D02-S02-C01-T02` | 185 | Putty skim coat | 腻子刮涂 | `putty_skim_coat` |
| `D02-S02-C01-T03` | 186 | Wall sanding | 墙面打磨 | `wall_sanding` |
| `D02-S02-C01-T04` | 187 | Latex paint rolling | 乳胶漆辊涂 | `latex_paint_rolling` |
| `D02-S02-C01-T05` | 188 | Spray painting | 喷漆 | `spray_painting` |
| `D02-S02-C01-T06` | 189 | Wallpaper hanging | 贴墙纸 | `wallpaper_hanging` |

#### D02-S02-C02 Flooring / 地板

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S02-C02-T01` | 190 | Floor leveling | 地面找平 | `floor_leveling` |
| `D02-S02-C02-T02` | 191 | Tile laying | 瓷砖铺贴 | `tile_laying` |
| `D02-S02-C02-T03` | 192 | Wood flooring install | 木地板安装 | `wood_flooring_install` |
| `D02-S02-C02-T04` | 193 | Self-leveling compound | 自流平施工 | `self-leveling_compound` |
| `D02-S02-C02-T05` | 194 | Stone slab laying | 石材铺装 | `stone_slab_laying` |
| `D02-S02-C02-T06` | 195 | Carpet laying | 地毯铺设 | `carpet_laying` |

#### D02-S02-C03 Ceiling & Partition / 吊顶与隔断

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S02-C03-T01` | 196 | Stud framing | 轻钢龙骨隔墙 | `stud_framing` |
| `D02-S02-C03-T02` | 197 | Drywall hanging | 石膏板封板 | `drywall_hanging` |
| `D02-S02-C03-T03` | 198 | Mineral fiber ceiling | 矿棉板吊顶 | `mineral_fiber_ceiling` |
| `D02-S02-C03-T04` | 199 | Light-gauge steel partition | 轻钢龙骨隔断 | `light-gauge_steel_partition` |
| `D02-S02-C03-T05` | 200 | Integrated ceiling install | 集成吊顶安装 | `integrated_ceiling_install` |
| `D02-S02-C03-T06` | 201 | Decorative ceiling work | 装饰吊顶 | `decorative_ceiling_work` |

#### D02-S02-C04 Doors & Windows / 门窗

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S02-C04-T01` | 202 | Aluminum window install | 铝合金窗安装 | `aluminum_window_install` |
| `D02-S02-C04-T02` | 203 | uPVC window install | 塑钢窗安装 | `upvc_window_install` |
| `D02-S02-C04-T03` | 204 | Security door install | 防盗门安装 | `security_door_install` |
| `D02-S02-C04-T04` | 205 | Interior door install | 室内门安装 | `interior_door_install` |
| `D02-S02-C04-T05` | 206 | Curtain wall install | 幕墙安装 | `curtain_wall_install` |
| `D02-S02-C04-T06` | 207 | Sealant caulking | 密封胶打胶 | `sealant_caulking` |

### D02-S03 MEP Installation / 机电安装

#### D02-S03-C01 Plumbing / 管道

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S03-C01-T01` | 208 | Water supply piping | 给水管道 | `water_supply_piping` |
| `D02-S03-C01-T02` | 209 | Drain piping | 排水管道 | `drain_piping` |
| `D02-S03-C01-T03` | 210 | Pipe pressure testing | 管道试压 | `pipe_pressure_testing` |
| `D02-S03-C01-T04` | 211 | Sanitary fixture install | 卫生器具安装 | `sanitary_fixture_install` |
| `D02-S03-C01-T05` | 212 | Water pump installation | 水泵安装 | `water_pump_installation` |
| `D02-S03-C01-T06` | 213 | Pipe insulation | 管道保温 | `pipe_insulation` |

#### D02-S03-C02 HVAC / 暖通空调

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S03-C02-T01` | 214 | Ductwork fabrication & install | 风管制作与安装 | `ductwork_fabrication_install` |
| `D02-S03-C02-T02` | 215 | AHU installation | 新风机组安装 | `ahu_installation` |
| `D02-S03-C02-T03` | 216 | Fan coil unit install | 风机盘管安装 | `fan_coil_unit_install` |
| `D02-S03-C02-T04` | 217 | Refrigerant line brazing | 冷媒管焊接 | `refrigerant_line_brazing` |
| `D02-S03-C02-T05` | 218 | Insulation wrap | 保温包扎 | `insulation_wrap` |
| `D02-S03-C02-T06` | 219 | System commissioning | 系统调试 | `system_commissioning` |

#### D02-S03-C03 Electrical Install / 电气安装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S03-C03-T01` | 220 | Cable tray installation | 桥架安装 | `cable_tray_installation` |
| `D02-S03-C03-T02` | 221 | Conduit installation | 线管敷设 | `conduit_installation` |
| `D02-S03-C03-T03` | 222 | Cable pulling | 电缆敷设 | `cable_pulling` |
| `D02-S03-C03-T04` | 223 | Distribution panel install | 配电箱安装 | `distribution_panel_install` |
| `D02-S03-C03-T05` | 224 | Lighting fixture install | 灯具安装 | `lighting_fixture_install` |
| `D02-S03-C03-T06` | 225 | Switch & socket install | 开关插座安装 | `switch_socket_install` |

#### D02-S03-C04 Fire Protection / 消防

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S03-C04-T01` | 226 | Sprinkler pipe install | 喷淋管安装 | `sprinkler_pipe_install` |
| `D02-S03-C04-T02` | 227 | Fire hydrant install | 消火栓安装 | `fire_hydrant_install` |
| `D02-S03-C04-T03` | 228 | Smoke detector install | 烟感安装 | `smoke_detector_install` |
| `D02-S03-C04-T04` | 229 | Firestop sealing | 防火封堵 | `firestop_sealing` |
| `D02-S03-C04-T05` | 230 | Gas suppression install | 气体灭火安装 | `gas_suppression_install` |
| `D02-S03-C04-T06` | 231 | Fire alarm commissioning | 火灾报警调试 | `fire_alarm_commissioning` |

### D02-S04 Foundation & Underground / 地基与地下工程

#### D02-S04-C01 Geotechnical / 岩土

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S04-C01-T01` | 232 | Pile drilling | 钻孔桩 | `pile_drilling` |
| `D02-S04-C01-T02` | 233 | Rebar cage lowering | 钢筋笼下放 | `rebar_cage_lowering` |
| `D02-S04-C01-T03` | 234 | Bored pile concreting | 钻孔灌注桩浇筑 | `bored_pile_concreting` |
| `D02-S04-C01-T04` | 235 | Excavation | 开挖 | `excavation` |
| `D02-S04-C01-T05` | 236 | Slope shoring | 边坡支护 | `slope_shoring` |
| `D02-S04-C01-T06` | 237 | Dewatering well installation | 降水井施工 | `dewatering_well_installation` |

#### D02-S04-C02 Waterproofing / 防水

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S04-C02-T01` | 238 | Membrane waterproofing | 卷材防水 | `membrane_waterproofing` |
| `D02-S04-C02-T02` | 239 | Liquid-applied waterproofing | 涂膜防水 | `liquid-applied_waterproofing` |
| `D02-S04-C02-T03` | 240 | Waterproof detailing | 防水细部处理 | `waterproof_detailing` |
| `D02-S04-C02-T04` | 241 | Flood test | 蓄水试验 | `flood_test` |
| `D02-S04-C02-T05` | 242 | Roof waterproofing | 屋面防水 | `roof_waterproofing` |
| `D02-S04-C02-T06` | 243 | Basement waterproofing | 地下室防水 | `basement_waterproofing` |

### D02-S05 Roads & Municipal / 道路与市政

#### D02-S05-C01 Paving / 铺装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S05-C01-T01` | 244 | Subgrade compaction | 路基压实 | `subgrade_compaction` |
| `D02-S05-C01-T02` | 245 | Asphalt paving | 沥青摊铺 | `asphalt_paving` |
| `D02-S05-C01-T03` | 246 | Asphalt rolling | 沥青碾压 | `asphalt_rolling` |
| `D02-S05-C01-T04` | 247 | Concrete pavement pouring | 混凝土路面浇筑 | `concrete_pavement_pouring` |
| `D02-S05-C01-T05` | 248 | Curb installation | 路缘石安装 | `curb_installation` |
| `D02-S05-C01-T06` | 249 | Road marking | 路面标线 | `road_marking` |

#### D02-S05-C02 Utility Networks / 公用管网

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D02-S05-C02-T01` | 250 | Trenching for utilities | 管沟开挖 | `trenching_for_utilities` |
| `D02-S05-C02-T02` | 251 | Pipe jacking | 顶管 | `pipe_jacking` |
| `D02-S05-C02-T03` | 252 | Manhole masonry | 检查井砌筑 | `manhole_masonry` |
| `D02-S05-C02-T04` | 253 | Storm/sewer pipe laying | 雨/污水管铺设 | `storm_sewer_pipe_laying` |
| `D02-S05-C02-T05` | 254 | Trench backfilling | 管沟回填 | `trench_backfilling` |
| `D02-S05-C02-T06` | 255 | Pipe pushing | 拉管 | `pipe_pushing` |

## D03 Repair Services / Repair Services

### D03-S01 Automotive Repair / 汽车维修(总)

#### D03-S01-C01 Engine / 发动机

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S01-C01-T01` | 256 | Engine diagnostics | 发动机诊断 | `engine_diagnostics` |
| `D03-S01-C01-T02` | 257 | Spark plug replacement | 火花塞更换 | `spark_plug_replacement` |
| `D03-S01-C01-T03` | 258 | Timing belt replacement | 正时皮带更换 | `timing_belt_replacement` |
| `D03-S01-C01-T04` | 259 | Cylinder head repair | 缸盖维修 | `cylinder_head_repair` |
| `D03-S01-C01-T05` | 260 | Oil and filter change | 机油机滤更换 | `oil_and_filter_change` |
| `D03-S01-C01-T06` | 261 | Throttle body cleaning | 节气门清洗 | `throttle_body_cleaning` |
| `D03-S01-C01-T07` | 262 | Carbon deposit cleaning | 积碳清洗 | `carbon_deposit_cleaning` |
| `D03-S01-C01-T08` | 263 | Compression test | 缸压测试 | `compression_test` |

#### D03-S01-C02 Chassis & Drivetrain / 底盘与传动

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S01-C02-T01` | 264 | Brake pad replacement | 刹车片更换 | `brake_pad_replacement` |
| `D03-S01-C02-T02` | 265 | Brake rotor replacement | 刹车盘更换 | `brake_rotor_replacement` |
| `D03-S01-C02-T03` | 266 | Tire replacement | 轮胎更换 | `tire_replacement` |
| `D03-S01-C02-T04` | 267 | Wheel alignment | 四轮定位 | `wheel_alignment` |
| `D03-S01-C02-T05` | 268 | Suspension/shock replacement | 悬挂/减震更换 | `suspension_shock_replacement` |
| `D03-S01-C02-T06` | 269 | Transmission fluid change | 变速箱油更换 | `transmission_fluid_change` |
| `D03-S01-C02-T07` | 270 | Clutch replacement | 离合器更换 | `clutch_replacement` |
| `D03-S01-C02-T08` | 271 | Driveshaft repair | 传动轴维修 | `driveshaft_repair` |

#### D03-S01-C03 Electrical Systems / 电气系统

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S01-C03-T01` | 272 | Battery replacement & test | 电池更换与测试 | `battery_replacement_test` |
| `D03-S01-C03-T02` | 273 | Alternator replacement | 发电机更换 | `alternator_replacement` |
| `D03-S01-C03-T03` | 274 | Starter motor repair | 起动机维修 | `starter_motor_repair` |
| `D03-S01-C03-T04` | 275 | Wiring fault diagnosis | 线路故障诊断 | `wiring_fault_diagnosis` |
| `D03-S01-C03-T05` | 276 | Headlight/bulb replacement | 大灯/灯泡更换 | `headlight_bulb_replacement` |
| `D03-S01-C03-T06` | 277 | Sensor replacement | 传感器更换 | `sensor_replacement` |
| `D03-S01-C03-T07` | 278 | ECU code read/clear | ECU 故障码读取/清除 | `ecu_code_read_clear` |

#### D03-S01-C04 AC & Body / 空调与车身

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S01-C04-T01` | 279 | AC refrigerant recharge | 空调冷媒加注 | `ac_refrigerant_recharge` |
| `D03-S01-C04-T02` | 280 | AC compressor replacement | 空调压缩机更换 | `ac_compressor_replacement` |
| `D03-S01-C04-T03` | 281 | Body panel repair | 车身板件修复 | `body_panel_repair` |
| `D03-S01-C04-T04` | 282 | Paint touch-up | 漆面修补 | `paint_touch-up` |
| `D03-S01-C04-T05` | 283 | Auto glass replacement | 汽车玻璃更换 | `auto_glass_replacement` |
| `D03-S01-C04-T06` | 284 | Interior refurbishment | 内饰翻新 | `interior_refurbishment` |

### D03-S02 Appliance Repair / 电器维修

#### D03-S02-C01 Major Appliances / 大型家电

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S02-C01-T01` | 285 | Refrigerator cooling repair | 冰箱制冷维修 | `refrigerator_cooling_repair` |
| `D03-S02-C01-T02` | 286 | Washing machine repair | 洗衣机维修 | `washing_machine_repair` |
| `D03-S02-C01-T03` | 287 | Air conditioner installation | 空调安装 | `air_conditioner_installation` |
| `D03-S02-C01-T04` | 288 | AC recharge and cleaning | 空调加氟与清洗 | `ac_recharge_and_cleaning` |
| `D03-S02-C01-T05` | 289 | Water heater repair | 热水器维修 | `water_heater_repair` |
| `D03-S02-C01-T06` | 290 | Dishwasher repair | 洗碗机维修 | `dishwasher_repair` |

#### D03-S02-C02 Kitchen Appliances / 厨房电器

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S02-C02-T01` | 291 | Range hood repair & clean | 油烟机维修与清洗 | `range_hood_repair_clean` |
| `D03-S02-C02-T02` | 292 | Gas stove repair | 燃气灶维修 | `gas_stove_repair` |
| `D03-S02-C02-T03` | 293 | Microwave oven repair | 微波炉维修 | `microwave_oven_repair` |
| `D03-S02-C02-T04` | 294 | Electric oven repair | 电烤箱维修 | `electric_oven_repair` |
| `D03-S02-C02-T05` | 295 | Water purifier repair | 净水器维修 | `water_purifier_repair` |
| `D03-S02-C02-T06` | 296 | Rice cooker repair | 电饭煲维修 | `rice_cooker_repair` |

#### D03-S02-C03 Small Appliances / 小家电

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S02-C03-T01` | 297 | Electric fan repair | 电风扇维修 | `electric_fan_repair` |
| `D03-S02-C03-T02` | 298 | Vacuum cleaner repair | 吸尘器维修 | `vacuum_cleaner_repair` |
| `D03-S02-C03-T03` | 299 | Hair dryer repair | 电吹风维修 | `hair_dryer_repair` |
| `D03-S02-C03-T04` | 300 | Blender repair | 料理机维修 | `blender_repair` |
| `D03-S02-C03-T05` | 301 | Iron repair | 电熨斗维修 | `iron_repair` |
| `D03-S02-C03-T06` | 302 | Robot vacuum repair | 扫地机器人维修 | `robot_vacuum_repair` |

### D03-S03 Electronics Repair / 电子产品维修

#### D03-S03-C01 Board-Level Repair / 板级维修

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S03-C01-T01` | 303 | Board-level electronics repair | 板级电子维修 | `board-level_electronics_repair` |
| `D03-S03-C01-T02` | 304 | Component soldering | 元件焊接 | `component_soldering` |
| `D03-S03-C01-T03` | 305 | Capacitor/resistor replacement | 电容/电阻更换 | `capacitor_resistor_replacement` |
| `D03-S03-C01-T04` | 306 | BGA reballing/rework | BGA 返修/重植 | `bga_reballing_rework` |
| `D03-S03-C01-T05` | 307 | Short circuit tracing | 短路排查 | `short_circuit_tracing` |
| `D03-S03-C01-T06` | 308 | Power module repair | 电源模块维修 | `power_module_repair` |

#### D03-S03-C02 Consumer Electronics / 消费电子

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S03-C02-T01` | 309 | Phone screen replacement | 手机屏幕更换 | `phone_screen_replacement` |
| `D03-S03-C02-T02` | 310 | Phone battery replacement | 手机电池更换 | `phone_battery_replacement` |
| `D03-S03-C02-T03` | 311 | Phone motherboard repair | 手机主板维修 | `phone_motherboard_repair` |
| `D03-S03-C02-T04` | 312 | Laptop teardown & repair | 笔记本拆机维修 | `laptop_teardown_repair` |
| `D03-S03-C02-T05` | 313 | Tablet repair | 平板维修 | `tablet_repair` |
| `D03-S03-C02-T06` | 314 | Data recovery | 数据恢复 | `data_recovery` |

#### D03-S03-C03 AV Equipment / 音视频设备

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S03-C03-T01` | 315 | TV screen repair | 电视屏维修 | `tv_screen_repair` |
| `D03-S03-C03-T02` | 316 | Speaker/audio repair | 音箱/音响维修 | `speaker_audio_repair` |
| `D03-S03-C03-T03` | 317 | Projector repair | 投影机维修 | `projector_repair` |
| `D03-S03-C03-T04` | 318 | Monitor repair | 显示器维修 | `monitor_repair` |
| `D03-S03-C03-T05` | 319 | Game console repair | 游戏机维修 | `game_console_repair` |
| `D03-S03-C03-T06` | 320 | Camera repair | 相机维修 | `camera_repair` |

### D03-S04 Building MEP Repair / 楼宇机电维修

#### D03-S04-C01 Plumbing Repair / 管道维修

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S04-C01-T01` | 321 | Drain unclogging | 下水道疏通 | `drain_unclogging` |
| `D03-S04-C01-T02` | 322 | Faucet replacement | 水龙头更换 | `faucet_replacement` |
| `D03-S04-C01-T03` | 323 | Leak pipe patching | 漏水管修补 | `leak_pipe_patching` |
| `D03-S04-C01-T04` | 324 | Toilet parts replacement | 马桶配件更换 | `toilet_parts_replacement` |
| `D03-S04-C01-T05` | 325 | Water heater piping repair | 热水器管路维修 | `water_heater_piping_repair` |
| `D03-S04-C01-T06` | 326 | Floor heating repair | 地暖维修 | `floor_heating_repair` |

#### D03-S04-C02 Electrical Repair / 电气维修

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S04-C02-T01` | 327 | Switch/socket replacement | 开关/插座更换 | `switch_socket_replacement` |
| `D03-S04-C02-T02` | 328 | Ground fault / breaker tripping diagnosis | 漏电/跳闸诊断 | `ground_fault_breaker_tripping_diagnosis` |
| `D03-S04-C02-T03` | 329 | Light fixture replacement | 灯具更换 | `light_fixture_replacement` |
| `D03-S04-C02-T04` | 330 | Rewiring | 重新布线 | `rewiring` |
| `D03-S04-C02-T05` | 331 | Distribution box repair | 配电箱维修 | `distribution_box_repair` |
| `D03-S04-C02-T06` | 332 | Low-voltage system repair | 弱电系统维修 | `low-voltage_system_repair` |

#### D03-S04-C03 Doors, Locks & Hardware / 门窗锁与五金

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S04-C03-T01` | 333 | Door lock replacement | 门锁更换 | `door_lock_replacement` |
| `D03-S04-C03-T02` | 334 | Smart lock installation | 智能锁安装 | `smart_lock_installation` |
| `D03-S04-C03-T03` | 335 | Hinge adjustment | 铰链调整 | `hinge_adjustment` |
| `D03-S04-C03-T04` | 336 | Door closer replacement | 闭门器更换 | `door_closer_replacement` |
| `D03-S04-C03-T05` | 337 | Window hardware repair | 门窗五金维修 | `window_hardware_repair` |
| `D03-S04-C03-T06` | 338 | Glass sealing replacement | 玻璃密封条更换 | `glass_sealing_replacement` |

### D03-S05 Heavy Equipment Repair / 重型设备维修

#### D03-S05-C01 Construction Machinery / 工程机械

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S05-C01-T01` | 339 | Excavator hydraulic repair | 挖掘机液压维修 | `excavator_hydraulic_repair` |
| `D03-S05-C01-T02` | 340 | Loader maintenance | 装载机保养 | `loader_maintenance` |
| `D03-S05-C01-T03` | 341 | Engine overhaul | 发动机大修 | `engine_overhaul` |
| `D03-S05-C01-T04` | 342 | Track replacement | 履带更换 | `track_replacement` |
| `D03-S05-C01-T05` | 343 | Slewing bearing repair | 回转轴承维修 | `slewing_bearing_repair` |
| `D03-S05-C01-T06` | 344 | Electronic control inspection | 电控检测 | `electronic_control_inspection` |

#### D03-S05-C02 Agricultural Machinery / 农业机械

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S05-C02-T01` | 345 | Tractor maintenance | 拖拉机保养 | `tractor_maintenance` |
| `D03-S05-C02-T02` | 346 | Harvester repair | 收割机维修 | `harvester_repair` |
| `D03-S05-C02-T03` | 347 | Water pump repair | 水泵维修 | `water_pump_repair` |
| `D03-S05-C02-T04` | 348 | Diesel engine repair | 柴油机维修 | `diesel_engine_repair` |
| `D03-S05-C02-T05` | 349 | Transmission parts replacement | 变速箱配件更换 | `transmission_parts_replacement` |
| `D03-S05-C02-T06` | 350 | Cutter blade replacement | 割刀更换 | `cutter_blade_replacement` |

#### D03-S05-C03 General Equipment / 通用设备

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D03-S05-C03-T01` | 351 | Motor repair | 电机维修 | `motor_repair` |
| `D03-S05-C03-T02` | 352 | Reducer/gearbox repair | 减速机维修 | `reducer_gearbox_repair` |
| `D03-S05-C03-T03` | 353 | Air compressor repair | 空压机维修 | `air_compressor_repair` |
| `D03-S05-C03-T04` | 354 | Generator set repair | 发电机组维修 | `generator_set_repair` |
| `D03-S05-C03-T05` | 355 | Fan/blower repair | 风机维修 | `fan_blower_repair` |
| `D03-S05-C03-T06` | 356 | Pump repair | 水泵维修 | `pump_repair` |

## D04 Hardware & Tools / Hardware & Tools

### D04-S01 Hand Tool Work / 手工工具作业

#### D04-S01-C01 Fastening & Disassembly / 紧固与拆装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S01-C01-T01` | 357 | Screwdriver driving | 螺丝刀拧紧 | `screwdriver_driving` |
| `D04-S01-C01-T02` | 358 | Wrench tightening | 扳手紧固 | `wrench_tightening` |
| `D04-S01-C01-T03` | 359 | Socket wrench work | 套筒扳手作业 | `socket_wrench_work` |
| `D04-S01-C01-T04` | 360 | Torque wrench operation | 扭力扳手操作 | `torque_wrench_operation` |
| `D04-S01-C01-T05` | 361 | Rivet gun riveting | 铆钉枪铆接 | `rivet_gun_riveting` |
| `D04-S01-C01-T06` | 362 | Snap-ring plier work | 卡簧钳作业 | `snap-ring_plier_work` |

#### D04-S01-C02 Cutting & Sawing / 切割与锯削

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S01-C02-T01` | 363 | Hand saw cutting | 手锯切割 | `hand_saw_cutting` |
| `D04-S01-C02-T02` | 364 | Hacksaw pipe cutting | 钢锯管材切割 | `hacksaw_pipe_cutting` |
| `D04-S01-C02-T03` | 365 | Tubing cutter cutting | 切管器切割 | `tubing_cutter_cutting` |
| `D04-S01-C02-T04` | 366 | Glass scoring & breaking | 玻璃划割与掰断 | `glass_scoring_breaking` |
| `D04-S01-C02-T05` | 367 | Utility knife cutting | 美工刀切割 | `utility_knife_cutting` |
| `D04-S01-C02-T06` | 368 | Diagonal plier wire cutting | 斜口钳剪线 | `diagonal_plier_wire_cutting` |

#### D04-S01-C03 Measuring & Marking / 测量与划线

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S01-C03-T01` | 369 | Tape measure use | 卷尺测量 | `tape_measure_use` |
| `D04-S01-C03-T02` | 370 | Spirit level leveling | 水准仪找平 | `spirit_level_leveling` |
| `D04-S01-C03-T03` | 371 | Square layout marking | 直角尺划线 | `square_layout_marking` |
| `D04-S01-C03-T04` | 372 | Chalk line snapping | 弹线 | `chalk_line_snapping` |
| `D04-S01-C03-T05` | 373 | Laser line projection | 激光投线 | `laser_line_projection` |
| `D04-S01-C03-T06` | 374 | Feeler gauge measurement | 塞尺测量 | `feeler_gauge_measurement` |

### D04-S02 Power Tools / 电动工具

#### D04-S02-C01 Drilling Tools / 钻具

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S02-C01-T01` | 375 | Electric drill drilling | 电钻钻孔 | `electric_drill_drilling` |
| `D04-S02-C01-T02` | 376 | Impact drill hole-making | 冲击钻打孔 | `impact_drill_hole-making` |
| `D04-S02-C01-T03` | 377 | Rotary hammer chiseling | 电锤凿削 | `rotary_hammer_chiseling` |
| `D04-S02-C01-T04` | 378 | Hole saw cutting | 开孔器开孔 | `hole_saw_cutting` |
| `D04-S02-C01-T05` | 379 | Magnetic base drill drilling | 磁力钻钻孔 | `magnetic_base_drill_drilling` |
| `D04-S02-C01-T06` | 380 | Tapping machine work | 攻丝机作业 | `tapping_machine_work` |

#### D04-S02-C02 Cutting & Grinding / 切割与打磨

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S02-C02-T01` | 381 | Angle grinder cutting | 角磨机切割 | `angle_grinder_cutting` |
| `D04-S02-C02-T02` | 382 | Angle grinder grinding | 角磨机打磨 | `angle_grinder_grinding` |
| `D04-S02-C02-T03` | 383 | Chop saw stock cutting | 切铝机下料 | `chop_saw_stock_cutting` |
| `D04-S02-C02-T04` | 384 | Buffer polishing | 抛光机抛光 | `buffer_polishing` |
| `D04-S02-C02-T05` | 385 | Circular saw cutting | 圆锯切割 | `circular_saw_cutting` |
| `D04-S02-C02-T06` | 386 | Jigsaw curve cutting | 曲线锯切割 | `jigsaw_curve_cutting` |

#### D04-S02-C03 Pneumatic Tools / 气动工具

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S02-C03-T01` | 387 | Nail gun nailing | 气钉枪打钉 | `nail_gun_nailing` |
| `D04-S02-C03-T02` | 388 | Pneumatic wrench fastening | 气动扳手紧固 | `pneumatic_wrench_fastening` |
| `D04-S02-C03-T03` | 389 | Spray gun painting | 喷枪喷涂 | `spray_gun_painting` |
| `D04-S02-C03-T04` | 390 | Pneumatic sanding | 气动打磨 | `pneumatic_sanding` |
| `D04-S02-C03-T05` | 391 | Pneumatic rivet gun | 气动铆钉枪 | `pneumatic_rivet_gun` |
| `D04-S02-C03-T06` | 392 | Air blow cleaning | 气吹清洁 | `air_blow_cleaning` |

### D04-S03 Fabrication & Fitting / 装配与管件

#### D04-S03-C01 Bench Fitting / 钳工装配

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S03-C01-T01` | 393 | Filing | 锉削 | `filing` |
| `D04-S03-C01-T02` | 394 | Chiseling | 凿削 | `chiseling` |
| `D04-S03-C01-T03` | 395 | Scraping | 刮削 | `scraping` |
| `D04-S03-C01-T04` | 396 | Layout & drilling | 划线与钻孔 | `layout_drilling` |
| `D04-S03-C01-T05` | 397 | Manual tapping | 手动攻丝 | `manual_tapping` |
| `D04-S03-C01-T06` | 398 | Assembly fitting | 装配修配 | `assembly_fitting` |

#### D04-S03-C02 Pipefitting / 管道安装

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D04-S03-C02-T01` | 399 | Pipe threading | 管螺纹加工 | `pipe_threading` |
| `D04-S03-C02-T02` | 400 | Pipe bending | 管道弯制 | `pipe_bending` |
| `D04-S03-C02-T03` | 401 | Pipe fitting connection | 管件连接 | `pipe_fitting_connection` |
| `D04-S03-C02-T04` | 402 | Flange alignment | 法兰对中 | `flange_alignment` |
| `D04-S03-C02-T05` | 403 | Pipe support fabrication | 管架制作 | `pipe_support_fabrication` |
| `D04-S03-C02-T06` | 404 | Pipe pressure testing | 管道试压 | `pipe_pressure_testing` |

## D05 Textile & Apparel / Textile & Apparel

### D05-S01 Textile Production / 纺织生产

#### D05-S01-C01 Spinning / 纺纱

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S01-C01-T01` | 405 | Opening & cleaning operation | 开清棉 | `opening_cleaning_operation` |
| `D05-S01-C01-T02` | 406 | Carding machine tending | 梳棉机值车 | `carding_machine_tending` |
| `D05-S01-C01-T03` | 407 | Drawing frame operation | 并条机操作 | `drawing_frame_operation` |
| `D05-S01-C01-T04` | 408 | Roving frame operation | 粗纱机操作 | `roving_frame_operation` |
| `D05-S01-C01-T05` | 409 | Spinning frame piecing | 细纱接头 | `spinning_frame_piecing` |
| `D05-S01-C01-T06` | 410 | Winding operation | 络筒操作 | `winding_operation` |

#### D05-S01-C02 Weaving / 织造

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S01-C02-T01` | 411 | Warping operation | 整经操作 | `warping_operation` |
| `D05-S01-C02-T02` | 412 | Drawing-in (heald & reed) | 穿综穿筘 | `drawing-in_heald_reed` |
| `D05-S01-C02-T03` | 413 | Loom tending | 织机值车 | `loom_tending` |
| `D05-S01-C02-T04` | 414 | End/pick break repair | 断经/断纬处理 | `end_pick_break_repair` |
| `D05-S01-C02-T05` | 415 | Cloth inspection & mending | 验布与修布 | `cloth_inspection_mending` |
| `D05-S01-C02-T06` | 416 | Cloth roll doffing | 落布 | `cloth_roll_doffing` |

#### D05-S01-C03 Dyeing & Printing / 染整与印花

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S01-C03-T01` | 417 | Pre-treatment / desizing | 前处理/退浆 | `pre-treatment_desizing` |
| `D05-S01-C03-T02` | 418 | Dyeing operation | 染色操作 | `dyeing_operation` |
| `D05-S01-C03-T03` | 419 | Printing operation | 印花操作 | `printing_operation` |
| `D05-S01-C03-T04` | 420 | Setting / finishing | 定型/后整理 | `setting_finishing` |
| `D05-S01-C03-T05` | 421 | Color matching & sampling | 配色与打样 | `color_matching_sampling` |
| `D05-S01-C03-T06` | 422 | Finished goods inspection | 成品检验 | `finished_goods_inspection` |

### D05-S02 Garment Making / 成衣制作

#### D05-S02-C01 Cutting / 切割

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S02-C01-T01` | 423 | Marker making & lay-up | 排料与铺料 | `marker_making_lay-up` |
| `D05-S02-C01-T02` | 424 | Fabric cutting | 裁剪 | `fabric_cutting` |
| `D05-S02-C01-T03` | 425 | Fusing/interlining | 粘合/衬布 | `fusing_interlining` |
| `D05-S02-C01-T04` | 426 | Bundling & ticketing | 扎捆与贴票 | `bundling_ticketing` |
| `D05-S02-C01-T05` | 427 | Pattern making | 制版 | `pattern_making` |
| `D05-S02-C01-T06` | 428 | Marking & drafting | 画样与打版 | `marking_drafting` |

#### D05-S02-C02 Sewing / 缝纫

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S02-C02-T01` | 429 | Flat-lock sewing | 绷缝 | `flat-lock_sewing` |
| `D05-S02-C02-T02` | 430 | Overlock serging | 包缝 | `overlock_serging` |
| `D05-S02-C02-T03` | 431 | Button & buttonhole sewing | 钉扣与开扣眼 | `button_buttonhole_sewing` |
| `D05-S02-C02-T04` | 432 | Zipper attachment | 装拉链 | `zipper_attachment` |
| `D05-S02-C02-T05` | 433 | Sleeve & collar setting | 上袖与上领 | `sleeve_collar_setting` |
| `D05-S02-C02-T06` | 434 | Pressing & finishing | 整烫与后整理 | `pressing_finishing` |

#### D05-S02-C03 Knitting & Leather / 针织与皮革

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S02-C03-T01` | 435 | Flat knitting machine | 横机操作 | `flat_knitting_machine` |
| `D05-S02-C03-T02` | 436 | Linking & looping | 套口与缝合 | `linking_looping` |
| `D05-S02-C03-T03` | 437 | Leather die cutting | 皮革刀模 | `leather_die_cutting` |
| `D05-S02-C03-T04` | 438 | Leather goods stitching | 皮具缝制 | `leather_goods_stitching` |
| `D05-S02-C03-T05` | 439 | Quilting operation | 绗缝 | `quilting_operation` |
| `D05-S02-C03-T06` | 440 | Embroidery machine operation | 绣花机操作 | `embroidery_machine_operation` |

### D05-S03 Home Textiles / 家用纺织品

#### D05-S03-C01 Household Textiles / 家用纺织品

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D05-S03-C01-T01` | 441 | Folding clothes & linens | 床品衣物折叠 | `folding_clothes_linens` |
| `D05-S03-C01-T02` | 442 | Bedding sewing | 床上用品缝制 | `bedding_sewing` |
| `D05-S03-C01-T03` | 443 | Curtain making & install | 窗帘制作与安装 | `curtain_making_install` |
| `D05-S03-C01-T04` | 444 | Sofa cover sewing | 沙发套缝制 | `sofa_cover_sewing` |
| `D05-S03-C01-T05` | 445 | Carpet finishing | 地毯后整理 | `carpet_finishing` |
| `D05-S03-C01-T06` | 446 | Textile tailoring | 纺织品裁剪 | `textile_tailoring` |

## D06 Cooking & Food Service / Cooking & Food Service

### D06-S01 Prep Work / 预处理

#### D06-S01-C01 Produce Prep / 果蔬预处理

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S01-C01-T01` | 447 | Washing vegetables and fruit | 果蔬清洗 | `washing_vegetables_and_fruit` |
| `D06-S01-C01-T02` | 448 | Peeling | 削皮 | `peeling` |
| `D06-S01-C01-T03` | 449 | Cutting & chopping | 切丁 | `cutting_chopping` |
| `D06-S01-C01-T04` | 450 | Sorting produce | 果蔬分拣 | `sorting_produce` |
| `D06-S01-C01-T05` | 451 | Marinating/pickling | 腌制/泡制 | `marinating_pickling` |
| `D06-S01-C01-T06` | 452 | Blanching | 焯水 | `blanching` |

#### D06-S01-C02 Meat & Seafood / 肉类与海鲜

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S01-C02-T01` | 453 | Meat butchering | 肉类分割 | `meat_butchering` |
| `D06-S01-C02-T02` | 454 | Deboning | 剔骨 | `deboning` |
| `D06-S01-C02-T03` | 455 | Slaughtering & dressing seafood | 海鲜宰杀处理 | `slaughtering_dressing_seafood` |
| `D06-S01-C02-T04` | 456 | Scaling & gutting | 去鳞去内脏 | `scaling_gutting` |
| `D06-S01-C02-T05` | 457 | Marinating & coating | 腌制与裹粉 | `marinating_coating` |
| `D06-S01-C02-T06` | 458 | Slicing & shredding | 切片与切丝 | `slicing_shredding` |

#### D06-S01-C03 Staples & Pastry / 主食与点心

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S01-C03-T01` | 459 | Dough mixing & kneading | 和面 | `dough_mixing_kneading` |
| `D06-S01-C03-T02` | 460 | Rolling & filling | 擀皮与包馅 | `rolling_filling` |
| `D06-S01-C03-T03` | 461 | Steaming dim sum | 蒸点心 | `steaming_dim_sum` |
| `D06-S01-C03-T04` | 462 | Dough proofing | 面团发酵 | `dough_proofing` |
| `D06-S01-C03-T05` | 463 | Baking & shaping | 烘焙与成型 | `baking_shaping` |
| `D06-S01-C03-T06` | 464 | Noodle/dumpling boiling | 面条/饺子煮制 | `noodle_dumpling_boiling` |

### D06-S02 Hot Cooking / 热菜烹饪

#### D06-S02-C01 Chinese / 中餐

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S02-C01-T01` | 465 | Wok stir-frying | 爆炒 | `wok_stir-frying` |
| `D06-S02-C01-T02` | 466 | Stewing | 炖煮 | `stewing` |
| `D06-S02-C01-T03` | 467 | Red-braising | 红烧 | `red-braising` |
| `D06-S02-C01-T04` | 468 | Steaming | 清蒸 | `steaming` |
| `D06-S02-C01-T05` | 469 | Deep frying | 油炸 | `deep_frying` |
| `D06-S02-C01-T06` | 470 | Pan frying | 煎制 | `pan_frying` |
| `D06-S02-C01-T07` | 471 | Multi-dish timed cooking | 多菜同步出锅 | `multi-dish_timed_cooking` |

#### D06-S02-C02 Western / 西餐

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S02-C02-T01` | 472 | Steak searing | 牛排煎制 | `steak_searing` |
| `D06-S02-C02-T02` | 473 | Roasting | 烘烤 | `roasting` |
| `D06-S02-C02-T03` | 474 | Baking au gratin | 焗烤 | `baking_au_gratin` |
| `D06-S02-C02-T04` | 475 | Boiling pasta | 煮意面 | `boiling_pasta` |
| `D06-S02-C02-T05` | 476 | Sauce making | 酱汁制作 | `sauce_making` |
| `D06-S02-C02-T06` | 477 | Plating and garnishing | 摆盘与装饰 | `plating_and_garnishing` |

#### D06-S02-C03 Grill & Barbecue / 烧烤

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S02-C03-T01` | 478 | Skewer grilling | 串烤 | `skewer_grilling` |
| `D06-S02-C03-T02` | 479 | Teppanyaki / griddle cooking | 铁板烧 | `teppanyaki_griddle_cooking` |
| `D06-S02-C03-T03` | 480 | Charcoal grilling | 炭火烧烤 | `charcoal_grilling` |
| `D06-S02-C03-T04` | 481 | Pizza baking | 披萨烘烤 | `pizza_baking` |
| `D06-S02-C03-T05` | 482 | Smoking | 烟熏 | `smoking` |
| `D06-S02-C03-T06` | 483 | Open-flame searing | 明火炙烤 | `open-flame_searing` |

### D06-S03 Cold Food & Baking / 冷食与烘焙

#### D06-S03-C01 Baking / 烘焙(食品)

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S03-C01-T01` | 484 | Weighing ingredients | 称量食材 | `weighing_ingredients` |
| `D06-S03-C01-T02` | 485 | Whisking & whipping | 打发 | `whisking_whipping` |
| `D06-S03-C01-T03` | 486 | Dough shaping | 面团成型 | `dough_shaping` |
| `D06-S03-C01-T04` | 487 | Oven baking | 烤箱烘焙 | `oven_baking` |
| `D06-S03-C01-T05` | 488 | Piping & decorating | 裱花装饰 | `piping_decorating` |
| `D06-S03-C01-T06` | 489 | Cake assembly | 蛋糕组装 | `cake_assembly` |

#### D06-S03-C02 Cold Dishes & Drinks / 冷菜与饮品

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S03-C02-T01` | 490 | Cold appetizer plating | 冷盘摆盘 | `cold_appetizer_plating` |
| `D06-S03-C02-T02` | 491 | Salad making | 沙拉制作 | `salad_making` |
| `D06-S03-C02-T03` | 492 | Beverage mixing | 饮调配制 | `beverage_mixing` |
| `D06-S03-C02-T04` | 493 | Coffee brewing | 咖啡冲煮 | `coffee_brewing` |
| `D06-S03-C02-T05` | 494 | Ice/dessert making | 冰品/甜品制作 | `ice_dessert_making` |
| `D06-S03-C02-T06` | 495 | Cocktail bartending | 鸡尾酒调制 | `cocktail_bartending` |

### D06-S04 Restaurant Operations / 餐厅运营

#### D06-S04-C01 Front of House / 前厅

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S04-C01-T01` | 496 | Order taking | 点单 | `order_taking` |
| `D06-S04-C01-T02` | 497 | Food running & serving | 传菜 | `food_running_serving` |
| `D06-S04-C01-T03` | 498 | Table setting | 摆台 | `table_setting` |
| `D06-S04-C01-T04` | 499 | Checkout & payment | 结账收款 | `checkout_payment` |
| `D06-S04-C01-T05` | 500 | Table clearing | 收台 | `table_clearing` |
| `D06-S04-C01-T06` | 501 | Guest reception | 迎宾 | `guest_reception` |

#### D06-S04-C02 Back of House / 后厨

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D06-S04-C02-T01` | 502 | Expediting & plating handoff | 出餐调度 | `expediting_plating_handoff` |
| `D06-S04-C02-T02` | 503 | Dishwashing | 洗碗 | `dishwashing` |
| `D06-S04-C02-T03` | 504 | Kitchen cleaning & sanitation | 厨房清洁与消毒 | `kitchen_cleaning_sanitation` |
| `D06-S04-C02-T04` | 505 | Ingredient stock count | 食材盘点 | `ingredient_stock_count` |
| `D06-S04-C02-T05` | 506 | Cold-chain temperature check | 冷链温度检查 | `cold-chain_temperature_check` |
| `D06-S04-C02-T06` | 507 | Waste sorting | 垃圾分类 | `waste_sorting` |

## D07 Cleaning & Sanitation / Cleaning & Sanitation

### D07-S01 Environmental Cleaning / 环境清洁

#### D07-S01-C01 Indoor Cleaning / 室内清洁

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D07-S01-C01-T01` | 508 | Cleaning & disinfection | 清洁与消毒 | `cleaning_disinfection` |
| `D07-S01-C01-T02` | 509 | Wiping desks & countertops | 桌面台面擦拭 | `wiping_desks_countertops` |
| `D07-S01-C01-T03` | 510 | Vacuuming | 吸尘 | `vacuuming` |
| `D07-S01-C01-T04` | 511 | Mopping floors | 拖地 | `mopping_floors` |
| `D07-S01-C01-T05` | 512 | Glass wiping | 玻璃擦拭 | `glass_wiping` |
| `D07-S01-C01-T06` | 513 | Restroom cleaning | 卫生间清洁 | `restroom_cleaning` |
| `D07-S01-C01-T07` | 514 | Carpet cleaning | 地毯清洁 | `carpet_cleaning` |
| `D07-S01-C01-T08` | 515 | Shelf organizing | 货架整理 | `shelf_organizing` |

#### D07-S01-C02 Exterior & High-Rise / 外墙与高空

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D07-S01-C02-T01` | 516 | High-rise facade cleaning | 高空外墙清洗 | `high-rise_facade_cleaning` |
| `D07-S01-C02-T02` | 517 | Curtain wall cleaning | 幕墙清洗 | `curtain_wall_cleaning` |
| `D07-S01-C02-T03` | 518 | Roof sweeping | 屋面清扫 | `roof_sweeping` |
| `D07-S01-C02-T04` | 519 | Gutter cleaning | 檐沟清理 | `gutter_cleaning` |
| `D07-S01-C02-T05` | 520 | Signage cleaning | 标识清洗 | `signage_cleaning` |
| `D07-S01-C02-T06` | 521 | Stone facade restoration | 石材幕墙翻新 | `stone_facade_restoration` |

#### D07-S01-C03 Industrial Cleaning / 工业清洁

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D07-S01-C03-T01` | 522 | Shop floor cleaning | 车间地面清洁 | `shop_floor_cleaning` |
| `D07-S01-C03-T02` | 523 | Equipment exterior cleaning | 设备外表面清洁 | `equipment_exterior_cleaning` |
| `D07-S01-C03-T03` | 524 | Oil/grease degreasing | 油污脱脂 | `oil_grease_degreasing` |
| `D07-S01-C03-T04` | 525 | Pipe interior cleaning | 管道内清洁 | `pipe_interior_cleaning` |
| `D07-S01-C03-T05` | 526 | Tank cleaning | 罐体清洗 | `tank_cleaning` |
| `D07-S01-C03-T06` | 527 | Cleanroom cleaning | 洁净室清洁 | `cleanroom_cleaning` |

### D07-S02 Waste Handling / 废弃物处理

#### D07-S02-C01 Waste Disposal / 废弃物处置

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D07-S02-C01-T01` | 528 | Waste sorting & collection | 垃圾分类与收集 | `waste_sorting_collection` |
| `D07-S02-C01-T02` | 529 | Garbage hauling | 垃圾清运 | `garbage_hauling` |
| `D07-S02-C01-T03` | 530 | Hazardous waste temporary storage | 危废暂存 | `hazardous_waste_temporary_storage` |
| `D07-S02-C01-T04` | 531 | Recyclables sorting | 可回收物分拣 | `recyclables_sorting` |
| `D07-S02-C01-T05` | 532 | Food waste handling | 餐厨垃圾处理 | `food_waste_handling` |
| `D07-S02-C01-T06` | 533 | Hauling & disinfection | 清运与消毒 | `hauling_disinfection` |

#### D07-S02-C02 Sewer & Drain Maintenance / 下水道与排水维护

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D07-S02-C02-T01` | 534 | Septic tank pumping | 化粪池抽吸 | `septic_tank_pumping` |
| `D07-S02-C02-T02` | 535 | Drain unclogging | 下水道疏通 | `drain_unclogging` |
| `D07-S02-C02-T03` | 536 | Storm drain cleaning | 雨水井清理 | `storm_drain_cleaning` |
| `D07-S02-C02-T04` | 537 | Grease trap cleaning | 隔油池清理 | `grease_trap_cleaning` |
| `D07-S02-C02-T05` | 538 | Sewage treatment operation | 污水处理操作 | `sewage_treatment_operation` |
| `D07-S02-C02-T06` | 539 | High-pressure water jetting | 高压水射流清洗 | `high-pressure_water_jetting` |

## D08 Home & Living / Home & Living

### D08-S01 Household Chores / 家务

#### D08-S01-C01 Laundry / 洗衣

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S01-C01-T01` | 540 | End-to-end laundry | 洗衣全程 | `end-to-end_laundry` |
| `D08-S01-C01-T02` | 541 | Folding clothes | 叠衣 | `folding_clothes` |
| `D08-S01-C01-T03` | 542 | Hand washing | 手洗 | `hand_washing` |
| `D08-S01-C01-T04` | 543 | Hanging & putting away | 晾晒与收纳 | `hanging_putting_away` |
| `D08-S01-C01-T05` | 544 | Ironing | 熨烫 | `ironing` |
| `D08-S01-C01-T06` | 545 | Dry cleaning care | 干洗护理 | `dry_cleaning_care` |

#### D08-S01-C02 Home Organization / 家居整理

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S01-C02-T01` | 546 | Tidying & organizing | 整理与归纳 | `tidying_organizing` |
| `D08-S01-C02-T02` | 547 | Sorting and arranging | 分类与摆放 | `sorting_and_arranging` |
| `D08-S01-C02-T03` | 548 | Bed making | 铺床 | `bed_making` |
| `D08-S01-C02-T04` | 549 | Closet organizing | 衣柜整理 | `closet_organizing` |
| `D08-S01-C02-T05` | 550 | Kitchen organizing | 厨房整理 | `kitchen_organizing` |
| `D08-S01-C02-T06` | 551 | Clutter clearing | 杂物清理 | `clutter_clearing` |

#### D08-S01-C03 Kitchen Chores / 厨房杂务

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S01-C03-T01` | 552 | Dishwashing | 洗碗 | `dishwashing` |
| `D08-S01-C03-T02` | 553 | Loading/unloading dishwasher | 洗碗机装卸 | `loading_unloading_dishwasher` |
| `D08-S01-C03-T03` | 554 | Stove cleaning | 灶台清洁 | `stove_cleaning` |
| `D08-S01-C03-T04` | 555 | Refrigerator organizing | 冰箱整理 | `refrigerator_organizing` |
| `D08-S01-C03-T05` | 556 | Tableware storage | 餐具收纳 | `tableware_storage` |
| `D08-S01-C03-T06` | 557 | Food waste disposal | 厨余处理 | `food_waste_disposal` |

### D08-S02 Furniture Assembly & Care / 家具组装与保养

#### D08-S02-C01 Assembly / 木装配

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S02-C01-T01` | 558 | Assembling simple items | 简单物品组装 | `assembling_simple_items` |
| `D08-S02-C01-T02` | 559 | Assembling consumer furniture (e.g. IKEA) | 宜家类家具组装 | `assembling_consumer_furniture_e_g_ikea` |
| `D08-S02-C01-T03` | 560 | Assembling tables & chairs | 桌椅组装 | `assembling_tables_chairs` |
| `D08-S02-C01-T04` | 561 | Assembling cabinets | 柜子组装 | `assembling_cabinets` |
| `D08-S02-C01-T05` | 562 | Assembling bed frames | 床架组装 | `assembling_bed_frames` |
| `D08-S02-C01-T06` | 563 | Hanging wall fixtures | 壁挂安装 | `hanging_wall_fixtures` |

#### D08-S02-C02 Furniture Care / 家具保养

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S02-C02-T01` | 564 | Furniture waxing & polishing | 家具打蜡抛光 | `furniture_waxing_polishing` |
| `D08-S02-C02-T02` | 565 | Wood furniture repair | 木质家具维修 | `wood_furniture_repair` |
| `D08-S02-C02-T03` | 566 | Leather sofa care | 皮沙发护理 | `leather_sofa_care` |
| `D08-S02-C02-T04` | 567 | Screw tightening & reinforcement | 螺丝紧固加固 | `screw_tightening_reinforcement` |
| `D08-S02-C02-T05` | 568 | Slide rail adjustment | 滑轨调整 | `slide_rail_adjustment` |
| `D08-S02-C02-T06` | 569 | Protective film application | 保护膜粘贴 | `protective_film_application` |

### D08-S03 Gardening & Outdoor / 园艺与户外

#### D08-S03-C01 Gardening / 园艺

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S03-C01-T01` | 570 | Watering and fertilizing | 浇水施肥 | `watering_and_fertilizing` |
| `D08-S03-C01-T02` | 571 | Pruning branches | 修剪枝条 | `pruning_branches` |
| `D08-S03-C01-T03` | 572 | Weeding | 除草 | `weeding` |
| `D08-S03-C01-T04` | 573 | Tilling and sowing | 翻土与播种 | `tilling_and_sowing` |
| `D08-S03-C01-T05` | 574 | Transplanting & repotting | 移栽换盆 | `transplanting_repotting` |
| `D08-S03-C01-T06` | 575 | Pest and disease control | 病虫害防治 | `pest_and_disease_control` |

#### D08-S03-C02 Outdoor Maintenance / 户外维护

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D08-S03-C02-T01` | 576 | Lawn mowing | 草坪修剪 | `lawn_mowing` |
| `D08-S03-C02-T02` | 577 | Yard sweeping | 院子清扫 | `yard_sweeping` |
| `D08-S03-C02-T03` | 578 | Fence repair | 围栏维修 | `fence_repair` |
| `D08-S03-C02-T04` | 579 | Outdoor furniture maintenance | 户外家具维护 | `outdoor_furniture_maintenance` |
| `D08-S03-C02-T05` | 580 | Drainage cleaning | 排水沟清理 | `drainage_cleaning` |
| `D08-S03-C02-T06` | 581 | Snow shoveling | 铲雪 | `snow_shoveling` |

## D09 Retail & Commerce / Retail & Commerce

### D09-S01 Store Operations / 门店运营

#### D09-S01-C01 Checkout / 收银

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D09-S01-C01-T01` | 582 | Cashier task | 收银 | `cashier_task` |
| `D09-S01-C01-T02` | 583 | Barcode scan checkout | 扫码结账 | `barcode_scan_checkout` |
| `D09-S01-C01-T03` | 584 | Returns and exchanges | 退换货 | `returns_and_exchanges` |
| `D09-S01-C01-T04` | 585 | Cash counting | 点钞 | `cash_counting` |
| `D09-S01-C01-T05` | 586 | Membership registration | 会员注册 | `membership_registration` |
| `D09-S01-C01-T06` | 587 | Promotion entry | 促销录入 | `promotion_entry` |

#### D09-S01-C02 Merchandising / 陈列

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D09-S01-C02-T01` | 588 | Bagging items | 装袋 | `bagging_items` |
| `D09-S01-C02-T02` | 589 | Restocking shelves | 补货上架 | `restocking_shelves` |
| `D09-S01-C02-T03` | 590 | Facing and arranging stock | 陈列与整理 | `facing_and_arranging_stock` |
| `D09-S01-C02-T04` | 591 | Pricing & label tagging | 标价与贴标 | `pricing_label_tagging` |
| `D09-S01-C02-T05` | 592 | Inventory counting | 库存盘点 | `inventory_counting` |
| `D09-S01-C02-T06` | 593 | Near-expiry handling | 临期处理 | `near-expiry_handling` |

#### D09-S01-C03 Customer Service / 客户服务

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D09-S01-C03-T01` | 594 | Sales floor greeting | 卖场迎宾 | `sales_floor_greeting` |
| `D09-S01-C03-T02` | 595 | Product introduction | 商品介绍 | `product_introduction` |
| `D09-S01-C03-T03` | 596 | Fitting room assistance | 试衣间协助 | `fitting_room_assistance` |
| `D09-S01-C03-T04` | 597 | Complaint handling | 投诉处理 | `complaint_handling` |
| `D09-S01-C03-T05` | 598 | Queue management | 排队管理 | `queue_management` |
| `D09-S01-C03-T06` | 599 | Gift wrapping | 礼品包装 | `gift_wrapping` |

### D09-S02 Warehouse & Fulfillment / 仓储与履约

#### D09-S02-C01 E-commerce Fulfillment / 电商履约

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D09-S02-C01-T01` | 600 | Picking | 拣货 | `picking` |
| `D09-S02-C01-T02` | 601 | Packing & sealing | 打包封箱 | `packing_sealing` |
| `D09-S02-C01-T03` | 602 | Shipping label affixing | 运单贴标 | `shipping_label_affixing` |
| `D09-S02-C01-T04` | 603 | Weighing & shipping | 称重发货 | `weighing_shipping` |
| `D09-S02-C01-T05` | 604 | Returns putaway | 退货入库 | `returns_putaway` |
| `D09-S02-C01-T06` | 605 | Inventory transfer | 库存调拨 | `inventory_transfer` |

## D10 Healthcare / Healthcare

### D10-S01 Nursing Care / 护理

#### D10-S01-C01 Basic Nursing / 基础护理

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S01-C01-T01` | 606 | Basic nursing tasks | 基础护理 | `basic_nursing_tasks` |
| `D10-S01-C01-T02` | 607 | Vital signs measurement | 生命体征测量 | `vital_signs_measurement` |
| `D10-S01-C01-T03` | 608 | Linen change | 更换床品 | `linen_change` |
| `D10-S01-C01-T04` | 609 | Patient repositioning assistance | 协助翻身 | `patient_repositioning_assistance` |
| `D10-S01-C01-T05` | 610 | Oral care | 口腔护理 | `oral_care` |
| `D10-S01-C01-T06` | 611 | Wound dressing change | 伤口换药 | `wound_dressing_change` |

#### D10-S01-C02 Medication Administration / 给药

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S01-C02-T01` | 612 | Routine medication administration | 常规给药 | `routine_medication_administration` |
| `D10-S01-C02-T02` | 613 | Oral medication dispensing | 口服药发放 | `oral_medication_dispensing` |
| `D10-S01-C02-T03` | 614 | Intramuscular injection | 肌肉注射 | `intramuscular_injection` |
| `D10-S01-C02-T04` | 615 | Subcutaneous injection | 皮下注射 | `subcutaneous_injection` |
| `D10-S01-C02-T05` | 616 | Nebulizer treatment | 雾化治疗 | `nebulizer_treatment` |
| `D10-S01-C02-T06` | 617 | Topical medication application | 外用药涂抹 | `topical_medication_application` |

### D10-S02 Clinical Procedures / 临床操作

#### D10-S02-C01 Phlebotomy & Sampling / 采血与采样

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S02-C01-T01` | 618 | Blood drawing | 抽血 | `blood_drawing` |
| `D10-S02-C01-T02` | 619 | Fingerstick capillary sampling | 指尖采血 | `fingerstick_capillary_sampling` |
| `D10-S02-C01-T03` | 620 | Specimen collection | 标本接入 | `specimen_collection` |
| `D10-S02-C01-T04` | 621 | Specimen transport to lab | 标本送检 | `specimen_transport_to_lab` |
| `D10-S02-C01-T05` | 622 | Blood glucose measurement | 血糖测量 | `blood_glucose_measurement` |
| `D10-S02-C01-T06` | 623 | Urine sample collection | 尿样接入 | `urine_sample_collection` |

#### D10-S02-C02 Diagnostic Procedures / 诊断操作

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S02-C02-T01` | 624 | Diagnosing condition | 病情诊断 | `diagnosing_condition` |
| `D10-S02-C02-T02` | 625 | Auscultation & physical exam | 听诊与查体 | `auscultation_physical_exam` |
| `D10-S02-C02-T03` | 626 | IV infusion | 静脉输液 | `iv_infusion` |
| `D10-S02-C02-T04` | 627 | ECG recording | 心电图接入 | `ecg_recording` |
| `D10-S02-C02-T05` | 628 | Urinary catheterization | 导尿 | `urinary_catheterization` |
| `D10-S02-C02-T06` | 629 | Oxygen administration | 给氧 | `oxygen_administration` |

#### D10-S02-C03 Surgical Procedures / 外科操作

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S02-C03-T01` | 630 | Performing surgery | 外科手术 | `performing_surgery` |
| `D10-S02-C03-T02` | 631 | Surgical instrument handoff | 手术器械传递 | `surgical_instrument_handoff` |
| `D10-S02-C03-T03` | 632 | Wound suturing | 伤口缝合 | `wound_suturing` |
| `D10-S02-C03-T04` | 633 | Sterile draping & prep | 铺巾与准备 | `sterile_draping_prep` |
| `D10-S02-C03-T05` | 634 | Anesthesia administration | 麻醉给药 | `anesthesia_administration` |
| `D10-S02-C03-T06` | 635 | Post-op dressing | 术后包扎 | `post-op_dressing` |

### D10-S03 Rehab & Imaging / 康复与影像

#### D10-S03-C01 Rehabilitation / 康复

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S03-C01-T01` | 636 | Rehab exercise guidance | 康复训练指导 | `rehab_exercise_guidance` |
| `D10-S03-C01-T02` | 637 | Acupuncture & tuina massage | 针灸与推拿 | `acupuncture_tuina_massage` |
| `D10-S03-C01-T03` | 638 | Physiotherapy device operation | 理疗设备操作 | `physiotherapy_device_operation` |
| `D10-S03-C01-T04` | 639 | Traction therapy | 牵引治疗 | `traction_therapy` |
| `D10-S03-C01-T05` | 640 | Movement assessment | 运动评估 | `movement_assessment` |
| `D10-S03-C01-T06` | 641 | Prosthetics/orthotics fitting | 假肢/矫形器适配 | `prosthetics_orthotics_fitting` |

#### D10-S03-C02 Medical Imaging & Exam / 医学影像与检查

| ID | labelId | English | 中文 | slug |
|---|---|---|---|---|
| `D10-S03-C02-T01` | 642 | Ultrasound exam | 超声检查 | `ultrasound_exam` |
| `D10-S03-C02-T02` | 643 | X-ray imaging | X 光成像 | `x-ray_imaging` |
| `D10-S03-C02-T03` | 644 | CT scan operation | CT 操作 | `ct_scan_operation` |
| `D10-S03-C02-T04` | 645 | Dental exam | 口腔检查 | `dental_exam` |
| `D10-S03-C02-T05` | 646 | Vision test / refraction | 视力测试/验光 | `vision_test_refraction` |
| `D10-S03-C02-T06` | 647 | Nasal/throat swab sampling | 鼻咽拭子采样 | `nasal_throat_swab_sampling` |

## 待翻译 task(回退到英文,需补 `EN_TO_ZH` dict)

共 0 个。在 `tools/extract_scenario_taxonomy.py` 顶部的 `EN_TO_ZH` 字典里追加键值对,然后重跑脚本即可。

| ID | English |
|---|---|
