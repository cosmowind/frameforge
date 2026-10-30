# 上传必填参数字段分布表

> 更新时间：2026-06-27
> 总计 20+ 个必填上传参数，分布到录入员、SD卡/设备、任务、环境 四个维表。
> 视频管理页只保留对维表的引用 ID（`recorder_id`, `device_id`, `task_id`, `env_id`），
> 上传时自动从关联维表记录中填充所有字段。

---

## 一、录入员维表（recorders.csv）

路径：`recorders.csv` | 主键：`id`

该表描述接入操作员本人信息，上传时映射到 `Operator` 相关字段。

| # | 字段名 | 中文说明 | 上传表单映射 | 提交必填 | 数据类型 | 备注 |
|---|--------|---------|------------|:---:|---------|------|
| 1 | `id` (主键) | 录入员ID | `operator_name` | ✅ | text | 英文/数字/下划线 |
| 2 | `name` | 录入员姓名 | — | — | text | 显示用，不用于上传 |
| 3 | `operator_job` | 岗位 | `operator_job` | ✅ | select | 235 个标准岗位（Jobs Taxonomy） |
| 4 | `operator_consent` | 知情同意 | `operator_consent` | ✅ | select | Yes / No |
| 5 | `age_range` | 年龄段 | `age_range` | ✅ | select | 13 档：15–20 到 70+ |
| 6 | `gender` | 性别 | `gender` | ✅ | select | Male / Female / Prefer not to say |
| 7 | `handedness` | 惯用手 | `handedness` | ✅ | select | Right-handed / Left-handed / Ambidextrous |
| 8 | `gloves` | 手套 | `gloves` | ✅ | select | No — bare hands / Yes — wearing gloves |
| 9 | `workforce_type` | 劳动力类型 | `workforce_type` | ✅ | select | Real worker / Contractor |
| 10 | `role_experience` | 岗位经验 | `role_experience` | 推荐 | text | 推荐填写 |
| 11 | `task_experience` | 工序经验 | `task_experience` | 推荐 | text | 推荐填写 |
| 12 | `recording_hours_today` | 当日接入时长 | `recording_hours_today` | 推荐 | text | 推荐填写 |
| 13 | `recording_experience_days` | 累计接入天数 | `recording_experience_days` | 推荐 | text | 推荐填写 |
| 14 | `hand_size_cm` | 手尺寸(cm) | `hand_size_cm` | 推荐 | text | 推荐填写 |
| 15 | `notes` | 备注 | — | — | text | 可选 |

---

## 二、SD卡/设备维表（sd_cards.csv）

路径：`sd_cards.csv` | 主键：`volume_serial`

每张 SD 卡/设备绑定一组固定的地理位置信息。  
一个设备 → 一个接入地点 → 一次配置，对应视频可重复使用。

| # | 字段名 | 中文说明 | 上传表单映射 | 提交必填 | 数据类型 | 备注 |
|---|--------|---------|------------|:---:|---------|------|
| 1 | `volume_serial` (主键) | 卷序列号/设备ID | — | — | text | 自动识别/手动填写 |
| 2 | `volume_label` | 卷标 | — | — | text | 可选 |
| 3 | `device_id` | 设备编号 | — | — | text | 兼容旧有 |
| 4 | `device_name` | 设备名称 | — | — | text | |
| 5 | `capture_mode` | 接入模式 | `captureMode` | 推荐 | select | single / stereo / three_views |
| 6 | `country_code` | 国家/地区 | `country` | ✅ | select | ISO 3166-1 alpha-2（有内置默认 China） |
| 7 | `region` | 州/省/地区 | `state_province` | ✅ | select/text | 结构化列表或自由文本（有内置默认 FuJian） |
| 8 | `city` | 城市 | `city` | ✅ | text | 有内置默认 QuanZhou |
| 9 | `stable_site_identifier` | 固定场地标识 | `stable_site_identifier` | 推荐 | text | |
| 10 | `notes` | 备注 | — | — | text | 可选 |

---

## 三、任务维表（tasks.csv）

路径：`tasks.csv` | 主键：`task_id`

任务描述与工序信息。`business_type`、`business_name` 为前端可编辑下拉选项。

