# 扫描功能完善更新日志

## 日期：2026-06-21

## 更新内容

### 1. 新增 Data 目录扫描支持

**功能说明**：
- 支持从 SD 卡 `data/` 目录扫描 session 文件夹
- 自动读取 `session.json` 获取设备信息（兼容 `metadata.json`）
- 目标路径：`/media/inbox\data\<device_id>_session_xxxxx/`

**配置变更**：
- `config.json` 新增 `deviceMonitor.dataPatterns` 配置项（默认 `["data"]`）
- `device_monitor.py` 的 `DEFAULT_CONFIG` 新增 `data_patterns` 配置

**新增方法**：
- `find_data_sources(drive)`：扫描 SD 卡上的 data 目录
- `copy_data_sessions(data_sources, dest_dir, drive)`：复制 data session 到目标目录
- `register_data_to_csv(dest_dir, copied_sessions)`：注册 data session 到 CSV

### 2. 设备前缀自动添加

**功能说明**：
- HMD 和 Data session 自动添加 6 位设备ID前缀
- 避免不同设备的 session 编号冲突
- 支持从 `metadata.json` 或 `session.json` 读取设备ID
- 后备方案：使用 SD 卡卷序列号作为设备标识
- **🆕 日期前缀（2026-06-25）**：0623 及以后的视频额外添加 MMDD 日期前缀

**修改方法**：
- `_rename_session_with_device_prefix(session_name, device_id_short, dest_path)`：改进设备前缀添加逻辑，新增 `dest_path` 参数用于日期前缀判断
- `find_hmd_sources(drive)`：添加卷序列号作为后备设备ID
- `find_data_sources(drive)`：添加卷序列号作为后备设备ID

**命名规则**（2026-06-25 更新）：
- 0623 之前：`<device_id_short>_<session>`（如 `f83c30_session_00007`）
- 0623 及以后：`<MMDD>_<device_id_short>_<session>`（如 `0625_f83c30_session_00007`）

### 3. 配置加载增强

**修改内容**：
- `_load_scan_directory()` 方法新增对 `dataPatterns` 配置的加载
- 支持从 `config.json` 动态配置 HMD 和 Data 的目录名模式

### 4. 目录整合功能

**新增脚本**：
- `fix_data_sessions.py`：修复 data session 的设备前缀
- `fix_hmd_sessions.py`：修复 HMD session 的设备前缀
- `merge_hmd_directories.py`：整合 `hmd` 和 `hmd1` 目录
- `cleanup_duplicate_sessions.py`：清理重复 session

**使用场景**：
- 旧版本复制的 session 没有设备前缀，可以用这些脚本批量修复
- 支持检测和删除不完整的 session（缺少 part 文件）

## 测试验证

### 测试环境
- SD 卡：`E:\data\session_00000\`（包含 `session.json`）
- 目标目录：`/media\0621\data\`

### 测试结果
✅ **Data 目录扫描**：成功识别 `session.json` 中的设备ID（`a1b2c3d4e5f60001`）
✅ **设备前缀添加**：session 文件夹正确重命名为 `sample_session_00000`
✅ **目录整合**：成功将 `hmd1` 目录下的 session 移动到 `hmd` 目录
✅ **重复清理**：成功检测并删除 3 个重复的 session，保留 2 个不完整的 session 供手动检查

## 兼容性说明

### 向后兼容
- 旧版本复制的 MP4 文件不受影响
- 旧版本复制的 HMD session（无设备前缀）可以通过修复脚本批量添加前缀
- `config.json` 新增配置项有默认值，不会影响现有配置

### 文件类型支持
- **MP4**：单目设备视频（DJI/GoPro 等）
- **HMD**：双目设备 session（包含 `metadata.json` + `part_*.hmd`）
- **Data**：数据设备 session（包含 `session.json` + 视频文件）

## 文档更新

### 已更新文档
1. **README.md**：
   - 更新 "USB 设备自动监听" 部分，添加对 HMD 和 Data 目录扫描的说明
   - 更新 "配置 `config.json` 关键项" 部分，添加 `hmdPatterns` 和 `dataPatterns` 说明

2. **DEVELOPER_GUIDE.md**：
   - 更新 "设备监控 `device_monitor.py`" 部分，添加新增方法的说明
   - 添加 "新增功能（2026-06-21）" 章节，详细记录本次更新

## 后续建议

### 功能增强
1. 支持更多设备配置文件格式（如 `config.json`、`info.json` 等）
2. 添加 session 完整性自动检测（检查 part 文件是否连续）
3. 支持自动合并同一设备的多个 session（按时间顺序）

### 文档完善
1. 添加 Data 目录扫描的流程图
2. 添加设备前缀命名规则的示例说明
3. 更新 FAQ，添加 "如何修复旧 session 的设备前缀" 章节

### 测试覆盖
1. 为 `find_data_sources()` 添加单元测试
2. 为 `copy_data_sessions()` 添加集成测试
3. 测试不同 SD 卡文件系统（FAT32/exFAT/NTFS）的兼容性
