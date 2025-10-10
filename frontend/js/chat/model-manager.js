// model-manager.js - Model 切换和管理模块
(function(global) {
    const ModelManager = {
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

                let selected = localStorage.getItem('mcp_selected_model') || def;
                // 如果本地无记录，写入一次，保证首连就有 model
                if (!localStorage.getItem('mcp_selected_model')) {
                    localStorage.setItem('mcp_selected_model', selected);
                }
                
                this.updateModelButtonLabel(models, selected, dropdownBtn);

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
                                this.updateModelButtonLabel(models, m.id, dropdownBtn);
                                dropdown.style.display = 'none';
                                
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

