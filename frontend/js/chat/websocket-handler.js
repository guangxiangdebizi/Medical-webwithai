// websocket-handler.js - WebSocket 消息处理模块
(function(global) {
    const WebSocketHandler = {
        /**
         * 处理 WebSocket 消息
         * @param {object} data - 消息数据
         * @param {object} app - ChatApp 实例
         */
        handleMessage(data, app) {
            console.log('📨 收到消息:', data);
            
            switch (data.type) {
                case 'session_info':
                    // 接收会话 ID
                    app.sessionId = data.session_id;
                    console.log('🆔 收到会话ID:', app.sessionId);
                    break;
                    
                case 'resume_ok':
                    // 后端确认续聊绑定成功
                    try {
                        app.resumedSessionId = data.session_id;
                        app.resumedConversationId = data.conversation_id;
                        console.log('✅ 续聊绑定成功 ->', app.resumedSessionId, app.resumedConversationId);
                    } catch {}
                    break;
                    
                case 'resume_error':
                    app.showError(`Resume failed: ${data.content || 'unknown error'}`);
                    break;
                    
                case 'edit_ok':
                    // 回溯截断成功
                    console.log('✂️ 回溯截断成功，开始重生');
                    break;
                    
                case 'edit_error':
                    app.showError(`Edit failed: ${data.content || 'unknown error'}`);
                    break;
                    
                case 'user_msg_received':
                    // 用户消息已收到确认
                    break;
                    
                case 'status':
                    // 移除硬编码的 status 处理，让 AI 思考内容自然显示
                    break;
                    
                case 'ai_thinking_start':
                    // 开始 AI 思考流式显示
                    app.thinkingFlow.startThinkingContent(data.iteration);
                    break;
                    
                case 'ai_thinking_chunk':
                    // AI 思考内容片段
                    app.thinkingFlow.appendThinkingContent(data.content, data.iteration);
                    break;
                    
                case 'ai_thinking_end':
                    // 结束 AI 思考
                    app.thinkingFlow.endThinkingContent(data.iteration);
                    break;
                    
                case 'tool_plan':
                    app.thinkingFlow.updateThinkingStage(
                        'tools_planned', 
                        `Planning to use ${data.tool_count} tool(s)`, 
                        'Preparing clinical data operations...',
                        { toolCount: data.tool_count }
                    );
                    break;
                    
                case 'tool_start':
                    app.thinkingFlow.addToolToThinking(data);
                    break;
                    
                case 'tool_end':
                    app.thinkingFlow.updateToolInThinking(data, 'completed');
                    break;
                    
                case 'tool_error':
                    app.thinkingFlow.updateToolInThinking(data, 'error');
                    break;
                    
                case 'ai_response_start':
                    app.thinkingFlow.updateThinkingStage(
                        'responding', 
                        'Preparing response', 
                        'Organizing evidence-based conclusions and recommendations...'
                    );
                    
                    // 确保思维流可见 - 智能滚动策略
                    const currentFlow = app.thinkingFlow.getCurrentFlow();
                    if (currentFlow && !UIController.isUserViewingContent(app.chatMessages)) {
                        // 只有用户不在查看历史内容时才滚动到思维流
                        setTimeout(() => {
                            currentFlow.scrollIntoView({
                                behavior: 'smooth',
                                block: 'start',
                                inline: 'nearest'
                            });
                        }, 100);
                    }

                    app.startAIResponse();
                    // 进入流式阶段，切换按钮为暂停
                    app.isStreaming = true;
                    app.updateSendButton();
                    break;
                    
                case 'ai_response_chunk':
                    app.appendAIResponse(data.content);
                    break;
                    
                case 'ai_response_end':
                    app.endAIResponse();
                    app.thinkingFlow.completeThinkingFlow('success');
                    // 结束流式，恢复按钮
                    app.isStreaming = false;
                    app.updateSendButton();
                    break;
                    
                case 'token_usage':
                    // 在 AI 消息下方追加一行浅色用量提示
                    app.appendTokenUsageFooter(data);
                    break;
                    
                case 'record_saved':
                    // 后端返回新插入的记录 ID
                    MessageActions.attachActionsToLastUserMessage(app, data);
                    break;
                    
                case 'error':
                    app.showError(data.content);
                    app.thinkingFlow.completeThinkingFlow('error');
                    app.isStreaming = false;
                    app.updateSendButton();
                    break;
                    
                default:
                    console.warn('未知消息类型:', data.type);
            }
        }
    };

    global.WebSocketHandler = WebSocketHandler;
})(window);