| # | 字段名 | 中文说明 | 上传表单映射 | 提交必填 | 数据类型 | 备注 |
|---|--------|---------|------------|:---:|---------|------|
| 1 | `task_id` (主键) | 任务ID | — | — | text | 格式 `[a-z]+_[a-z]+_[a-z]+_\d{3}` |
| 2 | `product` | 产品 | — | — | text | |
| 3 | `task` | 任务 | — | — | text | |
| 4 | `tool` | 工具 | — | — | text | |
| 5 | `process` | 工序 | `task_description` | ✅ | text | |
| 6 | `process_en` | 工序(英文) | — | — | text | 自动翻译 |
| 7 | `difficulty` | 难度 | `task_difficulty` | ✅ | select | Easy / Medium / Hard |
| 8 | `business_type` | 业务类型 | `business_type` | ✅ | select-editable | 用户可编辑下拉选项 |
| 9 | `business_name` | 业务名称 | `business_name` | ✅ | select-editable | 用户可编辑下拉选项 |
| 10 | `notes` | 备注 | — | — | text | |

> 注：`scene`, `location_address`, `environment`, `environment_description`, `facility_venue` 等环境字段已迁移至 environments.csv。

---

## 三（新）、环境维表（environments.csv）

路径：`environments.csv` | 主键：`env_id`

环境/场景描述信息，2026-06-26 从 tasks.csv 拆分而来。

| # | 字段名 | 中文说明 | 上传表单映射 | 提交必填 | 数据类型 | 备注 |
|---|--------|---------|------------|:---:|---------|------|
| 1 | `env_id` (主键) | 环境ID | — | — | text | 格式 `env_<md5[:10]>`，自动生成 |
| 2 | `scene` | 场景 | `scene` | ✅ | select-editable | 选项来自 scene-categories + 用户自定义 |
| 3 | `location_address` | 详细地址 | `location_address` | ✅ | text | |
| 4 | `environment` | 环境类别 | `environment` | ✅ | select | 27 个标准环境类别 |
| 5 | `environment_description` | 环境描述 | `environment_description` | ✅ | text | 中文环境描述 |
| 6 | `environment_description_en` | 环境描述(英文) | `environment_description` | ✅ | text | 英文，自动翻译 |
| 7 | `facility_venue` | 设施场所 | `facility_venue` | ✅ | select | 43 个标准场所类别 |
| 8 | `notes` | 备注 | — | — | text | 可选 |

---

## 四、视频管理表（videos / video_manager.csv）

保留字段（移除上传相关字段后）：

| # | 字段名 | 说明 | 备注 |
|---|--------|-----|------|
| 1 | `path` | 视频路径 | 主键 |
| 2 | `recorder_id` → recorders.csv | 录入员引用 | FK |
| 3 | `device_id` → sd_cards.csv | 设备引用 | FK |
| 4 | `task_id` → tasks.csv | 任务引用 | FK |
| 5 | `env_id` → environments.csv | 环境引用 | FK |
| ... | (其余原有字段不变) | | |

---

## 五、上传时自动填充逻辑

`auto_upload.py` → `_build_template_from_row()` 填充优先级：

1. **内置默认值**（最低优先级）
2. **config.json `uploadTemplate`** 用户自定义默认值
3. **recorders.csv**：由 `recorder_id` 匹配 → 填充 `operator_name`, `operator_job`, `operator_consent`, `age_range`, `gender`, `handedness`, `gloves`, `workforce_type`, `role_experience`, `task_experience`, `recording_hours_today`, `recording_experience_days`, `hand_size_cm`
4. **sd_cards.csv**：由 `device_id`（匹配 `volume_serial`） → 填充 `captureMode`, `country`, `state_province`, `city`, `stable_site_identifier`
5. **tasks.csv**：由 `task_id` 匹配 → 填充 `task_difficulty`, `task_description`(=process), `business_type`, `business_name`
6. **environments.csv**：由 `env_id` 匹配 → 填充 `environment_description`, `scene`, `location_address`, `environment`, `facility_venue`
7. **videos CSV 行**（最高优先级）：`work_content_en` → 覆盖 `task_description`
