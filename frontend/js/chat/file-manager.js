// file-manager.js - 文件上传和附件管理模块
(function(global) {
    const FileManager = {
        /**
         * 上传文件并获取链接
         * @param {File[]} files - 文件列表
         * @param {object} configManager - 配置管理器
         * @returns {Promise<Array>} 上传结果
         */
        async uploadFilesAndGetLinks(files, configManager) {
            if (!configManager || !configManager.isLoaded) {
                await configManager.loadConfig();
            }
            const apiUrl = configManager.getFullApiUrl('/api/upload');
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
                const fullUrl = this.makeFullApiUrl(urlPath, configManager);
                
                // 若是图片，生成 dataURL 以便直接传给具备视觉能力的模型
                let dataUrl = null;
                const isImage = !!(f && f.type && f.type.startsWith('image/'));
                if (isImage) {
                    try {
                        dataUrl = await this.readFileAsDataURL(f);
                    } catch {}
                }
                
                results.push({ 
                    filename: json.data.filename || f.name, 
                    urlPath, 
                    fullUrl, 
                    isImage, 
                    dataUrl 
                });
            }
            
            return results;
        },

        /**
         * 读取文件为 DataURL
         * @param {File} file - 文件
         * @returns {Promise<string>} DataURL
         */
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
        },

        /**
         * 生成完整的 API URL
         * @param {string} path - 路径
         * @param {object} configManager - 配置管理器
         * @returns {string} 完整 URL
         */
        makeFullApiUrl(path, configManager) {
            try {
                const base = configManager.getApiBaseUrl();
                if (!path.startsWith('/')) return base + '/' + path;
                return base + path;
            } catch (e) {
                return path;
            }
        },

        /**
         * 添加附件标签
         * @param {Array} items - 附件项
         * @param {HTMLElement} container - 容器元素
         * @param {Array} pendingAttachments - 待发送附件列表
         * @param {Function} updateCallback - 更新回调
         * @param {Function} downloadCallback - 下载回调
         */
        addAttachmentChips(items, container, pendingAttachments, updateCallback, downloadCallback) {
            if (!container) return;
            
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
                    const index = pendingAttachments.indexOf(item);
                    if (index > -1) {
                        pendingAttachments.splice(index, 1);
                    }
                    if (updateCallback) updateCallback();
                });
                
                chip.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (downloadCallback) downloadCallback(item);
                });
                
                chip.appendChild(del);
                container.appendChild(chip);
            });
        },

        /**
         * 清空附件标签
         * @param {HTMLElement} container - 容器元素
         */
        clearAttachmentChips(container) {
            if (!container) return;
            container.innerHTML = '';
        },

        /**
         * 组合用户消息显示（包含附件）
         * @param {string} text - 文本
         * @param {Array} attachments - 附件列表
         * @param {Function} escapeHtml - HTML 转义函数
         * @returns {string} 组合后的 HTML
         */
        composeUserDisplayMessage(text, attachments, escapeHtml) {
            const base = (text || '').trim();
            if (!attachments || attachments.length === 0) return base;
            
            const list = attachments.map(a => {
                const safeName = escapeHtml(a.filename);
                const safeUrl = escapeHtml(a.fullUrl);
                if (a.isImage) {
                    const thumb = escapeHtml(a.dataUrl || a.fullUrl);
                    return `• ${safeName}<br><img src="${thumb}" alt="${safeName}" style="max-width:180px;max-height:180px;border-radius:6px;border:1px solid #e2e8f0;margin:4px 0;"/>`;
                }
                return `• <a href="${safeUrl}" download target="_blank" rel="noopener noreferrer">${safeName}</a>`;
            }).join('<br>');
            
            const html = `${escapeHtml(base)}${base ? '<br><br>' : ''}<strong>Attachments:</strong><br>${list}`;
            return html;
        },

        /**
         * 下载附件
         * @param {object} item - 附件项
         */
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
    };

    global.FileManager = FileManager;
})(window);

