import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import zhCN from 'antd/locale/zh_CN';
import { antdLightTheme, antdDarkTheme } from './theme/tokens';
import { useThemeStore } from './stores/themeStore';
import App from './App';
import './global.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function Root() {
  const theme = useThemeStore((s) => s.theme);
  return (
    <ConfigProvider
      theme={theme === 'dark' ? antdDarkTheme : antdLightTheme}
      locale={zhCN}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Root />
    </QueryClientProvider>
  </StrictMode>,
);
