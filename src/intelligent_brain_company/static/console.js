const state = {
  projects: [],
  activeProject: null,
  chatHistoryByProject: {},
  activeLanguage: 'zh-CN',
  employeeRosterByProjectAgent: {},
  replayPlayer: {
    steps: [],
    currentIndex: -1,
    timer: null,
    speed: 1,
  },
}

const DEPARTMENT_AGENTS = new Set(['hardware', 'software', 'design', 'marketing', 'finance'])

const LANGUAGE_SEQUENCE = ['zh-CN', 'en-US']

const I18N = {
  'zh-CN': {
    languageToggle: '语言: 中文',
    languageSwitching: '正在切换语言...',
    languageSaved: '语言已切换，后续新生成对话将使用中文。',
    languageError: '语言切换失败',
    chatReady: '聊天内容可以提升为正式干预，再用“执行下一环节”逐步重算。',
    interventionSaved: '干预已记录。请点击“执行下一环节”逐步重算。',
    chatSending: '正在发送消息...',
    chatReceived: '已收到回复，可直接提升为正式干预。',
    chatPromoting: '正在转为正式干预...',
    promoteButton: '转成正式干预',
    promotedNoRegenerate: '已转为正式干预。请点击“执行下一环节”逐步重算。',
    employeePickerButton: '选择员工 @',
    exportReplayButton: '导出回放 Demo',
    employeePickerNotDepartment: '当前角色不是部门角色，无可选员工。',
    employeePickerEmpty: '当前部门暂无可选员工。',
    employeeMentionHint: '点击后将插入 @员工 进行定向提问。',
    sourceStageReview: '阶段评审输出',
    sourceEmployeeStatement: '员工发言',
    sourceSuggestedStage: '建议阶段',
    impactSuggested: '建议影响',
    impactSource: '来源',
    emptyCurrentStage: '当前环节下还没有可展示的记录。',
    emptyAll: '当前角色还没有对话记录。',
    replayExporting: '正在导出回放 Demo...',
    replayExported: '回放 Demo 已下载。',
    replayExportFailed: '导出回放 Demo 失败',
    replayImportButton: '导入回放 Demo',
    replayPlayButton: '自动播放',
    replayPauseButton: '暂停',
    replayResetButton: '重播',
    replayEmpty: '未导入回放数据。',
    replayLoaded: '已载入 {count} 条回放步骤，开始自动播放。',
    replayPlaying: '正在播放第 {current}/{total} 步...',
    replayPaused: '回放已暂停。',
    replayCompleted: '回放已完成。',
    replayImportFailed: '导入回放 Demo 失败',
    generatedFromTurn: '已根据 {turnId} 生成新版本。',
    agentNames: {
      research: '研究组',
      board: '董事会',
      hardware: '硬件组',
      software: '软件组',
      design: '设计组',
      marketing: '营销组',
      finance: '财务组',
    },
    userName: '你',
    stageReplayName: '阶段评审回放',
    employeeFallback: '员工',
  },
  'en-US': {
    languageToggle: 'Language: English',
    languageSwitching: 'Switching language...',
    languageSaved: 'Language switched. New generated turns will use English.',
    languageError: 'Language switch failed',
    chatReady: 'Chat replies can be promoted to interventions, then regenerate step by step via Run Next Stage.',
    interventionSaved: 'Intervention recorded. Use Run Next Stage for step-by-step regeneration.',
    chatSending: 'Sending message...',
    chatReceived: 'Reply received. You can promote it to an intervention directly.',
    chatPromoting: 'Promoting chat turn to intervention...',
    promoteButton: 'Promote to intervention',
    promotedNoRegenerate: 'Promoted to intervention. Use "Run Next Stage" to regenerate step by step.',
    employeePickerButton: 'Pick Employee @',
    exportReplayButton: 'Export Replay Demo',
    employeePickerNotDepartment: 'Current role is not a department role.',
    employeePickerEmpty: 'No employees available for this department.',
    employeeMentionHint: 'Click one to insert @mention for directed questions.',
    sourceStageReview: 'Stage review output',
    sourceEmployeeStatement: 'Employee statement',
    sourceSuggestedStage: 'Suggested stage',
    impactSuggested: 'Suggested impact',
    impactSource: 'Source',
    emptyCurrentStage: 'No records available for the current stage yet.',
    emptyAll: 'No dialogue history for this role yet.',
    replayExporting: 'Exporting replay demo...',
    replayExported: 'Replay demo downloaded.',
    replayExportFailed: 'Failed to export replay demo',
    replayImportButton: 'Import Replay Demo',
    replayPlayButton: 'Autoplay',
    replayPauseButton: 'Pause',
    replayResetButton: 'Replay',
    replayEmpty: 'No replay data imported yet.',
    replayLoaded: 'Loaded {count} replay steps. Autoplay started.',
    replayPlaying: 'Playing step {current}/{total}...',
    replayPaused: 'Replay paused.',
    replayCompleted: 'Replay completed.',
    replayImportFailed: 'Failed to import replay demo',
    generatedFromTurn: 'Generated a new version from {turnId}.',
    agentNames: {
      research: 'Research Team',
      board: 'Board',
      hardware: 'Hardware Team',
      software: 'Software Team',
      design: 'Design Team',
      marketing: 'Marketing Team',
      finance: 'Finance Team',
    },
    userName: 'You',
    stageReplayName: 'Stage Replay',
    employeeFallback: 'Employee',
  },
}

const STAGE_NAMES = {
  'zh-CN': {
    intake: 'Intake 需求录入',
    research: '研究评估',
    department_design: '部门方案',
    roundtable: '跨部门圆桌',
    synthesis: '综合决策',
    board: '董事会评审',
  },
  'en-US': {
    intake: 'Intake',
    research: 'Research',
    department_design: 'Department Design',
    roundtable: 'Roundtable',
    synthesis: 'Synthesis',
    board: 'Board',
  },
}

const STAGE_STATUS_NAMES = {
  'zh-CN': { completed: '已完成', current: '进行中', pending: '待开始' },
  'en-US': { completed: 'Completed', current: 'Current', pending: 'Pending' },
}

