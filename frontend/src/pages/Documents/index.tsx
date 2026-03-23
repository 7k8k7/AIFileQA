import { FileTextOutlined } from '@ant-design/icons';
import styles from './Documents.module.css';

export default function DocumentsPage() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>文档管理</h1>
      </div>
      <div className={styles.placeholder}>
        <FileTextOutlined className={styles.placeholderIcon} />
        <p>文档管理页面 — 阶段 C 实现</p>
      </div>
    </div>
  );
}
