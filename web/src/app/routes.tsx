/** Route table. Every stateful view is deep-linkable. */

import { createBrowserRouter, Navigate } from 'react-router';
import { Shell } from './Shell';
import { NotFound } from './NotFound';
import { RootError } from './RootError';
import { Canvas } from '@/registers/canvas/Canvas';
import { PoolingWorkbench } from '@/registers/canvas/PoolingWorkbench';
import { WorkflowStudio } from '@/registers/canvas/WorkflowStudio';
import { Console } from '@/registers/console/Console';
import { Terminal } from '@/registers/terminal/Terminal';
import { Brief } from '@/registers/brief/Brief';
import { Cockpit } from '@/registers/cockpit/Cockpit';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    errorElement: <RootError />,
    children: [
      { index: true, element: <Navigate to="/canvas" replace /> },
      { path: 'canvas', element: <Canvas /> },
      { path: 'canvas/pooling', element: <PoolingWorkbench /> },
      { path: 'canvas/workflow/:workflowId', element: <WorkflowStudio /> },
      { path: 'console', element: <Console /> },
      { path: 'terminal', element: <Terminal /> },
      { path: 'brief', element: <Brief /> },
      { path: 'cockpit', element: <Cockpit /> },
      { path: 'cockpit/:entityId', element: <Cockpit /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
