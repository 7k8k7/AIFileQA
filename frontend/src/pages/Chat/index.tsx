import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Button, Modal, Radio, Select, Input, Skeleton, App, Tag, Tooltip, Descriptions } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  SendOutlined,
  ReloadOutlined,
  MessageOutlined,
  FileTextOutlined,
  GlobalOutlined,
  UserOutlined,
  RobotOutlined,
  ExclamationCircleOutlined,
  InboxOutlined,
  RightOutlined,
  FileSearchOutlined,
  ApiOutlined,
  InfoCircleOutlined,
  MenuOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import {
  useSessions,
  useCreateSession,
  useRenameSession,
  useDeleteSession,
  useMessages,
  useInvalidateMessages,
  useAllDocuments,
  useProviders,
} from '../../hooks';
import { regenerateMessage, sendMessage } from '../../services';
import { useChatStore } from '../../stores';
import type { SourcesData } from '../../stores/chatStore';
import type { ChatMessage, Document, ProviderConfig, ScopeType } from '../../types';
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

function getProviderRuntimeHint(provider?: ProviderConfig): string {
  if (!provider) return '当前没有可用供应商。';
  if (provider.provider_type === 'claude') {
    return '当前会话使用 Claude 聊天模型，检索阶段会固定退回关键词检索。';
  }
  if (!provider.enable_embedding) {
    return '当前会话已关闭 Embedding，系统会直接使用关键词检索。';
  }
  if (provider.provider_type === 'openai_compatible') {
    return '当前会话会先尝试兼容接口的 Embedding；如果本地服务不支持，会自动退回关键词检索。';
  }
  return '当前会话会优先使用 Embedding 检索；如果向量不可用，会自动退回关键词检索。';
}

function getRequestErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    const message = (error as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) {
      return message;
    }
  }
  return fallback;
}

// ── New Session Dialog ──

