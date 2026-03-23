import { MessageOutlined } from '@ant-design/icons';
import styles from './Chat.module.css';

export default function ChatPage() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>智能问答</h1>
      </div>
      <div className={styles.placeholder}>
        <MessageOutlined className={styles.placeholderIcon} />
        <p>智能问答页面 — 阶段 D 实现</p>
      </div>
    </div>
  );
}
