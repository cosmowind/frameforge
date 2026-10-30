// dim-table-crud.js — DIM table CRUD operations
// Extracted from index.html

/* ============================================================ */
/* === DIM TABLE CRUD                                         === */
/* ============================================================ */
const _DIM_FIELDS = {
  recorders: {
    name: { type: 'text', placeholder: '姓名 / 显示标签' },
    // 操作员职业：与上传页面对齐（235 项，可搜索）
    operator_job: { type: 'select', required: true, options: [
      '',
      '收银员',
      '零售店员',
      '快餐员工',
      '服务员',
      '厨师',
      '主厨',
      '咖啡师',
      '调酒师',
      '洗碗工',
      '备菜员',
      '迎宾员',
      '餐厅经理',
      '餐饮服务员',
      '面包师',
      '糕点师',
      '屠夫',
      '食品加工员',
      '配送司机',
      '货车司机',
      '快递员',
      '公交司机',
      '出租车 / 网约车司机',
      '叉车司机',
      '仓库员工',
      '拣货 / 打包员',
      '理货员',
      '发货员',
      '收货员',
      '库存专员',
      '物流协调员',
      '供应链员工',
      '分拣员',
      '邮递员',
      '邮政营业员',
      '搬运工',
      '装卸工',
      '保洁员',
      '清洁工',
      '家政员',
      '酒店客房服务员',
      '洗衣工',
      '干洗工',
      '场地养护员',
      '园林工',
      '园丁',
      '苗圃工',
      '有害生物防治员',
      '维修工',
      '楼宇管理员',
      '设施技术员',
      '水处理操作员',
      '保安',
      '警察',
      '消防员',
      '急救员',
      '急救医士',
      '交通协管员',
      '救生员',
      '注册护士',
      '护理员',
      '居家护理员',
      '生活护理员',
      '护工',
      '医疗助理',
      '医生',
      '医师助理',
      '执业护师',
      '药剂师',
      '药房技术员',
      '牙医',
      '口腔卫生士',
      '牙科助理',
      '理疗师',
      '作业治疗师',
      '呼吸治疗师',
      '放射技师',
      '化验员',
      '兽医技术员',
      '兽医',
      '托育员',
      '幼儿教师',
      '小学教师',
      '初中教师',
      '高中教师',
      '助教',
      '家教',
      '教授',
      '教练',
      '学校辅导员',
      '图书管理员',
      '社工',
      '心理咨询师',
      '行政助理',
      '文员',
      '前台',
      '秘书',
      '行政秘书',
      '数据录入员',
      '记账员',
      '会计',
      '薪资专员',
      '开票员',
      '人力资源专员',
      '招聘专员',
      '客服代表',
      '呼叫中心员工',
      '销售代表',
      '客户经理',
      '房产经纪',
      '保险代理人',
      '银行柜员',
      '信贷员',
      '理财顾问',
      '市场专员',
      '平面设计师',
      '摄影师',
      '摄像师',
      '记者',
      '撰稿 / 编辑',
      '律师',
      '律师助理',
      '法务助理',
      '软件工程师',
      '网页开发工程师',
      '数据分析师',
      '数据科学家',
      'IT 支持专员',
      '系统管理员',
      '网络技术员',
      '网络安全分析师',
      '产品经理',
      '用户体验设计师',
      '测试工程师',
      '电工',
      '水管工',
      '木工',
      '木匠',
      '油漆工',
      '建筑工',
      '屋顶工',
      '石膏板安装工',
      '地板安装工',
      '贴砖工',
      '泥瓦工',
      '混凝土工',
      '重型设备操作员',
      '起重机操作员',
      '工程经理',
      '暖通空调技术员',
      '家电维修技术员',
      '机修工',
      '汽车技师',
      '摩托车维修工',
      '自行车维修工',
      '船舶维修工',
      '柴油机维修工',
      '钣金喷漆技师',
      '轮胎技师',
      '汽车美容师',
      '焊工',
      '金属制作工',
      '机床工',
      '数控操作员',
      '工厂工人',
      '生产工人',
      '机器操作员',
      '装配工',
      '质检员',
      '包装工',
      '半导体技术员',
      '电子技术员',
      '手机维修技术员',
      '电脑维修技术员',
      '现场服务技术员',
      '印刷机操作员',
      '招牌制作工',
      '裁缝',
      '修鞋匠',
      '软包工',
      '皮革工匠',
      '发型师',
      '理发师',
      '美甲师',
      '美容师',
      '按摩师',
      '花艺师',
      '珠宝匠',
      '钟表匠',
      '装裱师',
      '蛋糕裱花师',
      '咖啡烘焙师',
      '陶艺师',
      '蜡烛工匠',
      '健身教练',
      '私人教练',
      '房屋粉刷工',
      '杂工',
      '安装工',
      '太阳能板安装工',
      '风电机组技术员',
      '农民',
      '农场工人',
      '牧场工人',
      '动物饲养员',
      '宠物美容师',
      '渔民',
      '鱼贩',
      '林业工人',
      '伐木工',
      '矿工',
      '油气田工人',
      '实验室研究员',
      '牙科技师',
      '科学家',
      '工程师',
      '建筑师',
      '测量员',
      '飞行员',
      '空乘',
      '机场地勤',
      '旅行社顾问',
      '酒店前台',
      '加油站员工',
      '活动工作人员',
      '赌场员工',
      '殡葬服务员',
      '学校行政人员',
      '供应链协调员',
      '物流经理',
      '维修技术员',
      '仪器维修技术员',
      '造纸厂工人',
      '锁匠',
      '军人',
      '银行职员',
    ] },
    // 操作员同意：与上传页面对齐
    operator_consent: { type: 'select', required: true, options: ['', '是', '否'] },
    age_range: { type: 'select', required: true, options: ['', '15–20', '20–25', '25–30', '30–35', '35–40', '40–45', '45–50', '50–55', '55–60', '60–65', '65–70', '70+'] },
    // 性别：与上传页面对齐
    gender: { type: 'select', required: true, options: ['', '男', '女', '不愿透露'] },
    // 惯用手：与上传页面对齐
    handedness: { type: 'select', required: true, options: ['', '右手', '左手', '双手皆可'] },
    // 手套：与上传页面对齐
    gloves: { type: 'select', required: true, options: ['', '否 —— 徒手', '是 —— 戴手套'] },
    // 劳动力类型：与上传页面对齐
    workforce_type: { type: 'select', required: true, options: ['', '真实员工(本职工作)', '承包者(为接入雇佣)'] },
    role_experience: { type: 'text', placeholder: '岗位经验（如 2 years）' },
    task_experience: { type: 'text', placeholder: '工序经验' },
    recording_hours_today: { type: 'text', placeholder: '当日接入时长(h)' },
    recording_experience_days: { type: 'text', placeholder: '累计接入天数' },
    hand_size_cm: { type: 'text', placeholder: '手尺寸(cm)' },
    notes: { type: 'text', placeholder: '备注（可选）' },
  },
  sd_cards: {
    volume_label:  { type: 'text', placeholder: '卷标' },
    device_id:     { type: 'text', required: true, placeholder: '设备编号（如 DX-0001）' },
    device_name:   { type: 'text', placeholder: '设备名称' },
    // 接入模式：与上传页面对齐，前端只显示中文、保存也存中文
    capture_mode:  { type: 'select', required: true, options: ['', '单目', '双目', '三目'] },
    country_code:  { type: 'text', required: true, placeholder: '国家代码（如 CN）' },
    region:        { type: 'text', required: true, placeholder: '省/州/地区（如 示例省）' },
    city:          { type: 'text', required: true, placeholder: '城市' },
    notes:         { type: 'text', placeholder: '备注' },
  },
  tasks: {
    product:       { type: 'text',   placeholder: '产品' },
    task:          { type: 'text',   placeholder: '任务' },
    tool:          { type: 'text',   placeholder: '工具' },
    process:       { type: 'text',   required: true, placeholder: '工序' },
    process_en:    { type: 'text',   placeholder: '工序（英文·自动翻译）' },
    // 任务难度：与上传页面对齐
    difficulty:    { type: 'select', required: true, options: ['', '简单', '中等', '困难'] },
    business_type: { type: 'select-editable', required: true, placeholder: '业务类型', optionField: 'business_type' },
    business_name: { type: 'select-editable', required: true, placeholder: '业务名称', optionField: 'business_name' },
    notes:         { type: 'text',   placeholder: '备注' },
  },
  environments: {
    scene:         { type: 'select', required: true, optionsFromUpload: 'scenes', searchable: true },
    // 详细地址：默认值与上传页面对齐，使用中文
    location_address: { type: 'text', required: true, placeholder: '示例市示例工业园区' },
    // 环境大类：与上传页面对齐（24 项）
    environment:   { type: 'select', required: true, options: [
      '',
      '零售与消费品',
      '时尚服饰',
      '维修服务',
      '餐饮',
      '建筑与五金',
      '食品加工',
      '印刷与设计',
      '工厂',
      '酒店服务',
      '汽车与运输',
      '运动与休闲',
      '创意工坊',
      '教育与培训',
      '工业制造',
      '能源与公用事业',
      '医疗与药房',
      '清洁与环卫',
      '实验室 / 科研',
      '托育与护理',
      '公共安全与应急',
      '农业与种植',
      '美容与个护',
      '娱乐与活动',
      '其他',
    ] },
    environment_description: { type: 'text', placeholder: '环境描述（照明/场景）', title: '照明 (Lighting): 特指光源的类型、强度和分布。\n场景 (Scene/Setting): 指具体的地点或情境，或者场景职能。' },
    environment_description_en: { type: 'text', placeholder: '环境描述（英文·自动翻译）' },
    // 设施类型：与上传页面对齐（257 项）
    facility_venue: { type: 'select', required: true, options: [
      '',
      '家',
      '包装食品店',
      '餐厅',
      '花店',
      '农场',
      '服装店',
      '礼品店',
      '香水店',
      '面包房',
      '糕点店',
      '杂货店',
      '缝纫厂',
      '洗衣店',
      '修鞋店',
      '木工坊',
      '园艺中心',
      '五金店',
      '渔具店',
      '摩托车修理店',
      '蛋糕店',
      '珠宝手工',
      '图书馆',
      '电子维修',
      '印刷店',
      '咖啡店',
      '酒店',
      '家具店',
      '改衣店',
      '宠物店',
      '履单中心',
      '药房',
      '皮具店',
      '金属加工',
      '摩托车精洗',
      '贴膜店',
      '文具店',
      '蜡烛工作室',
      '家具翻新',
      '美妆用品店',
      '包装厂',
      '玩具店',
      '汽车修理店',
      '家电店',
      '建筑公司',
      '装裱店',
      '清洁用品店',
      '电子产品店',
      '茶叶生产',
      '健身房',
      '手工作坊',
      '酒吧',
      '钟表店',
      '坚果加工厂',
      '咖啡生产',
      '书店',
      '家电维修',
      '水生产',
      '冰淇淋店',
      '汽车精洗',
      '婚纱工作室',
      '手机维修',
      '乐器维修',
      '自行车维修',
      '办公室',
      '制鞋厂',
      '服装印花',
      '地毯店',
      '标牌店',
      '塑料袋厂',
      '电脑维修',
      '回收中心',
      '披萨店',
      '干果厂',
      '外卖店',
      '管道公司',
      '玩具厂',
      '足球场',
      '水疗中心',
      '造纸厂',
      '羽毛球店',
      '物流中心',
      '线缆厂',
      '马赛克工坊',
      '商用厨房',
      '碾米厂',
      '油漆店',
      '民宿',
      '电工',
      '义齿技师',
      '皮带厂',
      '电子厂',
      '诊所',
      '五金厂',
      '拳击馆',
      '烹饪学校',
      '制造厂',
      '纺织软品制造',
      '鱼市',
      '鸡肉店',
      '百货配送',
      '理发店',
      '美甲店',
      '运输',
      '保健品店',
      '陶艺工作室',
      '湿实验室',
      '自行车精洗',
      '机电车间',
      '洗车店',
      '物流履单中心',
      '奶酪厂',
      '塑料厂',
      '柔性电路板制造',
      '枕头厂',
      '果蔬店',
      '塑料橡胶泡沫制品制造',
      '肉铺',
      '锁匠',
      '加油站',
      '船舶维修',
      '装修公司',
      '厨房',
      '个人护理',
      '体育用品店',
      '金属加工车间',
      '篮球场',
      '建筑工地',
      '车库',
      '镶嵌工艺',
      '回收区',
      '回收工作区',
      '阳台',
      '药房实验室',
      '洗衣房',
      '街头摊贩',
      '手工房/工作台',
      '零售店',
      '手工工位',
      '屏幕再造',
      '后院',
      '厨房作坊',
      '食品脱水作坊',
      '其他',
      '办公工作区',
      '回收作坊',
      '鸡蛋加工厂',
      '超市',
      '手工房',
      '家庭洗衣区',
      '杂乱房间',
      '台球',
      '市场',
      '室内杂乱工作区',
      '烘焙店',
      '烘焙厨房',
      '杂乱室内工作区',
      '五金制造',
      '家庭工作区',
      '药房储藏室',
      '清洁服务',
      '图书馆工作区',
      '家庭厨房',
      '机械车间',
      '回收分拣区',
      '垃圾分拣区',
      '药房配药区',
      '餐厅',
      '备餐区',
      '客厅/桌',
      '市场摊位',
      '宠物店',
      '手机配件店',
      '修鞋摊 01',
      '烘焙区',
      '温室',
      '药房配制实验室',
      '苗圃',
      '储藏室',
      '手工工作室',
      '洗衣房 01',
      '图书室',
      '户外维修站',
      '户外垃圾分拣',
      '文具店',
      '浴室',
      '花园清理',
      '家庭包装工位',
      '厨房备菜区',
      '图书馆档案室',
      '图书馆书架',
      '任意房间',
      '家庭作坊',
      '家庭书房',
      '家庭工坊',
      '室内工作区',
      '厨房餐具整理',
      '金属加工车间',
      '户外垃圾分拣区',
      '书店储藏室',
      '化学实验室',
      '椰子加工',
      '书桌/工作台',
      '电子作坊',
      '小吃摊',
      '酒店客房',
      '实验室工作区',
      '洗衣打包工位',
      '洗衣房/卧室',
      '皮具作坊',
      '图书馆储藏',
      '金属五金建材制造',
      '蘑菇农场',
      '药房工作区',
      '餐厅内部',
      '木工作坊',
      '卧室/衣橱/后院',
      '卧室/洗衣房',
      '鸡蛋店',
      '家',
      '厨房烘焙',
      '洗衣区',
      '临时厨房水槽',
      '药房储藏',
      '钟表维修站',
      '便利店',
      '电子维修作坊',
      '小店',
      '台球厅',
      '咖啡吧台',
      '咖啡厨房',
      '化学实验室',
      '便利店储藏',
      '手工房',
      '电子维修台',
      '电子维修站',
      '备餐区',
      '水果店',
      '花园/阳台',
      '花园/阳台/室内',
      '家庭办公室',
      '家庭打包区',
      '家庭书房',
      '室内住宅',
      '室内客厅',
      '室内起居空间',
      '厨房/浴室/走廊',
      '厨房/杂物间',
      '图书馆储藏室',
      '药房配制工位',
      '药房柜台',
      '药房实验室',
      '药房配药室',
      '手机维修店',
      '回收场',
      '电动车维修店',
      '小型零售店',
      '桌子',
    ] },
    notes:         { type: 'text',   placeholder: '备注' },
  }
};

