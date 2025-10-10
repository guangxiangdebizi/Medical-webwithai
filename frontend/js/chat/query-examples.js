// query-examples.js - 查询示例模块
(function(global) {
    const QueryExamples = {
        examples: [],
        container: null,

        /**
         * 初始化查询示例
         * @param {object} app - ChatApp 实例
         */
        async init(app) {
            this.app = app;
            await this.loadExamples();
            this.render();
        },

        /**
         * 从后端加载示例
         */
        async loadExamples() {
            try {
                const apiUrl = window.configManager.getFullApiUrl('/api/query-examples?count=3');
                const response = await fetch(apiUrl, { cache: 'no-store' });
                const result = await response.json();
                
                if (result.success && result.data) {
                    this.examples = result.data;
                }
            } catch (error) {
                console.warn('Failed to load query examples:', error);
                // 如果加载失败，使用默认示例
                this.examples = this.getDefaultExamples();
            }
        },

        /**
         * 获取默认示例（当 API 失败时使用）
         */
        getDefaultExamples() {
            return [
                {
                    id: 1,
                    text: "Query demographic information for all patients over 65 years old",
                    icon: "👥",
                    category: "demographics"
                },
                {
                    id: 2,
                    text: "Show list of serious adverse events (SAE) from the past week",
                    icon: "⚠️",
                    category: "safety"
                },
                {
                    id: 3,
                    text: "Generate enrollment trend chart for patient recruitment",
                    icon: "📈",
                    category: "enrollment"
                }
            ];
        },

        /**
         * 渲染示例卡片
         */
        render() {
            if (!this.app || !this.app.chatMessages) return;
            
            // 查找欢迎消息
            const welcomeMessage = this.app.chatMessages.querySelector('.welcome-message');
            if (!welcomeMessage) return;
            
            // 创建示例容器
            this.container = document.createElement('div');
            this.container.className = 'query-examples-container';
            this.container.innerHTML = `
                <div class="query-examples-header">
                    <span class="examples-icon">💡</span>
                    <span class="examples-title">Try asking:</span>
                </div>
                <div class="query-examples-list"></div>
            `;
            
            // 添加样式
            this.addStyles();
            
            // 渲染示例卡片
            const list = this.container.querySelector('.query-examples-list');
            this.examples.forEach(example => {
                const card = this.createExampleCard(example);
                list.appendChild(card);
            });
            
            // 插入到欢迎消息之后
            welcomeMessage.appendChild(this.container);
        },

        /**
         * 创建示例卡片
         */
        createExampleCard(example) {
            const card = document.createElement('div');
            card.className = 'example-card';
            card.innerHTML = `
                <span class="example-icon">${example.icon || '📝'}</span>
                <span class="example-text">${this.escapeHtml(example.text)}</span>
                <span class="example-arrow">→</span>
            `;
            
            // 点击事件
            card.addEventListener('click', () => {
                this.selectExample(example.text);
            });
            
            return card;
        },

        /**
         * 选择示例（填入输入框）
         */
        selectExample(text) {
            if (!this.app || !this.app.messageInput) return;
            
            // 填入输入框
            this.app.messageInput.value = text;
            
            // 更新 UI
            this.app.updateCharCount();
            this.app.adjustInputHeight();
            this.app.updateSendButton();
            
            // 聚焦输入框
            try {
                this.app.messageInput.focus();
                // 将光标移到末尾
                this.app.messageInput.setSelectionRange(text.length, text.length);
            } catch (e) {}
            
            // 添加视觉反馈
            this.addFeedback();
        },

        /**
         * 添加视觉反馈
         */
        addFeedback() {
            if (!this.app.messageInput) return;
            
            // 输入框闪烁效果
            this.app.messageInput.classList.add('example-filled');
            setTimeout(() => {
                this.app.messageInput.classList.remove('example-filled');
            }, 600);
        },

        /**
         * 隐藏示例（用户发送消息后）
         */
        hide() {
            if (this.container) {
                this.container.style.display = 'none';
            }
        },

        /**
         * 显示示例
         */
        show() {
            if (this.container) {
                this.container.style.display = 'block';
            }
        },

        /**
         * 重新加载示例
         */
        async refresh() {
            await this.loadExamples();
            if (this.container) {
                const list = this.container.querySelector('.query-examples-list');
                if (list) {
                    list.innerHTML = '';
                    this.examples.forEach(example => {
                        const card = this.createExampleCard(example);
                        list.appendChild(card);
                    });
                }
            }
        },

        /**
         * HTML 转义
         */
        escapeHtml(text) {
            if (text === null || text === undefined) return '';
            return text.toString()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },

        /**
         * 添加样式
         */
        addStyles() {
            if (document.getElementById('query-examples-styles')) {
                return; // 样式已存在
            }
            
            const styles = document.createElement('style');
            styles.id = 'query-examples-styles';
            styles.textContent = `
                .query-examples-container {
                    margin-top: 2rem;
                    animation: fadeInUp 0.6s ease-out;
                }
                
                @keyframes fadeInUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .query-examples-header {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    margin-bottom: 1rem;
                    font-size: 1rem;
                    color: #4a5568;
                }
                
                .examples-icon {
                    font-size: 1.2rem;
                }
                
                .examples-title {
                    font-weight: 600;
                }
                
                .query-examples-list {
                    display: flex;
                    flex-direction: column;
                    gap: 0.75rem;
                }
                
                .example-card {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    padding: 1rem 1.25rem;
                    background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                
                .example-card:hover {
                    background: linear-gradient(135deg, #667eea25 0%, #764ba225 100%);
                    border-color: #667eea;
                    transform: translateX(4px);
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
                }
                
                .example-icon {
                    font-size: 1.5rem;
                    flex-shrink: 0;
                }
                
                .example-text {
                    flex: 1;
                    color: #2d3748;
                    font-size: 0.95rem;
                    line-height: 1.5;
                }
                
                .example-arrow {
                    font-size: 1.2rem;
                    color: #667eea;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }
                
                .example-card:hover .example-arrow {
                    opacity: 1;
                }
                
                /* 输入框填充动画 */
                @keyframes inputFill {
                    0%, 100% {
                        background-color: transparent;
                    }
                    50% {
                        background-color: #667eea15;
                    }
                }
                
                .example-filled {
                    animation: inputFill 0.6s ease;
                }
                
                /* 移动端适配 */
                @media (max-width: 768px) {
                    .example-card {
                        padding: 0.875rem 1rem;
                    }
                    
                    .example-text {
                        font-size: 0.9rem;
                    }
                    
                    .example-icon {
                        font-size: 1.3rem;
                    }
                }
            `;
            
            document.head.appendChild(styles);
        }
    };

    global.QueryExamples = QueryExamples;
})(window);

