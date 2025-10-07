# main.py
"""
FastAPI 后端主文件
提供WebSocket聊天接口和REST API
"""

import json
import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi import UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv, find_dotenv
import uvicorn

from mcp_agent import WebMCPAgent
from database import ChatDatabase
from app_main.connection import ConnectionManager
from app_main.ws_handlers import handle_ping, handle_pause, handle_resume_conversation

# 全局变量
mcp_agent = None
chat_db = None  # SQLite数据库实例
active_connections: List[WebSocket] = []
# 当前会话的流式任务，支持暂停/取消
active_stream_tasks: Dict[str, asyncio.Task] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global mcp_agent, chat_db
    
    # 启动时初始化
    print("🚀 启动 MCP Web 智能助手...")
    
    # 初始化数据库
    chat_db = ChatDatabase()
    db_success = await chat_db.initialize()
    if not db_success:
        print("❌ 数据库初始化失败")
        raise Exception("数据库初始化失败")
    
    # 初始化MCP智能体
    mcp_agent = WebMCPAgent()
    mcp_success = await mcp_agent.initialize()
    
    if not mcp_success:
        print("❌ MCP智能体初始化失败")
        raise Exception("MCP智能体初始化失败")
    
    print("✅ MCP Web 智能助手启动成功")
    
    yield
    
    # 关闭时清理资源
    if mcp_agent:
        await mcp_agent.close()
    if chat_db:
        await chat_db.close()
    print("👋 MCP Web 智能助手已关闭")

# 创建FastAPI应用
# 预加载 .env（不覆盖系统变量）
try:
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

