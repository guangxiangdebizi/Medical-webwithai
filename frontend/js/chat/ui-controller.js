// ui-controller.js - UI 状态控制模块
(function(global) {
    const UIController = {
        /**
         * 更新连接状态
         * @param {string} status - 状态: online/offline/connecting
         * @param {HTMLElement} statusDot - 状态指示点
         * @param {HTMLElement} statusText - 状态文本
         */
        updateConnectionStatus(status, statusDot, statusText) {
            if (statusDot) {
                statusDot.className = `status-dot ${status}`;
            }
            
            if (statusText) {
                switch (status) {
                    case 'online':
                        statusText.textContent = 'Online';
                        break;
                    case 'offline':
                        statusText.textContent = 'Offline';
                        break;
                    case 'connecting':
                        statusText.textContent = 'Connecting';
                        break;
                }
            }
        },

        /**
         * 设置连接额外信息
         * @param {string} text - 额外信息
         * @param {HTMLElement} statusText - 状态文本元素
         */
        setConnectionExtra(text, statusText) {
            try {
                if (!statusText) return;
                const base = statusText.textContent.split(' | ')[0];
                if (text) {
                    statusText.textContent = `${base} | ${text}`;
                } else {
                    statusText.textContent = base;
                }
            } catch {}
        },

        /**
         * 更新字符计数
         * @param {string} value - 输入值
         * @param {HTMLElement} charCountEl - 字符计数元素
         */
        updateCharCount(value, charCountEl) {
            if (!charCountEl) return;
            
            const count = value.length;
            charCountEl.textContent = count;
            
            if (count > 1800) {
                charCountEl.style.color = '#e53e3e';
            } else if (count > 1500) {
                charCountEl.style.color = '#ed8936';
            } else {
                charCountEl.style.color = '#a0aec0';
            }
        },

        /**
         * 调整输入框高度
         * @param {HTMLTextAreaElement} textarea - 输入框
         */
        adjustInputHeight(textarea) {
            if (!textarea) return;
            
            // 保存滚动位置
            const scrollTop = textarea.scrollTop;
            
            // 重置高度
            textarea.style.height = 'auto';
            
            // 设置新高度
            const newHeight = Math.min(textarea.scrollHeight, 150);
            textarea.style.height = newHeight + 'px';
            
            // 恢复滚动位置
            textarea.scrollTop = scrollTop;
            
            // 如果内容超出了可视区域，滚动到底部
            if (textarea.scrollHeight > newHeight) {
                textarea.scrollTop = textarea.scrollHeight;
            }
        },

        /**
         * 更新发送按钮状态
         * @param {boolean} hasText - 是否有文本
         * @param {boolean} hasAttachments - 是否有附件
         * @param {boolean} isConnected - 是否已连接
         * @param {boolean} isStreaming - 是否正在生成
         * @param {HTMLElement} sendBtn - 发送按钮
         */
        updateSendButton(hasText, hasAttachments, isConnected, isStreaming, sendBtn) {
            if (!sendBtn) return;
            
            if (isStreaming) {
                sendBtn.innerHTML = '⏸️';
                sendBtn.disabled = !isConnected;
            } else {
                sendBtn.innerHTML = '📤';
                sendBtn.disabled = (!hasText && !hasAttachments) || !isConnected;
            }
        },

        /**
         * 滚动到底部
         * @param {HTMLElement} container - 容器元素
         */
        scrollToBottom(container) {
            if (!container) return;
            
            // 使用 requestAnimationFrame 确保 DOM 更新完成后再滚动
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        },

        /**
         * 智能滚动到底部（只有在用户接近底部时才滚动）
         * @param {HTMLElement} container - 容器元素
         * @param {boolean} force - 是否强制滚动
         */
        smartScrollToBottom(container, force = false) {
            if (!container) return;

            const threshold = 100; // 底部 100px 范围内认为用户在底部
            const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

            // 如果强制滚动或用户在底部附近，才滚动
            if (force || distanceFromBottom <= threshold) {
                this.scrollToBottom(container);
            }
        },

        /**
         * 检查用户是否正在主动查看内容
         * @param {HTMLElement} container - 容器元素
         * @returns {boolean} 是否正在查看
         */
        isUserViewingContent(container) {
            if (!container) return false;

            const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;

            // 如果用户距离底部超过 200px，认为正在查看历史内容
            return distanceFromBottom > 200;
        },

        /**
         * 隐藏欢迎消息
         * @param {HTMLElement} chatMessages - 聊天消息容器
         */
        hideWelcomeMessage(chatMessages) {
            if (!chatMessages) return;
            
            const welcomeMessage = chatMessages.querySelector('.welcome-message');
            if (welcomeMessage) {
                welcomeMessage.style.display = 'none';
            }
        },

        /**
         * 清空聊天界面
         * @param {HTMLElement} chatMessages - 聊天消息容器
         */
        clearChat(chatMessages) {
            if (!chatMessages) return;
            
            // 清空消息区域，保留欢迎消息
            const welcomeMessage = chatMessages.querySelector('.welcome-message');
            chatMessages.innerHTML = '';
            
            if (welcomeMessage) {
                chatMessages.appendChild(welcomeMessage);
                welcomeMessage.style.display = 'block';
            }
        },

        /**
         * 显示错误消息
         * @param {string} message - 错误消息
         * @param {HTMLElement} chatMessages - 聊天消息容器
         * @param {Function} escapeHtml - HTML 转义函数
         */
        showError(message, chatMessages, escapeHtml) {
            if (!chatMessages) return;
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'message ai';
            errorDiv.innerHTML = `
                <div class="message-bubble" style="background: rgba(245, 101, 101, 0.1); border-color: rgba(245, 101, 101, 0.3); color: #e53e3e;">
                    ❌ ${escapeHtml(message)}
                </div>
            `;

            chatMessages.appendChild(errorDiv);
            this.smartScrollToBottom(chatMessages, true);
        },

        /**
         * 插入文本到光标位置
         * @param {HTMLTextAreaElement} textarea - 输入框
         * @param {string} text - 要插入的文本
         */
        insertTextAtCursor(textarea, text) {
            if (!textarea) return;
            
            const start = textarea.selectionStart ?? textarea.value.length;
            const end = textarea.selectionEnd ?? textarea.value.length;
            const before = textarea.value.substring(0, start);
            const after = textarea.value.substring(end);
            const needsSpace = before && !before.endsWith(' ');
            const insert = (needsSpace ? ' ' : '') + text;
            textarea.value = before + insert + after;
            const caret = (before + insert).length;
            try { textarea.setSelectionRange(caret, caret); } catch {}
            try { textarea.focus(); } catch {}
        }
    };

    global.UIController = UIController;
})(window);