const PROJECT_STATUS_NAMES = {
  'zh-CN': { created: '已创建', planning: '规划中', reviewing: '评审中', completed: '已完成', failed: '失败' },
  'en-US': { created: 'Created', planning: 'Planning', reviewing: 'Reviewing', completed: 'Completed', failed: 'Failed' },
}

const NEXT_STAGE_ACTION_I18N = {
  'zh-CN': {
    intake: '执行研究阶段',
    research: '执行部门评审',
    department_design: '执行跨部门评审',
    roundtable: '执行方案综合',
    synthesis: '执行董事会评审',
    board: '已完成全部环节',
  },
  'en-US': {
    intake: 'Run Research',
    research: 'Run Department Review',
    department_design: 'Run Roundtable Review',
    roundtable: 'Run Synthesis',
    synthesis: 'Run Board Review',
    board: 'All Stages Completed',
  },
}

const EMPLOYEE_NAME_ZH = {
  'Maya Chen': '陈思雨', 'David Okoro': '李承泽', 'Amara Osei': '王安雅', 'Luca Neri': '赵景行',
  'Noah Bennett': '周彦霖', 'Sofia Martins': '林若彤', 'Priya Raman': '许嘉宁', 'Ethan Cole': '孙启航',
  'Iris Novak': '吴清妍', 'Kenji Watanabe': '郭明远', 'Marta Silva': '何诗妍', 'Felix Park': '郑亦辰',
  'Elena Rossi': '沈知夏', 'Haruto Sato': '叶子昂', 'Amina Farouk': '唐语薇', 'Jonas Weber': '顾闻舟',
  'Camila Duarte': '宋可欣', 'Leah Kim': '韩以宁', 'Mateo Alvarez': '陆泽宇', 'Rina Takahashi': '高若琳',
  'Oliver Grant': '梁书豪', 'Nadia Ibrahim': '冯雨桐', 'Grace Liu': '许知微', 'Tomas Novak': '曹景川',
  'Yuna Choi': '崔安然', 'Marco Bellini': '彭远航',
}

const TITLE_ZH = {
  'Trend Research Lead': '趋势研究负责人', 'Feedback Synthesis Manager': '反馈综合经理', 'Reality Validation Specialist': '现实验证专员',
  'Executive Insight Writer': '高层洞察撰写人', 'Embedded Systems Engineer': '嵌入式系统工程师', 'Rapid Prototype Lead': '快速原型负责人',
  'Reliability Operations Engineer': '可靠性运维工程师', 'Hardware QA Certifier': '硬件质量认证工程师', 'Backend Architecture Lead': '后端架构负责人',
  'Applied AI Engineer': '应用 AI 工程师', 'DevOps Automation Engineer': 'DevOps 自动化工程师', 'API Quality Specialist': 'API 质量专家',
  'UX Architecture Director': '用户体验架构总监', 'UI Design Lead': '界面设计负责人', 'UX Research Specialist': '用户体验研究专员',
  'Brand Guardian': '品牌守护者', 'Experience Delight Designer': '体验惊喜设计师', 'Growth Strategy Lead': '增长策略负责人',
  'Content Program Manager': '内容项目经理', 'Social Strategy Specialist': '社媒策略专家', 'Market Pulse Analyst': '市场脉搏分析师',
  'App Growth Optimization Manager': '应用增长优化经理', 'Finance Tracking Lead': '财务跟踪负责人', 'Business Intelligence Analyst': '商业智能分析师',
  'Compliance and Risk Counsel': '合规与风险顾问', 'Strategic Reporting Manager': '战略报告经理',
}

const EMPLOYEE_NAME_EN = Object.fromEntries(Object.entries(EMPLOYEE_NAME_ZH).map(([en, zh]) => [zh, en]))
const TITLE_EN = Object.fromEntries(Object.entries(TITLE_ZH).map(([en, zh]) => [zh, en]))

function stageLabel(stage) {
  return STAGE_NAMES[normalizeLanguage(state.activeLanguage)]?.[stage] || stage
}

function stageStatusLabel(status) {
  return STAGE_STATUS_NAMES[normalizeLanguage(state.activeLanguage)]?.[status] || status
}

function projectStatusLabel(status) {
  return PROJECT_STATUS_NAMES[normalizeLanguage(state.activeLanguage)]?.[status] || status
}

function localizeEmployeeName(name) {
  const text = String(name || '')
  if (normalizeLanguage(state.activeLanguage) === 'zh-CN') {
    return EMPLOYEE_NAME_ZH[text] || text
  }
  return EMPLOYEE_NAME_EN[text] || text
}

function localizeEmployeeTitle(title) {
  const text = String(title || '')
  if (normalizeLanguage(state.activeLanguage) === 'zh-CN') {
    return TITLE_ZH[text] || text
  }
  return TITLE_EN[text] || text
}

function employeeRole(name, title) {
  const localizedName = localizeEmployeeName(name)
  if (!title) return localizedName
  const localizedTitle = localizeEmployeeTitle(title)
  return normalizeLanguage(state.activeLanguage) === 'zh-CN'
    ? `${localizedName}（${localizedTitle}）`
    : `${localizedName} (${localizedTitle})`
}

function normalizeLanguage(language) {
  return LANGUAGE_SEQUENCE.includes(language) ? language : 'zh-CN'
}

function locale() {
  return I18N[normalizeLanguage(state.activeLanguage)]
}

function t(key, vars = {}) {
  const value = locale()[key] || I18N['zh-CN'][key] || key
  return Object.entries(vars).reduce((acc, [name, replacement]) => {
    return acc.replaceAll(`{${name}}`, String(replacement))
  }, value)
}

function getCachedChatHistory(projectId, agent) {
  return state.chatHistoryByProject[projectId]?.[agent] || []
}

function getCachedEmployeeRoster(projectId, agent) {
  return state.employeeRosterByProjectAgent[projectId]?.[agent] || []
}

