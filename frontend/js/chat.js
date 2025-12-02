// chat.js - 聊天界面主逻辑（重构版）
class ChatApp {
    constructor() {
        this.wsManager = new WebSocketManager();
        this.currentAIMessage = null;
        this.currentAIContent = '';
        this.thinkingFlow = new ThinkingFlow(this);
        this.sessionId = null;
        this.isStreaming = false;
        
        // Doctor Review 模式
        this.reviewMode = false;
        this.reviewOutput = null;
        
        // DOM 元素
        this.chatMessages = document.getElementById('chatMessages');
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
        
        this.init();
    }
    
    /**
     * 获取当前输出目标容器（普通模式用 chatMessages，审核模式用 reviewOutput）
     */
    getOutputContainer() {
        if (this.reviewMode && this.reviewOutput) {
            return this.reviewOutput;
        }
        return this.chatMessages;
    }

    // 在最后一条 AI 消息下面插入用量提示
    appendTokenUsageFooter(usage) {
        try {
            const { input_tokens, output_tokens, total_tokens } = usage || {};
            const container = this.chatMessages;
            if (!container) return;
            
            const nodes = Array.from(container.querySelectorAll('.message.ai .message-bubble'));
            const last = nodes[nodes.length - 1];
            if (!last) return;
            
            let footer = last.parentElement.querySelector('.ai-usage');
            if (!footer) {
                footer = document.createElement('div');
                footer.className = 'ai-usage';
                footer.style.cssText = 'margin-top:6px; font-size:12px; color:#94a3b8; user-select:none; -webkit-user-select:none;';
                last.parentElement.appendChild(footer);
            }
            
            const it = (input_tokens != null) ? input_tokens : '-';
            const ot = (output_tokens != null) ? output_tokens : '-';
            const tt = (total_tokens != null) ? total_tokens : ((typeof it==='number'?it:0) + (typeof ot==='number'?ot:0));
            footer.textContent = `Tokens: in ${it} | out ${ot} | total ${tt}`;
        } catch (e) {
            console.warn('渲染 token 用量提示失败', e);
        }
    }
    
    async init() {
        try {
            // 确保配置已加载
            if (!window.configManager.isLoaded) {
                await window.configManager.loadConfig();
            }
            
            // 配置加载成功后再初始化其他组件
            this.setupEventListeners();
            await this.loadModelsAndRenderDropdown();
            this.setupWebSocket();
            await this.connectWebSocket();
            
            // 加载查询示例
            await this.loadQueryExamples();
        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
        }
    }
    
    async loadQueryExamples() {
        if (typeof QueryExamples !== 'undefined') {
            await QueryExamples.init(this);
        }
    }
    
    setupEventListeners() {
        EventListeners.setupAll(this);
    }
    
    setupWebSocket() {
        // WebSocket 事件回调
        this.wsManager.onOpen = () => {
            this.updateConnectionStatus('online');
        };
        
        this.wsManager.onMessage = (data) => {
            WebSocketHandler.handleMessage(data, this);
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
        } catch (e) {
            console.warn('加载线程列表失败', e);
        }
    }

    renderThreads(threads) {
        if (window.History && typeof window.History.renderThreads === 'function') {
            return window.History.renderThreads(this, threads);
        }
    }

    async loadHistoryForConversation(sessionId, conversationId) {
        if (window.History && typeof window.History.loadHistoryForConversation === 'function') {
            return window.History.loadHistoryForConversation(this, sessionId, conversationId);
        }
    }

    async loadModelsAndRenderDropdown() {
        await ModelManager.loadModelsAndRenderDropdown(
            window.configManager,
            this.modelDropdownBtn,
            this.modelDropdown,
            this.wsManager,
            () => this.connectWebSocket()
        );
    }

    async uploadFilesAndGetLinks(files) {
        return await FileManager.uploadFilesAndGetLinks(files, window.configManager);
    }

    addAttachmentChips(items) {
        FileManager.addAttachmentChips(
            items,
            this.attachmentChips,
            this.pendingAttachments,
            () => this.updateSendButton(),
            (item) => FileManager.downloadAttachment(item)
        );
    }

    clearAttachmentChips() {
        FileManager.clearAttachmentChips(this.attachmentChips);
    }

    composeUserDisplayMessage(text, attachments) {
        return FileManager.composeUserDisplayMessage(text, attachments, (t) => this.escapeHtml(t));
    }

    insertTextAtCursor(text) {
        UIController.insertTextAtCursor(this.messageInput, text);
    }

    // AI 消息操作（复制）
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
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        const hasAttachments = (this.pendingAttachments && this.pendingAttachments.length > 0);
        if (!message && !hasAttachments) return;
        if (!this.wsManager.isConnected()) return;

