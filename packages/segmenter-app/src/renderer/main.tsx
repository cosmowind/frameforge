import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// 在开发模式下导入 Mock Electron API
import './mockElectron';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