function setCachedChatHistory(projectId, agent, history) {
  if (!state.chatHistoryByProject[projectId]) {
    state.chatHistoryByProject[projectId] = {}
  }
  state.chatHistoryByProject[projectId][agent] = history
}

function setCachedEmployeeRoster(projectId, agent, employees) {
  if (!state.employeeRosterByProjectAgent[projectId]) {
    state.employeeRosterByProjectAgent[projectId] = {}
  }
  state.employeeRosterByProjectAgent[projectId][agent] = employees
}

function isDepartmentAgent(agent) {
  return DEPARTMENT_AGENTS.has(String(agent || ''))
}

const projectList = document.getElementById('project-list')
const demoProjectList = document.getElementById('demo-project-list')
const projectName = document.getElementById('project-name')
const projectMeta = document.getElementById('project-meta')
const verdictBadge = document.getElementById('verdict-badge')
const verdictSummary = document.getElementById('verdict-summary')
const scoreGrid = document.getElementById('score-grid')
const planMarkdown = document.getElementById('plan-markdown')
const stageProgress = document.getElementById('stage-progress')
const timeline = document.getElementById('timeline')
const diffFrom = document.getElementById('diff-from')
const diffTo = document.getElementById('diff-to')
const diffOutput = document.getElementById('diff-output')
const chatAgentSelect = document.getElementById('chat-agent')
const chatHistoryScopeSelect = document.getElementById('chat-history-scope')
const chatHistory = document.getElementById('chat-history')
const chatStatus = document.getElementById('chat-status')
const sendChatButton = document.getElementById('send-chat')
const languageToggleButton = document.getElementById('language-toggle')
const refreshChatButton = document.getElementById('refresh-chat')
const exportReplayDemoButton = document.getElementById('export-replay-demo')
const importReplayDemoButton = document.getElementById('import-replay-demo')
const replayFileInput = document.getElementById('replay-file')
const replayPlayButton = document.getElementById('replay-play')
const replayPauseButton = document.getElementById('replay-pause')
const replayResetButton = document.getElementById('replay-reset')
const replaySpeedSelect = document.getElementById('replay-speed')
const replayStatus = document.getElementById('replay-status')
const replayHistory = document.getElementById('replay-history')
const employeePickerToggleButton = document.getElementById('employee-picker-toggle')
const employeePickerPanel = document.getElementById('employee-picker-panel')
const generatePlanButton = document.getElementById('generate-plan')
const submitInterventionButton = document.getElementById('submit-intervention')
const loadDiffButton = document.getElementById('load-diff')
const interventionStageSelect = document.querySelector('#intervention-form select[name="stage"]')

const NEXT_STAGE_ACTION = {
  intake: '执行研究阶段',
  research: '执行部门评审',
  department_design: '执行跨部门评审',
  roundtable: '执行方案综合',
  synthesis: '执行董事会评审',
  board: '已完成全部环节',
}

const AGENT_PROFILES = {
  research: { avatar: '研', hue: 198 },
  board: { avatar: '董', hue: 16 },
  hardware: { avatar: '硬', hue: 32 },
  software: { avatar: '软', hue: 220 },
  design: { avatar: '设', hue: 284 },
  marketing: { avatar: '营', hue: 138 },
  finance: { avatar: '财', hue: 50 },
}

function userProfile() {
  return { name: t('userName'), avatar: '你', hue: 188 }
}

function stageReplayProfile() {
  return { name: t('stageReplayName'), avatar: '回', hue: 270 }
}

function profileByAgent(agent) {
  const profile = AGENT_PROFILES[agent]
  if (!profile) {
    return { name: agent, avatar: String(agent || '?').slice(0, 1), hue: 210 }
  }
  return {
    ...profile,
    name: locale().agentNames[agent] || agent,
  }
}