// UI-only 字段屏蔽：schema / CSV 保持原样（保留历史 env 数据），但这些列不在 task 表单里渲染。
// 迁移记录: 2db9001 已把 scene/env 从 task_id 公式、生成向导、说明文案里清理，但底层 schema 没改。
const _DIM_UI_HIDDEN = {
  tasks: ['scene', 'location_address', 'environment',
          'environment_description', 'environment_description_en', 'facility_venue', 'quota_min'],
};

// 操作列一键复制：每个 dim 配置要复制的字段（不挂 inline cell，避免和 input/翻译按钮事件冲突）
const _DIM_COPY_OPS = {
  recorders:   { field: 'id',                          label: '录入员 id' },
  tasks:        { field: 'process_en',                  label: '工序英文' },
  environments: { field: 'environment_description_en',  label: '环境描述英文' },
};

function _uiFields(name) {
  const hidden = _DIM_UI_HIDDEN[name] || [];
  const schema = (dimPageState[name] && dimPageState[name].schema) || [];
  return schema.filter(f => !hidden.includes(f));
}

async function dimReload(name) {
  const st = dimPageState[name];
  const hasNew = st.newKeys && st.newKeys.size > 0;
  const hasDirty = st.dirty && st.dirty.size > 0;
  if (hasNew || hasDirty) {
    const which = [];
    if (hasNew) which.push('新增行（未保存）');
    if (hasDirty) which.push('已修改行（未保存）');
    if (!confirm('有未保存的改动：\n' + which.join('和') + '\n\n重载会丢失这些改动。\n\n确定要重载吗？')) return;
  }
  const status = document.getElementById('dimStatus' + _cap(name));
  if (status) status.textContent = '加载中…';
  try {
    const r = await fetch('/api/dim/' + name);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    dimCache[name] = data.rows || [];
    dimPageState[name].schema = data.schema || [];
    dimPageState[name].rows = (data.rows || []).map(r => ({ ...r }));
    dimPageState[name].dirty = new Set();
    dimPageState[name].newKeys = new Set();
    // 自动排序：tasks 页面加载后按 产品→任务→工具 排序
    if (name === 'tasks' && _tasksAutoSort) {
      _applyTasksSort();
      _persistTasksOrder();
    }
    dimRenderTable(name);
    let msg = `已加载 ${data.count} 行`;
    if (data.migrated && data.migrated.length) {
      msg += ` · 自动收录 ${data.migrated.length} 项（录入员列）`;
    }
    if (status) status.textContent = msg;
    _updateDimSaveCount(name);
  } catch (e) {
    if (status) status.textContent = '加载失败: ' + e.message;
  }
}

