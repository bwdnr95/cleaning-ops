import React from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './app/App';
import { initSentry } from './observability';
import { AuthProvider } from './store/authStore';
import 'pretendard/dist/web/static/pretendard.css';
import './styles/global.css';
import './styles/app.css';

initSentry();

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>,
);