function profileByTurn(agent, turn) {
  if (turn.source === 'stage_review') {
    return stageReplayProfile()
  }
  if (turn.source === 'chat' && turn.speaker && turn.speaker !== agent) {
    const speaker = employeeRole(turn.speaker, turn.speaker_title)
    return { name: speaker, avatar: speaker.slice(0, 1), hue: 126 }
  }
  if (turn.source === 'employee_statement') {
    const speaker = employeeRole(turn.speaker || t('employeeFallback'), turn.speaker_title)
    return { name: speaker, avatar: speaker.slice(0, 1), hue: 94 }
  }
  return profileByAgent(agent)
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatChatBody(text) {
  return escapeHtml(text).replace(/\n/g, '<br>')
}

function avatarStyle(profile) {
  return `--avatar-hue: ${profile.hue};`
}

function updateGenerateButton(project) {
  const action = NEXT_STAGE_ACTION_I18N[normalizeLanguage(state.activeLanguage)]?.[project.current_stage]
    || NEXT_STAGE_ACTION_I18N['zh-CN'][project.current_stage]
    || '执行下一环节'
  generatePlanButton.textContent = action
  generatePlanButton.disabled = project.current_stage === 'board'
}

function renderLanguageButton() {
  languageToggleButton.textContent = t('languageToggle')
}

function applyLanguageToChatUi() {
  renderLanguageButton()
  applyLanguageToStageSelector()
  if (employeePickerToggleButton) {
    employeePickerToggleButton.textContent = t('employeePickerButton')
  }
  if (exportReplayDemoButton) {
    exportReplayDemoButton.textContent = t('exportReplayButton')
  }
  if (importReplayDemoButton) {
    importReplayDemoButton.textContent = t('replayImportButton')
  }
  if (replayPlayButton) {
    replayPlayButton.textContent = t('replayPlayButton')
  }
  if (replayPauseButton) {
    replayPauseButton.textContent = t('replayPauseButton')
  }
  if (replayResetButton) {
    replayResetButton.textContent = t('replayResetButton')
  }
  renderEmployeePicker(chatAgentSelect.value)
  if (!state.activeProject) {
    chatStatus.textContent = t('chatReady')
    return
  }
  const agent = chatAgentSelect.value
  const history = getCachedChatHistory(state.activeProject.project_id, agent)
  if (history.length) {
    renderChat(agent, history)
  } else {
    chatStatus.textContent = t('chatReady')
  }
}

function applyLanguageToStageSelector() {
  if (!interventionStageSelect) return
  Array.from(interventionStageSelect.options).forEach((option) => {
    option.textContent = stageLabel(option.value)
  })
}

function insertEmployeeMention(mentionKey) {
  const input = document.getElementById('chat-message')
  const original = input.value
  const spacer = original && !original.endsWith(' ') ? ' ' : ''
  input.value = `${original}${spacer}@${mentionKey} `
  input.focus()
}

function renderEmployeePicker(agent) {
  if (!employeePickerPanel || !employeePickerToggleButton) return
  employeePickerToggleButton.textContent = t('employeePickerButton')
  if (!state.activeProject) {
    employeePickerToggleButton.disabled = true
    employeePickerPanel.classList.add('hidden')
    employeePickerPanel.innerHTML = ''
    return
  }
  if (!isDepartmentAgent(agent)) {
    employeePickerToggleButton.disabled = true
    employeePickerPanel.innerHTML = `<div class="employee-item-meta" style="padding:10px 12px;">${escapeHtml(t('employeePickerNotDepartment'))}</div>`
    return
  }
  employeePickerToggleButton.disabled = false
  const employees = getCachedEmployeeRoster(state.activeProject.project_id, agent)
  if (!employees.length) {
    employeePickerPanel.innerHTML = `<div class="employee-item-meta" style="padding:10px 12px;">${escapeHtml(t('employeePickerEmpty'))}</div>`
    return
  }
  employeePickerPanel.innerHTML = employees.map((employee) => {
    const name = employeeRole(employee.name, employee.title)
    return `
      <button type="button" class="employee-item" data-mention="${escapeHtml(employee.mention_key)}">
        <div class="employee-item-name">${escapeHtml(name)}</div>
        <div class="employee-item-meta">@${escapeHtml(employee.mention_key)} · ${escapeHtml(t('employeeMentionHint'))}</div>
      </button>
    `
  }).join('')
}

async function loadEmployeeRoster(projectId, agent) {
  if (!projectId) return
  if (!isDepartmentAgent(agent)) {
    setCachedEmployeeRoster(projectId, agent, [])
    renderEmployeePicker(agent)
    return
  }
  const data = await api(`/api/projects/${projectId}/chat/employees?agent=${encodeURIComponent(agent)}`)
  setCachedEmployeeRoster(projectId, agent, data.employees || [])
  renderEmployeePicker(agent)
}

function resetProjectView() {
  state.activeProject = null
  projectName.textContent = '未选择项目'
  projectMeta.textContent = '请先创建项目或选择已有项目。'
  planMarkdown.textContent = '尚未生成计划。'
  renderScorecard(null)
  stageProgress.innerHTML = ''
  timeline.innerHTML = ''
  diffFrom.innerHTML = ''
  diffTo.innerHTML = ''
  diffOutput.textContent = '至少需要两个版本。'
  chatHistory.innerHTML = ''
  chatStatus.textContent = t('chatReady')
  generatePlanButton.textContent = '执行下一环节'
  generatePlanButton.disabled = true
  submitInterventionButton.disabled = true
  sendChatButton.disabled = true
  languageToggleButton.disabled = true
  employeePickerToggleButton.disabled = true
  exportReplayDemoButton.disabled = true
  employeePickerPanel.classList.add('hidden')
  employeePickerPanel.innerHTML = ''
  refreshChatButton.disabled = true
  loadDiffButton.disabled = true
}

function replayStepProfile(step) {
  const speaker = String(step.speaker || '')
  if (step.kind === 'user_message') {
    return { row: 'outgoing', name: t('userName'), avatar: '你', hue: 188 }
  }
  if (speaker === 'stage_replay' || step.kind === 'stage_output') {
    return { row: 'incoming', name: t('stageReplayName'), avatar: '回', hue: 270 }
  }
  if (step.kind === 'employee_statement') {
    const display = employeeRole(step.speaker || t('employeeFallback'), step.speaker_title)
    return { row: 'incoming', name: display, avatar: display.slice(0, 1), hue: 94 }
  }
  if (step.agent && AGENT_PROFILES[step.agent]) {
    const profile = profileByAgent(step.agent)
    return { row: 'incoming', name: profile.name, avatar: profile.avatar, hue: profile.hue }
  }
  return { row: 'incoming', name: speaker || 'Agent', avatar: (speaker || 'A').slice(0, 1), hue: 210 }
}

function renderReplayPlayer() {
  const steps = state.replayPlayer.steps
  const currentIndex = state.replayPlayer.currentIndex
  replayHistory.innerHTML = ''
  if (!steps.length) {
    replayStatus.textContent = t('replayEmpty')
    return
  }

  const visible = steps.slice(0, Math.max(0, currentIndex + 1))
  visible.forEach((step) => {
    const profile = replayStepProfile(step)
    const content = formatChatBody(step.content || '')
    const row = document.createElement('div')
    row.className = `chat-row ${profile.row}`
    if (profile.row === 'outgoing') {
      row.innerHTML = `
        <div class="chat-bubble user">
          <div class="chat-bubble-head">
            <span class="chat-role">${escapeHtml(profile.name)}</span>
            <span class="chat-time">${new Date(step.timestamp).toLocaleString()}</span>
          </div>
          <div class="chat-message">${content}</div>
        </div>
        <div class="chat-avatar" style="${avatarStyle(profile)}">${escapeHtml(profile.avatar)}</div>
      `
    } else {
      row.innerHTML = `
        <div class="chat-avatar" style="${avatarStyle(profile)}">${escapeHtml(profile.avatar)}</div>
        <div class="chat-bubble agent">
          <div class="chat-bubble-head">
            <span class="chat-role">${escapeHtml(profile.name)}</span>
            <span class="chat-time">${new Date(step.timestamp).toLocaleString()}</span>
          </div>
          <div class="chat-message">${content}</div>
          <div class="chat-meta">${escapeHtml(step.kind || 'step')} · ${escapeHtml(step.stage || '')}</div>
        </div>
      `
    }
    replayHistory.appendChild(row)
  })

  replayHistory.scrollTop = replayHistory.scrollHeight
  const current = Math.min(currentIndex + 1, steps.length)
  if (current >= steps.length) {
    replayStatus.textContent = t('replayCompleted')
  } else {
    replayStatus.textContent = t('replayPlaying', { current, total: steps.length })
  }
}

function stopReplayAutoplay() {
  if (state.replayPlayer.timer) {
    window.clearInterval(state.replayPlayer.timer)
    state.replayPlayer.timer = null
  }
}

function replayStepForward() {
  const steps = state.replayPlayer.steps
  if (!steps.length) return
  if (state.replayPlayer.currentIndex >= steps.length - 1) {
    stopReplayAutoplay()
    renderReplayPlayer()
    return
  }
  state.replayPlayer.currentIndex += 1
  renderReplayPlayer()
}

function startReplayAutoplay() {
  const steps = state.replayPlayer.steps
  if (!steps.length) return
  stopReplayAutoplay()
  const interval = Math.max(300, Math.floor(1200 / (state.replayPlayer.speed || 1)))
  state.replayPlayer.timer = window.setInterval(replayStepForward, interval)
}

function updateReplayControlState() {
  const loaded = state.replayPlayer.steps.length > 0
  replayPlayButton.disabled = !loaded
  replayPauseButton.disabled = !loaded
  replayResetButton.disabled = !loaded
}

async function importReplayFromFile(file) {
  if (!file) return
  try {
    const content = await file.text()
    const data = JSON.parse(content)
    const steps = Array.isArray(data.steps) ? data.steps : []
    state.replayPlayer.steps = steps
    state.replayPlayer.currentIndex = -1
    stopReplayAutoplay()
    updateReplayControlState()
    replayStatus.textContent = t('replayLoaded', { count: steps.length })
    renderReplayPlayer()
    startReplayAutoplay()
  } catch (error) {
    replayStatus.textContent = `${t('replayImportFailed')}: ${error.message}`
  }
}

const DEMO_PROJECTS = [
  {
    title: 'AI 面试训练教练',
    summary: '面向应届生和转岗求职者的 AI 模拟面试产品。',
    constraints: ['首月上线 MVP', '优先验证付费意愿', '先做中文场景'],
    metrics: ['7 天留存', '付费转化率', '模拟面试完成率'],
  },
  {
    title: '跨境电商选品助手',
    summary: '帮助中小卖家快速评估选品机会、供货风险和渠道策略。',
    constraints: ['先服务亚马逊卖家', '强调低调研成本', '输出可执行选品建议'],
    metrics: ['周活卖家数', '候选商品转化率', '选品报告复用率'],
  },
  {
    title: '校园二手交易平台',
    summary: '围绕高校宿舍场景做高频低客单的可信二手流转。',
    constraints: ['低预算冷启动', '先跑单校模型', '优先供需匹配效率'],
    metrics: ['首周成交数', '发布到成交时长', '校园渗透率'],
  },
]

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const payload = await response.json()
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || 'Request failed')
  }
  return payload.data
}