function NewSessionDialog({
  open,
  onClose,
  onCreate,
  creating,
  providers,
  documents,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (scope: ScopeType, providerId?: string, docIds?: string[]) => void;
  creating: boolean;
  providers: ProviderConfig[];
  documents: Document[];
}) {
  const [scope, setScope] = useState<ScopeType>('all');
  const [providerId, setProviderId] = useState<string>();
  const [docIds, setDocIds] = useState<string[]>([]);
  const availableDocs = useMemo(
    () => documents.filter((d) => d.status === '可用'),
    [documents],
  );
  const verifiedProviders = useMemo(
    () => providers.filter((provider) => provider.last_test_success),
    [providers],
  );
  const hiddenProviderCount = providers.length - verifiedProviders.length;
  const defaultProviderId = useMemo(
    () => verifiedProviders.find((provider) => provider.is_default)?.id ?? verifiedProviders[0]?.id,
    [verifiedProviders],
  );

  useEffect(() => {
    if (!open) return;
    setScope('all');
    setDocIds([]);
    setProviderId(defaultProviderId);
  }, [defaultProviderId, open]);

  const handleOk = () => {
    onCreate(scope, providerId, scope === 'single' ? docIds : undefined);
  };

  return (
    <Modal
      title="新建会话"
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      okText="创建会话"
      cancelText="取消"
      confirmLoading={creating}
      okButtonProps={{ disabled: creating || !providerId || (scope === 'single' && docIds.length === 0) }}
      destroyOnClose
    >
      <div className={styles.dialogBody}>
        <div className={styles.dialogField}>
          <label className={styles.dialogLabel}>使用模型</label>
          {providers.length === 0 ? (
            <div className={styles.noDocsHint}>
              <ApiOutlined /> 暂无可用供应商，请先到设置页配置
            </div>
          ) : verifiedProviders.length === 0 ? (
            <div className={styles.noDocsHint}>
              <ApiOutlined /> 已配置 {providers.length} 个供应商，但都还没通过连接测试，请先到设置页完成测试
            </div>
          ) : (
            <>
              <Select
                placeholder="选择一个供应商"
                value={providerId}
                onChange={setProviderId}
                style={{ width: '100%' }}
                options={verifiedProviders.map((provider) => ({
                  value: provider.id,
                  label: `${provider.provider_type === 'openai' ? 'OpenAI' : provider.provider_type === 'claude' ? 'Claude' : '兼容接口'} · ${provider.model_name}${provider.is_default ? '（默认）' : ''}`,
                }))}
              />
              {hiddenProviderCount > 0 && (
                <div className={styles.noDocsHint}>
                  <InfoCircleOutlined /> 已隐藏 {hiddenProviderCount} 个未通过连接测试的供应商
                </div>
              )}
            </>
          )}
        </div>

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
                <InboxOutlined /> 暂无可用文档，请先上传文档
              </div>
            ) : (
              <Select
                mode="multiple"
                placeholder="选择一个或多个文档"
                value={docIds}
                onChange={setDocIds}
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
  msg: Pick<ChatMessage, 'role' | 'content'>;
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

// ── Sources Panel ──

function SourcesPanel({ sources }: { sources: SourcesData }) {
  const [expanded, setExpanded] = useState(false);
  const retrievalLabel =
    sources.retrieval_method === 'hybrid'
      ? '混合检索'
      : sources.retrieval_method === 'vector'
        ? '向量检索'
        : '关键词检索';

  if (sources.chunks.length === 0) {
    return (
      <div className={styles.sourcesEmpty}>
        <FileSearchOutlined /> 未检索到相关文档内容
      </div>
    );
  }

  return (
    <div className={styles.sourcesPanel}>
      <div className={styles.sourcesSummary} onClick={() => setExpanded(!expanded)}>
        <RightOutlined className={`${styles.sourcesArrow} ${expanded ? styles.sourcesArrowOpen : ''}`} />
        <FileSearchOutlined />
        <span>
          基于 {sources.chunks.length} 个文档片段回答
          {`（${retrievalLabel}）`}
        </span>
      </div>
      {sources.retrieval_method === 'keyword' && (
        <div className={styles.sourcesNotice}>
          当前回答已退回关键词检索，通常是因为当前 provider 未启用 Embedding、该 provider 不支持 Embedding，或当前文档还没有可用向量。
        </div>
      )}
      {sources.retrieval_method === 'hybrid' && (
        <div className={styles.sourcesNotice}>
          当前回答同时综合了向量检索和关键词检索结果，用来提高召回稳定性。
        </div>
      )}
      {expanded && (
        <div className={styles.sourcesList}>
          {sources.chunks.map((chunk, i) => (
            <div key={i} className={styles.sourceItem}>
              <div className={styles.sourceItemHeader}>
                <span className={styles.sourceDocName}>{chunk.document_name}</span>
                {chunk.page_no != null && (
                  <Tag color="default" style={{ fontSize: 11, lineHeight: '18px', margin: 0 }}>
                    第{chunk.page_no}页
                  </Tag>
                )}
                {chunk.score != null && (
                  <Tag color="blue" style={{ fontSize: 11, lineHeight: '18px', margin: 0 }}>
                    {chunk.score.toFixed(2)}
                  </Tag>
                )}
              </div>
              <div className={styles.sourceContent}>{chunk.content}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ──

export default function ChatPage() {
  const { message: msgApi } = App.useApp();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [documentModalOpen, setDocumentModalOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Store
  const {
    activeSessionId,
    streamingContent,
    isStreaming,
    streamingSources,
    optimisticMessages,
    regeneratingMessageId,
    setActiveSession,
    addOptimisticUserMessage,
    commitOptimisticUserMessage,
    clearConfirmedOptimisticMessages,
    clearOptimisticMessages,
    appendStreamToken,
    startStreaming,
    stopStreaming,
    setStreamingSources,
  } = useChatStore();

  // Queries
  const { data: sessions, isLoading: sessionsLoading } = useSessions();
  const { data: messages, isLoading: messagesLoading } = useMessages(activeSessionId);
  const { data: providers = [] } = useProviders();
  const { data: allDocuments = [] } = useAllDocuments();
  const invalidateMessages = useInvalidateMessages();
  const createMutation = useCreateSession();
  const renameMutation = useRenameSession();
  const deleteMutation = useDeleteSession();

  // Rename state
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const handleStartRename = useCallback((id: string, currentTitle: string) => {
    setRenamingId(id);
    setRenameValue(currentTitle);
  }, []);

  const handleConfirmRename = useCallback(() => {
    if (!renamingId) return;
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenamingId(null);
      return;
    }
    renameMutation.mutate(
      { id: renamingId, title: trimmed },
      {
        onSuccess: () => {
          setRenamingId(null);
          msgApi.success('会话已重命名');
        },
      },
    );
  }, [renamingId, renameValue, renameMutation, msgApi]);

  const handleCancelRename = useCallback(() => {
    setRenamingId(null);
  }, []);

  useEffect(() => {
    if (renamingId) {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }
  }, [renamingId]);

  // Auto-select first session
  useEffect(() => {
    if (!activeSessionId && sessions && sessions.length > 0) {
      setActiveSession(sessions[0].id);
    }
  }, [sessions, activeSessionId, setActiveSession]);

  const displayedMessages = useMemo(
    () => {
      const merged = [...(messages ?? []), ...optimisticMessages.filter((m) => m.session_id === activeSessionId)];
      const deduped = new Map(merged.map((message) => [message.id, message]));
      return Array.from(deduped.values()).sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      );
    },
    [messages, optimisticMessages, activeSessionId],
  );
  const latestAssistantMessageId = useMemo(
    () => [...displayedMessages].reverse().find((msg) => msg.role === 'assistant')?.id,
    [displayedMessages],
  );

  // Scroll to bottom on new messages or streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [displayedMessages, streamingContent]);

  useEffect(() => {
    if (messages?.length) {
      clearConfirmedOptimisticMessages(messages);
    }
  }, [messages, clearConfirmedOptimisticMessages]);

  // Current session info
  const activeSession = sessions?.find((s) => s.id === activeSessionId);
  const currentProvider = useMemo(
    () => providers.find((p) => p.id === activeSession?.provider_id),
    [providers, activeSession?.provider_id],
  );
  const sessionProviderMissing = useMemo(
    () => Boolean(activeSession && !currentProvider),
    [activeSession, currentProvider],
  );
  const currentProviderLabel = useMemo(() => {
    if (sessionProviderMissing) return '供应商已删除';
    if (!currentProvider) return '未配置供应商';
    if (currentProvider.provider_type === 'openai') return 'OpenAI';
    if (currentProvider.provider_type === 'claude') return 'Anthropic Claude';
    return 'OpenAI 兼容';
  }, [currentProvider, sessionProviderMissing]);
  const currentProviderRuntimeHint = useMemo(
    () =>
      sessionProviderMissing
        ? '这个会话绑定的 provider 已被删除。历史消息还能查看，但不能继续提问或重新生成。'
        : getProviderRuntimeHint(currentProvider),
    [currentProvider, sessionProviderMissing],
  );
  const documentNameMap = useMemo(
    () => new Map(allDocuments.map((doc) => [doc.id, doc.file_name])),
    [allDocuments],
  );
  const activeSessionDocumentNames = useMemo(() => {
    if (!activeSession || activeSession.scope_type !== 'single') return [];
    const ids = activeSession.document_ids?.length ? activeSession.document_ids : activeSession.document_id ? [activeSession.document_id] : [];
    return ids
      .map((id) => documentNameMap.get(id))
      .filter((name): name is string => !!name);
  }, [activeSession, documentNameMap]);
  const activeSessionDocumentSummary = useMemo(() => {
    if (activeSessionDocumentNames.length === 0) return '';
    if (activeSessionDocumentNames.length === 1) return activeSessionDocumentNames[0];
    return `${activeSessionDocumentNames[0]} 等${activeSessionDocumentNames.length}个文档`;
  }, [activeSessionDocumentNames]);
  const composerDisabled = isStreaming || sessionProviderMissing;

  // Create session
  const handleCreate = useCallback(
    (scope: ScopeType, providerId?: string, docIds?: string[]) => {
      createMutation.mutate(
        {
          scope_type: scope,
          provider_id: providerId,
          document_id: docIds?.[0],
          document_ids: docIds,
        },
        {
          onSuccess: (session) => {
            setActiveSession(session.id);
            setDialogOpen(false);
            msgApi.success('会话已创建');
          },
          onError: (error) => {
            msgApi.error(`创建会话失败：${getRequestErrorMessage(error, '请先检查模型供应商配置')}`);
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
    if (!content || !activeSessionId || isStreaming || sessionProviderMissing) return;

    setInputValue('');
    const tempId = addOptimisticUserMessage(activeSessionId, content);

    const abort = sendMessage(activeSessionId, content, {
      onToken: (token) => appendStreamToken(token),
      onAccepted: ({ userMessageId }) => {
        if (userMessageId) {
          commitOptimisticUserMessage(tempId, userMessageId);
        }
      },
      onDone: () => {
        stopStreaming();
        invalidateMessages(activeSessionId);
      },
      onError: (err) => {
        clearOptimisticMessages(activeSessionId);
        stopStreaming();
        invalidateMessages(activeSessionId);
        msgApi.error(`发送失败：${err.message}`);
      },
      onSources: (data) => setStreamingSources(data),
    });

    startStreaming(abort);
  }, [
    inputValue,
    activeSessionId,
    isStreaming,
    addOptimisticUserMessage,
    commitOptimisticUserMessage,
    clearConfirmedOptimisticMessages,
    clearOptimisticMessages,
    appendStreamToken,
    startStreaming,
    stopStreaming,
    invalidateMessages,
    setStreamingSources,
    msgApi,
    sessionProviderMissing,
  ]);

  const handleRegenerate = useCallback(
    (messageId: string) => {
      if (!activeSessionId || isStreaming || sessionProviderMissing) return;

      const abort = regenerateMessage(activeSessionId, messageId, {
        onToken: (token) => appendStreamToken(token),
        onDone: () => {
          stopStreaming();
          invalidateMessages(activeSessionId);
        },
        onError: (err) => {
          stopStreaming();
          invalidateMessages(activeSessionId);
          msgApi.error(`重新生成失败：${err.message}`);
        },
        onSources: (data) => setStreamingSources(data),
      });

      startStreaming(abort, { regeneratingMessageId: messageId });
    },
    [
      activeSessionId,
      isStreaming,
      appendStreamToken,
      stopStreaming,
      invalidateMessages,
      msgApi,
      setStreamingSources,
      startStreaming,
      sessionProviderMissing,
    ],
  );

  // Key handler
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Render ──

  return (
    <div className={styles.page}>
      {/* Mobile sidebar toggle */}
      <Button
        className={styles.mobileSidebarToggle}
        type="text"
        icon={<MenuOutlined />}
        onClick={() => setMobileSidebarOpen(true)}
      />
      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div className={styles.sidebarOverlay} onClick={() => setMobileSidebarOpen(false)} />
      )}
      {/* ══════ Sidebar ══════ */}
      <aside className={`${styles.sidebar} ${mobileSidebarOpen ? styles.sidebarMobileOpen : ''}`}>
        <div className={styles.sidebarHeader}>
          <span className={styles.sidebarTitle}>会话列表</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => setDialogOpen(true)}
            />
            <Button
              className={styles.mobileSidebarClose}
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={() => setMobileSidebarOpen(false)}
            />
          </div>
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
                onClick={() => { setActiveSession(s.id); setMobileSidebarOpen(false); }}
                onDoubleClick={() => handleStartRename(s.id, s.title)}
              >
                <div className={styles.sessionTop}>
                  {renamingId === s.id ? (
                    <input
                      ref={renameInputRef}
                      className={styles.sessionRenameInput}
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={handleConfirmRename}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleConfirmRename();
                        if (e.key === 'Escape') handleCancelRename();
                      }}
                      onClick={(e) => e.stopPropagation()}
                      maxLength={255}
                    />
                  ) : (
                    <span className={styles.sessionTitle}>{s.title}</span>
                  )}
                  <div className={styles.sessionActions}>
                    <Tooltip title="重命名">
                      <Button
                        type="text"
                        size="small"
                        className={styles.sessionActionBtn}
                        icon={<EditOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartRename(s.id, s.title);
                        }}
                      />
                    </Tooltip>
                    <Tooltip title="删除会话">
                      <Button
                        type="text"
                        size="small"
                        className={styles.sessionActionBtn}
                        icon={<DeleteOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSession(s.id);
                        }}
                      />
                    </Tooltip>
                  </div>
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
              <div className={styles.chatHeaderMeta}>
                <span className={styles.chatTitle}>{activeSession?.title}</span>
                <div className={styles.chatHeaderTags}>
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
                  {activeSession?.scope_type === 'single' && activeSessionDocumentNames.length > 0 && (
                    <Button
                      type="text"
                      size="small"
                      className={styles.docSummaryButton}
                      icon={<FileTextOutlined />}
                      onClick={() => setDocumentModalOpen(true)}
                    >
                      {activeSessionDocumentSummary}
                    </Button>
                  )}
                  <Tag color={sessionProviderMissing ? 'volcano' : currentProvider ? 'gold' : 'default'} className={styles.scopeTag}>
                    <ApiOutlined /> {currentProviderLabel}
                  </Tag>
                  {sessionProviderMissing && (
                    <Tag color="volcano" className={styles.scopeTag}>
                      <ExclamationCircleOutlined /> 无法继续对话
                    </Tag>
                  )}
                  {currentProvider && (
                    <Tag color="purple" className={styles.scopeTag}>
                      {currentProvider.model_name}
                    </Tag>
                  )}
                </div>
                <div className={styles.chatRuntimeHint}>{currentProviderRuntimeHint}</div>
              </div>
              <Button
                type="text"
                size="small"
                icon={<InfoCircleOutlined />}
                onClick={() => setProviderModalOpen(true)}
                disabled={!activeSession}
              >
                查看设置
              </Button>
            </div>

            {/* Messages */}
            <div className={styles.messages}>
              {messagesLoading ? (
                <div className={styles.messagesSkeleton}>
                  <Skeleton active avatar paragraph={{ rows: 2 }} />
                  <Skeleton active avatar paragraph={{ rows: 3 }} />
                </div>
              ) : displayedMessages.length === 0 && !isStreaming ? (
                <div className={styles.messagesEmpty}>
                  <RobotOutlined className={styles.messagesEmptyIcon} />
                  <p>在下方输入您的问题，开始智能问答</p>
                </div>
              ) : (
                <>
                  {displayedMessages.map((m) => (
                    <div key={m.id}>
                      {isStreaming && regeneratingMessageId === m.id ? (
                        <>
                          <MessageBubble
                            msg={{ role: 'assistant', content: streamingContent }}
                            isStreaming
                          />
                          {streamingSources && <SourcesPanel sources={streamingSources} />}
                        </>
                      ) : (
                        <>
                          <MessageBubble msg={m} />
                          {m.role === 'assistant' && (
                            <div className={styles.msgActions}>
                              <Tooltip
                                title={
                                  sessionProviderMissing
                                    ? '当前会话绑定的 provider 已删除，无法重新生成'
                                    : m.id === latestAssistantMessageId
                                      ? '重新生成这条回复'
                                      : '目前只支持重新生成最后一条回复'
                                }
                              >
                                <Button
                                  type="text"
                                  size="small"
                                  icon={<ReloadOutlined />}
                                  onClick={() => handleRegenerate(m.id)}
                                  disabled={isStreaming || sessionProviderMissing || m.id !== latestAssistantMessageId}
                                >
                                  重新生成
                                </Button>
                              </Tooltip>
                            </div>
                          )}
                          {m.role === 'assistant' && m.sources && (
                            <SourcesPanel sources={m.sources} />
                          )}
                        </>
                      )}
                    </div>
                  ))}
                  {isStreaming && !regeneratingMessageId && streamingContent && (
                    <MessageBubble
                      msg={{ role: 'assistant', content: streamingContent }}
                      isStreaming
                    />
                  )}
                  {isStreaming && !regeneratingMessageId && streamingSources && <SourcesPanel sources={streamingSources} />}
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
                placeholder={sessionProviderMissing ? '当前会话绑定的 provider 已删除，请新建会话继续' : '输入您的问题...'}
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={composerDisabled}
                className={styles.chatInput}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!inputValue.trim() || composerDisabled}
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
        creating={createMutation.isPending}
        providers={providers}
        documents={allDocuments}
      />

      <Modal
        title="当前会话模型设置"
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        footer={null}
      >
        {currentProvider ? (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="供应商">{currentProviderLabel}</Descriptions.Item>
            <Descriptions.Item label="聊天模型">{currentProvider.model_name}</Descriptions.Item>
            <Descriptions.Item label="Embedding 模型">
              {currentProvider.provider_type === 'claude'
                ? '不支持'
                : currentProvider.enable_embedding
                  ? currentProvider.embedding_model || '未填写'
                  : '已关闭'}
            </Descriptions.Item>
            <Descriptions.Item label="检索策略提示">{currentProviderRuntimeHint}</Descriptions.Item>
            <Descriptions.Item label="Base URL">{currentProvider.base_url}</Descriptions.Item>
            <Descriptions.Item label="API Key">{currentProvider.api_key || '未设置'}</Descriptions.Item>
            <Descriptions.Item label="Temperature">{currentProvider.temperature}</Descriptions.Item>
            <Descriptions.Item label="Max Tokens">{currentProvider.max_tokens}</Descriptions.Item>
            <Descriptions.Item label="超时">{currentProvider.timeout_seconds}s</Descriptions.Item>
          </Descriptions>
        ) : sessionProviderMissing ? (
          <div className={styles.noDocsHint}>
            <ApiOutlined /> 这个会话绑定的 provider 已被删除。历史消息还能查看，但不能继续提问或重新生成。
          </div>
        ) : (
          <div className={styles.noDocsHint}>
            <ApiOutlined /> 当前会话还没有可用的供应商配置
          </div>
        )}
      </Modal>

      <Modal
        title="当前会话文档范围"
        open={documentModalOpen}
        onCancel={() => setDocumentModalOpen(false)}
        footer={null}
      >
        {activeSessionDocumentNames.length > 0 ? (
          <div className={styles.documentList}>
            {activeSessionDocumentNames.map((name) => (
              <div key={name} className={styles.documentListItem}>
                <FileTextOutlined />
                <span>{name}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.noDocsHint}>
            <FileTextOutlined /> 当前会话没有选中文档
          </div>
        )}
      </Modal>
    </div>
  );
}
