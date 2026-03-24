import { useState, useCallback, useRef, useEffect } from 'react';
import { Button, Modal, Radio, Select, Input, Skeleton, App, Tag, Tooltip } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  SendOutlined,
  MessageOutlined,
  FileTextOutlined,
  GlobalOutlined,
  UserOutlined,
  RobotOutlined,
  ExclamationCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import {
  useSessions,
  useCreateSession,
  useDeleteSession,
  useMessages,
  useInvalidateMessages,
  useDocuments,
} from '../../hooks';
import { sendMessage } from '../../services';
import { useChatStore } from '../../stores';
import type { ScopeType, ChatMessage } from '../../types';
import styles from './Chat.module.css';

// ── Helpers ──

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86400000) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  if (diff < 172800000) return '昨天';
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

// ── New Session Dialog ──

function NewSessionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (scope: ScopeType, docId?: string) => void;
}) {
  const [scope, setScope] = useState<ScopeType>('all');
  const [docId, setDocId] = useState<string>();
  const { data: docsData } = useDocuments();
  const availableDocs = docsData?.items.filter((d) => d.status === '可用') ?? [];

  const handleOk = () => {
    onCreate(scope, scope === 'single' ? docId : undefined);
    setScope('all');
    setDocId(undefined);
    onClose();
  };

  return (
    <Modal
      title="新建会话"
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      okText="创建会话"
      cancelText="取消"
      okButtonProps={{ disabled: scope === 'single' && !docId }}
      destroyOnClose
    >
      <div className={styles.dialogBody}>
        <div className={styles.dialogField}>
          <label className={styles.dialogLabel}>检索范围</label>
          <Radio.Group value={scope} onChange={(e) => setScope(e.target.value)}>
            <Radio value="all">
              <GlobalOutlined /> 全部文档
            </Radio>
            <Radio value="single">
              <FileTextOutlined /> 指定文档
            </Radio>
          </Radio.Group>
        </div>

        {scope === 'single' && (
          <div className={styles.dialogField}>
            <label className={styles.dialogLabel}>选择文档</label>
            {availableDocs.length === 0 ? (
              <div className={styles.noDocsHint}>
                <InboxOutlined /> 暂无可用文档，请先上传并等待解析完成
              </div>
            ) : (
              <Select
                placeholder="选择一个文档"
                value={docId}
                onChange={setDocId}
                style={{ width: '100%' }}
                options={availableDocs.map((d) => ({
                  value: d.id,
                  label: d.file_name,
                }))}
              />
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Single Message ──

function MessageBubble({
  msg,
  isStreaming,
}: {
  msg: { role: 'user' | 'assistant'; content: string };
  isStreaming?: boolean;
}) {
  const isUser = msg.role === 'user';

  return (
    <div className={`${styles.msg} ${isUser ? styles.msgUser : styles.msgAssistant}`}>
      <div className={styles.msgAvatar}>
        {isUser ? <UserOutlined /> : <RobotOutlined />}
      </div>
      <div className={styles.msgBody}>
        {isUser ? (
          <div className={styles.msgText}>{msg.content}</div>
        ) : (
          <div className={styles.msgMarkdown}>
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
              {msg.content}
            </ReactMarkdown>
            {isStreaming && <span className={styles.cursor} />}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ──

export default function ChatPage() {
  const { message: msgApi } = App.useApp();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Store
  const {
    activeSessionId,
    streamingContent,
    isStreaming,
    setActiveSession,
    appendStreamToken,
    startStreaming,
    stopStreaming,
    resetStream,
  } = useChatStore();

  // Queries
  const { data: sessions, isLoading: sessionsLoading } = useSessions();
  const { data: messages, isLoading: messagesLoading } = useMessages(activeSessionId);
  const invalidateMessages = useInvalidateMessages();
  const createMutation = useCreateSession();
  const deleteMutation = useDeleteSession();

  // Auto-select first session
  useEffect(() => {
    if (!activeSessionId && sessions && sessions.length > 0) {
      setActiveSession(sessions[0].id);
    }
  }, [sessions, activeSessionId, setActiveSession]);

  // Scroll to bottom on new messages or streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Create session
  const handleCreate = useCallback(
    (scope: ScopeType, docId?: string) => {
      createMutation.mutate(
        { scope_type: scope, document_id: docId },
        {
          onSuccess: (session) => {
            setActiveSession(session.id);
            msgApi.success('会话已创建');
          },
        },
      );
    },
    [createMutation, setActiveSession, msgApi],
  );

  // Delete session
  const handleDeleteSession = useCallback(
    (id: string) => {
      Modal.confirm({
        title: '删除会话',
        icon: <ExclamationCircleOutlined />,
        content: '确定要删除该会话吗？所有消息将被清除。',
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () =>
          deleteMutation.mutateAsync(id).then(() => {
            if (activeSessionId === id) setActiveSession(undefined);
            msgApi.success('会话已删除');
          }),
      });
    },
    [deleteMutation, activeSessionId, setActiveSession, msgApi],
  );

  // Send message
  const handleSend = useCallback(() => {
    const content = inputValue.trim();
    if (!content || !activeSessionId || isStreaming) return;

    setInputValue('');

    const abort = sendMessage(activeSessionId, content, {
      onToken: (token) => appendStreamToken(token),
      onDone: () => {
        stopStreaming();
        invalidateMessages(activeSessionId);
      },
      onError: (err) => {
        stopStreaming();
        msgApi.error(`发送失败：${err.message}`);
      },
    });

    startStreaming(abort);
    // Invalidate to show user message immediately
    invalidateMessages(activeSessionId);
  }, [
    inputValue,
    activeSessionId,
    isStreaming,
    appendStreamToken,
    startStreaming,
    stopStreaming,
    invalidateMessages,
    msgApi,
  ]);

  // Key handler
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Current session info
  const activeSession = sessions?.find((s) => s.id === activeSessionId);

  // ── Render ──

  return (
    <div className={styles.page}>
      {/* ══════ Sidebar ══════ */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <span className={styles.sidebarTitle}>会话列表</span>
          <Button
            type="text"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setDialogOpen(true)}
          />
        </div>

        {sessionsLoading ? (
          <div className={styles.sidebarSkeleton}>
            <Skeleton active title={false} paragraph={{ rows: 4, width: ['80%', '60%', '70%', '50%'] }} />
          </div>
        ) : !sessions || sessions.length === 0 ? (
          <div className={styles.sidebarEmpty}>
            <MessageOutlined className={styles.sidebarEmptyIcon} />
            <p>暂无会话</p>
          </div>
        ) : (
          <div className={styles.sessionList}>
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`${styles.sessionItem} ${s.id === activeSessionId ? styles.sessionActive : ''}`}
                onClick={() => setActiveSession(s.id)}
              >
                <div className={styles.sessionTop}>
                  <span className={styles.sessionTitle}>{s.title}</span>
                  <Tooltip title="删除会话">
                    <Button
                      type="text"
                      size="small"
                      className={styles.sessionDelete}
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(s.id);
                      }}
                    />
                  </Tooltip>
                </div>
                <span className={styles.sessionTime}>{formatTime(s.updated_at)}</span>
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* ══════ Main Chat Area ══════ */}
      <div className={styles.main}>
        {!activeSessionId ? (
          /* No session selected */
          <div className={styles.noSession}>
            <MessageOutlined className={styles.noSessionIcon} />
            <p className={styles.noSessionTitle}>开始一段新对话</p>
            <p className={styles.noSessionDesc}>选择左侧会话或创建新会话开始提问</p>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setDialogOpen(true)}
            >
              新建会话
            </Button>
          </div>
        ) : (
          <>
            {/* Session header */}
            <div className={styles.chatHeader}>
              <span className={styles.chatTitle}>{activeSession?.title}</span>
              <Tag
                color={activeSession?.scope_type === 'all' ? 'blue' : 'green'}
                className={styles.scopeTag}
              >
                {activeSession?.scope_type === 'all' ? (
                  <><GlobalOutlined /> 全部文档</>
                ) : (
                  <><FileTextOutlined /> 指定文档</>
                )}
              </Tag>
            </div>

            {/* Messages */}
            <div className={styles.messages}>
              {messagesLoading ? (
                <div className={styles.messagesSkeleton}>
                  <Skeleton active avatar paragraph={{ rows: 2 }} />
                  <Skeleton active avatar paragraph={{ rows: 3 }} />
                </div>
              ) : messages && messages.length === 0 && !isStreaming ? (
                <div className={styles.messagesEmpty}>
                  <RobotOutlined className={styles.messagesEmptyIcon} />
                  <p>在下方输入您的问题，开始智能问答</p>
                </div>
              ) : (
                <>
                  {messages?.map((m) => (
                    <MessageBubble key={m.id} msg={m} />
                  ))}
                  {isStreaming && streamingContent && (
                    <MessageBubble
                      msg={{ role: 'assistant', content: streamingContent }}
                      isStreaming
                    />
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className={styles.inputArea}>
              <Input.TextArea
                ref={inputRef as any}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入您的问题..."
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={isStreaming}
                className={styles.chatInput}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!inputValue.trim() || isStreaming}
                className={styles.sendBtn}
              />
            </div>
          </>
        )}
      </div>

      {/* Dialog */}
      <NewSessionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
