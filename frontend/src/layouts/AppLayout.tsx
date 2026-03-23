import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  FileTextOutlined,
  MessageOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import styles from './AppLayout.module.css';

const navItems = [
  { path: '/documents', label: '文档管理', icon: <FileTextOutlined /> },
  { path: '/chat', label: '智能问答', icon: <MessageOutlined /> },
  { path: '/settings', label: '系统设置', icon: <SettingOutlined /> },
];

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className={styles.root}>
      {/* ── Glassmorphism Top Nav ── */}
      <nav className={styles.nav}>
        <div className={styles.navInner}>
          {/* Logo */}
          <div className={styles.logo} onClick={() => navigate('/documents')}>
            <span className={styles.logoIcon}>D</span>
            <span className={styles.logoText}>DocQA</span>
          </div>

          {/* Nav Links */}
          <ul className={styles.links}>
            {navItems.map((item) => (
              <li key={item.path}>
                <button
                  className={`${styles.link} ${
                    location.pathname.startsWith(item.path)
                      ? styles.linkActive
                      : ''
                  }`}
                  onClick={() => navigate(item.path)}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>

          {/* Spacer for right side actions (future: theme toggle, user menu) */}
          <div className={styles.actions} />
        </div>
      </nav>

      {/* ── Page Content ── */}
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