// Dim page element-id convention: "sd_cards" → "SdCards" (camelCase, not naive _cap)
const DIM_ID_CAP = {
  recorders:   "Recorders",
  sd_cards:     "SdCards",
  tasks:        "Tasks",
  environments: "Environments",
};
function _cap(name) {
  if (DIM_ID_CAP[name]) return DIM_ID_CAP[name];
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function dimRenderTable(name) {
  const st = dimPageState[name];
  const headEl = document.getElementById('dimHead' + _cap(name));
  const bodyEl = document.getElementById('dimBody' + _cap(name));
  const key = st.schema[0]; // 主键（永远保留显示，不用 _uiFields 屏蔽）
  const uiFields = _uiFields(name);          // 含主键，过滤掉 UI 隐藏列
  const fields = _DIM_FIELDS[name] || {};

  // 表头
  let head = '<th style="min-width:60px;">#</th>';
  head += `<th style="min-width:80px;">${key}</th>`;
  uiFields.slice(1).forEach(fn => {
    const ph = fields[fn] && fields[fn].placeholder ? fields[fn].placeholder : fn;
    const star = (fields[fn] && fields[fn].required) ? '<span style="color:#cf1322;" title="提交视频必填">*</span>' : '';
    const extraStyle = (fn === 'process') ? ' style="min-width:360px;"' : '';
    const thTitle = (fields[fn] && fields[fn].title) ? fields[fn].title : fn;
    head += `<th title="${thTitle}"${extraStyle}>${star} ${ph}</th>`;
  });
  if (name === 'tasks') {
    head += '<th>校验</th>';
  }
  head += '<th style="min-width:140px;">操作</th>';
  headEl.innerHTML = head;

  // 表体
  let body = '';
  const search = (st.filter || '').toLowerCase();
  st.rows.forEach((row, idx) => {
    // 过滤
    if (search) {
      const hay = Object.values(row).join(' ').toLowerCase();
      if (!hay.includes(search)) return;
    }
    // 新行判断：newKeys 存的是 _tmpKey（如 __new_12345__），不是主键值
    const isNew = !!(row._tmpKey && st.newKeys.has(row._tmpKey));
    const isDirty = st.dirty.has(row._tmpKey) || st.dirty.has(row[key]);
    const rowKey = isNew && row._tmpKey ? row._tmpKey : row[key];
    st.newKeys.add(rowKey);  // 兜底：保证 isNew 状态可识别
    body += `<tr data-key="${esc(rowKey)}" class="${isNew ? 'dim-new' : ''} ${isDirty ? 'dirty' : ''}">`;
    // 行级校验指示（每行开头）：✅ 有效 / ❌ 无效 + tooltip 说明
    if (name === 'tasks') {
      const v = _taskValidateRow(row);
      const icon = v.ok ? '✅' : '❌';
      const cls = v.ok ? 'ok' : 'err';
      body += `<td><span class="task-row-status ${cls}" title="${esc(v.reason || '5 元组有效')}" data-row-valid="${v.ok ? '1' : '0'}">${icon}</span></td>`;
    } else {
      body += `<td style="color:#aaa;">${idx + 1}</td>`;
    }
    body += `<td>`;
    {
      // 主键列也可能要挂 📋（比如 recorders.id 是主键，COPY_FIELDS 目标）
      const pkCopy = _DIM_COPY_OPS[name];
      if (pkCopy && key === pkCopy.field) {
        body += `<span style="display:inline-flex;align-items:center;gap:3px;width:100%;">
          <input type="text" data-field="${key}" value="${esc(row[key])}" ${(isNew && name !== 'tasks') ? '' : (name === 'tasks' ? 'readonly style="background:#fafafa;color:#555;"' : '')} oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)" style="flex:1;min-width:0;">
          <button type="button" class="btn btn-outline btn-small" style="background:#f6ffed;border-color:#b7eb8f;color:#389e0d;padding:2px 8px;line-height:1.2;flex-shrink:0;" title="把${pkCopy.label}一键复制到上传助手" onclick="dimCopyFieldToClipboard('${name}', '${esc(rowKey)}', '${pkCopy.field}', this)">📋</button>
        </span>`;
      } else {
        body += `<input type="text" data-field="${key}" value="${esc(row[key])}" ${(isNew && name !== 'tasks') ? '' : (name === 'tasks' ? 'readonly style="background:#fafafa;color:#555;"' : '')} oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)">`;
      }
    }
    body += `</td>`;
    uiFields.slice(1).forEach(fn => {
      const spec = fields[fn] || { type: 'text' };
      let cell;
      if (spec.type === 'select' && spec.optionsFromUpload && spec.searchable) {
        // 可搜索下拉（如 scene）：前端只显示中文，保存也存中文，对齐提交页面前端选项
        const uploadKey = spec.optionsFromUpload;
        const uploadOptsList = (uploadOpts && uploadOpts[uploadKey]) ? uploadOpts[uploadKey] : [];
        const curVal = row[fn] || '';
        let curDisplay = curVal;
        if (curVal) {
          // 先在 taxonomy scenes 中按 value 找
          const found = uploadOptsList.find(o => o.value === curVal);
          if (found) {
            curDisplay = found.label || found.value;
          } else {
            // 在 live sceneNames 中按 value/labelZh 找（兼容中文/英文旧值）
            const liveList = (uploadOpts && uploadOpts.sceneNames) ? uploadOpts.sceneNames : [];
            const liveFound = liveList.find(s => s.value === curVal || s.labelZh === curVal);
            if (liveFound) {
              curDisplay = liveFound.labelZh || liveFound.label || liveFound.value;
            } else {
              curDisplay = curVal;
            }
          }
        }
        console.log('[scene render]', { fn, curVal, curDisplay, uploadOptsListLen: uploadOptsList.length });
        const safeKey = (rowKey || ('idx' + idx)).replace(/[^a-zA-Z0-9一-鿿]/g, '_');
        const uid = 'ss-' + name + '-' + safeKey;
        // 注册选项到全局；v（真实值）和 d（显示文本）都使用中文
        if (!window._ssOpts) window._ssOpts = {};
        window._ssOpts[uid] = uploadOptsList.map(o => ({
          v: o.label || o.value,
          d: o.label || o.value
        }));
        // 合并 live 抓取的 sceneNames（809 个），只显示中文、保存中文
        if (fn === 'scene' && uploadOpts && uploadOpts.sceneNames && uploadOpts.sceneNames.length) {
          const existingDisplays = new Set(uploadOptsList.map(o => o.label || o.value));
          const extra = uploadOpts.sceneNames
            .filter(s => {
              const zh = s.labelZh || s.value;
              return !existingDisplays.has(zh);
            })
            .map(s => {
              const zh = s.labelZh || s.value;
              return { v: zh, d: zh };
            });
          if (extra.length) {
            window._ssOpts[uid] = [...window._ssOpts[uid], ...extra].sort((a, b) => a.d.localeCompare(b.d, 'zh'));
          }
        }
        cell = `<span class="searchable-sel" style="position:relative;display:inline-block;width:100%;">
          <input class="searchable-sel-input" id="${uid}_inp" type="text" value="${esc(curDisplay)}"
            onfocus="ssOpen('${uid}')" oninput="ssFilter('${uid}')"
            onkeydown="ssKeyNav(event,'${uid}')"
            onblur="setTimeout(() => dimRowBlur('${name}', document.getElementById('${uid}_val')), 150)"
            placeholder="搜索场景…" autocomplete="off" style="width:100%;box-sizing:border-box;">
          <input type="hidden" data-field="${fn}" class="searchable-sel-val" id="${uid}_val" value="${esc(curVal)}">
          <div class="searchable-sel-drop" id="${uid}_drop" style="display:none;position:fixed;z-index:2147483647;background:#fff;border:1px solid #d9d9d9;border-radius:4px;max-height:240px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,0.18);font-size:13px;"></div>
        </span>`;
      } else if (spec.type === 'select') {
        // 任务页 difficulty 改值时触发 dimOnDifficultyChange
        const onchangeHandlers = [`dimRowInput('${name}', this)`];
        if (name === 'tasks' && fn === 'difficulty') {
          onchangeHandlers.push('dimOnDifficultyChange(this)');
        }
        cell = `<select data-field="${fn}" onchange="${onchangeHandlers.join('; ')}" onblur="dimRowBlur('${name}', this)">` +
          spec.options.map(o => {
            if (o && typeof o === 'object') {
              return `<option value="${esc(o.value)}" ${row[fn]===o.value?'selected':''}>${esc(o.label)}</option>`;
            }
            return `<option value="${esc(o)}" ${row[fn]===o?'selected':''}>${esc(o||'--')}</option>`;
          }).join('') +
          '</select>';
      } else if (spec.type === 'number') {
        cell = `<input type="number" data-field="${fn}" value="${esc(row[fn])}" oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)">`;
      } else if (spec.type === 'select-editable') {
        const optField = spec.optionField || fn;
        const opts = getEditableOptions(optField);
        const cur = row[fn] || '';
        const editBtn = `<button class="btn btn-outline btn-tiny" title="编辑选项" onclick="event.stopPropagation(); openEditOptionsModal('${name}', '${optField}')" style="margin-left:2px;padding:0 4px;font-size:10px;">✎</button>`;
        cell = `<span style="display:inline-flex;align-items:center;gap:2px;">
          <select data-field="${fn}" onchange="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)" style="flex:1;">
            <option value="">--</option>` +
          opts.map(o => `<option value="${esc(o.value)}" ${cur===o.value?'selected':''}>${esc(o.label||o.value)}</option>`).join('') +
          (cur && !opts.some(o => o.value === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)}</option>` : '') +
          `</select>${editBtn}</span>`;
      } else if (name === 'tasks' && fn === 'process_en') {
        cell = `<span style="display:inline-flex;align-items:center;gap:3px;width:100%;">
          <button class="btn btn-outline btn-tiny" title="重新翻译" onclick="event.stopPropagation(); translateSingleProcess(this)" style="padding:0 4px;font-size:13px;flex-shrink:0;line-height:1;">🔄</button>
          <input type="text" data-field="${fn}" value="${esc(row[fn])}" oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)" style="flex:1;min-width:0;">
          <button type="button" class="btn btn-outline btn-small" style="background:#f6ffed;border-color:#b7eb8f;color:#389e0d;padding:2px 8px;line-height:1.2;flex-shrink:0;" title="复制工序英文到剪贴板" onclick="dimCopyFieldToClipboard('${name}', '${esc(rowKey)}', '${fn}', this)">📋</button>
        </span>`;
      } else if (name === 'environments' && fn === 'environment_description_en') {
        cell = `<span style="display:inline-flex;align-items:center;gap:3px;width:100%;">
          <button class="btn btn-outline btn-tiny" title="重新翻译" onclick="event.stopPropagation(); translateSingleEnvDescription(this)" style="padding:0 4px;font-size:13px;flex-shrink:0;line-height:1;">🔄</button>
          <input type="text" data-field="${fn}" value="${esc(row[fn])}" oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)" style="flex:1;min-width:0;">
          <button type="button" class="btn btn-outline btn-small" style="background:#f6ffed;border-color:#b7eb8f;color:#389e0d;padding:2px 8px;line-height:1.2;flex-shrink:0;" title="复制环境描述英文到剪贴板" onclick="dimCopyFieldToClipboard('${name}', '${esc(rowKey)}', '${fn}', this)">📋</button>
        </span>`;
      } else {
        const inputExtraStyle = (name === 'tasks' && fn === 'process') ? ' style="min-width:360px;width:100%;"' : '';
        cell = `<input type="text" data-field="${fn}" value="${esc(row[fn])}" oninput="dimRowInput('${name}', this)" onblur="dimRowBlur('${name}', this)"${inputExtraStyle}>`;
      }
      body += `<td>${cell}</td>`;
    });
    if (name === 'tasks') {
      // 行级缺字段提示：4 元组必填，difficulty 可选
      const v = _taskValidateRow(row);
      const filledCount = ['product','task','tool','process'].filter(f => (row[f]||'').trim()).length;
      const missingHint = filledCount < 4
        ? `<span class="task-row-hint" style="color:#cf1322;font-size:11px;">⚠ 还差 ${4 - filledCount} / 4 字段</span>`
        : `<span class="task-row-hint" style="color:#389e0d;font-size:11px;">✓ 4/4</span>`;
      body += `<td>${missingHint}</td>`;
    }
    body += `<td class="dim-actions">
      <button class="btn btn-success btn-small" onclick="dimSaveOne('${name}', '${esc(rowKey)}')">保存</button>
      <button class="btn btn-danger btn-small" onclick="dimDeleteRow('${name}', '${esc(rowKey)}')">删</button>${name === 'tasks' ? `<button class="btn btn-outline btn-small" title="复制并清空task_id/产品/任务/工具/工序" onclick="dimCopyRow('${name}', '${esc(rowKey)}')">拷贝</button>` : ''}
    </td>`;
    body += '</tr>';
  });
  bodyEl.innerHTML = body || '<tr><td colspan="99" style="text-align:center;color:#888;padding:20px;">（空）</td></tr>';
}

function dimFilterRows(name) {
  const el = document.getElementById('dimSearch' + _cap(name));
  dimPageState[name].filter = el ? el.value : '';
  dimRenderTable(name);
  _updateDimSaveCount(name);
}

function dimRowInput(name, input) {
  const tr = input.closest('tr');
  if (!tr) { console.warn('[dimRowInput] no tr.parent for input', input); return; }
  const key = tr.dataset.key || tr.getAttribute('data-key') || '';
  const field = input.dataset.field;
  // searchable-sel 组件：真实值存在同名的 hidden.searchable-sel-val 里，不能取可见 input 的 value（那是显示文本）
  const hiddenVal = input.classList.contains('searchable-sel-input')
    ? (tr.querySelector('input.searchable-sel-val[data-field="' + field + '"]') || {}).value
    : undefined;
  const value = hiddenVal !== undefined ? hiddenVal : input.value;
  const st = dimPageState[name];
  if (!st) { console.warn('[dimRowInput] no dimPageState for', name); return; }
  const primary = st.schema[0];
  console.log('[dimRowInput]', { name, key, field, value, rowKey: key });
  let target = st.rows.find(r => (r[primary] || '') === key);
  if (!target) target = st.rows.find(r => r._tmpKey === key);
  if (!target) target = st.rows.find(r => !(r[primary] || ''));
  if (target) {
    const oldPrimary = target[primary];
    target[field] = value;
    const newPrimary = field === primary ? value : target[primary];
    // 主键改名：第一次改后记录 originalKey（=最初保存到服务器的主键值），之后
    // 后续的连续修改（一次输入 l → "" → o → op → op02 多次改名）都以这个 originalKey
    // 为锚，dimSaveOne 用它作为 ?original_key= 参数，从而服务端能正确 rename。
    if (field === primary && newPrimary !== oldPrimary) {
      if (!tr.dataset.originalKey) {
        tr.dataset.originalKey = oldPrimary || key;
      }
      const newKey = newPrimary;
      if (st.dirty.has(key)) { st.dirty.delete(key); st.dirty.add(newKey); }
      if (st.newKeys.has(key)) { st.newKeys.delete(key); st.newKeys.add(newKey); }
      tr.setAttribute('data-key', newKey);
      tr.dataset.key = newKey;
    }

    if (name === 'tasks') _taskRefreshRowHint(tr, target);
  } else {
    console.error('[dimRowInput] NO TARGET FOUND!', { key, primary, rows: st.rows.length, sampleKeys: st.rows.map(r => r[primary] || r._tmpKey) });
  }
  st.dirty.add(tr.dataset.key);
  tr.classList.add('dirty');
  _updateDimSaveCount(name);
}

// 任务页：局部刷新该行的「校验」状态图标 + 「缺字段提示」
function _taskRefreshRowHint(tr, row) {
  if (!tr) return;
  const v = _taskValidateRow(row);
  // 1) 第一个 td 里的 .task-row-status
  const statusSpan = tr.querySelector('td .task-row-status');
  if (statusSpan) {
    statusSpan.textContent = v.ok ? '✅' : '❌';
    statusSpan.className = 'task-row-status ' + (v.ok ? 'ok' : 'err');
    statusSpan.title = v.reason || '5 元组有效';
    statusSpan.setAttribute('data-row-valid', v.ok ? '1' : '0');
  }
  // 2) 「缺字段提示」cell（table 内第 4 列：idx, status, key, primary, 校验, scene, ... — 校验列）
  //    我们根据现有结构找：找第一个 .task-row-hint
  const hintSpan = tr.querySelector('.task-row-hint');
  if (hintSpan) {
    if (v.ok) {
      hintSpan.textContent = '✓ 4/4';
      hintSpan.style.color = '#389e0d';
      hintSpan.title = '';
    } else {
      const missing = ['product','task','tool','process'].filter(f => !(row[f]||'').trim()).length;
      hintSpan.textContent = `⚠ 还差 ${missing} / 4 字段`;
      hintSpan.style.color = '#cf1322';
      hintSpan.title = v.reason || '';
    }
  }
}

function dimOnDifficultyChange(sel) {
  // 任务页 difficulty 改值时：已由 _DIM_FIELDS 的 onChange handler 处理 dimRowInput
  // （配额相关逻辑已移除）
}

/* dimRowBlur — 输入框/下拉框失去焦点时自动保存当前行（400ms 防抖） */
const _dimBlurTimers = {};

function dimRowBlur(name, input) {
  const tr = input.closest('tr');
  if (!tr) return;
  const st = dimPageState[name];
  if (!st || !st.dirty) return;
  const rowKey = tr.dataset.key || tr.getAttribute('data-key') || '';
  if (!rowKey) return;
  // 只保存确实被标记为 dirty 的行
  if (!st.dirty.has(rowKey)) return;
  if (!_dimBlurTimers[name]) _dimBlurTimers[name] = {};
  if (_dimBlurTimers[name][rowKey]) clearTimeout(_dimBlurTimers[name][rowKey]);
  _dimBlurTimers[name][rowKey] = setTimeout(() => {
    delete _dimBlurTimers[name][rowKey];
    dimSaveOne(name, rowKey);
  }, 400);
}