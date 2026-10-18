import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { Providers } from './app/providers';
import { router } from './app/routes';
import './styles/globals.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root container is missing from index.html.');

createRoot(container).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
);
