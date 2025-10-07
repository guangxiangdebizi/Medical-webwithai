// chat.js - 聊天界面逻辑
class ChatApp {
    constructor() {
        this.wsManager = new WebSocketManager();
        this.currentAIMessage = null; // 当前正在接收的AI消息
        this.currentAIContent = ''; // 当前AI消息的累积内容
        this.thinkingFlow = new ThinkingFlow(this); // 思维流管理器
        this.sessionId = null; // 当前会话ID，由后端分配
        this.isStreaming = false; // 是否正在生成（用于切换发送/暂停）
        
        // DOM 元素
        this.chatMessages = document.getElementById('chatMessages');
        // 缓存欢迎卡片模板，供“Start New Chat”复用
        this.welcomeHTML = (this.chatMessages.querySelector('.welcome-message')?.outerHTML) || '';
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.startNewChatBtn = document.getElementById('startNewChatBtn');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.connectionText = document.getElementById('connectionText');
        this.charCount = document.getElementById('charCount');
        this.modelDropdownBtn = document.getElementById('modelDropdownBtn');
        this.modelDropdown = document.getElementById('modelDropdown');
        this.threadsList = document.getElementById('threadsList');
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        this.openSidebarBtn = document.getElementById('openSidebarBtn');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.fileInput = document.getElementById('fileInput');
        this.attachmentChips = document.getElementById('attachmentChips');
        this.pendingAttachments = [];
        this.mermaidInitialized = false;
        this.mermaidIdCounter = 0;
        
        this.init();
    }

    // 在最后一条AI消息下面插入用量提示，不纳入复制范围
    appendTokenUsageFooter(usage) {
        try {
            const { input_tokens, output_tokens, total_tokens } = usage || {};
            const container = this.chatMessages;
            if (!container) return;
            // 找到最后一个AI消息气泡
            const nodes = Array.from(container.querySelectorAll('.message.ai .message-bubble'));
            const last = nodes[nodes.length - 1];
            if (!last) return;
            // 如果已有footer则更新
            let footer = last.parentElement.querySelector('.ai-usage');
            if (!footer) {
                footer = document.createElement('div');
                footer.className = 'ai-usage';
                footer.style.cssText = 'margin-top:6px; font-size:12px; color:#94a3b8; user-select:none; -webkit-user-select:none;';
                last.parentElement.appendChild(footer);
            }
            const it = (input_tokens != null) ? input_tokens : '-';
            const ot = (output_tokens != null) ? output_tokens : '-';
            const tt = (total_tokens != null) ? total_tokens : ( (typeof it==='number'?it:0) + (typeof ot==='number'?ot:0) );
            footer.textContent = `Tokens: in ${it} | out ${ot} | total ${tt}`;
        } catch (e) {
            console.warn('渲染token用量提示失败', e);
        }
    }
    
    async init() {
        try {
            // 首先确保配置已加载
            if (!window.configManager.isLoaded) {
                await window.configManager.loadConfig();
            }
            
            // 配置加载成功后再初始化其他组件
            this.setupEventListeners();
            // 先加载Model并设置本地选择（确保首连就携带 model）
            await this.loadModelsAndRenderDropdown();
            this.setupWebSocket();
            await this.connectWebSocket();
        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            // 配置加载失败时，错误已经在configManager中显示，这里不需要额外处理
        }
    }
    