function showProject(project) {
  state.activeProject = project
  state.activeLanguage = normalizeLanguage(project.conversation_language)
  renderLanguageButton()
  const recommendation = project.latest_plan?.scorecard?.recommendation
  projectName.textContent = project.name
  const statusText = projectStatusLabel(project.status)
  const stageText = stageLabel(project.current_stage)
  projectMeta.textContent = recommendation
    ? `${statusText} · ${stageText} · ${project.plans.length} 个版本 · 结论 ${recommendation}`
    : `${statusText} · ${stageText} · ${project.plans.length} 个版本`
  planMarkdown.textContent = project.latest_plan_markdown || '尚未生成计划。'
  renderScorecard(project.latest_plan?.scorecard || null)
  updateGenerateButton(project)
  submitInterventionButton.disabled = false
  sendChatButton.disabled = false
  languageToggleButton.disabled = false
  employeePickerToggleButton.disabled = !isDepartmentAgent(chatAgentSelect.value)
  exportReplayDemoButton.disabled = false
  refreshChatButton.disabled = false
  renderProjects()
  loadProgress(project.project_id)
  loadTimeline(project.project_id)
  renderDiffSelectors(project.plans)
  loadChat(project.project_id, chatAgentSelect.value)
}

function renderDemoProjects() {
  demoProjectList.innerHTML = ''
  DEMO_PROJECTS.forEach((preset) => {
    const button = document.createElement('button')
    button.className = 'demo-card'
    button.innerHTML = `
      <div class="demo-card-title">${preset.title}</div>
      <div class="demo-card-summary">${preset.summary}</div>
      <div class="demo-card-meta">约束: ${preset.constraints.join(' / ')}</div>
    `
    button.addEventListener('click', async () => {
      projectMeta.textContent = `正在加载 Demo：${preset.title}`
      try {
        const project = await createProject(preset, true)
        showProject(project)
        await loadProjects()
      } catch (error) {
        projectMeta.textContent = error.message
      }
    })
    demoProjectList.appendChild(button)
  })
}

function renderScorecard(scorecard) {
  scoreGrid.innerHTML = ''
  if (!scorecard) {
    verdictBadge.textContent = '等待生成'
    verdictBadge.className = 'verdict-badge idle'
    verdictSummary.textContent = '生成计划后，这里会显示一个更像创业评审会的综合判断。'
    return
  }

  verdictBadge.textContent = scorecard.recommendation
  verdictBadge.className = `verdict-badge ${scorecard.recommendation.toLowerCase().replace(/[^a-z]/g, '-')}`
  verdictSummary.textContent = scorecard.summary

  const items = [
    ['市场需求', scorecard.market_demand, '目标客户是否足够明确、足够痛。'],
    ['技术可行性', scorecard.technical_feasibility, '现有能力与实现路径是否顺滑。'],
    ['执行复杂度', scorecard.execution_complexity, '越低越容易推进。'],
    ['MVP 时效', scorecard.time_to_mvp, '越高代表越适合快速启动。'],
    ['商业化潜力', scorecard.monetization_potential, '是否具备清晰的变现抓手。'],
  ]

  items.forEach(([label, score, note]) => {
    const item = document.createElement('div')
    item.className = 'score-card'
    item.innerHTML = `
      <div class="score-label">${label}</div>
      <div class="score-value">${score}<span>/10</span></div>
      <div class="score-note">${note}</div>
    `
    scoreGrid.appendChild(item)
  })
}

