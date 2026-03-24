import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { Skeleton } from 'antd';
import AppLayout from './layouts/AppLayout';

const DocumentsPage = lazy(() => import('./pages/Documents'));
const ChatPage = lazy(() => import('./pages/Chat'));
const SettingsPage = lazy(() => import('./pages/Settings'));

function PageFallback() {
  return (
    <div style={{ padding: 32, maxWidth: 960, margin: '0 auto' }}>
      <Skeleton active paragraph={{ rows: 6 }} />
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/documents" replace /> },
      {
        path: 'documents',
        element: (
          <Suspense fallback={<PageFallback />}>
            <DocumentsPage />
          </Suspense>
        ),
      },
      {
        path: 'chat',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ChatPage />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<PageFallback />}>
            <SettingsPage />
          </Suspense>
        ),
      },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