    setupEventListeners() {
        // 发送/暂停 按钮点击
        this.sendBtn.addEventListener('click', () => {
            if (this.isStreaming) {
                // 发送暂停指令
                this.wsManager.send({ type: 'pause' });
                // 立即将按钮恢复为Send，等待后端结束当前流
                this.isStreaming = false;
                this.updateSendButton();
                return;
            }
            this.sendMessage();
        });
        
        // 输入框事件
        this.messageInput.addEventListener('input', () => {
            this.updateCharCount();
            this.adjustInputHeight();
            this.updateSendButton();
        });
        
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                if (e.shiftKey) {
                    // Shift + Enter 换行
                    return;
                } else {
                    // Enter 发送
                    e.preventDefault();
                    this.sendMessage();
                }
            }
        });
        
        // 兼容旧按钮（如存在）
        if (this.clearChatBtn) {
            this.clearChatBtn.addEventListener('click', () => {
                // 仅清UI
                this.clearChat();
                // 明确用户点击清空时，才请求后端删除
                this.clearServerHistory();
            });
        }
        // 新建对话：仅清屏，不删除历史
        if (this.startNewChatBtn) {
            this.startNewChatBtn.addEventListener('click', () => {
                // 改为刷新页面，确保彻底重置连接与状态
                try { window.location.reload(); } catch (e) { try { window.location.href = window.location.href; } catch (_) {} }
            });
        }
        
        // 初始化分享模块
        this.shareModule = new ShareModule(this);

        
        // 页面卸载时关闭连接
        window.addEventListener('beforeunload', () => {
            this.wsManager.close();
        });

        // 侧栏开关
        if (this.toggleSidebarBtn) {
            this.toggleSidebarBtn.addEventListener('click', () => {
                const sidebar = document.getElementById('historySidebar');
                if (!sidebar) return;
                const isOpen = sidebar.classList.toggle('open');
                // 推拉主容器
                const app = document.querySelector('.app-container');
                if (app) {
                    app.classList.toggle('sidebar-open', isOpen);
                }
                this.toggleSidebarBtn.textContent = isOpen ? 'Hide' : 'Show';
            });
        }
        if (this.openSidebarBtn) {
            this.openSidebarBtn.addEventListener('click', async () => {
                const sidebar = document.getElementById('historySidebar');
                if (!sidebar) return;
                const isOpen = sidebar.classList.toggle('open');
                // 推拉主容器
                const app = document.querySelector('.app-container');
                if (app) {
                    app.classList.toggle('sidebar-open', isOpen);
                }
                // 打开时刷新；关闭时不动
                if (isOpen) {
                    await this.loadThreadsByMsidFromUrl();
                }
                // 可选：按钮文案提示
                this.openSidebarBtn.textContent = isOpen ? 'History (Open)' : 'History';
            });
        }

        // Model下拉
        if (this.modelDropdownBtn) {
            this.modelDropdownBtn.addEventListener('click', () => {
                if (!this.modelDropdown) return;
                this.modelDropdown.style.display = this.modelDropdown.style.display === 'none' || this.modelDropdown.style.display === '' ? 'block' : 'none';
            });
            // 点击页面其他地方关闭
            document.addEventListener('click', (e) => {
                if (!this.modelDropdownBtn.contains(e.target) && !this.modelDropdown.contains(e.target)) {
                    this.modelDropdown.style.display = 'none';
                }
            });
        }

        // 上传按钮与文件选择
        if (this.uploadBtn && this.fileInput) {
            this.uploadBtn.addEventListener('click', () => {
                try { this.fileInput.click(); } catch {}
            });
            this.fileInput.addEventListener('change', async (e) => {
                const files = Array.from(e.target.files || []);
                if (!files.length) return;
                try {
                    const items = await this.uploadFilesAndGetLinks(files);
                    this.addAttachmentChips(items);
                    this.pendingAttachments.push(...items);
                    this.updateSendButton();
                } catch (err) {
                    console.warn('文件上传失败', err);
                    this.showError('File upload failed');
                } finally {
                    try { this.fileInput.value = ''; } catch {}
                }
            });
        }

        // 粘贴图片支持
        if (this.messageInput) {
            this.messageInput.addEventListener('paste', async (event) => {
                try {
                    const clipboard = event.clipboardData || window.clipboardData;
                    if (!clipboard || !clipboard.items) return;
                    const imageItems = [];
                    for (const item of clipboard.items) {
                        if (item.kind === 'file' && item.type && item.type.startsWith('image/')) {
                            const blob = item.getAsFile();
                            if (blob) {
                                // 为粘贴内容生成文件名
                                const ext = (blob.type.split('/')[1] || 'png').toLowerCase();
                                const fname = `pasted-${Date.now()}.${ext}`;
                                const file = new File([blob], fname, { type: blob.type });
                                imageItems.push(file);
                            }
                        }
                    }
                    if (!imageItems.length) return;
                    event.preventDefault();
                    const items = await this.uploadFilesAndGetLinks(imageItems);
                    this.addAttachmentChips(items);
                    this.pendingAttachments.push(...items);
                    this.updateSendButton();
                } catch (e) {
                    console.warn('处理粘贴图片失败', e);
                }
            });
        }
    }
    
    setupWebSocket() {
        // WebSocket 事件回调
        this.wsManager.onOpen = () => {
            this.updateConnectionStatus('online');
            this.hideLoading();
        };
        
        this.wsManager.onMessage = (data) => {
            this.handleWebSocketMessage(data);
        };
        
        this.wsManager.onClose = () => {
            this.updateConnectionStatus('offline');
        };
        
        this.wsManager.onError = () => {
            this.updateConnectionStatus('offline');
            this.showError('WebSocket connection error');
        };
        
        this.wsManager.onReconnecting = (attempt, maxAttempts) => {
            this.updateConnectionStatus('connecting');
            this.showStatus(`Reconnecting... (${attempt}/${maxAttempts})`);
        };
    }
    
    async connectWebSocket() {
        this.updateConnectionStatus('connecting');
        await this.wsManager.connect();
        // 加载左侧线程列表（如果URL中有msid）
        this.loadThreadsByMsidFromUrl();
    }

    async loadThreadsByMsidFromUrl() {
        try {
            const urlParams = new URLSearchParams(window.location.search || '');
            const msid = urlParams.get('msid');
            if (!msid) return;
            const apiUrl = window.configManager.getFullApiUrl(`/api/threads?msid=${encodeURIComponent(msid)}`);
            const res = await fetch(apiUrl, { cache: 'no-store' });
            const json = await res.json();
            if (!json.success) return;
            this.renderThreads(json.data || []);
        } catch (e) { console.warn('加载线程列表失败', e); }
    }

    renderThreads(threads) {
        if (window.History && typeof window.History.renderThreads === 'function') {
            return window.History.renderThreads(this, threads);
        }
        // 回退：无模块时走旧逻辑（略）
    }

    async loadHistoryForConversation(sessionId, conversationId) {
        if (window.History && typeof window.History.loadHistoryForConversation === 'function') {
            return window.History.loadHistoryForConversation(this, sessionId, conversationId);
        }
    }

    async loadModelsAndRenderDropdown() {
        try {
            const apiUrl = window.configManager.getFullApiUrl('/api/models');
            const res = await fetch(apiUrl, { cache: 'no-store' });
            const json = await res.json();
            if (!json.success) throw new Error('加载Model列表失败');
            const { models, default: def } = json.data || { models: [], default: 'default' };

            let selected = localStorage.getItem('mcp_selected_model') || def;
            // 如果本地无记录，写入一次，保证首连就有 model
            if (!localStorage.getItem('mcp_selected_model')) {
                localStorage.setItem('mcp_selected_model', selected);
            }
            this.updateModelButtonLabel(models, selected);

            // 渲染菜单
            if (this.modelDropdown) {
                this.modelDropdown.innerHTML = '';
                models.forEach(m => {
                    const item = document.createElement('div');
                    item.className = 'dropdown-item';
                    item.textContent = `${m.label || m.id} (${m.model || ''})`;
                    item.addEventListener('click', async () => {
                        try {
                            // 改为通过WS指令切换模型，避免断开重连
                            localStorage.setItem('mcp_selected_model', m.id);
                            this.updateModelButtonLabel(models, m.id);
                            this.modelDropdown.style.display = 'none';
                            if (this.wsManager && this.wsManager.isConnected()) {
                                const ok = this.wsManager.send({ type: 'switch_model', model: m.id });
                                if (!ok) throw new Error('WS not connected');
                            } else {
                                // 若尚未连接，保留旧逻辑：初始化时会带上 model 参数
                                await this.connectWebSocket();
                            }
                        } catch (e) {
                            console.warn('切换模型失败，回退为重连方式', e);
                            try { this.wsManager.close(); } catch {}
                            this.wsManager.isInitialized = false;
                            await this.connectWebSocket();
                        }
                    });
                    this.modelDropdown.appendChild(item);
                });
            }
        } catch (e) {
            console.warn('⚠️ 无法加载Model列表:', e);
        }
    }

    async uploadFilesAndGetLinks(files) {
        if (!window.configManager || !window.configManager.isLoaded) {
            await window.configManager.loadConfig();
        }
        const apiUrl = window.configManager.getFullApiUrl('/api/upload');
        const results = [];
        for (const f of files) {
            const fd = new FormData();
            fd.append('file', f, f.name);
            const res = await fetch(apiUrl, { method: 'POST', body: fd });
            if (!res.ok) {
                const t = await res.text().catch(() => '');
                throw new Error(`Upload failed: ${res.status} ${t}`);
            }
            const json = await res.json();
            if (!json || !json.success || !json.data || !json.data.url) {
                throw new Error('Invalid upload response');
            }
            const urlPath = json.data.url; // like /uploads/20240101/uuid.ext
            const fullUrl = this.makeFullApiUrl(urlPath);
            // 若是图片，生成 dataURL 以便直接传给具备视觉能力的模型
            let dataUrl = null;
            const isImage = !!(f && f.type && f.type.startsWith('image/'));
            if (isImage) {
                try {
                    dataUrl = await this.readFileAsDataURL(f);
                } catch {}
            }
            results.push({ filename: json.data.filename || f.name, urlPath, fullUrl, isImage, dataUrl });
        }
        return results;
    }

    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            try {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = (e) => reject(e);
                reader.readAsDataURL(file);
            } catch (e) {
                reject(e);
            }
        });
    }

    addAttachmentChips(items) {
        if (!this.attachmentChips) return;
        items.forEach(item => {
            const chip = document.createElement('span');
            chip.className = 'attach-chip';
            chip.textContent = item.filename;
            const del = document.createElement('button');
            del.className = 'attach-chip-del';
            del.textContent = '×';
            del.addEventListener('click', (e) => {
                e.stopPropagation();
                chip.remove();
                this.pendingAttachments = (this.pendingAttachments || []).filter(x => x !== item);
                this.updateSendButton();
            });
            chip.addEventListener('click', (e) => {
                e.stopPropagation();
                this.downloadAttachment(item);
            });
            chip.appendChild(del);
            this.attachmentChips.appendChild(chip);
        });
    }

    clearAttachmentChips() {
        if (!this.attachmentChips) return;
        this.attachmentChips.innerHTML = '';
    }

    composeUserDisplayMessage(text, attachments) {
        const base = (text || '').trim();
        if (!attachments || attachments.length === 0) return base;
        const list = attachments.map(a => {
            const safeName = this.escapeHtml(a.filename);
            const safeUrl = this.escapeHtml(a.fullUrl);
            if (a.isImage) {
                const thumb = this.escapeHtml(a.dataUrl || a.fullUrl);
                return `• ${safeName}<br><img src="${thumb}" alt="${safeName}" style="max-width:180px;max-height:180px;border-radius:6px;border:1px solid #e2e8f0;margin:4px 0;"/>`;
            }
            return `• <a href="${safeUrl}" download target="_blank" rel="noopener noreferrer">${safeName}</a>`;
        }).join('<br>');
        const html = `${this.escapeHtml(base)}${base ? '<br><br>' : ''}<strong>Attachments:</strong><br>${list}`;
        return html;
    }

    downloadAttachment(item) {
        try {
            const a = document.createElement('a');
            a.href = item.fullUrl;
            a.download = item.filename || '';
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (e) {
            console.warn('下载失败', e);
        }
    }

    makeFullApiUrl(path) {
        try {
            const base = window.configManager.getApiBaseUrl();
            if (!path.startsWith('/')) return base + '/' + path;
            return base + path;
        } catch (e) {
            return path;
        }
    }

    insertTextAtCursor(text) {
        const el = this.messageInput;
        if (!el) return;
        const start = el.selectionStart ?? el.value.length;
        const end = el.selectionEnd ?? el.value.length;
        const before = el.value.substring(0, start);
        const after = el.value.substring(end);
        const needsSpace = before && !before.endsWith(' ');
        const insert = (needsSpace ? ' ' : '') + text;
        el.value = before + insert + after;
        const caret = (before + insert).length;
        try { el.setSelectionRange(caret, caret); } catch {}
        try { el.focus(); } catch {}
    }

    // 新增：AI消息操作（复制）
    attachAIActions(bubbleEl, rawText) {
        try {
            if (!bubbleEl) return;
            if (bubbleEl.querySelector('.msg-actions')) return;
            const actions = document.createElement('div');
            actions.className = 'msg-actions';
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.title = 'Copy';
            copyBtn.textContent = '📋';
            actions.appendChild(copyBtn);
            bubbleEl.appendChild(actions);

            copyBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const text = rawText != null ? String(rawText) : (bubbleEl.innerText || '');
                try {
                    if (navigator.clipboard && window.isSecureContext) {
                        await navigator.clipboard.writeText(text);
                    } else {
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                    }
                    copyBtn.textContent = '✅';
                    setTimeout(() => { copyBtn.textContent = '📋'; }, 1000);
                } catch (err) {
                    this.showError('Copy failed');
                }
            });
        } catch {}
    }

    updateModelButtonLabel(models, selectedId) {
        try {
            const picked = (models || []).find(m => m.id === selectedId);
            const label = picked ? (picked.label || picked.id) : selectedId;
            if (this.modelDropdownBtn) {
                this.modelDropdownBtn.textContent = `Model：${label} ▾`;
            }
        } catch {}
    }
    
    handleWebSocketMessage(data) {
        console.log('📨 收到消息:', data);
        
        switch (data.type) {
            case 'session_info':
                // 接收会话ID
                this.sessionId = data.session_id;
                console.log('🆔 收到会话ID:', this.sessionId);
                break;
            case 'resume_ok':
                // 后端确认续聊绑定成功
                try {
                    // 记录续聊目标，便于UI或后续逻辑使用（此处复用 sessionId 仅作显示，不影响底层WS）
                    this.resumedSessionId = data.session_id;
                    this.resumedConversationId = data.conversation_id;
                    console.log('✅ 续聊绑定成功 ->', this.resumedSessionId, this.resumedConversationId);
                } catch {}
                break;
            case 'resume_error':
                this.showError(`Resume failed: ${data.content || 'unknown error'}`);
                break;
            case 'edit_ok':
                // 回溯截断成功
                console.log('✂️ 回溯截断成功，开始重生');
                break;
            case 'edit_error':
                this.showError(`Edit failed: ${data.content || 'unknown error'}`);
                break;
                
            case 'user_msg_received':
                // 用户消息已收到确认
                break;
                
            case 'status':
                // 移除硬编码的status处理，让AI思考内容自然显示
                break;
                
            case 'ai_thinking_start':
                // 开始AI思考流式显示
                this.thinkingFlow.startThinkingContent(data.iteration);
                break;
                
            case 'ai_thinking_chunk':
                // AI思考内容片段
                this.thinkingFlow.appendThinkingContent(data.content, data.iteration);
                break;
                
            case 'ai_thinking_end':
                // 结束AI思考
                this.thinkingFlow.endThinkingContent(data.iteration);
                break;
                
            case 'tool_plan':
                this.thinkingFlow.updateThinkingStage(
                    'tools_planned', 
                    `Planning to use ${data.tool_count} tool(s)`, 
                    'Preparing clinical data operations...',
                    { toolCount: data.tool_count }
                );
                break;
                
            case 'tool_start':
                this.thinkingFlow.addToolToThinking(data);
                break;
                
            case 'tool_end':
                this.thinkingFlow.updateToolInThinking(data, 'completed');
                break;
                
            case 'tool_error':
                this.thinkingFlow.updateToolInThinking(data, 'error');
                break;
                
            case 'ai_response_start':
                this.thinkingFlow.updateThinkingStage('responding', 'Preparing response', 'Organizing evidence-based conclusions and recommendations...');
                
                // 确保思维流可见 - 智能滚动策略
                const currentFlow = this.thinkingFlow.getCurrentFlow();
                if (currentFlow && !this.isUserViewingContent()) {
                    // 只有用户不在查看历史内容时才滚动到思维流
                    setTimeout(() => {
                        currentFlow.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start',
                            inline: 'nearest'
                        });
                    }, 100);
                }

                this.startAIResponse();
                // 进入流式阶段，切换按钮为暂停
                this.isStreaming = true;
                this.updateSendButton();
                break;
                
            case 'ai_response_chunk':
                this.appendAIResponse(data.content);
                break;
                
            case 'ai_response_end':
                this.endAIResponse();
                this.thinkingFlow.completeThinkingFlow('success');
                // 结束流式，恢复按钮
                this.isStreaming = false;
                this.updateSendButton();
                break;
            case 'token_usage':
                // 在AI消息下方追加一行浅色用量提示，不进入复制范围
                this.appendTokenUsageFooter(data);
                break;
            case 'record_saved':
                // 后端返回新插入的记录ID，将最后一条用户消息补上操作按钮和recordId，避免刷新
                MessageActions.attachActionsToLastUserMessage(this, data);
                break;
                
            case 'error':
                this.showError(data.content);
                this.thinkingFlow.completeThinkingFlow('error');
                this.isStreaming = false;
                this.updateSendButton();
                break;
                
            default:
                console.warn('未知消息类型:', data.type);
        }
    }

    
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        const hasAttachments = (this.pendingAttachments && this.pendingAttachments.length > 0);
        if (!message && !hasAttachments) {
            return;
        }
        if (!this.wsManager.isConnected()) return;

        // 发送到服务器（若为回溯编辑，则发 replay_edit）。
        let payload;
        if (this.pendingEdit && this.pendingEdit.sessionId && this.pendingEdit.conversationId && this.pendingEdit.fromRecordId) {
            // 只有在真正发送时，才在前端截断（提高交互体验）
            this.truncateAfterRecord(this.pendingEdit.fromRecordId);
            payload = {
                type: 'replay_edit',
                session_id: this.pendingEdit.sessionId,
                conversation_id: this.pendingEdit.conversationId,
                from_record_id: this.pendingEdit.fromRecordId,
                new_user_input: message
            };
        } else {
            // 构建多模态内容：若包含图片，则将其作为 image_url 发送给模型
            const imageItems = (this.pendingAttachments || []).filter(a => a && a.isImage);
            if (imageItems.length > 0) {
                const parts = [];
                if (message) {
                    parts.push({ type: 'text', text: message });
                }
                imageItems.forEach(a => {
                    const urlForModel = a.dataUrl || a.fullUrl || a.urlPath;
                    parts.push({ type: 'image_url', image_url: { url: urlForModel } });
                });
                payload = {
                    type: 'user_msg',
                    content_parts: parts,
                    // 仍保留附件元信息，便于历史与下载
                    attachments: (this.pendingAttachments || []).map(a => ({ filename: a.filename, url: a.urlPath }))
                };
            } else {
                payload = { type: 'user_msg', content: message, attachments: (this.pendingAttachments || []).map(a => ({ filename: a.filename, url: a.urlPath })) };
            }
        }

        // 现在再把用户消息插入到UI，并立即附上复制/编辑动作（recordId 稍后由 record_saved 回填）
        const userDisplay = this.composeUserDisplayMessage(message, this.pendingAttachments);
        MessageActions.addUserMessageWithActions(this, userDisplay, {
            recordId: null,
            sessionId: this.resumedSessionId || this.sessionId,
            conversationId: this.resumedConversationId
        });

        // 清空输入框并重置状态
        this.messageInput.value = '';
        this.updateCharCount();
        this.adjustInputHeight();
        this.updateSendButton();
        this.clearAttachmentChips();
        this.pendingAttachments = [];

        // 隐藏欢迎消息
        this.hideWelcomeMessage();

        // 创建思维流
        this.thinkingFlow.createThinkingFlow();

        const success = this.wsManager.send(payload);
        
        if (!success) {
            this.showError('Failed to send message, please check network connection');
            this.thinkingFlow.completeThinkingFlow('error');
        } else {
            if (payload.type === 'replay_edit') {
                this.pendingEdit = null;
            }
        }
    }
    
    addUserMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        
        // 尝试渲染markdown，如果失败则使用原始文本
        let renderedContent;
        try {
            if (typeof marked !== 'undefined') {
                renderedContent = marked.parse(content);
            } else {
                renderedContent = this.escapeHtml(content);
            }
        } catch (error) {
            console.warn('User message Markdown rendering error:', error);
            renderedContent = this.escapeHtml(content);
        }
        
        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${renderedContent}
            </div>
        `;

        this.chatMessages.appendChild(messageDiv);
        this.smartScrollToBottom(true); // 用户消息强制滚动
    }

    // 带复制/编辑操作的用户消息（用于历史回放）
    addUserMessageWithActions(content, meta = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        if (meta && meta.recordId != null) {
            try { messageDiv.dataset.recordId = String(meta.recordId); } catch {}
        }

        let renderedContent;
        try {
            if (typeof marked !== 'undefined') {
                renderedContent = marked.parse(content);
            } else {
                renderedContent = this.escapeHtml(content);
            }
        } catch (error) {
            renderedContent = this.escapeHtml(content);
        }

        const actionsHtml = `
            <div class="msg-actions">
                <button class="copy-btn" title="Copy">📋</button>
                <button class="edit-btn" title="Edit & regenerate">✏️</button>
            </div>
        `;

        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${renderedContent}
                ${actionsHtml}
            </div>
        `;

        const copyBtn = messageDiv.querySelector('.copy-btn');
        const editBtn = messageDiv.querySelector('.edit-btn');

        copyBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(content);
                } else {
                    const ta = document.createElement('textarea');
                    ta.value = content;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                }
                copyBtn.textContent = '✅';
                setTimeout(() => { copyBtn.textContent = '📋'; }, 1000);
            } catch (err) {
                this.showError('Copy failed');
            }
        });

        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.messageInput.value = content;
            this.adjustInputHeight();
            this.updateCharCount();
            this.updateSendButton();
            this.pendingEdit = {
                sessionId: meta.sessionId,
                conversationId: meta.conversationId,
                fromRecordId: meta.recordId
            };
            try { this.messageInput.focus(); } catch {}
        });

        this.chatMessages.appendChild(messageDiv);
        this.smartScrollToBottom(); // 历史消息使用智能滚动
    }

    // 从指定记录ID对应的用户消息开始，删除其自身及后续的所有DOM节点
    truncateAfterRecord(recordId) {
        try {
            const nodes = Array.from(this.chatMessages.children);
            const anchor = nodes.find(el => el.classList && el.classList.contains('user') && String(el.dataset.recordId || '') === String(recordId));
            if (!anchor) return;
            let current = anchor;
            while (current) {
                const next = current.nextSibling;
                this.chatMessages.removeChild(current);
                current = next;
            }
            // 清理思维流/AI状态
            this.currentAIMessage = null;
            this.thinkingFlow.clear();
        } catch (e) { console.warn('截断历史失败', e); }
    }
    
    showStatus(content) {
        // 可以在这里显示状态信息，暂时用console.log
        console.log('📊 状态:', content);
    }
    
    
    startAIResponse() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai';
        messageDiv.innerHTML = `
            <div class="message-bubble">
                <span class="ai-cursor">▋</span>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.currentAIMessage = messageDiv.querySelector('.message-bubble');
        this.currentAIContent = ''; // 重置累积内容
        this.smartScrollToBottom(true); // AI回复开始时强制滚动
    }
    
    appendAIResponse(content) {
        if (this.currentAIMessage) {
            // 累积内容
            this.currentAIContent += content;

            // 实时渲染markdown
            this.renderMarkdownContent();

            // AI回复内容更新时使用智能滚动（尊重用户查看历史）
            this.smartScrollToBottom();
        }
    }
    
    endAIResponse() {
        if (this.currentAIMessage) {
            // 最终渲染markdown（确保所有内容都被处理）
            this.renderMarkdownContent(true);
            
            // 移除光标
            const cursor = this.currentAIMessage.querySelector('.ai-cursor');
            if (cursor) {
                cursor.remove();
            }
            
            // 新增：为AI消息添加复制按钮
            try {
                const rawFinal = this.currentAIContent || '';
                this.currentAIMessage.setAttribute('data-raw', rawFinal);
                this.attachAIActions(this.currentAIMessage, rawFinal);
            } catch {}
            
            this.currentAIMessage = null;
            this.currentAIContent = '';
        }
    }
    
    // 实时markdown渲染方法
    renderMarkdownContent(isFinal = false) {
        if (!this.currentAIMessage || typeof marked === 'undefined') {
            // 如果marked.js未加载，使用原始文本显示
            this.currentAIMessage.innerHTML = this.escapeHtml(this.currentAIContent) + 
                (!isFinal ? '<span class="ai-cursor">▋</span>' : '');
            return;
        }
        
        try {
            let content = this.currentAIContent;
            let renderedContent = '';
            
            if (isFinal) {
                // 最终渲染，直接处理所有内容
                renderedContent = marked.parse(content);
            } else {
                // 实时渲染，需要智能处理不完整的markdown
                renderedContent = this.renderPartialMarkdown(content);
            }
            
            // 更新内容并添加光标
            this.currentAIMessage.innerHTML = renderedContent + 
                (!isFinal ? '<span class="ai-cursor">▋</span>' : '');
            
            if (isFinal) {
                this.renderMermaidDiagrams(this.currentAIMessage);
            }
                
        } catch (error) {
            console.warn('Markdown渲染错误:', error);
            // 出错时使用原始文本
            this.currentAIMessage.innerHTML = this.escapeHtml(this.currentAIContent) + 
                (!isFinal ? '<span class="ai-cursor">▋</span>' : '');
        }
    }

    renderMermaidDiagrams(container) {
        if (!container || typeof window.mermaid === 'undefined' || !window.mermaid) {
            return;
        }

        try {
            if (!this.mermaidInitialized) {
                window.mermaid.initialize({ startOnLoad: false });
                this.mermaidInitialized = true;
            }
        } catch (e) {
            console.warn('Mermaid 初始化失败', e);
            return;
        }

        const selector = 'pre code.language-mermaid, pre code.lang-mermaid';
        const codeBlocks = container.querySelectorAll(selector);
        if (!codeBlocks.length) {
            return;
        }

        codeBlocks.forEach((codeBlock) => {
            if (!codeBlock || codeBlock.dataset.mermaidProcessed === 'true') {
                return;
            }
            const pre = codeBlock.closest('pre');
            if (!pre) {
                return;
            }

            const definition = codeBlock.textContent || '';
            const wrapper = document.createElement('div');
            wrapper.className = 'mermaid';
            wrapper.dataset.mermaidProcessed = 'true';
            wrapper.textContent = definition;

            try {
                pre.replaceWith(wrapper);
            } catch (e) {
                console.warn('Mermaid 容器替换失败', e);
                return;
            }

            const graphId = `mermaid-${Date.now()}-${this.mermaidIdCounter++}`;
            window.mermaid
                .render(graphId, definition)
                .then(({ svg, bindFunctions }) => {
                    wrapper.innerHTML = svg;
                    if (typeof bindFunctions === 'function') {
                        bindFunctions(wrapper);
                    }
                })
                .catch((err) => {
                    console.warn('Mermaid 渲染失败', err);
                    wrapper.classList.add('mermaid-error');
                    wrapper.innerHTML = `<pre>${this.escapeHtml(definition)}</pre>`;
                });

            codeBlock.dataset.mermaidProcessed = 'true';
        });
    }
    
    // 渲染部分markdown内容（处理不完整的语法）
    renderPartialMarkdown(content) {
        // 检测可能不完整的markdown模式
        const patterns = [
            { regex: /```[\s\S]*?```/g, type: 'codeblock' },  // 代码块
            { regex: /`[^`\n]*`/g, type: 'code' },            // 行内代码
            { regex: /\*\*[^*\n]*\*\*/g, type: 'bold' },      // 粗体
            { regex: /\*[^*\n]*\*/g, type: 'italic' },        // 斜体
            { regex: /^#{1,6}\s+.*/gm, type: 'heading' },     // 标题
            { regex: /^\*.+$/gm, type: 'list' },              // 列表
            { regex: /^\d+\..+$/gm, type: 'orderedlist' },    // 有序列表
            { regex: /^>.+$/gm, type: 'quote' }               // 引用
        ];
        
        let processedContent = content;
        let lastCompletePos = 0;
        
        // 找到最后一个完整的markdown元素位置
        for (let pattern of patterns) {
            const matches = [...content.matchAll(pattern.regex)];
            for (let match of matches) {
                const endPos = match.index + match[0].length;
                if (this.isCompleteMarkdown(match[0], pattern.type)) {
                    lastCompletePos = Math.max(lastCompletePos, endPos);
                }
            }
        }
        
        if (lastCompletePos > 0) {
            // 分割内容：完整部分用markdown渲染，不完整部分用原始文本
            const completeContent = content.substring(0, lastCompletePos);
            const incompleteContent = content.substring(lastCompletePos);
            
            const renderedComplete = marked.parse(completeContent);
            const escapedIncomplete = this.escapeHtml(incompleteContent);
            
            return renderedComplete + escapedIncomplete;
        } else {
            // 没有完整的markdown，使用原始文本
            return this.escapeHtml(content);
        }
    }
    
    // 检查markdown元素是否完整
    isCompleteMarkdown(text, type) {
        switch (type) {
            case 'codeblock':
                return text.startsWith('```') && text.endsWith('```') && text.length > 6;
            case 'code':
                return text.startsWith('`') && text.endsWith('`') && text.length > 2;
            case 'bold':
                return text.startsWith('**') && text.endsWith('**') && text.length > 4;
            case 'italic':
                return text.startsWith('*') && text.endsWith('*') && text.length > 2 && !text.startsWith('**');
            case 'heading':
                return text.match(/^#{1,6}\s+.+$/);
            case 'list':
                return text.match(/^\*\s+.+$/);
            case 'orderedlist':
                return text.match(/^\d+\.\s+.+$/);
            case 'quote':
                return text.match(/^>\s*.+$/);
            default:
                return true;
        }
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message ai';
        errorDiv.innerHTML = `
            <div class="message-bubble" style="background: rgba(245, 101, 101, 0.1); border-color: rgba(245, 101, 101, 0.3); color: #e53e3e;">
                ❌ ${this.escapeHtml(message)}
            </div>
        `;

        this.chatMessages.appendChild(errorDiv);
        this.smartScrollToBottom(true); // 错误消息强制滚动
    }
    
    clearChat() {
        // 清空消息区域，保留欢迎消息
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        this.chatMessages.innerHTML = '';
        
        if (welcomeMessage) {
            this.chatMessages.appendChild(welcomeMessage);
            welcomeMessage.style.display = 'block';
        }
        
        // 清理状态
        this.currentAIMessage = null;
        this.thinkingFlow.clear(); // 清理思维流状态
    }
    
    async clearServerHistory() {
        try {
            if (!window.configManager.isLoaded) {
                await window.configManager.loadConfig();
            }
            let apiUrl = window.configManager.getFullApiUrl('/api/history');
            if (this.sessionId) {
                apiUrl += `?session_id=${encodeURIComponent(this.sessionId)}`;
            }
            await fetch(apiUrl, { method: 'DELETE' });
        } catch (error) {
            console.warn('清空服务器历史失败:', error);
        }
    }
    
    hideWelcomeMessage() {
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus.className = `status-dot ${status}`;
        
        switch (status) {
            case 'online':
                this.connectionText.textContent = 'Online';
                break;
            case 'offline':
                this.connectionText.textContent = 'Offline';
                break;
            case 'connecting':
                this.connectionText.textContent = 'Connecting';
                break;
        }
    }

    setConnectionExtra(text) {
        try {
            if (!this.connectionText) return;
            const base = this.connectionText.textContent.split(' | ')[0];
            if (text) {
                this.connectionText.textContent = `${base} | ${text}`;
            } else {
                this.connectionText.textContent = base;
            }
        } catch {}
    }
    
    updateCharCount() {
        const count = this.messageInput.value.length;
        this.charCount.textContent = count;
        
        if (count > 1800) {
            this.charCount.style.color = '#e53e3e';
        } else if (count > 1500) {
            this.charCount.style.color = '#ed8936';
        } else {
            this.charCount.style.color = '#a0aec0';
        }
    }
    
    adjustInputHeight() {
        // 保存滚动位置
        const scrollTop = this.messageInput.scrollTop;
        
        // 重置高度
        this.messageInput.style.height = 'auto';
        
        // 设置新高度
        const newHeight = Math.min(this.messageInput.scrollHeight, 150);
        this.messageInput.style.height = newHeight + 'px';
        
        // 恢复滚动位置
        this.messageInput.scrollTop = scrollTop;
        
        // 如果内容超出了可视区域，滚动到底部
        if (this.messageInput.scrollHeight > newHeight) {
            this.messageInput.scrollTop = this.messageInput.scrollHeight;
        }
    }
    
    updateSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;
        const hasAttachments = (this.pendingAttachments && this.pendingAttachments.length > 0);
        const isConnected = this.wsManager.isConnected();

        if (this.isStreaming) {
            this.sendBtn.innerHTML = '⏸️';
            this.sendBtn.disabled = !isConnected; // 生成中允许点击暂停
        } else {
            this.sendBtn.innerHTML = '📤';
            this.sendBtn.disabled = (!hasText && !hasAttachments) || !isConnected;
        }
    }
    
    scrollToBottom() {
        // 使用requestAnimationFrame确保DOM更新完成后再滚动
        requestAnimationFrame(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        });
    }

    // 智能滚动：只有在用户接近底部时才滚动
    smartScrollToBottom(force = false) {
        if (!this.chatMessages) return;

        const container = this.chatMessages;
        const threshold = 100; // 底部100px范围内认为用户在底部
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

        // 如果强制滚动或用户在底部附近，才滚动
        if (force || distanceFromBottom <= threshold) {
            this.scrollToBottom();
        }
    }

    // 检查用户是否正在主动查看内容（用于决定是否滚动）
    isUserViewingContent() {
        if (!this.chatMessages) return false;

        const container = this.chatMessages;
        const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

        // 如果用户距离底部超过200px，认为正在查看历史内容
        return distanceFromBottom > 200;
    }
    
    escapeHtml(text) {
        if (text === null || text === undefined) {
            return '';
        }
        return text.toString()
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
    }
}
// 实例化并初始化
const chatApp = new ChatApp();
