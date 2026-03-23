import { SettingOutlined } from '@ant-design/icons';
import styles from './Settings.module.css';

export default function SettingsPage() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>系统设置</h1>
      </div>
      <div className={styles.placeholder}>
        <SettingOutlined className={styles.placeholderIcon} />
        <p>系统设置页面 — 阶段 E 实现</p>
      </div>
    </div>
  );
}
