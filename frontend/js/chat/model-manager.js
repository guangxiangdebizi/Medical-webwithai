// model-manager.js - Model 切换和管理模块
(function(global) {
    // Doctor Agent 模型 ID 列表
    const DOCTOR_MODELS = ['DOCTOR_M', 'DOCTOR_S'];
    
    const ModelManager = {
        // 存储当前选中的模型信息
        currentModel: null,
        models: [],
        
        /**
         * 检查是否为 Doctor 模型
         */
        isDoctorModel(modelId) {
            return DOCTOR_MODELS.includes(modelId?.toUpperCase());
        },
        
        /**
         * 获取 Doctor 模型类型 ('doctor-m' 或 'doctor-s')
         */
        getDoctorType(modelId) {
            const id = modelId?.toUpperCase();
            if (id === 'DOCTOR_M') return 'doctor-m';
            if (id === 'DOCTOR_S') return 'doctor-s';
            return null;
        },
        
        /**
         * 切换 UI 模式（聊天模式 vs 审核模式）
         */
        switchUIMode(modelId) {
            console.log('🔄 switchUIMode called with:', modelId);
            
            const chatContainer = document.getElementById('chatContainer');
            const chatInputContainer = document.getElementById('chatInputContainer');
            const reviewContainer = document.getElementById('reviewContainer');
            
            console.log('📦 Elements found:', {
                chatContainer: !!chatContainer,
                chatInputContainer: !!chatInputContainer,
                reviewContainer: !!reviewContainer
            });
            
            if (!chatContainer || !reviewContainer) {
                console.warn('⚠️ Required containers not found!');
                return;
            }
            
            const isDoctor = this.isDoctorModel(modelId);
            const doctorType = this.getDoctorType(modelId);
            
            console.log('🩺 Doctor check:', { modelId, isDoctor, doctorType });
            
            if (isDoctor) {
                console.log('✅ Switching to REVIEW MODE');
                // 切换到审核模式
                chatContainer.style.display = 'none';
                if (chatInputContainer) chatInputContainer.style.display = 'none';
                reviewContainer.style.display = 'flex';
                
                // 设置主题类
                reviewContainer.className = 'review-container';
                if (doctorType) {
                    reviewContainer.classList.add(doctorType);
                }
                
                // 更新 Agent 信息
                this.updateDoctorAgentInfo(modelId);
                
                // 显示欢迎面板，隐藏结果面板
                const reviewWelcome = document.getElementById('reviewWelcome');
                const reviewResults = document.getElementById('reviewResults');
                if (reviewWelcome) reviewWelcome.style.display = 'flex';
                if (reviewResults) reviewResults.style.display = 'none';
                
            } else {
                // 切换到聊天模式
                console.log('💬 Switching to CHAT MODE');
                chatContainer.style.display = 'flex';
                if (chatInputContainer) chatInputContainer.style.display = 'block';
                reviewContainer.style.display = 'none';
            }
        },
        
        /**
         * 更新 Doctor Agent 显示信息
         */
        updateDoctorAgentInfo(modelId) {
            const agentIcon = document.getElementById('reviewAgentIcon');
            const agentTitle = document.getElementById('reviewAgentTitle');
            const agentDesc = document.getElementById('reviewAgentDesc');
            const resultIcon = document.getElementById('reviewResultIcon');
            const resultTitle = document.getElementById('reviewResultTitle');
            const cap1 = document.getElementById('capabilityCard1');
            const cap2 = document.getElementById('capabilityCard2');
            const cap3 = document.getElementById('capabilityCard3');
            
            const id = modelId?.toUpperCase();
            
            if (id === 'DOCTOR_M') {
                // Dr.M - 医学洞察专家
                if (agentIcon) agentIcon.textContent = '🟠';
                if (agentTitle) agentTitle.textContent = 'Dr.M Medical Insight';
                if (agentDesc) agentDesc.textContent = 'AI-powered clinical trial safety analysis and medical interpretation';
                if (resultIcon) resultIcon.textContent = '🟠';
                if (resultTitle) resultTitle.textContent = 'Medical Insight Analysis';
                
                // 更新能力卡片
                if (cap1) {
                    cap1.innerHTML = `
                        <div class="capability-icon">⚠️</div>
                        <h3>Safety Signal Detection</h3>
                        <p>Identify potential safety signals from adverse event data</p>
                    `;
                }
                if (cap2) {
                    cap2.innerHTML = `
                        <div class="capability-icon">💊</div>
                        <h3>Medical Interpretation</h3>
                        <p>Provide clinical context and explain medical significance</p>
                    `;
                }
                if (cap3) {
                    cap3.innerHTML = `
                        <div class="capability-icon">📋</div>
                        <h3>Risk Assessment</h3>
                        <p>Evaluate benefit-risk balance and identify high-risk subgroups</p>
                    `;
                }
                
            } else if (id === 'DOCTOR_S') {
                // Dr.S - 统计精度专家
                if (agentIcon) agentIcon.textContent = '🔵';
                if (agentTitle) agentTitle.textContent = 'Dr.S Statistical Accuracy';
                if (agentDesc) agentDesc.textContent = 'AI-powered TFL quality control and statistical validation';
                if (resultIcon) resultIcon.textContent = '🔵';
                if (resultTitle) resultTitle.textContent = 'Statistical Audit Results';
                
                // 更新能力卡片
                if (cap1) {
                    cap1.innerHTML = `
                        <div class="capability-icon">🔢</div>
                        <h3>Statistical Accuracy</h3>
                        <p>Verify calculations, percentages, p-values and totals</p>
                    `;
                }
                if (cap2) {
                    cap2.innerHTML = `
                        <div class="capability-icon">🔗</div>
                        <h3>Data Consistency</h3>
                        <p>Cross-reference numbers and validate across tables</p>
                    `;
                }
                if (cap3) {
                    cap3.innerHTML = `
                        <div class="capability-icon">📜</div>
                        <h3>Regulatory Compliance</h3>
                        <p>Check ICH E3 guidelines and formatting standards</p>
                    `;
                }
            }
        },
        
        /**
         * 更新 Start Review 按钮状态
         */
        updateStartReviewButton(enabled) {
            const btn = document.getElementById('startReviewBtn');
            const hint = document.getElementById('reviewHint');
            
            if (btn) {
                btn.disabled = !enabled;
            }
            if (hint) {
                if (enabled) {
                    hint.textContent = 'Click to start automated document review';
                    hint.classList.add('ready');
                } else {
                    hint.textContent = 'Connecting to AI service...';
                    hint.classList.remove('ready');
                }
            }
        },
        
        /**
         * 加载 Model 列表并渲染下拉菜单
         * @param {object} configManager - 配置管理器
         * @param {HTMLElement} dropdownBtn - 下拉按钮
         * @param {HTMLElement} dropdown - 下拉菜单
         * @param {object} wsManager - WebSocket 管理器
         * @param {Function} connectCallback - 连接回调
         * @returns {Promise<void>}
         */
        async loadModelsAndRenderDropdown(configManager, dropdownBtn, dropdown, wsManager, connectCallback) {
            try {
                const apiUrl = configManager.getFullApiUrl('/api/models');
                const res = await fetch(apiUrl, { cache: 'no-store' });
                const json = await res.json();
                
                if (!json.success) throw new Error('加载 Model 列表失败');
                
                const { models, default: def } = json.data || { models: [], default: 'default' };
                this.models = models;

                let selected = localStorage.getItem('mcp_selected_model') || def;
                // 如果本地无记录，写入一次，保证首连就有 model
                if (!localStorage.getItem('mcp_selected_model')) {
                    localStorage.setItem('mcp_selected_model', selected);
                }
                
                this.currentModel = selected;
                this.updateModelButtonLabel(models, selected, dropdownBtn);
                
                // 根据选中的模型切换 UI
                this.switchUIMode(selected);

                // 渲染菜单
                if (dropdown) {
                    dropdown.innerHTML = '';
                    models.forEach(m => {
                        const item = document.createElement('div');
                        item.className = 'dropdown-item';
                        item.textContent = `${m.label || m.id} (${m.model || ''})`;
                        item.addEventListener('click', async () => {
                            try {
                                // 通过 WS 指令切换模型，避免断开重连
                                localStorage.setItem('mcp_selected_model', m.id);
                                this.currentModel = m.id;
                                this.updateModelButtonLabel(models, m.id, dropdownBtn);
                                dropdown.style.display = 'none';
                                
                                // 切换 UI 模式
                                this.switchUIMode(m.id);
                                
                                if (wsManager && wsManager.isConnected()) {
                                    const ok = wsManager.send({ type: 'switch_model', model: m.id });
                                    if (!ok) throw new Error('WS not connected');
                                } else {
                                    // 若尚未连接，保留旧逻辑：初始化时会带上 model 参数
                                    if (connectCallback) await connectCallback();
                                }
                            } catch (e) {
                                console.warn('切换模型失败，回退为重连方式', e);
                                try { wsManager.close(); } catch {}
                                wsManager.isInitialized = false;
                                if (connectCallback) await connectCallback();
                            }
                        });
                        dropdown.appendChild(item);
                    });
                }
            } catch (e) {
                console.warn('⚠️ 无法加载 Model 列表:', e);
            }
        },

        /**
         * 更新 Model 按钮标签
         * @param {Array} models - Model 列表
         * @param {string} selectedId - 选中的 Model ID
         * @param {HTMLElement} button - 按钮元素
         */
        updateModelButtonLabel(models, selectedId, button) {
            try {
                const picked = (models || []).find(m => m.id === selectedId);
                const label = picked ? (picked.label || picked.id) : selectedId;
                if (button) {
                    button.textContent = `Model：${label} ▾`;
                }
            } catch {}
        }
    };

    global.ModelManager = ModelManager;
})(window);