function renderProjects() {
  projectList.innerHTML = ''
  state.projects.forEach((project) => {
    const row = document.createElement('div')
    row.className = 'project-card-row'

    const openButton = document.createElement('button')
    openButton.className = `project-card ${state.activeProject?.project_id === project.project_id ? 'active' : ''}`
    openButton.type = 'button'
    openButton.innerHTML = `
      <div class="project-card-title">${project.name}</div>
      <div class="project-card-meta">${projectStatusLabel(project.status)} · ${project.plans.length} ${normalizeLanguage(state.activeLanguage) === 'zh-CN' ? '个版本' : 'versions'}</div>
    `
    openButton.addEventListener('click', async () => {
      const fresh = await api(`/api/projects/${project.project_id}`)
      showProject(fresh)
    })

    const deleteButton = document.createElement('button')
    deleteButton.className = 'project-delete-button'
    deleteButton.type = 'button'
    deleteButton.textContent = '删除'
    deleteButton.addEventListener('click', async () => {
      const confirmed = window.confirm(`确认删除项目“${project.name}”吗？此操作不可恢复。`)
      if (!confirmed) return
      await deleteProject(project.project_id)
    })

    row.appendChild(openButton)
    row.appendChild(deleteButton)
    projectList.appendChild(row)
  })
}

function renderProgress(stages) {
  stageProgress.innerHTML = ''
  stages.forEach((stage) => {
    const item = document.createElement('div')
    item.className = 'stage-item'
    item.innerHTML = `
      <div>${stageLabel(stage.stage)}</div>
      <span class="stage-badge ${stage.status}">${stageStatusLabel(stage.status)}</span>
    `
    stageProgress.appendChild(item)
  })
}

function localizeTimelineTitle(event) {
  const lang = normalizeLanguage(state.activeLanguage)
  if (lang === 'zh-CN') {
    if (event.type === 'project_created') return '项目创建'
    if (event.type === 'plan_version') return `计划版本 ${event.version_index || ''}`.trim()
    if (event.type === 'intervention') return `干预提交 · ${stageLabel(event.stage || 'research')}`
    if (event.type === 'chat') return `与 ${profileByAgent(event.agent || '').name || event.agent} 对话`
    if (event.type === 'task') return `任务 · ${event.title}`
    return event.title || ''
  }
  if (event.type === 'project_created') return 'Project Created'
  if (event.type === 'plan_version') return `Plan Version ${event.version_index || ''}`.trim()
  if (event.type === 'intervention') return `Intervention · ${stageLabel(event.stage || 'research')}`
  if (event.type === 'chat') return `Chat with ${profileByAgent(event.agent || '').name || event.agent}`
  return event.title || ''
}

function localizeTimelineDetail(event) {
  if (!event.detail) return ''
  if (event.type === 'intervention') {
    const raw = String(event.detail)
    const separator = raw.indexOf(':')
    if (separator > 0) {
      const speaker = raw.slice(0, separator).trim()
      const content = raw.slice(separator + 1).trim()
      return `${localizeEmployeeName(speaker)}: ${content}`
    }
  }
  return String(event.detail)
}

function renderTimeline(events) {
  timeline.innerHTML = ''
  events.forEach((event) => {
    const item = document.createElement('div')
    item.className = 'timeline-item'
    const title = localizeTimelineTitle(event)
    const detail = localizeTimelineDetail(event)
    item.innerHTML = `
      <div class="timeline-title">${title}</div>
      <div class="timeline-detail">${detail || ''}</div>
      <div class="timeline-time">${new Date(event.timestamp).toLocaleString()}</div>
    `
    timeline.appendChild(item)
  })
}

function renderDiffSelectors(plans) {
  diffFrom.innerHTML = ''
  diffTo.innerHTML = ''
  if (plans.length < 2) {
    loadDiffButton.disabled = true
    diffOutput.textContent = '至少需要两个版本。'
    return
  }

  plans.forEach((plan) => {
    const leftOption = document.createElement('option')
    leftOption.value = plan.version_id
    leftOption.textContent = `${plan.version_id} · ${new Date(plan.created_at).toLocaleString()}`
    diffFrom.appendChild(leftOption)

    const rightOption = document.createElement('option')
    rightOption.value = plan.version_id
    rightOption.textContent = `${plan.version_id} · ${new Date(plan.created_at).toLocaleString()}`
    diffTo.appendChild(rightOption)
  })
  diffFrom.selectedIndex = Math.max(0, plans.length - 2)
  diffTo.selectedIndex = plans.length - 1
  loadDiffButton.disabled = false
}

