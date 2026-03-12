const state = {
  projects: [],
  activeProject: null,
}

const projectList = document.getElementById('project-list')
const projectName = document.getElementById('project-name')
const projectMeta = document.getElementById('project-meta')
const planMarkdown = document.getElementById('plan-markdown')
const stageProgress = document.getElementById('stage-progress')
const timeline = document.getElementById('timeline')
const diffFrom = document.getElementById('diff-from')
const diffTo = document.getElementById('diff-to')
const diffOutput = document.getElementById('diff-output')
const chatAgentSelect = document.getElementById('chat-agent')
const chatHistory = document.getElementById('chat-history')
const chatStatus = document.getElementById('chat-status')
const sendChatButton = document.getElementById('send-chat')
const refreshChatButton = document.getElementById('refresh-chat')
const generatePlanButton = document.getElementById('generate-plan')
const submitInterventionButton = document.getElementById('submit-intervention')
const loadDiffButton = document.getElementById('load-diff')

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
  projectName.textContent = project.name
  projectMeta.textContent = `${project.status} · ${project.current_stage} · ${project.plans.length} 个版本`
  planMarkdown.textContent = project.latest_plan_markdown || '尚未生成计划。'
  generatePlanButton.disabled = false
  submitInterventionButton.disabled = false
  sendChatButton.disabled = false
  refreshChatButton.disabled = false
  renderProjects()
  loadProgress(project.project_id)
  loadTimeline(project.project_id)
  renderDiffSelectors(project.plans)
  loadChat(project.project_id, chatAgentSelect.value)
}

function renderProjects() {
  projectList.innerHTML = ''
  state.projects.forEach((project) => {
    const button = document.createElement('button')
    button.className = `project-card ${state.activeProject?.project_id === project.project_id ? 'active' : ''}`
    button.innerHTML = `
      <div class="project-card-title">${project.name}</div>
      <div class="project-card-meta">${project.status} · ${project.plans.length} versions</div>
    `
    button.addEventListener('click', async () => {
      const fresh = await api(`/api/projects/${project.project_id}`)
      showProject(fresh)
    })
    projectList.appendChild(button)
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
  chatHistory.innerHTML = ''
  if (!history.length) {
    chatHistory.innerHTML = '<div class="chat-bubble agent"><div class="chat-role">系统</div><div>当前角色还没有对话记录。</div></div>'
    return
  }

  history.forEach((turn) => {
    const user = document.createElement('div')
    user.className = 'chat-bubble user'
    user.innerHTML = `
      <div class="chat-role">你 -> ${agent}</div>
      <div>${turn.user_message}</div>
      <div class="chat-meta">${new Date(turn.created_at).toLocaleString()}</div>
    `
    chatHistory.appendChild(user)

    const reply = document.createElement('div')
    reply.className = 'chat-bubble agent'
    const promoteButton = turn.can_promote_to_intervention
      ? `<div class="chat-actions"><button class="chat-promote" data-turn-id="${turn.turn_id}">转成正式干预并重算</button></div>`
      : ''
    reply.innerHTML = `
      <div class="chat-role">${agent}</div>
      <div>${turn.assistant_message}</div>
      <div class="chat-meta">${turn.used_llm ? 'LLM' : 'Fallback'} · ${new Date(turn.created_at).toLocaleString()}</div>
      <div class="chat-meta">建议阶段: ${turn.suggested_stage} · 建议影响: ${turn.suggested_impact}</div>
      ${promoteButton}
    `
    chatHistory.appendChild(reply)
  })
  chatHistory.scrollTop = chatHistory.scrollHeight
}

async function loadProjects() {
  const projects = await api('/api/projects')
  state.projects = projects
  renderProjects()
  if (!state.activeProject && projects.length > 0) {
    showProject(projects[0])
  }
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

  const project = await api('/api/projects', {
    method: 'POST',
    body: JSON.stringify({
      title: form.get('title'),
      summary: form.get('summary'),
      constraints,
    }),
  })
  state.projects.unshift(project)
  renderProjects()
  showProject(project)
  event.currentTarget.reset()
})

generatePlanButton.addEventListener('click', async () => {
  if (!state.activeProject) return
  const data = await api('/api/planning/generate', {
    method: 'POST',
    body: JSON.stringify({ project_id: state.activeProject.project_id }),
  })
  showProject(data.project)
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
  const data = await api(`/api/projects/${state.activeProject.project_id}/chat`, {
    method: 'POST',
    body: JSON.stringify({ agent, message }),
  })
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

loadProjects().catch((error) => {
  projectMeta.textContent = error.message
})