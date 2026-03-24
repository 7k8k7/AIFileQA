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
  useCreateProvider,
  useUpdateProvider,
  useTestProvider,
  useSetDefaultProvider,
  useDeleteProvider,
} from '../../hooks';
import type { ProviderConfig, ProviderType } from '../../types';
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
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
}

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

  const defaultUrls: Record<ProviderType, string> = {
    openai: 'https://api.openai.com',
    claude: 'https://api.anthropic.com',
    openai_compatible: '',
  };

  return (
    <div className={styles.formWrap}>
      <Form
        form={form}
        layout="vertical"
        initialValues={
          initial
            ? {
                provider_type: initial.provider_type,
                base_url: initial.base_url,
                model_name: initial.model_name,
                api_key: initial.api_key,
                temperature: initial.temperature,
                max_tokens: initial.max_tokens,
                timeout_seconds: initial.timeout_seconds,
              }
            : {
                provider_type: 'openai',
                base_url: 'https://api.openai.com',
                model_name: 'gpt-4o',
                temperature: 0.7,
                max_tokens: 4096,
                timeout_seconds: 30,
              }
        }
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
                form.setFieldsValue({ base_url: defaultUrls[val] });
              }}
            />
          </Form.Item>

          <Form.Item
            name="model_name"
            label="模型名称"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="gpt-4o" />
          </Form.Item>
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
          rules={[]}
          extra="本地部署模型（如 Ollama）可留空"
        >
          <Input.Password placeholder="sk-...（本地模型可留空）" visibilityToggle />
        </Form.Item>

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
  testState?: { loading: boolean; result?: { success: boolean; message: string } };
}) {
  const color = PROVIDER_COLORS[provider.provider_type];
  const typeInfo = PROVIDER_TYPES.find((t) => t.value === provider.provider_type);

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
          {testState?.loading ? (
            <Spin size="small" />
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
            />
          </Tooltip>

          {!provider.is_default && (
            <Tooltip title="设为默认">
              <Button
                type="text"
                size="small"
                icon={<StarOutlined />}
                onClick={onSetDefault}
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
              disabled={provider.is_default}
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
    Record<string, { loading: boolean; result?: { success: boolean; message: string } }>
  >({});
  const testTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Cleanup test timers on unmount
  useEffect(() => {
    return () => {
      Object.values(testTimersRef.current).forEach(clearTimeout);
    };
  }, []);

  const { data: providers, isLoading } = useProviders();
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const testMutation = useTestProvider();
  const setDefaultMutation = useSetDefaultProvider();
  const deleteMutation = useDeleteProvider();

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
      // Clear any existing timer for this provider
      if (testTimersRef.current[id]) {
        clearTimeout(testTimersRef.current[id]);
        delete testTimersRef.current[id];
      }
      setTestStates((s) => ({ ...s, [id]: { loading: true } }));
      testMutation.mutate(id, {
        onSuccess: (result) => {
          setTestStates((s) => ({ ...s, [id]: { loading: false, result } }));
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
          setTestStates((s) => ({
            ...s,
            [id]: { loading: false, result: { success: false, message: err.message } },
          }));
        },
      });
    },
    [testMutation],
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
        content: `确定要删除「${PROVIDER_TYPES.find((t) => t.value === provider.provider_type)?.label}」配置吗？`,
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
                <ProviderForm
                  key={p.id}
                  initial={p}
                  onSave={(values) => handleEdit(p.id, values)}
                  onCancel={() => setEditingId(null)}
                  loading={updateMutation.isPending}
                />
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
