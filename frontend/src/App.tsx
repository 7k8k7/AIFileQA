import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import DocumentsPage from './pages/Documents';
import ChatPage from './pages/Chat';
import SettingsPage from './pages/Settings';

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/documents" replace /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
