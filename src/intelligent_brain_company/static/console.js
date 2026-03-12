const state = {
  projects: [],
  activeProject: null,
  chatHistoryByProject: {},
}

function getCachedChatHistory(projectId, agent) {
  return state.chatHistoryByProject[projectId]?.[agent] || []
}

function setCachedChatHistory(projectId, agent, history) {
  if (!state.chatHistoryByProject[projectId]) {
    state.chatHistoryByProject[projectId] = {}
  }
  state.chatHistoryByProject[projectId][agent] = history
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
const refreshChatButton = document.getElementById('refresh-chat')
const generatePlanButton = document.getElementById('generate-plan')
const submitInterventionButton = document.getElementById('submit-intervention')
const loadDiffButton = document.getElementById('load-diff')

const NEXT_STAGE_ACTION = {
  intake: '执行研究阶段',
  research: '执行部门评审',
  department_design: '执行跨部门评审',
  roundtable: '执行方案综合',
  synthesis: '执行董事会评审',
  board: '已完成全部环节',
}

const AGENT_PROFILES = {
  research: { name: '研究组', avatar: '研', hue: 198 },
  board: { name: '董事会', avatar: '董', hue: 16 },
  hardware: { name: '硬件组', avatar: '硬', hue: 32 },
  software: { name: '软件组', avatar: '软', hue: 220 },
  design: { name: '设计组', avatar: '设', hue: 284 },
  marketing: { name: '营销组', avatar: '营', hue: 138 },
  finance: { name: '财务组', avatar: '财', hue: 50 },
}

const USER_PROFILE = { name: '你', avatar: '你', hue: 188 }
const STAGE_REPLAY_PROFILE = { name: '阶段评审回放', avatar: '回', hue: 270 }

function profileByAgent(agent) {
  return AGENT_PROFILES[agent] || { name: agent, avatar: String(agent || '?').slice(0, 1), hue: 210 }
}

function profileByTurn(agent, turn) {
  if (turn.source === 'stage_review') {
    return STAGE_REPLAY_PROFILE
  }
  if (turn.source === 'chat' && turn.speaker && turn.speaker !== agent) {
    const speaker = String(turn.speaker)
    return { name: speaker, avatar: speaker.slice(0, 1), hue: 126 }
  }
  if (turn.source === 'employee_statement') {
    const speaker = String(turn.speaker || '员工')
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
  const action = NEXT_STAGE_ACTION[project.current_stage] || '执行下一环节'
  generatePlanButton.textContent = action
  generatePlanButton.disabled = project.current_stage === 'board'
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
  chatStatus.textContent = '聊天内容可以直接提升为正式干预并触发重算。'
  generatePlanButton.textContent = '执行下一环节'
  generatePlanButton.disabled = true
  submitInterventionButton.disabled = true
  sendChatButton.disabled = true
  refreshChatButton.disabled = true
  loadDiffButton.disabled = true
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
  const recommendation = project.latest_plan?.scorecard?.recommendation
  projectName.textContent = project.name
  projectMeta.textContent = recommendation
    ? `${project.status} · ${project.current_stage} · ${project.plans.length} 个版本 · 结论 ${recommendation}`
    : `${project.status} · ${project.current_stage} · ${project.plans.length} 个版本`
  planMarkdown.textContent = project.latest_plan_markdown || '尚未生成计划。'
  renderScorecard(project.latest_plan?.scorecard || null)
  updateGenerateButton(project)
  submitInterventionButton.disabled = false
  sendChatButton.disabled = false
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
      <div class="project-card-meta">${project.status} · ${project.plans.length} versions</div>
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
      <div>${stage.label}</div>
      <span class="stage-badge ${stage.status}">${stage.status}</span>
    `
    stageProgress.appendChild(item)
  })
}

function renderTimeline(events) {
  timeline.innerHTML = ''
  events.forEach((event) => {
    const item = document.createElement('div')
    item.className = 'timeline-item'
    item.innerHTML = `
      <div class="timeline-title">${event.title}</div>
      <div class="timeline-detail">${event.detail || ''}</div>
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
  const historyScope = chatHistoryScopeSelect?.value || 'all'
  const currentStage = state.activeProject?.current_stage
  const visibleHistory = historyScope === 'current_stage'
    ? history.filter((turn) => !turn.suggested_stage || turn.suggested_stage === currentStage)
    : history

  chatHistory.innerHTML = ''
  if (!visibleHistory.length) {
    const emptyText = historyScope === 'current_stage'
      ? '当前环节下还没有可展示的记录。'
      : '当前角色还没有对话记录。'
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
            <span class="chat-role">${escapeHtml(USER_PROFILE.name)}</span>
            <span class="chat-time">${new Date(turn.created_at).toLocaleString()}</span>
          </div>
          <div class="chat-message">${formatChatBody(turn.user_message)}</div>
        </div>
        <div class="chat-avatar" style="${avatarStyle(USER_PROFILE)}">${escapeHtml(USER_PROFILE.avatar)}</div>
      `
      chatHistory.appendChild(userRow)
    }

    const reply = document.createElement('div')
    reply.className = 'chat-row incoming'
    const promoteButton = turn.can_promote_to_intervention
      ? `<div class="chat-actions"><button class="chat-promote" data-turn-id="${turn.turn_id}">转成正式干预并重算</button></div>`
      : ''
    const sourceLabel =
      source === 'stage_review'
        ? '阶段评审输出'
        : source === 'employee_statement'
          ? '员工发言'
          : `${turn.used_llm ? 'LLM' : 'Fallback'} · 建议阶段 ${escapeHtml(turn.suggested_stage)}`
    const impactLabel =
      source === 'chat' ? `建议影响: ${escapeHtml(turn.suggested_impact)}` : `来源: ${escapeHtml(turn.suggested_impact)}`
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
  setCachedChatHistory(projectId, agent, data.history)
  renderChat(data.agent, data.history)
}

async function promoteTurn(turnId) {
  if (!state.activeProject) return
  chatStatus.textContent = '正在将聊天提升为正式干预并重算...'
  const data = await api(`/api/projects/${state.activeProject.project_id}/chat/promote`, {
    method: 'POST',
    body: JSON.stringify({ turn_id: turnId }),
  })
  showProject(data.project)
  await loadProjects()
  chatStatus.textContent = `已根据 ${data.promoted_turn.turn_id} 生成新版本。`
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
    projectMeta.textContent = `${data.project.status} · ${data.project.current_stage} · 已执行环节 ${data.executed_stage}`
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
})

document.getElementById('chat-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  if (!state.activeProject) return
  const messageField = document.getElementById('chat-message')
  const message = messageField.value.trim()
  if (!message) return
  const agent = chatAgentSelect.value
  chatStatus.textContent = '正在发送消息...'
  const data = await api(`/api/projects/${state.activeProject.project_id}/chat`, {
    method: 'POST',
    body: JSON.stringify({ agent, message }),
  })
  setCachedChatHistory(state.activeProject.project_id, agent, data.history)
  renderChat(data.agent, data.history)
  chatStatus.textContent = '已收到回复，可直接提升为正式干预。'
  messageField.value = ''
})

chatHistory.addEventListener('click', async (event) => {
  const button = event.target.closest('.chat-promote')
  if (!button) return
  await promoteTurn(button.dataset.turnId)
})

loadDiffButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  const data = await api(
    `/api/projects/${state.activeProject.project_id}/plans/diff?from=${encodeURIComponent(diffFrom.value)}&to=${encodeURIComponent(diffTo.value)}`,
  )
  diffOutput.textContent = data.diff || '两个版本没有文本差异。'
})

document.getElementById('refresh-projects').addEventListener('click', loadProjects)
refreshChatButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  await loadChat(state.activeProject.project_id, chatAgentSelect.value)
})
chatAgentSelect.addEventListener('change', async () => {
  if (!state.activeProject) return
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