app = FastAPI(
    title="MCP Web智能助手",
    description="基于MCP的智能助手Web版",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ─────────── WebSocket 接口 ───────────

manager = ConnectionManager()

# 挂载上传文件静态目录
try:
    UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
except Exception as _e:
    print(f"⚠️ 挂载上传目录失败: {_e}")

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket聊天接口"""
    # 为每个连接生成唯一会话ID并建立连接
    session_id = str(uuid.uuid4())
    await manager.connect(websocket, session_id)
    print(f"📱 新连接建立，会话ID: {session_id}，当前连接数: {len(manager.active_connections)}")
    # 向前端发送会话ID
    await manager.send_personal_message({"type": "session_info", "session_id": session_id}, websocket)
    # 从连接查询参数中读取 msid 与 model 并保存到会话上下文（后端隐藏使用，不回传给前端）
    try:
        print(f"🔍 WebSocket 查询参数: {dict(websocket.query_params)}")
        msid_param = websocket.query_params.get("msid")
        model_param = websocket.query_params.get("model")
        print(f"🔍 提取的 msid 参数: {msid_param}")
        print(f"🔍 提取的 model 参数: {model_param}")
        if msid_param is not None and msid_param != "":
            try:
                msid_value = int(msid_param)
                if not hasattr(mcp_agent, 'session_contexts'):
                    mcp_agent.session_contexts = {}
                mcp_agent.session_contexts[session_id] = {"msid": msid_value}
                print(f"🔐 已为会话 {session_id} 记录 msid={msid_value}")
                print(f"🔍 当前所有会话上下文: {mcp_agent.session_contexts}")
            except Exception as e:
                print(f"⚠️ 解析 msid 失败: {e}")
                # 非法 msid 忽略
                if not hasattr(mcp_agent, 'session_contexts'):
                    mcp_agent.session_contexts = {}
                mcp_agent.session_contexts[session_id] = {}
        else:
            print(f"⚠️ msid 参数为空或不存在")
            if not hasattr(mcp_agent, 'session_contexts'):
                mcp_agent.session_contexts = {}
            mcp_agent.session_contexts[session_id] = {}

        # 记录模型档位（如果提供）
        try:
            if model_param is not None and model_param != "":
                if not hasattr(mcp_agent, 'session_contexts'):
                    mcp_agent.session_contexts = {}
                session_ctx = mcp_agent.session_contexts.get(session_id, {})
                session_ctx["model"] = str(model_param)
                mcp_agent.session_contexts[session_id] = session_ctx
                print(f"🔐 已为会话 {session_id} 记录 model={model_param}")
        except Exception as e:
            print(f"⚠️ 记录 model 失败: {e}")
    except Exception as _e:
        print(f"❌ 处理 msid 参数异常: {_e}")
        if not hasattr(mcp_agent, 'session_contexts'):
            mcp_agent.session_contexts = {}
        mcp_agent.session_contexts[session_id] = {}
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "user_msg":
                    # 支持两种输入：
                    # 1) content: 纯文本字符串
                    # 2) content_parts: 多模态内容数组（[{type:'text',...}, {type:'image_url',...}]）
                    raw_content = message.get("content", None)
                    content_parts = message.get("content_parts") or []
                    attachments = message.get("attachments") or []

                    user_has_text = isinstance(raw_content, str) and raw_content.strip() != ""
                    user_has_images = isinstance(content_parts, list) and any(
                        isinstance(p, dict) and str(p.get("type") or "").lower() == "image_url" for p in content_parts
                    )
                    # 允许纯图片消息
                    if not user_has_text and not user_has_images and not attachments:
                        await manager.send_personal_message({
                            "type": "error",
                            "content": "User input cannot be empty"
                        }, websocket)
                        continue
                    
                    # 打印安全预览（文本前50字符或 [images] 提示）
                    try:
                        if isinstance(raw_content, str) and raw_content.strip():
                            _preview = raw_content[:50]
                        elif isinstance(content_parts, list) and any((isinstance(p, dict) and str(p.get('type') or '').lower() == 'image_url') for p in content_parts):
                            _preview = "[images]"
                        else:
                            _preview = ""
                    except Exception:
                        _preview = ""
                    print(f"📨 收到用户消息: {_preview}...")
                    
                    # 确认收到用户消息
                    await manager.send_personal_message({
                        "type": "user_msg_received",
                        "content": (raw_content if isinstance(raw_content, str) else "")
                    }, websocket)
                    
                    # 收集对话数据
                    conversation_data = {
                        "user_input": raw_content if raw_content is not None else "",
                        "mcp_tools_called": [],
                        "mcp_results": [],
                        "ai_response_parts": []
                    }
                    
                    # 获取当前连接与会话上下文
                    current_session_id = manager.get_session_id(websocket)
                    # 支持续聊：若存在生效的会话与线程，则复用；否则在生效会话上新建
                    try:
                        if not hasattr(mcp_agent, 'session_contexts'):
                            mcp_agent.session_contexts = {}
                        session_ctx = mcp_agent.session_contexts.get(current_session_id, {})
                        effective_session_id = session_ctx.get("effective_session_id") or current_session_id
                        conversation_id = session_ctx.get("effective_conversation_id") or session_ctx.get("conversation_id")
                        if conversation_id is None:
                            conversation_id = await chat_db.start_conversation(session_id=effective_session_id)
                            # 记录为当前连接的默认对话线程（未显式续聊时也复用该线程）
                            session_ctx["conversation_id"] = conversation_id
                            # 若此前已设置了 effective_session_id，则也将其与该对话绑定为生效线程
                            session_ctx["effective_session_id"] = effective_session_id
                            session_ctx["effective_conversation_id"] = conversation_id
                            mcp_agent.session_contexts[current_session_id] = session_ctx
                            print(f"🧵 新建对话线程 conversation_id={conversation_id} 用于会话 {effective_session_id}（连接 {current_session_id}）")
                    except Exception as _e:
                        print(f"⚠️ 初始化 conversation_id 失败: {_e}")
                        conversation_id = None

                    # 仅按生效的对话线程加载最近历史，避免串线
                    effective_session_id_for_history = session_ctx.get("effective_session_id") or current_session_id
                    history = await chat_db.get_chat_history(
                        session_id=effective_session_id_for_history,
                        limit=10,
                        conversation_id=conversation_id
                    ) # 限制最近10条
                    conversation_files = []
                    try:
                        if conversation_id is not None:
                            conversation_files = await chat_db.get_conversation_files(
                                session_id=effective_session_id_for_history,
                                conversation_id=conversation_id
                            )
                    except Exception as _e:
                        print(f"⚠️ 获取会话文件失败: {_e}")

                    # 启动后台任务消费流，允许外部 pause 取消
                    async def stream_and_persist():
                        try:
                            response_started = False
                            # 准备用户输入：
                            # - 如为多模态（content_parts），直接传入，不拼接附件提示
                            # - 否则为纯文本，可按需注入附件说明
                            user_payload = None
                            if isinstance(content_parts, list) and content_parts:
                                # 如果包含图片，但当前选择的模型不支持视觉，提前报错
                                try:
                                    selected_pid = session_ctx.get("model")
                                    cfg = None
                                    if selected_pid and selected_pid in mcp_agent.llm_profiles:
                                        cfg = mcp_agent.llm_profiles.get(selected_pid)
                                    else:
                                        cfg = mcp_agent.llm_profiles.get(mcp_agent.default_profile_id)
                                    model_name = (cfg or {}).get("model", "")
                                    base_url = (cfg or {}).get("base_url", "")
                                    if user_has_images and not mcp_agent._supports_vision(model_name, base_url):
                                        await manager.send_personal_message({
                                            "type": "error",
                                            "content": "当前所选模型不支持图像解析，请切换支持视觉的模型或移除图片。",
                                            "code": "vision_not_supported"
                                        }, websocket)
                                        return
                                except Exception:
                                    pass
                                user_payload = content_parts
                            else:
                                enriched_user_input = (raw_content or "").strip()
                                if attachments:
                                    try:
                                        names = ", ".join([str(a.get('filename') or '') for a in attachments if a])
                                        urls = "; ".join([str(a.get('url') or '') for a in attachments if a])
                                        note = f"\n\n[Attachments]\nfilenames: {names}\nurls: {urls}\nIf needed, use tool 'preview_uploaded_file' with the url string to preview content."
                                        enriched_user_input = (enriched_user_input or '') + note
                                    except Exception:
                                        pass
                                user_payload = enriched_user_input

                            async for response_chunk in mcp_agent.chat_stream(
                                user_payload,
                                history=history,
                                session_id=current_session_id,
                                conversation_files=conversation_files
                            ):
                                await manager.send_personal_message(response_chunk, websocket)
                                chunk_type = response_chunk.get("type")
                                if chunk_type == "ai_response_start":
                                    response_started = True
                                elif chunk_type == "tool_start":
                                    conversation_data["mcp_tools_called"].append({
                                        "tool_id": response_chunk.get("tool_id"),
                                        "tool_name": response_chunk.get("tool_name"),
                                        "tool_args": response_chunk.get("tool_args"),
                                        "progress": response_chunk.get("progress")
                                    })
                                elif chunk_type == "tool_end":
                                    conversation_data["mcp_results"].append({
                                        "tool_id": response_chunk.get("tool_id"),
                                        "tool_name": response_chunk.get("tool_name"),
                                        "result": response_chunk.get("result"),
                                        "success": True
                                    })
                                elif chunk_type == "tool_error":
                                    conversation_data["mcp_results"].append({
                                        "tool_id": response_chunk.get("tool_id"),
                                        "error": response_chunk.get("error"),
                                        "success": False
                                    })
                                elif chunk_type in ("ai_response_chunk", "ai_thinking_chunk"):
                                    conversation_data["ai_response_parts"].append(response_chunk.get("content", ""))
                                elif chunk_type == "token_usage":
                                    conversation_data["usage"] = {
                                        "input_tokens": response_chunk.get("input_tokens"),
                                        "output_tokens": response_chunk.get("output_tokens"),
                                        "total_tokens": response_chunk.get("total_tokens")
                                    }
                                elif chunk_type == "error":
                                    print(f"❌ MCP处理错误: {response_chunk.get('content')}")
                                    break
                        except asyncio.CancelledError:
                            # 被暂停：结束消息但不丢已生成内容
                            if response_started:
                                try:
                                    await manager.send_personal_message({"type": "ai_response_end", "content": ""}, websocket)
                                except Exception:
                                    pass
                            raise
                        except Exception as e:
                            print(f"❌ MCP流式处理异常: {e}")
                        finally:
                            ai_response_final = "".join(conversation_data["ai_response_parts"]) or ""
                            if not ai_response_final and conversation_data["mcp_results"]:
                                error_results = [r for r in conversation_data["mcp_results"] if not r.get("success", True)]
                                if error_results:
                                    ai_response_final = "处理过程中遇到错误：\n" + "\n".join([r.get("error", "未知错误") for r in error_results])
                            try:
                                if chat_db:
                                    # 续聊：保存到生效会话+线程
                                    effective_session_id_for_save = session_ctx.get("effective_session_id") or current_session_id
                                    inserted_id = await chat_db.save_conversation(
                                        user_input=conversation_data["user_input"],
                                        mcp_tools_called=conversation_data["mcp_tools_called"],
                                        mcp_results=conversation_data["mcp_results"],
                                        ai_response=ai_response_final,
                                        session_id=effective_session_id_for_save,
                                        conversation_id=conversation_id,
                                        msid=mcp_agent.session_contexts.get(current_session_id, {}).get("msid") if hasattr(mcp_agent, 'session_contexts') else None,
                                        attachments=attachments,
                                        usage=conversation_data.get("usage")
                                    )
                                    # 将新记录ID回传给前端，便于即时挂载操作按钮
                                    try:
                                        await manager.send_personal_message({
                                            "type": "record_saved",
                                            "record_id": inserted_id,
                                            "session_id": effective_session_id_for_save,
                                            "conversation_id": conversation_id
                                        }, websocket)
                                    except Exception:
                                        pass
                            except Exception as e:
                                print(f"❌ 保存对话记录异常: {e}")
                            finally:
                                active_stream_tasks.pop(current_session_id, None)

                    task = asyncio.create_task(stream_and_persist())
                    active_stream_tasks[current_session_id] = task
                    continue
                
                elif message.get("type") == "pause":
                    await handle_pause(websocket, manager, active_stream_tasks)
                    continue

                elif message.get("type") == "ping":
                    await handle_ping(websocket, manager)
                elif message.get("type") == "resume_conversation":
                    await handle_resume_conversation(message, websocket, manager, mcp_agent)
                elif message.get("type") == "switch_model":
                    # 切换当前连接的模型档位（不重连，不新开会话）
                    try:
                        payload = message or {}
                        new_model = str(payload.get("model") or "").strip()
                        if not new_model:
                            await manager.send_personal_message({
                                "type": "model_switch_error",
                                "content": "Missing model id"
                            }, websocket)
                            continue
                        current_session_id = manager.get_session_id(websocket)
                        if not hasattr(mcp_agent, 'session_contexts'):
                            mcp_agent.session_contexts = {}
                        session_ctx = mcp_agent.session_contexts.get(current_session_id, {})
                        session_ctx["model"] = new_model
                        mcp_agent.session_contexts[current_session_id] = session_ctx
                        await manager.send_personal_message({
                            "type": "model_switched",
                            "model": new_model
                        }, websocket)
                    except Exception as _e:
                        await manager.send_personal_message({
                            "type": "model_switch_error",
                            "content": f"Switch failed: {_e}"
                        }, websocket)
                elif message.get("type") == "replay_edit":
                    # 回溯编辑：删除某线程从指定记录ID起的历史，并以新内容作为本轮用户输入重新生成
                    try:
                        payload = message or {}
                        target_session = str(payload.get("session_id") or "").strip()
                        target_conv = payload.get("conversation_id")
                        from_record_id = payload.get("from_record_id")
                        new_user_input = str(payload.get("new_user_input") or "").strip()
                        if not target_session or target_conv is None or from_record_id is None or not new_user_input:
                            await manager.send_personal_message({
                                "type": "edit_error",
                                "content": "Missing required fields"
                            }, websocket)
                            continue
                        # 先删除后续记录
                        try:
                            ok = await chat_db.delete_records_after(target_session, int(target_conv), int(from_record_id))
                            if not ok:
                                await manager.send_personal_message({
                                    "type": "edit_error",
                                    "content": "Failed to truncate history"
                                }, websocket)
                                continue
                        except Exception as _e:
                            await manager.send_personal_message({
                                "type": "edit_error",
                                "content": f"Truncate failed: {_e}"
                            }, websocket)
                            continue

                        # 绑定生效会话/线程到当前连接，随后按普通 user_msg 流程处理
                        current_session_id = manager.get_session_id(websocket)
                        if not hasattr(mcp_agent, 'session_contexts'):
                            mcp_agent.session_contexts = {}
                        session_ctx = mcp_agent.session_contexts.get(current_session_id, {})
                        session_ctx["effective_session_id"] = target_session
                        session_ctx["effective_conversation_id"] = int(target_conv)
                        mcp_agent.session_contexts[current_session_id] = session_ctx
                        await manager.send_personal_message({
                            "type": "edit_ok",
                            "session_id": target_session,
                            "conversation_id": int(target_conv)
                        }, websocket)

                        # 直接按 user_msg 流程继续生成
                        user_input = new_user_input
                        # 收集对话数据
                        conversation_data = {
                            "user_input": user_input,
                            "mcp_tools_called": [],
                            "mcp_results": [],
                            "ai_response_parts": []
                        }
                        # 在目标线程上取历史
                        history = await chat_db.get_chat_history(
                            session_id=target_session,
                            limit=10,
                            conversation_id=int(target_conv)
                        )
                        conversation_files = []
                        try:
                            conversation_files = await chat_db.get_conversation_files(
                                session_id=target_session,
                                conversation_id=int(target_conv)
                            )
                        except Exception as _e:
                            print(f"⚠️ 获取会话文件失败: {_e}")
                        async def stream_and_persist_edit():
                            try:
                                response_started = False
                                async for response_chunk in mcp_agent.chat_stream(
                                    user_input,
                                    history=history,
                                    session_id=current_session_id,
                                    conversation_files=conversation_files
                                ):
                                    await manager.send_personal_message(response_chunk, websocket)
                                    chunk_type = response_chunk.get("type")
                                    if chunk_type == "ai_response_start":
                                        response_started = True
                                    elif chunk_type == "tool_start":
                                        conversation_data["mcp_tools_called"].append({
                                            "tool_id": response_chunk.get("tool_id"),
                                            "tool_name": response_chunk.get("tool_name"),
                                            "tool_args": response_chunk.get("tool_args"),
                                            "progress": response_chunk.get("progress")
                                        })
                                    elif chunk_type == "tool_end":
                                        conversation_data["mcp_results"].append({
                                            "tool_id": response_chunk.get("tool_id"),
                                            "tool_name": response_chunk.get("tool_name"),
                                            "result": response_chunk.get("result"),
                                            "success": True
                                        })
                                    elif chunk_type == "tool_error":
                                        conversation_data["mcp_results"].append({
                                            "tool_id": response_chunk.get("tool_id"),
                                            "error": response_chunk.get("error"),
                                            "success": False
                                        })
                                    elif chunk_type in ("ai_response_chunk", "ai_thinking_chunk"):
                                        conversation_data["ai_response_parts"].append(response_chunk.get("content", ""))
                                    elif chunk_type == "token_usage":
                                        conversation_data["usage"] = {
                                            "input_tokens": response_chunk.get("input_tokens"),
                                            "output_tokens": response_chunk.get("output_tokens"),
                                            "total_tokens": response_chunk.get("total_tokens")
                                        }
                                    elif chunk_type == "error":
                                        print(f"❌ MCP处理错误: {response_chunk.get('content')}")
                                        break
                            except asyncio.CancelledError:
                                if response_started:
                                    try:
                                        await manager.send_personal_message({"type": "ai_response_end", "content": ""}, websocket)
                                    except Exception:
                                        pass
                                raise
                            except Exception as e:
                                print(f"❌ MCP流式处理异常: {e}")
                            finally:
                                ai_response_final = "".join(conversation_data["ai_response_parts"]) or ""
                                if not ai_response_final and conversation_data["mcp_results"]:
                                    error_results = [r for r in conversation_data["mcp_results"] if not r.get("success", True)]
                                    if error_results:
                                        ai_response_final = "处理过程中遇到错误：\n" + "\n".join([r.get("error", "未知错误") for r in error_results])
                                try:
                                    if chat_db:
                                        inserted_id = await chat_db.save_conversation(
                                            user_input=conversation_data["user_input"],
                                            mcp_tools_called=conversation_data["mcp_tools_called"],
                                            mcp_results=conversation_data["mcp_results"],
                                            ai_response=ai_response_final,
                                            session_id=target_session,
                                            conversation_id=int(target_conv),
                                            msid=mcp_agent.session_contexts.get(current_session_id, {}).get("msid") if hasattr(mcp_agent, 'session_contexts') else None,
                                            attachments=[{"filename": "(edited)"}],  # 保留字段结构，后续可扩展
                                            usage=conversation_data.get("usage")
                                        )
                                        try:
                                            await manager.send_personal_message({
                                                "type": "record_saved",
                                                "record_id": inserted_id,
                                                "session_id": target_session,
                                                "conversation_id": int(target_conv)
                                            }, websocket)
                                        except Exception:
                                            pass
                                except Exception as e:
                                    print(f"❌ 保存对话记录异常: {e}")
                                finally:
                                    active_stream_tasks.pop(current_session_id, None)

                        task = asyncio.create_task(stream_and_persist_edit())
                        active_stream_tasks[current_session_id] = task
                        continue
                    except Exception as _e:
                        await manager.send_personal_message({
                            "type": "edit_error",
                            "content": f"Edit failed: {_e}"
                        }, websocket)
                        continue
                
                else:
                    await manager.send_personal_message({
                        "type": "error",
                        "content": f"未知消息类型: {message.get('type')}"
                    }, websocket)
                    
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "content": "Invalid message format. Please send valid JSON."
                }, websocket)
            except Exception as e:
                print(f"❌ WebSocket消息处理异常: {e}")
                import traceback
                traceback.print_exc()
                await manager.send_personal_message({
                    "type": "error",
                    "content": f"处理消息时出错: {str(e)}"
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket错误: {e}")
        manager.disconnect(websocket)

# ─────────── REST API 接口 ───────────

@app.get("/")
async def root():
    """根路径重定向到前端"""
    return {"message": "MCP Web智能助手API", "version": "1.0.0"}

@app.get("/api/tools")
async def get_tools():
    """获取可用工具列表"""
    if not mcp_agent:
        raise HTTPException(status_code=503, detail="MCP智能体未初始化")
    
    try:
        tools_info = mcp_agent.get_tools_info()
        return {
            "success": True,
            "data": tools_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {str(e)}")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件，返回可访问的URL路径。"""
    try:
        # 基础校验与限制（可按需调整）
        original_name = file.filename or "file"
        ext = os.path.splitext(original_name)[1]
        # 生成唯一文件名，避免重复
        unique_name = f"{uuid.uuid4().hex}{ext}"

        # 使用日期子目录，便于管理
        date_dir = datetime.now().strftime("%Y%m%d")
        target_dir = os.path.join(UPLOADS_DIR, date_dir)
        os.makedirs(target_dir, exist_ok=True)

        target_path = os.path.join(target_dir, unique_name)
        content = await file.read()
        # 简单大小限制：20MB
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 20MB)")
        with open(target_path, "wb") as f:
            f.write(content)

        # 返回静态访问路径（相对API根路径）
        url_path = f"/uploads/{date_dir}/{unique_name}"
        return {"success": True, "data": {"filename": original_name, "stored_as": unique_name, "url": url_path}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@app.get("/api/models")
async def get_models():
    """获取可选的大模型档位列表（用于前端下拉选择）。"""
    if not mcp_agent:
        raise HTTPException(status_code=503, detail="MCP智能体未初始化")
    try:
        return {"success": True, "data": mcp_agent.get_models_info()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@app.get("/api/history")
async def get_history(limit: int = 50, session_id: str = "default", conversation_id: int = None):
    """获取聊天历史"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    
    try:
        records = await chat_db.get_chat_history(
            session_id=session_id, 
            limit=limit,
            conversation_id=conversation_id
        )
        conversation_files = []
        if conversation_id is not None:
            try:
                conversation_files = await chat_db.get_conversation_files(
                    session_id=session_id,
                    conversation_id=conversation_id
                )
            except Exception as _e:
                print(f"⚠️ 获取会话文件失败: {_e}")
        
        # 获取统计信息
        stats = await chat_db.get_stats()
        
        return {
            "success": True,
            "data": records,
            "total": stats.get("total_records", 0),
            "returned": len(records),
            "session_id": session_id,
            "conversation_id": conversation_id,
            "conversation_files": conversation_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")

@app.get("/api/threads")
async def get_threads(msid: int, limit: int = 100):
    """按 msid 获取对话线程列表（左侧侧栏用）。"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    try:
        threads = await chat_db.get_threads_by_msid(msid=msid, limit=limit)
        return {"success": True, "data": threads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取线程列表失败: {str(e)}")

@app.delete("/api/history")
async def clear_history(session_id: str = None):
    """清空聊天历史"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    
    try:
        # 如果没有提供session_id，则清空所有历史（保持向后兼容）
        if session_id:
            success = await chat_db.clear_history(session_id=session_id)
            message = f"会话 {session_id} 的聊天历史已清空"
        else:
            success = await chat_db.clear_history()
            message = "所有聊天历史已清空"
        
        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=500, detail="清空历史记录失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空历史记录失败: {str(e)}")

@app.delete("/api/threads")
async def delete_thread(session_id: str, conversation_id: int):
    """删除某个对话线程"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    try:
        ok = await chat_db.delete_conversation(session_id=session_id, conversation_id=conversation_id)
        if ok:
            return {"success": True}
        raise HTTPException(status_code=500, detail="删除对话线程失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除对话线程失败: {str(e)}")

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    # 获取数据库统计信息
    db_stats = {}
    if chat_db:
        try:
            db_stats = await chat_db.get_stats()
        except Exception as e:
            print(f"⚠️ 获取数据库统计失败: {e}")
    
    return {
        "success": True,
        "data": {
            "agent_initialized": mcp_agent is not None,
            "database_initialized": chat_db is not None,
            "tools_count": len(mcp_agent.tools) if mcp_agent else 0,
            "active_connections": len(manager.active_connections),
            "chat_records_count": db_stats.get("total_records", 0),
            "chat_sessions_count": db_stats.get("total_sessions", 0),
            "chat_conversations_count": db_stats.get("total_conversations", 0),
            "latest_record": db_stats.get("latest_record"),
            "database_path": db_stats.get("database_path"),
            "timestamp": datetime.now().isoformat()
        }
    }

@app.get("/api/database/stats")
async def get_database_stats():
    """获取数据库详细统计信息"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    
    try:
        stats = await chat_db.get_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据库统计失败: {str(e)}")

@app.get("/api/share/{session_id}")
async def get_shared_chat(session_id: str, limit: int = 100):
    """获取分享的聊天记录（只读）"""
    if not chat_db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    
    try:
        # 获取指定会话的聊天历史
        records = await chat_db.get_chat_history(
            session_id=session_id, 
            limit=limit
        )
        
        if not records:
            raise HTTPException(status_code=404, detail="未找到该会话的聊天记录")
        
        # 获取会话统计信息
        stats = await chat_db.get_stats()
        
        return {
            "success": True,
            "data": records,
            "session_id": session_id,
            "total_records": len(records),
            "shared_at": datetime.now().isoformat(),
            "readonly": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分享聊天记录失败: {str(e)}")

# ─────────── 静态文件服务（可选） ───────────

# 如果要让FastAPI直接服务前端文件，取消下面的注释
# app.mount("/static", StaticFiles(directory="../frontend"), name="static")

if __name__ == "__main__":
    # 开发环境启动
    # 端口可通过环境变量 BACKEND_PORT 覆盖，默认 8003，与前端配置一致
    try:
        port = int(os.getenv("BACKEND_PORT", "8003"))
    except Exception:
        port = 8003
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
