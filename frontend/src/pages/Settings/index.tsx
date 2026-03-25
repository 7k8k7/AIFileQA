import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Button,
  Form,
  Input,
  InputNumber,
  Select,
  Modal,
  App,
  Skeleton,
  Tooltip,
  Spin,
  Switch,
  Tag,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  StarOutlined,
  StarFilled,
  ApiOutlined,
  LinkOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import {
  useProviders,
  useProvider,
  useCreateProvider,
  useUpdateProvider,
  useTestProvider,
  useSetDefaultProvider,
  useDeleteProvider,
} from '../../hooks';
import type { ProviderConfig, ProviderType, ProviderTestResult } from '../../types';
import styles from './Settings.module.css';

// ── Constants ──

const PROVIDER_TYPES: { value: ProviderType; label: string; icon: string }[] = [
  { value: 'openai', label: 'OpenAI', icon: 'O' },
  { value: 'claude', label: 'Anthropic Claude', icon: 'A' },
  { value: 'openai_compatible', label: 'OpenAI 兼容', icon: 'C' },
];

const PROVIDER_COLORS: Record<ProviderType, string> = {
  openai: '#10A37F',
  claude: '#D97B00',
  openai_compatible: '#6C5CE7',
};

interface ProviderCapabilityCopy {
  chatLabel: string;
  embeddingLabel: string;
  embeddingHint: string;
  fallbackHint: string;
  switchHint: string;
}

function getProviderCapabilityCopy(providerType: ProviderType, enableEmbedding: boolean): ProviderCapabilityCopy {
  if (providerType === 'openai') {
    return {
      chatLabel: '支持聊天生成',
      embeddingLabel: enableEmbedding ? '支持 Embedding 检索' : 'Embedding 已关闭',
      embeddingHint: 'OpenAI 适合将聊天模型和 Embedding 模型分开配置。',
      fallbackHint: enableEmbedding
        ? '若 Embedding 调用失败，系统会自动退回关键词检索。'
        : '当前已关闭 Embedding，问答时会直接使用关键词检索。',
      switchHint: '开启后会优先用当前会话绑定的供应商做向量检索。',
    };
  }
  if (providerType === 'claude') {
    return {
      chatLabel: '支持聊天生成',
      embeddingLabel: '不支持 Embedding',
      embeddingHint: 'Claude 当前不提供本项目使用的 Embedding 接口。',
      fallbackHint: 'Claude 会始终退回关键词检索，但聊天回答仍然使用 Claude 模型。',
      switchHint: 'Claude 当前固定使用关键词检索，因此这里不可开启。',
    };
  }
  return {
    chatLabel: '支持兼容聊天接口',
    embeddingLabel: enableEmbedding ? '按兼容接口尝试 Embedding' : 'Embedding 已关闭',
    embeddingHint: '只有你的兼容服务真的支持 /v1/embeddings 时，Embedding 才会生效。',
    fallbackHint: enableEmbedding
      ? '如果本地或兼容服务不支持 Embedding，系统会自动退回关键词检索。'
      : '当前未启用 Embedding，问答时会直接使用关键词检索。',
    switchHint: '适合本地模型；若服务不支持 Embedding，也不会阻塞问答。',
  };
}

function maskApiKey(key: string): string {
  if (!key) return '';
  if (key.length <= 8) return '****';
  return `${key.slice(0, 3)}****${key.slice(-4)}`;
}

// ── Provider Form ──

interface ProviderFormValues {
  provider_type: ProviderType;
  base_url: string;
  model_name: string;
  api_key: string;
  embedding_model: string;
  enable_embedding: boolean;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
}

function getProviderDefaults(providerType: ProviderType): Pick<ProviderFormValues, 'base_url' | 'model_name' | 'enable_embedding' | 'embedding_model'> {
  if (providerType === 'openai') {
    return {
      base_url: 'https://api.openai.com',
      model_name: 'gpt-4o',
      enable_embedding: true,
      embedding_model: 'text-embedding-3-small',
    };
  }
  if (providerType === 'claude') {
    return {
      base_url: 'https://api.anthropic.com',
      model_name: 'claude-sonnet',
      enable_embedding: false,
      embedding_model: '',
    };
  }
  return {
    base_url: '',
    model_name: 'local-model',
    enable_embedding: false,
    embedding_model: '',
  };
}

