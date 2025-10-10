// markdown-renderer.js - Markdown 和 Mermaid 渲染模块
(function(global) {
    const MarkdownRenderer = {
        mermaidInitialized: false,
        mermaidIdCounter: 0,

        /**
         * 渲染 Markdown 内容
         * @param {string} content - 要渲染的内容
         * @param {boolean} isFinal - 是否是最终渲染
         * @param {function} escapeHtml - HTML 转义函数
         * @returns {string} 渲染后的 HTML
         */
        renderMarkdown(content, isFinal = false, escapeHtml) {
            if (typeof marked === 'undefined') {
                return escapeHtml(content);
            }

            try {
                if (isFinal) {
                    // 最终渲染，直接处理所有内容
                    return marked.parse(content);
                } else {
                    // 实时渲染，需要智能处理不完整的 markdown
                    return this.renderPartialMarkdown(content, escapeHtml);
                }
            } catch (error) {
                console.warn('Markdown 渲染错误:', error);
                return escapeHtml(content);
            }
        },

        /**
         * 渲染部分 markdown 内容（处理不完整的语法）
         * @param {string} content - 内容
         * @param {function} escapeHtml - HTML 转义函数
         * @returns {string} 渲染后的 HTML
         */
        renderPartialMarkdown(content, escapeHtml) {
            // 检测可能不完整的 markdown 模式
            const patterns = [
                { regex: /```[\s\S]*?```/g, type: 'codeblock' },
                { regex: /`[^`\n]*`/g, type: 'code' },
                { regex: /\*\*[^*\n]*\*\*/g, type: 'bold' },
                { regex: /\*[^*\n]*\*/g, type: 'italic' },
                { regex: /^#{1,6}\s+.*/gm, type: 'heading' },
                { regex: /^\*.+$/gm, type: 'list' },
                { regex: /^\d+\..+$/gm, type: 'orderedlist' },
                { regex: /^>.+$/gm, type: 'quote' }
            ];

            let lastCompletePos = 0;

            // 找到最后一个完整的 markdown 元素位置
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
                // 分割内容：完整部分用 markdown 渲染，不完整部分用原始文本
                const completeContent = content.substring(0, lastCompletePos);
                const incompleteContent = content.substring(lastCompletePos);

                const renderedComplete = marked.parse(completeContent);
                const escapedIncomplete = escapeHtml(incompleteContent);

                return renderedComplete + escapedIncomplete;
            } else {
                // 没有完整的 markdown，使用原始文本
                return escapeHtml(content);
            }
        },

        /**
         * 检查 markdown 元素是否完整
         * @param {string} text - 文本
         * @param {string} type - 类型
         * @returns {boolean} 是否完整
         */
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
        },

        /**
         * 渲染 Mermaid 图表
         * @param {HTMLElement} container - 容器元素
         * @param {function} escapeHtml - HTML 转义函数
         */
        renderMermaidDiagrams(container, escapeHtml) {
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
                        wrapper.innerHTML = `<pre>${escapeHtml(definition)}</pre>`;
                    });

                codeBlock.dataset.mermaidProcessed = 'true';
            });
        }
    };

    global.MarkdownRenderer = MarkdownRenderer;
})(window);

