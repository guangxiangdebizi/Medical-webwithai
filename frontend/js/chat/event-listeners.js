// event-listeners.js - 事件监听器设置模块
(function(global) {
    const EventListeners = {
        /**
         * 设置所有事件监听器
         * @param {object} app - ChatApp 实例
         */
        setupAll(app) {
            this.setupSendButton(app);
            this.setupInputEvents(app);
            this.setupChatButtons(app);
            this.setupShareButton(app);
            this.setupSidebar(app);
            this.setupModelDropdown(app);
            this.setupFileUpload(app);
            this.setupPasteImage(app);
            this.setupPageUnload(app);
            this.setupDoctorReview(app);
        },

        /**
         * 设置发送按钮
         */
        setupSendButton(app) {
            if (!app.sendBtn) return;
            
            app.sendBtn.addEventListener('click', () => {
                if (app.isStreaming) {
                    // 发送暂停指令
                    app.wsManager.send({ type: 'pause' });
                    // 立即将按钮恢复为 Send
                    app.isStreaming = false;
                    app.updateSendButton();
                    return;
                }
                app.sendMessage();
            });
        },

        /**
         * 设置输入框事件
         */
        setupInputEvents(app) {
            if (!app.messageInput) return;
            
            // 输入事件
            app.messageInput.addEventListener('input', () => {
                app.updateCharCount();
                app.adjustInputHeight();
                app.updateSendButton();
            });
            
            // 键盘事件
            app.messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    if (e.shiftKey) {
                        // Shift + Enter 换行
                        return;
                    } else {
                        // Enter 发送
                        e.preventDefault();
                        app.sendMessage();
                    }
                }
            });
        },

        /**
         * 设置聊天按钮
         */
        setupChatButtons(app) {
            // 清空聊天按钮（兼容旧按钮）
            if (app.clearChatBtn) {
                app.clearChatBtn.addEventListener('click', () => {
                    app.clearChat();
                    app.clearServerHistory();
                });
            }
            
            // 新建对话按钮
            if (app.startNewChatBtn) {
                app.startNewChatBtn.addEventListener('click', () => {
                    // 刷新页面，确保彻底重置连接与状态
                    try { 
                        window.location.reload(); 
                    } catch (e) { 
                        try { 
                            window.location.href = window.location.href; 
                        } catch (_) {} 
                    }
                });
            }
        },

        /**
         * 设置分享按钮
         */
        setupShareButton(app) {
            // 初始化分享模块
            app.shareModule = new ShareModule(app);
        },

        /**
         * 设置侧栏
         */
        setupSidebar(app) {
            // 侧栏开关
            if (app.toggleSidebarBtn) {
                app.toggleSidebarBtn.addEventListener('click', () => {
                    const sidebar = document.getElementById('historySidebar');
                    if (!sidebar) return;
                    const isOpen = sidebar.classList.toggle('open');
                    
                    // 推拉主容器
                    const appContainer = document.querySelector('.app-container');
                    if (appContainer) {
                        appContainer.classList.toggle('sidebar-open', isOpen);
                    }
                    app.toggleSidebarBtn.textContent = isOpen ? 'Hide' : 'Show';
                });
            }
            
            if (app.openSidebarBtn) {
                app.openSidebarBtn.addEventListener('click', async () => {
                    const sidebar = document.getElementById('historySidebar');
                    if (!sidebar) return;
                    const isOpen = sidebar.classList.toggle('open');
                    
                    // 推拉主容器
                    const appContainer = document.querySelector('.app-container');
                    if (appContainer) {
                        appContainer.classList.toggle('sidebar-open', isOpen);
                    }
                    
                    // 打开时刷新；关闭时不动
                    if (isOpen) {
                        await app.loadThreadsByMsidFromUrl();
                    }
                    
                    // 按钮文案提示
                    app.openSidebarBtn.textContent = isOpen ? 'History (Open)' : 'History';
                });
            }
        },

        /**
         * 设置 Model 下拉菜单
         */
        setupModelDropdown(app) {
            if (!app.modelDropdownBtn) return;
            
            app.modelDropdownBtn.addEventListener('click', () => {
                if (!app.modelDropdown) return;
                const isVisible = app.modelDropdown.style.display === 'block';
                app.modelDropdown.style.display = isVisible ? 'none' : 'block';
            });
            
            // 点击页面其他地方关闭
            document.addEventListener('click', (e) => {
                if (!app.modelDropdownBtn.contains(e.target) && 
                    !app.modelDropdown.contains(e.target)) {
                    app.modelDropdown.style.display = 'none';
                }
            });
        },

        /**
         * 设置文件上传
         */
        setupFileUpload(app) {
            if (!app.uploadBtn || !app.fileInput) return;
            
            app.uploadBtn.addEventListener('click', () => {
                try { app.fileInput.click(); } catch {}
            });
            
            app.fileInput.addEventListener('change', async (e) => {
                const files = Array.from(e.target.files || []);
                if (!files.length) return;
                
                try {
                    const items = await app.uploadFilesAndGetLinks(files);
                    app.addAttachmentChips(items);
                    app.pendingAttachments.push(...items);
                    app.updateSendButton();
                } catch (err) {
                    console.warn('文件上传失败', err);
                    app.showError('File upload failed');
                } finally {
                    try { app.fileInput.value = ''; } catch {}
                }
            });
        },

        /**
         * 设置粘贴图片支持
         */
        setupPasteImage(app) {
            if (!app.messageInput) return;
            
            app.messageInput.addEventListener('paste', async (event) => {
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
                    
                    const items = await app.uploadFilesAndGetLinks(imageItems);
                    app.addAttachmentChips(items);
                    app.pendingAttachments.push(...items);
                    app.updateSendButton();
                } catch (e) {
                    console.warn('处理粘贴图片失败', e);
                }
            });
        },

        /**
         * 设置页面卸载事件
         */
        setupPageUnload(app) {
            window.addEventListener('beforeunload', () => {
                app.wsManager.close();
            });
        },
        
        /**
         * 设置 Doctor Review 模式的事件监听
         */
        setupDoctorReview(app) {
            const startReviewBtn = document.getElementById('startReviewBtn');
            const newReviewBtn = document.getElementById('newReviewBtn');
            const reviewWelcome = document.getElementById('reviewWelcome');
            const reviewResults = document.getElementById('reviewResults');
            const reviewOutput = document.getElementById('reviewOutput');
            
            if (startReviewBtn) {
                startReviewBtn.addEventListener('click', async () => {
                    if (!app.wsManager.isConnected()) {
                        app.showError('Not connected to AI service');
                        return;
                    }
                    
                    // 禁用按钮防止重复点击
                    startReviewBtn.disabled = true;
                    startReviewBtn.innerHTML = `
                        <span class="btn-icon" style="animation: spin 1s linear infinite;">⏳</span>
                        <span class="btn-text">Analyzing...</span>
                    `;
                    
                    // 切换到结果面板
                    if (reviewWelcome) reviewWelcome.style.display = 'none';
                    if (reviewResults) reviewResults.style.display = 'flex';
                    
                    // 清空之前的输出
                    if (reviewOutput) {
                        reviewOutput.innerHTML = `
                            <div class="review-progress">
                                <div class="review-progress-spinner"></div>
                                <div class="review-progress-text">Starting comprehensive document review...</div>
                            </div>
                        `;
                    }
                    
                    // 设置 app 的输出目标为 reviewOutput
                    app.reviewMode = true;
                    app.reviewOutput = reviewOutput;
                    
                    // 发送自动审核触发消息
                    const payload = {
                        type: 'user_msg',
                        content: '[AUTO_REVIEW_START]'
                    };
                    
                    // 创建思维流
                    app.thinkingFlow.createThinkingFlow();
                    
                    const success = app.wsManager.send(payload);
                    
                    if (!success) {
                        app.showError('Failed to start review, please check connection');
                        startReviewBtn.disabled = false;
                        startReviewBtn.innerHTML = `
                            <span class="btn-icon">🚀</span>
                            <span class="btn-text">Start Review</span>
                        `;
                    }
                });
            }
            
            // 新建审核按钮
            if (newReviewBtn) {
                newReviewBtn.addEventListener('click', () => {
                    // 重置 UI
                    if (reviewWelcome) reviewWelcome.style.display = 'flex';
                    if (reviewResults) reviewResults.style.display = 'none';
                    if (reviewOutput) reviewOutput.innerHTML = '';
                    
                    // 重置按钮状态
                    if (startReviewBtn) {
                        startReviewBtn.disabled = false;
                        startReviewBtn.innerHTML = `
                            <span class="btn-icon">🚀</span>
                            <span class="btn-text">Start Review</span>
                        `;
                    }
                    
                    // 退出审核模式
                    app.reviewMode = false;
                    app.reviewOutput = null;
                    
                    // 刷新页面以重置状态
                    try { 
                        window.location.reload(); 
                    } catch (e) {}
                });
            }
        }
    };

    global.EventListeners = EventListeners;
})(window);