        // 发送到服务器
        let payload;
        if (this.pendingEdit && this.pendingEdit.sessionId && this.pendingEdit.conversationId && this.pendingEdit.fromRecordId) {
            this.truncateAfterRecord(this.pendingEdit.fromRecordId);
            payload = {
                type: 'replay_edit',
                session_id: this.pendingEdit.sessionId,
                conversation_id: this.pendingEdit.conversationId,
                from_record_id: this.pendingEdit.fromRecordId,
                new_user_input: message
            };
        } else {
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
                    attachments: (this.pendingAttachments || []).map(a => ({ filename: a.filename, url: a.urlPath }))
                };
            } else {
                payload = {
                    type: 'user_msg',
                    content: message,
                    attachments: (this.pendingAttachments || []).map(a => ({ filename: a.filename, url: a.urlPath }))
                };
            }
        }

        // 插入用户消息到 UI
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

        // 隐藏欢迎消息和示例
        this.hideWelcomeMessage();
        if (typeof QueryExamples !== 'undefined') {
            QueryExamples.hide();
        }

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
        this.smartScrollToBottom(true);
    }

    // 从指定记录 ID 开始截断
    truncateAfterRecord(recordId) {
        try {
            const nodes = Array.from(this.chatMessages.children);
            const anchor = nodes.find(el => el.classList && el.classList.contains('user') && 
                String(el.dataset.recordId || '') === String(recordId));
            if (!anchor) return;
            
            let current = anchor;
            while (current) {
                const next = current.nextSibling;
                this.chatMessages.removeChild(current);
                current = next;
            }
            
            this.currentAIMessage = null;
            this.thinkingFlow.clear();
        } catch (e) {
            console.warn('截断历史失败', e);
        }
    }
    
    showStatus(content) {
        console.log('📊 状态:', content);
    }
    
    startAIResponse() {
        const container = this.getOutputContainer();
        
        // 审核模式下清除进度提示
        if (this.reviewMode && this.reviewOutput) {
            const progress = this.reviewOutput.querySelector('.review-progress');
            if (progress) progress.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai';
        messageDiv.innerHTML = `
            <div class="message-bubble">
                <span class="ai-cursor">▋</span>
            </div>
        `;
        
        container.appendChild(messageDiv);
        this.currentAIMessage = messageDiv.querySelector('.message-bubble');
        this.currentAIContent = '';
        this.smartScrollToBottom(true);
    }
    
    appendAIResponse(content) {
        if (this.currentAIMessage) {
            this.currentAIContent += content;
            this.renderMarkdownContent();
            this.smartScrollToBottom();
        }
    }
    
    endAIResponse() {
        if (this.currentAIMessage) {
            this.renderMarkdownContent(true);
            
            const cursor = this.currentAIMessage.querySelector('.ai-cursor');
            if (cursor) cursor.remove();
            
            try {
                const rawFinal = this.currentAIContent || '';
                this.currentAIMessage.setAttribute('data-raw', rawFinal);
                this.attachAIActions(this.currentAIMessage, rawFinal);
            } catch {}
            
            this.currentAIMessage = null;
            this.currentAIContent = '';
        }
    }
    
    renderMarkdownContent(isFinal = false) {
        if (!this.currentAIMessage) return;
        
        const renderedContent = MarkdownRenderer.renderMarkdown(
            this.currentAIContent,
            isFinal,
            (t) => this.escapeHtml(t)
        );
        
        this.currentAIMessage.innerHTML = renderedContent + 
            (!isFinal ? '<span class="ai-cursor">▋</span>' : '');
        
        if (isFinal) {
            MarkdownRenderer.renderMermaidDiagrams(
                this.currentAIMessage,
                (t) => this.escapeHtml(t)
            );
        }
    }
    
    showError(message) {
        UIController.showError(message, this.chatMessages, (t) => this.escapeHtml(t));
    }
    
    clearChat() {
        UIController.clearChat(this.chatMessages);
        this.currentAIMessage = null;
        this.thinkingFlow.clear();
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
        UIController.hideWelcomeMessage(this.chatMessages);
    }
    
    updateConnectionStatus(status) {
        UIController.updateConnectionStatus(status, this.connectionStatus, this.connectionText);
        
        // 更新 Doctor Review 模式的按钮状态
        if (typeof ModelManager !== 'undefined') {
            ModelManager.updateStartReviewButton(status === 'online');
        }
    }

    setConnectionExtra(text) {
        UIController.setConnectionExtra(text, this.connectionText);
    }
    
    updateCharCount() {
        UIController.updateCharCount(this.messageInput.value, this.charCount);
    }
    
    adjustInputHeight() {
        UIController.adjustInputHeight(this.messageInput);
    }
    
    updateSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;
        const hasAttachments = (this.pendingAttachments && this.pendingAttachments.length > 0);
        const isConnected = this.wsManager.isConnected();
        
        UIController.updateSendButton(
            hasText,
            hasAttachments,
            isConnected,
            this.isStreaming,
            this.sendBtn
        );
    }
    
    scrollToBottom() {
        UIController.scrollToBottom(this.chatMessages);
    }

    smartScrollToBottom(force = false) {
        UIController.smartScrollToBottom(this.chatMessages, force);
    }

    isUserViewingContent() {
        return UIController.isUserViewingContent(this.chatMessages);
    }
    
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
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