function renderChat(agent, history) {
  const agentProfile = profileByAgent(agent)
  const currentUserProfile = userProfile()
  const historyScope = chatHistoryScopeSelect?.value || 'all'
  const currentStage = state.activeProject?.current_stage
  const visibleHistory = historyScope === 'current_stage'
    ? history.filter((turn) => !turn.suggested_stage || turn.suggested_stage === currentStage)
    : history

  chatHistory.innerHTML = ''
  if (!visibleHistory.length) {
    const emptyText = historyScope === 'current_stage'
      ? t('emptyCurrentStage')
      : t('emptyAll')
    chatHistory.innerHTML = `
      <div class="chat-row incoming">
        <div class="chat-avatar" style="${avatarStyle(agentProfile)}">${escapeHtml(agentProfile.avatar)}</div>
        <div class="chat-bubble agent">
          <div class="chat-bubble-head">
            <span class="chat-role">${escapeHtml(agentProfile.name)}</span>
          </div>
          <div class="chat-message">${emptyText}</div>
        </div>
      </div>
    `
    return
  }

  visibleHistory.forEach((turn) => {
    const source = turn.source || 'chat'
    const replyProfile = profileByTurn(agent, turn)

    if (source === 'chat' && turn.user_message) {
      const userRow = document.createElement('div')
      userRow.className = 'chat-row outgoing'
      userRow.innerHTML = `
        <div class="chat-bubble user">
          <div class="chat-bubble-head">
            <span class="chat-role">${escapeHtml(currentUserProfile.name)}</span>
            <span class="chat-time">${new Date(turn.created_at).toLocaleString()}</span>
          </div>
          <div class="chat-message">${formatChatBody(turn.user_message)}</div>
        </div>
        <div class="chat-avatar" style="${avatarStyle(currentUserProfile)}">${escapeHtml(currentUserProfile.avatar)}</div>
      `
      chatHistory.appendChild(userRow)
    }

    const reply = document.createElement('div')
    reply.className = 'chat-row incoming'
    const promoteButton = turn.can_promote_to_intervention
      ? `<div class="chat-actions"><button class="chat-promote" data-turn-id="${turn.turn_id}">${t('promoteButton')}</button></div>`
      : ''
    const sourceLabel =
      source === 'stage_review'
        ? t('sourceStageReview')
        : source === 'employee_statement'
          ? t('sourceEmployeeStatement')
          : `${turn.used_llm ? 'LLM' : 'Fallback'} · ${t('sourceSuggestedStage')} ${escapeHtml(turn.suggested_stage)}`
    const impactLabel =
      source === 'chat'
        ? `${t('impactSuggested')}: ${escapeHtml(turn.suggested_impact)}`
        : `${t('impactSource')}: ${escapeHtml(turn.suggested_impact)}`
    reply.innerHTML = `
      <div class="chat-avatar" style="${avatarStyle(replyProfile)}">${escapeHtml(replyProfile.avatar)}</div>
      <div class="chat-bubble agent">
        <div class="chat-bubble-head">
          <span class="chat-role">${escapeHtml(replyProfile.name)}</span>
          <span class="chat-time">${new Date(turn.created_at).toLocaleString()}</span>
        </div>
        <div class="chat-message">${formatChatBody(turn.assistant_message)}</div>
        <div class="chat-meta">${sourceLabel}</div>
        <div class="chat-meta">${impactLabel}</div>
        ${promoteButton}
      </div>
    `
    chatHistory.appendChild(reply)
  })
  chatHistory.scrollTop = chatHistory.scrollHeight
}

async function loadProjects() {
  const previousProjectId = state.activeProject?.project_id
  const projects = await api('/api/projects')
  state.projects = projects

  if (projects.length === 0) {
    renderProjects()
    resetProjectView()
    return
  }

  if (previousProjectId) {
    const stillExists = projects.some((project) => project.project_id === previousProjectId)
    if (!stillExists) {
      state.activeProject = null
    }
  }

  renderProjects()
  if (!state.activeProject) {
    showProject(projects[0])
  }
}

async function deleteProject(projectId) {
  await api(`/api/projects/${projectId}`, { method: 'DELETE' })
  delete state.chatHistoryByProject[projectId]
  delete state.employeeRosterByProjectAgent[projectId]
  if (state.activeProject?.project_id === projectId) {
    state.activeProject = null
  }
  await loadProjects()
}

async function createProject(payload, autoGenerate = false) {
  const project = await api('/api/projects', {
    method: 'POST',
    body: JSON.stringify({
      title: payload.title,
      summary: payload.summary,
      constraints: payload.constraints || [],
      metrics: payload.metrics || [],
      language: state.activeLanguage,
    }),
  })
  if (!autoGenerate) {
    return project
  }
  const generation = await api('/api/planning/generate', {
    method: 'POST',
    body: JSON.stringify({ project_id: project.project_id }),
  })
  return generation.project
}

async function loadProgress(projectId) {
  const data = await api(`/api/projects/${projectId}/progress`)
  renderProgress(data.stages)
}

async function loadTimeline(projectId) {
  const events = await api(`/api/projects/${projectId}/timeline`)
  renderTimeline(events)
}

async function loadChat(projectId, agent) {
  const data = await api(`/api/projects/${projectId}/chat?agent=${encodeURIComponent(agent)}`)
  if (data.language) {
    state.activeLanguage = normalizeLanguage(data.language)
    renderLanguageButton()
  }
  await loadEmployeeRoster(projectId, agent)
  setCachedChatHistory(projectId, agent, data.history)
  renderChat(data.agent, data.history)
}

function triggerDownload(filename, content) {
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

async function exportReplayDemo() {
  if (!state.activeProject) return
  chatStatus.textContent = t('replayExporting')
  try {
    const data = await api(`/api/projects/${state.activeProject.project_id}/chat/replay-demo`)
    const exportedAt = String(data.exported_at || '').replace(/[:.]/g, '-')
    const safeTime = exportedAt || new Date().toISOString().replace(/[:.]/g, '-')
    const filename = `${state.activeProject.project_id}_replay_demo_${safeTime}.json`
    triggerDownload(filename, JSON.stringify(data, null, 2))
    chatStatus.textContent = t('replayExported')
  } catch (error) {
    chatStatus.textContent = `${t('replayExportFailed')}: ${error.message}`
  }
}

async function promoteTurn(turnId) {
  if (!state.activeProject) return
  chatStatus.textContent = t('chatPromoting')
  const data = await api(`/api/projects/${state.activeProject.project_id}/chat/promote`, {
    method: 'POST',
    body: JSON.stringify({ turn_id: turnId }),
  })
  showProject(data.project)
  await loadProjects()
  chatStatus.textContent = t('promotedNoRegenerate')
}

async function toggleConversationLanguage() {
  if (!state.activeProject) return
  const currentIndex = LANGUAGE_SEQUENCE.indexOf(normalizeLanguage(state.activeLanguage))
  const nextLanguage = LANGUAGE_SEQUENCE[(currentIndex + 1) % LANGUAGE_SEQUENCE.length]

  chatStatus.textContent = t('languageSwitching')
  try {
    const data = await api(`/api/projects/${state.activeProject.project_id}/language`, {
      method: 'POST',
      body: JSON.stringify({ language: nextLanguage }),
    })
    state.activeLanguage = normalizeLanguage(data.language)
    state.activeProject = {
      ...state.activeProject,
      conversation_language: state.activeLanguage,
    }
    applyLanguageToChatUi()
    updateGenerateButton(state.activeProject)
    renderProjects()
    await loadProgress(state.activeProject.project_id)
    await loadTimeline(state.activeProject.project_id)
    chatStatus.textContent = t('languageSaved')
  } catch (error) {
    chatStatus.textContent = `${t('languageError')}: ${error.message}`
  }
}

document.getElementById('create-project-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const form = new FormData(event.currentTarget)
  const constraints = String(form.get('constraints') || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)

  const project = await createProject({
    title: form.get('title'),
    summary: form.get('summary'),
    constraints,
  })
  state.projects.unshift(project)
  renderProjects()
  showProject(project)
  event.currentTarget.reset()
})

generatePlanButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  projectMeta.textContent = '正在执行下一环节...'
  const data = await api('/api/planning/generate', {
    method: 'POST',
    body: JSON.stringify({ project_id: state.activeProject.project_id }),
  })
  showProject(data.project)
  if (data.executed_stage) {
    projectMeta.textContent = `${projectStatusLabel(data.project.status)} · ${stageLabel(data.project.current_stage)} · ${normalizeLanguage(state.activeLanguage) === 'zh-CN' ? '已执行环节' : 'executed stage'} ${stageLabel(data.executed_stage)}`
  }
  await loadProjects()
})

document.getElementById('intervention-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  if (!state.activeProject) return
  const form = new FormData(event.currentTarget)
  const data = await api('/api/planning/interventions', {
    method: 'POST',
    body: JSON.stringify({
      project_id: state.activeProject.project_id,
      stage: form.get('stage'),
      speaker: form.get('speaker'),
      message: form.get('message'),
      impact: form.get('impact'),
    }),
  })
  showProject(data.project)
  await loadProjects()
  chatStatus.textContent = t('interventionSaved')
})

document.getElementById('chat-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  if (!state.activeProject) return
  const messageField = document.getElementById('chat-message')
  const message = messageField.value.trim()
  if (!message) return
  const agent = chatAgentSelect.value
  chatStatus.textContent = t('chatSending')
  const data = await api(`/api/projects/${state.activeProject.project_id}/chat`, {
    method: 'POST',
    body: JSON.stringify({ agent, message, language: state.activeLanguage }),
  })
  if (data.language) {
    state.activeLanguage = normalizeLanguage(data.language)
    renderLanguageButton()
  }
  setCachedChatHistory(state.activeProject.project_id, agent, data.history)
  renderChat(data.agent, data.history)
  chatStatus.textContent = t('chatReceived')
  employeePickerPanel.classList.add('hidden')
  messageField.value = ''
})

chatHistory.addEventListener('click', async (event) => {
  const button = event.target.closest('.chat-promote')
  if (!button) return
  await promoteTurn(button.dataset.turnId)
})

employeePickerToggleButton.addEventListener('click', () => {
  if (!state.activeProject || !isDepartmentAgent(chatAgentSelect.value)) return
  employeePickerPanel.classList.toggle('hidden')
})

employeePickerPanel.addEventListener('click', (event) => {
  const button = event.target.closest('.employee-item')
  if (!button) return
  const mention = button.dataset.mention
  if (!mention) return
  insertEmployeeMention(mention)
  employeePickerPanel.classList.add('hidden')
})

loadDiffButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  const data = await api(
    `/api/projects/${state.activeProject.project_id}/plans/diff?from=${encodeURIComponent(diffFrom.value)}&to=${encodeURIComponent(diffTo.value)}`,
  )
  diffOutput.textContent = data.diff || '两个版本没有文本差异。'
})

document.getElementById('refresh-projects').addEventListener('click', loadProjects)
languageToggleButton.addEventListener('click', toggleConversationLanguage)
refreshChatButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  await loadChat(state.activeProject.project_id, chatAgentSelect.value)
})
exportReplayDemoButton.addEventListener('click', exportReplayDemo)
importReplayDemoButton.addEventListener('click', () => replayFileInput.click())
replayFileInput.addEventListener('change', async (event) => {
  const file = event.target.files?.[0]
  await importReplayFromFile(file)
  event.target.value = ''
})
replayPlayButton.addEventListener('click', () => {
  startReplayAutoplay()
})
replayPauseButton.addEventListener('click', () => {
  stopReplayAutoplay()
  replayStatus.textContent = t('replayPaused')
})
replayResetButton.addEventListener('click', () => {
  state.replayPlayer.currentIndex = -1
  stopReplayAutoplay()
  renderReplayPlayer()
  startReplayAutoplay()
})
replaySpeedSelect.addEventListener('change', () => {
  state.replayPlayer.speed = Number(replaySpeedSelect.value || '1')
  if (state.replayPlayer.timer) {
    startReplayAutoplay()
  }
})
chatAgentSelect.addEventListener('change', async () => {
  if (!state.activeProject) return
  employeePickerPanel.classList.add('hidden')
  await loadChat(state.activeProject.project_id, chatAgentSelect.value)
})
chatHistoryScopeSelect.addEventListener('change', () => {
  if (!state.activeProject) return
  const agent = chatAgentSelect.value
  const history = getCachedChatHistory(state.activeProject.project_id, agent)
  renderChat(agent, history)
})

loadProjects().catch((error) => {
  projectMeta.textContent = error.message
})

renderDemoProjects()
renderScorecard(null)
renderLanguageButton()
applyLanguageToStageSelector()
renderEmployeePicker(chatAgentSelect.value)
updateReplayControlState()
renderReplayPlayer()