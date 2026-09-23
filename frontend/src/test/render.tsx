import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createQueryClient } from '../app/queryClient'

export const renderApp = (ui: ReactElement) => render(<QueryClientProvider client={createQueryClient()}>{ui}</QueryClientProvider>)
