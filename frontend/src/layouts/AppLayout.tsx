import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Button, Tooltip } from 'antd';
import {
  FileTextOutlined,
  MessageOutlined,
  SettingOutlined,
  SunOutlined,
  MoonOutlined,
} from '@ant-design/icons';
import { useThemeStore } from '../stores/themeStore';
import styles from './AppLayout.module.css';

const navItems = [
  { path: '/documents', label: '文档管理', icon: <FileTextOutlined /> },
  { path: '/chat', label: '智能问答', icon: <MessageOutlined /> },
  { path: '/settings', label: '系统设置', icon: <SettingOutlined /> },
];

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useThemeStore();

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

          {/* Theme toggle */}
          <div className={styles.actions}>
            <Tooltip title={theme === 'light' ? '切换暗色模式' : '切换亮色模式'}>
              <Button
                type="text"
                className={styles.themeBtn}
                icon={theme === 'light' ? <MoonOutlined /> : <SunOutlined />}
                onClick={toggleTheme}
              />
            </Tooltip>
          </div>
        </div>
      </nav>

      {/* ── Page Content ── */}
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
