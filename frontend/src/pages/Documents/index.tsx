import { useState, useCallback, useMemo } from 'react';
import {
  Table,
  Button,
  Input,
  Upload,
  Tag,
  Modal,
  App,
  Tooltip,
  Dropdown,
  Skeleton,
} from 'antd';
import type { UploadProps, MenuProps } from 'antd';
import {
  UploadOutlined,
  SearchOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileMarkdownOutlined,
  InboxOutlined,
  MoreOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  useDocumentsWithPolling,
  useUploadDocument,
  useDeleteDocument,
} from '../../hooks';
import type { Document, DocumentStatus } from '../../types';
import styles from './Documents.module.css';

// ── Helpers ──

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function FileIcon({ ext }: { ext: string }) {
  const cls = styles.fileIcon;
  switch (ext) {
    case '.pdf':
      return <span className={`${cls} ${styles.fileIconPdf}`}><FilePdfOutlined /></span>;
    case '.docx':
    case '.doc':
      return <span className={`${cls} ${styles.fileIconDoc}`}><FileWordOutlined /></span>;
    case '.md':
    case '.markdown':
      return <span className={`${cls} ${styles.fileIconMd}`}><FileMarkdownOutlined /></span>;
    default:
      return <span className={`${cls} ${styles.fileIconTxt}`}><FileTextOutlined /></span>;
  }
}

const STATUS_MAP: Record<DocumentStatus, { color: string; label: string }> = {
  '上传成功': { color: 'default', label: '上传成功' },
  '解析中': { color: 'processing', label: '解析中' },
  '可用': { color: 'success', label: '已完成' },
  '解析失败': { color: 'error', label: '解析失败' },
};

// ── Accepted file types ──

const ACCEPT = '.pdf,.docx,.doc,.txt,.md,.markdown';
const MAX_SIZE = 50 * 1024 * 1024; // 50MB

// ── Component ──

export default function DocumentsPage() {
  const { message: msg } = App.useApp();
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = useDocumentsWithPolling({ keyword, page, page_size: pageSize });
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();

  // Upload handler
  const handleUpload: UploadProps['customRequest'] = useCallback(
    (options: Parameters<NonNullable<UploadProps['customRequest']>>[0]) => {
      const file = options.file as File;
      if (file.size > MAX_SIZE) {
        msg.error(`文件 ${file.name} 超过 50MB 限制`);
        options.onError?.(new Error('文件过大'));
        return;
      }
      uploadMutation.mutate(file, {
        onSuccess: () => {
          msg.success(`${file.name} 上传成功，可立即用于问答`);
          options.onSuccess?.({});
        },
        onError: (err) => {
          msg.error(`上传失败：${err.message}`);
          options.onError?.(err as Error);
        },
      });
    },
    [uploadMutation, msg],
  );

  // Delete handler
  const handleDelete = useCallback(
    (doc: Document) => {
      Modal.confirm({
        title: '确认删除',
        icon: <ExclamationCircleOutlined />,
        content: `确定要删除「${doc.file_name}」吗？删除后无法恢复。`,
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        onOk: () =>
          deleteMutation.mutateAsync(doc.id).then(() => {
            msg.success('文档已删除');
          }),
      });
    },
    [deleteMutation, msg],
  );

  // Table columns — memoized to avoid unnecessary Table re-renders
  const columns: ColumnsType<Document> = useMemo(
    () => [
      {
        title: '文件名',
        dataIndex: 'file_name',
        key: 'file_name',
        render: (name: string, record) => (
          <div className={styles.fileName}>
            <FileIcon ext={record.file_ext} />
            <span className={styles.fileNameText}>{name}</span>
          </div>
        ),
      },
      {
        title: '大小',
        dataIndex: 'file_size',
        key: 'file_size',
        width: 100,
        render: (size: number) => (
          <span className={styles.fileSize}>{formatFileSize(size)}</span>
        ),
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        render: (status: DocumentStatus, record) => {
          const cfg = STATUS_MAP[status];
          return (
            <Tooltip title={record.error_message}>
              <Tag color={cfg.color}>{cfg.label}</Tag>
            </Tooltip>
          );
        },
      },
      {
        title: '上传时间',
        dataIndex: 'uploaded_at',
        key: 'uploaded_at',
        width: 140,
        render: (t: string) => <span className={styles.fileDate}>{formatDate(t)}</span>,
      },
      {
        title: '',
        key: 'actions',
        width: 48,
        render: (_, record) => {
          const items: MenuProps['items'] = [
            {
              key: 'delete',
              icon: <DeleteOutlined />,
              label: '删除',
              danger: true,
              onClick: () => handleDelete(record),
            },
          ];
          return (
            <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
              <Button type="text" size="small" icon={<MoreOutlined />} />
            </Dropdown>
          );
        },
      },
    ],
    [handleDelete],
  );

  // ── Empty state ──
  if (!isLoading && data && data.total === 0 && !keyword) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <h1 className={styles.title}>文档管理</h1>
        </div>
        <div className={styles.emptyState}>
          <InboxOutlined className={styles.emptyIcon} />
          <p className={styles.emptyTitle}>还没有文档</p>
          <p className={styles.emptyDesc}>上传文档后即可开始智能问答</p>
          <Upload
            accept={ACCEPT}
            showUploadList={false}
            customRequest={handleUpload}
            multiple
          >
            <Button type="primary" icon={<UploadOutlined />} size="large">
              上传文档
            </Button>
          </Upload>
        </div>
      </div>
    );
  }

  // ── Skeleton loading ──
  if (isLoading && !data) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <h1 className={styles.title}>文档管理</h1>
        </div>
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <h1 className={styles.title}>文档管理</h1>
          <Upload
            accept={ACCEPT}
            showUploadList={false}
            customRequest={handleUpload}
            multiple
          >
            <Button type="primary" icon={<UploadOutlined />}>
              上传文档
            </Button>
          </Upload>
        </div>
      </div>

      {/* ── Upload Zone ── */}
      <Upload.Dragger
        accept={ACCEPT}
        showUploadList={false}
        customRequest={handleUpload}
        multiple
        className={styles.uploadZone}
      >
        <p className={styles.uploadIcon}><InboxOutlined /></p>
        <p className={styles.uploadText}>
          拖拽文件到此处，或 <span className={styles.uploadLink}>点击选择</span>
        </p>
        <p className={styles.uploadHint}>支持 PDF、DOCX、TXT、Markdown，单文件最大 50MB</p>
      </Upload.Dragger>

      {/* ── Search ── */}
      <div className={styles.toolbar}>
        <Input
          placeholder="搜索文档名称..."
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => {
            setKeyword(e.target.value);
            setPage(1);
          }}
          allowClear
          className={styles.searchInput}
        />
        <span className={styles.docCount}>
          共 {data?.total ?? 0} 个文档
        </span>
      </div>

      {/* ── Table ── */}
      <div className={styles.tableWrap}>
        <Table<Document>
          columns={columns}
          dataSource={data?.items}
          rowKey="id"
          size="middle"
          pagination={
            (data?.total ?? 0) > pageSize
              ? {
                  current: page,
                  pageSize,
                  total: data?.total,
                  onChange: setPage,
                  showSizeChanger: false,
                }
              : false
          }
          loading={isLoading}
          locale={{ emptyText: '没有匹配的文档' }}
        />
      </div>
    </div>
  );
}