const DEFAULT_PROVIDER_VALUES: ProviderFormValues = {
  provider_type: 'openai',
  base_url: getProviderDefaults('openai').base_url,
  model_name: getProviderDefaults('openai').model_name,
  api_key: '',
  embedding_model: getProviderDefaults('openai').embedding_model,
  enable_embedding: getProviderDefaults('openai').enable_embedding,
  temperature: 0.7,
  max_tokens: 4096,
  timeout_seconds: 30,
};

function ProviderForm({
  initial,
  onSave,
  onCancel,
  loading,
}: {
  initial?: ProviderConfig;
  onSave: (values: ProviderFormValues) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [form] = Form.useForm<ProviderFormValues>();
  const providerType = Form.useWatch('provider_type', form) ?? initial?.provider_type ?? 'openai';
  const enableEmbedding = Form.useWatch('enable_embedding', form) ?? initial?.enable_embedding ?? false;
  const capabilityCopy = getProviderCapabilityCopy(providerType, enableEmbedding);
  const providerDefaults = getProviderDefaults(providerType);

  useEffect(() => {
    form.resetFields();
    form.setFieldsValue(
      initial
        ? {
            provider_type: initial.provider_type,
            base_url: initial.base_url,
            model_name: initial.model_name,
            api_key: initial.api_key,
            embedding_model: initial.embedding_model,
            enable_embedding: initial.enable_embedding,
            temperature: initial.temperature,
            max_tokens: initial.max_tokens,
            timeout_seconds: initial.timeout_seconds,
          }
        : DEFAULT_PROVIDER_VALUES,
    );
  }, [form, initial]);

  return (
    <div className={styles.formWrap}>
      <Form
        form={form}
        layout="vertical"
        initialValues={DEFAULT_PROVIDER_VALUES}
        onFinish={onSave}
        size="middle"
      >
        <div className={styles.formGrid}>
          <Form.Item
            name="provider_type"
            label="供应商类型"
            rules={[{ required: true, message: '请选择供应商' }]}
          >
            <Select
              options={PROVIDER_TYPES.map((t) => ({
                value: t.value,
                label: t.label,
              }))}
              onChange={(val: ProviderType) => {
                const defaults = getProviderDefaults(val);
                form.setFieldsValue({
                  base_url: defaults.base_url,
                  model_name: defaults.model_name,
                  enable_embedding: defaults.enable_embedding,
                  embedding_model: defaults.embedding_model,
                });
              }}
            />
          </Form.Item>

          <Form.Item
            name="model_name"
            label="聊天模型"
            rules={[{ required: true, message: '请输入模型名称' }]}
            extra="这里配置当前 provider 用于聊天生成的模型。"
          >
            <Input placeholder={providerDefaults.model_name} />
          </Form.Item>
        </div>

        <div className={styles.capabilityPanel}>
          <div className={styles.capabilityHeader}>当前能力说明</div>
          <div className={styles.capabilityTags}>
            <Tag color="blue">{capabilityCopy.chatLabel}</Tag>
            <Tag color={providerType === 'claude' ? 'orange' : enableEmbedding ? 'green' : 'default'}>
              {capabilityCopy.embeddingLabel}
            </Tag>
          </div>
          <div className={styles.capabilityText}>{capabilityCopy.embeddingHint}</div>
          <div className={styles.capabilityText}>{capabilityCopy.fallbackHint}</div>
        </div>

        <Form.Item
          name="base_url"
          label="Base URL"
          rules={[{ required: true, message: '请输入 Base URL' }]}
        >
          <Input placeholder="https://api.openai.com" />
        </Form.Item>

        <Form.Item
          name="api_key"
          label="API Key"
          rules={[
            {
              validator: async (_, value: string | undefined) => {
                if (providerType !== 'openai_compatible' && !value?.trim()) {
                  throw new Error('当前供应商必须填写 API Key');
                }
              },
            },
          ]}
          extra={
            providerType === 'openai_compatible'
              ? 'OpenAI 兼容接口在连接本地模型时可留空。'
              : '当前供应商必须填写 API Key，编辑已有 provider 时会回显已保存的 key。'
          }
        >
          <Input.Password
            placeholder={
              providerType === 'openai_compatible'
                ? '本地模型可留空，远程兼容接口请填写'
                : 'sk-...'
            }
            visibilityToggle
          />
        </Form.Item>

        <div className={styles.formGrid}>
          <Form.Item
            name="enable_embedding"
            label="启用 Embedding"
            valuePropName="checked"
            extra={capabilityCopy.switchHint}
          >
            <Switch
              checkedChildren="开启"
              unCheckedChildren="关闭"
              disabled={providerType === 'claude'}
            />
          </Form.Item>

          <Form.Item
            name="embedding_model"
            label="Embedding 模型"
            rules={[
              {
                validator: async (_, value: string | undefined) => {
                  if (providerType !== 'claude' && enableEmbedding && !value?.trim()) {
                    throw new Error('启用 Embedding 时必须填写 Embedding Model');
                  }
                },
              },
            ]}
            extra={
              providerType === 'openai_compatible'
                ? '本地兼容服务若支持 /v1/embeddings，请填写实际可用的 embedding 模型名；否则会自动退回关键词检索。'
                : '建议和聊天模型分开配置，避免把聊天模型直接用于 Embedding。'
            }
          >
            <Input
              placeholder={
                providerType === 'openai'
                  ? 'text-embedding-3-small'
                  : providerType === 'openai_compatible'
                    ? '例如 bge-m3 / nomic-embed-text'
                    : 'Claude 不支持'
              }
              disabled={providerType === 'claude' || !enableEmbedding}
            />
          </Form.Item>
        </div>

        <div className={styles.formGrid3}>
          <Form.Item
            name="temperature"
            label="Temperature"
            rules={[{ required: true }]}
          >
            <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="max_tokens"
            label="Max Tokens"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={128000} step={1024} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="timeout_seconds"
            label="超时 (秒)"
            rules={[{ required: true }]}
          >
            <InputNumber min={5} max={300} style={{ width: '100%' }} />
          </Form.Item>
        </div>

        <div className={styles.formActions}>
          <Button onClick={onCancel}>取消</Button>
          <Button type="primary" htmlType="submit" loading={loading}>
            {initial ? '保存修改' : '添加供应商'}
          </Button>
        </div>
      </Form>
    </div>
  );
}

// ── Provider Card ──

function ProviderCard({
  provider,
  onEdit,
  onTest,
  onSetDefault,
  onDelete,
  testState,
}: {
  provider: ProviderConfig;
  onEdit: () => void;
  onTest: () => void;
  onSetDefault: () => void;
  onDelete: () => void;
  testState?: { loading: boolean; result?: ProviderTestResult };
}) {
  const color = PROVIDER_COLORS[provider.provider_type];
  const typeInfo = PROVIDER_TYPES.find((t) => t.value === provider.provider_type);
  const capabilityCopy = getProviderCapabilityCopy(provider.provider_type, provider.enable_embedding);
  const verificationLabel = provider.last_test_success ? '连接已验证' : '未验证或最近测试失败';
  const isTesting = !!testState?.loading;

  return (
    <div className={styles.providerCard}>
      <div className={styles.providerMain}>
        <div className={styles.providerInfo}>
          <div
            className={styles.providerIcon}
            style={{ background: `${color}20`, color }}
          >
            {typeInfo?.icon ?? 'P'}
          </div>
          <div className={styles.providerMeta}>
            <div className={styles.providerName}>
              {typeInfo?.label}
              {provider.is_default && (
                <span className={styles.defaultBadge}>
                  <StarFilled /> 默认
                </span>
              )}
            </div>
            <div className={styles.providerModel}>{provider.model_name}</div>
          </div>
        </div>

        <div className={styles.providerActions}>
          {/* Test connection */}
          {isTesting ? (
            <span className={styles.testPending}>
              <Spin size="small" /> 正在测试连接...
            </span>
          ) : testState?.result ? (
            <span
              className={
                testState.result.success
                  ? styles.testSuccess
                  : styles.testError
              }
            >
              {testState.result.success ? (
                <><CheckCircleOutlined /> 连接成功</>
              ) : (
                <><ExclamationCircleOutlined /> {testState.result.message}</>
              )}
            </span>
          ) : null}

          <Tooltip title="测试连接">
            <Button
              type="text"
              size="small"
              icon={<ThunderboltOutlined />}
              onClick={onTest}
              loading={testState?.loading}
            />
          </Tooltip>

          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={onEdit}
              disabled={isTesting}
            />
          </Tooltip>

          {!provider.is_default && (
            <Tooltip title="设为默认">
              <Button
                type="text"
                size="small"
                icon={<StarOutlined />}
                onClick={onSetDefault}
                disabled={!provider.last_test_success || isTesting}
              />
            </Tooltip>
          )}

          <Tooltip title={provider.is_default ? '默认供应商不可删除' : '删除'}>
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={onDelete}
              disabled={provider.is_default || isTesting}
            />
          </Tooltip>
        </div>
      </div>

      <div className={styles.providerDetails}>
        <span className={styles.detailItem}>
          <LinkOutlined /> {provider.base_url}
        </span>
        <span className={styles.detailItem}>
          Key: {maskApiKey(provider.api_key)}
        </span>
        <span className={styles.detailItem}>
          聊天: {provider.model_name}
        </span>
        <span className={styles.detailItem}>
          <Tag color={provider.last_test_success ? 'green' : 'default'}>
            {verificationLabel}
          </Tag>
          {provider.last_test_message ? ` ${provider.last_test_message}` : ''}
        </span>
        <span className={styles.detailItem}>
          Embedding: {provider.provider_type === 'claude' ? '不支持' : provider.enable_embedding ? provider.embedding_model : '已关闭'}
        </span>
        <span className={styles.detailItem}>
          回退: {capabilityCopy.fallbackHint}
        </span>
        <span className={styles.detailItem}>
          T={provider.temperature} · {provider.max_tokens} tokens · {provider.timeout_seconds}s
        </span>
      </div>
    </div>
  );
}

// ── Main Component ──

export default function SettingsPage() {
  const { message: msgApi } = App.useApp();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [testStates, setTestStates] = useState<
    Record<string, { loading: boolean; result?: ProviderTestResult }>
  >({});
  const testTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Cleanup test timers on unmount
  useEffect(() => {
    return () => {
      Object.values(testTimersRef.current).forEach(clearTimeout);
    };
  }, []);

  const { data: providers, isLoading } = useProviders();
  const { data: editingProvider, isLoading: editingLoading } = useProvider(editingId);
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const testMutation = useTestProvider();
  const setDefaultMutation = useSetDefaultProvider();
  const deleteMutation = useDeleteProvider();
  const editingProviderForForm =
    editingProvider && editingId === editingProvider.id ? editingProvider : undefined;
  const isEditingProviderLoading = !!editingId && editingLoading && !editingProviderForForm;

  // Add provider
  const handleAdd = useCallback(
    (values: ProviderFormValues) => {
      createMutation.mutate(
        { ...values, is_default: false },
        {
          onSuccess: () => {
            msgApi.success('供应商已添加');
            setAdding(false);
          },
          onError: (err) => msgApi.error(`添加失败：${err.message}`),
        },
      );
    },
    [createMutation, msgApi],
  );

  // Edit provider
  const handleEdit = useCallback(
    (id: string, values: ProviderFormValues) => {
      const data: Record<string, unknown> = { ...values };
      updateMutation.mutate(
        { id, data },
        {
          onSuccess: () => {
            msgApi.success('供应商已更新');
            setEditingId(null);
          },
          onError: (err) => msgApi.error(`更新失败：${err.message}`),
        },
      );
    },
    [updateMutation, msgApi],
  );

  // Test connection
  const handleTest = useCallback(
    (id: string) => {
      const currentProvider = providers?.find((item) => item.id === id);
      // Clear any existing timer for this provider
      if (testTimersRef.current[id]) {
        clearTimeout(testTimersRef.current[id]);
        delete testTimersRef.current[id];
      }
      setTestStates((s) => ({ ...s, [id]: { loading: true } }));
      msgApi.open({
        key: `provider-test-${id}`,
        type: 'loading',
        content: '正在测试连接...',
        duration: 0,
      });
      testMutation.mutate(id, {
        onSuccess: (result) => {
          setTestStates((s) => ({ ...s, [id]: { loading: false, result } }));
          msgApi.open({
            key: `provider-test-${id}`,
            type: result.success ? 'success' : 'error',
            content: result.success ? '连接成功，已更新验证状态' : `连接失败：${result.message}`,
            duration: 2,
          });
          // Clear result after 5s
          testTimersRef.current[id] = setTimeout(() => {
            setTestStates((s) => {
              const next = { ...s };
              delete next[id];
              return next;
            });
            delete testTimersRef.current[id];
          }, 5000);
        },
        onError: (err) => {
          msgApi.open({
            key: `provider-test-${id}`,
            type: 'error',
            content: `连接失败：${err.message}`,
            duration: 2,
          });
          setTestStates((s) => ({
            ...s,
            [id]: currentProvider
              ? {
                  loading: false,
                  result: {
                    success: false,
                    message: err.message,
                    provider: currentProvider,
                  },
                }
              : { loading: false },
          }));
        },
      });
    },
    [msgApi, providers, testMutation],
  );

  // Set default
  const handleSetDefault = useCallback(
    (id: string) => {
      setDefaultMutation.mutate(id, {
        onSuccess: () => msgApi.success('已设为默认供应商'),
      });
    },
    [setDefaultMutation, msgApi],
  );

  // Delete
  const handleDelete = useCallback(
    (provider: ProviderConfig) => {
      if (provider.is_default) {
        msgApi.warning('无法删除默认供应商，请先设置其他供应商为默认');
        return;
      }
      Modal.confirm({
        title: '删除供应商',
        icon: <ExclamationCircleOutlined />,
        content: `确定要删除「${PROVIDER_TYPES.find((t) => t.value === provider.provider_type)?.label}」配置吗？删除后，引用它的历史会话还能查看记录，但不能继续发送消息或重新生成回复。`,
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () =>
          deleteMutation.mutateAsync(provider.id).then(() => {
            msgApi.success('供应商已删除');
          }),
      });
    },
    [deleteMutation, msgApi],
  );

  // ── Render ──

  return (
    <div className={styles.page}>
      <div className={styles.content}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>LLM 配置</h1>
            <p className={styles.desc}>管理大语言模型的 API 连接，支持多个供应商并行配置。</p>
          </div>
          {!adding && (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => { setAdding(true); setEditingId(null); }}
            >
              添加供应商
            </Button>
          )}
        </div>

        {/* Add form */}
        {adding && (
          <ProviderForm
            onSave={handleAdd}
            onCancel={() => setAdding(false)}
            loading={createMutation.isPending}
          />
        )}

        {/* Loading */}
        {isLoading ? (
          <div className={styles.skeleton}>
            <Skeleton active paragraph={{ rows: 3 }} />
            <Skeleton active paragraph={{ rows: 3 }} />
          </div>
        ) : !providers || providers.length === 0 ? (
          /* Empty state */
          <div className={styles.emptyState}>
            <ApiOutlined className={styles.emptyIcon} />
            <p className={styles.emptyTitle}>还没有配置</p>
            <p className={styles.emptyDesc}>添加您的第一个 AI 供应商以启用智能问答</p>
            {!adding && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setAdding(true)}
              >
                添加供应商
              </Button>
            )}
          </div>
        ) : (
          /* Provider list */
          <div className={styles.providerList}>
            {providers.map((p) =>
              editingId === p.id ? (
                isEditingProviderLoading ? (
                  <div key={p.id} className={styles.formWrap}>
                    <Skeleton active paragraph={{ rows: 6 }} />
                  </div>
                ) : (
                  <ProviderForm
                    key={p.id}
                    initial={editingProviderForForm}
                    onSave={(values) => handleEdit(p.id, values)}
                    onCancel={() => setEditingId(null)}
                    loading={updateMutation.isPending || editingLoading}
                  />
                )
              ) : (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  onEdit={() => { setEditingId(p.id); setAdding(false); }}
                  onTest={() => handleTest(p.id)}
                  onSetDefault={() => handleSetDefault(p.id)}
                  onDelete={() => handleDelete(p)}
                  testState={testStates[p.id]}
                />
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
